"""
Georgia POST data cleaning script.
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

parser = argparse.ArgumentParser(description="Clean GA POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_date_series(series):
    """Vectorized date cleaning. Returns a string series: YYYY-MM-DD or ''.
    0000-00-00 is kept as-is (means currently employed / unknown).
    Malformed dates that pandas cannot parse are kept as-is from source."""
    s = series.astype(str).str.strip()
    # Mark truly invalid (NaN/None/empty)
    invalid_mask = s.isin(['', 'nan', 'NaT', 'None'])
    # Keep 0000-xx-xx as-is
    zero_mask = s.str.startswith('0000') | s.isin(['0000-00-00'])
    # Parse remaining dates
    parseable_mask = ~invalid_mask & ~zero_mask
    parsed = pd.to_datetime(s.where(parseable_mask, other=pd.NaT), errors='coerce')
    result = s.copy()
    result[invalid_mask] = ''
    # For parseable dates, use formatted version; where coerce returned NaT, keep original
    parsed_formatted = parsed.dt.strftime('%Y-%m-%d')
    parse_ok = parseable_mask & parsed.notna()
    parse_fail = parseable_mask & parsed.isna()
    result[parse_ok] = parsed_formatted[parse_ok]
    # For parse failures, keep raw value (e.g. '0201-05-01', '2023-00-01')
    result[parse_fail] = s[parse_fail]
    return result


def safe_date(val):
    """Scalar fallback for single values."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None'):
        return ''
    if s == '0000-00-00':
        return '0000-00-00'
    try:
        parsed = pd.to_datetime(s, errors='coerce')
        if pd.isna(parsed):
            return ''
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return ''


NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}


def is_non_agency(name):
    return str(name).strip().lower() in NON_AGENCY_VALUES


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

print("Loading raw files...")

employment = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_employment.csv"),
    dtype=str,
    keep_default_na=False,
)

officer_data = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_data.csv"),
    dtype=str,
    keep_default_na=False,
)

violations = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_violations.csv"),
    dtype=str,
    keep_default_na=False,
)

sanctions = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_sanctions.csv"),
    dtype=str,
    keep_default_na=False,
)

print(f"  employment: {len(employment):,} rows")
print(f"  officer_data: {len(officer_data):,} rows")
print(f"  violations: {len(violations):,} rows")
print(f"  sanctions: {len(sanctions):,} rows")


# ---------------------------------------------------------------------------
# Clean officer_data (demographics)
# ---------------------------------------------------------------------------

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

# Lowercase person_nbr
officer_data['person_nbr'] = officer_data['person_nbr'].str.lower().str.strip()

# Lowercase name fields
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer_data[col] = officer_data[col].str.lower().str.strip()


# ---------------------------------------------------------------------------
# Clean employment (index)
# ---------------------------------------------------------------------------

employment.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'full_name_raw',
    'AGENCY': 'agency_name',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
}, inplace=True)

# Lowercase person_nbr
employment['person_nbr'] = employment['person_nbr'].str.lower().str.strip()

# Clean dates (vectorized)
employment['start_date'] = clean_date_series(employment['start_date'])
employment['end_date']   = clean_date_series(employment['end_date'])

# Drop rows with truly empty start_date ('' means NaN/None — not 0000-00-00)
n_before = len(employment)
employment = employment[employment['start_date'] != '']
print(f"  Dropped {n_before - len(employment):,} employment rows with empty start_date")

# Keep agency name exactly as-is from source (groundtruth keeps raw value incl. /INACTIVE, leading spaces, etc.)
# Do NOT strip — groundtruth preserves ' Not found' with leading space
employment['agency_name'] = employment['agency_name'].astype(str)

print(f"  Employment rows: {len(employment):,} rows")


# ---------------------------------------------------------------------------
# Merge employment + demographics
# ---------------------------------------------------------------------------

