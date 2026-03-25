"""
Georgia POST Data Cleaning Script
Processes raw GA POST files into standardized employment and discipline indexes.
"""

import argparse
import os
import re
import pandas as pd

# ---------------------------------------------------------------------------
# CLI args
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

def fast_clean_date(series, keep_zero=True):
    """
    Vectorized date cleaning.
    keep_zero=True  → '0000-00-00' stays as '0000-00-00'
    keep_zero=False → '0000-00-00' becomes ''
    """
    s = series.astype(str).str.strip()
    if keep_zero:
        # Replace blanks/nan/NaT/None with '' first
        s = s.replace({'nan': '', 'NaT': '', 'None': ''})
        # Parse everything that isn't '0000-00-00' or ''
        mask_zero = s == '0000-00-00'
        mask_empty = s == ''
        parsed = pd.to_datetime(s.where(~mask_zero & ~mask_empty), errors='coerce')
        result = parsed.dt.strftime('%Y-%m-%d').fillna('')
        result[mask_zero] = '0000-00-00'
        result[mask_empty] = ''
        return result
    else:
        s = s.replace({'nan': '', 'NaT': '', 'None': '', '0000-00-00': ''})
        parsed = pd.to_datetime(s.where(s != ''), errors='coerce')
        return parsed.dt.strftime('%Y-%m-%d').fillna('')


def build_full_name_vectorized(df):
    """
    Build full_name as 'last_name, first_name [middle] [suffix]' in lowercase.
    All vectorized.
    """
    last  = df['last_name'].fillna('').str.strip()
    first = df['first_name'].fillna('').str.strip()
    mid   = df['middle_name'].fillna('').str.strip()
    suf   = df['suffix'].fillna('').str.strip()

    # first + optional middle
    name_part = first.where(mid == '', first + ' ' + mid)
    # combine last, name_part
    full = last + ', ' + name_part
    # add suffix if present
    full = full.where(suf == '', full + ' ' + suf)
    return full.str.lower()


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------
print("Loading raw files...")

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

print(f"  employment: {len(employment):,} rows")
print(f"  officer_data: {len(officer_data):,} rows")
print(f"  violations: {len(violations):,} rows")
print(f"  sanctions: {len(sanctions):,} rows")

# ---------------------------------------------------------------------------
# Clean officer_data — demographics
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

officer_data['person_nbr'] = officer_data['person_nbr'].str.lower().str.strip()

for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    # Strip whitespace, remove periods, replace slash with space, lowercase
    officer_data[col] = (
        officer_data[col]
        .str.strip()
        .str.replace(r'\.', '', regex=True)       # remove periods (e.g. "J." → "J")
        .str.replace(r'/', ' ', regex=False)       # slash → space (e.g. "AARON/SMITH" → "AARON SMITH")
        .str.replace(r'\s+', ' ', regex=True)     # collapse extra spaces
        .str.strip()
        .str.lower()
    )
    officer_data[col] = officer_data[col].replace({'': None})

officer_data['race'] = officer_data['race'].str.strip().str.lower()
officer_data['sex']  = officer_data['sex'].str.strip().str.lower()

print(f"  officer_data cleaned: {len(officer_data):,} rows")

# ---------------------------------------------------------------------------
# Clean employment
# ---------------------------------------------------------------------------
print("Cleaning employment data...")

employment.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'full_name_raw',
    'AGENCY': 'agency_raw',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
}, inplace=True)

employment['person_nbr'] = employment['person_nbr'].str.lower().str.strip()
employment = employment[employment['person_nbr'] != '']

# Agency name: keep the raw AGENCY value as-is (groundtruth preserves codes, slashes, etc.)
# Only strip leading/trailing whitespace
employment['agency_name'] = employment['agency_raw'].str.strip()

# Only filter truly empty agency names (no agency code at all)
employment = employment[employment['agency_name'] != '']

# Dates
employment['start_date'] = fast_clean_date(employment['start_date'], keep_zero=True)
employment['end_date']   = fast_clean_date(employment['end_date'],   keep_zero=True)

# Drop rows with empty or zero start_date
employment = employment[
    (employment['start_date'] != '') & (employment['start_date'] != '0000-00-00')
]

employment['rank'] = employment['rank'].str.strip()

print(f"  employment cleaned: {len(employment):,} rows")

# ---------------------------------------------------------------------------
# Merge employment + demographics → employment index
# ---------------------------------------------------------------------------
print("Merging employment + demographics...")

merged = employment.merge(
    officer_data[[
        'person_nbr', 'last_name', 'first_name', 'middle_name',
        'suffix', 'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)

# Fill NaN name fields for full_name building
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    merged[col] = merged[col].fillna('')

merged['full_name'] = build_full_name_vectorized(merged)

# Deduplicate
dupes = merged.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
if dupes.any():
    print(f"  Dropping {dupes.sum():,} duplicate employment rows")
    merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

# Restore None for empty optional fields
for col in ['middle_name', 'suffix']:
    merged[col] = merged[col].replace({'': None})

print(f"  merged employment index: {len(merged):,} rows")

EMPLOYMENT_COLS = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex',
]
employment_index = merged[EMPLOYMENT_COLS].copy()

# ---------------------------------------------------------------------------
# Discipline index — join violations + sanctions
# ---------------------------------------------------------------------------
print("Building discipline index...")

violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
}, inplace=True)

sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw_s',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
}, inplace=True)

