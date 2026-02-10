# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

# target data fields
class FilmsItem(scrapy.Item):
    title = scrapy.Field()
    genre = scrapy.Field()
    director = scrapy.Field()
    country = scrapy.Field()
    year = scrapy.Field()
    imdb_rating = scrapy.Field()


