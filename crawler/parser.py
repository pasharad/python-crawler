from bs4 import BeautifulSoup
from typing import List, Dict

def exctract_articles(soup: BeautifulSoup, web: dict) -> List[Dict]:
    """
    Extracts all news articles from the soup.
    Returns a list of dictionaries with title, date, url.
    """
    articles = []
    divs = soup.find_all(web["divs"]["name"], class_=web["divs"]["class"])
    for div in divs:
        title_tag = div.find("h3")
        if web["type"] == 1:
            date_tag = div.find("span", class_="entry-meta-date updated").find("a").get_text(strip=True)
            date = date_tag if date_tag else None
        elif web["type"] == 2:
            date_tag = div.find("time")
            date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else None
        link_tag = div.find("a", href=True)


        title = title_tag.get_text(strip=True) if title_tag else None
        
        url = link_tag["href"] if link_tag else None

        articles.append({
            "title" : title,
            "url" : url,
            "date" : date
        })

    return articles

def exctract_full_description(soup: BeautifulSoup, id: str) -> str:
    """
    Fetches the article page and extracts full article content.
    Usually selects all <p> tags inside article body.
    """
    if not soup:
        return None
    article_div = soup.find("div", id=id)
    if not article_div:
        return None
    paragraphs = article_div.find_all("p")
    full_text = "\n".join([p.get_text(strip=True) for p in paragraphs])
    
    return full_text