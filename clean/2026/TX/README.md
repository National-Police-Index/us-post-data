# Texas TCOLE Employment History — 2026

## Data Files

The statewide Texas POST (TCOLE) officer/employment table, received as a
single CSV. The Dropbox link in `src/download.py` is not filled in yet; for
now place the file in `data/input/` by hand.

| File | Rows | Contents |
|---|---|---|
| `post_data_texas.csv` | 752,500 | One row per officer × agency × appointment type |

Columns: `PUBLIC ID`, `FULL NAME`, `DOB`, `DEPARTMENT NAME`, `SERVICE`,
`START DATE`, `END DATE`, plus an empty `Unnamed: 7` (left over from the
source once being an `.xlsx`). Missing values are the literal string `NULL`.
All dates are `M/D/YY` with **two-digit years** (one DOB is
`1774-06-16 00:00:00.000`). The latest date in the file is 2025-12-31.

`PUBLIC ID` is a stable 7-digit per-person ID: every ID maps to exactly one
name and one DOB.

## Replicating

Run from `clean/2026/TX/`:

```bash
# Writes data/output/tx_index.csv plus audit files in data/output/review/.
python src/clean.py --input-dir data/input --output-dir data/output
```

Takes ~45 s. `src/eda.ipynb` is the exploratory notebook the cleaning logic
came from.

## Python Packages Used

- `pandas`: everything. Name splitting is hand-rolled (no `nameparser`).

## Data Cleaning and Processing

All cleaning lives in `src/clean.py`. In order:

1. **Load and rename**:
   - `person_nbr` ← `PUBLIC ID`
   - `full_name` ← `FULL NAME` (format `First [Middle] Last [Suffix]`)
   - `agency_name` ← `DEPARTMENT NAME`
   - `rank` ← `SERVICE` (appointment type: Peace Officer, Jailer, Reserve
     Officer, Telecommunications Operator, …)
   - `start_date` / `end_date` ← `START DATE` / `END DATE`
   - `NULL` → empty string; `state` = `tx`
2. **Parse dates with an explicit century.** pandas would read `4/8/68` as
   2068. Since the export ends in 2025 and contains no year `26`, two-digit
   years `00–25` are 20xx and `26–99` are 19xx. Output is `YYYY-MM-DD`; an
   empty `end_date` means currently employed.
3. **Drop rows with no start date** (822 → `review/no_start_date.csv`). The
   same 822 rows are also missing agency, service and end date. They carry
   no employment information.
4. **Drop rows whose end date is before their start date** (921 →
   `review/end_before_start.csv`). Most are off by days or weeks (e.g.
   start 6/15/13, end 6/14/13) and look like data-entry errors. See open
   question 2.
5. **`year_of_birth`** from `DOB`. A two-digit birth year is ambiguous, so
   it is resolved per officer: 20xx unless that would make them younger
   than 14 at their first appointment, otherwise 19xx. The `1774` DOB is
   left empty.
6. **Agency names**, lowercased and trimmed:
   - Expand multi-letter acronyms first: `i.s.d.`→independent school
     district, `c.i.s.d.`→consolidated independent school district,
     `d.p.s.`→department of public safety, `p.d.`→police department,
     `d.a.`→district attorney, `s.d.`→school district, `u.s.`→us. Spaced
     variants (`i. s. d.`) are handled too.
   - Expand single-token abbreviations: `co.`→county, `dist.`→district,
     `dept.`→department, `pct.`→precinct, `const.`→constable,
     `univ.`→university, `mun./munic.`→municipal, `atty.`→attorney,
     `st.`→saint, and more (full list in `_ABBREVS`).
   - Fix source typos (`west virgina`, `ivest.`).
   - Strip trailing dept-id codes (`reno police department (367204) -
     367204`), `(inactive)` markers and trailing punctuation.

   This brings the trailing-period abbreviations across ~3,750 agencies
   from several hundred down to ~27, all left alone on purpose (see below).
