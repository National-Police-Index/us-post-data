#!/usr/bin/env python3
"""
Georgia POST data cleaning script.
Produces:
  - ga_index.csv        (employment index)
  - ga-discipline_index.csv  (discipline index)
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
# Helper functions
# ---------------------------------------------------------------------------

def safe_date(val):
    """Return YYYY-MM-DD string, keep 0000-00-00 as-is, or empty string (scalar)."""
    s = str(val).strip()
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


def safe_date_vec(series):
    """Vectorized version of safe_date for Series."""
    s = series.astype(str).str.strip()
    is_zero = s == '0000-00-00'
    is_empty = s.isin(['', 'nan', 'NaT', 'None'])
    parsed = pd.to_datetime(
        s.where(~is_zero & ~is_empty, other=pd.NaT), errors='coerce'
    )
    result = parsed.dt.strftime('%Y-%m-%d').fillna('')
    result = result.where(~is_zero, '0000-00-00')
    return result


def clean_person_nbr(val):
    return str(val).strip().lower()


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

print("Loading raw files...")

emp = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_employment.csv"),
    dtype=str,
).fillna("")

officer = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_data.csv"),
    dtype=str,
).fillna("")

violations = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_violations.csv"),
    dtype=str,
).fillna("")

sanctions = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_sanctions.csv"),
    dtype=str,
).fillna("")

print(f"  employment rows: {len(emp):,}")
print(f"  officer rows:    {len(officer):,}")
print(f"  violations rows: {len(violations):,}")
print(f"  sanctions rows:  {len(sanctions):,}")


# ---------------------------------------------------------------------------
# Clean officer demographics
# ---------------------------------------------------------------------------

officer = officer.rename(columns={
    "OKEY": "person_nbr",
    "LAST NAME": "last_name",
    "FIRST NAME": "first_name",
    "MIDDLE": "middle_name",
    "SUFFIX": "suffix",
    "YOB": "year_of_birth",
    "SEX": "sex",
    "RACE": "race",
})

officer["person_nbr"] = officer["person_nbr"].apply(clean_person_nbr)
officer["last_name"] = officer["last_name"].str.strip()
officer["first_name"] = officer["first_name"].str.strip()
officer["middle_name"] = officer["middle_name"].str.strip()
officer["suffix"] = officer["suffix"].str.strip()

# Build full_name: "last_name, first_name[ middle_name][ suffix]" (lowercase)
def build_full_name(row):
    parts = [row["first_name"]]
    if row["middle_name"]:
        parts.append(row["middle_name"])
    name = " ".join(p for p in parts if p)
    full = f"{row['last_name']}, {name}" if name else row["last_name"]
    if row["suffix"]:
        full = f"{full} {row['suffix']}"
    return full.lower()

officer["full_name"] = officer.apply(build_full_name, axis=1)


# ---------------------------------------------------------------------------
# Clean employment data
# ---------------------------------------------------------------------------

emp = emp.rename(columns={
    "OKEY": "person_nbr",
    "NAME": "_raw_name",
    "AGENCY": "agency_name",
    "RANK": "rank",
    "STATUS": "employment_status",
    "START DATE": "start_date",
    "END DATE": "end_date",
})

emp["person_nbr"] = emp["person_nbr"].apply(clean_person_nbr)

# Keep agency_name as-is (groundtruth keeps the raw value with code prefix)
# Just strip leading/trailing whitespace
emp["agency_name"] = emp["agency_name"].str.strip()

# Clean dates — keep 0000-00-00 as-is per groundtruth (vectorized for speed)
emp["start_date"] = safe_date_vec(emp["start_date"])
emp["end_date"] = safe_date_vec(emp["end_date"])

# Drop rows with empty start_date
before = len(emp)
emp = emp[emp["start_date"] != ""]
print(f"  Dropped {before - len(emp):,} rows with empty start_date")

# Filter out known non-agency values (after stripping code prefix for comparison)
def agency_code_stripped(name):
    """Return name without leading agency code for filter comparison."""
    return re.sub(r'^[A-Z]\d+\s+', '', str(name)).strip()

NON_AGENCY_VALUES = {
    'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''
}
mask = emp["agency_name"].apply(
    lambda n: agency_code_stripped(n).lower() in NON_AGENCY_VALUES
)
before = len(emp)
emp = emp[~mask]
print(f"  Dropped {before - len(emp):,} rows with non-agency agency_name")

# Clean rank
emp["rank"] = emp["rank"].str.strip()


# ---------------------------------------------------------------------------
# Merge employment + officer demographics
# ---------------------------------------------------------------------------

merged = emp.merge(
    officer[[
        "person_nbr", "last_name", "first_name", "middle_name",
        "suffix", "full_name", "year_of_birth", "race", "sex"
    ]],
    on="person_nbr",
    how="left",
)

# Fill blank names for officers not in officer_data
merged["last_name"] = merged["last_name"].fillna("").str.strip()
merged["first_name"] = merged["first_name"].fillna("").str.strip()
merged["middle_name"] = merged["middle_name"].fillna("").str.strip()
merged["suffix"] = merged["suffix"].fillna("").str.strip()
merged["full_name"] = merged["full_name"].fillna("").str.strip()

# De-duplicate on (person_nbr, agency_name, start_date)
before = len(merged)
merged = merged.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
print(f"  Dropped {before - len(merged):,} duplicate rows after merge")
print(f"  Final employment rows: {len(merged):,}")

# Select and order columns for output
INDEX_COLS = [
    "person_nbr", "full_name", "agency_name", "rank", "employment_status",
    "start_date", "end_date",
    "last_name", "first_name", "middle_name", "suffix",
    "year_of_birth", "race", "sex",
]
ga_index = merged[INDEX_COLS].copy()


# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------

print("\nBuilding discipline index...")

# Rename violations
violations = violations.rename(columns={
    "CASE": "case_id",
    "OKEY": "person_nbr",
    "NAME": "_viol_name",
    "VIOLATION": "violation",
    "VIOLATION DATE": "violation_date",
})
violations["person_nbr"] = violations["person_nbr"].apply(clean_person_nbr)
violations["violation_date"] = safe_date_vec(violations["violation_date"])
violations["case_id"] = violations["case_id"].str.strip()

# Rename sanctions
sanctions = sanctions.rename(columns={
    "CASE": "case_id",
    "OKEY": "person_nbr",
    "NAME": "_sanc_name",
    "SANCTION": "sanction",
    "DATE": "sanction_date",
})
sanctions["person_nbr"] = sanctions["person_nbr"].apply(clean_person_nbr)
sanctions["sanction_date"] = safe_date_vec(sanctions["sanction_date"])
sanctions["case_id"] = sanctions["case_id"].str.strip()

# Inner join violations + sanctions on (case_id, person_nbr)
discipline = violations.merge(
    sanctions[["case_id", "person_nbr", "sanction", "sanction_date"]],
    on=["case_id", "person_nbr"],
    how="inner",
)

print(f"  After inner join: {len(discipline):,} rows")

# Deduplicate on (case_id, person_nbr, violation, sanction) to remove exact duplicates
discipline = discipline.drop_duplicates(
    subset=["case_id", "person_nbr", "violation", "sanction", "sanction_date"]
)
print(f"  After dedup (case, person, violation, sanction, sanction_date): {len(discipline):,} rows")

# Keep case_id as-is (leading zeros preserved, matching groundtruth format)
discipline["case_id"] = discipline["case_id"].str.strip()


# ---------------------------------------------------------------------------
# Attach employment context to discipline records
# ---------------------------------------------------------------------------

# Prepare employment for join — keep all columns needed
emp_for_join = emp[["person_nbr", "agency_name", "rank", "start_date", "end_date"]].copy()

# Join discipline to employment on person_nbr (one-to-many)
disc_emp = discipline.merge(emp_for_join, on="person_nbr", how="left")

print(f"  After joining employment: {len(disc_emp):,} rows")

# Score each employment period by how well violation_date falls within it
# Vectorized for performance

NOW = pd.Timestamp.now()

def to_ts(series, fill_now=False):
    """Convert date string series to timestamps. fill_now replaces 0000-00-00/empty with NOW."""
    result = pd.to_datetime(series.replace({'0000-00-00': '', '': None}), errors='coerce')
    if fill_now:
        result = result.fillna(NOW)
    return result

vd = to_ts(disc_emp["violation_date"])
sd = to_ts(disc_emp["start_date"])
ed = to_ts(disc_emp["end_date"], fill_now=True)

# Invalid start_date → score 9999
bad_start = sd.isna()

# Violation date within range → score 0
within = (~vd.isna()) & (sd <= vd) & (vd <= ed)

# Distance-based score for out-of-range
before_start = (sd - vd).dt.days.clip(lower=0)
after_end = (vd - ed).dt.days.clip(lower=0)
dist_score = before_start + after_end

# No violation date → use distance from start to now as tiebreaker
no_vd_score = (NOW - sd).dt.days

_score = pd.Series(9999, index=disc_emp.index, dtype=float)
_score = _score.where(bad_start, dist_score.where(~vd.isna(), no_vd_score))
_score = _score.where(~within, 0)
disc_emp["_score"] = _score

# Keep the best-scoring employment period per (case_id, person_nbr, violation, sanction, sanction_date)
disc_emp = (
    disc_emp.sort_values("_score")
    .drop_duplicates(subset=["case_id", "person_nbr", "violation", "sanction", "sanction_date"])
)
disc_emp = disc_emp.drop(columns=["_score"])

print(f"  After best-period selection: {len(disc_emp):,} rows")

# Drop rows with no employment match (empty start_date)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp["start_date"].fillna("") != ""]
print(f"  Dropped {before - len(disc_emp):,} rows with no employment start_date")
print(f"  Final discipline rows: {len(disc_emp):,}")


# ---------------------------------------------------------------------------
# Attach officer demographics to discipline index
# ---------------------------------------------------------------------------

disc_emp = disc_emp.merge(
    officer[[
        "person_nbr", "last_name", "first_name", "middle_name",
        "suffix", "full_name", "year_of_birth", "race", "sex"
    ]],
    on="person_nbr",
    how="left",
)

disc_emp["last_name"] = disc_emp["last_name"].fillna("").str.strip()
disc_emp["first_name"] = disc_emp["first_name"].fillna("").str.strip()
disc_emp["middle_name"] = disc_emp["middle_name"].fillna("").str.strip()
disc_emp["suffix"] = disc_emp["suffix"].fillna("").str.strip()
disc_emp["full_name"] = disc_emp["full_name"].fillna("").str.strip()

# For discipline index, agency_name should be lowercase per groundtruth
disc_emp["agency_name"] = disc_emp["agency_name"].str.lower()

# Discipline columns — match groundtruth column order
DISC_COLS = [
    "case_id", "person_nbr", "sanction", "sanction_date",
    "violation", "violation_date",
    "full_name", "agency_name", "rank", "start_date", "end_date",
    "last_name", "first_name", "middle_name", "suffix",
    "year_of_birth", "race", "sex",
]
ga_discipline = disc_emp[DISC_COLS].copy()

# Lowercase string columns for discipline (per groundtruth pattern)
for col in ["sanction", "violation", "full_name", "rank", "last_name",
            "first_name", "middle_name", "suffix", "race", "sex",
            "employment_status"]:
    if col in ga_discipline.columns:
        ga_discipline[col] = ga_discipline[col].str.lower()


# ---------------------------------------------------------------------------
# Validate and write output
# ---------------------------------------------------------------------------

# Validate employment index
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing = [c for c in required if c not in ga_index.columns]
assert not missing, f"Missing required columns in employment index: {missing}"

empty_start = (ga_index["start_date"] == "").sum()
assert empty_start == 0, f"Employment index has {empty_start} empty start_date rows"

# Validate discipline index
disc_required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_disc = [c for c in disc_required if c not in ga_discipline.columns]
assert not missing_disc, f"Missing required columns in discipline index: {missing_disc}"

# Write output
emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

ga_index.to_csv(emp_path, index=False)
ga_discipline.to_csv(disc_path, index=False)

print(f"\nWrote {len(ga_index):,} rows → {emp_path}")
print(f"Wrote {len(ga_discipline):,} rows → {disc_path}")
print("Done.")
