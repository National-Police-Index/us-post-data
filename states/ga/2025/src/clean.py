"""
Georgia POST data cleaning script.
Produces:
  - output/ga_index.csv
  - output/ga-discipline_index.csv
"""
import argparse
import os
import re

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean Georgia POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Vectorized date cleaning helpers
# ---------------------------------------------------------------------------

def clean_date_col(series, keep_zeros=False):
    """
    Clean a date column vectorized.
    If keep_zeros=True, keep '0000-00-00' as-is (for end_date, matching groundtruth).
    Otherwise treat as empty string.
    """
    s = series.astype(str).str.strip()
    invalid = s.isin(['nan', 'NaT', 'None', '', '00/00/0000'])
    result = pd.to_datetime(s, errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    # Rows that couldn't be parsed are already '' from fillna
    # Restore '0000-00-00' if keep_zeros
    if keep_zeros:
        zero_mask = (series.astype(str).str.strip() == '0000-00-00')
        result = result.where(~zero_mask, '0000-00-00')
    # Explicit invalids get ''
    result = result.where(~invalid, '')
    return result


def safe_date_series(series):
    """Convert date series — invalid/missing become empty string."""
    return clean_date_col(series, keep_zeros=False)


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------
print("Loading data files...")

emp_df = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_employment.csv'),
    dtype=str,
    keep_default_na=False,
)

officer_df = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_data.csv'),
    dtype=str,
    keep_default_na=False,
)

violations_df = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_violations.csv'),
    dtype=str,
    keep_default_na=False,
)

sanctions_df = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_sanctions.csv'),
    dtype=str,
    keep_default_na=False,
)

print(f"  employment: {len(emp_df)} rows")
print(f"  officer_data: {len(officer_df)} rows")
print(f"  violations: {len(violations_df)} rows")
print(f"  sanctions: {len(sanctions_df)} rows")


# ===========================================================================
# EMPLOYMENT INDEX
# ===========================================================================

# ---------------------------------------------------------------------------
# Clean officer demographics
# ---------------------------------------------------------------------------
officer_df.rename(columns={
    'OKEY': 'person_nbr',
    'LAST NAME': 'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE': 'middle_name',
    'SUFFIX': 'suffix',
    'YOB': 'year_of_birth',
    'SEX': 'sex',
    'RACE': 'race',
}, inplace=True)

officer_df['person_nbr'] = officer_df['person_nbr'].str.strip().str.lower()
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer_df[col] = officer_df[col].str.strip()

# ---------------------------------------------------------------------------
# Clean employment
# ---------------------------------------------------------------------------
emp_df.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'raw_name',
    'AGENCY': 'agency_name',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
}, inplace=True)

emp_df['person_nbr'] = emp_df['person_nbr'].str.strip().str.lower()
emp_df['rank'] = emp_df['rank'].str.strip()
emp_df['employment_status'] = emp_df['employment_status'].str.strip()

# Keep agency_name as-is (groundtruth keeps codes + slash fragments)
# Only filter out obvious non-agency strings

# Date cleaning
# start_date: invalid → '' (rows with empty start_date will be dropped)
emp_df['start_date'] = safe_date_series(emp_df['start_date'])
# end_date: keep '0000-00-00' as-is (matches groundtruth), other invalid → ''
emp_df['end_date'] = clean_date_col(emp_df['end_date'], keep_zeros=True)

# Drop rows with empty start_date
before = len(emp_df)
emp_df = emp_df[emp_df['start_date'] != ''].copy()
print(f"Dropped {before - len(emp_df)} rows with empty start_date; {len(emp_df)} remain")

# Filter non-agency rows
def get_base_name(agency_series):
    """Strip code prefix and slash fragment for filter check."""
    s = agency_series.str.strip()
    s = s.str.replace(r'^[A-Z]\d+\s+', '', regex=True)
    s = s.str.replace(r'\s*/.*$', '', regex=True)
    return s.str.strip().str.lower()

NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}
base_names = get_base_name(emp_df['agency_name'])
before = len(emp_df)
emp_df = emp_df[~base_names.isin(NON_AGENCY_VALUES)].copy()
print(f"Dropped {before - len(emp_df)} non-agency rows; {len(emp_df)} remain")

# ---------------------------------------------------------------------------
# Merge employment + demographics
# ---------------------------------------------------------------------------
merged = emp_df.merge(
    officer_df[[
        'person_nbr', 'last_name', 'first_name', 'middle_name',
        'suffix', 'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)
print(f"After merge: {len(merged)} rows")

# Fill NaN strings with empty string
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    merged[col] = merged[col].fillna('').str.strip()

# Build full_name: "last_name, first_name [middle_name] [suffix]" lowercase
fn_parts = merged['first_name'].str.strip()
mn_parts = merged['middle_name'].str.strip()
# Combine first + middle
first_mid = fn_parts.where(mn_parts == '', fn_parts + ' ' + mn_parts)
first_mid = first_mid.where(fn_parts != '', mn_parts)  # handle missing first
# Combine last + first_mid
full = merged['last_name'].str.strip() + ', ' + first_mid
# Append suffix if present
suf = merged['suffix'].str.strip()
full = full.where(suf == '', full + ' ' + suf)
merged['full_name'] = full.str.lower()

# Drop duplicates
dupe_mask = merged.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
if dupe_mask.any():
    print(f"Dropping {dupe_mask.sum()} duplicate rows")
    merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

# ---------------------------------------------------------------------------
# Write employment index
# ---------------------------------------------------------------------------
employment_cols = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex',
]
employment_out = merged[employment_cols].copy()
print(f"Employment index: {len(employment_out)} rows")
employment_out.to_csv(os.path.join(OUTPUT_DIR, 'ga_index.csv'), index=False)
print("Wrote ga_index.csv")


# ===========================================================================
# DISCIPLINE INDEX
# ===========================================================================
# Approach:
#   1. Cross join violations x sanctions on case_id (all v x s combos per case)
#   2. Inner join with employment on person_nbr
#   3. For each (case_id, person_nbr, violation, sanction), keep best employment period
#   4. Drop rows with no employment match
#   5. Lowercase names/agency/rank to match groundtruth discipline format

# ---------------------------------------------------------------------------
# Clean violations
# ---------------------------------------------------------------------------
violations_df.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'raw_name_v',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
}, inplace=True)

violations_df['person_nbr'] = violations_df['person_nbr'].str.strip().str.lower()
violations_df['case_id'] = violations_df['case_id'].str.strip()
violations_df['violation'] = violations_df['violation'].str.strip().str.title()
violations_df['violation_date'] = safe_date_series(violations_df['violation_date'])

# ---------------------------------------------------------------------------
# Clean sanctions
# ---------------------------------------------------------------------------
sanctions_df.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'raw_name_s',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
}, inplace=True)

sanctions_df['person_nbr'] = sanctions_df['person_nbr'].str.strip().str.lower()
sanctions_df['case_id'] = sanctions_df['case_id'].str.strip()
sanctions_df['sanction'] = sanctions_df['sanction'].str.strip().str.title()
sanctions_df['sanction_date'] = safe_date_series(sanctions_df['sanction_date'])

# ---------------------------------------------------------------------------
# Cross join violations x sanctions on case_id (all combos per case)
# ---------------------------------------------------------------------------
discipline = violations_df[['case_id', 'person_nbr', 'violation', 'violation_date']].merge(
    sanctions_df[['case_id', 'sanction', 'sanction_date']],
    on='case_id',
    how='inner',
)
print(f"After violations x sanctions cross join on case_id: {len(discipline)} rows")

