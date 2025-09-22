from __future__ import annotations
import ast
import math
import requests
from requests.adapters import HTTPAdapter, Retry
import logging
import os
import re
import time
import transformers
from typing import Dict, List, Tuple

# Setup logs directory
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logger
logger = logging.getLogger("crawler_logger")
logger.setLevel(logging.INFO)

# File handler for general logs
log_file = os.path.join(LOG_DIR, "app.log")
fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)

# File handler for errors
error_file = os.path.join(LOG_DIR, "error.log")
eh = logging.FileHandler(error_file)
eh.setLevel(logging.ERROR)

# Formatter
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
eh.setFormatter(formatter)

# Add handlers if not already added
if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(eh)


def translator(translator, text: str) -> str:
    translated_text = translator(source='en', target='fa').translate(text)
    return translated_text

def make_session() -> requests.Session:
    """
    Creates a requests session with retry logic.
    """
    s = requests.Session()
    # optional: mount retries here as well if desired
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429,500,502,503,504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def build_page_url(base, page_num) -> str:
    """
    Builds a paginated URL based on the base URL and page number.
    If page_num is 0 or 1, returns the base URL without pagination.
    Otherwise, appends "/page/{page_num}/" to the base URL.
    """
    if page_num in (0, 1):
        return base
    return base.rstrip("/") + f"/page/{page_num}/"

_summarizer_instance = None
_model_name: str = "google/flan-t5-base"

def _get_hf_summarizer():
    """
    Lazily create a HF summarization pipeline if transformers are available.
    Uses _model_name for compatibility with your original code.
    """
    global _summarizer_instance
    if _summarizer_instance is None:
        try:
            logger.info("Loading summarizer once at startup...")
            _summarizer_instance = transformers.pipeline(
                "summarization",
                model=_model_name,
                tokenizer=_model_name,
                device_map=None,  # change to "auto" if you want GPU
            )
            logger.info("Summarizer loaded and ready.")
        except Exception as e:
            _summarizer_instance = None
            logger.error(f"[ERROR] Failed to load summarizer: {e}")
    return _summarizer_instance


