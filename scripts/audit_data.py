"""Report invalid archives without rewriting or deleting historical data."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.merge_prs import FILE, validate_file


def audit(folder):
    failures = []
    for path in sorted(Path(folder).glob('*.json')):
        try:
            match = FILE.fullmatch('data/' + path.name)
            if match is None:
                raise ValueError('Unexpected filename')
            validate_file('data/' + path.name, json.loads(path.read_text(encoding='utf-8')), match[1])
        except (ValueError, KeyError, TypeError) as error:
            failures.append({'file': path.name, 'error': str(error)})
    return failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', nargs='?', default=str(Path(__file__).resolve().parents[1] / 'data'))
    args = parser.parse_args()
    failures = audit(args.folder)
    print(json.dumps(failures, ensure_ascii=False, indent=2))
    sys.exit(bool(failures))
