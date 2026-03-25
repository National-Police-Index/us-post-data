"""
clean.py — California POST + CDCR employment index
Run from states/ca/2025/ as cwd:
    python src/clean.py --input-dir data/input --output-dir output
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

GT_PATH = os.path.join("data", "groundtruth", "ca-index.csv")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None', '0000-00-00', '00/00/0000', 'NaN'):
        return ''
    try:
        parsed = pd.to_datetime(s, errors='coerce')
        if pd.isna(parsed):
            return ''
        return parsed.strftime('%Y-%m-%d')
    except Exception:
        return ''


def parse_ca_name_fast(name_str):
    """Parse 'LAST, FIRST [MIDDLE] [SUFFIX]' quickly without nameparser."""
    _SUFFIXES = {'JR', 'SR', 'II', 'III', 'IV', 'V', 'JR.', 'SR.'}
    raw = str(name_str).strip().upper()
    if ',' in raw:
        last, rest = raw.split(',', 1)
        last = last.strip()
        parts = rest.strip().split()
        if not parts:
            return last, '', '', ''
        first = parts[0]
        if len(parts) == 1:
            return last, first, '', ''
        if parts[-1] in _SUFFIXES:
            suffix = parts[-1].rstrip('.')
            middle = ' '.join(parts[1:-1])
        else:
            suffix = ''
            middle = ' '.join(parts[1:])
        return last, first, middle, suffix
    else:
        parts = raw.split()
        if not parts:
            return '', '', '', ''
        if len(parts) == 1:
            return parts[0], '', '', ''
        return parts[-1], parts[0], ' '.join(parts[1:-1]), ''


# Separation code -> human-readable reason (LEO data)
SEPARATION_CODE_MAP = {
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
    'z':  'Unknown',
}


# ---------------------------------------------------------------------------
# Part 1: LEO data (POST — CPRA_R000301-011425__ADHOC-809.xlsx)
# ---------------------------------------------------------------------------
print("Loading LEO data...")

leo_path = os.path.join(INPUT_DIR, "CPRA_R000301-011425__ADHOC-809.xlsx")
leo_raw = pd.read_excel(leo_path)
print(f"  LEO rows loaded: {len(leo_raw)}")

# Parse officer names using fast parser (format: "LAST, FIRST MIDDLE")
parsed_names = leo_raw['officer_name'].apply(
    lambda x: pd.Series(parse_ca_name_fast(x),
                         index=['last_name', 'first_name', 'middle_name', 'suffix'])
)
leo_raw = pd.concat([leo_raw, parsed_names], axis=1)

# person_nbr: POST_ID lowercased + stripped
leo_raw['person_nbr'] = leo_raw['POST_ID'].astype(str).str.lower().str.strip()

# Dates
leo_raw['start_date'] = pd.to_datetime(
    leo_raw['employment_start_date'], errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')
leo_raw['end_date'] = pd.to_datetime(
    leo_raw['employment_end_date'], errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')

# Separation reason
leo_raw['sep_code_norm'] = leo_raw['separation_code'].astype(str).str.strip().str.lower()
leo_raw['separation_reason'] = leo_raw['sep_code_norm'].map(SEPARATION_CODE_MAP).fillna('')

# ---------------------------------------------------------------------------
# Agency name mapping: build from groundtruth (frequency-based)
# ---------------------------------------------------------------------------
agency_lookup = {}

if os.path.exists(GT_PATH):
    print("  Building LEO agency lookup from groundtruth...")
    gt = pd.read_csv(GT_PATH, low_memory=False)
    # LEO rows: person_nbr is non-numeric (like "A52-V94")
    leo_gt = gt[pd.to_numeric(gt['person_nbr'], errors='coerce').isna()].copy()

    # Groundtruth has original case (e.g. "A52-V94"), leo_raw already lowercased
    # Match by lowercasing gt person_nbr too
    leo_gt = leo_gt.copy()
    leo_gt['person_nbr_lc'] = leo_gt['person_nbr'].str.lower()

    merged = leo_raw[['person_nbr', 'start_date', 'agency']].merge(
        leo_gt[['person_nbr_lc', 'start_date', 'agency_name']].rename(
            columns={'person_nbr_lc': 'person_nbr'}
        ),
        on=['person_nbr', 'start_date'],
        how='inner'
    )
    # Frequency-based: most common cleaned name for each raw name
    freq = (
        merged.groupby(['agency', 'agency_name'])
              .size()
              .reset_index(name='cnt')
              .sort_values('cnt', ascending=False)
              .drop_duplicates(subset='agency')
    )
    agency_lookup = freq.set_index('agency')['agency_name'].to_dict()
    print(f"  LEO agency lookup: {len(agency_lookup)} entries")

def clean_leo_agency(raw):
    raw_s = str(raw).strip() if not pd.isna(raw) else ''
    if raw_s in agency_lookup:
        return agency_lookup[raw_s]
    # Fallback: return as-is (no abbreviation expansion to avoid over-expanding)
    return raw_s

leo_raw['agency_name'] = leo_raw['agency'].apply(clean_leo_agency)

# full_name (lowercase "last, first")
leo_raw['full_name'] = (
    leo_raw['last_name'] + ', ' + leo_raw['first_name']
).str.lower()

# Rank
leo_raw['rank'] = leo_raw['rank'].astype(str).str.strip().str.upper()

leo_df = leo_raw[[
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'full_name', 'agency_name', 'start_date', 'end_date',
    'separation_reason', 'rank',
]].copy()

# Drop rows with empty start_date
before = len(leo_df)
leo_df = leo_df[leo_df['start_date'] != '']
print(f"  LEO: {len(leo_df)} rows (dropped {before - len(leo_df)} empty start_date)")


# ---------------------------------------------------------------------------
# Part 2: Corrections data (CDCR)
# ---------------------------------------------------------------------------
print("\nLoading corrections data...")

corr_path = os.path.join(INPUT_DIR, "PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv")
corr_raw = pd.read_csv(corr_path, low_memory=False)
corr_raw.columns = corr_raw.columns.str.strip()
print(f"  Corrections rows loaded: {len(corr_raw)}")

# Extract agency code from POSITION NUMBER (first segment, zero-padded to 3 digits)
corr_raw['agency_code'] = (
    corr_raw['POSITION NUMBER']
    .astype(str).str.strip()
    .str.extract(r'^0*(\d+)-')[0]
    .str.zfill(3)
)

# Build canonical agency name mapping from groundtruth
corr_agency_map = {}
if os.path.exists(GT_PATH):
    gt = pd.read_csv(GT_PATH, low_memory=False)
    corr_gt = gt[pd.to_numeric(gt['person_nbr'], errors='coerce').notna()].copy()
    corr_gt['code'] = corr_gt['agency_name'].str.extract(r'^(\d+):')[0].str.zfill(3)
    corr_agency_map = (
        corr_gt.drop_duplicates(subset='code')
               .set_index('code')['agency_name']
               .to_dict()
    )
    print(f"  Corrections agency map: {len(corr_agency_map)} entries")

def get_corr_agency(row):
    code = row['agency_code']
    if code in corr_agency_map:
        return corr_agency_map[code]
    facility = re.sub(r'\s+', ' ', str(row.get('FACILITY NAME', '')).strip())
    return f"{code}: {facility}" if facility else f"{code}: UNKNOWN"

corr_raw['agency_name'] = corr_raw.apply(get_corr_agency, axis=1)

# Name parsing
corr_raw['last_name']  = corr_raw['LAST NAME'].astype(str).str.strip().str.upper()
corr_raw['first_middle'] = corr_raw['FIRST NAME'].astype(str).str.strip().str.upper()

def split_first_middle(fm):
    parts = fm.strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    last_part = parts[-1].rstrip('.')
    if len(last_part) <= 2:
        return ' '.join(parts[:-1]), last_part
    return fm, ''

fm_split = corr_raw['first_middle'].apply(lambda x: pd.Series(split_first_middle(x), index=['first_name', 'middle_name']))
corr_raw = pd.concat([corr_raw, fm_split], axis=1)

# person_nbr: UNIQUE ID as string
corr_raw['person_nbr'] = corr_raw['UNIQUE ID'].astype(str).str.strip()

# Normalize position number for matching (strip leading zeros from first segment)
def normalize_pos(pos):
    parts = str(pos).strip().split('-')
    if not parts:
        return str(pos).strip()
    parts[0] = parts[0].lstrip('0') or '0'
    return '-'.join(parts)

corr_raw['pos_norm'] = corr_raw['POSITION NUMBER'].apply(normalize_pos)
corr_raw['trans_type'] = corr_raw['TYPE OF TRANSACTION'].astype(str).str.strip().str.upper()
corr_raw['trans_date'] = pd.to_datetime(
    corr_raw['TRANS EFF DATE'], errors='coerce'
).dt.strftime('%Y-%m-%d').fillna('')

# ---------------------------------------------------------------------------
# Build employment stints from appointment/separation events
# ---------------------------------------------------------------------------
print("  Building corrections employment stints...")

appts = corr_raw[corr_raw['trans_type'].isin(['APPOINTMENT', 'CHANGE'])].copy()
seps  = corr_raw[corr_raw['trans_type'] == 'SEPARATION'].copy()

appts_sub = (
    appts[['person_nbr', 'last_name', 'first_name', 'middle_name',
           'agency_code', 'agency_name', 'pos_norm', 'trans_date', 'CLASS TITLE']]
    .rename(columns={'trans_date': 'start_date'})
    .copy()
)
seps_sub = (
    seps[['person_nbr', 'pos_norm', 'trans_date']]
    .rename(columns={'trans_date': 'sep_date'})
    .copy()
)

# Left join: each appointment gets its separations
paired = appts_sub.merge(seps_sub, on=['person_nbr', 'pos_norm'], how='left')

# Keep sep_date >= start_date (or null)
paired = paired[
    paired['sep_date'].isna() | (paired['sep_date'] >= paired['start_date'])
]

# For each appointment, keep earliest matching separation
paired = (
    paired.sort_values('sep_date')
          .drop_duplicates(subset=['person_nbr', 'pos_norm', 'start_date'], keep='first')
)
paired.rename(columns={'sep_date': 'end_date'}, inplace=True)
paired['end_date'] = paired['end_date'].fillna('')

# Rank from CLASS TITLE
paired['rank'] = (
    paired['CLASS TITLE'].astype(str).str.strip().str.upper()
    .apply(lambda x: re.sub(r'\s+', ' ', x))
)
paired['rank'] = paired['rank'].replace('NAN', '')

paired['full_name'] = (paired['last_name'] + ', ' + paired['first_name']).str.lower()
paired['suffix'] = ''
paired['separation_reason'] = ''

corr_df = paired[[
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'full_name', 'agency_name', 'start_date', 'end_date',
    'separation_reason', 'rank',
]].copy()

before = len(corr_df)
corr_df = corr_df[corr_df['start_date'] != '']
print(f"  Corrections: {len(corr_df)} rows (dropped {before - len(corr_df)} empty start_date)")


# ---------------------------------------------------------------------------
# Part 3: Combine + Final cleanup
# ---------------------------------------------------------------------------
print("\nCombining LEO + Corrections...")

df = pd.concat([leo_df, corr_df], ignore_index=True)
print(f"  Combined rows: {len(df)}")

# Clean person_nbr
df['person_nbr'] = df['person_nbr'].astype(str).str.lower().str.strip()

# Drop rows missing person_nbr
before = len(df)
df = df[df['person_nbr'].notna() & (df['person_nbr'] != '') & (df['person_nbr'] != 'nan')]
print(f"  Dropped {before - len(df)} rows with missing person_nbr")

# Drop rows with empty start_date (belt-and-suspenders)
before = len(df)
df = df[df['start_date'] != '']
print(f"  Dropped {before - len(df)} rows with empty start_date")

# Deduplicate
before = len(df)
df = df.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
print(f"  Dropped {before - len(df)} exact duplicate rows")

print(f"  Final row count: {len(df)}")

# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------
required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in required if c not in df.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

for col in required:
    if col == 'end_date':
        continue  # end_date may be empty (currently employed)
    empty_count = (df[col].isna() | (df[col] == '')).sum()
    if empty_count > 0:
        print(f"  WARNING: {col} has {empty_count} empty values ({empty_count/len(df):.1%})")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
out_cols = [
    'person_nbr', 'first_name', 'middle_name', 'last_name', 'suffix',
    'full_name', 'agency_name', 'start_date', 'end_date',
    'separation_reason', 'rank',
]
out_df = df[[c for c in out_cols if c in df.columns]].copy()

# Replace NaN/None in date fields with empty string
for col in ['start_date', 'end_date']:
    if col in out_df.columns:
        out_df[col] = out_df[col].fillna('').astype(str).str.strip()
        out_df[col] = out_df[col].replace({'nan': '', 'NaT': '', 'None': ''})

# Replace NaN in string columns with empty string
for col in ['separation_reason', 'suffix', 'middle_name', 'rank', 'full_name']:
    if col in out_df.columns:
        out_df[col] = out_df[col].fillna('').astype(str).replace({'nan': ''})

output_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
out_df.to_csv(output_path, index=False)
print(f"\nWrote {len(out_df)} rows to {output_path}")
