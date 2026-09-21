"""Collect exactly one record and expose its filename to GitHub Actions."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dicolink.dicolink import scrape
from robert.robert import RobertScraper
from wordhunt.common import validate


def preserve_history(path, base_ref):
    # The base may not exist yet on a newly initialized repository.
    exists = subprocess.run(['git', 'rev-parse', '--verify', base_ref], capture_output=True)
    if exists.returncode:
        return
    previous = subprocess.run(['git', 'show', f'{base_ref}:data/{path.name}'], capture_output=True)
    if previous.returncode:
        return  # No record for this date in the base branch.
    try:
        data = json.loads(previous.stdout)
        validate(data)
    except (ValueError, KeyError, TypeError):
        return  # A new valid result can repair invalid data.
    current = json.loads(path.read_text(encoding='utf-8'))
    if data['word_of_the_day'].casefold() != current['word_of_the_day'].casefold():
        raise ValueError(f'A different valid word already exists on {base_ref} for {path.name}')
    path.write_bytes(previous.stdout)  # Preserve legacy date format and definitions exactly.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', choices=('dicolink', 'robert'))
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--base-ref')
    args = parser.parse_args()
    path = scrape(args.output_dir) if args.source == 'dicolink' else RobertScraper(args.output_dir).scrape()
    if args.base_ref:
        preserve_history(path, args.base_ref)
    print(path)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'filename={path.name}\n')
            output.write(f'date={path.stem[-10:]}\n')


if __name__ == '__main__':
    main()
