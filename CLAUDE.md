# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backend data pipeline for the **National Police Index** — aggregates Peace Officer Standards and Training (POST) databases from U.S. states into a unified Firebase Firestore database. The project handles downloading, cleaning, normalizing, and uploading police officer employment records.

An automated `pipeline/` package polls Dropbox for new data, invokes a Claude SDK agent to write state-specific cleaning scripts, runs LLM-as-judge validation, and opens a GitHub PR. A GitHub Actions workflow triggers Firebase upload on merge.

## Commands

### Environment Setup
```bash
make make-env            # Create virtual environment using uv
pip install -r requirements.txt
```

### Linting / Formatting
```bash
make lint                # Run pre-commit hooks on all files (ruff, black, isort)
```

### Automated Pipeline
```bash
# Run against test remote (ga and ca test states):
set -a && source states/helpers/.env && set +a
RCLONE_REMOTE=dropbox:post-db-test python3 -m pipeline.main --states ga ca

# Run against production remote (all states):
python3 -m pipeline.main

# Run a single state:
python3 -m pipeline.main --states ga
```

### Manual State Cleaning (run from states/<state>/<year>/)
```bash
python src/clean.py --input-dir data/input --output-dir output
python src/validate.py   # LLM-as-judge — writes output/judge_report.md + judge_report.json
```

### Database Pipeline (run from db/)
```bash
cd db && make dry-run STATE=<STATE>    # Preprocess + validate upload manifest (no Firebase write)
cd db && make dry-run                  # Dry-run all states
cd db && make upload STATE=<STATE>     # Live upload one state to Firebase
cd db && make upload                   # Live upload all states
```

### Tests
```bash
pytest tests/pipeline/ -v              # Run all pipeline unit tests (56 tests)
```

## Architecture

### Data Flow
```
Dropbox (<remote>/<state>/<year>/input/)
    → states/<state>/<year>/data/input/     (raw files, read-only)
    → states/<state>/<year>/src/clean.py    (CC agent writes this)
    → states/<state>/<year>/output/         (cleaned CSVs + judge reports)
    → db/preprocess/                        (normalize + compress → .csv.gz)
    → db/upload/ --dry-run                  (validate manifest without writing)
    → db/upload/                            (push to Firebase Firestore)
    → Front-end deployment
```

State codes are **lowercase everywhere** (dirs, rclone paths, registry). Each `(state, year)` is fully self-contained.

### Directory Structure

- **`pipeline/`** — Automated pipeline package (see `pipeline/README.md`)
  - `main.py` — CLI entry point (`python -m pipeline.main --states ga ca`)
  - `orchestrate.py` — Wires rclone → CC agent → PR together
  - `cc_agent.py` — Anthropic SDK tool-use loop (writes clean.py + validate.py)
  - `rclone_client.py` — Dropbox sync (list_years, lsjson, copy, copy_groundtruth)
  - `clean_runner.py` — Runs existing clean.py + validate.py
  - `pr_generator.py` — Commits outputs, opens GitHub PR
  - `registry.py` — Tracks cleaned/firebase_pushed per (state, year)
  - `state_manifest.py` — rclone lsjson snapshots for change detection
  - `judge_parser.py` — Reads judge_report.json (preferred) + .md fallback
  - `data/manifest.json` — Change-detection snapshots (git-tracked)
  - `data/registry.csv` — Clean/Firebase status per (state, year) (git-tracked)
  - `logs/` — Runtime logs (gitignored)
- **`readmes/<STATE>_README.md`** — State-specific README files. The CC agent reads these before writing clean.py.
- **`states/<state>/<year>/data/input/`** — Raw source files from Dropbox. Read-only.
- **`states/<state>/<year>/data/groundtruth/`** — Reference CSVs for LLM judge comparison. Read-only.
- **`states/<state>/<year>/src/clean.py`** — State+year-specific cleaning script.
- **`states/<state>/<year>/src/validate.py`** — LLM-as-judge test suite. Writes `output/judge_report.md` + `output/judge_report.json`.
- **`states/<state>/<year>/output/`** — Cleaned CSVs and judge reports. Consumed by `db/preprocess/`.
- **`AGENT_INSTRUCTIONS.md`** — Brief for Claude agents processing a new state (repo root).
- **`DATA_PREPROCESSING.md`** — Authoritative cleaning guide for agents and humans.
- **`states/helpers/llm_models.py`** — Azure OpenAI wrapper used by validate.py.
- **`db/preprocess/`** — Normalizes all states' data: standardizes dates, expands agency abbreviations, proper-cases names, filters anonymous records. Writes `.csv.gz`.
- **`db/upload/`** — Uploads compressed `.csv.gz` to Firebase Firestore collection `db_launch`. Supports `--dry-run`.

### CC Agent

`pipeline/cc_agent.py` uses the Anthropic Python SDK tool-use loop:
- Model: `claude-sonnet-4-6`, `MAX_TURNS=100`, `MAX_TOKENS=16384`
- Tools: `read_file`, `write_file`, `append_to_file`, `edit_file`, `bash`
- Reads `readmes/<STATE>_README.md` if present (state-specific context)
- Streams every turn to `pipeline/logs/cc-agent-<state>-<year>-<ts>.log`
- Requires `ANTHROPIC_API_KEY` in env (`states/helpers/.env` locally, GitHub secret in CI)

### Standardized Output Schema

Every state's cleaned data must conform to this schema:

```
person_nbr        # Required: unique officer identifier (lowercase string)
first_name        # Required
last_name         # Required
agency_name       # Required (no agency code prefixes)
start_date        # Required: YYYY-MM-DD
end_date          # YYYY-MM-DD or empty string (empty = currently employed)
# Optional: full_name, middle_name, suffix, rank, employment_status,
#           separation_reason, race, sex, year_of_birth, state,
#           current_certificate_status, position, notes,
#           offense, sanction, violation, sanction_date, type
```

The `document_id` field (`<state>_<person_nbr>`) and `state` field are added by `db/preprocess/`.

### Adding a New State (manual)

1. Place raw Dropbox files in `states/<state>/<year>/data/input/`
2. Place any reference/ground-truth CSVs in `states/<state>/<year>/data/groundtruth/`
3. Write `states/<state>/<year>/src/clean.py` following `DATA_PREPROCESSING.md`
4. Run from `states/<state>/<year>/`: `python src/clean.py --input-dir data/input --output-dir output`
5. Run `python src/validate.py` — review `output/judge_report.md`
6. Run `cd db && make dry-run STATE=<STATE>` to validate the full pipeline
7. Run `cd db && make upload STATE=<STATE>` when ready for Firebase

### Required Secrets

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | CC agent (Anthropic SDK) |
| `RCLONE_CONFIG` | rclone.conf for Dropbox access |
| `RCLONE_REMOTE` | Override remote (default: `dropbox:national-post-db`) |
| `AZURE_ENDPOINT` / `AZURE_API_KEY` / `API_VERSION` | LLM judge (Azure OpenAI) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase upload |

### Code Style

- Python 3.10+, target 3.11 for linting
- Line length: 80 characters
- Formatters: `ruff` (linter), `black` (formatter), `isort` (imports)
- CI runs pre-commit on all pushes/PRs to `main` and `dev`
- **Always run `make lint` before committing.** CI will fail if pre-commit hooks find issues. Run until all hooks pass, then commit.
