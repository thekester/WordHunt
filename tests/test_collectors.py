import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import requests
from dicolink.dicolink import parse_content as parse_dicolink
from frenchdictionary.frenchdictionary import parse_content as parse_frenchdictionary
from scripts.fetch_word import COLLECTORS, preserve_history
from wiktionary.wiktionary import extract_daily_word, extract_french_definitions
from wordhunt.common import fetch_json, parse_date, save_data, validate


def record(**updates):
    return {'word_of_the_day': 'éclat', 'date': '2026-09-21', 'source_url': 'https://example.org',
            'definitions': ['Lumière vive.'], **updates}


class CommonTests(unittest.TestCase):
    def test_dates_and_invalid_records(self):
        self.assertEqual(parse_date('September 21, 2026'), date(2026, 9, 21))
        self.assertEqual(parse_date('2026-09-21'), date(2026, 9, 21))
        for data in (record(definitions=[]), record(word_of_the_day='Suggestions proposées pour mot-du-jour')):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate(data)

    def test_valid_history_preserved_and_invalid_history_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_data('dicolink', record(), directory)
            old = path.read_bytes()
            save_data('dicolink', record(definitions=['A different valid definition.']), directory)
            self.assertEqual(path.read_bytes(), old)
            with self.assertRaises(ValueError):
                save_data('dicolink', record(word_of_the_day='autre'), directory)
            path.write_text(json.dumps(record(definitions=[])))
            save_data('dicolink', record(), directory)
            self.assertEqual(json.loads(path.read_text())['word_of_the_day'], 'éclat')

    def test_network_errors_are_raised(self):
        with patch('wordhunt.common.requests.Session') as session_class:
            session = session_class.return_value.__enter__.return_value
            session.get.return_value.raise_for_status.side_effect = requests.HTTPError('403')
            with self.assertRaises(requests.HTTPError):
                fetch_json('https://example.org')
            self.assertEqual(session.get.call_args.kwargs['timeout'], (10, 30))


class DicolinkTests(unittest.TestCase):
    def test_keeps_source_attribution_when_a_source_has_no_list(self):
        data = parse_dicolink('''<h1>Éclat</h1><span class="date">September 21, 2026</span>
          <div class="module-definitions"><h3 class="source">Empty</h3>
          <h3 class="source">Correct</h3><ul><li>Lumière vive.</li></ul></div>''')
        self.assertEqual(data['definitions'], [{'source': 'Correct', 'definitions': ['Lumière vive.']}])

    def test_no_date_or_definition_is_rejected(self):
        for html in ('<h1>Mot</h1>', '<h1>Mot</h1><span class="date">September 21, 2026</span>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_dicolink(html)


class FrenchDictionaryTests(unittest.TestCase):
    def test_today_card_is_selected(self):
        data = parse_frenchdictionary('''<div><div>TODAY</div><h3><a href="/translate/éclat">éclat</a></h3>
          <div>sparkle</div><div><span>Un éclat de lumière.</span></div></div>
          <h3><a href="/translate/autre">autre</a></h3>''', date(2026, 9, 21))
        self.assertEqual(data['word_of_the_day'], 'éclat')
        self.assertEqual(data['definitions'], ['sparkle', 'Un éclat de lumière.'])
        self.assertEqual(data['date'], '2026-09-21')

    def test_missing_today_card_fails(self):
        with self.assertRaises(ValueError):
            parse_frenchdictionary('<h3><a href="/translate/x">x</a></h3>')


class WiktionaryTests(unittest.TestCase):
    def test_calendar_uses_requested_day_and_month(self):
        html = '''<table><tr><th></th><th>septembre</th><th>octobre</th></tr>
          <tr><th>21</th><td><a href="/wiki/éclat">éclat</a></td><td><a href="/wiki/autre">autre</a></td></tr></table>'''
        self.assertEqual(extract_daily_word(html, date(2026, 9, 21)),
                         ('éclat', 'https://fr.wiktionary.org/wiki/éclat'))

    def test_redlink_or_no_french_definition_fails(self):
        with self.assertRaises(ValueError):
            extract_daily_word('<table><tr><th></th><th>septembre</th></tr><tr><th>21</th><td><a class="new" href="/w/x">x</a></td></tr></table>', date(2026, 9, 21))
        with self.assertRaises(ValueError):
            extract_french_definitions('<h2 id="en">English</h2><ol><li>word</li></ol>')

    def test_french_definitions_stay_inside_french_section(self):
        html = '<h2 id="fr">Français</h2><ol><li>Définition.</li></ol><h2 id="en">English</h2><ol><li>definition</li></ol>'
        self.assertEqual(extract_french_definitions(html), ['Définition.'])


class AutomationTests(unittest.TestCase):
    def test_sources_are_registered(self):
        self.assertEqual(set(COLLECTORS), {'dicolink', 'frenchdictionary', 'wiktionary'})

    def test_valid_remote_history_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dicolink_word_of_the_day_2026-09-21.json'
            path.write_text(json.dumps(record()))
            import subprocess
            previous = json.dumps(record(), ensure_ascii=False).encode()
            with patch('scripts.fetch_word.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0, stdout=previous)]):
                preserve_history(path, 'origin/dev')
            self.assertIn('éclat', path.read_text())


if __name__ == '__main__':
    unittest.main()
