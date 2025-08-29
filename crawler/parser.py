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
    full_text = "\n".join([p.get_text(strip=True) for p in paragraphs])
    
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
    return any(keyword.lower() in text for keyword in KEYWORDS)



def extract_tags(text: str) -> list[str]:
    """
    Returns a list of matched keywords found in the input text.
    """
    tags = []
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