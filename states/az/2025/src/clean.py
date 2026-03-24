"""
Arizona POST employment index cleaner — 2025
Input:  data/input/arizona_index.csv
Output: output/az_index.csv
"""

import argparse
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Clean AZ POST data")
    parser.add_argument("--input-dir", default="data/input")
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Date helper
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    input_path = os.path.join(args.input_dir, "arizona_index.csv")
    os.makedirs(args.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    print(f"Loading {input_path} ...")
    df = pd.read_csv(input_path, dtype=str)
    print(f"  Loaded {len(df):,} rows, columns: {list(df.columns)}")

    # ------------------------------------------------------------------
    # Clean person_nbr — lowercase string, strip whitespace
    # ------------------------------------------------------------------
    df['person_nbr'] = df['person_nbr'].fillna('').astype(str).str.strip().str.lower()

    # Drop rows with no person_nbr
    before = len(df)
    df = df[df['person_nbr'] != '']
    if len(df) < before:
        print(f"  Dropped {before - len(df)} rows with empty person_nbr")

    # ------------------------------------------------------------------
    # Name columns — strip whitespace, keep as-is (pipeline proper-cases)
    # ------------------------------------------------------------------
    for col in ('first_name', 'middle_name', 'last_name', 'full_name'):
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    df['start_date'] = df['start_date'].apply(safe_date)
    df['end_date']   = df['end_date'].apply(safe_date)

    # Drop rows with empty start_date (pipeline would drop them anyway)
    before = len(df)
    df = df[df['start_date'] != '']
    if len(df) < before:
        print(f"  Dropped {before - len(df)} rows with empty start_date")

    # ------------------------------------------------------------------
    # Agency name — already clean; strip leading/trailing whitespace only
    # ------------------------------------------------------------------
    df['agency_name'] = df['agency_name'].fillna('').astype(str).str.strip()

    # Filter out known non-agency values
    NON_AGENCY = {'application denied', 'application purged', 'pending',
                  'unknown', 'n/a', ''}
    before = len(df)
    df = df[~df['agency_name'].str.lower().isin(NON_AGENCY)]
    if len(df) < before:
        print(f"  Dropped {before - len(df)} rows with non-agency agency_name")

    # ------------------------------------------------------------------
    # Optional columns — clean rank and current_certificate_status
    # ------------------------------------------------------------------
    if 'rank' in df.columns:
        df['rank'] = df['rank'].fillna('').astype(str).str.strip()

    if 'current_certificate_status' in df.columns:
        df['current_certificate_status'] = (
            df['current_certificate_status'].fillna('').astype(str).str.strip()
        )

    # ------------------------------------------------------------------
    # Deduplicate on (person_nbr, agency_name, start_date)
    # ------------------------------------------------------------------
    before = len(df)
    df = df.drop_duplicates(subset=['person_nbr', 'agency_name', 'start_date'])
    if len(df) < before:
        print(f"  Dropped {before - len(df)} duplicate rows")

    # ------------------------------------------------------------------
    # Select / order output columns
    # ------------------------------------------------------------------
    output_cols = [
        'person_nbr', 'first_name', 'middle_name', 'last_name', 'full_name',
        'agency_name', 'rank', 'start_date', 'end_date',
        'current_certificate_status',
    ]
    # Keep only columns that exist
    output_cols = [c for c in output_cols if c in df.columns]
    df = df[output_cols]

    # ------------------------------------------------------------------
    # Validate required columns
    # ------------------------------------------------------------------
    required = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                'start_date', 'end_date']
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"Missing required columns: {missing}"
    assert (df['start_date'] != '').all(), "start_date must not be empty"

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    out_path = os.path.join(args.output_dir, "az_index.csv")
    df.to_csv(out_path, index=False)
    print(f"  Wrote {len(df):,} rows to {out_path}")


if __name__ == "__main__":
    main()
