"""
Arizona 2025 — clean.py
Cleans the raw arizona_index.csv into az_index.csv per the standard schema.
"""

import argparse
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Clean Arizona POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

input_dir = args.input_dir
output_dir = args.output_dir
os.makedirs(output_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

input_path = os.path.join(input_dir, "arizona_index.csv")
df = pd.read_csv(input_path, dtype=str)
print(f"Loaded {len(df):,} rows from {input_path}")


# ---------------------------------------------------------------------------
# Clean person_nbr
# ---------------------------------------------------------------------------

df["person_nbr"] = df["person_nbr"].astype(str).str.strip().str.lower()

# Drop rows with no person_nbr
df = df[
    df["person_nbr"].notna()
    & (df["person_nbr"] != "")
    & (df["person_nbr"] != "nan")
]
print(f"  After person_nbr filter: {len(df):,} rows")

# ---------------------------------------------------------------------------
# Clean names
# ---------------------------------------------------------------------------

for col in ["first_name", "last_name", "middle_name", "full_name"]:
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

# Build full_name in standard format: "last, first" lowercase (if not already sensible)
# Source has full_name as "FIRST MIDDLE LAST" — rebuild from parts
df["full_name"] = (
    df["last_name"].str.strip() + ", " + df["first_name"].str.strip()
).str.lower()


# ---------------------------------------------------------------------------
# Clean dates
# ---------------------------------------------------------------------------


def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ("nan", "NaT", "None", "0000-00-00", "00/00/0000"):
        return ""
    try:
        return pd.to_datetime(s, errors="coerce").strftime("%Y-%m-%d")
    except Exception:
        return ""


df["start_date"] = df["start_date"].apply(safe_date)
df["end_date"] = df["end_date"].apply(safe_date)

# Drop rows with empty start_date (pipeline would drop them anyway)
before = len(df)
df = df[df["start_date"] != ""]
print(
    f"  Dropped {before - len(df):,} rows with empty start_date; {len(df):,} remain"
)


# ---------------------------------------------------------------------------
# Clean agency names
# ---------------------------------------------------------------------------

AGENCY_ABBREVIATIONS = [
    (r"\bDEPT\.?\b", "DEPARTMENT"),
    (r"\bSO\b", "SHERIFF'S OFFICE"),
    (r"\bPD\b", "POLICE DEPARTMENT"),
    (r"\bCO\.?\b", "COUNTY"),
    (r"\bCORR\.?\b", "CORRECTIONS"),
    (r"\bDA\b", "DISTRICT ATTORNEY'S OFFICE"),
    (r"\bDPS\b", "DEPARTMENT OF PUBLIC SAFETY"),
    (r"\bSVCS?\b", "SERVICES"),
    (r"\bDIV\.?\b", "DIVISION"),
    (r"\bDIST\.?\b", "DISTRICT"),
    (r"\bADMIN\.?\b", "ADMINISTRATION"),
    (r"\bINVEST\.?\b", "INVESTIGATIONS"),
    (r"\bCTY\b", "COUNTY"),
]

NON_AGENCY_VALUES = {
    "application denied",
    "application purged",
    "pending",
    "unknown",
    "n/a",
    "",
}


def clean_agency_name(name):
    if pd.isna(name) or str(name).strip() == "":
        return ""
    s = str(name).strip()
    # Strip leading agency code prefix (e.g. "G1720 ")
    s = re.sub(r"^[A-Z]\d{3,}\s+", "", s)
    # Strip trailing status markers
    s = re.sub(
        r"\s*/\s*(INACTIVE|ACTIVE|CLOSED|RETIRED).*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\s*\((INACTIVE|CLOSED)\).*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*/.*$", "", s)
    # Expand known AZ abbreviations (work on uppercase copy)
    s_upper = s.upper()
    for pattern, replacement in AGENCY_ABBREVIATIONS:
        s_upper = re.sub(pattern, replacement, s_upper)
    # Collapse whitespace
    return re.sub(r"\s+", " ", s_upper).strip()


df["agency_name"] = df["agency_name"].apply(clean_agency_name)

# Filter out non-agency strings
df = df[~df["agency_name"].str.lower().isin(NON_AGENCY_VALUES)]
print(f"  After agency filter: {len(df):,} rows")
print(f"  Sample agency names: {df['agency_name'].unique()[:5].tolist()}")


# ---------------------------------------------------------------------------
# Clean rank / status columns
# ---------------------------------------------------------------------------

if "rank" in df.columns:
    df["rank"] = df["rank"].fillna("").astype(str).str.strip()

if "current_certificate_status" in df.columns:
    df = df.rename(columns={"current_certificate_status": "employment_status"})
    df["employment_status"] = (
        df["employment_status"].fillna("").astype(str).str.strip()
    )

# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

before = len(df)
df = df.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
print(f"  Dropped {before - len(df):,} duplicate rows; {len(df):,} remain")

# ---------------------------------------------------------------------------
# Select and order output columns
# ---------------------------------------------------------------------------

output_cols = [
    "person_nbr",
    "first_name",
    "last_name",
    "middle_name",
    "full_name",
    "agency_name",
    "rank",
    "start_date",
    "end_date",
    "employment_status",
]
# Only keep columns that exist
output_cols = [c for c in output_cols if c in df.columns]
df = df[output_cols]

# ---------------------------------------------------------------------------
# Final validation
# ---------------------------------------------------------------------------

required = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]
missing_cols = [c for c in required if c not in df.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

assert (df["start_date"] != "").all(), "start_date must not be empty"
assert (df["person_nbr"] != "").all(), "person_nbr must not be empty"

print(f"\nFinal output: {len(df):,} rows, {len(df.columns)} columns")
print(f"Columns: {df.columns.tolist()}")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------

out_path = os.path.join(output_dir, "az_index.csv")
df.to_csv(out_path, index=False)
print(f"\nWrote {len(df):,} rows to {out_path}")
