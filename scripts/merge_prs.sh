#!/usr/bin/env bash
# Merge only same-repository, validated daily-data pull requests.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python "$SCRIPT_DIR/merge_prs.py" "${1:-${GITHUB_REPOSITORY:-}}"