violations['person_nbr'] = violations['person_nbr'].str.lower().str.strip()
sanctions['person_nbr']  = sanctions['person_nbr'].str.lower().str.strip()
violations['case_id'] = violations['case_id'].str.strip()
sanctions['case_id']  = sanctions['case_id'].str.strip()

violations['violation']      = violations['violation'].str.strip().str.title()
sanctions['sanction']        = sanctions['sanction'].str.strip().str.title()

violations['violation_date'] = fast_clean_date(violations['violation_date'], keep_zero=False)
sanctions['sanction_date']   = fast_clean_date(sanctions['sanction_date'],   keep_zero=False)

# Inner join
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner',
)
print(f"  discipline after inner join: {len(discipline):,} rows")

# Deduplicate: one row per (case_id, person_nbr, violation, sanction)
# Keep all distinct sanctions per violation (not just most recent)
discipline = discipline.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
print(f"  discipline after dedup: {len(discipline):,} rows")

# ---------------------------------------------------------------------------
# Attach employment context to discipline records (vectorized)
# ---------------------------------------------------------------------------
print("Attaching employment context to discipline...")

emp_lookup = employment[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()

# Only keep employment rows for persons that appear in discipline
disc_persons = discipline['person_nbr'].unique()
emp_lookup_disc = emp_lookup[emp_lookup['person_nbr'].isin(disc_persons)]

disc_with_emp = discipline.merge(emp_lookup_disc, on='person_nbr', how='left')
print(f"  discipline after employment join (before scoring): {len(disc_with_emp):,} rows")

# Vectorized scoring
TODAY = pd.Timestamp.today().normalize()

v_dates = pd.to_datetime(disc_with_emp['violation_date'], errors='coerce')
s_dates = pd.to_datetime(disc_with_emp['start_date'], errors='coerce')

raw_end = disc_with_emp['end_date'].replace({'0000-00-00': '', '': None})
e_dates = pd.to_datetime(raw_end, errors='coerce').fillna(TODAY)

before   = (v_dates < s_dates)
after_dt = (v_dates > e_dates)
no_vdate = v_dates.isna()
no_start = s_dates.isna()

score = pd.Series(0, index=disc_with_emp.index, dtype='int64')
mask_before = before & ~no_vdate & ~no_start
mask_after  = after_dt & ~no_vdate
score[mask_before] = (s_dates[mask_before] - v_dates[mask_before]).dt.days.astype('int64')
score[mask_after]  = (v_dates[mask_after]  - e_dates[mask_after]).dt.days.astype('int64')
score[no_vdate | no_start] = 9_999_999

disc_with_emp['_score'] = score

disc_with_emp = disc_with_emp.sort_values('_score').drop_duplicates(
    subset=['case_id', 'person_nbr', 'violation', 'sanction']
).drop(columns=['_score'])
print(f"  discipline after employment scoring: {len(disc_with_emp):,} rows")

# Drop rows with no employment match
disc_with_emp = disc_with_emp[
    disc_with_emp['start_date'].notna() & (disc_with_emp['start_date'] != '')
]
print(f"  discipline after dropping no-employment rows: {len(disc_with_emp):,} rows")

# ---------------------------------------------------------------------------
# Attach demographics to discipline
# ---------------------------------------------------------------------------
disc_with_emp = disc_with_emp.merge(
    officer_data[[
        'person_nbr', 'last_name', 'first_name', 'middle_name',
        'suffix', 'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)

for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    disc_with_emp[col] = disc_with_emp[col].fillna('')

disc_with_emp['full_name'] = build_full_name_vectorized(disc_with_emp)

# Discipline agency_name: lowercase with code prefix (matching groundtruth)
disc_with_emp['agency_name'] = disc_with_emp['agency_name'].str.lower()

# case_id: keep 10-digit zero-padded format matching groundtruth (e.g. "0045701195")
disc_with_emp['case_id'] = disc_with_emp['case_id'].str.zfill(10)

# end_date: 0000-00-00 → empty string for discipline
disc_with_emp['end_date'] = disc_with_emp['end_date'].replace({'0000-00-00': ''})

# Restore None for empty optional fields
for col in ['middle_name', 'suffix']:
    disc_with_emp[col] = disc_with_emp[col].replace({'': None})

print(f"  discipline final: {len(disc_with_emp):,} rows")

DISCIPLINE_COLS = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date',
    'violation', 'violation_date', 'full_name', 'agency_name',
    'rank', 'start_date', 'end_date', 'last_name', 'first_name',
    'middle_name', 'suffix', 'year_of_birth', 'race', 'sex',
]
discipline_index = disc_with_emp[DISCIPLINE_COLS].copy()

# ---------------------------------------------------------------------------
# Validate and write output
# ---------------------------------------------------------------------------
print("Validating output...")

required_emp = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing = [c for c in required_emp if c not in employment_index.columns]
assert not missing, f"Employment index missing columns: {missing}"

empty_start = (employment_index['start_date'].isna() | (employment_index['start_date'] == '')).sum()
assert empty_start == 0, f"Employment index has {empty_start} empty start_date rows"

required_disc = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_disc = [c for c in required_disc if c not in discipline_index.columns]
assert not missing_disc, f"Discipline index missing columns: {missing_disc}"

emp_path  = os.path.join(OUTPUT_DIR, 'ga_index.csv')
disc_path = os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv')

employment_index.to_csv(emp_path, index=False)
discipline_index.to_csv(disc_path, index=False)

print(f"\nDone!")
print(f"  Employment index → {emp_path}  ({len(employment_index):,} rows)")
print(f"  Discipline index → {disc_path}  ({len(discipline_index):,} rows)")