merged = employment.merge(
    officer_data[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left',
)

# Build full_name: "last_name, first_name middle_name suffix" (lowercase)
def build_full_name(row):
    parts = [row['first_name']]
    if row['middle_name'] and str(row['middle_name']).strip():
        parts.append(str(row['middle_name']).strip())
    if row['suffix'] and str(row['suffix']).strip():
        parts.append(str(row['suffix']).strip())
    given = ' '.join(p for p in parts if p)
    last = str(row['last_name']).strip() if row['last_name'] else ''
    if last:
        return f"{last}, {given}".strip().rstrip(',').strip()
    return given


def build_full_name_vectorized(df):
    """Vectorized full_name construction."""
    first  = df['first_name'].fillna('').str.strip()
    middle = df['middle_name'].fillna('').str.strip()
    suffix = df['suffix'].fillna('').str.strip()
    last   = df['last_name'].fillna('').str.strip()
    # given = first [+ middle] [+ suffix]
    given = first.copy()
    has_middle = middle != ''
    given[has_middle] = given[has_middle] + ' ' + middle[has_middle]
    has_suffix = suffix != ''
    given[has_suffix] = given[has_suffix] + ' ' + suffix[has_suffix]
    # full = last + ', ' + given  (when last exists)
    has_last = last != ''
    full = given.copy()
    full[has_last] = last[has_last] + ', ' + given[has_last]
    return full

merged['full_name'] = build_full_name_vectorized(merged)

# Fill NaN in name columns
for col in ['first_name', 'last_name', 'middle_name', 'suffix']:
    merged[col] = merged[col].fillna('').str.strip()

# Dedup on person_nbr + agency_name + start_date
dupes = merged.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
if dupes > 0:
    print(f"  Warning: {dupes:,} duplicate employment rows — dropping")
    merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

print(f"  Employment index rows: {len(merged):,}")

# Select output columns
index_cols = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex',
]
ga_index = merged[index_cols].copy()


# ---------------------------------------------------------------------------
# Discipline index
# ---------------------------------------------------------------------------

# Rename violations
violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'viol_name',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
}, inplace=True)

violations['person_nbr'] = violations['person_nbr'].str.lower().str.strip()
violations['case_id'] = violations['case_id'].str.strip()
violations['violation'] = violations['violation'].str.strip()
violations['violation_date'] = clean_date_series(violations['violation_date'])

# Rename sanctions
sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'sanc_name',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
}, inplace=True)

sanctions['person_nbr'] = sanctions['person_nbr'].str.lower().str.strip()
sanctions['case_id'] = sanctions['case_id'].str.strip()
sanctions['sanction'] = sanctions['sanction'].str.strip()
sanctions['sanction_date'] = clean_date_series(sanctions['sanction_date'])

# Inner join violations + sanctions on case_id + person_nbr
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner',
)

print(f"  Discipline after inner join: {len(discipline):,} rows")

# Deduplicate: keep most recent sanction per (case_id, person_nbr, violation)
discipline['sanction_date_sort'] = discipline['sanction_date'].replace('', '0000-00-00')
discipline = (
    discipline
    .sort_values('sanction_date_sort', ascending=False)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
    .drop(columns=['sanction_date_sort'])
)
print(f"  Discipline after dedup: {len(discipline):,} rows")

# Title-case violation and sanction (to match groundtruth casing)
def title_case_field(s):
    if not s or str(s).strip() == '':
        return s
    return str(s).strip().title()

discipline['violation'] = discipline['violation'].apply(title_case_field)
discipline['sanction'] = discipline['sanction'].apply(title_case_field)

# Keep case_id as string with leading zeros (groundtruth uses '0045701195' format)
discipline['case_id'] = discipline['case_id'].str.strip()


# ---------------------------------------------------------------------------
# Attach employment context to discipline rows (vectorized)
# ---------------------------------------------------------------------------