# ---------------------------------------------------------------------------
# Attach employment context (inner join to get officers with employment records)
# ---------------------------------------------------------------------------
# Use the raw employment data (pre-merged) for discipline context
emp_for_disc = emp_df[[
    'person_nbr', 'agency_name', 'rank', 'start_date', 'end_date',
]].copy()
# Also join demographics
emp_for_disc = emp_for_disc.merge(
    officer_df[[
        'person_nbr', 'last_name', 'first_name', 'middle_name',
        'suffix', 'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    emp_for_disc[col] = emp_for_disc[col].fillna('').str.strip()

# Rebuild full_name (lowercased for discipline index)
fn2 = emp_for_disc['first_name'].str.strip()
mn2 = emp_for_disc['middle_name'].str.strip()
fm2 = fn2.where(mn2 == '', fn2 + ' ' + mn2)
fm2 = fm2.where(fn2 != '', mn2)
full2 = emp_for_disc['last_name'].str.strip() + ', ' + fm2
suf2 = emp_for_disc['suffix'].str.strip()
full2 = full2.where(suf2 == '', full2 + ' ' + suf2)
emp_for_disc['full_name'] = full2.str.lower()

# Join discipline to employment (inner join - only officers with employment)
disc_with_emp = discipline.merge(emp_for_disc, on='person_nbr', how='inner')
print(f"After discipline+employment inner join: {len(disc_with_emp)} rows")

# ---------------------------------------------------------------------------
# Score employment periods: pick best per (case_id, person_nbr, violation, sanction)
# ---------------------------------------------------------------------------
vd = pd.to_datetime(disc_with_emp['violation_date'], errors='coerce')
sd = pd.to_datetime(disc_with_emp['start_date'], errors='coerce')
ed_raw = disc_with_emp['end_date'].copy()
ed = pd.to_datetime(
    ed_raw.where(~ed_raw.isin(['0000-00-00', '']), '2099-12-31'),
    errors='coerce'
)

before_sd = (vd < sd)
after_ed = (vd > ed)
score = pd.Series(0.0, index=disc_with_emp.index)
score = score.where(~before_sd, (sd - vd).dt.days)
score = score.where(~after_ed, (vd - ed).dt.days)
score = score.where(sd.notna() & vd.notna(), 9999.0)
disc_with_emp['_score'] = score

# Keep best employment period per (case_id, person_nbr, violation, sanction)
disc_with_emp = (
    disc_with_emp.sort_values('_score', ascending=True)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
    .reset_index(drop=True)
)
print(f"After picking best employment period: {len(disc_with_emp)} rows")

# Drop rows with no employment start_date
before = len(disc_with_emp)
disc_with_emp = disc_with_emp[disc_with_emp['start_date'].fillna('') != ''].copy()
print(f"Dropped {before - len(disc_with_emp)} with no employment; {len(disc_with_emp)} remain")

disc_with_emp.drop(columns=['_score'], inplace=True)

# ---------------------------------------------------------------------------
# Lowercase all string fields (matches groundtruth discipline format)
# ---------------------------------------------------------------------------
for col in ['agency_name', 'rank', 'last_name', 'first_name', 'middle_name', 'suffix', 'race', 'sex']:
    disc_with_emp[col] = disc_with_emp[col].str.lower()

# Keep case_id as zero-padded string (matches groundtruth format: '0045701195')
# Already stripped, just ensure 10-char zero-padding where applicable
disc_with_emp['case_id'] = disc_with_emp['case_id'].str.zfill(10)

# ---------------------------------------------------------------------------
# Write discipline index
# ---------------------------------------------------------------------------
disc_cols = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date', 'violation',
    'violation_date', 'full_name', 'agency_name', 'rank', 'start_date',
    'end_date', 'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]
discipline_out = disc_with_emp[disc_cols].copy()
print(f"Discipline index: {len(discipline_out)} rows")
discipline_out.to_csv(os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv'), index=False)
print("Wrote ga-discipline_index.csv")
print("Done.")
