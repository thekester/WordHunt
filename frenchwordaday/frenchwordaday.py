"""Collect dated vocabulary posts from French Word-A-Day's public RSS feed."""
import sys
import re
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.etree import ElementTree

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from wordhunt.common import fetch_page, save_data, validate

FEED_URL = 'https://kristinespinasse.com/feed/'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'


def extract_word_post(html):
    soup = BeautifulSoup(html, 'html.parser')
    paragraphs = [node.get_text(' ', strip=True) for node in soup.find_all('p')]
    if not paragraphs:
        paragraphs = [node.get_text(' ', strip=True) for node in soup.find_all('div')]
    paragraphs = [value for value in paragraphs if value]
    for index, text in enumerate(paragraphs):
        marker = re.search(
            r"today['’]s\s+(?:word|verb)\s*:\s*(.+?)(?:\s+pronounced\b|$)",
            text, re.IGNORECASE)
        if not marker:
            continue
        word = marker.group(1).strip().strip('“”\"\' ')
        definitions = []
        for following in paragraphs[index + 1:]:
            if following.casefold().startswith('a day in a french life'):
                break
            if len(following) > 15:
                definitions.append(following)
            if len(definitions) == 2:
                break
        if not definitions:
            remainder = text[marker.end():].strip(' —–-:')
            if len(remainder) > 15:
                definitions.append(remainder)
        if definitions:
            return word, definitions
    raise ValueError('No explicit Today’s Word/Verb entry found in the feed item')


def parse_feed(xml, collection_date=None):
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise ValueError('French Word-A-Day feed is not valid XML') from error
    for item in root.findall('.//item'):
        content = item.findtext(CONTENT) or item.findtext('description') or ''
        try:
            word, definitions = extract_word_post(content)
        except ValueError:
            continue
        publication = item.findtext('pubDate')
        if not publication:
            continue
        try:
            published_date = parsedate_to_datetime(publication).date()
        except (TypeError, ValueError, OverflowError):
            continue
        link = item.findtext('link') or FEED_URL
        data = {'word_of_the_day': word, 'date': published_date.isoformat(),
                'source_url': urljoin(FEED_URL, link), 'definitions': definitions}
        validate(data)
        return data
    raise ValueError('No dated word-of-the-day entry found in the French Word-A-Day feed')


def scrape(data_dir=None, collection_date=None):
    return save_data('frenchwordaday', parse_feed(fetch_page(FEED_URL), collection_date), data_dir)


if __name__ == '__main__':
    print(scrape())