# Build a lookup table from employment with lowercase agency names (for discipline)
emp_lookup = employment[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()
emp_lookup['agency_name'] = emp_lookup['agency_name'].str.lower()

# Join discipline to all employment periods for the officer
disc_emp = discipline.merge(
    emp_lookup,
    on='person_nbr',
    how='left',
)

print(f"  Discipline after employment join: {len(disc_emp):,} rows")

# Vectorized period scoring
# Convert dates to numeric (days since epoch) for fast comparison
def dates_to_numeric(series):
    dt = pd.to_datetime(series.replace({'0000-00-00': pd.NaT, '': pd.NaT}), errors='coerce')
    return dt.view('int64').where(dt.notna(), other=pd.NaT)

v_dt  = pd.to_datetime(disc_emp['violation_date'].replace({'0000-00-00': pd.NaT, '': pd.NaT}), errors='coerce')
s_dt  = pd.to_datetime(disc_emp['start_date'].replace({'0000-00-00': pd.NaT, '': pd.NaT}), errors='coerce')
e_dt  = pd.to_datetime(
    disc_emp['end_date'].replace({'0000-00-00': pd.NaT, '': pd.NaT}), errors='coerce'
).fillna(pd.Timestamp('2099-12-31'))

no_vdate = v_dt.isna()
no_sdate = s_dt.isna()

inside = (~no_vdate) & (~no_sdate) & (v_dt >= s_dt) & (v_dt <= e_dt)
before = (~no_vdate) & (~no_sdate) & (v_dt < s_dt)
after  = (~no_vdate) & (~no_sdate) & (v_dt > e_dt)

score = pd.Series(1, index=disc_emp.index, dtype='int64')
score[no_sdate] = 9999
score[inside] = 0
score[before] = (s_dt[before] - v_dt[before]).dt.days
score[after]  = (v_dt[after]  - e_dt[after]).dt.days

disc_emp['_period_score'] = score

# Keep best employment period per (case_id, person_nbr, violation)
disc_emp = (
    disc_emp
    .sort_values('_period_score')
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
    .drop(columns=['_period_score'])
)

print(f"  Discipline after best-period dedup: {len(disc_emp):,} rows")

# Drop rows where start_date is empty (no employment match)
disc_emp = disc_emp[disc_emp['start_date'].fillna('') != '']
print(f"  Discipline after dropping no-employment: {len(disc_emp):,} rows")


# ---------------------------------------------------------------------------
# Build discipline index with demographics
# ---------------------------------------------------------------------------

# Join demographics
disc_final = disc_emp.merge(
    officer_data[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left',
)

# Fill NaN
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    disc_final[col] = disc_final[col].fillna('').str.strip()

# Build full_name (lowercase)
disc_final['full_name'] = disc_final.apply(build_full_name, axis=1)

# lowercase race, sex for discipline (groundtruth shows lowercase)
disc_final['race'] = disc_final['race'].str.lower().fillna('')
disc_final['sex'] = disc_final['sex'].str.lower().fillna('')

# Select output columns matching groundtruth column order
disc_cols = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date', 'violation',
    'violation_date', 'full_name', 'agency_name', 'rank', 'start_date',
    'end_date', 'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]

disc_final = disc_final[disc_cols].copy()
disc_final['year_of_birth'] = disc_final['year_of_birth'].fillna('').astype(str).str.strip()

print(f"  Discipline index rows: {len(disc_final):,}")


# ---------------------------------------------------------------------------
# Validate before writing
# ---------------------------------------------------------------------------

required_index = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in required_index if c not in ga_index.columns]
assert not missing_cols, f"Missing required columns in index: {missing_cols}"

# start_date must not be empty string (0000-00-00 is allowed)
assert (ga_index['start_date'] != '').all(), "start_date must not be empty in index"

# person_nbr should be lowercase, no whitespace
assert ga_index['person_nbr'].str.lower().eq(ga_index['person_nbr']).all(), \
    "person_nbr must be lowercase"

# Discipline required columns
required_disc = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_disc = [c for c in required_disc if c not in disc_final.columns]
assert not missing_disc, f"Missing required columns in discipline: {missing_disc}"

assert (disc_final['start_date'] != '').all(), "start_date must not be empty in discipline"

print("Validation passed!")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

index_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

ga_index.to_csv(index_path, index=False)
disc_final.to_csv(disc_path, index=False)

print(f"Wrote {len(ga_index):,} rows to {index_path}")
print(f"Wrote {len(disc_final):,} rows to {disc_path}")
print("Done.")
