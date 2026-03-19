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

### Database Pipeline (run in order)
```bash
cd db/download && make download      # Stage 1: Fetch CSVs from Dropbox → data/output/
cd db/preprocess && make run         # Stage 2: Normalize data → data/output/*.csv.gz
cd db/preprocess && make run-force   # Stage 2: Force reprocess all states
cd db/upload && make run             # Stage 3: Upload to Firebase Firestore
cd db/upload && make run FORCE_STATES="CA,VA" DELAY=2   # Upload specific states with delay
```

### Running a single state cleaning script
```bash
python clean/src/<STATE>/clean.py    # e.g., python clean/src/VA/clean.py
```

## Architecture

### Data Flow
```
State agency raw data
    → Dropbox (national-post-db/<state>/input/)
    → clean/src/<STATE>/clean.py     (state-specific cleaning)
    → Dropbox (national-post-db/<state>/output/<state>-index.csv)
    → db/download/                   (fetch from Dropbox)
    → db/preprocess/                 (normalize across all states)
    → db/upload/                     (push to Firebase Firestore)
    → Front-end deployment
```

### Directory Structure

- **`clean/src/<STATE>/`** — State-specific cleaning scripts. Each state has its own `clean.py` (and often notebooks) with custom logic for its raw data format. Output is uploaded to Dropbox.
- **`db/download/`** — Downloads cleaned CSVs from Dropbox. Dropbox links are stored in `db/download/src/src.py`.
- **`db/preprocess/`** — Normalizes all states' data to a consistent schema. Key operations: standardizing dates to YYYY-MM-DD, expanding agency abbreviations (SO→Sheriff's Office, PD→Police Department), proper-casing names, filtering anonymous records, collapsing contiguous employment stints.
- **`db/upload/`** — Uploads compressed `.csv.gz` files to Firebase Firestore collection `db_launch`. Documents are keyed as `<state>-processed.csv_<index>`.
- **`data/`** — Local data storage organized by state (gitignored).

### Standardized Output Schema

Every state's cleaned data must conform to this schema:

```
person_nbr        # Required: unique officer identifier
full_name         # Required
first_name        # Required
middle_name       # Optional
last_name         # Required
agency_name       # Required
rank              # Required
start_date        # Required: YYYY-MM-DD
end_date          # Required: YYYY-MM-DD
state             # Required: lowercase two-letter code (e.g., "va")
# Optional fields: current_certificate_status, position, status, notes,
#                  offense, sanction, violation, sanction_date,
#                  separation_reason, employment_status, certification_type, type
```

The `document_id` field is generated as `<state>_<person_nbr>` during preprocessing.

### Adding a New State

1. Create `clean/src/<STATE>/clean.py` to read raw data and output a CSV matching the schema above
2. Upload output to Dropbox at `national-post-db/<state>/output/<state>-index.csv`
3. Add Dropbox download link to `db/download/src/src.py`
4. Run the full database pipeline

### Code Style

- Python 3.10+, target 3.11 for linting
- Line length: 80 characters
- Formatters: `ruff` (linter), `black` (formatter), `isort` (imports)
- CI runs pre-commit on all pushes/PRs to `main` and `dev`
