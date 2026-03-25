#!/usr/bin/env python3
"""
Georgia POST data cleaning script.
Produces:
  - output/georgia_index.csv       (employment index)
  - output/georgia-discipline_index.csv  (discipline index)
"""

import argparse
import os
import re
import pandas as pd

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean Georgia POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------
print("Loading raw files...")

employment = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_employment.csv"),
    dtype=str,
)
officer_data = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_data.csv"),
    dtype=str,
)
agency_data = pd.read_csv(
    os.path.join(INPUT_DIR, "agency_data.csv"),
    dtype=str,
)
violations = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_violations.csv"),
    dtype=str,
)
sanctions = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_sanctions.csv"),
    dtype=str,
)

print(f"  employment rows: {len(employment)}")
print(f"  officer_data rows: {len(officer_data)}")
print(f"  agency_data rows: {len(agency_data)}")
print(f"  violations rows: {len(violations)}")
print(f"  sanctions rows: {len(sanctions)}")

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def clean_dates_vectorized(series):
    """Vectorized date cleaning: returns YYYY-MM-DD, '0000-00-00', or ''."""
    s = series.astype(str).str.strip()
    invalid = s.isin(['nan', 'NaT', 'None', '', 'NaN'])
    zero_date = s == '0000-00-00'
    valid = ~invalid & ~zero_date
    result = pd.Series('', index=s.index)
    result[zero_date] = '0000-00-00'
    if valid.any():
        parsed = pd.to_datetime(s[valid], errors='coerce')
        result[valid] = parsed.dt.strftime('%Y-%m-%d').fillna('')
    return result


def safe_date(val):
    """Single-value date cleaning (used for small series only)."""
    s = str(val).strip() if val is not None else ''
    if not s or s in ('nan', 'NaT', 'None', ''):
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


def clean_person_nbr(val):
    """Lowercase and strip the officer key."""
    return str(val).strip().lower()


def build_full_name(last, first, middle, suffix):
    """Build full_name in 'last, first middle suffix' format (lowercase)."""
    parts = [str(first).strip()]
    if middle and str(middle).strip() and str(middle).strip().lower() not in ('nan', 'none', ''):
        parts.append(str(middle).strip())
    if suffix and str(suffix).strip() and str(suffix).strip().lower() not in ('nan', 'none', ''):
        parts.append(str(suffix).strip())
    name = str(last).strip() + ', ' + ' '.join(parts)
    return name.lower()


# ---------------------------------------------------------------------------
# Clean officer demographics
# ---------------------------------------------------------------------------
print("Cleaning officer demographics...")

officer_data = officer_data.rename(columns={
    'OKEY': 'person_nbr',
    'LAST NAME': 'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE': 'middle_name',
    'SUFFIX': 'suffix',
    'YOB': 'year_of_birth',
    'SEX': 'sex',
    'RACE': 'race',
})

officer_data['person_nbr'] = officer_data['person_nbr'].apply(clean_person_nbr)

# Clean name fields — strip whitespace, keep original case from source
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer_data[col] = officer_data[col].astype(str).str.strip()
    officer_data[col] = officer_data[col].apply(
        lambda x: '' if x.lower() in ('nan', 'none') else x
    )

# Lowercase name fields to match groundtruth format
officer_data['last_name'] = officer_data['last_name'].str.lower()
officer_data['first_name'] = officer_data['first_name'].str.lower()
officer_data['middle_name'] = officer_data['middle_name'].str.lower()
officer_data['suffix'] = officer_data['suffix'].str.lower()

# year_of_birth: keep as string
officer_data['year_of_birth'] = officer_data['year_of_birth'].apply(
    lambda x: str(int(float(x))) if x not in ('nan', 'none', '', 'NaN') else ''
)

# Deduplicate officer demographics on person_nbr (keep first)
officer_data = officer_data.drop_duplicates(subset=['person_nbr'], keep='first')

print(f"  Unique officers in demographics: {len(officer_data)}")


# ---------------------------------------------------------------------------
# Clean employment data
# ---------------------------------------------------------------------------
print("Cleaning employment data...")

employment = employment.rename(columns={
    'OKEY': 'person_nbr',
    'NAME': 'raw_name',
    'AGENCY': 'agency_name',
    'RANK': 'rank',
    'STATUS': 'employment_status',
    'START DATE': 'start_date',
    'END DATE': 'end_date',
})

employment['person_nbr'] = employment['person_nbr'].apply(clean_person_nbr)

# Date cleaning — keep 0000-00-00 for end_date (means currently employed)
employment['start_date'] = clean_dates_vectorized(employment['start_date'])
employment['end_date'] = clean_dates_vectorized(employment['end_date'])

# Drop rows with unparseable start_date (returns '' after cleaning)
# NOTE: 0000-00-00 start_dates are kept (groundtruth retains them)
before = len(employment)
employment = employment[employment['start_date'].fillna('') != '']
print(f"  Dropped {before - len(employment)} rows with unparseable start_date")

# agency_name: keep the full raw string from officer_employment.csv
# (groundtruth shows agency_name = "G1720 DEKALB COUNTY POLICE DEPARTMENT")
employment['agency_name'] = employment['agency_name'].astype(str).str.strip()

