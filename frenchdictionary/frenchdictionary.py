"""Collect FrenchDictionary.com's card labelled TODAY."""
import sys
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from wordhunt.common import fetch_page, save_data, today, validate

URL = 'https://www.frenchdictionary.com/wordoftheday'


def parse_content(html, collection_date=None):
    soup = BeautifulSoup(html, 'html.parser')
    marker = soup.find(string=lambda value: value and value.strip().casefold() == 'today')
    if marker is None:
        raise ValueError('FrenchDictionary TODAY card missing')
    card = marker.parent
    for _ in range(4):
        if card is None:
            break
        word_link = card.select_one('h3 a[href*="/translate/"]')
        if word_link:
            word = word_link.get_text(' ', strip=True)
            translation = word_link.find_parent().find_next_sibling()
            definition = translation.get_text(' ', strip=True) if translation else ''
            example = card.select_one('span')
            definitions = [definition] if definition else []
            if example and example.get_text(' ', strip=True):
                definitions.append(example.get_text(' ', strip=True))
            data = {'word_of_the_day': word, 'date': (collection_date or today()).isoformat(),
                    'source_url': urljoin(URL, word_link['href']), 'definitions': definitions}
            validate(data)
            return data
        card = card.parent
    raise ValueError('FrenchDictionary TODAY card is incomplete')


def scrape(data_dir=None, collection_date=None):
    return save_data('frenchdictionary', parse_content(fetch_page(URL), collection_date), data_dir)


if __name__ == '__main__':
    print(scrape())
