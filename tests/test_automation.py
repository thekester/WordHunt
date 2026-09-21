import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.fetch_word import preserve_history
from scripts.merge_prs import main

DATA = {'word_of_the_day': 'éclat', 'date': '2026-09-21',
        'source_url': 'https://dictionnaire.lerobert.com/definition/eclat',
        'definitions': ['Lumière vive.']}


class MergeTests(unittest.TestCase):
    def run_merge(self, files=None, merged=True, head_repo='owner/repo'):
        pull = {'number': 1, 'draft': False, 'head': {'ref': 'add-robert-word-of-the-day-2026-09-21',
                'sha': 'checked-head', 'repo': {'full_name': head_repo}}}
        session = Mock()
        def response(method, url, **kwargs):
            result = Mock()
            if url.endswith('/pulls'):
                result.json.return_value = [pull]
            elif url.endswith('/files'):
                result.json.return_value = files if files is not None else [
                    {'filename': 'data/robert_word_of_the_day_2026-09-21.json', 'status': 'added'}]
            elif '/contents/' in url:
                self.assertEqual(kwargs['params']['ref'], 'checked-head')
                result.json.return_value = {'content': base64.b64encode(json.dumps(DATA).encode()).decode()}
            elif url.endswith('/merge'):
                self.assertEqual(kwargs['json']['sha'], 'checked-head')
                result.json.return_value = {'merged': merged, 'message': 'test result'}
            else:
                raise AssertionError(url)
            return result
        session.request.side_effect = response
        with patch('scripts.merge_prs.requests.Session', return_value=session), patch.dict('os.environ', {'GH_TOKEN': 'test-only-token'}):
            try:
                main('owner/repo')
            except SystemExit:
                if merged and files is None:
                    raise
        return session

    def test_merge_reads_and_merges_same_sha(self):
        session = self.run_merge()
        self.assertEqual(sum(c.args[0] == 'PUT' for c in session.request.call_args_list), 1)

    def test_code_change_is_never_merged(self):
        session = self.run_merge(files=[{'filename': '.github/workflows/evil.yml', 'status': 'modified'}])
        self.assertFalse(any(c.args[0] == 'PUT' for c in session.request.call_args_list))

    def test_fork_is_never_merged(self):
        session = self.run_merge(head_repo='other/repo')
        self.assertEqual(len(session.request.call_args_list), 1)

    def test_api_merge_refusal_exits_nonzero(self):
        session = Mock()
        pull = {'number': 1, 'draft': False, 'head': {'ref': 'add-robert-word-of-the-day-test',
                'sha': 'head', 'repo': {'full_name': 'owner/repo'}}}
        responses = [[pull], [{'filename': 'data/robert_word_of_the_day_2026-09-21.json', 'status': 'added'}],
                     {'content': base64.b64encode(json.dumps(DATA).encode()).decode()}, {'merged': False}]
        session.request.side_effect = [Mock(json=Mock(return_value=r)) for r in responses]
        with patch('scripts.merge_prs.requests.Session', return_value=session), patch.dict('os.environ', {'GH_TOKEN': 'test-only-token'}):
            with self.assertRaises(SystemExit) as result:
                main('owner/repo')
        self.assertEqual(result.exception.code, 1)


class HoldingHistoryTests(unittest.TestCase):
    def test_existing_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'robert_word_of_the_day_2026-09-21.json'
            path.write_text(json.dumps(DATA))
            old = json.dumps({**DATA, 'date': 'September 21, 2026'}).encode()
            with patch('scripts.fetch_word.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0, stdout=old)]):
                preserve_history(path, 'origin/holding')
            self.assertEqual(path.read_bytes(), old)

    def test_different_existing_word_blocks_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record.json'
            path.write_text(json.dumps(DATA))
            old = json.dumps({**DATA, 'word_of_the_day': 'autre'}).encode()
            with patch('scripts.fetch_word.subprocess.run', side_effect=[
                subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0, stdout=old)]):
                with self.assertRaises(ValueError):
                    preserve_history(path, 'origin/holding')
