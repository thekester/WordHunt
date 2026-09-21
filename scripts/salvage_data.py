"""Recover missing valid JSON records without replacing existing history."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.merge_prs import BRANCH, FILE, validate_file


def git(*args):
    return subprocess.check_output(['git', *args])


def salvage(destination='data'):
    count = 0
    branches = git('for-each-ref', '--format=%(refname)', 'refs/remotes/origin/add-*').decode().splitlines()
    for branch in branches:
        source = BRANCH.match(branch.removeprefix('refs/remotes/origin/'))
        if not source:
            continue
        for raw in git('ls-tree', '-r', '--name-only', '-z', branch, '--', 'data/').split(b'\0'):
            if not raw:
                continue
            path = raw.decode()
            if not FILE.fullmatch(path):
                continue
            target = Path(destination) / Path(path).name
            if target.exists():
                continue
            content = git('show', f'{branch}:{path}')
            try:
                data = json.loads(content)
                validate_file(path, data, source[1])
            except (ValueError, KeyError, TypeError) as error:
                print(f'Skipping {branch}:{path}: {error}', file=sys.stderr)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            count += 1
    return count


if __name__ == '__main__':
    print(f'Recovered {salvage()} missing records')
