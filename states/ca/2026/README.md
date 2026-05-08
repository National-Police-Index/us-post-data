# California State Police Officers Certification — 2026

## Data Files

Data obtained in 2026 under the Public Records Act from the [CA Commission on
Peace Officer Standards and Training](https://post.ca.gov/), combined with the
2023 corrections officer data from the [California Department of Corrections
and Rehabilitation](https://www.cdcr.ca.gov/).

Inputs (in `data/input/`):

- `ca-2026-post-raw.csv` — raw POST law enforcement officer employment records
- `ca-2023-clean-corrections.csv` — pre-cleaned CDCR corrections officer data
  (carried over from the 2025 release)

## Python Packages Used

- `pandas`: data manipulation

## Data Cleaning and Processing

All cleaning lives in `src/src.ipynb`. Law enforcement (POST) and corrections
(CDCR) data are processed separately, then concatenated into a single index
(`output/ca_index.csv`). The two databases have no shared identifier; an
officer who appears in both will have two distinct `person_nbr`s.

### `leo` data (POST)

Source: `ca-2026-post-raw.csv`. Dropped: `officer_id`, `term_code`, `rank`,
`app_status`. Renamed and processed:

- `person_nbr`: from `POST_ID`
- `last_name`, `first_name`, `middle_name`, `suffix`: parsed from
  `officer_name` (`"LAST, FIRST MIDDLE [SUFFIX]"`); rows with
  `officer_name == "name withheld"` are dropped
- `agency_name`: lowercased and normalized via `clean_agency_name` —
  strips trailing legacy C-codes (e.g. `c-04`), expands abbreviations
  (`pd` → `police department`, `sd` → `sheriff's department`,
  `usd` → `unified school district`, `csu` → `california state university`,
  etc.), applies multi-word phrase rules, handles full-string irregulars
  (e.g. `cal fire`, `cal - oes`), and rewrites comma-separated sub-units as
  ` - ` notation
- `start_date`, `end_date`: from `employment_start_date` /
  `employment_end_date`, coerced to `YYYY-MM-DD`
- `separation_reason`: from `term_code_desc`, lowercased; `unknown` blanked
- `type`: `POLICE`

### `corrections` data (CDCR)

Source: `ca-2023-clean-corrections.csv` (already cleaned in the 2025 release;
see `readmes/CA_README.md` for the original CDCR processing methodology).
Renames `agcy_name` → `agency_name` and `middle_initial` → `middle_name`,
title-cases the name fields, and sets `type = CORRECTIONS`.

### Final index

The two frames are concatenated, name/date/separation fields are normalized
(empty strings instead of `NaT`/`None`/`nan`), rows missing `start_date` are
dropped, and duplicates on
`(person_nbr, agency_name, start_date)` are removed.

Output: `output/ca_index.csv`.