7. **Split `full_name`** into `first_name`, `middle_name`, `last_name`,
   `suffix` with a hand-rolled tokenizer (`_split_one`). It never drops a
   token: every input token ends up in exactly one output field.

   In this data a middle name, when present, is **always a single initial**.
   So the first single-initial token after position 0 is a clean pivot:
   everything before it is the first name (possibly compound), everything
   after it is the surname (possibly double or with a particle). It also:
   - keeps surname particles with the last name (`de la garza`,
     `st. clair`, `von muldau`) via `_PARTICLES`;
   - pulls off generational suffixes (`jr`, `iii`, including the
     comma'd `Matta, III`);
   - handles compound first names (`MARY JANE R DELGADO`) and Hispanic
     double surnames (`Julio E Rivera Arce` → last `Rivera Arce`);
   - collapses duplicated initials (`Kevin D D Tran` → middle `D`);
   - normalizes hyphen spacing (`Choice -Farkasdi` joins;
     `Jeannine - Langley`, spaced on both sides, splits).

   A **bare single-word middle** (`LARRY DEAN LEE`) is kept as the middle
   name. It is genuinely ambiguous between a middle name, a compound first
   name and a double surname. Result: 0 rows with an empty first or last
   name.
8. **Collapse stints** (750,757 → 593,099 rows; members of multi-row
   stints → `review/collapsed_stints.csv`). See below.

### Why stints are collapsed

TCOLE keeps one row per **appointment type**, not per job. An officer who
is both a jailer and a peace officer at one sheriff's office has two rows
side by side:

```
1000018  HARRIS CO. SHERIFF'S OFFICE  Jailer         3/3/03  5/23/08
1000018  HARRIS CO. SHERIFF'S OFFICE  Peace Officer  3/3/03  5/23/08
```

Appointments also nest (an open Jailer row spanning several Peace Officer
rows) and run back to back. Before collapsing, ~147k rows start within a
day of, or inside, an earlier row at the same agency.

`collapse_stints` groups by `(person_nbr, agency_name)`, sorts by start,
and starts a new stint when a row begins more than one day after the
**running maximum** end date so far. A long open appointment therefore
absorbs everything inside it. The merged row takes the earliest start, the
latest end (open if any member is open), and other fields from its
latest-starting row. `rank` therefore reflects only that last appointment;
it isn't shown on the front end.

Two differences from the other implementations:

- **No stale-open rule.** KS/IL treat an open end date followed by a later
  row at the same agency as never closed. In Texas the later row is usually
  a concurrent appointment or a zero-length artifact row (start = end). For
  example, a Baytown officer open since 1997 has a one-day telecom row in
  2003. Closing the open row there would wrongly end ~1,000 current stints.
- **Running max instead of previous row.** `db/preprocess`'s
  `collapse_contiguous_stints` compares each row only with the one before
  it. That splits stints nested inside a long appointment.

Texas is not in `COLLAPSE_STINTS` in `db/preprocess`. It wouldn't matter if
it were: after this pass no two stints at one agency are within a day of
each other.

## Output

`data/output/tx_index.csv`: **593,099 rows, 320,198 officers, 3,752
agencies.** 101,218 stints are open (currently employed).

Columns: `person_nbr`, `full_name`, `first_name`, `middle_name`,
`last_name`, `suffix`, `agency_name`, `rank`, `start_date`, `end_date`,
`year_of_birth`, `state`.

Review files in `data/output/review/`:

| File | Rows | Meaning |
|---|---|---|
| `no_start_date.csv` | 822 | Dropped: no agency, service or dates |
| `end_before_start.csv` | 921 | Dropped: end date before start date |
| `collapsed_stints.csv` | 282,593 | Kept, merged: every member of a multi-row stint |

## Deliberately not cleaned

- **`state of <other state>`** (e.g. `state of maine`): out-of-state
  agencies on a TCOLE record (transfers or reciprocity), not errors.
- **`... no. N`**: court numbers. Not expanded to "number" because in
  `oak ridge no.` it means North.
- **`comm.`**: ambiguous between communications *center*, commission *on
  jail standards* and community college. Only `comm. college` is expanded.
- **Genuine initials** kept as-is: `l.c.r.a.` (Lower Colorado River
  Authority), `stephen f. austin`, `t. don hutto`.
- **`Redacted - Peace Officer` / `Redacted - Jailer`** in `SERVICE`
  (25 rows): kept verbatim in `rank`. Names and agencies on these rows are
  present.

## Issues / open questions

1. **Export cut-off.** Only 248 rows start in 2025, all but one in January
   (latest start after cleaning: 2025-01-16). The file looks like it was
   pulled in mid-January 2025, despite the 2026 directory.
2. **End-before-start drops.** 190 of the 921 dropped rows are an officer's
   only record at that agency, and 86 officers vanish from the index
   entirely. Most look like swapped or mistyped dates. A fix (e.g. swapping
   the dates when the gap is small) could recover them.
3. **Birth-year edge cases.** After century resolution, 137 stints start
   before age 16 and 305 after age 75. These are likely DOB typos in the
   source and are left as-is.
4. **Missing departments.** The 822 no-start rows above were flagged to the
   data team as a production issue; another request is out.
