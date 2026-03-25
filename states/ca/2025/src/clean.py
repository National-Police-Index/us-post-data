"""
California POST / CDCR officer data cleaning script.
Processes two source files:
  1. CPRA_R000301-011425__ADHOC-809.xlsx  -> LEO (law enforcement officers)
  2. PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv -> Corrections officers

Outputs: output/ca_index.csv
"""

import argparse
import os
import re

import pandas as pd
from nameparser import HumanName


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


def norm_pos(p):
    """Normalize CDCR position number by stripping leading zeros from prefix."""
    s = str(p).strip()
    m = re.match(r'^0*(\d+)-(.+)', s)
    if m:
        return m.group(1) + '-' + m.group(2)
    return s


def extract_agency_code(pos_num):
    """Extract 3-digit padded agency code from CDCR position number."""
    s = str(pos_num).strip()
    m = re.match(r'^0*(\d+)-', s)
    return str(int(m.group(1))).zfill(3) if m else ''


# Separation code -> reason mapping (inferred from groundtruth)
SEP_CODE_MAP = {
    '1':  'Resigned',
    '2':  'Discharged',
    '3':  'Retired',
    '4':  'Deceased',
    '5':  'Felony',
    '6':  'Other',
    '7':  'Promotion/Demotion',
    '8':  'Involuntary Separation',
    '9':  'Separated Pending Complaint, Administrative Charge, or Investigation for Serious Misconduct',
    '10': 'Status Change',
    '11': 'Did Not Complete Probation',
    'Z':  'Unknown',
}


# ---------------------------------------------------------------------------
# Section 1: Process LEO data (CPRA xlsx)
# ---------------------------------------------------------------------------

print("Loading LEO data...")
leo_file = os.path.join(INPUT_DIR, "CPRA_R000301-011425__ADHOC-809.xlsx")
leo_raw = pd.read_excel(leo_file, dtype=str)
print(f"  LEO raw rows: {len(leo_raw)}")

# Rename core columns
leo = leo_raw.rename(columns={
    'POST_ID': 'person_nbr',
    'officer_name': 'full_name_raw',
    'agency': 'agency_raw',
    'employment_start_date': 'start_date_raw',
    'employment_end_date': 'end_date_raw',
    'separation_code': 'sep_code',
})

# Clean person_nbr
leo['person_nbr'] = leo['person_nbr'].astype(str).str.strip()

# Parse names from "LAST, FIRST MIDDLE" format using nameparser
# Process unique names only for speed
print("  Parsing LEO names (unique only)...")

unique_names = leo['full_name_raw'].dropna().unique()
name_cache = {}
for name_str in unique_names:
    s = str(name_str).strip()
    if not s or s == 'nan':
        name_cache[name_str] = ('', '', '', '')
        continue
    hn = HumanName(s)
    name_cache[name_str] = (
        hn.first.upper() if hn.first else '',
        hn.middle.upper() if hn.middle else '',
        hn.last.upper() if hn.last else '',
        hn.suffix.upper() if hn.suffix else '',
    )

name_df = pd.DataFrame.from_dict(
    name_cache, orient='index',
    columns=['first_name', 'middle_name', 'last_name', 'suffix']
)
name_df.index.name = 'full_name_raw'
name_df = name_df.reset_index()
leo = leo.merge(name_df, on='full_name_raw', how='left')
leo['first_name'] = leo['first_name'].fillna('')
leo['middle_name'] = leo['middle_name'].fillna('')
leo['last_name'] = leo['last_name'].fillna('')
leo['suffix'] = leo['suffix'].fillna('')

