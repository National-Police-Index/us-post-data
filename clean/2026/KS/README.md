# Kansas CPOST Employment History — 2026

## Data Files

Data obtained in July 2026 via a Kansas Open Records Act (KORA) request to
the [Kansas Commission on Peace Officers' Standards and Training
(KS-CPOST)](https://www.kscpost.gov/), covering employment stints that
started from November 2024 onward. It is appended to the previously cleaned
KS index (`ks-2024-index.csv`, stints from 1979 through 2024).

The raw files live in a Dropbox shared folder (link in `src/download.py`)
and, once downloaded, in `data/input/`:

| File | Used | Contents |
|---|---|---|
| `ks-2024-index.csv` | yes | Previously cleaned KS index, 24,905 rows |
| `Nov-Dec 2024 Employment History.xls` | yes | 179 stints starting 2024-11-01 → 2024-12-31 |
| `2025 Employment History.xls` | yes | 1,602 stints starting in 2025 |
| `2026 Employment History.xls` | yes | 798 stints starting 2026-01-01 → 2026-07-27 |
| `2025 TY Certification Status Report.xls` | no | Certification status per officer (used only to confirm the meaning of the F/P status code) |
| `2026 TY Certification Status Report.xls` | no | Same, 2026 |
| `KORA Request ... .pdf` | no | Email correspondence with CPOST |

Each `Employment History.xls` has a 5-row title block, then one row per
stint in columns C–K: `Officer Name`, `Cert ID`, `Agency Name`,
`Start Date`, `Stop or Leave Date`, `Officers Rank`, `Status`.

### How the three exports relate

They are **disjoint by start date** — each file is the set of stints that
*began* in that window, not a snapshot of everyone employed. Concatenating
them produces no duplicates. The only overlap is with the old index, which
was pulled in late December 2024 and already contains 115 of the Nov–Dec
2024 stints (with fewer end dates filled in). The old index's rows from
2024-11-01 on are therefore dropped in favour of the new file.

## Replicating

Run everything from `clean/2026/KS/`.

```bash
# 1. Download the shared folder as a zip and extract it into data/input/.
python src/download.py --keep-zip

# 2. Clean. Writes data/output/ks_index.csv plus audit files in
#    data/output/review/.
python src/clean.py --input-dir data/input --output-dir data/output

# 3. Hand off to the db pipeline (it reads states/<state>/<year>/output/).
mkdir -p ../../../states/ks/2026/output
cp data/output/ks_index.csv ../../../states/ks/2026/output/
cd ../../../db && make dry-run STATE=ks YEAR=2026
```

`xlrd` is required to read the legacy `.xls` files (it is in
`pyproject.toml`).

## Python Packages Used

- `pandas`, `xlrd`: reading xls/csv, data manipulation
- `nameparser`: splitting `Officer Name` into first/middle/last/suffix
- `requests`: downloading the Dropbox zip

## Data Cleaning and Processing

All cleaning lives in `src/clean.py`. In order:

1. **Load** the old index and the three xls files, and normalise columns:
   - `person_nbr`: from `Cert ID` (the CPOST certification number)
   - `full_name`: from `Officer Name`, whitespace collapsed
   - `agency_name`: from `Agency Name` (see below)
   - `rank`: from `Officers Rank` (see below)
   - `employment_status`: from `Status` — `F` → `Full-Time`, `P` →
     `Part-Time` (confirmed against the Certification Status Report, which
     spells the same values out)
   - `start_date`, `end_date`: from `Start Date` / `Stop or Leave Date`,
     coerced to `YYYY-MM-DD`. CPOST uses `1/1/0001` for "no end date"; it
     becomes an empty string (currently employed).
   - `state`: `ks`
2. **Supersede**: drop old-index rows with `start_date >= 2024-11-01`
   (115 rows, all re-reported in the Nov–Dec 2024 file).
3. **Drop test records** (23 rows): agencies matching `^test` (`TEST
   AGENCY`, `TEST9999`, `Test Agnecy123`) and names matching `^test`,
   `testtttt…`, `testmmmm…`, `mpa mpb`. One of these (`test manoj`) sits
   under a real sheriff's office.
4. **Resolve duplicates** on `(person_nbr, agency_name, start_date)`
   (913 rows dropped). These all come from the old index, which was built by
   concatenating overlapping CPOST exports, so most stints appear once
   open and once with the end date that was reported later. The row with the
   latest end date wins (closed beats open) and supplies rank and status.
5. **Collapse contiguous stints** (26,433 → 23,608 rows). CPOST closes a row
   and opens a new one whenever an officer's rank or full/part-time status
   changes, so an officer typically has several back-to-back rows at one
   agency. Rows for the same `(person_nbr, agency_name)` are merged when the
   next start is within one day of the latest end seen so far; the merged
   stint takes the earliest start, the latest end, and rank / status / name
   from the most recent row. This is adapted from
   `collapse_contiguous_stints` in `db/preprocess/src/src.py` with one
   change: an open end date on a row that is *followed* by another row at
   the same agency is treated as stale (CPOST never closed it) and is taken
   to end when the next row starts, so the merged stint is open only if its
   most recent row is open. Because collapsing happens here, `kansas` is
   **not** added to `COLLAPSE_STINTS` in preprocess.
6. **Name parsing**: `nameparser.HumanName` on `full_name`, with `Marquis`
   removed from its title list; positional fallback when it cannot find
   both a first and last name (`JR McCreery`); a leading particle stays
   with the first name (`De Anna Jo Balencia` → first `De Anna`). The
   old index's pre-parsed name columns are discarded and re-parsed so all
   rows use the same rules.
7. **Write** `data/output/ks_index.csv`, sorted by `person_nbr`,
   `start_date`.

### Agency names

Abbreviations are expanded with word-bounded, case-insensitive patterns
(`Dept` → `Department`, `Univ` → `University`, `Comm College` → `Community
College`, then `Comm` → `Commission`, `Co` → `County`, `Dist Attrny` →
`District Attorney`, `Dist` → `District`, `Div` → `Division`, `Sec` →
`Security`, `Med` → `Medical`, `KS` → `Kansas`, `USD #229` → `Unified School
District #229`, `MTAA` → `Metropolitan Topeka Airport Authority`, `PD` →
`Police Department`). Two whole-name rewrites: `KSCPOST` → `Kansas
Commission on Peace Officers' Standards and Training`, and `Kansas City KS
Comm College Campus Police` → `Kansas City Kansas Community College Police`
(the same institution under its current name; one officer had the same
stint listed under both spellings). Casing is left to `db/preprocess`.

### Ranks

The 2010–2022 exports used codes (`TRPR`, `PRGR`, `NRO`, `INT CHF`, …) that
later exports spell out. Codes with an unambiguous expansion are mapped
(see `RANK_CODES` in `clean.py`). Twenty codes with no safe expansion are
left as upper-case codes rather than guessed: `AMGR`, `ATPM`, `CNOF`, `FSP2`,
`ISP`, `MCI`, `MCI2`, `MDPTY`, `SAG2`, `SAGS`, `SAGT ISP`, `SFOF`, `SIN`,
`SIN 2`, `SINV`, `SINVR`, `SRVO`, `STOF`, `TSO`, `WPMR`, `WTOF` (~65 rows).

### Known issues

- 79 rows have `end_date` earlier than `start_date` — source typos (e.g. a
  2025 stint ending `2021-07-12` alongside identical stints ending
  `2025-07-12`). They are kept as reported and listed in
  `data/output/review/end_before_start.csv`.
- Old-index rows carry whatever rank code the export of the day used, so an
  officer's rank history can mix codes and spelled-out titles.

### Audit files (`data/output/review/`)

| File | Contents |
|---|---|
| `superseded_rows.csv` | Old-index rows replaced by the Nov–Dec 2024 file |
| `test_rows.csv` | Placeholder records dropped |
| `duplicate_rows.csv` | Every row involved in a duplicate group, before resolution |
| `collapsed_stints.csv` | Every row that was merged into a multi-row stint, with `_stint_id` |
| `end_before_start.csv` | Rows kept despite `end_date < start_date` |

## Output

`data/output/ks_index.csv` — 23,608 rows, 16,305 officers, 453 agencies.

Columns: `person_nbr`, `full_name`, `first_name`, `middle_name`,
`last_name`, `suffix`, `agency_name`, `rank`, `employment_status`,
`start_date`, `end_date`, `state`.
