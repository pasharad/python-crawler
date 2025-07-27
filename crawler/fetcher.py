import requests
from bs4 import BeautifulSoup
from typing import Optional


def fetch_page(url: str) -> Optional[str]:
    """
    Fetches the HTML content of the given URL.
    Returns the HTML text or None if request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SpaceNewsCrawler/1.0)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch page: {url}\n{e}")
        return None
    
def get_soup(url: str) -> Optional[BeautifulSoup]:
    """
    Returns a BeautifulSoup object for the given URL, or None if failed.
    """
    html = fetch_page(url)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        return soup
    return None