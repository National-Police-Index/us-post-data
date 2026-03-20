"""
Georgia POST data cleaning script.

Reads from:  states/GA/data/input/
Writes to:   states/GA/output/
    - georgia_index.csv
    - georgia-discipline_index.csv

Run from repo root:
    python states/GA/src/clean.py
"""

import os
import re

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SRC = os.path.dirname(__file__)
INPUT_DIR = os.path.join(_SRC, "..", "data", "input")
OUTPUT_DIR = os.path.join(_SRC, "..", "output")


def p(fname):
    return os.path.join(INPUT_DIR, fname)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AGENCY_CODE_RE = re.compile(r"^[A-Z]\d+\s+")

# Strings that appear in the AGENCY column but are not actual agency names.
NON_AGENCY_VALUES = {
    "application denied",
    "application purged",
    "pending",
    "unknown",
    "n/a",
    "none",
    "",
}


def clean_agency_name(raw):
    """
    Strip leading agency code, trailing status markers, and noise from
    agency names.

    Examples:
      "G1720 DEKALB COUNTY POLICE DEPARTMENT"  → "DEKALB COUNTY POLICE DEPARTMENT"
      "G1276 METRO STATE PRISON/INACTIVE"       → "METRO STATE PRISON"
      "G0001 ATLANTA POLICE DEPT."              → "ATLANTA POLICE DEPARTMENT"
    """
    if pd.isna(raw):
        return ""
    s = str(raw).strip()

    # Strip leading agency code (e.g. "G1720 ")
    s = AGENCY_CODE_RE.sub("", s)

    # Strip trailing status markers and noise (/ INACTIVE, /18 MOS., etc.)
    s = re.sub(
        r"\s*/\s*(inactive|active|closed|retired).*$", "", s, flags=re.IGNORECASE
    )
    s = re.sub(r"\s*\((inactive|closed)\).*$", "", s, flags=re.IGNORECASE)
    # Strip trailing slash-delimited fragments (e.g. "/18 MOS.", "/PURGED")
    s = re.sub(r"\s*/.*$", "", s)

    # Expand common abbreviations (order matters — more specific first)
    s = re.sub(r"\bD\.P\.S\.?\b", "DEPARTMENT OF PUBLIC SAFETY", s, flags=re.IGNORECASE)
    s = re.sub(r"\bP\.D\.?\b", "POLICE DEPARTMENT", s, flags=re.IGNORECASE)
    s = re.sub(r"\bPOLICE\s+DEPT\.?\b", "POLICE DEPARTMENT", s, flags=re.IGNORECASE)
    s = re.sub(r"\bSHERIFFS\s+OFFICE\b", "SHERIFF'S OFFICE", s, flags=re.IGNORECASE)
    s = re.sub(r"\bSHERIFFS?\s+DEPT\.?\b", "SHERIFF'S DEPARTMENT", s, flags=re.IGNORECASE)
    s = re.sub(r"\bDEPT\.?\b", "DEPARTMENT", s, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", s).strip().upper()


def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if s in ("", "nan", "NaT", "None", "0000-00-00", "00/00/0000"):
        return ""
    try:
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return ""


def build_full_name(last, first, middle, suffix=""):
    """Format: 'last, first middle suffix' in lowercase."""
    last = str(last).strip().lower() if pd.notna(last) and str(last) != "nan" else ""
    first = str(first).strip().lower() if pd.notna(first) and str(first) != "nan" else ""
    middle = str(middle).strip().lower() if pd.notna(middle) and str(middle) not in ("nan", "") else ""
    suffix = str(suffix).strip().lower() if pd.notna(suffix) and str(suffix) not in ("nan", "") else ""

    name = f"{last}, {first}"
    if middle:
        name = f"{name} {middle}"
    if suffix:
        name = f"{name} {suffix}"
    return name.strip(", ").strip()


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------

print("Loading raw files...")

employment = pd.read_csv(p("officer_employment.csv"), low_memory=False)
officer = pd.read_csv(p("officer_data.csv"), low_memory=False)
violations = pd.read_csv(p("officer_violations.csv"), low_memory=False)
sanctions = pd.read_csv(p("officer_sanctions.csv"), low_memory=False)

print(f"  employment:  {len(employment):,} rows")
print(f"  officer:     {len(officer):,} rows")
print(f"  violations:  {len(violations):,} rows")
print(f"  sanctions:   {len(sanctions):,} rows")

# ---------------------------------------------------------------------------
# Clean employment table
# ---------------------------------------------------------------------------

print("\nCleaning employment data...")

employment = employment.rename(
    columns={
        "OKEY": "person_nbr",
        "AGENCY": "_raw_agency",
        "RANK": "rank",
        "STATUS": "employment_status",
        "START DATE": "start_date",
        "END DATE": "end_date",
    }
)

employment["person_nbr"] = (
    employment["person_nbr"].astype(str).str.strip().str.lower()
)

# Clean agency names (strip codes, status markers, expand abbreviations)
employment["agency_name"] = employment["_raw_agency"].apply(clean_agency_name)

# Filter out non-agency entries (APPLICATION DENIED, etc.)
before = len(employment)
employment = employment[
    ~employment["agency_name"].str.lower().isin(NON_AGENCY_VALUES)
].copy()
if len(employment) < before:
    print(f"  Dropped {before - len(employment):,} rows with non-agency values")

employment["start_date"] = employment["start_date"].apply(safe_date)
employment["end_date"] = employment["end_date"].apply(safe_date)

before = len(employment)
employment = employment[employment["start_date"] != ""].copy()
if len(employment) < before:
    print(f"  Dropped {before - len(employment):,} rows with empty start_date")

# ---------------------------------------------------------------------------
# Clean officer demographics table
# ---------------------------------------------------------------------------

officer = officer.rename(
    columns={
        "OKEY": "person_nbr",
        "LAST NAME": "last_name",
        "FIRST NAME": "first_name",
        "MIDDLE": "middle_name",
        "SUFFIX": "suffix",
        "YOB": "year_of_birth",
        "SEX": "sex",
        "RACE": "race",
    }
)

officer["person_nbr"] = (
    officer["person_nbr"].astype(str).str.strip().str.lower()
)

for col in ("last_name", "first_name", "middle_name", "suffix", "race", "sex"):
    officer[col] = officer[col].fillna("").astype(str).str.strip().str.lower()

officer["year_of_birth"] = (
    officer["year_of_birth"].fillna("").astype(str).str.strip()
)

# ---------------------------------------------------------------------------
# Merge employment + demographics → employment index
# ---------------------------------------------------------------------------

print("Merging employment + demographics...")

merged = employment.merge(
    officer[[
        "person_nbr", "last_name", "first_name", "middle_name",
        "suffix", "year_of_birth", "race", "sex",
    ]],
    on="person_nbr",
    how="left",
)

merged["full_name"] = merged.apply(
    lambda r: build_full_name(
        r["last_name"], r["first_name"], r["middle_name"], r.get("suffix", "")
    ),
    axis=1,
)
merged["state"] = "ga"

emp_cols = [
    "person_nbr", "full_name", "first_name", "middle_name", "last_name",
    "suffix", "agency_name", "rank", "employment_status",
    "start_date", "end_date", "year_of_birth", "race", "sex", "state",
]
georgia_index = merged[emp_cols].copy()

# Validate
for col in ("person_nbr", "first_name", "last_name", "agency_name", "start_date"):
    empty = (georgia_index[col].fillna("") == "")
    if empty.any():
        print(f"  Warning: '{col}' has {empty.sum():,} empty values")

before = len(georgia_index)
georgia_index = georgia_index.drop_duplicates(
    subset=["person_nbr", "agency_name", "start_date"]
)
if len(georgia_index) < before:
    print(f"  Dropped {before - len(georgia_index):,} duplicate rows")

print(f"  Employment index: {len(georgia_index):,} rows")

# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------

print("\nBuilding discipline index...")

violations = violations.rename(
    columns={
        "CASE": "case_id",
        "OKEY": "person_nbr",
        "VIOLATION": "violation",
        "VIOLATION DATE": "violation_date",
    }
).drop(columns=["NAME"], errors="ignore")

violations["person_nbr"] = (
    violations["person_nbr"].astype(str).str.strip().str.lower()
)
violations["case_id"] = violations["case_id"].astype(str).str.strip()
violations["violation_date"] = violations["violation_date"].apply(safe_date)

sanctions = sanctions.rename(
    columns={
        "CASE": "case_id",
        "OKEY": "person_nbr",
        "SANCTION": "sanction",
        "DATE": "sanction_date",
    }
).drop(columns=["NAME"], errors="ignore")

sanctions["person_nbr"] = (
    sanctions["person_nbr"].astype(str).str.strip().str.lower()
)
sanctions["case_id"] = sanctions["case_id"].astype(str).str.strip()
sanctions["sanction_date"] = sanctions["sanction_date"].apply(safe_date)

# Inner join violations → sanctions on (case_id, person_nbr).
# This keeps only violations that have at least one sanction, matching the
# reference output structure. Where a violation has multiple sanctions, keep
# the most recent one (one row per violation).
discipline = violations.merge(
    sanctions[["case_id", "person_nbr", "sanction", "sanction_date"]],
    on=["case_id", "person_nbr"],
    how="inner",
)

# One row per violation: keep the most recent sanction for each
discipline = (
    discipline.sort_values("sanction_date", ascending=False)
    .drop_duplicates(subset=["case_id", "person_nbr", "violation"])
    .reset_index(drop=True)
)

print(f"  Discipline records before employment join: {len(discipline):,}")

# Attach employment context: score each possible employment period and keep best
emp_ctx = employment[
    ["person_nbr", "agency_name", "rank", "start_date", "end_date"]
].copy()
emp_ctx["_start"] = pd.to_datetime(emp_ctx["start_date"], errors="coerce")
emp_ctx["_end"] = pd.to_datetime(emp_ctx["end_date"], errors="coerce")

discipline["_vdate"] = pd.to_datetime(
    discipline["violation_date"], errors="coerce"
)

disc_emp = discipline.merge(emp_ctx, on="person_nbr", how="left")


def _period_score(row):
    vd = row["_vdate"]
    if pd.isna(vd):
        return 3
    s, e = row["_start"], row["_end"]
    if pd.notna(s) and pd.notna(e):
        return 0 if s <= vd <= e else (1 if vd < s else 2)
    if pd.notna(s):
        return 0 if vd >= s else 1
    return 3


disc_emp["_score"] = disc_emp.apply(_period_score, axis=1)

# Keep the single best-matching employment period per discipline record
disc_emp = (
    disc_emp.sort_values("_score")
    .drop_duplicates(
        subset=["case_id", "person_nbr", "violation", "sanction"], keep="first"
    )
)

# Drop rows with no employment match (empty start_date after join)
before = len(disc_emp)
disc_emp = disc_emp[disc_emp["start_date"].fillna("") != ""].copy()
if len(disc_emp) < before:
    print(
        f"  Dropped {before - len(disc_emp):,} discipline rows "
        f"with no employment match"
    )

# Attach demographics
disc_emp = disc_emp.merge(
    officer[[
        "person_nbr", "last_name", "first_name", "middle_name",
        "suffix", "year_of_birth", "race", "sex",
    ]],
    on="person_nbr",
    how="left",
)

disc_emp["full_name"] = disc_emp.apply(
    lambda r: build_full_name(
        r["last_name"], r["first_name"], r["middle_name"], r.get("suffix", "")
    ),
    axis=1,
)

disc_cols = [
    "case_id", "person_nbr", "sanction", "sanction_date",
    "violation", "violation_date", "full_name", "agency_name", "rank",
    "start_date", "end_date", "last_name", "first_name", "middle_name",
    "suffix", "year_of_birth", "race", "sex",
]

georgia_discipline = disc_emp[
    [c for c in disc_cols if c in disc_emp.columns]
].copy()

georgia_discipline = georgia_discipline[
    georgia_discipline["person_nbr"].fillna("") != ""
]

print(f"  Discipline index: {len(georgia_discipline):,} rows")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

emp_path = os.path.join(OUTPUT_DIR, "georgia_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "georgia-discipline_index.csv")

georgia_index.to_csv(emp_path, index=False)
georgia_discipline.to_csv(disc_path, index=False)

print(f"\nWrote: {emp_path}")
print(f"Wrote: {disc_path}")

print("\n--- Validation summary ---")
print(
    f"georgia_index.csv:            {len(georgia_index):,} rows, "
    f"{len(georgia_index.columns)} cols"
)
print(
    f"georgia-discipline_index.csv: {len(georgia_discipline):,} rows, "
    f"{len(georgia_discipline.columns)} cols"
)
print(f"Unique officers (employment): {georgia_index['person_nbr'].nunique():,}")
print(f"Unique agencies (employment): {georgia_index['agency_name'].nunique():,}")
if "violation" in georgia_discipline.columns:
    print(
        f"Unique violations:            "
        f"{georgia_discipline['violation'].nunique():,}"
    )
