from bs4 import BeautifulSoup
from typing import List, Dict

def exctract_articles(soup: BeautifulSoup) -> List[Dict]:
    """
    Extracts all news articles from the soup.
    Returns a list of dictionaries with title, description, date, url.
    """
    articles = []
    divs = soup.find_all("div", class_="listingResult")

    for div in divs:
        title_tag = div.find("h3")
        date_tag = div.find("time")
        link_tag = div.find("a", href=True)

        title = title_tag.get_text(strip=True) if title_tag else None
        date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else None
        url = link_tag["href"] if link_tag else None

        articles.append({
            "title" : title,
            "url" : url,
            "date" : date
        })

    return articles

def exctract_full_description(soup: BeautifulSoup) -> str:
    """
    Fetches the article page and extracts full article content.
    Usually selects all <p> tags inside article body.
    """
    if not soup:
        return None
    article_div = soup.find("div", id="article-body")
    if not article_div:
        return None
    paragraphs = article_div.find_all("p")
    full_text = "\n".join([p.get_text(strip=True) for p in paragraphs])
    
    return full_text