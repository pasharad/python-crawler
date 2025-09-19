webs = {
    "space": {
        "type": 0,
        "link": "https://www.space.com/news/",
        "pages": 9,
        "divs": {"name": "div", "class": "listingResult"},
        "desc-tag": "article-body"
    },
    "spaceflightnow": {
        "type": 1,
        "link": "https://spaceflightnow.com/category/news-archive/",
        "pages": 698,
        "divs": {"name": "header", "class": "mh-posts-list-header"},
        "desc-tag": "main-content"
    },
    "spacenews": {
        "type": 2,
        "link": "https://spacenews.com/section/news-archive/",
        "pages": 2876,
        "divs": {"name": "article", "class": "post"},
        "desc-tag": "entry-content"
    }
}

live_web = {
    "divs" : {"name": "div", "class": "wcp-item-content"}
}
# tuning
FAST_PAGES = 3
FAST_INTERVAL = 60
BACKFILL_INTERVAL = 60 * 60
REQUEST_MIN = 1.0
REQUEST_MAX = 3.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64)"
]


TOKEN = "bot344222:4fd469a6-3882-43da-ba12-8f24dee58e74"
API_URL = f"https://eitaayar.ir/api/{TOKEN}/sendMessage"
CHAT_ID = 10853438