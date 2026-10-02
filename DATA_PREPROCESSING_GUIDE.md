# DATA_PREPROCESSING.md

Step by step guide for cleaning POST data for any state. This is a general guide, built by reviewing the all stats that were previouslyc leaned, that shouldn't be taken as an exact formula for cleaning because every state has it's own quirks.  

It is in three parts:

| Part | Applies to | Contents |
|---|---|---|
| [Part 1 — Cleaning](#part-1--cleaning) | **everyone** (humans and agents) | Step-by-step: download the raw data, write `clean.py`, produce `<state>_index.csv` |
| [Part 2 — Uploading](#part-2--uploading) | **everyone** | Preprocess, dry run, Firebase upload, front-end scripts |
| [Part 3 — The automated agent pipeline](#part-3--the-automated-agent-pipeline) | **the CC agent only** | `validate.py`, the LLM-as-judge, ground truth, the `states/` layout |

**If you are cleaning a state by hand, you only need Parts 1 and 2.**
Part 3 describes machinery that exists for the automated pipeline; the LLM
judge and ground-truth comparison are not required for manual work.

### Where the work lives

Manual cleaning lives in `clean/<year>/<STATE>/` (uppercase state code), one
self-contained directory per release:

```
clean/<year>/<STATE>/
├── README.md              ← document the source and every cleaning decision
├── src/
│   ├── download.py        ← fetch the raw data from Dropbox
│   └── clean.py           ← produce the index
└── data/
    ├── input/             ← raw source files (read-only)
    └── output/
        ├── <state>_index.csv
        └── review/        ← rows dropped or flagged, for audit
```

The automated pipeline uses a different layout, `states/<state>/<year>/`
(lowercase) — see Part 3. This is a bug that needs to be fixed. 

---

# Part 1 — Cleaning

## Output schema

Every state must produce at least one CSV: `<state>_index.csv`. States with disciplinary records should also produce `<state>-discipline_index.csv`.

### Employment Index (`<state>_index.csv`)

**Required columns** (pipeline will fail without these):

| Column | Format | Notes |
|--------|--------|-------|
| `person_nbr` | string | Unique officer ID from the state POST system |
| `first_name` | string | |
| `last_name` | string | |
| `agency_name` | string | See agency cleaning section below |
| `start_date` | YYYY-MM-DD | Employment start |
| `end_date` | YYYY-MM-DD or empty | Empty = currently employed |

**Optional columns** (include when available):

| Column | Notes |
|--------|-------|
| `full_name` | Concatenated name |
| `middle_name` | |
| `suffix` | Jr, Sr, II, III, etc. |
| `rank` | Officer's title/rank at this agency |
| `employment_status` | e.g. "Actively Employed", "Voluntary Resignation" |
| `separation_reason` | Why employment ended |
| `race` | As reported in source data |
| `sex` | As reported in source data |
| `year_of_birth` | 4-digit year string |
| `state` | Lowercase 2-letter abbreviation (e.g. `ga`) |

### Discipline Index (`<state>-discipline_index.csv`)

States that track disciplinary actions separately (currently: **GA**, **FL**) should also produce this file.

**Required columns:**

| Column | Notes |
|--------|-------|
| `person_nbr` | Must match person_nbr in employment index |
| `first_name` | |
| `last_name` | |
| `agency_name` | Agency where the incident occurred |
| `start_date` | Employment start at the agency |
| `end_date` | Employment end at the agency |

**Additional discipline columns** (include when available):

| Column | Notes |
|--------|-------|
| `case_id` | Disciplinary case identifier |
| `violation` | Nature of the violation |
| `violation_date` | YYYY-MM-DD |
| `sanction` | Penalty imposed |
| `sanction_date` | YYYY-MM-DD |
| `full_name` | |
| `rank` | |
| `middle_name` | |
| `suffix` | |
| `year_of_birth` | |
| `race` | |
| `sex` | |

---

---

## Step-by-step cleaning process

### Step 0: Write `download.py`

**Every new state gets a `src/download.py`** so the raw data can be fetched
again by anyone, and so the provenance of `data/input/` is recorded in code
rather than in someone's browser history. Dropbox is the canonical source —
upload the raw files there first if they are not already.

Copy `clean/2026/KS/src/download.py` as the starting point. It:

1. Takes a Dropbox shared link as a module-level constant.
2. Rewrites the link's `dl=0` to `dl=1`, which makes Dropbox serve a shared
   *folder* as a single zip.
3. Streams the download to `data/input/` and extracts it in place.
4. Checks the `Content-Type` and raises if the response is not a zip —
   an expired or private link otherwise saves an HTML error page.

```bash
python src/download.py              # download + extract
python src/download.py --keep-zip   # leave the archive in data/input/
```

For a link to a single file rather than a folder, skip the zip handling and
stream the response straight to disk under its real filename.

Always confirm the files you extracted are the ones you expect before
cleaning: check the sheet names, row counts and column headers. A shared
link can silently point at the wrong state's folder.

---

### Step 1: Inventory the raw files


Before writing any code, list all files in `data/input/` and identify:

- **Core employment file**: Usually named something like `officer_employment.csv`, `employment_history.xlsx`, or similar. This is the primary table — one row per officer-agency-period.
- **Officer demographics file**: Named `officer_data.csv`, `personnel.csv`, or similar. Contains name, DOB, race, sex keyed by officer ID.
- **Agency reference file**: Named `agency_data.csv` or similar. Maps agency codes to full names.
- **Disciplinary files**: `officer_violations.csv`, `officer_sanctions.csv`, `officer_investigations.csv`, or similar.
- **Certification files**: Often not needed for the index — skip unless the state has no employment file.

Common file patterns by state type:
- **Single file**: State provides one flat CSV with all data already joined.
- **Wide format**: One row per officer, multiple employer columns (e.g. Indiana). Must be melted to long format.
- **Separate tables**: Multiple files joined on officer ID (e.g. Georgia).

### Step 2: Identify the officer identifier

Every state uses a different field name for the unique officer ID. Common names:
- `OKEY`, `OfficerID`, `PSID`, `post_id`, `cert_id`, `person_id`, `badge_number`

This becomes `person_nbr`. It should be treated as a **string** (not numeric) — pad with leading zeros if the state uses a fixed-length format.

Prefix with a lowercase state letter if the source data has raw numeric IDs (e.g. Georgia uses `O143810` → keep as `o143810` after lowercasing).

### Step 3: Join tables

If the data comes in multiple files, join on the officer identifier. Standard merges:

```python
# Merge employment + demographics
merged = employment_df.merge(
    officer_df[['person_nbr', 'last_name', 'first_name', 'middle_name',
                'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)
```

If the state provides an agency reference table, join to resolve agency codes to full names:
```python
# Strip agency code prefix before joining (e.g. "G1720 DEKALB COUNTY PD" → "DEKALB COUNTY PD")
employment_df['agency_name'] = employment_df['AGENCY'].str.replace(
    r'^[A-Z]\d+\s+', '', regex=True
)
```

### Step 4: Rename columns to schema names

Map raw column names to the standard schema:

```python
df.rename(columns={
    'OKEY': 'person_nbr',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    # etc.
}, inplace=True)
```

### Step 5: Clean person_nbr

```python
# Lowercase, strip whitespace
df['person_nbr'] = df['person_nbr'].astype(str).str.lower().str.strip()
```

### Step 6: Parse and clean names

If the state provides separate `first_name`/`last_name` columns, just clean them:
```python
df['first_name'] = df['first_name'].astype(str).str.strip()
df['last_name'] = df['last_name'].astype(str).str.strip()
```

If the state provides a combined `full_name` (e.g. `"SMITH JOHN A"` or `"SMITH, JOHN A"`):
```python
from nameparser import HumanName

def parse_name(name_str):
    name = HumanName(str(name_str).strip())
    return pd.Series({
        'first_name': name.first,
        'middle_name': name.middle,
        'last_name': name.last,
        'suffix': name.suffix,
    })

df[['first_name', 'middle_name', 'last_name', 'suffix']] = \
    df['full_name'].apply(parse_name)
```

Build `full_name` if it doesn't exist:
```python
df['full_name'] = (
    df['last_name'].str.strip() + ', ' + df['first_name'].str.strip()
).str.lower()
```

**Note:** The preprocess pipeline will handle proper-casing. Output names in whatever case the source provides — do not spend time normalizing case in the cleaning script.

### Step 7: Clean dates

Invalid dates in source data are common. Handle them explicitly:

```python
def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None', '0000-00-00', '00/00/0000'):
        return ''
    try:
        return pd.to_datetime(s, errors='coerce').strftime('%Y-%m-%d')
    except Exception:
        return ''

df['start_date'] = df['start_date'].apply(safe_date)
df['end_date'] = df['end_date'].apply(safe_date)
```

**Records with an empty `start_date` will be dropped by the preprocess pipeline.** If there are many such records, investigate whether the source data stores dates in a non-standard field.

### Step 8: Clean agency names

This is the most state-specific step. Agency names in raw data often contain:
- **Agency code prefixes**: `"G1720 DEKALB COUNTY POLICE DEPARTMENT"` → strip the leading code
- **Abbreviations**: `"DEPT"`, `"SO"`, `"PD"`, `"CO"` — expand them
- **Trailing noise**: `"/INACTIVE"`, `"(CLOSED)"` — strip these
- **All-caps**: Leave as-is; the preprocess pipeline handles proper-casing

Common abbreviation expansions (apply in this order to avoid partial matches):

```python
AGENCY_ABBREVIATIONS = [
    (r'\bDEPT\.?\b', 'DEPARTMENT'),
    (r'\bSO\b', "SHERIFF'S OFFICE"),
    (r'\bPD\b', 'POLICE DEPARTMENT'),
    (r'\bCO\.?\b', 'COUNTY'),
    (r'\bCORR\.?\b', 'CORRECTIONS'),
    (r'\bDA\b', "DISTRICT ATTORNEY'S OFFICE"),
    (r'\bDPS\b', 'DEPARTMENT OF PUBLIC SAFETY'),
    (r'\bSVCS?\b', 'SERVICES'),
    (r'\bDIV\.?\b', 'DIVISION'),
    (r'\bDIST\.?\b', 'DISTRICT'),
    (r'\bADMIN\.?\b', 'ADMINISTRATION'),
    (r'\bINVEST\.?\b', 'INVESTIGATIONS'),
]

def clean_agency_name(name):
    if pd.isna(name):
        return name
    s = str(name).strip().upper()
    # Strip leading agency codes (e.g. "G1720 " or "A001 ")
    s = re.sub(r'^[A-Z]\d{3,}\s+', '', s)
    # Strip trailing status markers — word-based patterns first
    s = re.sub(r'\s*/\s*(INACTIVE|ACTIVE|CLOSED|RETIRED).*$', '', s)
    s = re.sub(r'\s*\((INACTIVE|CLOSED)\).*$', '', s)
    # Strip any remaining slash-delimited fragment (e.g. "/18 MOS.", "/PURGED")
    s = re.sub(r'\s*/.*$', '', s)
    # Expand abbreviations
    for pattern, replacement in AGENCY_ABBREVIATIONS:
        s = re.sub(pattern, replacement, s)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', s).strip()

df['agency_name'] = df['agency_name'].apply(clean_agency_name)

# Filter out non-agency strings that appear in the agency column
NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}
df = df[~df['agency_name'].str.lower().isin(NON_AGENCY_VALUES)]
```

### Step 9: Clean ranks

Rank fields typically need:
- Stripping leading/trailing whitespace
- Expanding abbreviations (expand — do not invent titles not in the data)

Common rank abbreviations:
```python
RANK_ABBREVIATIONS = {
    r'\bLT\.?\b': 'LIEUTENANT',
    r'\bSGT\.?\b': 'SERGEANT',
    r'\bCPL\.?\b': 'CORPORAL',
    r'\bCAPT\.?\b': 'CAPTAIN',
    r'\bDET\.?\b': 'DETECTIVE',
    r'\bDEP\.?\b': 'DEPUTY',
    r'\bASST\.?\b': 'ASSISTANT',
    r'\bADMIN\.?\b': 'ADMINISTRATOR',
    r'\bSPEC\.?\b': 'SPECIALIST',
    r'\bSR\.?\b': 'SENIOR',
    r'\bOFC\.?\b': 'OFFICER',
    r'\bDIR\.?\b': 'DIRECTOR',
}
```

### Step 10: Handle wide-to-long reshaping

Some states (e.g. Indiana) provide one row per officer with multiple employment periods as separate column groups (`start_date_1`, `employer_1`, `end_date_1`, `start_date_2`, ...). These must be melted:

```python
# Identify column groups
start_cols = [c for c in df.columns if c.startswith('start_date')]
end_cols   = [c for c in df.columns if c.startswith('end_date')]
agency_cols = [c for c in df.columns if c.startswith('employer')]

# Assign a stint number to each group
start_df = df.melt(id_vars=['person_nbr', ...], value_vars=start_cols,
                   var_name='stint_num', value_name='start_date')
start_df['stint_num'] = start_df['stint_num'].str.extract(r'(\d+)')
# Repeat for end_date, agency, etc., then merge on person_nbr + stint_num
```

### Step 11: Handle discipline data

For states with separate disciplinary records (GA, FL):

1. Join violations and sanctions on `CASE` (case identifier)
2. Join the combined discipline table to employment using `person_nbr`
3. The discipline index should have **one row per sanction** (not per case), with the corresponding employment period for context

```python
# Use violations as the LEFT base; LEFT JOIN sanctions.
# Do NOT use outer join — it creates a cartesian product within cases
# when a case has multiple violations and multiple sanctions.
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner',   # Keep only violations that have a sanction
)

# One row per violation: keep the most recent sanction
discipline = (
    discipline.sort_values('sanction_date', ascending=False)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
)

# Attach employment context (score each possible period, keep best match)
discipline = discipline.merge(
    employment[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']],
    on='person_nbr',
    how='left'
)
# ... score and dedup employment periods ...
discipline = discipline.drop_duplicates(
    subset=['case_id', 'person_nbr', 'violation']
)

# Drop rows with no employment match (empty start_date) — preprocess drops
# them anyway, and it is better to be explicit here.
discipline = discipline[discipline['start_date'].fillna('') != '']
```

For cases where a person has multiple employment periods, score each period by how well the violation_date falls within it (exact match = 0, outside = 1+) and keep the best-scoring row.

### Step 12: Collapse contiguous stints (when the state splits them)

Many states close an employment row and open a new one whenever an
officer's rank or employment status changes, so one continuous period of
employment is spread across several adjacent rows. **If the source behaves
that way, collapse those rows into a single stint in `clean.py`.**

Check before deciding:

```python
w = df.sort_values(["person_nbr", "agency_name", "start_date"])
prev_end = w.groupby(["person_nbr", "agency_name"])["end_date"].transform(
    lambda s: s.cummax().shift(1)
)
print("rows contiguous with the previous stint:",
      ((pd.to_datetime(w.start_date) - pd.to_datetime(prev_end))
       <= pd.Timedelta(days=1)).sum())
```

If the count is material, and the adjacent rows differ only in `rank`,
`employment_status` or similar, collapse. If the state reports genuine
re-hires as separate rows with real gaps between them, do not — merging
them would silently join distinct periods of employment.

Model the implementation on `collapse_contiguous_stints` in
`db/preprocess/src/src.py`. Group by `(person_nbr, agency_name)`, sort by
start date, and start a new stint when the next start is more than a day
after the latest end seen so far. The merged row takes the earliest start,
the latest end, and every other field from the most recent member.

Two refinements worth copying from `clean/2026/IL/src/clean.py`:

- **An open end date mid-sequence is stale.** If a row has an empty
  `end_date` but is followed by another row at the same agency, the state
  never closed it; treat it as ending when the next row starts. Only a
  genuinely final open row should keep the stint open.
- **Fall back for empty fields.** Taking the most recent row wholesale can
  pick up an empty `separation_reason`; fall back to the latest non-empty
  value in the group.

**Collapsing flattens rank history** — a promotion recorded as two adjacent
rows becomes one stint carrying the later rank. That is the intended
trade-off, but say so in the state's README.

Collapsing can also happen downstream instead, for states listed in
`COLLAPSE_STINTS` at the top of `db/preprocess/src/src.py`. **Do not do
both.** If `clean.py` collapses, leave the state out of that set. Discipline
indexes are never collapsed — they are one row per violation.

---

### Step 13: Validate output

Before writing to disk, check:

```python
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in required if c not in df.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

empty_required = {c: (df[c].isna() | (df[c] == '')).sum() for c in required}
for col, count in empty_required.items():
    if count > 0:
        print(f"Warning: {col} has {count} empty values ({count/len(df):.1%})")

# No empty start_date rows (pipeline drops them)
assert (df['start_date'] != '').all(), "start_date must not be empty"
```

### Step 14: Write output

```python
import argparse, os

parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

output_dir = args.output_dir
os.makedirs(output_dir, exist_ok=True)

df.to_csv(os.path.join(output_dir, '<state>_index.csv'), index=False)

# If discipline data exists:
discipline_df.to_csv(
    os.path.join(output_dir, '<state>-discipline_index.csv'), index=False
)
```

---

---

## Common pitfalls

### Date `0000-00-00`
Georgia and some other states use `0000-00-00` to represent a missing or open-ended date. Treat this as empty (currently employed for `end_date`, invalid for `start_date`).

### Agency codes in the name column
States like Georgia prefix agency names with an alphanumeric code (`G1720 DEKALB...`). Always strip these before outputting — the code is not part of the name.

### Duplicate employment records
After joining tables, check for duplicate rows. Common cause: a person appears in both an "active" and "inactive" roster that got concatenated without deduplication.

```python
dupe_check = df.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
if dupe_check.any():
    print(f"Warning: {dupe_check.sum()} duplicate rows found")
    df = df.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
```

### Wide-format multi-employer data
States like Indiana provide employment history as wide-format columns. Always melt to long format before outputting.

### "WITHHELD" names
Some states anonymize officers involved in ongoing investigations. The preprocess pipeline filters out records where `last_name` contains "withheld". This is expected behavior.

### Records with no `person_nbr`
Drop these — they cannot be joined to other records or identified across updates.

---

## Incremental releases: appending new data to a prior index

Some states do not re-send their full history with each records request.
Instead they send only the stints that *started* since the last request
(e.g. Kansas sends one `Employment History` file per calendar year). The
new files are therefore not a replacement for what is already in Firebase —
uploading them alone would drop every earlier year. The cleaning script must
rebuild a comprehensive index by appending the new rows to the previously
cleaned index.

### How to recognise it

Before writing any code, check the `start_date` range of each new file and
compare it with the prior index (`dropbox:national-post-db/<state>/output/`
or the last `<state>_index.csv` you produced):

- New files cover only recent start dates (months or a few years) while the
  prior index goes back decades → **incremental release, append**.
- New files cover the same span as the prior index → **full refresh, replace**.
- Row counts are a poor signal on their own; an incremental file for one
  year can be larger than a small state's full history.

### Procedure

1. **Put the prior index in `data/input/`** alongside the new raw files and
   treat it as an input, not something to hand-merge afterwards. The whole
   rebuild must be reproducible from `clean.py`.

2. **Find the overlap window.** The prior index was pulled on some date; the
   new files usually start a little before that (the state's export window
   rarely aligns with your last pull). Rows in that window exist in both
   sources, and the *new* copy is more current — it has end dates that were
   still open at the last pull. Determine the cut-off empirically:

   ```python
   old_sd = pd.to_datetime(old["start_date"])
   new_sd = pd.to_datetime(new["start_date"])
   print("old max start:", old_sd.max(), "| new min start:", new_sd.min())
   # Confirm every old row in the window has a counterpart in new
   window = old[old_sd >= new_sd.min()]
   m = window.merge(new, on=["person_nbr", "agency_name", "start_date"],
                    how="outer", indicator=True)
   print(m["_merge"].value_counts())   # want no 'left_only'
   ```

   If every old row in the window matches a new row, drop the old rows from
   the window and let the new file supply them. Hard-code the cut-off as a
   named constant (`SUPERSEDE_FROM = "2024-11-01"`) and write the dropped
   rows to a review file.

3. **Normalise both sources with the same functions before concatenating.**
   The prior index was cleaned under older rules — different rank codes,
   agency spellings, name parsing. Run the old rows through the *current*
   `clean_agency_name`, `clean_rank`, name parser, and date cleaner so the
   result is internally consistent, rather than accepting its columns as-is.
   Re-parse names from `full_name` for every row instead of trusting the
   old `first_name`/`last_name` columns.

4. **Deduplicate with a deterministic winner, not `keep="first"`.** The prior
   index was itself often built by concatenating overlapping exports, so it
   can contain the same stint twice (once open, once closed). Row order in a
   CSV is not a recency signal. Pick the row to keep by an explicit rule —
   latest `end_date` wins, closed beats open — and write every duplicate
   group to a review file before resolving it:

   ```python
   key = ["person_nbr", "agency_name", "start_date"]
   ordered = df.assign(_open=df["end_date"] == "").sort_values(
       key + ["_open", "end_date"], ascending=[True, True, True, False, True]
   )
   df = ordered.drop_duplicates(subset=key, keep="last").drop(columns="_open")
   ```

5. **Check for stale open end dates across the seam.** An officer who was
   "currently employed" in the prior index and then appears in the new file
   at a different agency (or at the same agency after a promotion) still has
   an open row from the old data. If the state splits stints on rank/status
   changes, collapse contiguous rows per `(person_nbr, agency_name)` and
   treat a non-final open row as ending when the next row starts (see
   `clean/2026/KS/src/clean.py::collapse_contiguous_stints`). If the state
   does not split stints, leave the rows alone — a genuine second job at a
   different agency is not an error.

6. **Do not naively `drop_duplicates()` on all columns and move on.** Inspect
   what would be dropped first: group the duplicate candidates by which
   source they came from and by which column differs. Exact duplicates across
   files usually mean the files overlap and step 2 applies; rows that differ
   only in `end_date` are step 4; rows that differ in `rank` at the same
   agency are step 5.

7. **Report the seam in the README.** Record the cut-off date, how many old
   rows were superseded, how many duplicates were resolved, and the final
   `start_date` range, so the next incremental release can be appended on top
   of this one the same way.

### Output naming

The rebuilt index is the state's complete history and is written as the
normal `<state>_index.csv`; the year directory reflects the release, not the
data range. Preprocess and upload it exactly as a full refresh — it replaces
the prior Firebase data for that state (`make force-upload STATE=<state>`).

Worked example: `clean/2026/KS/` (README documents every decision).

---

---

## Lessons from the Georgia test case

These patterns were discovered during the first automated pipeline run and apply to any state, not just Georgia.

### Agency name noise beyond code prefixes
After stripping the leading agency code, the name field may still contain:
- **Trailing status fragments** joined by a slash: `"METRO STATE PRISON/INACTIVE"`, `"DEPT OF CORRECTIONS/18 MOS."`. Strip everything after the first `/`.
- **Non-agency administrative strings**: `"APPLICATION DENIED"`, `"APPLICATION PURGED"`. These appear when an officer's application was rejected. Filter them out by checking against a known set after cleaning.

### Discipline join must be inner, not outer
Using `how='outer'` to join violations and sanctions inflates row counts via a cartesian product when a case has multiple violations *and* multiple sanctions. The correct approach:
1. `how='inner'` from violations to sanctions — keeps only violations that have a sanction
2. Deduplicate on `(case_id, person_nbr, violation)` keeping the most recent sanction
3. This produces one row per violation with its best sanction

### Discipline rows with no employment match
After joining discipline records to the employment table for context, some officers will have no employment record. These produce rows with an empty `start_date`, which the preprocess pipeline silently drops. Drop them explicitly in the cleaning script so the output is clean and the count is predictable.

### Suffix casing in full_name
The `suffix` column from demographics tables is often sparsely populated (7–8% fill rate in Georgia). Include it in `full_name` when present: `"smith, john a jr"`. The preprocess pipeline will proper-case the suffix column (`jr` → `Jr`), so leave it lowercase in the cleaning script output.

---

# Part 2 — Uploading

Applies to manual and automated work alike.

### Step 1: Put the index where `db/preprocess` looks for it

`db/preprocess` reads `states/<state>/<year>/output/*_index.csv` (lowercase
state code). Manual cleaning writes to `clean/<year>/<STATE>/data/output/`,
so copy the index across:

```bash
mkdir -p states/<state>/<year>/output
cp clean/<year>/<STATE>/data/output/<state>_index.csv \
   states/<state>/<year>/output/
```

### Step 2: Preprocess and dry run

```bash
cd db && make dry-run STATE=<state> YEAR=<year>
```

This normalizes the data, writes
`db/data/output/<full-state>/<full-state>-processed.csv.gz`, and prints the
upload manifest without writing to Firebase. Read the output: it reports row
counts and warns about empty values in required columns.

Preprocess applies its own transformations on top of your cleaning —
lowercasing, agency abbreviation expansion, proper-casing, dropping rows
with an empty `start_date`, filtering `withheld` names, and adding the
`state` and `document_id` fields. Do not duplicate that work in `clean.py`.

### Step 3: Upload

```bash
cd db && make upload STATE=<state> YEAR=<year>        # first time
cd db && make force-upload STATE=<state> YEAR=<year>  # replacing existing data
```

Use `force-upload` when the state is already in Firebase — it deletes the
existing documents first. A plain `upload` over existing data leaves stale
rows behind.

### Step 4: Run the front-end scripts

From the front-end repo, in order:

```bash
npx tsx scripts/normalizeStateData.ts <full-state>
npx tsx scripts/normalizeDatesByState.ts <full-state>
npx tsx scripts/addSearchQueriesByState.ts <full-state>
npx tsx scripts/generateStateStats.ts <full-state>
npx tsx scripts/generateAgencyStats.ts <full-state>
```

### State naming

Two schemes coexist and `db/helpers/state_names.py` bridges them:
two-letter codes (`ks`, `il`) upstream of Firebase, full hyphenated names
(`kansas`, `illinois`) downstream. `make` accepts either. When adding a new
state, add its code to `STATE_NAMES` and keep it in sync with
`constants/states.ts` in the front-end repo. See the repo `README.md` for
the full explanation and the orphan-document incident that motivated it.

---

# Part 3 — The automated agent pipeline

**This part applies only to the CC agent** (`pipeline/cc_agent.py`), which
writes cleaning scripts unattended and needs a machine-readable way to judge
its own output. Humans cleaning a state by hand can stop at Part 2.

### Layout

The agent works in `states/<state>/<year>/` (lowercase state code), which
`pipeline/rclone_client.py` populates from Dropbox:

```
states/<state>/<year>/
├── data/
│   ├── input/        ← raw files from Dropbox (read-only)
│   └── groundtruth/  ← reference outputs, when available (read-only)
├── output/           ← cleaned CSVs + judge reports
└── src/
    ├── clean.py
    └── validate.py   ← LLM-as-judge test suite
```

The agent reads `readmes/<STATE>_README.md` first when one exists.

### Running validation

```bash
cd states/<state>/<year>/ && python src/validate.py
```

Writes `output/judge_report.md` (human-readable) and `output/judge_report.json`
(`{"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}`). The report
must be PASS or WARN for the pipeline to accept the run.

### Ground truth

`validate.py` degrades gracefully based on what is available:

- **With `data/groundtruth/`**: full comparison checks, including LLM
  row-count comparison and side-by-side agency/name scoring against the
  reference.
- **Without it**: schema, date-format and `person_nbr` checks only. The LLM
  still scores agency-name and name-parsing quality against general
  best-practice criteria.

Ground truth exists only for states that have been manually validated. A new
state will not have it — that is expected, not an error.

### Row-count drift against reference outputs

Reference outputs in `data/groundtruth/` are point-in-time snapshots. As
Dropbox data is updated, row counts drift — expect ±5% for employment
indexes, and more for discipline indexes if coverage has grown. The judge
WARNs but does not fail above 5%.