print(f"  Employment rows after cleaning: {len(employment)}")


# ---------------------------------------------------------------------------
# Merge employment + officer demographics
# ---------------------------------------------------------------------------
print("Merging employment + demographics...")

merged = employment.merge(
    officer_data[[
        'person_nbr', 'last_name', 'first_name', 'middle_name', 'suffix',
        'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)

# Build full_name
merged['full_name'] = merged.apply(
    lambda r: build_full_name(r['last_name'], r['first_name'], r['middle_name'], r['suffix']),
    axis=1
)

# Note: groundtruth keeps duplicate rows (person_nbr, agency_name, start_date)
dupes = merged.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
if dupes:
    print(f"  Note: {dupes} duplicate rows found (keeping per groundtruth behavior)")

print(f"  Merged employment rows: {len(merged)}")

# ---------------------------------------------------------------------------
# Build employment index output
# ---------------------------------------------------------------------------
INDEX_COLS = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]

# Ensure all columns exist
for col in INDEX_COLS:
    if col not in merged.columns:
        merged[col] = ''

ga_index = merged[INDEX_COLS].copy()

# Validate required columns
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required:
    empty_count = (ga_index[col].isna() | (ga_index[col] == '')).sum()
    if empty_count > 0:
        print(f"  Warning: {col} has {empty_count} empty values")

# Note: 0000-00-00 start_dates are retained (groundtruth keeps them)
# Only completely empty strings are rejected
empty_sd = (ga_index['start_date'].fillna('') == '').sum()
if empty_sd > 0:
    print(f"  Warning: {empty_sd} rows with empty start_date (will be dropped by pipeline)")
    ga_index = ga_index[ga_index['start_date'].fillna('') != '']

out_path = os.path.join(OUTPUT_DIR, 'georgia_index.csv')
ga_index.to_csv(out_path, index=False)
print(f"Wrote {len(ga_index)} rows to {out_path}")


# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------
print("\nBuilding discipline index...")

# Rename violations columns
violations = violations.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'raw_name',
    'VIOLATION': 'violation',
    'VIOLATION DATE': 'violation_date',
})
violations['person_nbr'] = violations['person_nbr'].apply(clean_person_nbr)
violations['case_id'] = violations['case_id'].astype(str).str.strip()
violations['violation_date'] = clean_dates_vectorized(violations['violation_date'])
# Title-case violation to match groundtruth (e.g., "Departmental Rule(S) Violations")
violations['violation'] = violations['violation'].astype(str).str.strip().str.title()

# Rename sanctions columns
sanctions = sanctions.rename(columns={
    'CASE': 'case_id',
    'OKEY': 'person_nbr',
    'NAME': 'raw_name',
    'SANCTION': 'sanction',
    'DATE': 'sanction_date',
})
sanctions['person_nbr'] = sanctions['person_nbr'].apply(clean_person_nbr)
sanctions['case_id'] = sanctions['case_id'].astype(str).str.strip()
sanctions['sanction_date'] = clean_dates_vectorized(sanctions['sanction_date'])
# Title-case sanction
sanctions['sanction'] = sanctions['sanction'].astype(str).str.strip().str.title()

print(f"  Violations: {len(violations)}, Sanctions: {len(sanctions)}")

# Filter out violations and sanctions with invalid/unknown dates
# (groundtruth has no 0000-00-00 violation_dates or sanction_dates)
before_v = len(violations)
violations = violations[
    violations['violation_date'].fillna('').isin(['']) == False
]
violations = violations[violations['violation_date'] != '0000-00-00']
violations = violations[violations['violation_date'] != '']
print(f"  Violations with valid date: {len(violations)} (dropped {before_v - len(violations)} with invalid date)")

before_s = len(sanctions)
sanctions = sanctions[sanctions['sanction_date'] != '0000-00-00']
sanctions = sanctions[sanctions['sanction_date'] != '']
print(f"  Sanctions with valid date: {len(sanctions)} (dropped {before_s - len(sanctions)} with invalid date)")

# Deduplicate violations on (case_id, person_nbr, violation)
violations = violations.drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
print(f"  Violations after dedup: {len(violations)}")

# Inner join violations + sanctions on (case_id, person_nbr)
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner',
)
print(f"  After inner join: {len(discipline)}")

# Deduplicate: one row per (case_id, person_nbr, violation) — keep most recent sanction
discipline = (
    discipline.sort_values('sanction_date', ascending=False)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
)
print(f"  After dedup (case_id, person_nbr, violation) - most recent sanction: {len(discipline)}")

# Convert case_id to integer (groundtruth shows it as int, no leading zeros)
discipline['case_id'] = pd.to_numeric(discipline['case_id'], errors='coerce').astype('Int64')


# ---------------------------------------------------------------------------
# Attach employment context to discipline records
# ---------------------------------------------------------------------------
print("Attaching employment context to discipline records...")

