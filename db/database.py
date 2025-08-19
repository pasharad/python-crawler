import sqlite3
from typing import Optional
from db.models import Article, CleanArticle
from utils.helpers import logger

DB_PATH = "data/news.db"

def connect():
    return sqlite3.connect(DB_PATH)

def create_tables():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS articles_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            date TEXT,
            description TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, '+3 hours', '+30 minutes'))
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS articles_cleaned (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            date TEXT,
            description TEXT,
            summery TEXT,
            translated_text TEXT,
            source TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, '+3 hours', '+30 minutes'))
        )""")
        conn.commit()

def raw_article_exists(url: str) -> bool:
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM articles_raw WHERE url = ?", (url,))
        return c.fetchone() is not None

def insert_raw_article(article: Article):
    with connect() as conn:
        c = conn.cursor()
        try:
            c.execute("""
            INSERT INTO articles_raw (title, url, date, description, source)
            VALUES (?, ?, ?, ?, ?)""",
            (article.title, article.url, article.date, article.description, article.source))
            conn.commit()
            logger.info(f"New article inserted: {article.title}")
        except sqlite3.IntegrityError:
            pass

def insert_cleaned_article(article: CleanArticle):
    with connect() as conn:
        c = conn.cursor()
        try:
            c.execute("""
            INSERT INTO articles_cleaned (title, url, date, description, summery, translated_text, source, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (article.title, article.url, article.date, article.description, article.summery, article.translated_text, article.source, article.tags))
            conn.commit()
            logger.info(f"Article cleaned and saved: {article.title}")
        except sqlite3.IntegrityError:
            pass


def get_uncleaned_articles():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        SELECT r.title, r.url, r.date, r.description, r.source
        FROM articles_raw r
        LEFT JOIN articles_cleaned c ON r.url = c.url
        WHERE c.url IS NULL
        """)
        rows = c.fetchall()
        return [Article(*row) for row in rows]

def get_cleaned_articles():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        SELECT *
        FROM articles_cleaned c
        """)
        rows = c.fetchall()
        return [Article(*row) for row in rows]