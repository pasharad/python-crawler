from crawler.fetcher import get_soup
from crawler.parser import exctract_articles, exctract_full_description


webs = {
    "spaceflightnow" : {
        "type" : 1,
        "link" : "https://spaceflightnow.com/category/news-archive/",
        "pages" : 696,
        "divs" : {"name":"header", "class":"mh-posts-list-header"},
        "desc-tag" : "main-content"
        },
    "space" : {
        "type" : 2,
        "link" : "https://www.space.com/news",
        "pages" : 9,
        "divs" : {"name":"div", "class":"listingResult"},
        "desc-tag" : "article-body"
        }
        }

# url = "https://spaceflightnow.com/category/news-archive/"
for web in webs:    
    soup = get_soup(webs[web]["link"])

    if soup:
        articles = exctract_articles(soup, webs[web])
        for article in articles:
            content = exctract_full_description(get_soup(article['url']), webs[web]["desc-tag"])
            print(f"🔭 {article['title']}")
            print(f"📅 {article['date']}")
            print(f"🔗 {article['url']}")
            print(content)
            print("------")