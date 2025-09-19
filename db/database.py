import sqlite3
from db.models import Article, CleanArticle, RocketNews
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
            sent BOOL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, '+3 hours', '+30 minutes'))
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS match_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,     -- واژه/عبارت یا الگوی ساده
            tag TEXT NOT NULL,         -- تگ مقصد
            enabled BOOL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, '+3 hours', '+30 minutes'))
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS rocket_launch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, 
            item_list TEXT NOT NULL,         
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            translated TEXT NOT NULL,
            sent BOOL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, '+3 hours', '+30 minutes'))
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_cleaned_sent ON articles_cleaned(sent)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_articles_cleaned_tags ON articles_cleaned(tags)")
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
            SELECT r.title, r.url, r.date, r.description, r.summery, r.translated_text, r.source, r.tags
            """)
        rows = c.fetchall()
        return [CleanArticle(*row) for row in rows]
    
def update_cleaned_articles(tags: str, url:str):
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
                UPDATE articles_cleaned SET tags=? where url=?
                """, (tags, url))
        conn.commit()

def get_not_send_cleaned_articles():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        SELECT c.title, c.url, c.date, c.description, c.summery, c.translated_text, c.source, c.tags
        FROM articles_cleaned c
        WHERE c.sent = FALSE
        """)
        rows = c.fetchall()
        return [CleanArticle(*row) for row in rows]
    
def mark_article_sent(url: str):
    with connect() as conn:
        c = conn.cursor()
        try:    

            c.execute("""
            UPDATE articles_cleaned
            SET sent = TRUE
            WHERE url = ?
            """, (url, ))
            conn.commit()

        except sqlite3.IntegrityError:
            pass

def get_counts_and_tags_breakdown():
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM articles_raw")
        total_raw = c.fetchone()[0] or 0

        c.execute("SELECT COUNT(*) FROM articles_cleaned")
        total_cleaned = c.fetchone()[0] or 0

        # استخراج فراوانی تگ‌ها از ستون tags که CSV است
        c.execute("SELECT COALESCE(tags,'') FROM articles_cleaned")
        rows = c.fetchall()

        from collections import Counter
        counter = Counter()
        for (tags_csv,) in rows:
            if not tags_csv:
                continue
            for t in [x.strip() for x in tags_csv.split(",") if x.strip()]:
                counter[t] += 1

        breakdown = [{"tag": k, "count": v} for k, v in counter.most_common()]
        return total_raw, total_cleaned, breakdown
    

def rules_all():
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id, pattern, tag, enabled FROM match_rules ORDER BY id DESC")
        return c.fetchall()

def rules_create(pattern: str, tag: str, enabled: bool=True):
    with connect() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO match_rules (pattern, tag, enabled) VALUES (?, ?, ?)",
                  (pattern.strip(), tag.strip(), enabled))
        conn.commit()
        return c.lastrowid

def rules_update(rule_id: int, pattern: str, tag: str, enabled: bool):
    with connect() as conn:
        c = conn.cursor()
        c.execute("UPDATE match_rules SET pattern=?, tag=?, enabled=? WHERE id=?",
                  (pattern.strip(), tag.strip(), enabled, rule_id))
        conn.commit()

def rules_delete(rule_id: int):
    with connect() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM match_rules WHERE id=?", (rule_id,))
        conn.commit()

def rocket_lunch_exists(title: str) -> bool:
    """Return True if url already stored in rocket_launch table."""
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM rocket_launch WHERE title = ?", (title,))
        row = c.fetchone()
        return row is not None

def insert_rocket_lunch(rocket_news: RocketNews) -> None:
    """Insert a rocket launch record into DB."""
    with connect() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO rocket_launch (title, item_list, description, date, translated) VALUES (?, ?, ?, ?, ?)",
                   (rocket_news.title, rocket_news.item_list, rocket_news.description, rocket_news.date, rocket_news.translated))
        conn.commit()

def get_not_send_rocket_news():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        SELECT r.title, r.item_list, r.description, r.date, r.translated
        FROM rocket_launch r
        WHERE r.sent = FALSE
        """)
        rows = c.fetchall()
        return [RocketNews(*row) for row in rows]
    
def mark_rocket_news_sent(title: str):
    with connect() as conn:
        c = conn.cursor()
        try:    

            c.execute("""
            UPDATE rocket_launch
            SET sent = TRUE
            WHERE title = ?
            """, (title, ))
            conn.commit()

        except sqlite3.IntegrityError:
            pass