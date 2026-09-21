import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from dicolink.dicolink import parse_content, scrape
from robert.robert import RobertScraper
from wordhunt.common import fetch_page, parse_date, save_data, validate
from scripts.merge_prs import validate_file
from scripts.salvage_data import salvage

FIXTURES = Path(__file__).parent / 'fixtures'


def record(**changes):
    return {'word_of_the_day': 'éclat', 'date': '2026-09-21',
            'source_url': 'https://example.org', 'definitions': ['Lumière vive.'], **changes}


class DicolinkTests(unittest.TestCase):
    def test_live_fixture_word_date_and_full_definitions(self):
        data = parse_content((FIXTURES / 'dicolink.html').read_text())
        self.assertEqual(data['word_of_the_day'], 'Calomnier')
        self.assertEqual(data['date'], '2026-09-21')
        self.assertEqual(len(data['definitions']), 3)
        self.assertIn('Dénaturer sciemment', data['definitions'][0]['definitions'][0])
        self.assertFalse(any('pas de définition' in str(d) for d in data['definitions']))

    def test_missing_source_list_does_not_shift_attribution(self):
        data = parse_content('''<h1>Éclat</h1><span class="date">September 21, 2026</span>
          <div class="module-definitions"><h3 class="source">Empty</h3>
          <h3 class="source">Correct</h3><ul><li>Lumière vive.</li></ul></div>''')
        self.assertEqual(data['definitions'], [{'source': 'Correct', 'definitions': ['Lumière vive.']}])

    def test_missing_or_unrecognized_date_is_rejected(self):
        for html in ('<h1>Mot</h1>', '<h1>Mot</h1><div class="date">Invalid</div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_content(html)

    def test_network_error_creates_no_file(self):
        with tempfile.TemporaryDirectory() as directory, patch('dicolink.dicolink.fetch_page', side_effect=requests.Timeout):
            with self.assertRaises(requests.Timeout):
                scrape(directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_import_has_no_network_or_filesystem_side_effects(self):
        root = str(Path(__file__).resolve().parents[1])
        subprocess.run([sys.executable, '-c',
            f'import sys; sys.path.insert(0, {root!r}); from unittest.mock import patch; '
            'p = patch("requests.sessions.Session.request", side_effect=AssertionError("network")); '
            'p.start(); import dicolink.dicolink'], check=True, cwd='/tmp')


class RobertTests(unittest.TestCase):
    def test_suggestion_page_regression(self):
        with self.assertRaises(ValueError):
            RobertScraper().parse_content('''<h1>Suggestions proposées pour mot-du-jour</h1>
                <section class="def"><div class="b"><b>modulor</b></div></section>''')

    def test_full_definitions_not_bold_words(self):
        data = RobertScraper().parse_content('''<h1><span class="d_mot">éclat</span> nom masculin</h1>
            <section class="def"><div class="d_dfn">Lumière <b>vive</b>.</div>
            <div class="d_dfn">Bruit retentissant.</div></section>''')
        self.assertEqual(data['word_of_the_day'], 'éclat')
        self.assertEqual(data['definitions'], ['Lumière vive .', 'Bruit retentissant.'])

    def test_only_daily_card_link_selected(self):
        html = '''<a href="/definition/autre">Other</a><div><h2>Le mot du jour</h2>
            <a href="/definition/eclat">éclat</a></div>'''
        self.assertEqual(RobertScraper().find_word_url(html), 'https://dictionnaire.lerobert.com/definition/eclat')

    def test_missing_ambiguous_or_external_card_rejected(self):
        for html in ('<h1>Suggestions</h1>',
                     '<div>Le mot du jour<a href="https://evil.example/definition/x">x</a></div>',
                     '<div>Le mot du jour<a href="/definition/a">a</a><a href="/definition/b">b</a></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                RobertScraper().find_word_url(html)

    def test_end_to_end_follows_definition_link(self):
        with tempfile.TemporaryDirectory() as directory, patch('robert.robert.fetch_page', side_effect=[
            '<div>Le mot du jour<a href="/definition/eclat">éclat</a></div>',
            '<h1>éclat</h1><section class="def"><span class="d_dfn">Lumière vive.</span></section>'
        ]) as fetch:
            result = RobertScraper(directory).scrape()
            self.assertEqual(fetch.call_args.args[0], 'https://dictionnaire.lerobert.com/definition/eclat')
            self.assertEqual(json.loads(result.read_text())['definitions'], ['Lumière vive.'])


class StorageTests(unittest.TestCase):
    def test_english_and_iso_dates(self):
        self.assertEqual(parse_date('September 21, 2026'), date(2026, 9, 21))
        self.assertEqual(parse_date('2026-09-21'), date(2026, 9, 21))
        with self.assertRaises(ValueError):
            parse_date('Yesterday')

    def test_valid_history_preserved_and_invalid_record_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_data('robert', record(), directory)
            original = path.read_bytes()
            save_data('robert', record(definitions=['Another definition.']), directory)
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                save_data('robert', record(word_of_the_day='autre'), directory)
            path.write_text(json.dumps(record(word_of_the_day='Suggestions proposées pour mot-du-jour')))
            save_data('robert', record(), directory)
            self.assertEqual(json.loads(path.read_text())['word_of_the_day'], 'éclat')

    def test_invalid_result_does_not_create_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new'
            with self.assertRaises(ValueError):
                save_data('robert', record(definitions=[]), target)
            self.assertFalse(target.exists())

    def test_http_failure_is_raised_with_timeout(self):
        session = Mock()
        session.get.return_value.raise_for_status.side_effect = requests.HTTPError('403')
        with patch('wordhunt.common.requests.Session') as cls:
            cls.return_value.__enter__.return_value = session
            with self.assertRaises(requests.HTTPError):
                fetch_page('https://example.org')
        self.assertEqual(session.get.call_args.kwargs['timeout'], (10, 30))

    def test_atomic_failure_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'robert_word_of_the_day_2026-09-21.json'
            path.write_text('broken')
            with patch('wordhunt.common.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    save_data('robert', record(), directory)
            self.assertEqual(path.read_text(), 'broken')
            self.assertEqual(len(list(Path(directory).iterdir())), 1)


class AutomationTests(unittest.TestCase):
    def test_data_gate_rejects_code_wrong_date_and_source(self):
        validate_file('data/robert_word_of_the_day_2026-09-21.json', record(), 'robert')
        for path, source in [('.github/workflows/evil.yml', 'robert'),
                             ('data/robert_word_of_the_day_2026-09-20.json', 'robert'),
                             ('data/robert_word_of_the_day_2026-09-21.json', 'dicolink')]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_file(path, record(), source)

    def test_salvage_preserves_existing_and_rejects_invalid(self):
        branch = b'refs/remotes/origin/add-robert-word-of-the-day-test\n'
        def fake_git(*args):
            if args[0] == 'for-each-ref':
                return branch
            if args[0] == 'ls-tree':
                return b'data/robert_word_of_the_day_2026-09-21.json\0data/robert_word_of_the_day_2026-09-20.json\0'
            return json.dumps(record(date='2026-09-20', definitions=[])).encode()
        with tempfile.TemporaryDirectory() as directory, patch('scripts.salvage_data.git', side_effect=fake_git):
            path = Path(directory) / 'robert_word_of_the_day_2026-09-21.json'
            path.write_text('preserve this existing archive')
            self.assertEqual(salvage(directory), 0)
            self.assertEqual(path.read_text(), 'preserve this existing archive')
            self.assertEqual(len(list(Path(directory).iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
