# TEXAS

## note for future 
- the filename and pathnames should be updated once there is a link to dropbox data and we settle on output filename convention, which I think should be "[state]_cleaned_data_[year].csv"

Cleaning of the Texas POST officer/employment table
(`data/input/post_data_texas.csv`). See `clean_post_texas.py` (a runnable mirror
of the `clean_post_texas.ipynb` EDA notebook). This is the statewide POST table —
the canonical match target for the per-agency rosters described in the top-level
`README.md`.

## Goal

Turn the raw POST export into a clean per-officer employment table — one row per
officer-agency stint — with a stable person id (`uid`), normalized agency names,
and the officer's name split into structured fields. This is the canonical
Texas table we match agency rosters (see `../docs/index_rosters.md`) against:
cleaned names and agencies are what make cross-source matching possible. Output
is written to `data/output/post_data_texas_cleaned.csv`.

## What `clean_post_texas.py` does

Pure `pandas` — no third-party name-parsing dependency.

`read_tbl()`
- Drops `Unnamed: 7` (a fully-null column left over from the source once being
  an `.xlsx`).
- Renames columns to snake_case, including `PUBLIC ID` → `uid` (the stable
  per-person id — one person can hold many rows across agencies/stints).
- Drops rows with a blank `hire_date` (see issue 1 below).

`clean_agency_name()` normalizes `agency_name` (lowercased, trimmed):
- Expands multi-letter acronyms first: `i.s.d.`→independent school district,
  `c.i.s.d.`→consolidated independent school district, `d.p.s.`→department of
  public safety, `p.d.`→police department, `d.a.`→district attorney,
  `s.d.`→school district, `u.s.`→us. Spaced variants (`i. s. d.`) are handled too.
- Expands single-token abbreviations: `co.`→county, `dist.`→district,
  `dept.`→department, `pct.`→precinct, `univ.`→university, `mun./munic.`→municipal,
  `reg.`→regional, `intl.`→international, `crim.`→criminal, `auth.`→authority,
  `inv./invest.`→investigation, `hosp.`→hospital, `st.`→saint, and more (full
  list in the `_ABBREVS` table).
- Fixes source typos (`pct.`→precinct was previously "precient"; `west virgina`;
  `ivest.`).
- Strips trailing dept-id codes (`reno police department (367204) - 367204`),
  `(inactive)` markers, and stray trailing punctuation.

This takes the trailing-period abbreviations across the ~3,750 unique agency
names from several hundred down to ~27, all of which are intentionally left
alone (see below).

`split_full_name()` splits `full_name` (format `First [Middle] Last [Suffix]`)
into `first_name`, `middle_name`, `last_name`, `suffix` with a hand-rolled
tokenizer (`_split_one`). It has no honorific/title dictionary and **never drops
a token** — every input token survives in exactly one output field.

The key structural fact it exploits: in this data a middle, when present, is
**always a single initial**. So the first single-initial token (after position
0) is a clean pivot — everything before it is the (possibly compound) first
name, everything after is the (possibly double / particle) surname. It also:

- keeps surname particles with the last name (`de la garza`, `st. clair`,
  `von muldau`, `des camps`) via an explicit `_PARTICLES` set;
- pulls off generational suffixes (`jr`, `iii`, incl. the comma'd `Matta, III`);
- handles compound first names (`MARY JANE R DELGADO`) and Hispanic double
  surnames (`Julio E Rivera Arce` → last `Rivera Arce`);
- collapses duplicated initials (`Kevin D D Tran` → middle `D`);
- normalizes hyphen-spacing (`Choice -Farkasdi` joins; `Jeannine - Langley`, a
  both-sides-spaced hyphen, splits into first/last).

A **bare single-word middle** (`LARRY DEAN LEE`, `JUAN CARLOS SALAZAR`) is
deliberately kept as the middle name: it's genuinely ambiguous between a real
middle name, a compound first, and a double surname, so we assume middle name.

Result: **0 rows with a missing last name**, and no dropped tokens (a
token-preservation check confirms every input token survives in the output,
except intentionally-collapsed duplicate initials). Split correctness was
spot-checked by sampling people (grouped by `uid`); the remaining untouched
cases are genuinely unresolvable from the string alone (name-order reversals; a
few corrupted source rows with duplicated/reversed names).

## Deliberately not cleaned

- **`state of <other state>`** (e.g. `state of maine`, `state of vermont`) —
  these are officers whose POST record points at an out-of-state agency
  (transfers / reciprocity), not a data error.
- **`... no. N`** — court numbers (`court of appeals district no. 11`). Not
  expanded to "number" because `oak ridge no.` means North.
- **`comm.`** — ambiguous: communications *center* vs commission *on jail
  standards* vs community college (only the "comm. college" case is expanded).
- **Genuine initials/acronyms** kept as-is: `l.c.r.a.` (Lower Colorado River
  Authority), `stephen f. austin`, `t. don hutto`.

## Issues / open questions

1. **Missing dates/departments.** Of the 752,500 raw rows:
   - `DEPARTMENT NAME` missing: **822 (0.11%)**
   - `START DATE` missing: **822 (0.11%)** — the *same* 822 rows
   - `END DATE` missing: **111,479 (14.81%)**

   Department and start date are perfectly coupled: missing-start ⟺ missing-dept,
   always the same 822 rows (which are also missing end date). There is no case
   of a missing start date with a present department, or vice versa. These 822
   rows carry no usable employment info and are dropped via the blank-`hire_date`
   filter in `read_tbl()`. A missing *end* date is a different, benign thing — an
   open/current stint (officer still employed as of the snapshot), not a
   data-production error — so those ~111k rows are kept. Start date is the field
   we most rely on for interval matching, and it is present for every retained
   row.
