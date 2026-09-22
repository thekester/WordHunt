"""Fetch Dicolink's dated word without performing I/O on import."""
import sys
from pathlib import Path

# Keep `python dicolink/dicolink.py` usable from any working directory.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from wordhunt.common import fetch_page, parse_date, save_data, validate

URL = 'https://www.dicolink.com/motdujour'


def parse_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    date_element = soup.select_one('.date')
    if heading is None or date_element is None:
        raise ValueError('Dicolink word or publication date missing')
    definitions = []
    for section in soup.select('.module-definitions'):
        for source in section.select('h3.source'):
            items = []
            # Do not zip unrelated lists: a source may have no definitions.
            for sibling in source.next_siblings:
                if getattr(sibling, 'name', None) == 'h3':
                    break
                if getattr(sibling, 'name', None) == 'ul':
                    items.extend(li.get_text(' ', strip=True) for li in sibling.find_all('li'))
            items = [text for text in items if text and text.casefold().rstrip('. ') != 'pas de définition']
            if items:
                definitions.append({'source': source.get_text(' ', strip=True), 'definitions': items})
    data = {'word_of_the_day': heading.get_text(' ', strip=True),
            'date': parse_date(date_element.get_text(' ', strip=True)).isoformat(),
            'source_url': URL, 'definitions': definitions}
    validate(data)
    return data


def scrape(data_dir=None):
    return save_data('dicolink', parse_content(fetch_page(URL)), data_dir)


if __name__ == '__main__':
    print(scrape())
