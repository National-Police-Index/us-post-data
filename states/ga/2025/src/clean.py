"""
Georgia POST data cleaning script.
Produces:
  - output/ga_index.csv
  - output/ga-discipline_index.csv

Run from states/ga/2025/:
  python src/clean.py --input-dir data/input --output-dir output
"""

import argparse
import os
import re
import pandas as pd


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Vectorized date helpers
# ---------------------------------------------------------------------------

def parse_start_dates(series):
    """Parse start_date/violation_date/sanction_date: 0000-00-00 and blanks → empty string."""
    s = series.astype(str).str.strip()
    bad_mask = s.isin(['', 'nan', 'NaT', 'None', '0000-00-00', '00/00/0000'])
    result = pd.to_datetime(s.where(~bad_mask), errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    result = result.where(~bad_mask, '')
    return result


def parse_end_dates(series):
    """Parse end_date: preserve 0000-00-00 as-is (groundtruth keeps it for currently employed)."""
    s = series.astype(str).str.strip()
    zero_mask = s == '0000-00-00'
    bad_mask = s.isin(['', 'nan', 'NaT', 'None', '00/00/0000'])
    result = pd.to_datetime(s.where(~bad_mask & ~zero_mask), errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    result = result.where(~bad_mask, '')
    result = result.where(~zero_mask, '0000-00-00')
    return result


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

print("Loading officer_employment.csv...")
emp = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_employment.csv"),
    dtype=str,
    keep_default_na=False,
)
print(f"  {len(emp):,} rows")

print("Loading officer_data.csv...")
odata = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_data.csv"),
    dtype=str,
    keep_default_na=False,
)
print(f"  {len(odata):,} rows")

print("Loading officer_violations.csv...")
violations = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_violations.csv"),
    dtype=str,
    keep_default_na=False,
)
print(f"  {len(violations):,} rows")

print("Loading officer_sanctions.csv...")
sanctions = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_sanctions.csv"),
    dtype=str,
    keep_default_na=False,
)
print(f"  {len(sanctions):,} rows")


# ---------------------------------------------------------------------------
# Clean officer_data (demographics)
# ---------------------------------------------------------------------------

odata = odata.rename(columns={
    'OKEY': 'person_nbr',
    'LAST NAME': 'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE': 'middle_name',
    'SUFFIX': 'suffix',
    'YOB': 'year_of_birth',
    'SEX': 'sex',
    'RACE': 'race',
})

odata['person_nbr'] = odata['person_nbr'].str.lower().str.strip()
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    odata[col] = odata[col].str.strip()
odata['year_of_birth'] = odata['year_of_birth'].str.strip()
odata = odata.drop_duplicates(subset=['person_nbr'])
print(f"officer_data: {len(odata):,} unique officers")


# ---------------------------------------------------------------------------
# Clean officer_employment
# ---------------------------------------------------------------------------

emp = emp.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'name_raw',
    'AGENCY': 'agency_name',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
})

emp['person_nbr'] = emp['person_nbr'].str.lower().str.strip()
emp['agency_name'] = emp['agency_name'].str.strip()
emp['rank'] = emp['rank'].str.strip()
emp['employment_status'] = emp['employment_status'].str.strip()

# Parse dates (vectorized)
emp['start_date'] = parse_start_dates(emp['start_date'])
emp['end_date'] = parse_end_dates(emp['end_date'])

# Drop rows with empty start_date
before = len(emp)
emp = emp[emp['start_date'] != '']
print(f"Dropped {before - len(emp):,} rows with empty start_date → {len(emp):,} remain")

# Filter non-agency values (strip code prefix for check only)
name_no_code = emp['agency_name'].str.replace(r'^[A-Z]\d+\s+', '', regex=True)
name_no_code = name_no_code.str.replace(r'\s*/.*$', '', regex=True).str.strip().str.lower()
NON_AGENCY = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
before = len(emp)
emp = emp[~name_no_code.isin(NON_AGENCY)]
print(f"Dropped {before - len(emp):,} rows with non-agency values → {len(emp):,} remain")


# ---------------------------------------------------------------------------
# Merge employment + demographics
# ---------------------------------------------------------------------------

merged = emp.merge(
    odata[['person_nbr', 'last_name', 'first_name', 'middle_name',
           'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left',
)
print(f"After merge: {len(merged):,} rows")

# Fill NaN strings
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    merged[col] = merged[col].fillna('').str.strip()


def build_full_name_series(df):
    """Build lowercase 'last, first middle suffix' full_name."""
    first = df['first_name'].str.strip()
    middle = df['middle_name'].str.strip()
    suffix = df['suffix'].str.strip()

    right = first
    right = right + middle.apply(lambda x: ' ' + x if x else '')
    right = right + suffix.apply(lambda x: ' ' + x if x else '')
    right = right.str.strip()

    last = df['last_name'].str.strip()
    full = last + right.apply(lambda x: ', ' + x if x else '')
    return full.str.lower()


merged['full_name'] = build_full_name_series(merged)

# Deduplicate
before = len(merged)
merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"Dropped {before - len(merged):,} duplicate rows → {len(merged):,} remain")


# ---------------------------------------------------------------------------
# Write employment index
# ---------------------------------------------------------------------------

EMP_COLS = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]
for col in EMP_COLS:
    if col not in merged.columns:
        merged[col] = ''

emp_index = merged[EMP_COLS].copy()

# Validate
assert (emp_index['start_date'] != '').all(), "start_date must not be empty"
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required:
    empty = (emp_index[col].isna() | (emp_index[col] == '')).sum()
    if empty > 0 and col not in ('end_date',):
        print(f"  Warning: {col} has {empty} empty values")

out_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
emp_index.to_csv(out_path, index=False)
print(f"\nWrote {len(emp_index):,} rows → {out_path}")


