# State Processing — Agent Instructions

> **This file is for the automated pipeline (`pipeline/`), which is currently
> paused.** The pipeline's agent reads it (`pipeline/cc_agent.py`). Manual
> cleaning happens in `clean/<year>/<STATE>/` instead; see `CLAUDE.md`. How to
> run the pipeline itself is in the
> [appendix](#appendix-running-the-automated-pipeline-paused) at the end.

**Before doing anything else, read [`DATA_PREPROCESSING_GUIDE.md`](DATA_PREPROCESSING_GUIDE.md)
in full.** It is the authoritative schema definition, step-by-step cleaning
process, common pitfalls, and code patterns. This file only tells you *what*
to process and *where* files live.

The guide's checklist applies to you, with two differences. You work in
`states/<state>/<year>/` (below), not `clean/<year>/<STATE>/`. And
`download.py` is not needed, because rclone fills `data/input/` for you.

---

## Working Directories

State codes are **lowercase everywhere**. Each `(state, year)` is fully
self-contained:

```
readmes/
└── <STATE>_README.md  ← state-specific README (read-only, when available)

states/
└── <state>/
    └── <year>/
        ├── data/
        │   ├── input/        ← raw source files from Dropbox (read-only)
        │   └── groundtruth/  ← reference outputs (read-only, when available)
        ├── output/           ← write cleaned CSVs + judge reports here
        └── src/
            ├── clean.py      ← write your cleaning script here
            └── validate.py   ← LLM-as-judge test suite
```

---

## State README (when available)

If `readmes/<STATE>_README.md` exists (e.g. `readmes/CA_README.md`),
**read it before writing `clean.py`**. It provides state-specific context
about the raw data format, column names, file layout, and known quirks that
supplements `DATA_PREPROCESSING_GUIDE.md`.

---

## What You Must Produce

### Always required

`states/<state>/<year>/output/<state>_index.csv`

Must contain at minimum: `person_nbr`, `first_name`, `last_name`,
`agency_name`, `start_date`, `end_date`.

### When the state has disciplinary data

Also produce: `states/<state>/<year>/output/<state>-discipline_index.csv`

Must contain at minimum: `person_nbr`, `first_name`, `last_name`,
`agency_name`, `start_date`, `end_date`, plus discipline-specific columns
(`case_id`, `violation`, `violation_date`, `sanction`, `sanction_date`).

See [Discipline Data](#discipline-data) below for which states apply and how
to handle this.

---

## Cleaning Script

Write `states/<state>/<year>/src/clean.py` that:

1. Accepts `--input-dir` and `--output-dir` CLI args
2. Reads from the path given by `--input-dir`
3. Performs all cleaning (see `DATA_PREPROCESSING_GUIDE.md`)
4. Writes output to the path given by `--output-dir`

Run it from `states/<state>/<year>/` as cwd:

```bash
python src/clean.py --input-dir data/input --output-dir output
```

---

## Validation Script

Write `states/<state>/<year>/src/validate.py` that:

1. Compares output CSVs against ground truth (if available in `data/groundtruth/`)
2. Falls back to schema, date, and `person_nbr` format checks plus LLM quality
   scoring when no ground truth exists
3. Writes **both** of the following to `output/`:
   - `judge_report.md` — human-readable per-check scores
   - `judge_report.json` — machine-readable summary:
     `{"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}`

Run it from `states/<state>/<year>/` as cwd:

```bash
python src/validate.py
```

The report must be **PASS** or **WARN** (not FAIL) to be accepted by the
pipeline.

---

## Ground Truth

Reference outputs live at `states/<state>/<year>/data/groundtruth/` when
available.

- **When present**: run full comparison checks (row counts, value spot-checks).
- **When absent**: fall back to schema + format checks + LLM quality scoring.
  Do not treat missing ground truth as an error.

Your output does not need to be identical row-for-row to the ground truth —
source data may have been updated since the snapshot was taken.

---

## Validation Checklist

Before writing output files, verify:

- [ ] All required columns are present
- [ ] `start_date` has no empty values (rows with empty `start_date` are
      dropped by the preprocess pipeline)
- [ ] `person_nbr` is a lowercase string with no leading/trailing whitespace
- [ ] `agency_name` has no agency code prefixes
- [ ] Date strings are `YYYY-MM-DD` or empty string (not `0000-00-00`, `NaT`,
      `None`)
- [ ] No fully duplicate rows (`person_nbr` + `agency_name` + `start_date`)
- [ ] Output directory exists

---

## Discipline Data

Some states provide a separate disciplinary records table alongside the
employment index. When present, produce a `<state>-discipline_index.csv` in
addition to the standard employment index.

### States with known discipline data

| State | Status | Notes |
|-------|--------|-------|
| GA | Configured — see below | Multiple raw tables; join logic documented |
| FL | Config pending | Similar structure to GA; will be added |

### Unknown states with discipline data

If you are processing a state not listed above and find that the raw input
contains a distinct discipline or misconduct table (separate from the
employment records), treat it as analogous to the GA/FL pattern:

- Produce a `<state>-discipline_index.csv` alongside the standard index
- Use the GA/FL section below as a high-level reference for join logic and
  column mapping
- Note any structural differences in `validate.py` and in your output summary

---

## GA-Specific Configuration

> **GA only.** This section describes raw file layout and join logic specific
> to Georgia. Use it as a reference when processing GA, or as a structural
> analogy when encountering a new state with similar discipline tables.

### Raw files

| File | Contents |
|------|----------|
| `officer_employment.csv` | Primary: one row per officer-agency stint. Columns: `OKEY`, `NAME`, `AGENCY`, `RANK`, `STATUS`, `START DATE`, `END DATE` |
| `officer_data.csv` | Demographics: `OKEY`, `LAST NAME`, `FIRST NAME`, `MIDDLE`, `SUFFIX`, `YOB`, `SEX`, `RACE` |
| `agency_data.csv` | Agency registry: `AKEY`, `NAME` and address fields |
| `officer_violations.csv` | Disciplinary: `CASE`, `OKEY`, `NAME`, `VIOLATION`, `VIOLATION DATE` |
| `officer_sanctions.csv` | Disciplinary: `CASE`, `OKEY`, `NAME`, `SANCTION`, `DATE` |
| `officer_investigations.csv` | Disciplinary: `CASE`, `OKEY`, `NAME`, `AGENCY`, `DATE OPENED` |
| `officer_certifications.csv` | Certification history (not needed for index) |
| `officer_registrations.csv` | Registration history (not needed for index) |
| `officer_instructor_certifications.csv` | Instructor certs (not needed for index) |
| `course_codes_current.csv` | Course catalog (not needed for index) |
| `course_codes_legacy.csv` | Historical course catalog (not needed for index) |
| `academy_list.csv` | Academy directory (not needed for index) |
| `reciprocity.csv` | Cross-state reciprocity (not needed for index) |

### Key GA-specific cleaning notes

1. **Officer IDs**: `OKEY` values look like `O143810`. Lowercase to `o143810`
   for `person_nbr`.

2. **Agency names**: The `AGENCY` column in `officer_employment.csv` has codes
   prepended: `"G1720 DEKALB COUNTY POLICE DEPARTMENT"`. Strip the leading
   code (`G` + digits + space). Cross-reference `agency_data.csv` (where
   `AKEY = "G1720"` maps to `NAME = "DEKALB COUNTY POLICE DEPARTMENT"`) for
   the canonical name.

3. **Invalid dates**: `end_date = 0000-00-00` means currently employed. Treat
   as empty string.

4. **Employment index join**: Merge `officer_employment.csv` +
   `officer_data.csv` on `OKEY` (left join) to get names and demographics
   alongside employment history.

5. **Discipline index**: Join `officer_violations.csv` +
   `officer_sanctions.csv` on `CASE` using **inner join** (not outer — outer
   join inflates row counts via cartesian product when a case has multiple
   violations and sanctions). After joining, deduplicate on
   `(case_id, person_nbr, violation)` keeping the most recent sanction per
   violation. Attach employment context via `officer_employment.csv` on
   `OKEY`. Where a person has multiple employment periods, join to the period
   whose date range most closely contains the `violation_date`. Drop rows
   where `start_date` is empty after the join.

6. **`full_name` format**: `"last_name, first_name middle_name suffix"` in
   lowercase. Include suffix if present (e.g. `"smith, john a jr"`).

7. **Agency name noise**: After stripping the leading code, also strip any
   trailing slash fragment (`/.*$`) and filter rows where the cleaned name
   matches known non-agency values (`application denied`,
   `application purged`, `pending`, `unknown`).

---

## Appendix: running the automated pipeline (paused)

> For operators, not the agent. This section was moved here from `CLAUDE.md`
> when the pipeline was paused, so none of it is lost. Setup, secrets and
> `registry.csv` are also described in `pipeline/README.md`.

### What it does

`pipeline/` polls Dropbox for new data and invokes a Claude SDK agent to
write state-specific `clean.py` and `validate.py`. It then runs the
LLM-as-judge validation and opens a GitHub PR. A GitHub Actions workflow
(`.github/workflows/firebase-upload.yaml`) uploads to Firebase on merge.

### Commands

```bash
# Run against test remote (ga and ca test states):
set -a && source states/helpers/.env && set +a
RCLONE_REMOTE=dropbox:post-db-test python3 -m pipeline.main --states ga ca

# Run against production remote (all states):
python3 -m pipeline.main

# Run a single state:
python3 -m pipeline.main --states ga

# Re-run a state by hand (from states/<state>/<year>/):
python src/clean.py --input-dir data/input --output-dir output
python src/validate.py   # LLM-as-judge: writes output/judge_report.md + judge_report.json

# Unit tests:
pytest tests/pipeline/ -v
```

### Data flow

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

State codes are **lowercase everywhere** (dirs, rclone paths, registry).

### `pipeline/` package

- `main.py`: CLI entry point (`python -m pipeline.main --states ga ca`)
- `orchestrate.py`: wires rclone → CC agent → PR together
- `cc_agent.py`: Anthropic SDK tool-use loop (writes clean.py + validate.py)
- `rclone_client.py`: Dropbox sync (list_years, lsjson, copy, copy_groundtruth)
- `clean_runner.py`: runs an existing clean.py + validate.py
- `pr_generator.py`: commits outputs, opens a GitHub PR
- `registry.py`: tracks cleaned/firebase_pushed per (state, year)
- `state_manifest.py`: rclone lsjson snapshots for change detection
- `judge_parser.py`: reads judge_report.json (preferred), falls back to .md
- `data/manifest.json`: change-detection snapshots (git-tracked)
- `data/registry.csv`: clean/Firebase status per (state, year) (git-tracked)
- `logs/`: runtime logs (gitignored)

Related: `states/<state>/<year>/data/groundtruth/` (reference CSVs for the
judge) and `states/helpers/llm_models.py` (Azure OpenAI wrapper used by
`validate.py`).

### CC agent

`pipeline/cc_agent.py` uses the Anthropic Python SDK tool-use loop:

- Model `claude-sonnet-4-6`, `MAX_TURNS=100`, `MAX_TOKENS=16384`
- Tools: `read_file`, `write_file`, `append_to_file`, `edit_file`, `bash`
- Reads this file, `DATA_PREPROCESSING_GUIDE.md` and
  `readmes/<STATE>_README.md` (if present)
- Streams every turn to `pipeline/logs/cc-agent-<state>-<year>-<ts>.log`
- Do not call it with `claude --print`: that exits 0 with empty stdout when
  run from inside a Claude Code session

### Secrets

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | CC agent (Anthropic SDK) |
| `RCLONE_CONFIG` | rclone.conf for Dropbox access |
| `RCLONE_REMOTE` | Override remote (default: `dropbox:national-post-db`) |
| `AZURE_ENDPOINT` / `AZURE_API_KEY` / `API_VERSION` | LLM judge (Azure OpenAI) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase upload from CI |

Locally these go in `states/helpers/.env`; in CI they are GitHub secrets.
