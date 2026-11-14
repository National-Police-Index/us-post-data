# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Backend data pipeline for the **National Police Index**. It aggregates Peace
Officer Standards and Training (POST) databases from U.S. states into a
unified Firebase Firestore database. The repo handles downloading, cleaning,
normalizing and uploading police officer employment and discipline records.

States are cleaned **by hand**, one release at a time, in
`clean/<year>/<STATE>/`, following `DATA_PREPROCESSING_GUIDE.md`, then
uploaded with `make` from `db/`.

An automated pipeline (`pipeline/`: a Dropbox poll, then a Claude agent that
writes `clean.py`, then an LLM judge, then a PR) also exists but is **paused**.
How to run it is in `AGENT_INSTRUCTIONS.md` and `pipeline/README.md`.

## Cleaning a state

**Start every state from the checklist at the top of
`DATA_PREPROCESSING_GUIDE.md` and tick off every item.** The detailed steps
and worked examples are below it in the guide. Also read the state's old
README (`readmes/<STATE>_README.md`), its old cleaning
(`clean_deprecated/src/<STATE>/`), and the most recent
`clean/<year>/*/src/clean.py` scripts for conventions.

```
clean/<year>/<STATE>/          # uppercase state code
├── README.md                  # source, every cleaning step with counts, open questions
├── src/
│   ├── download.py            # fetch raw data from Dropbox (copy KS's)
│   ├── clean.py               # produce the index
│   └── *.ipynb                # exploratory notebook (optional)
└── data/                      # gitignored
    ├── input/                 # raw files (read-only)
    └── output/
        ├── <state>_index.csv
        ├── <state>-discipline_index.csv   # when the state has discipline data
        └── review/            # every dropped or flagged row
```

```bash
# from clean/<year>/<STATE>/
python src/download.py
python src/clean.py --input-dir data/input --output-dir data/output
```

### `clean.py` house style

Small helper functions (`clean_race(df)`, `clean_dates(df)`) chained with
`.pipe`. Lookup tables and regex lists live **inside** the function that uses
them, with no module-level constants. Use single-line section comments
(`# employment history data`, `# complaint data`) and docstrings of two
sentences at most; the reasoning goes in the state README. Every dropped row
is written to `review/`. See `DATA_PREPROCESSING_GUIDE.md` → "How to write
`clean.py`".

## Uploading (run from `db/`)

`db/preprocess` reads `states/<state>/<year>/output/*_index.csv`, so copy the
index there first (lowercase state code):

```bash
mkdir -p states/<state>/<year>/output
cp clean/<year>/<STATE>/data/output/<state>_index.csv states/<state>/<year>/output/

cd db && make dry-run STATE=<state> YEAR=<year>       # preprocess + validate, no Firebase write
cd db && make upload STATE=<state> YEAR=<year>        # first upload of a state
cd db && make force-upload STATE=<state> YEAR=<year>  # replace a state already in Firebase
```

`YEAR` is required whenever `STATE` is given. `db/preprocess` normalizes
dates, expands agency abbreviations, proper-cases names, drops rows with an
empty `start_date`, and adds `state` and `document_id`
(`<state>_<person_nbr>`). `db/upload` writes to the Firestore collection
`db_launch`, with credentials from `db/upload/serviceAccountKey.json`.
Then run the front-end scripts (guide, Part 2, Step 4).

## Standardized Output Schema

```
person_nbr        # Required: unique officer identifier (lowercase string)
first_name        # Required
last_name         # Required
agency_name       # Required (no agency code prefixes)
start_date        # Required: YYYY-MM-DD
end_date          # YYYY-MM-DD or empty string (empty = currently employed)
# Optional: full_name, middle_name, suffix, rank, employment_status,
#           separation_reason, race, sex, year_of_birth, state,
#           current_certificate_status, position, notes, type
# Discipline index adds: case_id, violation, violation_date, offense,
#           sanction, sanction_date
```

## Commands

```bash
make make-env                 # create the virtualenv with uv
pip install -r requirements.txt
make lint                     # pre-commit on all tracked files
pytest tests/pipeline/ -v     # automated-pipeline unit tests
```

## Code Style and Lint

- Python 3.10+, target 3.11 for linting; line length 80
- `ruff`, `black`, `isort`, plus `nbqa-*` on notebooks and
  `pretty-format-json`
- CI runs pre-commit on PRs and pushes to `main` and `dev`
- **Run lint until every hook passes, then commit.** The first run fixes
  files in place and reports "Failed".
- **`make lint` only covers tracked files.** A new state folder isn't linted
  until it has been `git add`ed. Before that, run
  `pre-commit run --files $(git ls-files -o --exclude-standard clean/)`.
- **Lint again after your last notebook save.** Jupyter and VS Code
  re-indent `.ipynb` files on save, which fails `pretty-format-json`.
- **CI can fail after a local pass:** `nbqa-ruff` installs the latest ruff in
  CI. If it fails, read the diff in the CI log and apply it exactly.
