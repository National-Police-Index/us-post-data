# db — Processing Pipeline

Takes cleaned state index CSVs produced by the automated processing agent and preprocesses + uploads them to Firebase Firestore.

## Data Flow

```
automated_processing/data/output/<STATE>/<state>_index.csv
    ↓
db/preprocess/   — normalize, validate, compress → db/data/output/<STATE>/*.csv.gz
    ↓
db/upload/       — upload to Firebase (db_launch collection)
```

## Prerequisites

- Python dependencies installed (`pip install -r requirements.txt` from repo root)
- For live upload only: `db/upload/serviceAccountKey.json` (Firebase credentials)

## Commands

Run from the `db/` directory:

```bash
# Full pipeline for one state — preprocess + dry run (no Firebase needed)
make dry-run STATE=GA

# Full pipeline for all states — preprocess + dry run
make dry-run

# Live upload one state (preprocesses first)
make upload STATE=GA

# Force re-upload (deletes existing state data in Firebase, then re-uploads)
make force-upload STATE=GA

# Preprocess only (no upload)
make preprocess STATE=GA

# Preprocess with force (reprocess even if output already exists)
cd preprocess && make run-force STATE=GA
```

## Input

Cleaned CSVs written by the processing agent:

```
automated_processing/data/output/
└── <STATE>/
    ├── <state>_index.csv               ← employment history (required)
    └── <state>-discipline_index.csv    ← disciplinary records (GA, FL only)
```

The agent is instructed by `automated_processing/AGENT_INSTRUCTIONS.md`.

## Output

Compressed files ready for Firebase:

```
db/data/output/
└── <STATE>/
    ├── <state>-processed.csv.gz
    └── <state>-discipline-processed.csv.gz   (if discipline index exists)
```

## Preprocessing Transformations

Applied to all states:

1. Normalize column names (lowercase, strip whitespace)
2. Lowercase string columns: `person_nbr`, `first_name`, `last_name`, `agency_name`, `start_date`, `end_date`, and demographic columns
3. Clean dates — strip decimal precision, replace `nan` with empty, drop rows with empty `start_date`
4. Expand agency abbreviations: `so` → `sheriff's office`, `pd` → `police department`
5. Apply proper casing to name/agency columns (with special handling for roman numerals, Jr/Sr, abbreviations)
6. Filter out records where `last_name` contains "withheld"
7. Validate required columns are present
8. Add `state` field (lowercase hyphenated state name)
9. Add `document_id` field (`<state>_<person_nbr>`)
10. Compress output as `.csv.gz`

## Firebase Structure

- **Collection:** `db_launch`
- **Document ID pattern:** `<state>-processed.csv_<row_index>`
  - e.g. `georgia-processed.csv_0`, `georgia-processed.csv_1`, ...
  - Discipline: `georgia-discipline-processed.csv_0`, ...

## Archive

The previous `db/` implementation (with hardcoded Dropbox download URLs) has been moved to `db_archive/`. It is no longer used but preserved for reference.
