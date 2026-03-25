"""
California POST + CDCR Employment Index Cleaner
Processes two data sources:
  1. LEO data: CPRA_R000301-011425__ADHOC-809.xlsx (POST officers)
  2. Corrections data: PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv (CDCR)

Outputs: ca_index.csv
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

INPUT_DIR  = args.input_dir
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


def parse_leo_name(name_str):
    """Fast parse of 'LAST, FIRST MIDDLE' LEO name format.
    Returns (first, middle, last, suffix) all uppercase.
    """
    s = str(name_str).strip()
    suffix = ''
    if ',' in s:
        last, rest = s.split(',', 1)
        rest = rest.strip()
        parts = rest.split()
        first  = parts[0] if parts else ''
        middle = ' '.join(parts[1:]) if len(parts) > 1 else ''
    else:
        parts = s.split()
        last   = parts[0] if parts else ''
        first  = parts[1] if len(parts) > 1 else ''
        middle = ' '.join(parts[2:]) if len(parts) > 2 else ''
    return first.upper(), middle.upper(), last.upper(), suffix


# ---------------------------------------------------------------------------
# Separation code → reason mapping (LEO data)
# ---------------------------------------------------------------------------
SEP_CODE_MAP = {
    '1':  'Resigned',
    '2':  'Discharged',
    '3':  'Retired',
    '4':  'Deceased',
    '5':  'Felony',
    '6':  'Other',
    '7':  'Promotion/Demotion',
    '8':  'Involuntary Separation',
    '9':  ('Separated Pending Complaint, Administrative Charge, '
           'or Investigation for Serious Misconduct'),
    '10': 'Status Change',
    '11': 'Did Not Complete Probation',
    'Z':  'Unknown',
}

# ---------------------------------------------------------------------------
# Agency abbreviation expansions (LEO)
# ---------------------------------------------------------------------------
AGENCY_ABBREVIATIONS = [
    (r'\bDEPT\.?\b',          'DEPARTMENT'),
    (r'\bSD\b',               "SHERIFF'S DEPARTMENT"),
    (r'\bSO\b',               "SHERIFF'S OFFICE"),
    (r'\bPD\b',               'POLICE DEPARTMENT'),
    (r'\bCORR\.?\b',          'CORRECTIONS'),
    (r'\bDA\b',               "DISTRICT ATTORNEY'S OFFICE"),
    (r'\bDPS\b',              'DEPARTMENT OF PUBLIC SAFETY'),
    (r'\bSVCS?\b',            'SERVICES'),
    (r'\bDIV\.?\b',           'DIVISION'),
    (r'\bDIST\.?\b',          'DISTRICT'),
    (r'\bADMIN\.?\b',         'ADMINISTRATION'),
    (r'\bINVEST\.?\b',        'INVESTIGATIONS'),
    (r'\bMAR\b',              'MARSHAL'),
    (r'\bHWY\b',              'HIGHWAY'),
    (r'\bCO\.\s+',            'COUNTY '),
    (r'\bCO\s+',              'COUNTY '),
]

NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}


def clean_leo_agency(name):
    if pd.isna(name):
        return ''
    s = str(name).strip().upper()
    # Strip trailing slash fragments (e.g. "SD/CORONER" → keep "/CORONER" visible)
    # Actually groundtruth keeps e.g. "ORANGE COUNTY SHERIFF'S DEPARTMENT/CORONER"
    # so do NOT strip slash fragments for LEO — they are meaningful
    # Expand abbreviations
    for pattern, replacement in AGENCY_ABBREVIATIONS:
        s = re.sub(pattern, replacement, s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ===========================================================================
# PART 1 — LEO data (POST)
# ===========================================================================
print("Loading LEO data...")
leo_xlsx  = os.path.join(INPUT_DIR, 'CPRA_R000301-011425__ADHOC-809.xlsx')
leo_cache = os.path.join(INPUT_DIR, 'leo_cache.csv')  # pre-converted CSV if available

if os.path.exists(leo_cache):
    print("  (using pre-converted CSV cache)")
    leo_raw = pd.read_csv(leo_cache, dtype=str)
else:
    print("  Reading Excel (this may take ~30s)...")
    leo_raw = pd.read_excel(leo_xlsx, dtype=str, engine='openpyxl')
    leo_raw.to_csv(leo_cache, index=False)

print(f"  LEO raw rows: {len(leo_raw)}")

# Strip whitespace
for col in leo_raw.columns:
    leo_raw[col] = leo_raw[col].fillna('').astype(str).str.strip()

# Parse names
name_parsed = [parse_leo_name(n) for n in leo_raw['officer_name']]
leo_raw['first_name']  = [x[0] for x in name_parsed]
leo_raw['middle_name'] = [x[1] for x in name_parsed]
leo_raw['last_name']   = [x[2] for x in name_parsed]
leo_raw['suffix']      = [x[3] for x in name_parsed]

# person_nbr: POST_ID, lowercased and stripped
leo_raw['person_nbr'] = leo_raw['POST_ID'].astype(str).str.lower().str.strip()

# Dates (vectorized for speed)
def parse_dates_vec(series):
    dt = pd.to_datetime(series, errors='coerce')
    result = dt.dt.strftime('%Y-%m-%d').fillna('')
    return result

leo_raw['start_date'] = parse_dates_vec(leo_raw['employment_start_date'])
leo_raw['end_date']   = parse_dates_vec(leo_raw['employment_end_date'])

# Agency name: expand abbreviations (vectorized)
def clean_leo_agency_vec(series):
    s = series.fillna('').astype(str).str.strip().str.upper()
    for pattern, replacement in AGENCY_ABBREVIATIONS:
        s = s.str.replace(pattern, replacement, regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    return s

leo_raw['agency_name'] = clean_leo_agency_vec(leo_raw['agency'])

# Separation reason from code
leo_raw['separation_reason'] = (
    leo_raw['separation_code'].astype(str).str.strip()
    .map(SEP_CODE_MAP).fillna('')
)

# Rank
leo_raw['rank'] = leo_raw['rank'].astype(str).str.strip().str.upper().replace('NAN', '')

# Build LEO dataframe
leo = leo_raw[[
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'agency_name', 'start_date', 'end_date', 'separation_reason', 'rank',
]].copy()
leo['type'] = 'POLICE'

# Filter non-agency values
leo = leo[~leo['agency_name'].str.lower().isin(NON_AGENCY_VALUES)]

# Drop rows with empty start_date
before = len(leo)
leo = leo[leo['start_date'] != '']
print(f"  LEO rows after dropping empty start_date: {len(leo)} (dropped {before - len(leo)})")

# Deduplicate
leo = leo.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  LEO rows after dedup: {len(leo)}")


# ===========================================================================
# PART 2 — Corrections data (CDCR)
# ===========================================================================
print("Loading corrections data...")
corr_file = os.path.join(INPUT_DIR, 'PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv')
corr_raw = pd.read_csv(corr_file, low_memory=False, dtype=str)
print(f"  Corrections raw rows: {len(corr_raw)}")

# Strip whitespace
for col in corr_raw.columns:
    corr_raw[col] = corr_raw[col].fillna('').astype(str).str.strip()

# Normalize POSITION NUMBER: strip leading zeros from first segment
def norm_position(p):
    parts = str(p).strip().split('-')
    if parts:
        try:
            parts[0] = str(int(parts[0]))
        except ValueError:
            pass
    return '-'.join(parts)

corr_raw['pos_norm'] = corr_raw['POSITION NUMBER'].apply(norm_position)

# Extract agency code from normalized position number (first segment)
_agency_code_re = re.compile(r'^(\d+)-')
corr_raw['agency_code'] = corr_raw['pos_norm'].apply(
    lambda p: m.group(1) if (m := _agency_code_re.match(str(p))) else None
)

# Build canonical agency name: "NNN: FACILITY NAME"
# Use most common facility name per agency code (standardize)
agency_code_to_name = (
    corr_raw[corr_raw['agency_code'].notna() & (corr_raw['agency_code'] != '')]
    .groupby('agency_code')['FACILITY NAME']
    .agg(lambda x: x.value_counts().index[0])
    .to_dict()
)

def build_corrections_agency(code, facility):
    if not code or code in ('None', ''):
        return str(facility).upper().strip()
    canonical = agency_code_to_name.get(str(code), str(facility))
    try:
        return f"{int(code):03d}: {canonical.strip().upper()}"
    except (ValueError, TypeError):
        return str(facility).upper().strip()

corr_raw['agency_name'] = [
    build_corrections_agency(c, f)
    for c, f in zip(corr_raw['agency_code'], corr_raw['FACILITY NAME'])
]

# Parse names
corr_raw['last_name']   = corr_raw['LAST NAME'].str.upper().str.strip()
corr_raw['first_middle'] = corr_raw['FIRST NAME'].str.upper().str.strip()
corr_raw['first_name']  = corr_raw['first_middle'].str.split().str[0].fillna('')
corr_raw['middle_name'] = corr_raw['first_middle'].apply(
    lambda s: ' '.join(str(s).split()[1:]) if len(str(s).split()) > 1 else ''
)

# person_nbr from UNIQUE ID
corr_raw['person_nbr'] = corr_raw['UNIQUE ID'].astype(str).str.strip()

# Parse dates vectorized
corr_raw['date_dt'] = pd.to_datetime(corr_raw['TRANS EFF DATE'], errors='coerce')

# Separate into starts (APPOINTMENT + CHANGE) and separations
mask_start = corr_raw['TYPE OF TRANSACTION'].isin(['APPOINTMENT', 'CHANGE'])
starts = corr_raw[mask_start].copy()
seps   = corr_raw[corr_raw['TYPE OF TRANSACTION'] == 'SEPARATION'].copy()

# ---------------------------------------------------------------------------
# Link by (person_nbr, pos_norm):
# start_date = earliest date among APPOINTMENT/CHANGE rows for that position
# end_date   = latest date among SEPARATION rows for that position
# ---------------------------------------------------------------------------
key_cols  = ['person_nbr', 'pos_norm']
name_cols = ['last_name', 'first_name', 'middle_name', 'agency_name']

# Start records: earliest date per (person, pos_norm)
starts_sorted = starts.sort_values(['person_nbr', 'pos_norm', 'date_dt'])
starts_agg = (
    starts_sorted
    .drop_duplicates(subset=['person_nbr', 'pos_norm'])  # keep first = earliest
    [key_cols + name_cols + ['date_dt']]
    .rename(columns={'date_dt': 'start_dt'})
    .reset_index(drop=True)
)

# Separation records: latest date per (person_nbr, pos_norm)
seps_agg = (
    seps
    .sort_values(['person_nbr', 'pos_norm', 'date_dt'])
    .drop_duplicates(subset=['person_nbr', 'pos_norm'], keep='last')
    [key_cols + ['date_dt']]
    .rename(columns={'date_dt': 'end_dt'})
    .reset_index(drop=True)
)

# Merge
linked = starts_agg.merge(seps_agg, on=key_cols, how='left')

# Format dates (vectorized)
linked['start_date'] = linked['start_dt'].dt.strftime('%Y-%m-%d').fillna('')
linked['end_date']   = linked['end_dt'].dt.strftime('%Y-%m-%d').fillna('')
# NaT -> empty string
linked.loc[linked['start_dt'].isna(), 'start_date'] = ''
linked.loc[linked['end_dt'].isna(), 'end_date']     = ''

print(f"  Corrections linked rows: {len(linked)}")

# Build corrections dataframe
corr = linked[[
    'person_nbr', 'first_name', 'middle_name', 'last_name',
    'agency_name', 'start_date', 'end_date',
]].copy()
corr['suffix']           = ''
corr['separation_reason'] = ''
corr['rank']             = ''
corr['type']             = 'CORRECTIONS'

# Drop empty start_dates
before = len(corr)
corr = corr[corr['start_date'] != '']
print(f"  Corrections rows after dropping empty start_date: {len(corr)} (dropped {before - len(corr)})")

# Deduplicate
corr = corr.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Corrections rows after dedup: {len(corr)}")


# ===========================================================================
# PART 3 — Combine and output
# ===========================================================================
print("Combining LEO + Corrections...")

all_cols = ['person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
            'agency_name', 'start_date', 'end_date', 'separation_reason', 'rank', 'type']

combined = pd.concat([
    leo.reindex(columns=all_cols),
    corr.reindex(columns=all_cols),
], ignore_index=True)

print(f"  Combined rows: {len(combined)}")

# Final cleanup
for col in ['person_nbr', 'first_name', 'last_name', 'middle_name', 'suffix',
            'agency_name', 'separation_reason', 'rank', 'type']:
    combined[col] = combined[col].fillna('').astype(str).str.strip()

combined['person_nbr'] = combined['person_nbr'].str.lower()

# Build full_name: "last, first middle suffix" lowercased
def build_full_name(row):
    parts = [row['first_name']]
    if row['middle_name']:
        parts.append(row['middle_name'])
    if row['suffix']:
        parts.append(row['suffix'])
    first_part = ' '.join(p for p in parts if p)
    last_part  = row['last_name']
    if first_part and last_part:
        return f"{last_part}, {first_part}".lower()
    elif last_part:
        return last_part.lower()
    return ''

# Vectorized full_name construction
first_parts = combined['first_name'].str.cat(
    [combined['middle_name'].where(combined['middle_name'] != '', other=''),
     combined['suffix'].where(combined['suffix'] != '', other='')],
    sep=' ', na_rep=''
).str.strip().str.replace(r'\s+', ' ', regex=True)
combined['full_name'] = (
    combined['last_name'] + ', ' + first_parts
).str.lower().where(
    combined['last_name'] != '', other=''
)

# Validate required columns
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required:
    assert col in combined.columns, f"Missing required column: {col}"

# Check for empty start_dates
empty_start = (combined['start_date'] == '') | combined['start_date'].isna()
if empty_start.any():
    print(f"WARNING: dropping {empty_start.sum()} rows with empty start_date")
    combined = combined[~empty_start]

# Final dedup
combined = combined.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Final combined rows: {len(combined)}")

# Write output
out_path = os.path.join(OUTPUT_DIR, 'ca_index.csv')
combined.to_csv(out_path, index=False)
print(f"Wrote {out_path} ({len(combined)} rows)")

# Note: leo_cache.csv in data/input/ is a pre-converted version of the xlsx
# for faster re-runs. It is intentionally left in place.
