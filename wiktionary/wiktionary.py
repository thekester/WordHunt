"""Collect the French Wiktionary's explicitly curated word of the day."""
import sys
from pathlib import Path
from urllib.parse import quote

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from wordhunt.common import fetch_json, save_data, today, validate

API = 'https://fr.wiktionary.org/w/api.php'
MONTHS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin',
          'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre')


def api_page(title):
    payload = fetch_json(API, params={'action': 'parse', 'page': title, 'prop': 'text',
                                      'format': 'json', 'formatversion': '2'})
    try:
        return payload['parse']['text']
    except KeyError as error:
        raise ValueError(f'Wiktionary did not return {title!r}') from error


def extract_daily_word(calendar_html, date):
    soup = BeautifulSoup(calendar_html, 'html.parser')
    month = MONTHS[date.month - 1]
    for table in soup.select('table'):
        headings = [header.get_text(' ', strip=True).casefold() for header in table.select('tr:first-child th')]
        if month not in headings:
            continue
        column = headings.index(month)
        for row in table.select('tr'):
            cells = row.find_all(['th', 'td'], recursive=False)
            if not cells or cells[0].get_text(' ', strip=True) != str(date.day) or len(cells) <= column:
                continue
            cell = cells[column]
            link = next((anchor for anchor in cell.select('a[href]')
                         if 'new' not in (anchor.get('class') or []) and '/wiki/' in anchor['href']
                         and 'Modèle:' not in anchor['href']), None)
            if link is None:
                raise ValueError(f'No published Wiktionary word for {date.isoformat()}')
            return link.get_text(' ', strip=True), 'https://fr.wiktionary.org' + link['href']
    raise ValueError(f'Wiktionary calendar has no {month} column')


def extract_french_definitions(entry_html):
    soup = BeautifulSoup(entry_html, 'html.parser')
    heading = soup.find(id='fr')
    if heading is None:
        raise ValueError('Wiktionary entry has no French section')
    definitions = []
    section = heading if heading.name == 'h2' else heading.parent
    for node in section.next_siblings:
        if getattr(node, 'name', None) == 'h2':
            break
        if getattr(node, 'name', None) == 'ol':
            for item in node.find_all('li', recursive=False):
                text = item.get_text(' ', strip=True)
                if text:
                    definitions.append(text)
    if not definitions:
        raise ValueError('Wiktionary entry has no French definitions')
    return definitions


def scrape(data_dir=None, collection_date=None):
    collection_date = collection_date or today()
    calendar = api_page(f'Wiktionnaire:Mot du jour/{collection_date.year}')
    word, source_url = extract_daily_word(calendar, collection_date)
    entry = api_page(word)
    data = {'word_of_the_day': word, 'date': collection_date.isoformat(),
            'source_url': source_url, 'definitions': extract_french_definitions(entry)}
    validate(data)
    return save_data('wiktionary', data, data_dir)


if __name__ == '__main__':
    print(scrape())