# Prepare employment for discipline join (with lowercase agency_name)
emp_for_disc = merged[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()
# Lowercase agency_name for discipline index (groundtruth shows lowercase)
emp_for_disc['agency_name'] = emp_for_disc['agency_name'].str.lower()
# Lowercase rank for discipline index
emp_for_disc['rank'] = emp_for_disc['rank'].astype(str).str.strip().str.lower()

# Join discipline to employment on person_nbr (many employment periods per person)
disc_emp = discipline.merge(emp_for_disc, on='person_nbr', how='left')
print(f"  After joining to employment: {len(disc_emp)}")

# Vectorized scoring: score each employment period against violation_date
# Convert dates to datetime for vectorized comparison
def to_dt(series, fill_future=False):
    """Convert date strings to datetime; 0000-00-00 -> NaT or 2099-12-31 if fill_future."""
    s = series.copy()
    if fill_future:
        s = s.replace('0000-00-00', '2099-12-31')
    else:
        s = s.replace('0000-00-00', pd.NaT)
    return pd.to_datetime(s, errors='coerce')

vd = to_dt(disc_emp['violation_date'])
sd = to_dt(disc_emp['start_date'])
ed = to_dt(disc_emp['end_date'], fill_future=True)

# Score: 0 if within period; else days outside (large = bad)
within = (sd <= vd) & (vd <= ed)
before_start = vd < sd
after_end = vd > ed

score = pd.Series(9999, index=disc_emp.index)
score[within] = 0
score[before_start] = (sd[before_start] - vd[before_start]).dt.days
score[after_end] = (vd[after_end] - ed[after_end]).dt.days
# Unknown violation date: score = 9999 (default)
# Unknown start_date: very bad
score[sd.isna()] = 9998

disc_emp['_score'] = score

# Sort by score, keep best employment period per (case_id, person_nbr, violation)
disc_emp = disc_emp.sort_values('_score')
disc_emp = disc_emp.drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
disc_emp = disc_emp.drop(columns=['_score'])
print(f"  After selecting best employment period: {len(disc_emp)}")

# Drop rows with empty start_date (no employment match)
disc_emp = disc_emp[disc_emp['start_date'].fillna('') != '']
print(f"  After dropping rows with empty start_date: {len(disc_emp)}")


# ---------------------------------------------------------------------------
# Add officer demographics to discipline index
# ---------------------------------------------------------------------------

# Merge officer demographics into discipline
disc_emp = disc_emp.merge(
    officer_data[[
        'person_nbr', 'last_name', 'first_name', 'middle_name', 'suffix',
        'year_of_birth', 'race', 'sex'
    ]],
    on='person_nbr',
    how='left',
)

# Build full_name (lowercase, to match groundtruth)
disc_emp['full_name'] = disc_emp.apply(
    lambda r: build_full_name(r['last_name'], r['first_name'], r['middle_name'], r['suffix']),
    axis=1
)

# Apply appropriate case per groundtruth:
# - violation, sanction: Title Case (e.g. 'Departmental Rule(S) Violations')
# - other text fields: lowercase
for col in ['last_name', 'first_name', 'middle_name', 'suffix', 'race', 'sex']:
    if col in disc_emp.columns:
        disc_emp[col] = disc_emp[col].astype(str).str.strip()
        disc_emp[col] = disc_emp[col].apply(
            lambda x: '' if x.lower() in ('nan', 'none') else x.lower()
        )
# violation and sanction stay Title Case (already set via .str.title() when loading)
for col in ['violation', 'sanction']:
    if col in disc_emp.columns:
        disc_emp[col] = disc_emp[col].astype(str).str.strip()
        disc_emp[col] = disc_emp[col].apply(
            lambda x: '' if x.lower() in ('nan', 'none') else x
        )

# Dates in discipline: 0000-00-00 stays as-is; empty stays empty
# violation_date: treat 0000-00-00 as empty string for discipline
disc_emp['violation_date'] = disc_emp['violation_date'].apply(
    lambda x: '' if x == '0000-00-00' else x
)
# sanction_date: treat 0000-00-00 as empty string
disc_emp['sanction_date'] = disc_emp['sanction_date'].apply(
    lambda x: '' if x == '0000-00-00' else x
)

# ---------------------------------------------------------------------------
# Build discipline index output columns
# ---------------------------------------------------------------------------
DISC_COLS = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date', 'violation', 'violation_date',
    'full_name', 'agency_name', 'rank', 'start_date', 'end_date',
    'last_name', 'first_name', 'middle_name', 'suffix',
    'year_of_birth', 'race', 'sex',
]

# Ensure all columns exist
for col in DISC_COLS:
    if col not in disc_emp.columns:
        disc_emp[col] = ''

ga_discipline = disc_emp[DISC_COLS].copy()

# Validate: no empty start_date rows
empty_sd_disc = (ga_discipline['start_date'].fillna('') == '').sum()
if empty_sd_disc > 0:
    print(f"  Warning: {empty_sd_disc} discipline rows with empty start_date")
    ga_discipline = ga_discipline[ga_discipline['start_date'].fillna('') != '']

out_path = os.path.join(OUTPUT_DIR, 'georgia-discipline_index.csv')
ga_discipline.to_csv(out_path, index=False)
print(f"Wrote {len(ga_discipline)} rows to {out_path}")

print("\nDone.")
