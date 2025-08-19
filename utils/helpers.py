
import logging
import os

# Setup logs directory
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logger
logger = logging.getLogger("crawler_logger")
logger.setLevel(logging.DEBUG)

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

def summarizer_func(summarizer, text: str) -> str:
    summarized = summarizer(
            text,
            max_length=350,
            min_length=15,
            do_sample=False
        )
    summarized_text = summarized[0]['summary_text']
    if not summarized_text:
        summarized_text = ""

    return summarized_text

def translator(translator, text: str) -> str:
    translated_text = translator(source='en', target='fa').translate(text)
    if not translated_text:
        translated_text = ""
    return translated_text