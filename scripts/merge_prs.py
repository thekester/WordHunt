"""Validate exact PR head contents before allowing unattended data merges."""
import base64
import json
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wordhunt.common import parse_date, validate

BRANCH = re.compile(r'^add-(dicolink|robert)-word-of-the-day-')
FILE = re.compile(r'^data/(dicolink|robert)_word_of_the_day_(\d{4}-\d{2}-\d{2})\.json$')


def validate_file(path, data, source):
    match = FILE.fullmatch(path)
    if match is None or match[1] != source:
        raise ValueError(f'Unexpected changed path: {path}')
    validate(data)
    if parse_date(data['date']).isoformat() != match[2]:
        raise ValueError(f'Date differs from filename: {path}')


def main(repo):
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError('Supply owner/repository')
    token = os.environ.get('GH_TOKEN') or os.environ.get('PERSONAL_ACCESS_TOKEN')
    if not token:
        raise ValueError('GH_TOKEN or PERSONAL_ACCESS_TOKEN is required')
    session = requests.Session()
    session.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})
    root = f'https://api.github.com/repos/{repo}'

    def request(method, path, **kwargs):
        response = session.request(method, root + path, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def pages(path, params=None):
        page = 1
        while True:
            batch = request('GET', path, params={**(params or {}), 'per_page': 100, 'page': page})
            yield from batch
            if len(batch) < 100:
                break
            page += 1

    # Snapshot the list before merging: otherwise pagination can skip shifted entries.
    pulls = list(pages('/pulls', {'state': 'open', 'base': 'holding'}))
    failures = []
    for pr in pulls:
        branch = BRANCH.match(pr['head']['ref'])
        if not branch or pr['draft'] or (pr['head'].get('repo') or {}).get('full_name') != repo:
            continue
        number, sha = pr['number'], pr['head']['sha']
        try:
            files = list(pages(f'/pulls/{number}/files'))
            if len(files) != 1 or files[0]['status'] not in ('added', 'modified'):
                raise ValueError('Expected exactly one added/modified daily data file')
            path = files[0]['filename']
            if not FILE.fullmatch(path):
                raise ValueError(f'Unexpected changed path: {path}')
            blob = request('GET', f'/contents/{path}', params={'ref': sha})
            data = json.loads(base64.b64decode(blob['content']))
            validate_file(path, data, branch[1])
            result = request('PUT', f'/pulls/{number}/merge', json={'merge_method': 'merge', 'sha': sha})
            if not result.get('merged'):
                raise ValueError(result.get('message', 'Merge refused'))
            print(f'Merged #{number}')
        except (ValueError, KeyError, requests.RequestException) as error:
            failures.append(number)
            print(f'PR #{number}: {error}', file=sys.stderr)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get('GITHUB_REPOSITORY', ''))
