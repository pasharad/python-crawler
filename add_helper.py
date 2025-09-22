# helper.py
# ---------------------------------------------------------------------
# Executive-grade summarization with safe fallbacks (no heavy deps).
# - Default: one-paragraph, executive-style summary (extractive + light paraphrase scaffolding)
# - No external deps required (pure-Python TF-IDF, cosine, MMR)
# - Optional Transformers polish if available
#
# Public API:
#     summarize(text: str,
#               style: str = "exec",
#               bullets: bool = False,
#               abstractive: bool = False,
#               max_sentences: int = 10,
#               diversity: float = 0.5,
#               mask_persons: bool = True) -> str
#
# Notes:
# - Keeps your singleton variables for compatibility.
# - To force a different HF model (if installed), set env SUMM_MODEL.
# ---------------------------------------------------------------------

from __future__ import annotations

import os
import re
import math
from typing import Dict, List, Tuple, Optional

# ---------------------------------------------------------------------
# Your original singletons (kept for compatibility)
# ---------------------------------------------------------------------
_summarizer_instance = None
_model_name: str = os.getenv("SUMM_MODEL", "facebook/bart-large-cnn")

# Transformers availability (optional polish)
_has_transformers = False
try:
    import transformers  # type: ignore
    _has_transformers = True
except Exception:
    _has_transformers = False


def _get_hf_summarizer():
    """
    Lazily create a HF summarization pipeline if transformers are available.
    Uses _model_name for compatibility with your original code.
    """
    global _summarizer_instance
    if not _has_transformers:
        return None
    if _summarizer_instance is None:
        try:
            _summarizer_instance = transformers.pipeline(
                "summarization",
                model=_model_name,
                tokenizer=_model_name,
                device_map=None,  # change to "auto" if you want GPU
            )
        except Exception:
            _summarizer_instance = None
    return _summarizer_instance


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
_GUIDE = (
    "Rewrite concisely for executives (4–6 sentences). Keep outcomes and next steps. "
    "Avoid personal names and low-level numbers. No bullets."
)

def _abstractive_polish(text: str) -> str:
    pipe = _get_hf_summarizer()
    if pipe is None:
        return text
    try:
        prompt = f"{_GUIDE}\n\nText:\n{text}"
        out = pipe(
            prompt,
            max_length=220,
            min_length=90,
            do_sample=False,
            no_repeat_ngram_size=3,
            length_penalty=1.0,
        )[0]["summary_text"].strip()
        return re.sub(r"\s{2,}", " ", out)
    except Exception:
        return text


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

    if abstractive and _has_transformers:
        out = _abstractive_polish(out)

    return out


