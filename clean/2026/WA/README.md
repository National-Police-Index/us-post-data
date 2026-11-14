# Washington WSCJTC Employment History — 2026

## Data Files

Obtained through a public records request (PRR) to the [Washington State
Criminal Justice Training Commission](https://www.cjtc.wa.gov/) (WSCJTC),
fulfilled July 2026. The 2023 release is documented in
`readmes/WA_README.md`.

| File | Used | Contents |
|---|---|---|
| `PRR_7.29.26.xlsx`, sheet `ALL` | yes | 103,098 people, one row each, with up to 12 employment stints and 35 certifications side by side |
| `PRR_7.29.26.xlsx`, sheets `BLEEA`, `COEA`, `Reserves` | no | Training rosters (name, student ID, session) |
| `DOBs_PRR_7.30.26.csv` | no | One column, `Person Date of Birth`, with no person ID (see open questions) |

`ALL` covers everyone in WSCJTC's system, not only peace officers. It also
includes private security, corrections, telecommunicators, civilians,
military, and others (see `certification_type` below).

## Replicating

Run from `clean/2026/WA/`:

```bash
# 1. Download the raw files into data/input/ (see note below).
python src/download.py

# 2. Clean.
python src/clean.py --input-dir data/input --output-dir data/output
```

**`DROPBOX_URL` in `src/download.py` is empty.** It needs a public
("Anyone with the link") Dropbox folder link. Until then, place the files
in `data/input/` by hand.

Writes `data/output/wa_index.csv` plus audit files in
`data/output/review/`. `src/clean.ipynb` is the exploratory notebook.

## Python Packages Used

- `pandas`, `openpyxl`: reading the xlsx and data manipulation

## Data Cleaning and Processing

All cleaning lives in `src/clean.py`. In order:

1. **Reshape to one row per stint** (`melt_stints`). Each stint's columns
   start at an `Employment Start Date` column. The export drops columns
   that are empty for everyone, so later stints have fewer fields (e.g. no
   `Employment Employment Assignment`); those come through empty. Agency
   address and certification columns are not stint fields and are not
   carried over. This gives 92,270 stints for 73,135 people. The other
   29,963 people have no employment record.
2. **Rename** to the schema:
   - `person_nbr` ← `Person Student ID`
   - `sex` ← `Person Gender`
   - `certification_type` ← `Employment Appointment Type`
   - `rank` ← `Employment Title/Rank (Current)`
   - `status` ← `Employment Status`
   - `separation_reason` ← `Employment Change Reason`
   - `agency_name` ← `Employing Organization Name`

   ORI/UBI, is-employer, assignment and the stint number are dropped.
3. **Normalize text**: blanks become `""`, and whitespace is collapsed in
   every column. `person_nbr` is lowercased.
4. **Dates** to `YYYY-MM-DD`. `1901-01-01` (once `1900-01-01`) is
   WSCJTC's placeholder for an unknown date and is blanked. It is almost
   entirely on non-peace-officer appointments (private security, civilian,
   military); only 0.15% of Certified Peace Officer stints have it.
5. **Suffix**: only generational suffixes are kept (`Jr`, `Sr`, `II`,
   `III`, `IV`…). Credentials typed into the field (`M.D.`, `Ph.D.`,
   `D.O.`, `J.D.`) are cleared. Three suffixes typed into `last_name` are
   moved over. `full_name` is `last, first middle suffix`, lowercased.
6. **`rank`**: `Unknown` is a placeholder and is cleared.
7. **Agency names** (`clean_agency_names`). The source names are mostly
   clean: there are no agency codes, no truncation, and they are mixed
   case. The rules handle the rest:
   - **Redirects and variants:** `Allied Protection Services, Inc. (Use
     Allied Universal Security Services)` → Allied Universal Security
     Services; `A1 Security Services` → `A-1 Security Services`.
   - **Acronyms:** `WSCJTC` → Washington State Criminal Justice Training
     Commission (and `PS` → Private Security after it); `WSP` /
     `(WSP)` → Washington State Patrol (`WSP IIT` → Independent
     Investigation Team); `JRA` → Juvenile Rehabilitation
     Administration; `UW` → University of Washington; `HIDTA` → High
     Intensity Drug Trafficking Area; `NW` → Northwest; `WA` →
     Washington.
   - **Noise:** a trailing `(s)` is removed, and lopsided dashes are
     respaced (`Region 1 & 2- Yakima` → `Region 1 & 2 - Yakima`).
     Hyphenated names (`Sedro-Woolley`) are left alone.
   - **Left as-is on purpose:** parentheses that carry meaning (`(Self)`
     for self-employed licensees, `(ID)`/`(AK)` for out-of-state,
     `(Spokane)`), `DBA` names, and `USA`/`U.S.` in company names.
   - **Non-agency values** (`Other`) are dropped to
     `review/non_agency.csv` (1 row).
8. **Drop rows with no start date** (`review/no_start_date.csv`).
   `db/preprocess` drops every row with an empty `start_date`, so they are
   dropped here explicitly and the counts are recorded:
   - **18,537 rows** (20% of stints), nearly all the `1901` placeholder;
   - **18,109 unique people** have at least one row dropped;
   - **16,159 people drop out of the index entirely**, having no other
     stint with a start date. Most are private security (7,418), no
     appointment type recorded (3,182), civilian (1,387) and military
     (968). Only **31 are Certified Peace Officers**.
9. **Duplicates**: 438 rows share a person, agency and start date
   (`review/duplicate_rows.csv`). This happens, for example, when one
   person holds several private-security licenses at the same company.
   One row is kept: a closed row beats an open one, and otherwise the
   latest end wins.
10. **Collapse stints**: overlapping or back-to-back rows at the same agency
    are merged (1,600 rows → `review/collapsed_stints.csv`; 73,511 →
    72,686 rows). This uses the running-maximum rule from TX/FL. Open end
    dates are kept open, and the most recent row supplies the other fields.

`status` and `separation_reason` are kept as WSCJTC reports them.
`separation_reason` is WSCJTC's *change reason*: on ended stints it is a
separation (`Resignation`, `Retired`, `Terminated`), and on open ones it is
the latest change (`Hire`, `Certified`, `Promotion`).

### `certification_type`

WSCJTC's `Employment Appointment Type`: what the person was appointed as
at that agency. Counts are stints in the output.

| Value | Stints | Notes |
|---|---|---|
| Certified Peace Officer | 27,734 | Sworn, certified law enforcement |
| Certified Corrections Officer | 4,264 | |
| Certified Tribal Police Officer | 341 | |
| Certification Pending - Recruit / Lateral | 2,112 | Hired, not yet certified |
| Non-Certified Reserve Peace Officer, Reserve Officer – Recruit | 2,158 | |
| Non-Certified Corrections Officer (WA DOC) | 1,548 | |
| Corrections / Juvenile Corrections Personnel | 4,826 | |
| Private Security Personnel | 9,366 | Licensed security guards |
| Private Investigation, Bail Bonds Recovery | 818 | |
| Telecommunicator (E911) | 2,779 | Dispatchers |
| Civilian, Non-Certified Position, Contractor | 8,103 | |
| Military Police / Personnel, Federal, Fire, Medicolegal, … | ~1,300 | |
| *(empty)* | 6,213 | Not recorded, mostly older stints |

## Output

`data/output/wa_index.csv`: **72,686 rows, 56,975 people, 1,660
agencies.** 32,660 stints are open.

Columns: `person_nbr`, `full_name`, `first_name`, `middle_name`,
`last_name`, `suffix`, `sex`, `agency_name`, `certification_type`, `rank`,
`status`, `start_date`, `end_date`, `separation_reason`, `state`.

## Issues / open questions

1. **Who to include.** Only about 40% of stints are Certified Peace or
   Corrections Officers. Should private security, civilians, dispatchers
   etc. be dropped? This is still to be asked of the team. Everyone is kept
   for now, and `certification_type` makes the filter one line.
2. **`DOBs_PRR_7.30.26.csv` can't be joined.** It has no person ID, and
   its 103,156 rows don't match the 103,098 people in `ALL`, so the rows
   can't be lined up by position either. A version with `Student ID` is
   needed to add `year_of_birth`.
3. **Future-dated stints.** 42 stints start or end after the 7/29/26
   export: academy start dates for recruits (mostly WSP) and scheduled
   retirements. They are kept as reported.
