# Minnesota POST Employment History — 2026

## Data Files

Data obtained via a MuckRock request to the Minnesota Board of Peace
Officer Standards and Training (MN POST), filed 2026-08-04.

The raw file lives in a Dropbox shared folder (link in `src/download.py`)
and, once downloaded, in `input/`:

| File | Used | Contents |
|---|---|---|
| `Officer-with-Agency-Data-Public-Only-2026-08-04_Muckrock_request.xlsx` | yes | 51,139 stints, 26,911 officers, 1973→2026 |

The sheet (`Officer-with-Agency-Data-Public`) has a header on row 1 and
then one block per officer: the license number sits only on the block's
first row, and a `Subtotal / Count / N` row closes each block. A final
`Total / Count` row closes the sheet. A `Status` column says `Active` or
`Terminated`; a blank `Date Terminated` means the officer is still
employed. There is **no rank field** in this export, and stints are not
split on rank/status changes the way KS-CPOST splits them.

## Replicating

Run everything from `clean/2026/MN/`.

```bash
# 1. Download the shared folder as a zip and extract it into input/.
python src/download.py --keep-zip

# 2. Clean. Writes output/mn_index.csv plus audit files in
#    output/review/.
python src/clean.py --input-dir input --output-dir output

# 3. Hand off to the db pipeline (it reads states/<state>/<year>/output/).
mkdir -p ../../../states/mn/2026/output
cp output/mn_index.csv ../../../states/mn/2026/output/
cd ../../../db && make dry-run STATE=mn YEAR=2026
```

`openpyxl` is required to read the `.xlsx` (it is in `pyproject.toml`).

## Python Packages Used

- `pandas`, `openpyxl`: reading xlsx, data manipulation

## Data Cleaning and Processing

All cleaning lives in `src/clean.py`. In order:

1. **Load** the workbook and normalise columns:
   - `person_nbr`: from `License Number`, forward-filled down each
     officer's block (the number appears only on the block's first row).
     All values are 1–5 digit strings, lowercased; they are not
     zero-padded because the source uses no fixed width.
   - `first_name`, `last_name`: from `First Name` / `Last Name`,
     whitespace-stripped.
   - `agency_name`: from `Law Enforcement Agency` (see below).
   - `employment_status`: from `Status` — `Active` / `Terminated`,
     kept verbatim.
   - `start_date`, `end_date`: from `Start Date` / `Date Terminated`,
     coerced to `YYYY-MM-DD`. Blank `Date Terminated` (11,232 rows)
     becomes an empty string (currently employed). There is no
     `1/1/0001` sentinel in this file.
   - `suffix`: MN puts suffixes in the last-name column (`Ryan Ii`,
     `Walls Jr.`, `Hankee, Jr.`); a trailing ` Jr/Sr/II/III/IV/…`
     (separated by space, comma or hyphen) is split off (241 rows; 232
     survive, the rest were dropped/deduped).
   - `state`: `mn`
2. **Drop summary and junk rows**: the `Subtotal`/`Total` counter rows,
   a stray header echo, and rows with no name/agency (one orphan cell
   `1/17/2014` under the header).
3. **Drop rows with no start date** (36 rows). These are `Terminated`
   rows with no dates at all — the preprocess pipeline drops empty
   `start_date` anyway, so they are removed here explicitly.
4. **Drop test records** (0 rows): none are present in this export; the
   filter (`^test…` agency/name) is kept for parity with KS and for
   future updates.
5. **Resolve duplicates** on `(person_nbr, agency_name, start_date)`
   (1,935 rows dropped from 1,678 groups). The export lists the same
   stint twice with different end dates (overlapping employment records
   in the source). The row with the latest end date wins (closed beats
   open).
6. **Do NOT collapse contiguous stints.** Unlike KS, MN has no rank
   field and does not split a continuous period into adjacent rows; its
   rows are already one stint per officer-agency period. Collapsing
   would wrongly merge genuinely separate back-to-back stints such as
   the seasonal State Fair Police Dept. details (many officers work the
   fair each year). `mn` is therefore **not** added to
   `COLLAPSE_STINTS` in preprocess.
7. **Write** `data/output/mn_index.csv`, sorted by `person_nbr`,
   `start_date`.

### Agency names

Two abbreviations are expanded with word-bounded, case-insensitive
patterns — `Dept.` → `Department` and `Co.` → `County` — plus `DPS` →
`Department Of Public Safety` (`DPS, Bureau Of Criminal Apprehension` →
`Department Of Public Safety, Bureau Of Criminal Apprehension`). White
space is collapsed. All other names are already spelled out
(`Metropolitan Transit Police Department`, `Minnesota State Patrol`,
`University of Minnesota-Twin Cities Police Dept.`, etc.). Casing is
left to `db/preprocess`.

### Known issues

- 24 rows have `end_date` earlier than `start_date` — source typos
  (e.g. a 2025 State Fair stint ending `2024-12-02`). They are kept as
  reported and listed in `data/output/review/suspicious_dates.csv`.
- 2 rows have `start_date = 1900-01-01` — source placeholders; kept as
  reported and listed in the same file.
- The source is inconsistent about the apostrophe in county sheriff's
  offices (`Anoka Co. Sheriff's Office` vs `Big Stone Co. Sheriffs
  Office`). Both spellings are kept as reported, so a handful of the
  same offices appear under two names.
- 1 row (license `16723`, Carlson) has no agency name at all — kept as
  reported (the preprocess pipeline only warns on this).

### Audit files (`data/output/review/`)

| File | Contents |
|---|---|
| `duplicate_rows.csv` | Every row involved in a duplicate group, before resolution |
| `suspicious_dates.csv` | Rows kept despite `end_date < start_date` or `start_date <= 1900-01-01` |
| `test_rows.csv` | Placeholder records dropped (none in this export) |

## Output

`data/output/mn_index.csv` — 49,168 rows, 26,875 officers, 547 agencies
(including one agency-less row).

Columns: `person_nbr`, `full_name`, `first_name`, `last_name`, `suffix`,
`agency_name`, `employment_status`, `start_date`, `end_date`, `state`.
