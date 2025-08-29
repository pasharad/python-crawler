import requests
from requests.adapters import HTTPAdapter, Retry
import logging
import os
import time
from transformers import AutoTokenizer, pipeline

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

tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")

def chunk_text_by_tokens(text, tokenizer, max_tokens=900):
    tokens = tokenizer.encode(text, truncation=False)
    for i in range(0, len(tokens), max_tokens):
        yield tokenizer.decode(tokens[i:i+max_tokens], skip_special_tokens=True)

def summarizer_func(summarizer, text: str) -> str:
    max_len = len(text.split())
    if max_len > 1000:
        summaries = []
        for chunk in chunk_text_by_tokens(text, tokenizer, max_tokens=800):
            try:
                if len(chunk.split()) < 30:
                    summaries.append(chunk)
                    continue
                if len(chunk.split()) < 150:
                    summaries.append(chunk)
                    continue
                summarized = summarizer(
                    chunk,
                    max_length=150,
                    min_length=15,
                    truncation=True,
                    max_new_tokens=150
                )
                if summarized and isinstance(summarized, list) and len(summarized) > 0:
                    summaries.append(summarized[0].get('summary_text', chunk))
                else:
                    logger.warning("Summarizer returned empty result, using fallback text.")
                    summaries.append(chunk)
            except Exception as e:
                logger.error(f"Error summarizing chunk: {e}")
        final_summary = " ".join(summaries)
        return final_summary
    else:
        try:
            if len(text.split()) < 50:
                return text
            summarized = summarizer(
                text,
                max_length=150,
                min_length=30,
                do_sample=False,
                truncation=True,
                max_new_tokens=150
            )
            if summarized and isinstance(summarized, list) and len(summarized) > 0:
                return summarized[0].get('summary_text', text)
            else:
                logger.warning("Summarizer returned empty result for short text.")
                return text
        except Exception as e:
            logger.error(f"Error summarizing text: {e}")
            return ""

def translator(translator, text: str) -> str:
    if len(text) > 5000:
        translated_chunks = []
        for chunk in chunk_text_by_tokens(text, max_tokens=5000):
            try:
                translated_chunk = translator(source='en', target=chunk)
                translated_chunks.append(translated_chunk)
            except Exception as e:
                logger.error(f"[ERROR] failed to translating chunk: {e}")
        final_translation = " ".join(translated_chunks)
        return final_translation
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
_model_name: str = "facebook/bart-large-cnn"

def get_summarizer() -> pipeline:
    """
    Loads and returns a summarization pipeline once (singleton pattern).
    """
    global _summarizer_instance
    try:
        if _summarizer_instance is None:
            logger.info("Loading summarizer once at startup...")
            _summarizer_instance = pipeline("summarization", model=_model_name, device=-1)
            logger.info("Summarizer loaded and ready.")
        return _summarizer_instance
    except Exception as e:
        logger.error(f"[ERROR] Failed to load summarizer: {e}")
        return None
    
def sender_thread(chat_id: int, api_url: str, get_article, marker) -> None:
    """
    Background thread to send cleaned articles to Eitaa channel.
    """
    CHAT_ID = chat_id
    API_URL = api_url

    while True:
        try:
            not_send_cleaned_articles = get_article()
            for article in not_send_cleaned_articles:
                if not article.translated_text:
                    continue
                text_to_sent = article.translated_text  
                tags = " ".join([f"#{tag.strip()}" for tag in article.tags.split(",") if tag.strip()])
                message = f"{text_to_sent}\n\n{tags}\n{article.url}"

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


    
