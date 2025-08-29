import requests
import random
from crawler.fetcher import get_soup
from crawler.parser import exctract_articles, exctract_full_description, check_article, extract_tags
from db.database import create_tables, raw_article_exists, insert_raw_article, get_uncleaned_articles, insert_cleaned_article, get_not_send_cleaned_articles, mark_article_sent
from db.models import Article, CleanArticle
from utils.helpers import summarizer_func, translator, logger, build_page_url, make_session, get_summarizer, sender_thread
from config import webs, USER_AGENTS, FAST_INTERVAL, FAST_PAGES, BACKFILL_INTERVAL, REQUEST_MAX, REQUEST_MIN, API_URL, CHAT_ID
from deep_translator import GoogleTranslator
import threading
import time



def cleaner_thread(summarizer: get_summarizer = None) -> None:
    """
    Background thread to clean and summarize & translate articles.
    """
    try:
        summarizer = summarizer
        if summarizer is None:
            logger.warning("Summarizer unavailable — continuing without summarization.")
    except Exception as e:
        logger.error(f"[ERROR] Failed to get summarizer: {e}")
        summarizer = None
    
    while True:
        try:
            uncleaned = get_uncleaned_articles()
            for article in uncleaned:
                if check_article(article._asdict()):
                    print("*********checked********")
                    if article.source == "spacenews":
                        text = article.description.split("\n")[0]
                        article = article._replace(description=text)

                    if summarizer:
                        try:
                            summarized_text = summarizer_func(summarizer, article.description)
                        except Exception as e:
                            logger.error(f"Summarizer failed. Title: {article.title}")
                            summarized_text = ""
                    try:
                        translated_text = translator(GoogleTranslator, summarized_text)
                    except Exception as e:
                        logger.error(f"Translator failed. Title: {article.title}")
                        translated_text = ""

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
            logger.error(f"[ERROR] Cleaner thread failed: {e}")
        time.sleep(10)

def crawl_site_once(session: requests.Session, web_key: str, page_num: int) -> None:
    """
    Crawls a single page of the specified website and processes articles.
    """
    web = webs[web_key]
    url = build_page_url(web["link"], page_num)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    soup = get_soup(url, session=session, headers=headers)
    if not soup :
        return
    articles = exctract_articles(soup, web)
    for article in articles:
        try:
            if article['url'] == "" or not article['url'].startswith("http"):
                logger.warning(f"Skipping article with invalid URL: {article['url']}")
                continue
            if raw_article_exists(article['url']):
                continue
            detail_soup = get_soup(article['url'], session=session, headers=headers)
            if not detail_soup:
                continue
            if web["type"] == 2:
                content = exctract_full_description(detail_soup, class_=web["desc-tag"], id=None)
            else:
                content = exctract_full_description(detail_soup, id=web["desc-tag"], class_=None)
            art = Article(
                title=article['title'],
                url=article['url'],
                date=article['date'],
                description=content,
                source=web_key
            )
            insert_raw_article(art)
            logger.info(f"Article processed: {article['title']}")
            time.sleep(random.uniform(REQUEST_MIN, REQUEST_MAX))
        except Exception as e:
            logger.error(f"[ERROR] Failed to process article {article['title']}: {e}")
            continue


def main():
    create_tables()
    summarizer = get_summarizer()
    t = threading.Thread(target=cleaner_thread, args=(summarizer,), daemon=True)
    t.start()

    t2 = threading.Thread(target=sender_thread, args=(CHAT_ID, API_URL, get_not_send_cleaned_articles, mark_article_sent), daemon=True)
    t2.start()

    session = make_session()
    while True:
        for web_key in webs:
            pages = min(FAST_PAGES, webs[web_key].get("pages", FAST_PAGES))
            for page_num in range(1, pages + 1):
                try:
                    crawl_site_once(session, web_key, page_num)
                except Exception as e:
                    logger.error(f"Fast poll failed for {web_key} page {page_num}: {e}")
                time.sleep(random.uniform(REQUEST_MIN, REQUEST_MAX))
        time.sleep(FAST_INTERVAL)

        for web_key in webs:
            total = webs[web_key].get("pages", 1)
            for page_num in range(FAST_PAGES + 1, total + 1):
                try:
                    crawl_site_once(session, web_key, page_num)
                except Exception as e:
                    logger.error(f"Backfill poll failed for {web_key} page {page_num}: {e}")
                time.sleep(random.uniform(3.0, 9.0))
        time.sleep(BACKFILL_INTERVAL)

                

if __name__ == "__main__":
    main()