"""Collect the public French's Cool word-of-the-day card."""
import sys
from pathlib import Path
from urllib.parse import urljoin

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from wordhunt.common import fetch_page, save_data, today, validate

URL = 'https://learnfrench.co/word-of-the-day/'


def parse_content(html, collection_date=None):
    soup = BeautifulSoup(html, 'html.parser')
    heading = next((node for node in soup.find_all(['h2', 'h3'])
                    if node.get_text(' ', strip=True).casefold().replace('’', "'") == "today's word"), None)
    if heading is None:
        raise ValueError("French's Cool today's word section is missing")

    container = heading.parent
    for _ in range(3):
        if container is None:
            break
        if container.find('a', href=True):
            break
        container = container.parent
    if container is None:
        raise ValueError("French's Cool today's word card is incomplete")

    word_link = next((link for link in container.find_all('a', href=True)
                      if link.get_text(' ', strip=True)), None)
    if word_link is None:
        raise ValueError("French's Cool word link is missing")
    word = word_link.get_text(' ', strip=True)

    paragraphs = []
    for paragraph in container.find_all('p'):
        text = paragraph.get_text(' ', strip=True)
        if text and paragraph.find('a') is not word_link and text.casefold() != 'part of speech':
            paragraphs.append(text)
    if not paragraphs:
        # Some page layouts place the gloss directly in the next text block.
        following = word_link.find_parent().find_next_sibling() if word_link.find_parent() else None
        if following:
            text = following.get_text(' ', strip=True)
            if text:
                paragraphs.append(text)

    data = {'word_of_the_day': word,
            'date': (collection_date or today()).isoformat(),
            'source_url': urljoin(URL, word_link['href']),
            'definitions': paragraphs}
    validate(data)
    return data


def scrape(data_dir=None, collection_date=None):
    return save_data('frenchscool', parse_content(fetch_page(URL), collection_date), data_dir)


if __name__ == '__main__':
    print(scrape())
