# Illinois ILETSB Employment History — 2026

## Data Files

Data obtained in 2026 from the [Illinois Law Enforcement Training and
Standards Board (ILETSB)](https://www.ptb.illinois.gov/).

Inputs (in `data/input/`):

| File | Used | Contents |
|---|---|---|
| `26-327.xlsx` | yes | Sheet `Employment` — 237,200 stints. Sheet `Certificates` — not used by the index. |
| `Employment-Table 1.csv` | no | Earlier delivery of the same table. Superseded. |

### Use the xlsx, not the CSV

The two files hold identical data — same 237,200 rows in the same order,
same values in every cell. But the CSV wrote 2-digit years, which loses the
century: `1901-01-01` becomes `1/1/01`, indistinguishable from a real 2001
hire date. The xlsx stores real datetimes, so no parsing heuristic is
needed.

## Replicating

Run from `clean/2026/IL/src/`:

```bash
python clean.py
```

Writes `data/output/illinois_index.csv` plus four review files:

| File | Rows | In the index? |
|---|---|---|
| `review/unusable_hire_date.csv` | 13,791 | dropped |
| `review/end_before_start.csv` | 505 | dropped |
| `review/hired_before_born.csv` | 556 | dropped |
| `review/batch_end_date_2010-01-01.csv` | 27,193 | **kept** — exported for review |

## Python Packages Used

- `pandas`, `openpyxl`

## Data Cleaning and Processing

All cleaning lives in `src/clean.py`.

1. **Read** the `Employment` sheet and map columns: `PTBID` → `person_nbr`,
   `BirthYear` → `year_of_birth`, `Gender` → `sex`, `Employer` →
   `agency_name`, `Branch` → `type`, `Status` → `employment_status`,
   `Hired` → `start_date`, `Separated` → `end_date`, `Reason` →
   `separation_reason`; name, race, education and rank map by their obvious
   equivalents. Adds `state = il` and a `full_name` of
   `"last, first suffix"`.
2. **Dates** convert straight from Excel datetimes to `YYYY-MM-DD`.
3. **Agency names and ranks** are upper-cased and expanded with
   word-bounded patterns (`PD` → `POLICE DEPARTMENT`, `UNIV` →
   `UNIVERSITY`, …; see `AGENCY_ABBREVIATIONS` / `RANK_ABBREVIATIONS`).
   Casing is left to `db/preprocess`.
4. **Drop** rows with no `person_nbr`, no `last_name`, or a non-agency
   `agency_name`, then the rows below, then deduplicate on
   `(person_nbr, agency_name, start_date, end_date)`.
5. **Collapse contiguous stints** at the same agency into one row —
   222,229 → 207,005. ILETSB opens a new row when an officer's rank or
   status changes, so rows for the same `(person_nbr, agency_name)` are
   merged when the next start falls within a day of the latest end so far.
   The merged stint takes the earliest start, the latest end, and rank,
   status and the rest from the most recent row; an empty
   `separation_reason` falls back to the latest one present, and an empty
   `end_date` keeps the stint open. An open end date on a row that is
   followed by another row at the same agency was never closed, so it is
   taken to end at the next start (96 rows).
6. **Blank** `year_of_birth` on 635 rows holding `1901` (ILETSB's
   unknown-value marker) or a malformed `199`. The rest of the row is kept.

### Rows dropped

Each condition is either a specific value the source writes or a
contradiction between two fields. No invented thresholds.

| Condition | Rows | Review file |
|---|---|---|
| `start_date` empty | 16 | `unusable_hire_date.csv` |
| `start_date` is `1900-01-01`, `1901-01-01` or `1902-01-01` | 13,775 | `unusable_hire_date.csv` |
| `end_date` < `start_date` | 505 | `end_before_start.csv` |
| hire year ≤ `year_of_birth` | 556 | `hired_before_born.csv` |

Those three dates are what ILETSB writes when it has no hire date — the
rows carry ordinary separation dates in the 1990s and 2000s. Without a hire
date the stint cannot be placed in time, so it is dropped. This is a change
in policy: they were previously published as `2001-01-01`, which looks
plausible and is undetectable downstream.

### The `2010-01-01` end date — kept, flagged for review

**27,193 rows carry an `end_date` of exactly `2010-01-01`.** It is a
system-wide batch write, not real separations: it spans 1,275 of the
table's 1,582 agencies, and that month holds 39,055 separations against
roughly 250 in the months either side.

They are kept and exported to
`review/batch_end_date_2010-01-01.csv` for the team to decide on. Dropping
them would erase about **16,000 officers entirely** — officers whose only
stint this is — and those records are otherwise sound: real agency, real
hire date, plausible tenure. Only the end date is wrong. Blanking is not an
option either, since an empty `end_date` means *currently employed* in this
schema.

The real gap is that the schema cannot express "separated, date unknown".
That is a schema question for the team.

### Known issues

This index reflects what ILETSB supplied. Where a value is implausible but
not provably wrong, it is left as recorded.

- **Implausible birth years.** Four rows are dated after 2010 (one officer
  is recorded as born in 2017 and hired in 2018); catching them would need
  an invented minimum age. A further 28 rows hold `1900`, possibly the same
  unknown-value marker as `1901`, but 28 is within the natural tail (1914
  has 20).
- **Very early hire dates.** Start years run back to 1908. Likely
  transcription errors, but nothing in the record contradicts them.
- **Other bulk end dates**, left alone because each is concentrated in one
  agency rather than system-wide: `2006-06-23` (6,036 rows, 99.8% Chicago
  PD), `2010-09-16` (1,698 rows, 99.6% IDOC, which has no activity after
  that date), and `2012`/`2016`/`2017-01-01` (95–97% Chicago PD each).
- **Collapsing flattens rank and status history.** A promotion recorded as
  two adjacent rows becomes one stint carrying the later rank. Because the
  collapse happens here, `illinois` is **not** added to `COLLAPSE_STINTS`
  in `db/preprocess`.
- The `Certificates` sheet is unused; available if certification data is
  wanted later.

## Output

`data/output/illinois_index.csv` — 207,005 rows, 137,607 officers,
1,479 agencies. Hire years span 1908–2026.

Columns: `person_nbr`, `last_name`, `first_name`, `middle_name`, `suffix`,
`year_of_birth`, `race`, `sex`, `education`, `agency_name`, `type`,
`employment_status`, `rank`, `start_date`, `end_date`, `separation_reason`,
`state`, `full_name`.
