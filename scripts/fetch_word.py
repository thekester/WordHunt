"""Collect one source safely and expose the resulting filename to GitHub Actions."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dicolink.dicolink import scrape as dicolink
from frenchdictionary.frenchdictionary import scrape as frenchdictionary
from wiktionary.wiktionary import scrape as wiktionary
from wordhunt.common import validate

COLLECTORS = {'dicolink': dicolink, 'frenchdictionary': frenchdictionary, 'wiktionary': wiktionary}


def preserve_history(path, base_ref):
    exists = subprocess.run(['git', 'rev-parse', '--verify', base_ref], capture_output=True)
    if exists.returncode:
        return
    previous = subprocess.run(['git', 'show', f'{base_ref}:data/{path.name}'], capture_output=True)
    if previous.returncode:
        return
    try:
        data = json.loads(previous.stdout)
        validate(data)
    except (ValueError, KeyError, TypeError):
        return
    current = json.loads(path.read_text(encoding='utf-8'))
    if data['word_of_the_day'].casefold() != current['word_of_the_day'].casefold():
        raise ValueError(f'A different valid word already exists on {base_ref} for {path.name}')
    path.write_bytes(previous.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', choices=sorted(COLLECTORS))
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--base-ref')
    args = parser.parse_args()
    path = COLLECTORS[args.source](args.output_dir)
    if args.base_ref:
        preserve_history(path, args.base_ref)
    print(path)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'filename={path.name}\n')
            output.write(f'date={path.stem[-10:]}\n')


if __name__ == '__main__':
    main()
