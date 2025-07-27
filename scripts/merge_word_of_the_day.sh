#!/usr/bin/env bash
# Merge pull requests with branch names matching 'add-.*word-of-the-day'
# into the 'holding' branch.
# Requires: curl, jq

set -euo pipefail

REPO=${1:-"${GITHUB_REPOSITORY:-}"}
if [ -z "$REPO" ]; then
  echo "Repository not specified. Pass as first argument or set GITHUB_REPOSITORY." >&2
  exit 1
fi

if [ -z "${PERSONAL_ACCESS_TOKEN:-}" ]; then
  echo "PERSONAL_ACCESS_TOKEN environment variable is required" >&2
  exit 1
fi

PRS=$(curl -s -H "Authorization: Bearer $PERSONAL_ACCESS_TOKEN" -H "Accept: application/vnd.github+json" \
          "https://api.github.com/repos/${REPO}/pulls?state=open&base=holding" | \
          jq -r '.[] | select(.head.ref | test("add-.*word-of-the-day")) | .number')

if [ -z "$PRS" ]; then
  echo "No matching pull requests found" >&2
  exit 0
fi

for pr in $PRS; do
  echo "Merging PR #$pr" >&2
  STATUS=$(curl -s -o /tmp/merge_out -w "%{http_code}" -X PUT \
    -H "Authorization: Bearer $PERSONAL_ACCESS_TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${REPO}/pulls/${pr}/merge" \
    -d '{"merge_method":"merge"}')
  cat /tmp/merge_out
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "201" ]; then
    echo "Successfully merged PR #$pr" >&2
  else
    echo "Failed to merge PR #$pr (status: $STATUS)" >&2
  fi
  rm -f /tmp/merge_out
done
