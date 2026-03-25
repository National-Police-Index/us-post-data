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

def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None', '0000-00-00', '00/00/0000'):
        return ''
    try:
        parsed = pd.to_datetime(s, errors='coerce')
        if pd.isna(parsed):
            return ''
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return ''


def build_full_name(last, first, middle, suffix):
    """Build full_name as 'last, first middle suffix' in lowercase."""
    parts = [str(first).strip()]
    if str(middle).strip() and str(middle).strip().lower() not in ('nan', ''):
        parts.append(str(middle).strip())
    name = str(last).strip() + ', ' + ' '.join(parts)
    if str(suffix).strip() and str(suffix).strip().lower() not in ('nan', ''):
        name += ' ' + str(suffix).strip()
    return name.lower()


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

investigations = pd.read_csv(
    os.path.join(INPUT_DIR, 'officer_investigations.csv'),
    dtype=str,
    keep_default_na=False,
)

print(f"  employment rows: {len(employment)}")
print(f"  officer_data rows: {len(officer_data)}")
print(f"  violations rows: {len(violations)}")
print(f"  sanctions rows: {len(sanctions)}")
print(f"  investigations rows: {len(investigations)}")


# ---------------------------------------------------------------------------
# Clean employment data
# ---------------------------------------------------------------------------

print("Cleaning employment data...")

# Rename columns
employment.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'full_name_raw',
    'AGENCY': 'agency_name',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
}, inplace=True)

# Clean person_nbr: lowercase, strip whitespace
employment['person_nbr'] = employment['person_nbr'].str.lower().str.strip()

# Clean dates
# NOTE: groundtruth keeps 0000-00-00 as-is for end_date; start_date must be valid
employment['start_date'] = employment['start_date'].apply(safe_date)
# For end_date: keep 0000-00-00 as-is (groundtruth shows this value)
employment['end_date'] = employment['end_date'].apply(
    lambda v: '' if str(v).strip() in ('nan', 'NaT', 'None') else str(v).strip()
)

# Drop rows with empty start_date
n_before = len(employment)
employment = employment[employment['start_date'] != '']
print(f"  Dropped {n_before - len(employment)} rows with empty start_date")

# agency_name: keep as-is from source (groundtruth shows code prefix e.g. "G1720 DEKALB...")
# Filter out known non-agency values
NON_AGENCY = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
employment = employment[~employment['agency_name'].str.strip().str.lower().isin(NON_AGENCY)]

print(f"  Employment rows after cleaning: {len(employment)}")


# ---------------------------------------------------------------------------
# Clean officer demographics
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

# Clean name fields
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer_data[col] = officer_data[col].str.strip()


# ---------------------------------------------------------------------------
# Build employment index
# ---------------------------------------------------------------------------

print("Merging employment + demographics...")

emp = employment.merge(
    officer_data[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Build full_name: "last, first middle suffix" lowercase
emp['full_name'] = emp.apply(
    lambda r: build_full_name(r['last_name'], r['first_name'], r['middle_name'], r['suffix']),
    axis=1
)

# Deduplicate on (person_nbr, agency_name, start_date)
dupe_mask = emp.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
if dupe_mask.any():
    print(f"  Dropping {dupe_mask.sum()} duplicate employment rows")
    emp = emp.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

print(f"  Employment index rows: {len(emp)}")

# Select and order columns
emp_out = emp[[
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex'
]]

# Write employment index
emp_path = os.path.join(OUTPUT_DIR, 'ga_index.csv')
emp_out.to_csv(emp_path, index=False)
print(f"  Wrote {emp_path} ({len(emp_out)} rows)")


# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------

print("Building discipline index...")

# Rename violations columns
violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
}, inplace=True)
violations['person_nbr'] = violations['person_nbr'].str.lower().str.strip()
violations['case_id'] = violations['case_id'].str.strip()

# Clean violation_date
violations['violation_date'] = violations['violation_date'].apply(safe_date)

# Rename sanctions columns
sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw_s',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
}, inplace=True)
sanctions['person_nbr'] = sanctions['person_nbr'].str.lower().str.strip()
sanctions['case_id'] = sanctions['case_id'].str.strip()
sanctions['sanction_date'] = sanctions['sanction_date'].apply(safe_date)

# Rename investigations columns (used for agency_name in discipline)
investigations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'name_raw_i',
    'AGENCY': 'disc_agency_name',
    'DATE OPENED': 'date_opened',
}, inplace=True)
investigations['person_nbr'] = investigations['person_nbr'].str.lower().str.strip()
investigations['case_id'] = investigations['case_id'].str.strip()

# Normalize case_id: strip spaces (raw has e.g. "010 780707" → "010780707")
for df in [violations, sanctions, investigations]:
    df['case_id'] = df['case_id'].str.replace(r'\s', '', regex=True)

# Drop violations with empty/invalid violation_date (GT excludes 0000-00-00)
# safe_date() already converted 0000-00-00 to empty string
n_viol_before = len(violations)
violations = violations[violations['violation_date'] != ''].copy()
print(f"  Dropped {n_viol_before - len(violations)} violations with empty/invalid violation_date")

