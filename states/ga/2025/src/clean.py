"""
Georgia POST data cleaning script.
Produces:
  - ga_index.csv          (employment index)
  - ga-discipline_index.csv  (discipline index)
"""

import argparse
import os
import re
import pandas as pd


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Clean GA POST data")
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def clean_date_series(series):
    """Vectorized date cleaning. Returns a Series of 'YYYY-MM-DD', '0000-00-00', or ''."""
    s = series.astype(str).str.strip()
    result = pd.Series('', index=series.index, dtype=str)
    sentinel_mask = s == '0000-00-00'
    result[sentinel_mask] = '0000-00-00'
    parse_mask = ~sentinel_mask & s.notna() & ~s.isin(['', 'nan', 'NaT', 'None'])
    to_parse = s[parse_mask]
    # Try to parse normally
    parsed = pd.to_datetime(to_parse, format='%Y-%m-%d', errors='coerce')
    valid_idx = parsed.dropna().index
    result[valid_idx] = parsed[valid_idx].dt.strftime('%Y-%m-%d')
    # For values that look like YYYY-MM-DD but pandas couldn't parse
    # (e.g. month=00, year=0018), preserve them as-is rather than dropping
    still_empty = parse_mask & (result == '')
    looks_like_date = s[still_empty].str.match(r'^\d{4}-\d{2}-\d{2}$')
    preserve_idx = looks_like_date[looks_like_date].index
    result[preserve_idx] = s[preserve_idx]
    return result


NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}


def is_valid_agency(name):
    """Return True if the name is a real agency (not an admin placeholder)."""
    if not name or pd.isna(name):
        return False
    return name.strip().lower() not in NON_AGENCY_VALUES



# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

def load_data(input_dir):
    emp = pd.read_csv(
        os.path.join(input_dir, "officer_employment.csv"),
        dtype=str,
        keep_default_na=False,
    )
    officers = pd.read_csv(
        os.path.join(input_dir, "officer_data.csv"),
        dtype=str,
        keep_default_na=False,
    )
    violations = pd.read_csv(
        os.path.join(input_dir, "officer_violations.csv"),
        dtype=str,
        keep_default_na=False,
    )
    sanctions = pd.read_csv(
        os.path.join(input_dir, "officer_sanctions.csv"),
        dtype=str,
        keep_default_na=False,
    )
    return emp, officers, violations, sanctions


# ---------------------------------------------------------------------------
# Build employment index
# ---------------------------------------------------------------------------

def build_employment_index(emp, officers):
    # --- Rename employment columns ---
    emp = emp.rename(columns={
        'OKEY': 'person_nbr',
        'NAME': 'raw_name',
        'AGENCY': 'agency_name',
        'RANK': 'rank',
        'STATUS': 'employment_status',
        'START DATE': 'start_date',
        'END DATE': 'end_date',
    })

    # --- Rename officer demographics columns ---
    officers = officers.rename(columns={
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
    emp['person_nbr'] = emp['person_nbr'].str.lower().str.strip()
    officers['person_nbr'] = officers['person_nbr'].str.lower().str.strip()

    # --- Merge employment + demographics ---
    df = emp.merge(
        officers[['person_nbr', 'last_name', 'first_name', 'middle_name',
                  'suffix', 'year_of_birth', 'race', 'sex']],
        on='person_nbr',
        how='left',
    )

    # --- Lowercase name columns to match groundtruth ---
    for col in ('last_name', 'first_name', 'middle_name', 'suffix'):
        df[col] = df[col].str.lower().str.strip()

    # --- Build full_name: "last_name, first_name [middle] [suffix]" lowercase ---
    def make_full_name(row):
        parts = [row['first_name']]
        if row.get('middle_name', ''):
            parts.append(row['middle_name'])
        first_part = ' '.join(p for p in parts if p)
        last_part = row['last_name']
        result = f"{last_part}, {first_part}" if first_part else last_part
        if row.get('suffix', ''):
            result = f"{result} {row['suffix']}"
        return result.strip()

    df['full_name'] = df.apply(make_full_name, axis=1)

    # --- Clean dates ---
    # end_date: keep 0000-00-00 as-is (groundtruth preserves it)
    df['start_date'] = clean_date_series(df['start_date'])
    df['end_date'] = clean_date_series(df['end_date'])

    # --- Filter out rows with empty start_date ---
    df = df[df['start_date'] != '']

    # --- Drop duplicates ---
    df = df.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])

    # --- Select and order output columns ---
    output_cols = [
        'person_nbr', 'full_name', 'agency_name', 'rank', 'employment_status',
        'start_date', 'end_date', 'last_name', 'first_name', 'middle_name',
        'suffix', 'year_of_birth', 'race', 'sex',
    ]
    df = df[output_cols]

    return df



# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------

def build_discipline_index(violations, sanctions, emp_df, officers):
    # --- Rename violations ---
    violations = violations.rename(columns={
        'CASE': 'case_id',
        'OKEY': 'person_nbr',
        'NAME': 'raw_name',
        'VIOLATION': 'violation',
        'VIOLATION DATE': 'violation_date',
    })
    violations['person_nbr'] = violations['person_nbr'].str.lower().str.strip()
    violations['violation_date'] = clean_date_series(violations['violation_date'])

    # --- Rename sanctions ---
    sanctions = sanctions.rename(columns={
        'CASE': 'case_id',
        'OKEY': 'person_nbr',
        'NAME': 'raw_name',
        'SANCTION': 'sanction',
        'DATE': 'sanction_date',
    })
    sanctions['person_nbr'] = sanctions['person_nbr'].str.lower().str.strip()
    sanctions['sanction_date'] = clean_date_series(sanctions['sanction_date'])

    # --- Inner join violations × sanctions on case_id + person_nbr (cartesian per case/person) ---
    # This produces one row per (violation, sanction) combination within a case.
    disc = violations.merge(
        sanctions[['case_id', 'person_nbr', 'sanction', 'sanction_date']],
        on=['case_id', 'person_nbr'],
        how='inner',
    )

    # --- Deduplicate on (case_id, person_nbr, violation, sanction, sanction_date) ---
    # Include sanction_date because the same sanction can appear on different dates
    disc = disc.drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction',
                                        'sanction_date'])

    # --- Title-case violation and sanction to match groundtruth format ---
    disc['violation'] = disc['violation'].str.title()
    disc['sanction'] = disc['sanction'].str.title()

    # --- Attach employment context ---
    # emp_df has already-cleaned columns; we need raw employment for matching
    # Use a copy with only the columns we need
    emp_for_join = emp_df[['person_nbr', 'agency_name', 'rank', 'start_date', 'end_date']].copy()

    disc = disc.merge(emp_for_join, on='person_nbr', how='left')

    # --- Score employment periods by how well violation_date falls within them ---
    # Vectorized scoring to avoid slow row-by-row apply on a large cartesian product

    def to_days(series):
        """Convert a string date series to float days since epoch; invalid → NaN."""
        s = series.copy().astype(str)
        s[s.isin(['0000-00-00', '', 'nan', 'NaT', 'None'])] = ''
        parsed = pd.to_datetime(s.replace('', pd.NaT), format='%Y-%m-%d', errors='coerce')
        # days since epoch (integer-compatible)
        return (parsed - pd.Timestamp('1970-01-01')).dt.days.astype(float)

    v_days = to_days(disc['violation_date'])
    s_days = to_days(disc['start_date'])
    e_days = to_days(disc['end_date'])

    # Default score = 1 (unknown violation date)
    score = pd.Series(1, index=disc.index, dtype=float)

    has_v = v_days.notna()
    has_s = s_days.notna()
    has_e = e_days.notna()

    # No start → worst match
    score[~has_s] = 999999

    # Has start, no end (open-ended) → 0 if v >= s, else distance
    mask_open = has_v & has_s & ~has_e
    score[mask_open] = (s_days[mask_open] - v_days[mask_open]).clip(lower=0)

    # Has start and end → perfect if within, else distance
    mask_closed = has_v & has_s & has_e
    within = mask_closed & (v_days >= s_days) & (v_days <= e_days)
    score[within] = 0
    before = mask_closed & (v_days < s_days)
    score[before] = (s_days[before] - v_days[before])
    after = mask_closed & (v_days > e_days)
    score[after] = (v_days[after] - e_days[after])

    disc['_score'] = score

    # Sort by score (best match first), then deduplicate to one employment row per
    # (case, person, violation, sanction, sanction_date)
    disc = (
        disc.sort_values('_score')
        .drop_duplicates(subset=['case_id', 'person_nbr', 'violation', 'sanction',
                                 'sanction_date'])
    )
    disc = disc.drop(columns=['_score'])

    # --- Drop rows where start_date is empty (no employment match) ---
    disc = disc[disc['start_date'].fillna('') != '']

    # --- Attach demographics ---
    officers_clean = officers.copy()
    for col in ('last_name', 'first_name', 'middle_name', 'suffix',
                'year_of_birth', 'race', 'sex'):
        if col in officers_clean.columns:
            officers_clean[col] = officers_clean[col].str.lower().str.strip()

    disc = disc.merge(
        officers_clean[['person_nbr', 'last_name', 'first_name', 'middle_name',
                         'suffix', 'year_of_birth', 'race', 'sex']],
        on='person_nbr',
        how='left',
    )

    # --- Build full_name ---
    def make_full_name(row):
        parts = [row.get('first_name', '')]
        if row.get('middle_name', ''):
            parts.append(row['middle_name'])
        first_part = ' '.join(p for p in parts if p)
        last_part = row.get('last_name', '')
        result = f"{last_part}, {first_part}" if first_part else last_part
        if row.get('suffix', ''):
            result = f"{result} {row['suffix']}"
        return result.strip()

    disc['full_name'] = disc.apply(make_full_name, axis=1)

    # Lowercase agency_name to match groundtruth discipline index
    disc['agency_name'] = disc['agency_name'].str.lower()

    # Lowercase rank to match groundtruth discipline index
    disc['rank'] = disc['rank'].str.lower()

    # --- Select output columns ---
    output_cols = [
        'case_id', 'person_nbr', 'sanction', 'sanction_date',
        'violation', 'violation_date',
        'full_name', 'agency_name', 'rank', 'start_date', 'end_date',
        'last_name', 'first_name', 'middle_name', 'suffix',
        'year_of_birth', 'race', 'sex',
    ]
    # Keep only cols that exist
    output_cols = [c for c in output_cols if c in disc.columns]
    disc = disc[output_cols]

    return disc



# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print("Loading raw files…")
    emp, officers, violations, sanctions = load_data(input_dir)
    print(f"  employment rows: {len(emp)}")
    print(f"  officer rows:    {len(officers)}")
    print(f"  violation rows:  {len(violations)}")
    print(f"  sanction rows:   {len(sanctions)}")

    # --- Rename officer demographics for re-use ---
    officers = officers.rename(columns={
        'OKEY': 'person_nbr',
        'LAST NAME': 'last_name',
        'FIRST NAME': 'first_name',
        'MIDDLE': 'middle_name',
        'SUFFIX': 'suffix',
        'YOB': 'year_of_birth',
        'SEX': 'sex',
        'RACE': 'race',
    })
    officers['person_nbr'] = officers['person_nbr'].str.lower().str.strip()

    print("\nBuilding employment index…")
    emp_df = build_employment_index(emp, officers)
    print(f"  output rows: {len(emp_df)}")

    # Validate required columns
    required = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                'start_date', 'end_date']
    missing = [c for c in required if c not in emp_df.columns]
    assert not missing, f"Missing required columns: {missing}"
    assert (emp_df['start_date'] != '').all(), "start_date must not be empty"

    print("\nBuilding discipline index…")
    disc_df = build_discipline_index(violations, sanctions, emp_df, officers)
    print(f"  output rows: {len(disc_df)}")

    # Write outputs
    emp_path = os.path.join(output_dir, "ga_index.csv")
    disc_path = os.path.join(output_dir, "ga-discipline_index.csv")

    emp_df.to_csv(emp_path, index=False)
    disc_df.to_csv(disc_path, index=False)

    print(f"\nWrote {emp_path}")
    print(f"Wrote {disc_path}")


if __name__ == "__main__":
    main()
