# POST Data Quality Standards — Groundtruth Reference

Used by `test_cleaning.py` scripts when no state-specific CSV groundtruth
exists in `data/groundtruth/`. Defines what correct POST output looks like.

> **TODO (future):** Build a more comprehensive version of this file by
> iterating over all existing state `test_cleaning.py` scripts and
> `data/groundtruth/` CSVs to extract common patterns, edge cases, and
> state-specific quirks into a single unified reference.

---

## Output files expected

A typical state produces two CSVs in `output/`:

| File pattern | Content |
|---|---|
| `<state>_index.csv` | Employment records — one row per officer+agency stint |
| `<state>-discipline_index.csv` | Discipline/sanction records (if available) |

Both files are fed through `db/preprocess/` before upload to Firebase.

---

## Required columns (employment)

| Column | Type | Rules |
|---|---|---|
| `person_nbr` | string | **Required.** Unique officer identifier; lowercase; no whitespace |
| `first_name` | string | **Required.** Proper case |
| `last_name` | string | **Required.** Proper case |
| `agency_name` | string | **Required.** Full name — no agency codes (see below) |
| `start_date` | string | **Required.** `YYYY-MM-DD`; never empty |
| `end_date` | string | `YYYY-MM-DD` or empty string (empty = currently employed) |

## Optional columns (employment)

Include when available in source data:

| Column | Rules |
|---|---|
| `full_name` | Combined name; proper case |
| `middle_name` | Parsed separately; not merged into first/last |
| `suffix` | `Jr`, `Sr`, `II`, `III`, `IV` — never appended to last_name |
| `rank` | Officer rank/title |
| `employment_status` | e.g. `Voluntary Resignation`, `Terminated` |
| `separation_reason` | Reason for leaving |
| `race` | Lowercase, e.g. `black or african american (not hispanic or latino)` |
| `sex` | `male` / `female` (lowercase) |
| `year_of_birth` | 4-digit integer or string |
| `current_certificate_status` | Certification status |
| `position` | Position title |
| `state` | Lowercase 2-letter abbreviation, e.g. `ga` |

## Discipline columns (when applicable)

| Column | Rules |
|---|---|
| `case_id` | Unique case identifier |
| `offense` | Description of disciplinary offense |
| `sanction` | Sanction imposed (e.g. `REVOKE CERTIFICATION`) |
| `violation` | Type of violation (e.g. `DEPARTMENTAL RULE(S) VIOLATIONS`) |
| `sanction_date` | `YYYY-MM-DD` |
| `violation_date` | `YYYY-MM-DD` |

---

## Reference data — Georgia 2025

The Georgia dataset is the canonical example. Columns from `georgia_index.csv`:

```
person_nbr, full_name, first_name, middle_name, last_name, suffix,
agency_name, rank, employment_status, start_date, end_date,
year_of_birth, race, sex, state
```

Columns from `georgia-discipline_index.csv`:

```
case_id, person_nbr, sanction, sanction_date, violation, violation_date,
full_name, agency_name, rank, start_date, end_date,
last_name, first_name, middle_name, suffix, year_of_birth, race, sex
```

Key observations from GA:
- `person_nbr` format: `o` prefix + 6 digits, e.g. `o143810`
- Agency names are fully expanded (no codes like `G1720`)
- Names are lowercase (GA source has them lowercase; other states may vary)
- `state` column contains `ga`

---

## Quality checks test_cleaning.py must run

### 1. Schema check — FAIL if failing
- All required columns present in output CSV
- `start_date` has zero empty/null values

### 2. Date format check — FAIL if failing
- All date columns (`start_date`, `end_date`, `sanction_date`, `violation_date`)
  must match `YYYY-MM-DD`
- These are invalid: `0000-00-00`, `NaT`, `None`, `nan`, empty string in start_date

### 3. `person_nbr` format check — WARN if failing
- All values must be lowercase
- No whitespace characters
- Values must be consistent across employment and discipline tables

### 4. Row count check — WARN if > 5% difference from reference
- If CSV groundtruth exists: compare row count; WARN if diff > 5%
- If no CSV groundtruth: log count and SKIP

### 5. Agency name quality — WARN if LLM score < 6/10
LLM judge evaluates:
- **No raw codes**: agency names like `G1720 DEKALB...` or `P0042 ...` are FAIL
- **Abbreviations expanded**:
  - `PD` → `Police Department`
  - `SO` → `Sheriff's Office`
  - `DEPT` → `Department`
  - `CO` → `County` (context-dependent)
- Overall similarity to reference list (if available)

### 6. Name parsing quality — WARN if LLM score < 6/10
LLM judge evaluates:
- `first_name` and `last_name` not swapped
- Suffixes (`Jr`, `Sr`, `II`, `III`) in `suffix` column, not in `last_name`
- `middle_name` populated where present; not merged into other columns
- No punctuation attached to names (stray commas, periods)
- Consistent casing (not ALL CAPS)

---

## Overall result logic

| Condition | Result |
|---|---|
| Any check returns `FAIL` | `FAIL` |
| Any check returns `WARN`, no `FAIL` | `WARN` |
| All checks `PASS` or `SKIP` | `PASS` |

`judge_report.md` must contain the line:
```
**Overall result:** `PASS`
```
(or `WARN` / `FAIL`). Exit code 1 on `FAIL`, 0 on `PASS`/`WARN`.

---

## How to use this file in test_cleaning.py

```python
# At the top of test_cleaning.py for a new state:
GROUNDTRUTH_DIR = os.path.join(BASE, "data", "groundtruth")
has_groundtruth = (
    os.path.isdir(GROUNDTRUTH_DIR)
    and any(f.endswith(".csv") for f in os.listdir(GROUNDTRUTH_DIR))
)
if not has_groundtruth:
    # Refer to pipeline/data/groundtruth.md for quality standards.
    # Row count and direct comparison checks will be SKIP.
    # Schema, date, person_nbr, agency name, and name parsing checks still run.
    pass
```

The LLM judge prompts should reference the standards in this document when
no CSV groundtruth is available (e.g., "agency names must not contain raw
codes like G1720; abbreviations like PD should be expanded").