# Inner join violations + sanctions on case_id ONLY (cartesian product per case)
disc = violations.merge(
    sanctions[['case_id', 'sanction', 'sanction_date']],
    on='case_id',
    how='inner'
)

print(f"  After viol+sanc inner join (case_id only): {len(disc)} rows")

# Drop full duplicates
disc = disc.drop_duplicates().reset_index(drop=True)
print(f"  After drop_duplicates: {len(disc)} rows")

# Attach agency from investigations (one per case+person)
inv_dedup = (
    investigations[['case_id', 'person_nbr', 'disc_agency_name']]
    .drop_duplicates(subset=['case_id', 'person_nbr'])
)
disc = disc.merge(
    inv_dedup[['case_id', 'person_nbr', 'disc_agency_name']],
    on=['case_id', 'person_nbr'],
    how='left'
)

# Keep case_id as string (groundtruth uses zero-padded strings like '0045701195')
# case_id is already a string from dtype=str loading

# disc_agency_name: lowercase to match groundtruth
disc['disc_agency_name'] = disc['disc_agency_name'].str.lower().str.strip()
# Replace empty/missing with empty string
disc['disc_agency_name'] = disc['disc_agency_name'].fillna('')


# ---------------------------------------------------------------------------
# Join discipline to ALL matching employment periods
# ---------------------------------------------------------------------------

# The groundtruth keeps every employment period where violation_date
# falls within [start_date, end_date] (inclusive). This is a left-join on
# person_nbr followed by a date range filter.

# Build employment lookup with parsed start/end dates
emp_lookup = emp[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()
emp_lookup['start_dt'] = pd.to_datetime(emp_lookup['start_date'], errors='coerce')
emp_lookup['end_dt'] = pd.to_datetime(
    emp_lookup['end_date'].replace({'0000-00-00': pd.NaT}),
    errors='coerce'
)
# Agency name in discipline index = employment agency_name lowercased
emp_lookup['agency_name_lower'] = emp_lookup['agency_name'].str.lower()

# Parse violation_date
disc['viol_dt'] = pd.to_datetime(disc['violation_date'], errors='coerce')

print("  Joining discipline to all matching employment periods...")

# Cross-join discipline to all employment periods for each person (left join)
disc_emp = disc.merge(
    emp_lookup[['person_nbr', 'agency_name_lower', 'rank', 'start_date', 'end_date',
                'start_dt', 'end_dt']],
    on='person_nbr',
    how='left'
)

print(f"  After left join to employment: {len(disc_emp)} rows")

# Filter: keep only rows where violation_date is within [start_dt, end_dt]
# For open-ended employment (end_dt NaT): keep if viol_dt >= start_dt
mask_valid = disc_emp['viol_dt'].notna() & disc_emp['start_dt'].notna()
within = (
    disc_emp['start_dt'] <= disc_emp['viol_dt']
) & (
    disc_emp['end_dt'].isna() | (disc_emp['viol_dt'] <= disc_emp['end_dt'])
)

# Keep rows that pass the date filter
disc_best = disc_emp[mask_valid & within].copy()
disc_best['agency_name'] = disc_best['agency_name_lower']

print(f"  After date-range filter: {len(disc_best)} rows")

# Drop rows with empty start_date
n_before = len(disc_best)
disc_best = disc_best[disc_best['start_date'].fillna('') != '']
print(f"  Dropped {n_before - len(disc_best)} rows with no employment match (empty start_date)")

# ---------------------------------------------------------------------------
# Merge demographics into discipline index
# ---------------------------------------------------------------------------

disc_best = disc_best.merge(
    officer_data[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Build full_name for discipline (lowercase)
disc_best['full_name'] = disc_best.apply(
    lambda r: build_full_name(r['last_name'], r['first_name'], r['middle_name'], r['suffix']),
    axis=1
)

# Lowercase names, violation, sanction to match groundtruth
disc_best['last_name'] = disc_best['last_name'].str.lower().str.strip()
disc_best['first_name'] = disc_best['first_name'].str.lower().str.strip()
disc_best['middle_name'] = disc_best['middle_name'].str.lower().str.strip()
disc_best['suffix'] = disc_best['suffix'].str.lower().str.strip()
disc_best['race'] = disc_best['race'].str.lower().str.strip()
disc_best['sex'] = disc_best['sex'].str.lower().str.strip()
disc_best['rank'] = disc_best['rank'].str.lower().str.strip()

# Title-case violation and sanction (groundtruth shows Title Case)
disc_best['violation'] = disc_best['violation'].str.title()
disc_best['sanction'] = disc_best['sanction'].str.title()

# Select and order columns for discipline index
disc_out = disc_best[[
    'case_id', 'person_nbr', 'sanction', 'sanction_date',
    'violation', 'violation_date',
    'full_name', 'agency_name', 'rank',
    'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex'
]]

# Write discipline index
disc_path = os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv')
disc_out.to_csv(disc_path, index=False)
print(f"  Wrote {disc_path} ({len(disc_out)} rows)")

print("\nDone.")

