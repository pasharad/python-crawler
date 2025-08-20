from crawler.fetcher import get_soup
from crawler.parser import exctract_articles, exctract_full_description, check_article, extract_tags
from db.database import create_tables, raw_article_exists, insert_raw_article, get_uncleaned_articles, insert_cleaned_article, get_cleaned_articles
from db.models import Article, CleanArticle
from utils.helpers import summarizer_func, translator, logger
from config import webs
from transformers import pipeline
from deep_translator import GoogleTranslator
import threading
import time



def cleaner_thread():
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    except Exception as e:
        logger.error(f"[ERROR] Failed to load summarizer: {e}", exc_info=True)
        summarizer = None
    while True:
        try:
            uncleaned = get_uncleaned_articles()
            for article in uncleaned:
                if check_article(article._asdict()):
                    if article.source == "spacenews":
                        text = article.description.split("\n")[0]
                        article = article._replace(description=text)

                    
                    if summarizer:
                        try:
                            summarized_text = summarizer_func(summarizer, article.description)
                        except Exception as e:
                            logger.error(f"Summarizer failed {article.title}", exc_info=True)
                    try:
                        translated_text = translator(GoogleTranslator, summarized_text)
                    except Exception as e:
                        logger.error(f"Translator failed {article.title}", exc_info=True)

                    tags = extract_tags(article.description)

                    cleaned_article = CleanArticle(
                            title=article.title,
                            url=article.url,
                            date=article.date,
                            description=article.description,
                            summery=summarized_text,
                            translated_text=translated_text,
                            source=article.source,
                            tags=", ".join(tags)
                            
                    )
                    insert_cleaned_article(cleaned_article)
                    logger.info(f"translated: {translated_text}")
        except Exception as e:
            logger.error(f"[ERROR] Cleaner thread failed: {e}", exc_info=True)
        time.sleep(10)

def main():
    create_tables()

    t = threading.Thread(target=cleaner_thread, daemon=True)
    t.start()

    for web in webs:
        for page_num in range(1, webs[web]["pages"]):
            if page_num > 1:
                webs[web]["link"] += f"page/{page_num}"
            soup = get_soup(webs[web]["link"])

            if soup:
                articles = exctract_articles(soup, webs[web])
                for article in articles:
                    if raw_article_exists(article['url']):
                        continue

                    detail_soup = get_soup(article['url'])
                    if webs[web]["type"] == 2:
                        content = exctract_full_description(detail_soup, class_=webs[web]["desc-tag"], id=None)
                    else:
                        content = exctract_full_description(detail_soup, id=webs[web]["desc-tag"], class_=None)

                    article_obj = Article(
                        title=article['title'],
                        url=article['url'],
                        date=article['date'],
                        description=content,
                        source=web
                    )
                    insert_raw_article(article_obj)
                    time.sleep(5)
            if page_num > 1 and page_num < 10:
                webs[web]["link"] = webs[web]["link"][:-6]
            elif page_num > 9 and page_num < 100:
                webs[web]["link"] = webs[web]["link"][:-7]
            elif page_num > 99 and page_num < 1000:
                webs[web]["link"] = webs[web]["link"][:-8]
            elif page_num > 999 and page_num < 10000:
                webs[web]["link"] = webs[web]["link"][:-9]
                

if __name__ == "__main__":
    main()