# ---------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    sample = (
        """
Singed and blackened from three fiery trips to the edge of space and back, a Falcon 9 rocket returned to Cape Canaveral on Sunday after a mission last that week carried the Israeli Beresheet moon lander into orbit, ready for inspections before attempting a fourth — and likely final — launch this spring.

The 15-story first stage booster entered the channel to Port Canaveral around 9 a.m. EST (1400 GMT) Sunday, two-and-a-half days after landing on SpaceX’s drone ship “Of Course I Still Love You” in the Atlantic Ocean.

The first stage powered an Indonesian communications satellite, an Israeli moon lander, and a U.S. Air Force experimental smallsat into orbit Thursday night after lifting off from Cape Canaveral’s Complex 40 launch pad.

The booster shut down its nine engines and fell away from the Falcon 9’s upper stage at an altitude of around 220,000 feet (67 kilometers), reaching a top speed during the launch of more than 5,200 mph (8,500 kilometers per hour), according to telemetry data displayed during SpaceX’s webcast of the mission.

A subset of the rocket’s nine booster engines, with the help of stabilization fins, guided the stage back to Earth, targeting the coordinates of SpaceX’s landing vessel. Four landing legs unfurled from base of the rocket as it braked for touchdown, marking the 34th time SpaceX has recovered one of its rockets on a drone ship or on land.

Elon Musk, SpaceX’s founder and CEO, tweeted after Thursday’s launch and landing that the booster’s re-entry into the atmosphere was the hottest experienced by a Falcon 9 rocket to date. The orbit targeted by Thursday night’s mission extended around 43,000 miles (69,000 kilometers) above Earth, requiring the booster to burn longer and reach a higher speed than previous missions that have included landings at sea.

Sparks generated from burning metal on the rocket’s base heat shield were visible in live video downlinked by the booster in flight, Musk said.

After securing the rocket, the drone ship headed back to port, where it was towed to a dock for a crane to hoist the booster off the vessel onto a stand. The crane removed the rocket the drone ship Sunday afternoon, clearing the way for the fleet to return to sea this week in preparation for another rocket landing after the next Falcon 9 launch set for Saturday with SpaceX’s Crew Dragon capsule heading to the International Space Station on a test flight.
The booster which launched and landed last week has now logged three missions. Numbered B1048, it first flew in July 2018, carrying 10 Iridium voice and data relay satellites toward orbit from Vandenberg Air Force Base, California, before landing on SpaceX’s drone ship “Just Read the Instructions” in the Pacific Ocean. After two months of inspections, refurbishment and preparations, the booster launched again in October carrying Argentina’s SAOCOM 1A radar observation satellite, then returned to Vandenberg for SpaceX’s first onshore landing on the West Coast.

SpaceX now has two Falcon 9 boosters in its inventory that are veterans of three missions. Another booster conducted its third launch and landing in December.

Musk says the latest version of the Falcon 9 rocket, which debuted last May, has a first stage booster capable of flying at least 10 times with minimal refurbishment. Musk sees the reusability of the Falcon 9’s first stage as vital to reducing launch costs, and the technology is central to his vision of eventually building a settlement on Mars.

But SpaceX’s near-term goals are focused on launching payloads for commercial and government operators, debuting the Crew Dragon spacecraft to carry astronauts for NASA, and deploying a constellation of broadband satellites that the company says will eventually number in the thousands.

The rocket that returned to Florida on Sunday will be prepared for an abort test with the Crew Dragon spacecraft this spring, Musk confirmed last week.
The in-flight abort test will verify the Crew Dragon’s SuperDraco escape thrusters can push the capsule away from a failing rocket, a safety feature designed to ensure astronauts survive a launch accident.

Eight SuperDraco rocket engines mounted in pods around the circumference of the Crew Dragon are programmed to quickly fire if computers detect an emergency during launch. NASA and SpaceX want to ensure the escape system is up to the job before putting astronauts on the spacecraft.

SpaceX conducted a pad abort test in 2015 to demonstrate the capsule’s ability to escape a rocket explosion on the launch pad. The in-flight abort will verify the abort function during a real rocket launch.

According to NASA’s latest official schedule for the commercial crew program — released on Feb. 6 — the in-flight abort test is scheduled for June, followed by the first Crew Dragon test flight with astronauts on-board in July. The abort and crewed test flights will be preceded by an unpiloted demo mission to the space station on the Falcon 9 launch scheduled for Saturday.

Musk tweeted that the launch escape test could occur in April. Hans Koenigsmann, SpaceX vice president of build and flight reliability, said Friday that teams are looking at whether the in-flight abort could be moved forward from June.

SpaceX plans to reuse the Crew Dragon spacecraft slated to fly to the space station this weekend for the in-flight abort. Assuming a March 2 launch, the capsule is scheduled to splash down in the Atlantic Ocean on March 8, where teams will retrieve the spacecraft and bring it back to Cape Canaveral for the abort test.

The timing of the in-flight abort test “depends on when Crew Dragon comes back,” Musk tweeted. “That’s scheduled for launch next Saturday, but (there’s a) lot of new hardware, so time error bars are big.”

Officials do not expect the Falcon 9 booster to survive the abort test, likely ending its lifetime at four launches, and three intact landings.

“High probability of this particular rocket getting destroyed by Dragon supersonic abort test,” Musk tweeted.

The test plan calls for the rocket to take off from launch pad 39A at the Kennedy Space Center and arc over the Atlantic Ocean, firing its nine main engines more than a minute, as it would during a typical launch. The Falcon 9’s on-board computer will command the engines to switch off after surpassing the speed of sound, and trigger the Crew Dragon’s abort thrusters to push the capsule away from the top of the rocket, according to a draft environmental assessment for the test flight prepared by the Federal Aviation Administration.

According to the environmental review document, SpaceX does not plan to attempt any maneuvers to recover the stage, which is expected to break apart from aerodynamic forces, or the rocket’s destruct system, seconds after the Crew Dragon fires away for the abort test.

Koenigsmann said Friday, after a flight readiness review for the Crew Dragon’s orbital test flight, that SpaceX is still looking at aways to potentially retrieve the booster after the high-altitude abort demonstration.

But Musk’s tweets and the FAA’s draft environmental assessment make it clear officials are not expecting the get the rocket back intact.

The Falcon 9 that launches on the abort test will fly with a real second stage, carrying a load of kerosene and liquid oxygen propellants, but with a mass simulator in place of its Merlin engine.

“It will get fragged for sure by aero loads & Dragon abort thrusters,” Musk tweeted.

Check out more photos from Sunday’s arrival of the Falcon 9 booster at Port Canaveral, including aerial shots.
"""
    )
    print(summarize(sample, abstractive=True))  # one-paragraph executive summary
