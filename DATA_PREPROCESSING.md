# DATA_PREPROCESSING.md

This document is the authoritative guide for Claude agents and humans cleaning raw POST (Peace Officer Standards and Training) data for any U.S. state. It covers how to read raw downloads, produce a standardized output CSV, and pass it through the processing pipeline.

---

## Overview of the Pipeline

```
Dropbox (raw state data)
    ↓
automated_processing/data/input/<STATE>/data/input/   ← raw files land here
    ↓
  [Claude agent runs, reads this guide]
    ↓
automated_processing/data/output/<STATE>/             ← agent writes cleaned CSVs here
    ↓
db/preprocess/                                        ← normalizes + compresses
    ↓
db/upload/ --dry-run                                  ← validates without uploading
    ↓
db/upload/                                            ← live Firebase upload
```

---

## Output Schema

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

## Step-by-Step Cleaning Process

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

### Step 12: Validate output

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

### Step 13: Write output

```python
import os

output_dir = 'states/<STATE>/data/output/'
os.makedirs(output_dir, exist_ok=True)

df.to_csv(os.path.join(output_dir, '<state>_index.csv'), index=False)

# If discipline data exists:
discipline_df.to_csv(
    os.path.join(output_dir, '<state>-discipline_index.csv'), index=False
)
```

---

## Common Pitfalls

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

## Lessons from the Georgia Test Case

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

### Row count differences against reference outputs
Reference outputs in `states/<STATE>/data/output/` are point-in-time snapshots. As Dropbox data is updated, row counts will drift — expect ±5% for employment indexes and larger variation for discipline indexes if data coverage has grown. The LLM-as-judge test WARNs but does not fail on row count differences above 5%.

---

## Running the Pipeline After Cleaning

Once the cleaned CSV(s) are in `states/<STATE>/data/output/`:

```bash
# Dry run (validate preprocess + print upload summary without writing to Firebase)
cd db
make run STATE=<state> DRY_RUN=true

# Live upload (when ready)
make run STATE=<state>
```

See `db/README.md` for full pipeline documentation.
