import requests
from bs4 import BeautifulSoup
from typing import Optional
from utils.helpers import logger

def fetch_page(url: str) -> Optional[str]:
    """
    Fetches the HTML content of the given URL.
    Returns the HTML text or None if request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SpaceNewsCrawler/1.0)"
    }
    if not url:
        return None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Web page fetched, {url}")
        return response.text
    except requests.RequestException as e:
        logger.error(f"[ERROR] Failed to fetch page: {url}\n{e}")
        return None
    
def get_soup(url: str, session=None, headers=None, timeout=15) -> Optional[BeautifulSoup]:
    """
    Returns a BeautifulSoup object for the given URL, or None if failed.
    """
    try:
        resp = session.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        logger.info(f"Web page fetched, {url}")
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.error(f"[ERROR] Failed to get soup for {url}: {e}")
        return None