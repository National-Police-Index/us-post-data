"""
Georgia POST Data Cleaning Script — 2025
Produces:
  - output/ga_index.csv
  - output/ga-discipline_index.csv
"""

import argparse
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Clean Georgia POST data")
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ('nan', 'NaT', 'None', '0000-00-00', '00/00/0000'):
        return ''
    try:
        return pd.to_datetime(s, errors='coerce').strftime('%Y-%m-%d')
    except Exception:
        return ''


def safe_date_vec(series):
    """Vectorized version of safe_date for Series."""
    s = series.astype(str).str.strip()
    invalid = s.isin(['', 'nan', 'NaT', 'None', '0000-00-00', '00/00/0000'])
    result = pd.to_datetime(s, errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
    result = result.where(~invalid, '')
    return result


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

def load_data(input_dir):
    emp = pd.read_csv(
        os.path.join(input_dir, "officer_employment.csv"),
        dtype=str,
    )
    officer = pd.read_csv(
        os.path.join(input_dir, "officer_data.csv"),
        dtype=str,
    )
    violations = pd.read_csv(
        os.path.join(input_dir, "officer_violations.csv"),
        dtype=str,
    )
    sanctions = pd.read_csv(
        os.path.join(input_dir, "officer_sanctions.csv"),
        dtype=str,
    )
    investigations = pd.read_csv(
        os.path.join(input_dir, "officer_investigations.csv"),
        dtype=str,
    )
    return emp, officer, violations, sanctions, investigations


# ---------------------------------------------------------------------------
# Build employment index
# ---------------------------------------------------------------------------

def build_employment_index(emp, officer):
    """
    Join officer_employment + officer_data on OKEY.
    Returns DataFrame with standard schema columns.

    NOTE: The groundtruth keeps the original AGENCY string (with G-code prefix)
    and keeps '0000-00-00' for end_date (currently employed).
    """
    # --- Rename employment columns ---
    emp = emp.rename(columns={
        'OKEY': 'person_nbr',
        'NAME': 'full_name_raw',
        'AGENCY': 'agency_name',
        'RANK': 'rank',
        'STATUS': 'employment_status',
        'START DATE': 'start_date',
        'END DATE': 'end_date',
    })

    # --- Rename officer demographic columns ---
    officer = officer.rename(columns={
        'OKEY': 'person_nbr',
        'LAST NAME': 'last_name',
        'FIRST NAME': 'first_name',
        'MIDDLE': 'middle_name',
        'SUFFIX': 'suffix',
        'YOB': 'year_of_birth',
        'SEX': 'sex',
        'RACE': 'race',
    })

    # --- Clean person_nbr ---
    emp['person_nbr'] = emp['person_nbr'].astype(str).str.lower().str.strip()
    officer['person_nbr'] = officer['person_nbr'].astype(str).str.lower().str.strip()

    # --- Merge ---
    merged = emp.merge(
        officer[['person_nbr', 'last_name', 'first_name', 'middle_name',
                 'suffix', 'year_of_birth', 'race', 'sex']],
        on='person_nbr',
        how='left',
    )

    # --- Clean name fields ---
    for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
        merged[col] = merged[col].fillna('').str.strip()

    # --- Build full_name: "last, first middle" lowercase (vectorized) ---
    first_mid = merged['first_name'].str.strip()
    has_mid = merged['middle_name'].str.strip() != ''
    first_mid = first_mid.where(~has_mid, first_mid + ' ' + merged['middle_name'].str.strip())
    has_suf = merged['suffix'].str.strip() != ''
    base = merged['last_name'].str.strip() + ', ' + first_mid
    base = base.where(~has_suf, base + ' ' + merged['suffix'].str.strip())
    merged['full_name'] = base.str.lower()

    # --- Clean dates ---
    # For the index: keep start_date as YYYY-MM-DD (drop if empty)
    merged['start_date'] = safe_date_vec(merged['start_date'])

    # end_date: leave '0000-00-00' as-is per groundtruth; convert others to YYYY-MM-DD
    def clean_end_date_index_vec(series):
        s = series.astype(str).str.strip()
        # Keep '0000-00-00' as-is
        keep_raw = s == '0000-00-00'
        invalid = s.isin(['', 'nan', 'NaT', 'None'])
        result = pd.to_datetime(s, errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
        result = result.where(~invalid, '')
        result = result.where(~keep_raw, '0000-00-00')
        return result

    merged['end_date'] = clean_end_date_index_vec(merged['end_date'])

    # --- Drop rows with empty start_date ---
    before = len(merged)
    merged = merged[merged['start_date'] != ''].copy()
    print(f"  Dropped {before - len(merged)} rows with empty start_date")

    # --- Drop rows with missing person_nbr ---
    merged = merged[merged['person_nbr'].notna() & (merged['person_nbr'] != '')].copy()

    # --- Deduplicate ---
    dupes = merged.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
    if dupes.any():
        print(f"  Dropping {dupes.sum()} duplicate rows")
        merged = merged.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

    # --- Select and order columns ---
    cols = [
        'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
        'start_date', 'end_date',
        'last_name', 'first_name', 'middle_name', 'suffix',
        'year_of_birth', 'race', 'sex',
    ]
    merged = merged[[c for c in cols if c in merged.columns]]

    return merged


# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------

def build_discipline_index(violations, sanctions, investigations, emp, officer):
    """
    Join violations + sanctions on CASE (inner join).
    Attach employment context and demographic info.
    """
    # --- Normalize CASE to zero-padded 10-char string (matching GT format) ---
    # Some CASE values have internal spaces: '005 360711' -> strip & zero-pad to 10
    def normalize_case(s):
        s = str(s).strip().replace(' ', '')  # strip internal spaces
        return s.zfill(10) if s.isdigit() else s

    violations['case_id'] = violations['CASE'].apply(normalize_case)
    sanctions['case_id'] = sanctions['CASE'].apply(normalize_case)

    # --- Normalize OKEY to lowercase person_nbr ---
    violations['person_nbr'] = violations['OKEY'].astype(str).str.lower().str.strip()
    sanctions['person_nbr'] = sanctions['OKEY'].astype(str).str.lower().str.strip()

    # --- Rename violation/sanction columns ---
    violations = violations.rename(columns={
        'VIOLATION': 'violation',
        'VIOLATION DATE': 'violation_date',
    })
    sanctions = sanctions.rename(columns={
        'SANCTION': 'sanction',
        'DATE': 'sanction_date',
    })

    # --- Clean dates in violations/sanctions ---
    violations['violation_date'] = safe_date_vec(violations['violation_date'])
    sanctions['sanction_date'] = safe_date_vec(sanctions['sanction_date'])

    # --- Title-case violation and sanction ---
    violations['violation'] = violations['violation'].astype(str).str.strip().str.title()
    sanctions['sanction'] = sanctions['sanction'].astype(str).str.strip().str.title()

    # --- Inner join violations + sanctions on case_id + person_nbr ---
    disc = violations[['case_id', 'person_nbr', 'violation', 'violation_date']].merge(
        sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
        on=['case_id', 'person_nbr'],
        how='inner',
    )

    # --- Deduplicate: one row per (case_id, person_nbr, violation, sanction) ---
    # Keep the most recent sanction_date when there are exact dupes
    disc = (
        disc.sort_values('sanction_date', ascending=False)
        .drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction'])
    )

    # --- Prepare employment table for joining ---
    emp2 = emp.rename(columns={
        'OKEY': 'person_nbr',
        'AGENCY': 'agency_name',
        'RANK': 'rank',
        'STATUS': 'employment_status',
        'START DATE': 'start_date',
        'END DATE': 'end_date',
    })
    emp2['person_nbr'] = emp2['person_nbr'].astype(str).str.lower().str.strip()
    # agency_name: lowercase (as per groundtruth for discipline index)
    emp2['agency_name'] = emp2['agency_name'].astype(str).str.lower()
    # clean dates for employment join
    emp2['start_date'] = safe_date_vec(emp2['start_date'])
    emp2['end_date'] = safe_date_vec(emp2['end_date'])

    # --- Join disc to employment on person_nbr ---
    disc_emp = disc.merge(
        emp2[['person_nbr', 'agency_name', 'rank', 'employment_status', 'start_date', 'end_date']],
        on='person_nbr',
        how='left',
    )

    # --- Score employment periods: prefer period containing violation_date ---
    # Vectorized scoring
    vdate = pd.to_datetime(disc_emp['violation_date'], errors='coerce')
    sdate = pd.to_datetime(disc_emp['start_date'], errors='coerce')
    edate = pd.to_datetime(disc_emp['end_date'].replace('', pd.NaT), errors='coerce')
    edate = edate.fillna(pd.Timestamp('2099-12-31'))

    inside = (sdate <= vdate) & (vdate <= edate)
    dist_s = (vdate - sdate).dt.days.abs()
    dist_e = (vdate - edate).dt.days.abs()
    outside_score = dist_s.combine(dist_e, min)

    disc_emp['_score'] = outside_score
    disc_emp.loc[inside, '_score'] = 0
    disc_emp.loc[vdate.isna() | sdate.isna(), '_score'] = 9999

    # --- Keep best employment period per (case_id, person_nbr, violation, sanction) ---
    disc_emp = disc_emp.sort_values(['_score', 'start_date'], ascending=[True, False])
    disc_emp = disc_emp.drop_duplicates(
        subset=['case_id', 'person_nbr', 'violation', 'sanction']
    )
    disc_emp = disc_emp.drop(columns=['_score'])

    # --- Drop rows with no employment match (empty start_date) ---
    before = len(disc_emp)
    disc_emp = disc_emp[disc_emp['start_date'].fillna('') != ''].copy()
    print(f"  Discipline: dropped {before - len(disc_emp)} rows with empty start_date")

    # --- Prepare officer demographics ---
    officer2 = officer.rename(columns={
        'OKEY': 'person_nbr',
        'LAST NAME': 'last_name',
        'FIRST NAME': 'first_name',
        'MIDDLE': 'middle_name',
        'SUFFIX': 'suffix',
        'YOB': 'year_of_birth',
        'SEX': 'sex',
        'RACE': 'race',
    })
    officer2['person_nbr'] = officer2['person_nbr'].astype(str).str.lower().str.strip()

    # --- Merge demographics ---
    disc_emp = disc_emp.merge(
        officer2[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
        on='person_nbr',
        how='left',
    )

    # --- Clean name fields ---
    for col in ['last_name', 'first_name', 'middle_name', 'suffix']:
        disc_emp[col] = disc_emp[col].fillna('').str.strip().str.lower()

    # --- Build full_name lowercase (vectorized) ---
    first_mid = disc_emp['first_name'].str.strip()
    has_mid = disc_emp['middle_name'].str.strip() != ''
    first_mid = first_mid.where(~has_mid, first_mid + ' ' + disc_emp['middle_name'].str.strip())
    has_suf = disc_emp['suffix'].str.strip() != ''
    base = disc_emp['last_name'].str.strip() + ', ' + first_mid
    base = base.where(~has_suf, base + ' ' + disc_emp['suffix'].str.strip())
    disc_emp['full_name'] = base

    # --- Lowercase remaining string columns ---
    disc_emp['rank'] = disc_emp['rank'].fillna('').str.lower()
    disc_emp['race'] = disc_emp['race'].fillna('')
    disc_emp['sex'] = disc_emp['sex'].fillna('')
    disc_emp['year_of_birth'] = disc_emp['year_of_birth'].fillna('')

    # --- Select and order columns ---
    cols = [
        'case_id', 'person_nbr', 'sanction', 'sanction_date',
        'violation', 'violation_date',
        'full_name', 'agency_name', 'rank', 'start_date', 'end_date',
        'last_name', 'first_name', 'middle_name', 'suffix',
        'year_of_birth', 'race', 'sex',
    ]
    disc_emp = disc_emp[[c for c in cols if c in disc_emp.columns]]

    return disc_emp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir

    os.makedirs(output_dir, exist_ok=True)

    print("Loading raw files...")
    emp, officer, violations, sanctions, investigations = load_data(input_dir)
    print(f"  Employment rows: {len(emp)}")
    print(f"  Officer rows: {len(officer)}")
    print(f"  Violations rows: {len(violations)}")
    print(f"  Sanctions rows: {len(sanctions)}")

    # --- Employment Index ---
    print("\nBuilding employment index...")
    index_df = build_employment_index(emp.copy(), officer.copy())
    print(f"  Employment index rows: {len(index_df)}")

    # Validate required columns
    required = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
    missing = [c for c in required if c not in index_df.columns]
    assert not missing, f"Missing required columns: {missing}"
    assert (index_df['start_date'] != '').all(), "start_date must not be empty"
    print("  Employment index validation passed.")

    index_out = os.path.join(output_dir, 'ga_index.csv')
    index_df.to_csv(index_out, index=False)
    print(f"  Written: {index_out}")

    # --- Discipline Index ---
    print("\nBuilding discipline index...")
    disc_df = build_discipline_index(
        violations.copy(), sanctions.copy(), investigations.copy(),
        emp.copy(), officer.copy()
    )
    print(f"  Discipline index rows: {len(disc_df)}")

    disc_out = os.path.join(output_dir, 'ga-discipline_index.csv')
    disc_df.to_csv(disc_out, index=False)
    print(f"  Written: {disc_out}")

    print("\nDone.")


if __name__ == '__main__':
    main()
