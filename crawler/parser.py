from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from db.database import rules_all

def exctract_articles(soup: BeautifulSoup, web: dict) -> List[Dict]:
    """
    Extracts all news articles from the soup.
    Returns a list of dictionaries with title, date, url.
    """
    articles = []
    if not soup:
        return articles
    divs = soup.find_all(web["divs"]["name"], class_=web["divs"]["class"])
    for div in divs:
        if web["type"] == 2:
            title_tag = div.find("h2").find("a")
        else:
            title_tag = div.find("h3")
        if web["type"] == 1:
            date_tag = div.find("span", class_="entry-meta-date updated").find("a")
            date = date_tag.get_text(strip=True) if date_tag else ""
        else:
            date_tag = div.find("time")
            date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else ""
        link_tag = div.find("a", href=True)
        if link_tag == "https://www.space.com/live/rocket-launch-today":
            continue


        title = title_tag.get_text(strip=True) if title_tag else ""
        
        url = link_tag["href"] if link_tag else ""

        articles.append({
            "title" : title,
            "url" : url,
            "date" : date
        })

    return articles

def exctract_full_description(soup: BeautifulSoup, id: Optional[str], class_: Optional[str]) -> str:
    """
    Fetches the article page and extracts full article content.
    Usually selects all <p> tags inside article body.
    """
    if not soup:
        return None
    if id:
        article_div = soup.find("div", id=id)
    elif class_:
        article_div = soup.find("div", class_=class_)   
    if not article_div:
        return None
    paragraphs = article_div.find_all("p")
    clean_paragraphs = [p.get_text(strip=True) for p in paragraphs if not p.find_parent("div", class_="newsletter-form__container")]
    full_text = "\n".join(clean_paragraphs)
    
    return full_text




KEYWORDS = [
    "Israel", "Spy satellite", "Ofek series", "Orbit", "Classified tle",
    "Ofek 13", "Palmachim Airbase", "Mystery object into orbit",
    "Launch", "Satellite Launch Center", "Retrograde orbit", "Spies in space"
]

def check_article(article: dict) -> bool:
    """
    Returns True if the article description contains any of the defined keywords.
    """

    if not article or "description" not in article or not article["description"]:
        return False

    text = article["description"].lower()
    
    rows = rules_all()
    
    
    c_keywords = KEYWORDS.copy()


    for r in rows:
        pattern = r[1]
        enabled = bool(r[3])
        if not enabled or not pattern:
            continue
        c_keywords.append(pattern)
    return any(keyword.lower() in text for keyword in c_keywords)



def extract_tags(text: str) -> list[str]:
    """
    Returns a list of matched keywords found in the input text.
    """
    if not text:
        return tags

    text_lower = text.lower()
    c_keywords = KEYWORDS.copy()
    rows = rules_all()

    for r in rows:
        pattern = r[1]
        enabled = bool(r[3])
        if not enabled or not pattern:
            continue
        if pattern not in c_keywords:
            c_keywords.append(pattern)
    tags = [kw for kw in c_keywords if kw.lower() in text_lower]
    return tags

def extract_articles_from_live(soup: BeautifulSoup, web: dict, last_date: int) -> List[Dict]:
    """Return list of article dicts with keys: title, url, date (datetime or None), description, source"""
    results = []
    if not soup:
        return results
    divs = soup.find_all(web["divs"]["name"], class_=web["divs"]["class"])
    today = datetime.now()
    last_date = today - timedelta(days=11)
    for div in divs:
        title = div.find("h3")
        date = div.find("time")
        description = div.find_all("p")
        clean_description = [p.get_text(strip=True) for p in description]
        full_text = "\n".join(clean_description)
        if description == None:
            continue
        items = []

        unordered_items = div.find_all("li")
        if unordered_items:
            for item in unordered_items:
                item_keyword = item.find("strong").get_text(strip=True)
                item_value = item.get_text(strip=True).replace(item_keyword, "").strip()
                items.append({item_keyword : item_value})
        else:
            continue

        if title == None or date == None or full_text == None or datetime.fromisoformat(date.get_text(strip=True).replace("Z", "+00:00")).replace(tzinfo=None).date() < last_date.date():
            continue
        news = {
            "title" : title.get_text(strip=True) if title else "",
            "description" : full_text,
            "date" : date.get_text(strip=True) if date else "",
            "ul" : items
        }
        results.append(news)

    return results