# ---------------------------------------------------------------------------
# Discipline index
# ---------------------------------------------------------------------------

print("\n--- Building discipline index ---")

# Rename violations
violations = violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw_v',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
})
violations['person_nbr'] = violations['person_nbr'].str.lower().str.strip()
# Strip internal spaces from case_id (e.g. '010 780707' → '010780707', matching groundtruth)
violations['case_id'] = violations['case_id'].str.replace(r'\s+', '', regex=True)
violations['violation'] = violations['violation'].str.strip()

# Rename sanctions
sanctions = sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw_s',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
})
sanctions['person_nbr'] = sanctions['person_nbr'].str.lower().str.strip()
# Strip internal spaces from case_id
sanctions['case_id'] = sanctions['case_id'].str.replace(r'\s+', '', regex=True)
sanctions['sanction'] = sanctions['sanction'].str.strip()

# Filter out 0000-00-00 dates BEFORE join (groundtruth has no such values in violation_date)
violations_valid = violations[violations['violation_date'] != '0000-00-00'].copy()
sanctions_valid = sanctions[sanctions['sanction_date'] != '0000-00-00'].copy()

# Parse dates to YYYY-MM-DD
violations_valid['violation_date'] = parse_start_dates(violations_valid['violation_date'])
sanctions_valid['sanction_date'] = parse_start_dates(sanctions_valid['sanction_date'])

# Keep only rows with valid parsed dates
violations_valid = violations_valid[violations_valid['violation_date'] != '']
sanctions_valid = sanctions_valid[sanctions_valid['sanction_date'] != '']

print(f"Violations (valid dates): {len(violations_valid):,}, Sanctions (valid dates): {len(sanctions_valid):,}")

# Inner join on case_id + person_nbr
# This produces the full cartesian product of violations × sanctions per (case, officer)
# e.g. 3 violations × 2 sanctions = 6 rows — this matches groundtruth structure
discipline = violations_valid.merge(
    sanctions_valid[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner',
)
print(f"After inner join (all violation×sanction combos): {len(discipline):,} rows")

# Deduplicate on exact (case, person, violation, sanction) to remove any true duplicates
discipline = discipline.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
print(f"After dedup on (case+person+violation+sanction): {len(discipline):,} rows")

# case_id: keep as original string with leading zeros (groundtruth format: '0045701195')


# ---------------------------------------------------------------------------
# Attach best employment context to each discipline row
# ---------------------------------------------------------------------------

# Prepare employment periods for join (use lowercase agency_name for discipline index)
emp_disc = emp[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()
emp_disc['agency_name'] = emp_disc['agency_name'].str.lower()

# Left-join discipline to all employment periods per person
disc_emp = discipline.merge(emp_disc, on='person_nbr', how='left')
print(f"After joining to employment (all periods): {len(disc_emp):,} rows")

# Score each employment period: how well does violation_date fall within start..end?
vdate = pd.to_datetime(disc_emp['violation_date'], errors='coerce')
sdate = pd.to_datetime(disc_emp['start_date'], errors='coerce')

# end_date: 0000-00-00 → use today as open-ended
edate_str = disc_emp['end_date'].replace('0000-00-00', '').replace('', pd.NaT)
edate = pd.to_datetime(edate_str, errors='coerce').fillna(pd.Timestamp.now())

within = (sdate <= vdate) & (vdate <= edate)
before_start = vdate < sdate

score = pd.Series(9999999.0, index=disc_emp.index)
# Within range = 0
score = score.where(~within, 0.0)
# Before start: distance in days
score = score.where(~(before_start & ~within), (sdate - vdate).dt.days.clip(lower=0))
# After end: distance in days
after_end = ~within & ~before_start
score = score.where(~after_end, (vdate - edate).dt.days.clip(lower=0))

disc_emp['_score'] = score

# Keep best-scoring employment period per (case_id, person_nbr, violation, sanction)
disc_emp = disc_emp.sort_values('_score')
disc_emp = disc_emp.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
disc_emp = disc_emp.drop(columns=['_score'])
print(f"After selecting best employment period: {len(disc_emp):,} rows")

# Drop rows with no employment match (empty start_date)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp['start_date'].fillna('') != '']
print(f"Dropped {before - len(disc_emp):,} rows with empty start_date (no employment match)")


# ---------------------------------------------------------------------------
# Merge demographics into discipline & build output
# ---------------------------------------------------------------------------

disc_emp = disc_emp.merge(
    odata[['person_nbr', 'last_name', 'first_name', 'middle_name',
           'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left',
)

for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    disc_emp[col] = disc_emp[col].fillna('').str.strip()

disc_emp['full_name'] = build_full_name_series(disc_emp)

# Title case for sanction and violation (matching groundtruth)
disc_emp['sanction'] = disc_emp['sanction'].str.title()
disc_emp['violation'] = disc_emp['violation'].str.title()

# Lowercase for agency/name/demographic fields (matching groundtruth)
for col in ['full_name', 'agency_name', 'rank', 'last_name', 'first_name',
            'middle_name', 'suffix', 'race', 'sex']:
    disc_emp[col] = disc_emp[col].astype(str).str.lower().str.strip()

DISC_COLS = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date', 'violation', 'violation_date',
    'full_name', 'agency_name', 'rank', 'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]
for col in DISC_COLS:
    if col not in disc_emp.columns:
        disc_emp[col] = ''

disc_index = disc_emp[DISC_COLS].copy()

# Replace nan strings with empty
disc_index = disc_index.replace({'nan': '', '<NA>': ''})

out_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
disc_index.to_csv(out_path, index=False)
print(f"\nWrote {len(disc_index):,} rows → {out_path}")

print("\nDone!")
