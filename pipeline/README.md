# Pipeline — Setup & Secrets

## Directory structure

Each `(state, year)` is fully self-contained:

```
states/ga/
  2025/
    src/
      clean.py        # year-specific cleaning script (--input-dir / --output-dir args)
      validate.py     # LLM judge — writes output/judge_report.md + judge_report.json
    data/
      input/          # synced from Dropbox ga/2025/input/ only
      groundtruth/    # local only — NOT synced from Dropbox
    output/           # cleaned CSVs + judge_report.md + judge_report.json
```

State codes are **lowercase everywhere**.

## pipeline/data/ files

| File | Purpose |
|------|---------|
| `manifest.json` | rclone lsjson snapshots per `(state, year)` — auto-managed, tracked in git |
| `registry.csv` | Clean/Firebase status per `(state, year)` — human-editable, tracked in git |
| `groundtruth.md` | Quality reference for states without CSV groundtruth |

### registry.csv columns

| Column | Values |
|--------|--------|
| `state` | lowercase state code |
| `year` | 4-digit year string |
| `cleaned` | `yes` / `no` |
| `firebase_pushed` | `no` / `yes` / `skipped` |

`skipped` = cleaned but intentionally not pushed (superseded by a newer year).

### judge_report.json schema

`validate.py` in each state must write this alongside the human-readable `judge_report.md`:

```json
{"overall": "PASS", "has_groundtruth": true}
```

`overall` values: `PASS`, `WARN` (both treated as success), `FAIL`.

## Required GitHub Secrets

| Secret | How to get it |
|--------|--------------|
| `RCLONE_CONFIG` | `rclone config` locally → copy `~/.config/rclone/rclone.conf` |
| `RCLONE_REMOTE` | e.g. `dropbox:national-post-db` (override for testing) |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `AZURE_ENDPOINT` | Azure portal → OpenAI resource |
| `AZURE_API_KEY` | Azure portal → OpenAI resource |
| `API_VERSION` | e.g. `2024-02-01` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase console → Service Accounts → Generate key |

## Local usage

```bash
brew install rclone
rclone config   # create remote named "dropbox", authorize via browser

# Test against post-db-test folder:
RCLONE_REMOTE=dropbox:post-db-test python -m pipeline.main --states ga ca

# Production (all states):
python -m pipeline.main
```

## Pre-seeding already-processed pairs

Add rows to `pipeline/data/registry.csv` with `cleaned=yes` before the first run.
The pipeline will seed `manifest.json` from Dropbox for those pairs on startup —
so they won't be re-downloaded or re-cleaned unless their files actually change on Dropbox.

```csv
state,year,cleaned,firebase_pushed
ga,2025,yes,yes
```
