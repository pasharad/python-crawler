from crawler.fetcher import get_soup
from crawler.parser import exctract_articles, exctract_full_description

url = "https://www.space.com/news"
soup = get_soup(url)

if soup:
    articles = exctract_articles(soup)
    for article in articles:
        content = exctract_full_description(get_soup(article['url']))
        print(f"🔭 {article['title']}")
        print(f"📅 {article['date']}")
        print(f"🔗 {article['url']}")
        print(content)
        print("------")