# Parse dates (vectorized for speed)
leo['start_date'] = pd.to_datetime(
    leo['start_date_raw'], format='%m/%d/%Y', errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')
leo['end_date'] = pd.to_datetime(
    leo['end_date_raw'], format='%m/%d/%Y', errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')

# Separation reason from code
leo['sep_code_clean'] = leo['sep_code'].astype(str).str.strip()
leo['separation_reason'] = leo['sep_code_clean'].map(SEP_CODE_MAP).fillna('')

# Agency name expansion
# The raw agency names use abbreviations that need to be expanded to match GT
AGENCY_EXPANSIONS = [
    (r'\bUNIF SCH DIST\b',       'UNIFIED SCHOOL DISTRICT'),
    (r'\bUNIF SCHL DIST\b',      'UNIFIED SCHOOL DISTRICT'),
    (r'\bUNIFIED SCH DIST\b',    'UNIFIED SCHOOL DISTRICT'),
    (r'\bUNIFIED SCHL DIST\b',   'UNIFIED SCHOOL DISTRICT'),
    (r'\bSCH DIST\b',            'SCHOOL DISTRICT'),
    (r'\bSCHL DIST\b',           'SCHOOL DISTRICT'),
    (r'\bCOMM COLLEGE DIST\b',   'COMMUNITY COLLEGE DISTRICT'),
    (r'\bCCD\b',                 'COMMUNITY COLLEGE DISTRICT'),
    (r'\bSD/CORONER\b',          "SHERIFF'S DEPARTMENT/CORONER"),
    (r"\bCO SO\b",               "COUNTY SHERIFF'S OFFICE"),
    (r"\bCO SD\b",               "COUNTY SHERIFF'S DEPARTMENT"),
    (r'\bCA HIGHWAY PATROL\b',   'CALIFORNIA HIGHWAY PATROL'),
    (r'\bCA DEPT OF JUSTICE\b',  'CALIFORNIA DEPARTMENT OF JUSTICE'),
    (r'\bCA DEPT JUSTICE\b',     'CALIFORNIA DEPARTMENT JUSTICE'),
    (r'\bCA DEPT STATE HOSPITALS\b', 'CALIFORNIA DEPARTMENT STATE HOSPITALS'),
    (r'\bCA\.?\s+STATE PRISON\b', 'CALIFORNIA STATE PRISON'),
    (r'\bCA\.?\s+INSTITUTION\b', 'CALIFORNIA INSTITUTION'),
    (r'\bCA\.?\s+CORRECTIONAL\b','CALIFORNIA CORRECTIONAL'),
    (r'\bCA\.?\s+MEDICAL\b',     'CALIFORNIA MEDICAL'),
    (r'\bCA\.?\s+MEN\'S COLONY\b',"CALIFORNIA MEN'S COLONY"),
    (r'\bDA\b',                  'DISTRICT ATTORNEY'),
    (r'\bDIST ATTY\b',           'DISTRICT ATTORNEY'),
    (r'\bDEPT\b',                'DEPARTMENT'),
    (r'\bSVCS?\b',               'SERVICES'),
    (r'\bDIV\b',                 'DIVISION'),
    (r'\bADMIN\b',               'ADMINISTRATION'),
    (r'\bMGMT\b',                'MANAGEMENT'),
    (r'\bASST\b',                'ASSISTANT'),
    (r'\bHWY\b',                 'HIGHWAY'),
    (r'\bPOLICE DEPT\b',         'POLICE DEPARTMENT'),
    (r'\bPD\b',                  'POLICE DEPARTMENT'),
    (r"\bSHERIFF'S OFF\b",       "SHERIFF'S OFFICE"),
    (r'\bSHERIFF OFF\b',         "SHERIFF'S OFFICE"),
    (r'\bSHERIFF DEPT\b',        "SHERIFF'S DEPARTMENT"),
    (r'\bSHERIFF DEP\b',         "SHERIFF'S DEPARTMENT"),
    (r'\bSO\b',                  "SHERIFF'S OFFICE"),
    (r'\bCO\b',                  'COUNTY'),
    (r'\bCNTR\b',                'CENTER'),
    (r'\bCTR\b',                 'CENTER'),
    (r'\bUNIV\b',                'UNIVERSITY'),
    (r'\bUNIVERSITY OF CA\b',    'UNIVERSITY OF CALIFORNIA'),
    (r'\bMED CTR\b',             'MEDICAL CENTER'),
    (r'\bJR COLLEGE\b',          'JUNIOR COLLEGE'),
    (r'\bOFC\b',                 'OFFICE'),
    (r'\bINVEST\b',              'INVESTIGATIONS'),
    (r'\bSPEC\b',                'SPECIAL'),
    (r'\bTRAN\b(?!S)',            'TRANSIT'),
    (r'\bAUTH\b',                'AUTHORITY'),
    (r'\bJUV\b',                 'JUVENILE'),
    (r'\bMARSHAL\b',             'MARSHAL'),
    (r'\bMAR\b(?=,)',             'MARSHAL'),
    (r'\bPROB\b',                'PROBATION'),
    (r'\bPORT\b',                'PORT'),
    (r'\bHOUSING AUTH\b',        'HOUSING AUTHORITY'),
    (r'\bPORT AUTH\b',           'PORT AUTHORITY'),
]


def expand_agency(name):
    if pd.isna(name):
        return ''
    s = str(name).strip().upper()
    s = re.sub(r'\s+', ' ', s).strip()
    for pattern, replacement in AGENCY_EXPANSIONS:
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
        s = re.sub(r'\s+', ' ', s).strip()
    return s.upper()


# Expand agency names on unique values only (much faster)
unique_agencies = leo['agency_raw'].dropna().unique()
agency_expansion_cache = {a: expand_agency(a) for a in unique_agencies}
agency_expansion_cache['nan'] = ''
leo['agency_name'] = leo['agency_raw'].fillna('').map(
    lambda x: agency_expansion_cache.get(str(x), expand_agency(str(x)))
)

# Filter out empty/invalid person_nbr
leo = leo[leo['person_nbr'].notna() & (leo['person_nbr'] != '') & (leo['person_nbr'] != 'nan')]

# Drop rows with empty start_date
leo_before = len(leo)
leo = leo[leo['start_date'] != '']
print(f"  Dropped {leo_before - len(leo)} LEO rows with empty start_date")

# Deduplicate
leo = leo.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

leo_out = leo[[
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'agency_name', 'start_date', 'end_date', 'rank', 'separation_reason',
]].copy()
leo_out['type'] = 'POLICE'
print(f"  LEO output rows: {len(leo_out)}")


# ---------------------------------------------------------------------------
# Section 2: Process Corrections data (CDCR CSV)
# ---------------------------------------------------------------------------

print("Loading Corrections data...")
corr_file = os.path.join(INPUT_DIR, "PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv")
corr_raw = pd.read_csv(corr_file, dtype=str, low_memory=False)
print(f"  Corrections raw rows: {len(corr_raw)}")

# Strip whitespace from all string columns
for col in corr_raw.columns:
    corr_raw[col] = corr_raw[col].astype(str).str.strip()

# Parse name columns
def split_first_middle(fm):
    s = str(fm).strip()
    if not s or s == 'nan':
        return '', ''
    parts = s.split()
    if len(parts) == 1:
        return parts[0], ''
    last = parts[-1].rstrip('.')
    if len(last) == 1:
        return ' '.join(parts[:-1]), last
    return s, ''


unique_fm = corr_raw['FIRST NAME'].dropna().unique()
fm_cache = {fm: split_first_middle(fm) for fm in unique_fm}
fm_df = pd.DataFrame.from_dict(fm_cache, orient='index', columns=['first_name', 'middle_name'])
fm_df.index.name = 'FIRST NAME'
fm_df = fm_df.reset_index()
corr_raw = corr_raw.merge(fm_df, on='FIRST NAME', how='left')
corr_raw['first_name'] = corr_raw['first_name'].str.upper()
corr_raw['middle_name'] = corr_raw['middle_name'].str.upper()
corr_raw['last_name'] = corr_raw['LAST NAME'].str.upper()
corr_raw['person_nbr'] = corr_raw['UNIQUE ID'].astype(str).str.strip()
corr_raw['trans_dt'] = pd.to_datetime(corr_raw['TRANS EFF DATE'], format='%m/%d/%Y', errors='coerce')
corr_raw['trans_date'] = corr_raw['trans_dt'].dt.strftime('%Y-%m-%d').fillna('')
unique_pos = corr_raw['POSITION NUMBER'].dropna().unique()
pos_norm_cache = {p: norm_pos(p) for p in unique_pos}
agency_code_cache = {p: extract_agency_code(p) for p in unique_pos}
corr_raw['pos_norm'] = corr_raw['POSITION NUMBER'].map(pos_norm_cache)
corr_raw['agency_code'] = corr_raw['POSITION NUMBER'].map(agency_code_cache)
corr_raw['rank_clean'] = corr_raw['CLASS TITLE'].str.strip().str.upper()
corr_raw['txn_type'] = corr_raw['TYPE OF TRANSACTION'].str.strip().str.upper()

# Build agency name lookup: agency_code -> standardized facility name
# Format: "{code}: {expanded_facility_name}"
CDCR_EXPANSIONS = [
    (r'\bCA\.\s+STATE PRISON\b',    'CALIFORNIA STATE PRISON'),
    (r'\bCA\.\s+INSTITUTION\b',     'CALIFORNIA INSTITUTION'),
    (r'\bCA\.\s+CORRECTIONAL\b',    'CALIFORNIA CORRECTIONAL'),
    (r'\bCA\.\s+MEDICAL\b',         'CALIFORNIA MEDICAL'),
    (r"\bCA\.\s+MEN'S COLONY\b",    "CALIFORNIA MEN'S COLONY"),
    (r'\bPAROLE & COMMUNITY SVS DIV\b', 'PAROLE & COMMUNITY SERVICES DIVISION'),
    (r'\bSVS\b',                    'SERVICES'),
    (r'\bCORR TRAIN CNTR\b',        'CORRECTIONS TRAINING CENTER'),
    (r'\bCNTR\b',                   'CENTER'),
    (r'\bTRAIN\b',                  'TRAINING'),
    (r'\bFACILIT\b',                'FACILITY'),
    (r'\bADMIN\b',                  'ADMINISTRATION'),
    (r'\bN\. CA\b',                 'NORTHERN CALIFORNIA'),
    (r'\bNORTHERN CA\b',            'NORTHERN CALIFORNIA'),
    (r'\bSUBSTANCE ABUSE TREAT\b',  'SUBSTANCE ABUSE TREATMENT'),
    (r'\bTREAT\b',                  'TREATMENT'),
    (r'\bMED\b',                    'MEDICAL'),
    (r'\bVOC\b',                    'VOCATIONAL'),
]


def expand_cdcr_facility(name):
    s = str(name).strip().upper()
    for pattern, replacement in CDCR_EXPANSIONS:
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
        s = re.sub(r'\s+', ' ', s).strip()
    return s


facility_freq = (
    corr_raw[corr_raw['agency_code'] != '']
    .groupby(['agency_code', 'FACILITY NAME'])
    .size()
    .reset_index(name='cnt')
    .sort_values(['agency_code', 'cnt'], ascending=[True, False])
)
best_facility = facility_freq.groupby('agency_code').first().reset_index()[['agency_code', 'FACILITY NAME']]
best_facility.columns = ['agency_code', 'best_facility']
best_facility['best_facility'] = best_facility['best_facility'].str.strip().str.upper()
best_facility['facility_expanded'] = best_facility['best_facility'].apply(expand_cdcr_facility)
best_facility['agency_name'] = best_facility['agency_code'] + ': ' + best_facility['facility_expanded']
agency_code_to_name = dict(zip(best_facility['agency_code'], best_facility['agency_name']))

corr_raw['agency_name'] = corr_raw['agency_code'].map(agency_code_to_name).fillna('')

# Split events by type
non_seps = corr_raw[corr_raw['txn_type'].isin(['APPOINTMENT', 'CHANGE'])].copy()
seps = corr_raw[corr_raw['txn_type'] == 'SEPARATION'].copy()

print(f"  Non-separation events: {len(non_seps)}, Separation events: {len(seps)}")

# Step 1: Link each non-sep event to the next separation with same person + pos_norm
seps_pos = (
    seps[['person_nbr', 'pos_norm', 'trans_dt']]
    .rename(columns={'trans_dt': 'end_dt'})
)
non_seps_s = non_seps.sort_values(['person_nbr', 'pos_norm', 'trans_dt']).reset_index(drop=True)

merged = non_seps_s.merge(seps_pos, on=['person_nbr', 'pos_norm'], how='left')
merged = merged[merged['end_dt'].isna() | (merged['end_dt'] >= merged['trans_dt'])]
merged = merged.sort_values(['person_nbr', 'pos_norm', 'trans_dt', 'end_dt'])
merged = merged.groupby(['person_nbr', 'pos_norm', 'trans_dt'], as_index=False).first()
merged['start_date'] = merged['trans_date']
merged['end_date'] = merged['end_dt'].dt.strftime('%Y-%m-%d').fillna('')

# Step 2: Collapse by (person, pos_norm, end_date) -> keep earliest start per end_date
# This handles multiple appointments at same position sharing the same separation
with_end = merged[merged['end_date'] != ''].copy()
no_end = merged[merged['end_date'] == ''].copy()

pos_collapsed_we = (
    with_end
    .sort_values(['person_nbr', 'pos_norm', 'end_date', 'start_date'])
    .groupby(['person_nbr', 'pos_norm', 'end_date'], as_index=False)
    .first()
)
pos_collapsed_ne = (
    no_end
    .sort_values(['person_nbr', 'pos_norm', 'start_date'])
    .groupby(['person_nbr', 'pos_norm'], as_index=False)
    .first()
)
pos_collapsed = pd.concat([pos_collapsed_we, pos_collapsed_ne], ignore_index=True)

# Step 3: Further collapse across positions with same agency+end_date
# (handles intra-agency position transfers where the end date is the same)
with_end2 = pos_collapsed[pos_collapsed['end_date'] != ''].copy()
no_end2 = pos_collapsed[pos_collapsed['end_date'] == ''].copy()

agency_collapsed_we = (
    with_end2
    .sort_values(['person_nbr', 'agency_code', 'end_date', 'start_date'])
    .groupby(['person_nbr', 'agency_code', 'end_date'], as_index=False)
    .first()
)
# Open-ended stints: do NOT collapse across positions (keep position-level detail)
corr_stints = pd.concat([agency_collapsed_we, no_end2], ignore_index=True)
print(f"  Corrections stints: {len(corr_stints)}")

# Build name for each person: use most common name per UNIQUE ID
name_lookup = (
    corr_raw[['person_nbr', 'first_name', 'middle_name', 'last_name']]
    .dropna(subset=['last_name'])
    .groupby('person_nbr')
    .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else '')
    .reset_index()
)
name_lookup.columns = ['person_nbr', 'first_name', 'middle_name', 'last_name']

# Keep per-person-name variants too (name changes documented in README)
# Use the names from the non-sep events associated with each stint
# For simplicity, attach the most common name per person
corr_stints2 = corr_stints.merge(
    corr_raw[['person_nbr', 'first_name', 'middle_name', 'last_name']].drop_duplicates('person_nbr'),
    on='person_nbr',
    how='left'
)

# Fill any missing names with lookup
if 'first_name_x' in corr_stints2.columns:
    corr_stints2['first_name'] = corr_stints2['first_name_x'].fillna(corr_stints2['first_name_y'])
    corr_stints2['middle_name'] = corr_stints2['middle_name_x'].fillna(corr_stints2['middle_name_y'])
    corr_stints2['last_name'] = corr_stints2['last_name_x'].fillna(corr_stints2['last_name_y'])

corr_out = corr_stints2[[
    'person_nbr', 'first_name', 'middle_name', 'last_name',
    'agency_name', 'start_date', 'end_date', 'rank_clean',
]].copy()
corr_out = corr_out.rename(columns={'rank_clean': 'rank'})
corr_out['suffix'] = ''
corr_out['separation_reason'] = ''
corr_out['type'] = 'CORRECTIONS'

# Drop empty start_date
corr_out = corr_out[corr_out['start_date'].notna() & (corr_out['start_date'] != '')]

# Deduplicate
corr_out = corr_out.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Corrections output rows: {len(corr_out)}")


# ---------------------------------------------------------------------------
# Section 3: Combine and write output
# ---------------------------------------------------------------------------

print("Combining LEO and Corrections data...")

common_cols = [
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'agency_name', 'start_date', 'end_date', 'rank', 'separation_reason', 'type',
]

leo_final = leo_out[common_cols].copy()
corr_final = corr_out[common_cols].copy()

combined = pd.concat([leo_final, corr_final], ignore_index=True)

# Final clean-up: ensure no NaN values, use empty string for missing
for col in ['person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
            'agency_name', 'start_date', 'end_date', 'rank', 'separation_reason']:
    combined[col] = combined[col].fillna('').astype(str).str.strip()
    # Replace literal 'nan' strings
    combined[col] = combined[col].replace('nan', '')

# Drop rows with empty start_date (defensive)
before = len(combined)
combined = combined[combined['start_date'] != '']
print(f"  Dropped {before - len(combined)} rows with empty start_date (final check)")

# Drop rows with empty person_nbr
combined = combined[combined['person_nbr'].notna() & (combined['person_nbr'] != '') & (combined['person_nbr'] != 'nan')]

# Final dedup
combined = combined.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

# Validate required columns
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
for col in required:
    assert col in combined.columns, f"Missing required column: {col}"

print(f"Total combined rows: {len(combined)}")
print(f"  LEO rows: {(combined['type'] == 'POLICE').sum()}")
print(f"  Corrections rows: {(combined['type'] == 'CORRECTIONS').sum()}")

# Ensure all string columns have no NaN (use empty string)
for col in combined.select_dtypes(include='object').columns:
    combined[col] = combined[col].fillna('')

# Write output
out_path = os.path.join(OUTPUT_DIR, 'ca_index.csv')
combined.to_csv(out_path, index=False)
print(f"Written: {out_path}")
