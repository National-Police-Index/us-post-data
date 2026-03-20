# State Processing — Agent Instructions

You are a data processing agent. Your job is to clean raw POST (Peace Officer Standards and Training) data for a U.S. state and write standardized output CSVs.

**Before doing anything else, read [`DATA_PREPROCESSING.md`](../DATA_PREPROCESSING.md) in full.** It contains the schema definition, step-by-step cleaning process, common pitfalls, and code patterns. This file only tells you *what* to process and *where* files live.

---

## Your Working Directories

```
states/
└── <STATE>/
    ├── data/
    │   ├── input/     ← raw source files from Dropbox (read-only)
    │   └── output/    ← reference/ground-truth outputs (read-only, for comparison)
    ├── output/        ← write your cleaned CSVs here
    └── clean.py       ← write your cleaning script here
```

Replace `<STATE>` with the two-letter state abbreviation in uppercase (e.g. `GA`, `FL`).

---

## What You Must Produce

### Always required

`states/<STATE>/output/<state>_index.csv`

Where `<state>` is the lowercase full state name (e.g. `georgia_index.csv`).

This file must contain at minimum: `person_nbr`, `first_name`, `last_name`, `agency_name`, `start_date`, `end_date`.

### When the state has disciplinary data (GA, FL)

Also produce: `states/<STATE>/output/<state>-discipline_index.csv`

This file must contain at minimum: `person_nbr`, `first_name`, `last_name`, `agency_name`, `start_date`, `end_date`, plus discipline-specific columns (`case_id`, `violation`, `violation_date`, `sanction`, `sanction_date`).

---

## Reference Outputs

Reference outputs (ground truth) are located at:

```
states/<STATE>/data/output/
```

Use these to validate your output schema and spot-check values. Your output does not need to be identical row-for-row (source data may have been updated), but the columns and general data patterns should match.

---

## Cleaning Script

Write a self-contained `states/<STATE>/clean.py` that:
1. Reads from `states/<STATE>/data/input/`
2. Performs all cleaning (see DATA_PREPROCESSING.md for patterns)
3. Writes output to `states/<STATE>/output/`

The script should be runnable as `python states/<STATE>/clean.py` from the repo root, or with paths adjusted accordingly.

---

## Georgia (GA) — Test Case

Georgia is the initial test case. Its raw files are:

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

### Key GA-specific notes

1. **Officer IDs**: `OKEY` values look like `O143810`. Lowercase to `o143810` for `person_nbr`.

2. **Agency names**: The `AGENCY` column in `officer_employment.csv` has codes prepended: `"G1720 DEKALB COUNTY POLICE DEPARTMENT"`. Strip the leading code (`G` + digits + space). Cross-reference `agency_data.csv` (where `AKEY = "G1720"` and `NAME = "DEKALB COUNTY POLICE DEPARTMENT"`) for the canonical name.

3. **Invalid dates**: `end_date = 0000-00-00` means currently employed. Treat as empty string.

4. **Employment index join**: Merge `officer_employment.csv` + `officer_data.csv` on `OKEY` (left join) to get names and demographics alongside employment history.

5. **Discipline index**: Join `officer_violations.csv` + `officer_sanctions.csv` on `CASE`. Attach employment context via `officer_employment.csv` on `OKEY`. Where a person has multiple employment periods, join to the period whose date range most closely contains the `violation_date`.

6. **full_name format**: `"last_name, first_name middle_name suffix"` in lowercase. Include suffix if present (e.g. `"smith, john a jr"`).

7. **Agency name noise**: The `AGENCY` column contains non-agency strings (`APPLICATION DENIED`, `APPLICATION PURGED/18 MOS.`) and status-suffixed names (`G1276 METRO STATE PRISON/INACTIVE`). After stripping the leading code, also strip any trailing slash fragment (`/.*$`) and filter rows where the cleaned name matches known non-agency values (`application denied`, `application purged`, `pending`, `unknown`).

8. **Discipline join — use inner join, not outer**: Join violations (left) to sanctions (right) using `how='inner'` on `(case_id, person_nbr)`. An outer join inflates row counts via cartesian product when a case has multiple violations and sanctions. After joining, deduplicate on `(case_id, person_nbr, violation)` keeping the most recent sanction per violation.

9. **Discipline rows with no employment match**: After the employment context join, drop rows where `start_date` is empty. These are officers present in disciplinary records but absent from the employment table.

---

## Validation Checklist

Before writing output files, verify:

- [ ] All required columns are present
- [ ] `start_date` has no empty values (rows with empty `start_date` are dropped by preprocess pipeline)
- [ ] `person_nbr` is lowercase string with no leading/trailing whitespace
- [ ] `agency_name` has no agency code prefixes
- [ ] Date strings are `YYYY-MM-DD` or empty (not `0000-00-00`, `NaT`, `None`)
- [ ] No fully duplicate rows (`person_nbr` + `agency_name` + `start_date`)
- [ ] Output directory `states/<STATE>/output/` exists

---

## After You Write the Output

Report:
1. Row count of each output file
2. Data quality warnings (empty required fields, duplicate rows, etc.)
3. Column list for each output file
4. State-specific decisions or assumptions made

The next step is: `cd db && make dry-run STATE=<STATE>` to validate preprocessing.
