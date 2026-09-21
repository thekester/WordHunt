# WordHunt

Discover a French word every day, with definitions from Dicolink and Le Robert.
Records are stored in `data/<source>_word_of_the_day_YYYY-MM-DD.json`.

## Run locally

Requires Python 3.9+ (GitHub Actions uses 3.12).

```bash
git clone https://github.com/thekester/WordHunt.git
cd WordHunt
python -m pip install -r requirements.txt
python dicolink/dicolink.py
python robert/robert.py
python -m unittest discover -s tests -v
```

Scripts work from any directory and default to this repository's `data/` folder.
To select an output directory:

```bash
python scripts/fetch_word.py dicolink --output-dir /tmp/wordhunt-data
```

Dicolink's publication date is read from the page (including its `span.date`).
Robert's collector resolves the daily-word card on the home page, then reads the
linked dictionary entry. Its collection date uses Europe/Paris time. New records
use ISO dates; legacy English dates remain readable. The existing JSON structure
is retained: Dicolink groups definitions by source, Robert uses a list of strings.

Missing words, missing definitions, unrecognized source dates, HTTP errors and
suggestion pages fail the run before a data pull request is created. HTTP requests
have timeouts and bounded retries for transient errors. A valid existing record
is preserved; a different word for the same date is reported as a conflict.
Invalid existing records can be repaired with a newly validated result.

## Automation

The `holding → dev → main` branch flow is retained:

| Workflow | Schedule (UTC) | Behavior |
| --- | --- | --- |
| Sync main into holding | 06:30 | Normal merge; conflicts fail visibly, no force push |
| Fetch Dicolink | 07:00 | Validate a record and open a dated PR into holding |
| Fetch Robert | 08:00 | Validate a record and open a dated PR into holding |
| Merge daily data branches | 08:15, 09:15, 12:15, 18:15 | Validate same-repository PR contents and merge the exact checked head |
| Promote holding | 09:30 | Merge into dev, then promote through a PR into main |
| Delete old merged data branches | 03:30 | Only old daily-data branches whose commits are already in main and which have no open PR |

All these workflows also support manual dispatch. Fetches always run the code
from main and submit only the freshly collected file to holding. They preserve
valid existing holding records, and manual and scheduled runs use the same base.
Maintenance workflows share a concurrency group. Collection and maintenance do
not trigger on every push or PR closure, preventing recursive PAT-triggered runs.
Normal pushes fail on concurrent remote changes; rerun after resolving any conflict.

Workflows prefer `PERSONAL_ACCESS_TOKEN` when configured and otherwise use
`GITHUB_TOKEN`. The token needs repository contents and pull-request write access,
and repository Actions settings must allow pull-request creation. Branch rules
still apply. A PAT is needed if automatic writes must trigger further workflows;
`GITHUB_TOKEN` writes do not trigger most subsequent Actions events. The scheduled
maintenance jobs still run independently.

To run the same guarded auto-merge locally, after installing requirements:

```bash
GH_TOKEN=... bash scripts/merge_prs.sh thekester/WordHunt
```

Only non-draft PRs from this repository with an
`add-(dicolink|robert)-word-of-the-day-*` branch, targeting holding, and changing
exactly one valid daily JSON file qualify. The source and date must match the
filename. API errors or refused merges make the job fail. Unrelated PRs are skipped.

The manually dispatched salvage workflow opens a review PR into main. It only
recovers missing, valid records from daily-data branches; it never overwrites
existing archives or silently imports malformed results.

## Historical data quality

The September 2026 audit found that all 601 Robert records present in main at
commit `f0fb494` contain suggestion-page text instead of a genuine daily word.
They are retained for traceability, **not valid vocabulary data**. The old endpoint
`/mot-du-jour` must not be used to infer their original words. Their true historical
contents cannot be reconstructed from those files alone.

One empty Dicolink definition in the May 15, 2026 record has been removed while
preserving all meaningful definitions. To inspect the remaining invalid archives:

```bash
python scripts/audit_data.py
```

The audit prints offending filenames/reasons and exits nonzero when any are found.
CI validates changed data separately so historical corruption does not mask a new
regression. Robert's new parsing is covered by synthetic fixtures; a live
end-to-end verification remains necessary because this development environment
received HTTP 403 from Le Robert. It now fails visibly instead of saving false data.

## Contributing and license

Bug reports and pull requests are welcome. Code is licensed under the MIT License.
Dictionary content remains attributable to the respective sources.
