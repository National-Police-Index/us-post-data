# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backend data pipeline for the **National Police Index** — aggregates Peace Officer Standards and Training (POST) databases from U.S. states into a unified Firebase Firestore database. The project handles downloading, cleaning, normalizing, and uploading police officer employment records.

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

### State Cleaning Scripts
```bash
python states/<STATE>/src/clean.py          # e.g., python states/GA/src/clean.py
python states/<STATE>/src/test_cleaning.py  # Run LLM-as-judge validation, writes judge_report.md
```

### Database Pipeline (run from db/)
```bash
cd db && make dry-run STATE=<STATE>    # Preprocess + validate upload manifest (no Firebase write)
cd db && make dry-run                  # Dry-run all states
cd db && make upload STATE=<STATE>     # Live upload one state to Firebase
cd db && make upload                   # Live upload all states
```

## Architecture

### Data Flow
```
Dropbox (national-post-db/<state>/input/)
    → states/<STATE>/data/input/         (raw files, read-only)
    → states/<STATE>/src/clean.py        (state-specific cleaning script)
    → states/<STATE>/output/             (cleaned CSVs + judge_report.md)
    → db/preprocess/                     (normalize + compress → .csv.gz)
    → db/upload/ --dry-run               (validate manifest without writing)
    → db/upload/                         (push to Firebase Firestore)
    → Front-end deployment
```

### Directory Structure

- **`states/<STATE>/data/input/`** — Raw source files fetched from Dropbox. Read-only.
- **`states/<STATE>/data/groundtruth/`** — Reference/ground-truth CSVs for LLM judge comparison. Read-only.
- **`states/<STATE>/src/clean.py`** — State-specific cleaning script. Reads from `data/input/`, writes to `output/`.
- **`states/<STATE>/src/test_cleaning.py`** — LLM-as-judge test suite. Compares output against ground truth and writes `states/<STATE>/output/judge_report.md`.
- **`states/<STATE>/output/`** — Cleaned CSVs and judge report. Consumed by `db/preprocess/`.
- **`states/AGENT_INSTRUCTIONS.md`** — Brief for Claude agents processing a new state.
- **`states/helpers/llm_models.py`** — Azure OpenAI wrapper used by test suites.
- **`DATA_PREPROCESSING.md`** — Authoritative cleaning guide for agents and humans.
- **`db/preprocess/`** — Normalizes all states' data: standardizes dates, expands agency abbreviations, proper-cases names, filters anonymous records. Writes `.csv.gz`.
- **`db/upload/`** — Uploads compressed `.csv.gz` to Firebase Firestore collection `db_launch`. Supports `--dry-run`.
- **`db_archive/`** — Archived original per-state pipeline scripts (superseded).

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

### Adding a New State

1. Place raw Dropbox files in `states/<STATE>/data/input/`
2. Place any reference/ground-truth CSVs in `states/<STATE>/data/groundtruth/`
3. Write `states/<STATE>/src/clean.py` following `DATA_PREPROCESSING.md`
4. Run `python states/<STATE>/src/clean.py` — output goes to `states/<STATE>/output/`
5. Run `python states/<STATE>/src/test_cleaning.py` — review `judge_report.md`
6. Run `cd db && make dry-run STATE=<STATE>` to validate the full pipeline
7. Run `cd db && make upload STATE=<STATE>` when ready for Firebase

### Code Style

- Python 3.10+, target 3.11 for linting
- Line length: 80 characters
- Formatters: `ruff` (linter), `black` (formatter), `isort` (imports)
- CI runs pre-commit on all pushes/PRs to `main` and `dev`
