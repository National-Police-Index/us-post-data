"""
Georgia POST data cleaning script.
Produces:
  - output/ga_index.csv              (employment index)
  - output/ga-discipline_index.csv   (discipline index)
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

def clean_dates_vectorized(series, keep_zeros=True):
    """
    Vectorized date cleaning.
    - Strips whitespace
    - Replaces 'nan'/'NaT'/'None' with ''
    - If keep_zeros=True, preserves '0000-00-00' as-is (ground truth convention)
    - Everything else: parse as YYYY-MM-DD or return ''
    """
    s = series.astype(str).str.strip()
    if keep_zeros:
        zero_mask = s == '0000-00-00'
    else:
        zero_mask = pd.Series(False, index=s.index)

    bad_mask = s.isin(['nan', 'NaT', 'None', '0000-00-00', '']) | zero_mask
    # parse only non-bad, non-zero rows
    to_parse = s.copy()
    to_parse[bad_mask] = ''
    parsed = pd.to_datetime(to_parse, errors='coerce', format='%Y-%m-%d')
    # fallback: mixed format
    fallback_mask = to_parse.ne('') & parsed.isna()
    if fallback_mask.any():
        parsed[fallback_mask] = pd.to_datetime(to_parse[fallback_mask], errors='coerce')

    result = parsed.dt.strftime('%Y-%m-%d').fillna('')
    if keep_zeros:
        result[zero_mask] = '0000-00-00'
    return result


def build_full_name_series(df):
    """Build 'last, first [middle] [suffix]' in lowercase from a DataFrame."""
    last  = df['last_name'].fillna('').str.strip()
    first = df['first_name'].fillna('').str.strip()
    mid   = df['middle_name'].fillna('').str.strip()
    suf   = df['suffix'].fillna('').str.strip()

    name = last + ', ' + first
    has_mid = mid != ''
    name = name + mid.where(~has_mid, ' ' + mid)
    # fix: only prepend space when middle exists
    name = last + ', ' + first
    name[has_mid] = name[has_mid] + ' ' + mid[has_mid]
    has_suf = suf != ''
    name[has_suf] = name[has_suf] + ' ' + suf[has_suf]
    return name.str.lower()


def agency_is_valid(name_series):
    """Returns boolean mask — True = real agency."""
    NON_AGENCY = {
        'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
    }
    s = name_series.fillna('').astype(str)
    # Strip leading code and trailing slash fragment for the check only
    cleaned = s.str.replace(r'^[A-Z]\d+\s+', '', regex=True)
    cleaned = cleaned.str.replace(r'/.*$', '', regex=True).str.strip().str.lower()
    return ~cleaned.isin(NON_AGENCY)


# ---------------------------------------------------------------------------
# Step 1: Load raw files
# ---------------------------------------------------------------------------
print("Loading raw files...")

emp      = pd.read_csv(os.path.join(INPUT_DIR, 'officer_employment.csv'), dtype=str)
officers = pd.read_csv(os.path.join(INPUT_DIR, 'officer_data.csv'), dtype=str)
violations = pd.read_csv(os.path.join(INPUT_DIR, 'officer_violations.csv'), dtype=str)
sanctions  = pd.read_csv(os.path.join(INPUT_DIR, 'officer_sanctions.csv'), dtype=str)

print(f"  Employment rows: {len(emp)}")
print(f"  Officers rows:   {len(officers)}")
print(f"  Violations rows: {len(violations)}")
print(f"  Sanctions rows:  {len(sanctions)}")

# ---------------------------------------------------------------------------
# Step 2: Clean officer demographics
# ---------------------------------------------------------------------------
officers = officers.rename(columns={
    'OKEY':       'person_nbr',
    'LAST NAME':  'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE':     'middle_name',
    'SUFFIX':     'suffix',
    'YOB':        'year_of_birth',
    'SEX':        'sex',
    'RACE':       'race',
})
officers['person_nbr'] = officers['person_nbr'].astype(str).str.strip().str.lower()
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officers[col] = officers[col].astype(str).str.strip().replace('nan', '')

# ---------------------------------------------------------------------------
# Step 3: Clean employment data
# ---------------------------------------------------------------------------
emp = emp.rename(columns={
    'OKEY':       'person_nbr',
    'NAME':       'full_name_raw',
    'AGENCY':     'agency_name',
    'RANK':       'rank',
    'STATUS':     'employment_status',
    'START DATE': 'start_date',
    'END DATE':   'end_date',
})

emp['person_nbr'] = emp['person_nbr'].astype(str).str.strip().str.lower()
emp['start_date'] = clean_dates_vectorized(emp['start_date'], keep_zeros=False)
emp['end_date']   = clean_dates_vectorized(emp['end_date'],   keep_zeros=True)

# Drop rows with empty start_date
before = len(emp)
emp = emp[emp['start_date'] != '']
print(f"Dropped {before - len(emp)} rows with empty start_date")

# Filter out non-agency rows
before = len(emp)
emp = emp[agency_is_valid(emp['agency_name'])]
print(f"Dropped {before - len(emp)} rows with non-agency values")

# ---------------------------------------------------------------------------
# Step 4: Merge employment + demographics
# ---------------------------------------------------------------------------
merged = emp.merge(
    officers[['person_nbr', 'last_name', 'first_name', 'middle_name',
              'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Fill NaN string columns after merge
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    merged[col] = merged[col].fillna('')

# Build full_name
merged['full_name'] = build_full_name_series(merged)

print(f"Merged employment rows: {len(merged)}")

# ---------------------------------------------------------------------------
# Step 5: Deduplicate employment index
# ---------------------------------------------------------------------------
before = len(merged)
merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"Dropped {before - len(merged)} duplicate employment rows")

# ---------------------------------------------------------------------------
# Step 6: Select and order columns for employment index
# ---------------------------------------------------------------------------
EMP_COLS = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]
employment_index = merged[EMP_COLS].copy()

# Replace empty strings with NaN for middle_name/suffix (match ground truth NaN)
employment_index['middle_name'] = employment_index['middle_name'].replace('', float('nan'))
employment_index['suffix']      = employment_index['suffix'].replace('', float('nan'))

print(f"\nEmployment index shape: {employment_index.shape}")

# ---------------------------------------------------------------------------
# Step 7: Build discipline index
# ---------------------------------------------------------------------------
print("\nBuilding discipline index...")

violations = violations.rename(columns={
    'CASE':           'case_id',
    'OKEY':           'person_nbr',
    'NAME':           'name_raw',
    'VIOLATION':      'violation',
    'VIOLATION DATE': 'violation_date',
})
violations['person_nbr']    = violations['person_nbr'].astype(str).str.strip().str.lower()
violations['case_id']       = violations['case_id'].astype(str).str.strip()
violations['violation_date'] = clean_dates_vectorized(violations['violation_date'], keep_zeros=False)

sanctions = sanctions.rename(columns={
    'CASE':     'case_id',
    'OKEY':     'person_nbr',
    'NAME':     'name_raw',
    'SANCTION': 'sanction',
    'DATE':     'sanction_date',
})
sanctions['person_nbr']   = sanctions['person_nbr'].astype(str).str.strip().str.lower()
sanctions['case_id']      = sanctions['case_id'].astype(str).str.strip()
sanctions['sanction_date'] = clean_dates_vectorized(sanctions['sanction_date'], keep_zeros=False)

print(f"  Violations: {len(violations)}, Sanctions: {len(sanctions)}")

# Cartesian join: all violations x all sanctions per (case_id, person_nbr)
# This matches the ground truth structure (one row per violation+sanction combo)
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner'
)
print(f"  After cartesian inner join: {len(discipline)}")

# Dedup on (case_id, person_nbr, violation, sanction) - matches GT convention
discipline = discipline.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
print(f"  After dedup (case+person+violation+sanction): {len(discipline)}")

# ---------------------------------------------------------------------------
# Step 8: Load investigations to get incident agency context
# ---------------------------------------------------------------------------
investigations = pd.read_csv(os.path.join(INPUT_DIR, 'officer_investigations.csv'), dtype=str)
investigations = investigations.rename(columns={
    'CASE':        'case_id',
    'OKEY':        'person_nbr',
    'NAME':        'name_raw',
    'AGENCY':      'inv_agency',
    'DATE OPENED': 'date_opened',
})
investigations['person_nbr'] = investigations['person_nbr'].astype(str).str.strip().str.lower()
investigations['case_id']    = investigations['case_id'].astype(str).str.strip()
investigations['inv_agency_lower'] = investigations['inv_agency'].str.lower()
print(f"  Investigations: {len(investigations)}")

# Keep one investigation row per (case_id, person_nbr)
investigations = investigations.drop_duplicates(subset=['case_id', 'person_nbr'])

# ---------------------------------------------------------------------------
# Step 9: Attach employment context via investigations agency
# ---------------------------------------------------------------------------
# employment with lowercase agency for matching
emp_for_disc = emp[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()
emp_for_disc['agency_lower'] = emp_for_disc['agency_name'].str.lower()

# Join investigations to employment on person_nbr + agency
inv_emp = investigations.merge(
    emp_for_disc[['person_nbr', 'agency_lower', 'rank', 'start_date', 'end_date']],
    left_on=['person_nbr', 'inv_agency_lower'],
    right_on=['person_nbr', 'agency_lower'],
    how='inner'
)
# Use inv_agency_lower as agency_name (matches GT lowercase format)
inv_emp = inv_emp.rename(columns={'inv_agency_lower': 'agency_name_disc'})
inv_emp = inv_emp.drop_duplicates(subset=['case_id', 'person_nbr'])
print(f"  Investigations+employment context rows: {len(inv_emp)}")

# Join discipline records to investigation employment context
discipline = discipline.merge(
    inv_emp[['case_id', 'person_nbr', 'agency_name_disc', 'rank', 'start_date', 'end_date']],
    on=['case_id', 'person_nbr'],
    how='inner'  # only keep discipline rows where we have employment context
)
discipline = discipline.rename(columns={'agency_name_disc': 'agency_name'})
print(f"  After discipline+inv_emp join: {len(discipline)}")

# Drop rows with no employment (empty start_date)
before = len(discipline)
discipline = discipline[discipline['start_date'].fillna('') != '']
print(f"  After dropping no-employment rows: {len(discipline)} (removed {before - len(discipline)})")

# ---------------------------------------------------------------------------
# Step 10: Attach officer demographics to discipline records
# ---------------------------------------------------------------------------
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officers[col] = officers[col].fillna('').astype(str)

discipline = discipline.merge(
    officers[['person_nbr', 'last_name', 'first_name', 'middle_name',
              'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    discipline[col] = discipline[col].fillna('')

discipline['full_name'] = build_full_name_series(discipline)

# Convert case_id to integer string (strip leading zeros, matches ground truth int format)
discipline['case_id'] = pd.to_numeric(discipline['case_id'], errors='coerce').astype('Int64')

# ---------------------------------------------------------------------------
# Step 11: Select discipline columns
# ---------------------------------------------------------------------------
DISC_COLS = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date',
    'violation', 'violation_date',
    'full_name', 'agency_name', 'rank', 'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]
discipline_index = discipline[DISC_COLS].copy()

# Replace empty strings with NaN for sparsely populated columns
discipline_index['middle_name'] = discipline_index['middle_name'].replace('', float('nan'))
discipline_index['suffix']      = discipline_index['suffix'].replace('', float('nan'))

print(f"\nDiscipline index shape: {discipline_index.shape}")

# ---------------------------------------------------------------------------
# Step 12: Write output
# ---------------------------------------------------------------------------
emp_out  = os.path.join(OUTPUT_DIR, 'ga_index.csv')
disc_out = os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv')

employment_index.to_csv(emp_out, index=False)
discipline_index.to_csv(disc_out, index=False)

print(f"\nWrote {len(employment_index)} rows to {emp_out}")
print(f"Wrote {len(discipline_index)} rows to {disc_out}")
print("Done.")
