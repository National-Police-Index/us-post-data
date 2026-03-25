"""
Georgia POST Data Cleaner — 2025
Produces:
  output/ga_index.csv
  output/ga-discipline_index.csv
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
# Helpers
# ---------------------------------------------------------------------------

def clean_date_series(series):
    """Vectorized date cleaning. Returns string series with YYYY-MM-DD or '' or '0000-00-00'."""
    s = series.astype(str).str.strip()
    # Mark nullish
    null_mask = s.isin(['', 'nan', 'NaT', 'None'])
    zero_mask = (s == '0000-00-00')
    # Parse valid dates
    parsed = pd.to_datetime(s, errors='coerce')
    result = parsed.dt.strftime('%Y-%m-%d').fillna('')
    # Restore 0000-00-00 and empty
    result = result.where(~null_mask, '')
    result = result.where(~zero_mask, '0000-00-00')
    return result


def safe_date(val):
    """Scalar version — use vectorized clean_date_series where possible."""
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


def build_full_name(last, first, middle, suffix):
    """Build full_name as 'last, first middle suffix' in lowercase."""
    parts = [p for p in [first, middle, suffix] if p and str(p).strip()]
    rest = ' '.join(str(p).strip() for p in parts)
    last = str(last).strip() if last and str(last).strip() else ''
    if last and rest:
        full = f"{last}, {rest}"
    elif last:
        full = last
    else:
        full = rest
    return full.lower()


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

employment = pd.read_csv(os.path.join(INPUT_DIR, 'officer_employment.csv'), dtype=str)
officer    = pd.read_csv(os.path.join(INPUT_DIR, 'officer_data.csv'),       dtype=str)
agency_ref = pd.read_csv(os.path.join(INPUT_DIR, 'agency_data.csv'),        dtype=str)
violations = pd.read_csv(os.path.join(INPUT_DIR, 'officer_violations.csv'), dtype=str)
sanctions  = pd.read_csv(os.path.join(INPUT_DIR, 'officer_sanctions.csv'),  dtype=str)

print(f"Loaded: employment={len(employment)}, officer={len(officer)}, "
      f"violations={len(violations)}, sanctions={len(sanctions)}")


# ---------------------------------------------------------------------------
# Clean officer demographics
# ---------------------------------------------------------------------------

officer = officer.rename(columns={
    'OKEY':       'person_nbr',
    'LAST NAME':  'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE':     'middle_name',
    'SUFFIX':     'suffix',
    'YOB':        'year_of_birth',
    'SEX':        'sex',
    'RACE':       'race',
})

officer['person_nbr'] = officer['person_nbr'].astype(str).str.lower().str.strip()
for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
    officer[col] = officer[col].fillna('').astype(str).str.strip().str.lower()

# Build full_name from demographics
officer['full_name'] = officer.apply(
    lambda r: build_full_name(r['last_name'], r['first_name'], r['middle_name'], r['suffix']),
    axis=1
)


# ---------------------------------------------------------------------------
# Clean employment
# ---------------------------------------------------------------------------

employment = employment.rename(columns={
    'OKEY':       'person_nbr',
    'NAME':       'officer_name_raw',
    'AGENCY':     'agency_name',
    'RANK':       'rank',
    'STATUS':     'employment_status',
    'START DATE': 'start_date',
    'END DATE':   'end_date',
})

employment['person_nbr'] = employment['person_nbr'].astype(str).str.lower().str.strip()

# Clean dates — keep 0000-00-00 as-is per groundtruth
employment['start_date'] = clean_date_series(employment['start_date'])
employment['end_date']   = clean_date_series(employment['end_date'])

# Agency name: groundtruth keeps the code prefix (e.g. "G1720 DEKALB COUNTY POLICE DEPARTMENT")
# Just strip trailing slash fragments and filter non-agency values
NON_AGENCY = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}

def clean_agency_employment(name):
    if pd.isna(name):
        return ''
    s = str(name).strip()
    # Do NOT strip trailing slash fragments — groundtruth preserves them (e.g. "G1276 METRO STATE PRISON/INACTIVE")
    return s

employment['agency_name'] = employment['agency_name'].apply(clean_agency_employment)

# Filter non-agency rows — check against base name (before slash)
def agency_base(name):
    return re.sub(r'\s*/.*$', '', str(name)).strip().lower()

employment = employment[
    ~employment['agency_name'].apply(agency_base).isin(NON_AGENCY)
]

# Drop rows with empty start_date (pipeline drops them anyway)
employment = employment[employment['start_date'] != '']

print(f"After employment cleaning: {len(employment)} rows")


# ---------------------------------------------------------------------------
# Merge employment + demographics
# ---------------------------------------------------------------------------

merged = employment.merge(
    officer[['person_nbr', 'last_name', 'first_name', 'middle_name',
             'suffix', 'full_name', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Fill missing name fields
for col in ['last_name', 'first_name', 'middle_name', 'suffix', 'full_name']:
    merged[col] = merged[col].fillna('')

# Drop duplicates on person_nbr + agency_name + start_date
before = len(merged)
merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"Dropped {before - len(merged)} duplicate rows; final employment: {len(merged)}")


# ---------------------------------------------------------------------------
# Build employment index output
# ---------------------------------------------------------------------------

EMPLOYMENT_COLS = [
    'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex',
]

emp_out = merged[EMPLOYMENT_COLS].copy()

# Validate required columns
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in required if c not in emp_out.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

emp_out.to_csv(os.path.join(OUTPUT_DIR, 'ga_index.csv'), index=False)
print(f"Wrote ga_index.csv: {len(emp_out)} rows")


# ---------------------------------------------------------------------------
# Discipline index
# ---------------------------------------------------------------------------

# Rename violations
violations = violations.rename(columns={
    'CASE':           'case_id',
    'OKEY':           'person_nbr',
    'NAME':           'officer_name_raw',
    'VIOLATION':      'violation',
    'VIOLATION DATE': 'violation_date',
})
violations['person_nbr']     = violations['person_nbr'].astype(str).str.lower().str.strip()
violations['case_id']        = violations['case_id'].astype(str).str.strip()
violations['violation']      = violations['violation'].fillna('').astype(str).str.strip().str.title()
violations['violation_date'] = clean_date_series(violations['violation_date'])

# Rename sanctions
sanctions = sanctions.rename(columns={
    'CASE':    'case_id',
    'OKEY':    'person_nbr',
    'NAME':    'officer_name_raw_s',
    'SANCTION':'sanction',
    'DATE':    'sanction_date',
})
sanctions['person_nbr']    = sanctions['person_nbr'].astype(str).str.lower().str.strip()
sanctions['case_id']       = sanctions['case_id'].astype(str).str.strip()
sanctions['sanction']      = sanctions['sanction'].fillna('').astype(str).str.strip().str.title()
sanctions['sanction_date'] = clean_date_series(sanctions['sanction_date'])

# Inner join violations + sanctions on case_id + person_nbr
discipline = violations.merge(
    sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
    on=['case_id', 'person_nbr'],
    how='inner'
)
print(f"After violations-sanctions inner join: {len(discipline)} rows")

# Deduplicate: keep most recent sanction per (case_id, person_nbr, violation)
discipline = (
    discipline
    .sort_values('sanction_date', ascending=False)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
)
print(f"After dedup on (case_id, person_nbr, violation): {len(discipline)} rows")

# Attach demographics
discipline = discipline.merge(
    officer[['person_nbr', 'last_name', 'first_name', 'middle_name',
             'suffix', 'full_name', 'year_of_birth', 'race', 'sex']],
    on='person_nbr',
    how='left'
)

# Attach employment context — pick the best matching period per discipline row
# Build employment lookup (with the cleaned agency_name)
emp_lookup = employment[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()

# Vectorized approach: merge then score, keeping best per (case_id, person_nbr, violation)
discipline = discipline.merge(emp_lookup, on='person_nbr', how='left')
print(f"After employment join: {len(discipline)} rows")


# ---------------------------------------------------------------------------
# Score employment periods for discipline rows — vectorized
# ---------------------------------------------------------------------------

today = pd.Timestamp('today').normalize()

def score_periods_vectorized(df):
    """Vectorized scoring: how well does violation_date fall in [start_date, end_date].
    Lower score = better match. 0 = within period."""
    vd = pd.to_datetime(df['violation_date'], errors='coerce')
    sd = pd.to_datetime(df['start_date'].replace('0000-00-00', ''), errors='coerce')
    ed = df['end_date'].replace('0000-00-00', '')
    end = pd.to_datetime(ed, errors='coerce').fillna(today)

    # Invalid start → worst score
    bad_start = sd.isna()
    score = pd.Series(9999, index=df.index, dtype=float)

    # No violation date → prefer latest start (use negative start timestamp)
    no_vd = vd.isna()
    has_start = ~bad_start

    # Within period: score = 0
    within = has_start & ~no_vd & (vd >= sd) & (vd <= end)
    score[within] = 0

    # Before start: score = days before start
    before = has_start & ~no_vd & (vd < sd)
    score[before] = (sd[before] - vd[before]).dt.days.astype(float)

    # After end: score = days after end
    after = has_start & ~no_vd & (vd > end)
    score[after] = (vd[after] - end[after]).dt.days.astype(float)

    # No violation date but valid start: prefer latest start (lower is better → negate)
    no_vd_good = has_start & no_vd
    score[no_vd_good] = -(sd[no_vd_good] - pd.Timestamp('1970-01-01')).dt.days.astype(float)

    return score


discipline['_score'] = score_periods_vectorized(discipline)

# Keep best-scoring employment period per (case_id, person_nbr, violation)
discipline = (
    discipline
    .sort_values('_score', ascending=True)
    .drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
)
discipline = discipline.drop(columns=['_score'])

# Drop rows with no employment match (empty start_date)
discipline = discipline[discipline['start_date'].fillna('') != '']
discipline = discipline[discipline['start_date'] != '0000-00-00']

print(f"After employment period selection & filtering: {len(discipline)} rows")

# Fill demographic fields
for col in ['last_name', 'first_name', 'middle_name', 'suffix', 'full_name',
            'year_of_birth', 'race', 'sex']:
    discipline[col] = discipline[col].fillna('')

# Agency_name for discipline: groundtruth keeps lowercase with code prefix
# The employment agency_name is uppercase with code — lowercase it for discipline
discipline['agency_name'] = discipline['agency_name'].str.lower()

# Lowercase name fields (already lowercase from officer table)
discipline['rank'] = discipline['rank'].str.lower().fillna('')


# ---------------------------------------------------------------------------
# Build discipline index output
# ---------------------------------------------------------------------------

DISCIPLINE_COLS = [
    'case_id', 'person_nbr', 'sanction', 'sanction_date',
    'violation', 'violation_date', 'full_name', 'agency_name', 'rank',
    'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
    'suffix', 'year_of_birth', 'race', 'sex',
]

disc_out = discipline[DISCIPLINE_COLS].copy()

# Final dedup on discipline
before = len(disc_out)
disc_out = disc_out.drop_duplicates(subset=['case_id', 'person_nbr', 'violation'])
print(f"Final discipline dedup: {before - len(disc_out)} removed; final={len(disc_out)}")

disc_out.to_csv(os.path.join(OUTPUT_DIR, 'ga-discipline_index.csv'), index=False)
print(f"Wrote ga-discipline_index.csv: {len(disc_out)} rows")
print("Done.")
