from collections import namedtuple

Article = namedtuple("Article", ["title", "url", "date", "description", "source"])
CleanArticle = namedtuple("CleanArticle", ["title", "url", "date", "description", "summery", "second_summery", "translated_text", "second_translated_text", "source", "tags"])
RocketNews = namedtuple("RocketNews", ["title", "item_list", "description", "date", "translated"])