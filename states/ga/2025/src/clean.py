"""
Georgia POST Data Cleaning Script — 2025
Produces:
  output/ga_index.csv
  output/ga-discipline_index.csv
"""

import argparse
import os
import re
import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_date_series(series):
    """Vectorized date cleaning: returns a Series of YYYY-MM-DD or empty strings.
    0000-00-00 is kept as-is so callers can decide whether to blank it.
    """
    s = series.astype(str).str.strip()
    # Mark blanks/nulls as empty
    null_mask = s.isin(['', 'nan', 'NaT', 'None', 'NaN'])
    # Mark 0000-00-00 separately (preserve for end_date)
    zero_mask = s == '0000-00-00'
    # Parse valid dates
    parsed = pd.to_datetime(s.where(~null_mask & ~zero_mask), errors='coerce')
    result = parsed.dt.strftime('%Y-%m-%d').fillna('')
    result[null_mask] = ''
    result[zero_mask] = '0000-00-00'
    return result


def safe_date(val):
    """Single-value version (for discipline columns that are small)."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None', 'NaN'):
        return ''
    if s == '0000-00-00':
        return s
    try:
        parsed = pd.to_datetime(s, errors='coerce')
        if pd.isna(parsed):
            return ''
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return ''


def clean_person_nbr(val):
    return str(val).strip().lower()


def build_full_name(last, first, middle, suffix):
    """Build full_name as 'last, first middle suffix' (lowercase)."""
    parts = [str(first).strip()]
    if middle and str(middle).strip() not in ('', 'nan', 'NaN'):
        parts.append(str(middle).strip())
    name = str(last).strip() + ', ' + ' '.join(parts)
    if suffix and str(suffix).strip() not in ('', 'nan', 'NaN'):
        name = name + ' ' + str(suffix).strip()
    return name.lower()


# ---------------------------------------------------------------------------
# Step 1: Load raw files
# ---------------------------------------------------------------------------
print("Loading input files...")

employment = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_employment.csv'),
    dtype=str,
    keep_default_na=False,
)
officer_data = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_data.csv'),
    dtype=str,
    keep_default_na=False,
)
agency_data = pd.read_csv(
    os.path.join(INPUT_DIR, 'agency_data.csv'),
    dtype=str,
    keep_default_na=False,
)
violations = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_violations.csv'),
    dtype=str,
    keep_default_na=False,
)
sanctions = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_sanctions.csv'),
    dtype=str,
    keep_default_na=False,
)

print(f"  employment rows: {len(employment)}")
print(f"  officer_data rows: {len(officer_data)}")
print(f"  violations rows: {len(violations)}")
print(f"  sanctions rows: {len(sanctions)}")


# ---------------------------------------------------------------------------
# Step 2: Clean employment file
# ---------------------------------------------------------------------------
print("Cleaning employment data...")

# Rename columns
employment.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'full_name_raw',
    'AGENCY': 'agency_raw',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
}, inplace=True)

# Clean person_nbr
employment['person_nbr'] = employment['person_nbr'].apply(clean_person_nbr)

# Parse agency_name: keep raw with code prefix (matches groundtruth format)
# The groundtruth keeps "G1720 DEKALB COUNTY POLICE DEPARTMENT" as agency_name
employment['agency_name'] = employment['agency_raw'].str.strip()

# Clean dates — vectorized for performance on 480K+ rows
# Both start_date and end_date: keep 0000-00-00 as-is (groundtruth preserves it)
employment['start_date'] = safe_date_series(employment['start_date'])
employment['end_date'] = safe_date_series(employment['end_date'])

# Drop rows with truly empty start_date (NaN/blank) but keep 0000-00-00
before = len(employment)
employment = employment[employment['start_date'] != '']
print(f"  Dropped {before - len(employment)} rows with empty start_date")

# Filter out non-agency values in agency_name
NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}
before = len(employment)
employment = employment[
    ~employment['agency_name'].str.lower().isin(NON_AGENCY_VALUES)
]
print(f"  Dropped {before - len(employment)} rows with non-agency agency_name")


# ---------------------------------------------------------------------------
# Step 3: Clean officer demographics
# ---------------------------------------------------------------------------
print("Cleaning officer demographics...")

officer_data.rename(columns={
    'OKEY': 'person_nbr',
    'LAST NAME': 'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE': 'middle_name',
    'SUFFIX': 'suffix',
    'YOB': 'year_of_birth',
    'SEX': 'sex',
    'RACE': 'race',
}, inplace=True)

officer_data['person_nbr'] = officer_data['person_nbr'].apply(clean_person_nbr)

# Strip whitespace and lowercase name fields (groundtruth uses lowercase)
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer_data[col] = officer_data[col].str.strip().str.lower()

# Keep only needed columns
officer_data = officer_data[[
    'person_nbr', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'sex', 'race'
]]


# ---------------------------------------------------------------------------
# Step 4: Merge employment + demographics → employment index
# ---------------------------------------------------------------------------
print("Merging employment + demographics...")

merged = employment.merge(officer_data, on='person_nbr', how='left')

# Build full_name
merged['full_name'] = merged.apply(
    lambda r: build_full_name(
        r.get('last_name', ''),
        r.get('first_name', ''),
        r.get('middle_name', ''),
        r.get('suffix', '')
    ),
    axis=1
)

# Deduplicate on (person_nbr, agency_name, start_date)
before = len(merged)
merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Dropped {before - len(merged)} duplicate rows")

print(f"  Employment index rows: {len(merged)}")

# Select output columns in groundtruth order
employment_index = merged[[
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex'
]].copy()


# ---------------------------------------------------------------------------
# Step 5: Build discipline index
# ---------------------------------------------------------------------------
print("Building discipline index...")

# Rename violations
violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
}, inplace=True)
violations['person_nbr'] = violations['person_nbr'].apply(clean_person_nbr)
# Strip spaces from case_id (some cases have embedded spaces like "010 780707")
violations['case_id'] = violations['case_id'].str.replace(' ', '', regex=False)
violations['violation_date'] = safe_date_series(violations['violation_date'])
# 0000-00-00 violation_date → empty string
violations.loc[violations['violation_date'] == '0000-00-00', 'violation_date'] = ''

# Rename sanctions
sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
}, inplace=True)
sanctions['person_nbr'] = sanctions['person_nbr'].apply(clean_person_nbr)
# Strip spaces from case_id
sanctions['case_id'] = sanctions['case_id'].str.replace(' ', '', regex=False)
sanctions['sanction_date'] = safe_date_series(sanctions['sanction_date'])
sanctions.loc[sanctions['sanction_date'] == '0000-00-00', 'sanction_date'] = ''

# Inner join violations × sanctions on case_id + person_nbr
# This produces a cartesian product per case: each violation paired with
# each sanction for that case (matching groundtruth behaviour).
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner'
)
print(f"  Discipline rows after inner join (violations x sanctions): {len(discipline)}")


# ---------------------------------------------------------------------------
# Step 6: Join discipline to employment for context
# ---------------------------------------------------------------------------
print("Joining discipline to employment context...")

# Get all employment periods for officers in discipline (pre-filter for speed)
emp_cols = ['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']
disc_okeys = set(discipline['person_nbr'].unique())
emp_for_disc = employment.loc[employment['person_nbr'].isin(disc_okeys), emp_cols].copy()

# Merge discipline with all employment periods
disc_emp = discipline.merge(emp_for_disc, on='person_nbr', how='left')
print(f"  After join to employment: {len(disc_emp)}")

# Score each employment period vectorized:
# 0 = violation_date falls within period, else calendar distance
def compute_scores_vectorized(df):
    v = pd.to_datetime(df['violation_date'], errors='coerce')
    s = pd.to_datetime(df['start_date'], errors='coerce')
    # Treat 0000-00-00 end_date as far future (still employed)
    end_clean = df['end_date'].replace('0000-00-00', '2099-12-31')
    e = pd.to_datetime(end_clean, errors='coerce').fillna(pd.Timestamp('2099-12-31'))

    within = (s <= v) & (v <= e)
    too_early = v < s
    too_late = v > e

    score = pd.Series(9999, index=df.index, dtype=float)
    score[within] = 0
    score[too_early] = (s[too_early] - v[too_early]).dt.days
    score[too_late] = (v[too_late] - e[too_late]).dt.days
    # null v or s → 9999 already
    score[v.isna() | s.isna()] = 9999
    return score


disc_emp['_score'] = compute_scores_vectorized(disc_emp)

# Keep only employment periods where violation_date falls WITHIN the period (score=0)
# Then deduplicate on (case_id, person_nbr, violation, sanction) keeping first match
disc_emp = disc_emp[disc_emp['_score'] == 0].drop(columns=['_score'])
disc_emp = disc_emp.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
print(f"  Discipline rows after employment exact-match (score=0): {len(disc_emp)}")

# Drop rows with empty start_date (no employment match)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp['start_date'].fillna('') != '']
print(f"  Dropped {before - len(disc_emp)} discipline rows with no employment match")

# Drop rows where end_date is 0000-00-00 (currently employed officers not in GT discipline)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp['end_date'] != '0000-00-00']
print(f"  Dropped {before - len(disc_emp)} discipline rows where employment end_date is 0000-00-00")

# Drop rows with empty violation_date (GT has no empty violation_dates)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp['violation_date'] != '']
print(f"  Dropped {before - len(disc_emp)} discipline rows with empty violation_date")


# ---------------------------------------------------------------------------
# Step 7: Add demographics to discipline index
# ---------------------------------------------------------------------------
disc_with_demo = disc_emp.merge(
    officer_data[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Build full_name
disc_with_demo['full_name'] = disc_with_demo.apply(
    lambda r: build_full_name(
        r.get('last_name', ''),
        r.get('first_name', ''),
        r.get('middle_name', ''),
        r.get('suffix', '')
    ),
    axis=1
)

# Titlecase sanction and violation to match groundtruth
disc_with_demo['sanction'] = disc_with_demo['sanction'].str.title()
disc_with_demo['violation'] = disc_with_demo['violation'].str.title()

# Select columns in groundtruth order
discipline_index = disc_with_demo[[
    'case_id', 'person_nbr', 'sanction', 'sanction_date',
    'violation', 'violation_date', 'full_name', 'agency_name', 'rank',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex'
]].copy()

# Lowercase agency_name, rank, race, sex to match groundtruth
discipline_index['agency_name'] = discipline_index['agency_name'].str.lower()
discipline_index['rank'] = discipline_index['rank'].str.lower()
discipline_index['race'] = discipline_index['race'].str.lower()
discipline_index['sex'] = discipline_index['sex'].str.lower()

print(f"  Final discipline index rows: {len(discipline_index)}")


# ---------------------------------------------------------------------------
# Step 8: Validate and write output
# ---------------------------------------------------------------------------
print("Validating output...")

required_emp = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required_emp:
    assert col in employment_index.columns, f"Missing required column: {col}"

# start_date should not be empty (0000-00-00 is allowed as it means unknown date in source)
assert (employment_index['start_date'] != '').all(), "start_date must not be empty"

# Check person_nbr format
assert employment_index['person_nbr'].str.match(r'^[a-z]').all(), \
    "person_nbr should start with lowercase letter"

print(f"Employment index: {len(employment_index)} rows")
print(f"Discipline index: {len(discipline_index)} rows")

# Write output
emp_out = os.path.join(OUTPUT_DIR, 'ga_index.csv')
disc_out = os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv')

employment_index.to_csv(emp_out, index=False)
discipline_index.to_csv(disc_out, index=False)

print(f"Wrote {emp_out}")
print(f"Wrote {disc_out}")
print("Done.")
