"""CI gate for changed records; known bad archives are audited separately."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.merge_prs import FILE, validate_file

for name in Path(sys.argv[1]).read_text().splitlines():
    if not name.startswith('data/'):
        continue
    match = FILE.fullmatch(name)
    if match is None:
        raise ValueError(f'Unexpected data file: {name}')
    validate_file(name, json.loads(Path(name).read_text(encoding='utf-8')), match[1])