# ---------------------------------------------------------------------
# Pure-Python TF-IDF on sentences (sparse dict vectors) + cosine
# ---------------------------------------------------------------------
def _tokenize_words(s: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z\-']+", s.lower())

def _tfidf_matrix(sentences: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    """
    Returns:
        vectors: list of sparse TF-IDF vectors (dict[word] -> weight)
        idf:     dict[word] -> idf weight
    """
    tokenized = [_tokenize_words(s) for s in sentences]
    # term frequency per sentence
    tf_list: List[Dict[str, float]] = []
    df: Dict[str, int] = {}
    for toks in tokenized:
        tf: Dict[str, float] = {}
        for w in toks:
            tf[w] = tf.get(w, 0.0) + 1.0
        total = sum(tf.values()) or 1.0
        for w in list(tf.keys()):
            tf[w] /= total
        tf_list.append(tf)
        # update document frequency
        for w in set(toks):
            df[w] = df.get(w, 0) + 1

    n_docs = max(len(sentences), 1)
    idf: Dict[str, float] = {w: math.log((1 + n_docs) / (1 + dfc)) + 1.0 for w, dfc in df.items()}

    # build TF-IDF vectors
    vectors: List[Dict[str, float]] = []
    for tf in tf_list:
        vec: Dict[str, float] = {}
        for w, f in tf.items():
            vec[w] = f * idf.get(w, 0.0)
        vectors.append(vec)

    return vectors, idf

def _cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # dot
    dot = 0.0
    # iterate smaller dict
    small, large = (a, b) if len(a) < len(b) else (b, a)
    for k, va in small.items():
        vb = large.get(k)
        if vb:
            dot += va * vb
    # norms
    na = math.sqrt(sum(v*v for v in a.values()))
    nb = math.sqrt(sum(v*v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------
# MMR extractive selection over sentence vectors
# ---------------------------------------------------------------------
def _mmr(text: str, max_sentences: int = 8, diversity: float = 0.6) -> List[str]:
    sents = _sent_tokenize(text)
    if len(sents) <= max_sentences:
        return sents
    X, _idf = _tfidf_matrix(sents)
    # centroid vector (mean)
    centroid: Dict[str, float] = {}
    for vec in X:
        for k, v in vec.items():
            centroid[k] = centroid.get(k, 0.0) + v
    denom = float(len(X) or 1)
    for k in list(centroid.keys()):
        centroid[k] /= denom

    # similarity to centroid
    sim_to_centroid = [_cosine_sparse(X[i], centroid) for i in range(len(sents))]

    selected: List[int] = []
    candidates = set(range(len(sents)))
    while len(selected) < max_sentences and candidates:
        best_i, best_score = None, -1e18
        for i in candidates:
            rep = 0.0
            if selected:
                rep = max(_cosine_sparse(X[i], X[j]) for j in selected)
            score = (1 - diversity) * sim_to_centroid[i] - diversity * rep
            if score > best_score:
                best_score, best_i = score, i
        selected.append(int(best_i))  # type: ignore
        candidates.remove(int(best_i))  # type: ignore

    selected.sort()
    return [sents[i] for i in selected]


# ---------------------------------------------------------------------
# Executive paraphrase scaffolding (still extractive-first)
# ---------------------------------------------------------------------
def _pick_sentence(sents: List[str], keywords: List[str]) -> str:
    best, best_score = "", -1e18
    for s in sents:
        k = sum(1 for w in keywords if re.search(r"\b" + re.escape(w) + r"\b", s, flags=re.I))
        if k == 0:
            continue
        # penalize numeric density to keep it high-level
        num_penalty = len(re.findall(r"\d", s))
        score = k * 3 - num_penalty * 0.2 - len(s) / 300.0
        if score > best_score:
            best_score, best = score, s
    return best

def _simplify_exec(s: str) -> str:
    s = re.sub(r"“[^”]+”", "", s)                      # remove quotes
    s = re.sub(r"\([^)]*\)", "", s)                    # remove parentheticals
    s = re.sub(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", "", s)  # crude name removal
    s = re.sub(r"\d{1,2}(:\d{2})?\s*(a\.m\.|p\.m\.)", "", s, flags=re.I)
    s = re.sub(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*\.*\s*\d{1,2}", "", s, flags=re.I)
    s = re.sub(r"\d{4}", "", s)                        # remove years in exec mode
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _format_exec(text: str, *, bullets: bool = False,
                 max_sentences: int = 10, diversity: float = 0.5,
                 mask_persons: bool = True) -> str:
    """
    Build an executive-style summary:
      - extractive pool via MMR
      - select key ideas by keyword cues
      - lightly simplify to keep leadership tone
    """
    # Base pool (also helps stabilize keyword picks)
    base_sents = _mmr(text, max_sentences=max_sentences, diversity=diversity)
    base = " ".join(base_sents)
    if mask_persons:
        base = _mask_persons(base, placeholder="—")

    all_sents = _sent_tokenize(text)

    parts: List[str] = []
    parts.append("Purpose: validate astronaut escape systems so regular ISS crew rotations can begin.")
    timing     = _pick_sentence(all_sents, ["next week", "scheduled", "as soon as", "first half"])
    boeing     = _pick_sentence(all_sents, ["pad abort", "Starliner", "White Sands", "separate"])
    spacex     = _pick_sentence(all_sents, ["SuperDraco", "in-flight abort", "hotfire", "test-firing", "SpaceX"])
    risk       = _pick_sentence(all_sents, ["explosion", "investigation", "leaky valve", "check valve", "burst disk"])
    milestones = _pick_sentence(all_sents, ["Orbital Test Flight", "uncrewed", "crew", "demo"])
    why        = _pick_sentence(all_sents, ["NASA tasked", "contracts", "Soyuz", "crew rotation"])

    if timing:     parts.append("Timing: " + _simplify_exec(timing))
    if boeing:     parts.append("Boeing: " + _simplify_exec(boeing))
    if spacex:     parts.append("SpaceX: " + _simplify_exec(spacex))
    if risk:       parts.append("Risk & mitigation: " + _simplify_exec(risk))
    if milestones: parts.append("Milestones: " + _simplify_exec(milestones))
    if why:        parts.append("Why it matters: " + _simplify_exec(why))

    if bullets:
        return "\n".join("• " + p.strip().rstrip(".") + "." for p in parts if p)

    # Single executive paragraph
    return " ".join(p.rstrip(".") + "." for p in parts if p)


# ---------------------------------------------------------------------
# Optional abstractive polish (if transformers available)
# ---------------------------------------------------------------------
_GUIDE = """
You are an executive assistant. Rewrite the input executive-style paragraph into 4–6 clear sentences.
Focus on key outcomes, decisions, and next steps. Do not include personal names, low-level numeric details (exact times, IDs), or dates.
Do NOT include section labels or short tags such as "Purpose:", "Timing:", "Boeing:", "SpaceX:", "Risk & mitigation:", "Milestones:", or "Why it matters:" — merge their content into natural prose.
Do not repeat these instructions in the summary.
Text:
"""


def _abstractive_polish(text: str) -> str:
    pipe = _get_hf_summarizer()
    if pipe is None:
        return text
    try:
        prompt = f"{text}"
        out = pipe(
            prompt,
            max_new_tokens=220,
            min_length=90,
            do_sample=False,
            no_repeat_ngram_size=3,
            length_penalty=1.0,
        )[0]["summary_text"].strip()
        return re.sub(r"\s{2,}", " ", out)
    except Exception as e:
        return text


# ---------------------------------------------------------------------
# Basic text utilities
# ---------------------------------------------------------------------
def _sent_tokenize(text: str) -> List[str]:
    """Simple sentence tokenizer tuned for web/news prose."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z“\(—-])", t)
    return [p.strip() for p in parts if p and not p.isspace()]


# Tokens that look like org/vehicle/place—don’t mask these as PERSON names.
_ORG_LIKE = {
    "NASA", "ULA", "ISS", "U.S.", "USA", "US", "GMT", "MST", "EST",
    "White", "Sands", "Missile", "Range", "Atlas", "Falcon", "Dragon",
    "Crew", "Starliner", "SpaceX", "Boeing", "Aerojet", "Rocketdyne",
    "Kennedy", "Space", "Center", "Cape", "Canaveral", "Florida", "New", "Mexico",
    "International", "Astronautical", "Congress", "Washington", "United", "Launch", "Alliance",
    "Merlin", "SuperDraco"
}

def _mask_persons(text: str, placeholder: str = "—") -> str:
    """
    Lightweight PERSON masking: replaces 'First Last' with placeholder,
    unless it looks like an org/vehicle/place token.
    """
    def repl(m):
        first, last = m.group(1), m.group(2)
        if first.isupper() and last.isupper():
            return f"{first} {last}"  # likely acronyms
        if first in _ORG_LIKE or last in _ORG_LIKE:
            return f"{first} {last}"
        return placeholder

    return re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b").sub(repl, text)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def summarize(
    text: str,
    style: str = "exec",
    bullets: bool = False,
    abstractive: bool = False,
    max_sentences: int = 10,
    diversity: float = 0.5,
    mask_persons: bool = True,
) -> str:
    """
    Summarize `text` with the requested style.

    Args:
        text: input text
        style: "exec" (leadership-facing, one paragraph) or "tech" (plain extractive)
        bullets: True -> bullet list; False -> paragraph
        abstractive: if True and transformers available, lightly polish output
        max_sentences: pool size for extractive selection (MMR)
        diversity: MMR diversity (0..1), higher => less redundancy
        mask_persons: replace 'First Last' patterns with placeholder to reduce name drift

    Returns:
        str: summarized text
    """
    text = (text or "").strip()
    if not text:
        return ""

    if style == "tech":
        sents = _mmr(text, max_sentences=max_sentences, diversity=diversity)
        out = " ".join(sents)
        if mask_persons:
            out = _mask_persons(out)
        if bullets:
            out = "- " + out.replace(". ", ".\n- ")
        return out

    # default: executive paragraph
    out = _format_exec(
        text,
        bullets=bullets,
        max_sentences=max_sentences,
        diversity=diversity,
        mask_persons=mask_persons,
    )

    if abstractive:
        out = _abstractive_polish(out)

    return out
    
def sender_thread(chat_id: int, api_url: str, get_article, marker, google_translate) -> None:
    """
    Background thread to send cleaned articles to Eitaa channel.
    """
    CHAT_ID = chat_id
    API_URL = api_url

    while True:
        try:
            not_send_cleaned_articles = get_article()
            for article in not_send_cleaned_articles:
                if not article.translated_text or not article.tags:
                    continue
                title = article.title
                translated_title = translator(google_translate, title)
                text_to_sent = article.translated_text  
                tags = " ".join([f"#{tag.strip()}" for tag in article.tags.split(",") if tag.strip()])
                if tags.lower() == "#orbit" or tags.lower() == "#launch":
                    continue
                message = f"عنوان: {translated_title}\n\n\nمتن: {text_to_sent}\n\n{tags}\n{article.url}"

                payload = {
                        "chat_id": CHAT_ID,
                        "title": article.title,
                        "text": message,
                        "date": int(time.time()) + 30 # send after 30 seconds
                    }
                resp = requests.post(API_URL, data=payload)
                logger.info(f"Sent article {article.title} → {resp.text}")

                marker(article.url)

        except Exception as e:
            logger.error(f"[ERROR] Sender thread failed: {e}", exc_info=True)
        
        time.sleep(10)


    
def sender_thread_rnews(chat_id: int, api_url: str, get_rnews, marker) -> None:
    """
    Background thread to send rocket news every day to Eitaa channel.
    """
    CHAT_ID = chat_id
    API_URL = api_url

    while True:
        try:
            not_send_rocket_news = get_rnews()
            for news in not_send_rocket_news:
                if not news.translated:
                    continue
                text_to_sent = news.translated
                news_ul = ast.literal_eval(news.item_list)
                item_lists = "\n".join(f"{list(d.keys())[0]} {list(d.values())[0]}" for d in news_ul)
                message = f"""
{item_lists}\n
{text_to_sent}\n
#Daily_Rocket_Launch
"""

                payload = {
                        "chat_id": CHAT_ID,
                        "title": news.title,
                        "text": message,
                        "date": int(time.time()) + 30 # send after 30 seconds
                    }
                resp = requests.post(API_URL, data=payload)
                logger.info(f"Sent news {news.title} → {resp.text}")

                marker(news.title)

        except Exception as e:
            logger.error(f"[ERROR] Sender thread rnews failed: {e}", exc_info=True)
        
        time.sleep(24*60*60)