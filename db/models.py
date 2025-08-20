from collections import namedtuple

Article = namedtuple("Article", ["title", "url", "date", "description", "source"])
CleanArticle = namedtuple("CleanArticle", ["title", "url", "date", "description", "summery", "translated_text", "source", "tags"])