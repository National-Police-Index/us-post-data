"""
CA 2025 clean.py
Processes:
  1. LEO data from CPRA_R000301-011425__ADHOC-809.xlsx
  2. Corrections data from PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv
Outputs: ca_index.csv
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

def clean_date_series(series):
    """Vectorized date cleaning → YYYY-MM-DD strings or empty string."""
    s = series.astype(str).str.strip()
    bad = s.isin(['nan', 'NaT', 'None', '0000-00-00', '00/00/0000', 'NaN', ''])
    parsed = pd.to_datetime(s.where(~bad, other=pd.NaT), errors='coerce')
    result = parsed.dt.strftime('%Y-%m-%d').fillna('')
    return result

# ---------------------------------------------------------------------------
# Agency name expansion for LEO data (vectorized)
# ---------------------------------------------------------------------------

LEO_AGENCY_EXPANSIONS = [
    # Longer / more-specific patterns first
    (r'\bSCHL\s+DIST\b', 'SCHOOL DISTRICT'),
    (r'\bUNIF\s+SCHL\b', 'UNIFIED SCHOOL'),
    (r'\bCOLLEGE\s+DIST\s+PD\b', 'COMMUNITY COLLEGE DISTRICT POLICE DEPARTMENT'),
    (r'\bCCD\b', 'COMMUNITY COLLEGE DISTRICT'),
    (r'\bUNIF\b', 'UNIFIED'),
    (r'\bSCHL\b', 'SCHOOL'),
    # California prefix
    (r'\bCA\b', 'CALIFORNIA'),
    (r'\bCALIF\b', 'CALIFORNIA'),
    # County
    (r'\bCO\b', 'COUNTY'),
    # Dept
    (r'\bDEPT\.?\b', 'DEPARTMENT'),
    # DA / DOJ
    (r'\bDA\b', 'DISTRICT ATTORNEY'),
    (r'\bDPS\b', 'DEPARTMENT OF PUBLIC SAFETY'),
    # Sheriff
    (r"\bSD\b", "SHERIFF'S DEPARTMENT"),
    (r"\bSO\b", "SHERIFF'S OFFICE"),
    # Police Department
    (r'\bPD\b', 'POLICE DEPARTMENT'),
    # Marshal
    (r'\bMAR\b', 'MARSHAL'),
    # Highway
    (r'\bHWY\b', 'HIGHWAY'),
    # Other
    (r'\bCORR\.?\b', 'CORRECTIONS'),
    (r'\bSVCS?\b', 'SERVICES'),
    (r'\bDIV\.?\b', 'DIVISION'),
    (r'\bDIST\.?\b', 'DISTRICT'),
    (r'\bADMIN\.?\b', 'ADMINISTRATION'),
    (r'\bSPEC\b', 'SPECIAL'),
    (r'\bINV\b', 'INVESTIGATIONS'),
    (r'\bOFC\.?\b', 'OFFICE'),
]

def expand_leo_agency_series(series):
    """Vectorized agency name expansion."""
    s = series.fillna('').astype(str).str.strip().str.upper()
    s = s.str.replace(r'  +', ' ', regex=True)
    for pattern, replacement in LEO_AGENCY_EXPANSIONS:
        s = s.str.replace(pattern, replacement, regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

# ---------------------------------------------------------------------------
# Separation code mapping for LEO data
# ---------------------------------------------------------------------------

SEP_CODE_MAP = {
    '1': 'Resigned',
    '2': 'Discharge',
    '3': 'Retired',
    '4': 'Deceased',
    '5': 'Felony',
    '6': 'Other',
    '7': 'Promotion/Demotion',
    '8': 'Involuntary Separation',
    '9': 'Separated Pending Complaint, Administrative Charge, or Investigation for serious misconduct',
    '10': 'Status Change',
    '11': 'Did Not Complete Probation',
    '12': 'Cancelled',
    'Z': 'Unknown',
}

# ---------------------------------------------------------------------------
# SECTION 1: Process LEO data
# ---------------------------------------------------------------------------
print("Loading LEO data...")
leo_raw = pd.read_excel(
    os.path.join(INPUT_DIR, 'CPRA_R000301-011425__ADHOC-809.xlsx'),
    sheet_name='Sheet1',
    dtype=str
)
print(f"  Loaded {len(leo_raw):,} LEO rows")

leo = leo_raw.copy()

# person_nbr
leo['person_nbr'] = leo['POST_ID'].astype(str).str.strip()
leo = leo[leo['person_nbr'].notna() & (leo['person_nbr'] != '') & (leo['person_nbr'] != 'nan')]

# Parse names: "LAST, FIRST [MIDDLE]" (vectorized)
name_str = leo['officer_name'].fillna('').astype(str).str.strip()
split_comma = name_str.str.split(',', n=1, expand=True)
last_name = split_comma[0].str.strip()
rest = split_comma.get(1, pd.Series([''] * len(leo), index=leo.index)).fillna('').str.strip()
split_rest = rest.str.split(r'\s+', n=1, expand=True)
first_name = split_rest.get(0, pd.Series([''] * len(leo), index=rest.index)).fillna('').str.strip()
middle_name = split_rest.get(1, pd.Series([''] * len(leo), index=rest.index)).fillna('').str.strip()

leo['last_name'] = last_name
leo['first_name'] = first_name
leo['middle_name'] = middle_name
leo['suffix'] = ''

# Dates
leo['start_date'] = clean_date_series(leo['employment_start_date'])
leo['end_date'] = clean_date_series(leo['employment_end_date'])

# Separation reason
leo['sep_code'] = leo['separation_code'].astype(str).str.strip()
leo['separation_reason'] = leo['sep_code'].map(SEP_CODE_MAP).fillna('')

# Agency names
leo['agency_name'] = expand_leo_agency_series(leo['agency'])

# Rank
leo['rank'] = leo['rank'].fillna('').astype(str).str.strip().str.upper()

# Drop rows with empty start_date
before = len(leo)
leo = leo[leo['start_date'] != '']
print(f"  Dropped {before - len(leo):,} LEO rows with empty start_date, {len(leo):,} remain")

leo['type'] = 'POLICE'

# Output columns
leo_out = leo[[
    'person_nbr', 'first_name', 'middle_name', 'last_name',
    'agency_name', 'start_date', 'end_date', 'separation_reason',
    'rank', 'type',
]].copy()

print(f"  LEO output: {len(leo_out):,} rows")

# ---------------------------------------------------------------------------
# SECTION 2: Process Corrections data
# ---------------------------------------------------------------------------
print("Loading corrections data...")
corr_raw = pd.read_csv(
    os.path.join(INPUT_DIR, 'PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv'),
    dtype=str
)
print(f"  Loaded {len(corr_raw):,} corrections event rows")

# Strip whitespace
for col in corr_raw.columns:
    corr_raw[col] = corr_raw[col].astype(str).str.strip()

# Extract 3-digit agency code from POSITION NUMBER
corr_raw['agency_code'] = (
    corr_raw['POSITION NUMBER']
    .str.extract(r'^0*(\d{2,3})-')[0]
    .str.zfill(3)
)

# Normalize position number for matching (all digits, strip leading zeros)
corr_raw['pos_norm'] = (
    corr_raw['POSITION NUMBER']
    .str.replace(r'[^0-9]', '', regex=True)
    .str.lstrip('0')
)

# ---------------------------------------------------------------------------
# Build corrections agency names: "NNN: FACILITY_STR"
# where FACILITY_STR = sorted unique expanded facility names joined with -AKA-
# This matches the original groundtruth construction.
# ---------------------------------------------------------------------------
CORR_FAC_EXPANSIONS = [
    (r'\bCA\.\s+', 'CALIFORNIA '),    # CA. → CALIFORNIA (with period)
    (r'\bCA\b(?!\.)', 'CALIFORNIA'),   # CA without period (standalone word)
    (r'\bCORR\b', 'CORRECTIONS'),
    (r'\bSVS\b', 'SERVICES'),
    (r'\bDIV\b', 'DIVISION'),
    (r'\bCNTR\b', 'CENTER'),
    (r'\bYTH\b', 'YOUTH'),
]

def expand_corr_facility(s):
    s = str(s).strip().upper()
    for pat, repl in CORR_FAC_EXPANSIONS:
        s = re.sub(pat, repl, s)
    return re.sub(r'\s+', ' ', s).strip()

# Apply expansion to facility names
valid_mask = corr_raw['agency_code'].notna()
corr_raw['fac_expanded'] = corr_raw['FACILITY NAME'].apply(expand_corr_facility)

# Build code → "NAME1 -AKA- NAME2" (sorted unique expanded names per code)
def build_agency_for_code(group):
    names = sorted(group['fac_expanded'].drop_duplicates().tolist())
    return names[0] if len(names) == 1 else ' -AKA- '.join(names)

code_agency_df = (
    corr_raw[valid_mask]
    .groupby('agency_code')
    .apply(build_agency_for_code, include_groups=False)
    .reset_index()
)
code_agency_df.columns = ['agency_code', 'facility_str']
code_facility_map = dict(zip(code_agency_df['agency_code'], code_agency_df['facility_str']))

corr_raw['agency_name'] = (
    corr_raw['agency_code'].fillna('') + ': ' +
    corr_raw['agency_code'].map(code_facility_map).fillna(corr_raw['fac_expanded'])
)

# Parse dates
corr_raw['trans_date'] = pd.to_datetime(
    corr_raw['TRANS EFF DATE'], errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')

# Trans type and other fields
corr_raw['trans_type'] = corr_raw['TYPE OF TRANSACTION'].str.upper().str.strip()
corr_raw['person_nbr'] = corr_raw['UNIQUE ID'].astype(str).str.strip()
corr_raw['last_name'] = corr_raw['LAST NAME'].str.upper().str.strip()
corr_raw['rank'] = corr_raw['CLASS TITLE'].str.upper().str.strip()

# Parse FIRST NAME → first + middle
# Format: "FIRST [M]" where M is single-letter middle initial
fm_split = corr_raw['FIRST NAME'].str.strip().str.rsplit(n=1, expand=True)
has_mid = fm_split.get(1, pd.Series([''] * len(corr_raw))).str.len() == 1
corr_raw['first_name'] = (
    fm_split[0].where(has_mid, corr_raw['FIRST NAME'].str.strip())
    .fillna('').str.strip().str.upper()
)
corr_raw['middle_name'] = (
    fm_split.get(1, pd.Series([''] * len(corr_raw)))
    .where(has_mid, '')
    .fillna('').str.strip().str.upper()
)

print("  Building corrections employment stints (vectorized)...")

# Appointments (APPOINTMENT + CHANGE = start of a stint)
appts = corr_raw[corr_raw['trans_type'].isin(['APPOINTMENT', 'CHANGE'])].sort_values('trans_date')
seps = corr_raw[corr_raw['trans_type'] == 'SEPARATION'].sort_values('trans_date')

# Group by (person, position): earliest appointment = start_date
appt_g = (
    appts.groupby(['person_nbr', 'pos_norm'])
    .agg(
        start_date=('trans_date', 'first'),
        agency_name=('agency_name', 'first'),
        rank=('rank', 'last'),
    )
    .reset_index()
)

# Group by (person, position): earliest separation = end_date
sep_g = (
    seps.groupby(['person_nbr', 'pos_norm'])
    .agg(end_date=('trans_date', 'first'))
    .reset_index()
)

# Merge
corr_stints = appt_g.merge(sep_g, on=['person_nbr', 'pos_norm'], how='left')
corr_stints['end_date'] = corr_stints['end_date'].fillna('')

# Fix end < start
bad_end = corr_stints['end_date'].ne('') & (corr_stints['end_date'] < corr_stints['start_date'])
corr_stints.loc[bad_end, 'end_date'] = ''

# Attach person names (use last record per person for canonical name)
person_names = (
    corr_raw.sort_values('trans_date')
    .groupby('person_nbr')
    .last()[['last_name', 'first_name', 'middle_name']]
    .reset_index()
)
corr_stints = corr_stints.merge(person_names, on='person_nbr', how='left')

# Drop rows with empty start_date
before = len(corr_stints)
corr_stints = corr_stints[corr_stints['start_date'] != '']
print(f"  Dropped {before - len(corr_stints):,} corrections rows with empty start_date")

corr_stints['type'] = 'CORRECTIONS'
corr_stints['separation_reason'] = ''

corr_out = corr_stints[[
    'person_nbr', 'first_name', 'middle_name', 'last_name',
    'agency_name', 'start_date', 'end_date', 'separation_reason',
    'rank', 'type',
]].copy()

print(f"  Corrections output: {len(corr_out):,} rows")

# ---------------------------------------------------------------------------
# SECTION 3: Combine and output
# ---------------------------------------------------------------------------
print("Combining LEO and corrections data...")

combined = pd.concat([leo_out, corr_out], ignore_index=True)
print(f"  Combined: {len(combined):,} rows")

# Validate required columns
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required:
    if col not in combined.columns:
        raise ValueError(f"Missing required column: {col}")

# No empty start_date
assert (combined['start_date'] != '').all(), "start_date must not be empty"

# Clean up NaN → empty string
for col in ['end_date', 'middle_name', 'separation_reason', 'rank', 'type']:
    if col in combined.columns:
        combined[col] = combined[col].fillna('').astype(str).replace('nan', '')

# Deduplicate
before = len(combined)
combined = combined.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Dropped {before - len(combined):,} duplicates, {len(combined):,} rows remain")

# Write output
out_path = os.path.join(OUTPUT_DIR, 'ca_index.csv')
combined.to_csv(out_path, index=False)
print(f"\nWrote {len(combined):,} rows to {out_path}")

print(f"\nSummary:")
print(f"  LEO rows:         {len(leo_out):,}")
print(f"  Corrections rows: {len(corr_out):,}")
print(f"  Total rows:       {len(combined):,}")
print(f"  Unique officers:  {combined['person_nbr'].nunique():,}")
print(f"  Unique agencies:  {combined['agency_name'].nunique():,}")
