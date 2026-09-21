"""Networking, dates and lossless storage shared by the collectors."""
import json
import os
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]


def today():
    return datetime.now(ZoneInfo('Europe/Paris')).date()


def parse_date(value):
    value = value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        # Independent of the machine's locale.
        months = ('January February March April May June July August September '
                  'October November December').split()
        parts = value.replace(',', '').split()
        if len(parts) == 3 and parts[0] in months:
            return date(int(parts[2]), months.index(parts[0]) + 1, int(parts[1]))
        raise ValueError(f'Unrecognized source date: {value!r}')


def fetch_page(url):
    retries = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=('GET',))
    with requests.Session() as session:
        session.mount('https://', HTTPAdapter(max_retries=retries))
        response = session.get(url, timeout=(10, 30),
                               headers={'User-Agent': 'WordHunt/1.0 (daily dictionary collector)'})
        response.raise_for_status()
        return response.content


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Record must be a JSON object')
    word = data.get('word_of_the_day')
    if not isinstance(word, str) or not word.strip():
        raise ValueError('Missing word')
    if word.casefold() in ('unknown', 'inconnu', 'mot-du-jour', 'mot du jour') or 'suggestions proposées' in word.casefold():
        raise ValueError('Search/suggestion page received instead of a word')
    definitions = data.get('definitions')
    if not isinstance(definitions, list) or not definitions:
        raise ValueError('No definitions found')
    for item in definitions:
        values = item.get('definitions') if isinstance(item, dict) else [item]
        if isinstance(item, dict) and not item.get('source'):
            raise ValueError('Missing definition source')
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError('Empty definition')
    parse_date(data['date'])


def save_data(source, data, data_dir=None):
    validate(data)
    folder = Path(data_dir) if data_dir is not None else ROOT / 'data'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{source}_word_of_the_day_{parse_date(data["date"]).isoformat()}.json'
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding='utf-8'))
            validate(previous)
        except (ValueError, KeyError, TypeError):
            pass  # Repair an invalid existing record, but never overwrite valid history.
        else:
            if previous['word_of_the_day'].casefold() != data['word_of_the_day'].casefold():
                raise ValueError(f'A different valid word already exists in {path}')
            return path
    temporary = None
    try:
        with NamedTemporaryFile('w', encoding='utf-8', dir=folder, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=4)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
