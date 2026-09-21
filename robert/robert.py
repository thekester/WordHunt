"""Resolve the featured word on Robert's home page, then read its definition."""
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from wordhunt.common import fetch_page, save_data, today, validate


class RobertScraper:
    def __init__(self, data_dir=None):
        self.url = 'https://dictionnaire.lerobert.com/'
        self.data_dir = data_dir

    def find_word_url(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        # Resolve only a definition link inside the explicitly labelled daily card.
        # Never treat /mot-du-jour (a suggestion/search page) as a dictionary entry.
        for label in soup.find_all(string=lambda s: s and s.strip().casefold() in ('le mot du jour', 'mot du jour')):
            container = label.parent
            for _ in range(4):
                if container is None or container.name in ('body', 'html'):
                    break
                links = container.select('a[href]')
                candidates = []
                for link in links:
                    target = urljoin(self.url, link['href'])
                    parsed = urlparse(target)
                    if parsed.scheme == 'https' and parsed.netloc == 'dictionnaire.lerobert.com' and parsed.path.startswith('/definition/'):
                        candidates.append(target)
                candidates = list(dict.fromkeys(candidates))
                if len(candidates) == 1:
                    return candidates[0]
                if len(candidates) > 1:
                    break
                container = container.parent
        raise ValueError('Cannot identify the Robert daily word card; refusing to save suggestions')

    def parse_content(self, html, source_url=None):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('h1 .d_mot') or soup.find('h1')
        if heading is None:
            raise ValueError('Robert word missing')
        # d_dfn contains the full definition; div.b/b only contained a suggested word.
        definitions = list(dict.fromkeys(node.get_text(' ', strip=True)
                                        for node in soup.select('section.def .d_dfn')
                                        if node.get_text(' ', strip=True)))
        data = {'word_of_the_day': heading.get_text(' ', strip=True),
                'date': today().isoformat(), 'source_url': source_url or self.url,
                'definitions': definitions}
        validate(data)
        return data

    def scrape(self):
        word_url = self.find_word_url(fetch_page(self.url))
        data = self.parse_content(fetch_page(word_url), word_url)
        return save_data('robert', data, self.data_dir)


if __name__ == '__main__':
    print(RobertScraper().scrape())
