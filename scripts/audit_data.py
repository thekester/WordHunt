"""Report invalid active daily records without modifying them."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wordhunt.common import parse_date, validate

FILE = re.compile(r"^(dicolink|frenchdictionary|wiktionary)_word_of_the_day_(\d{4}-\d{2}-\d{2})\.json$")

def audit(folder):
    failures = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            match = FILE.fullmatch(path.name)
            if match is None:
                raise ValueError("Unexpected active archive filename")
            data = json.loads(path.read_text(encoding="utf-8"))
            validate(data)
            if parse_date(data["date"]).isoformat() != match[2]:
                raise ValueError("Date differs from filename")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            failures.append({"file": path.name, "error": str(error)})
    return failures

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=str(Path(__file__).resolve().parents[1] / "data"))
    failures = audit(parser.parse_args().folder)
    print(json.dumps(failures, ensure_ascii=False, indent=2))
    sys.exit(bool(failures))
