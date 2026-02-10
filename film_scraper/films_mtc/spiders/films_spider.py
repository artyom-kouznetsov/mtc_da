import scrapy
import json
from films_mtc.items import FilmsItem


class FilmSpider(scrapy.Spider):
    name = "film_spider"
    allowed_domains = ["ru.wikipedia.org", "imdb.com"]
    start_urls = [
        "https://ru.wikipedia.org/wiki/Категория:Фильмы_по_алфавиту"
    ]

    # get the initial film links on catalog page
    def parse(self, response):
        # collect film links by category
        film_links = response.css(
            '#mw-pages .mw-category-group ul li a::attr(href)').getall()
        for link in film_links:
            yield response.follow(link, callback=self.parse_film_page)

        # move to the next page if any
        next_page = response.xpath(
            '//a[contains(text(), "Следующая страница")]/@href').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    # data parsing function
    def parse_film_page(self, response):
        item = FilmsItem()
        
        # wiki film box
        film_box = response.xpath('(//table[contains(@class, "infobox")])[1]')
        # if filmbox not found - use all page
        if not film_box: film_box = response

        # title (in Russian)
        raw_title = response.css(
            'h1#firstHeading span.mw-page-title-main::text').get()
        if raw_title:
            item['title'] = raw_title.split('(')[0].strip()
        else:
            item['title'] = response.css('h1#firstHeading::text').get()

        # genre
        genre_raw = film_box.xpath(
            './/th[contains(., "Жанр")]/following-sibling' \
            '::td//*[self::a or self::span]/text()'
            ).getall()
        if genre_raw:
            cleaned_genres = []
            seen = set()
            for g in genre_raw:
                clean_g = g.replace(
                    ',', '').replace('(', '').replace(')', '').strip()
                if clean_g and len(clean_g) > 2 and \
                clean_g.lower() not in seen and '[' not in clean_g:
                    cleaned_genres.append(clean_g.capitalize())
                    seen.add(clean_g.lower())
            item['genre'] = ", ".join(cleaned_genres)
        else:
            item['genre'] = None

        # country
        country_td = film_box.xpath(
            './/th[contains(., "Стран")]/following-sibling::td')
        if country_td:
            raw_countries = country_td.xpath('.//text()').getall()
            clean_countries = []
            seen = set()
            for c in raw_countries:
                c_clean = c.strip().strip(',').strip()
                if len(c_clean) > 2 and c_clean not in seen and \
                '[' not in c_clean:
                    clean_countries.append(c_clean)
                    seen.add(c_clean)
            item['country'] = ", ".join(clean_countries)
        else:
            item['country'] = None

        # director
        director_td = film_box.xpath(
            './/th[contains(., "Режисс")]/following-sibling::td')
        if director_td:
            raw_directors = director_td.xpath(
                './/text()[not(ancestor::div[contains(@class, "navbox")]) ' \
                'and not(ancestor::style) and not(ancestor::script)]'
                ).getall()
            bad_words = ['нем.', 'англ.', 'фр.', 'ит.', 'исп.', 'рус.']
            director_vals = []
            for d in raw_directors:
                d_clean = d.replace('(', '').replace(')', '').strip()
                if (len(d_clean) > 1 and '[' not in d_clean and \
                    not any(bw in d_clean.lower() for bw in bad_words) and  \
                        d_clean not in ['Полнометражные', 
                                        'Короткометражные', 
                                        'Документальные']):
                    director_vals.append(d_clean)
            item['director'] = ", ".join(
                list(dict.fromkeys(director_vals))[:3]
                )
        else:
            item['director'] = None

        # year
        year_raw = film_box.xpath(
            './/th[contains(., "Год") or contains(., "Дата выхода")]' \
            '/following-sibling::td//text()'
            ).getall()
        found_year = None
        if year_raw:
            for y in year_raw:
                clean_y = y.strip()
                if clean_y.isdigit() and len(clean_y) == 4 and (
                    clean_y.startswith('19') or clean_y.startswith('20')):
                    found_year = clean_y
                    break
        item['year'] = found_year

        # --- imdb rating ---
        # look for the imdb link on wiki page
        imdb_link = response.xpath(
            '//a[contains(@href, "imdb.com/title/tt")]/@href').get()
        
        if imdb_link:
            imdb_link = response.urljoin(imdb_link)
            yield scrapy.Request(
                url=imdb_link, 
                callback=self.parse_imdb_rating,
                meta={'item': item},
                dont_filter=True 
            )
        else:
            item['imdb_rating'] = None
            yield item

    def parse_imdb_rating(self, response):
        item = response.meta['item']
        # try JSON-LD
        json_ld = response.xpath(
            '//script[@type="application/ld+json"]/text()').get()
        rating = None
        
        if json_ld:
            try:
                data = json.loads(json_ld)
                if isinstance(data, dict):
                    if data.get('@type') == 'Movie' or \
                    'aggregateRating' in data:
                        rating = data.get(
                            'aggregateRating', {}).get('ratingValue')
                elif isinstance(data, list):
                    for entity in data:
                        if entity.get('@type') == 'Movie':
                            rating = entity.get(
                                'aggregateRating', {}).get('ratingValue')
                            break
            except (json.JSONDecodeError, AttributeError):
                self.logger.warning(
                    f"Failed to parse JSON-LD for {response.url}"
                    )

        # fallback: if rating not found - try visual selectors
        if not rating:
            rating = response.css(
                '[data-testid="hero-rating-bar__aggregate-rating__score"] ' \
                'span::text'
                ).get()
        
        if not rating:
             rating = response.css('.sc-bde20123-1.cMEQkK::text').get()

        item['imdb_rating'] = rating

        yield item


