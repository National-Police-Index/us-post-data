"""
Arizona POST data cleaning script — 2025
Input:  data/input/arizona_index.csv
Output: output/az_index.csv
"""

import argparse
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean AZ POST data")
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
print(f"Columns: {list(df.columns)}")


# ---------------------------------------------------------------------------
# Clean person_nbr — lowercase string, strip whitespace
# ---------------------------------------------------------------------------
df["person_nbr"] = df["person_nbr"].astype(str).str.strip().str.lower()

# Drop rows with no person_nbr
df = df[df["person_nbr"].notna() & (df["person_nbr"] != "") & (df["person_nbr"] != "nan")]


# ---------------------------------------------------------------------------
# Clean names
# ---------------------------------------------------------------------------
for col in ["first_name", "middle_name", "last_name", "suffix"]:
    if col in df.columns:
        df[col] = df[col].fillna("").astype(str).str.strip()

# Build full_name in "last, first" lowercase format
df["full_name"] = (
    df["last_name"].str.strip() + ", " + df["first_name"].str.strip()
).str.lower()


# ---------------------------------------------------------------------------
# Clean dates — parse to YYYY-MM-DD or empty string
# ---------------------------------------------------------------------------
def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip() if val is not None else ""
    if not s or s in ("nan", "NaT", "None", "0000-00-00", "00/00/0000"):
        return ""
    try:
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return ""


df["start_date"] = df["start_date"].apply(safe_date)
df["end_date"] = df["end_date"].apply(safe_date)

# Drop rows with empty start_date
before = len(df)
df = df[df["start_date"] != ""]
print(f"Dropped {before - len(df):,} rows with empty start_date; {len(df):,} remaining")


# ---------------------------------------------------------------------------
# Clean agency names
# ---------------------------------------------------------------------------
AGENCY_ABBREVIATIONS = [
    (r"\bCTY\b", "COUNTY"),
    (r"\bSHERIFFS\b", "SHERIFF'S"),         # plural possessive fix (no trailing 'S)
    (r"\bDEPT\.?\b", "DEPARTMENT"),
    (r"\bPD\b", "POLICE DEPARTMENT"),
    (r"\bSO\b", "SHERIFF'S OFFICE"),
    (r"\bCORR\.?\b", "CORRECTIONS"),
    (r"\bDA\b", "DISTRICT ATTORNEY'S OFFICE"),
    (r"\bDPS\b", "DEPARTMENT OF PUBLIC SAFETY"),
    (r"\bSVCS?\b", "SERVICES"),
    (r"\bDIV\.?\b", "DIVISION"),
    (r"\bDIST\.?\b", "DISTRICT"),
    (r"\bADMIN\.?\b", "ADMINISTRATION"),
]

NON_AGENCY_VALUES = {
    "application denied", "application purged", "pending",
    "unknown", "n/a", "",
}


def clean_agency_name(name):
    if pd.isna(name) or str(name).strip() == "":
        return ""
    s = str(name).strip()
    # Strip leading agency codes if present (e.g. "G1720 NAME")
    s = re.sub(r"^[A-Z]\d{3,}\s+", "", s)
    # Strip trailing slash fragments
    s = re.sub(r"\s*/.*$", "", s)
    # Strip trailing status markers in parentheses
    s = re.sub(r"\s*\((INACTIVE|CLOSED)\).*$", "", s, flags=re.IGNORECASE)
    # Expand abbreviations
    s_upper = s.upper()
    for pattern, replacement in AGENCY_ABBREVIATIONS:
        s_upper = re.sub(pattern, replacement, s_upper)
    # Collapse whitespace
    s_upper = re.sub(r"\s+", " ", s_upper).strip()
    return s_upper


df["agency_name"] = df["agency_name"].apply(clean_agency_name)

# Filter out non-agency strings
df = df[~df["agency_name"].str.lower().isin(NON_AGENCY_VALUES)]

print(f"After agency cleaning: {len(df):,} rows")
print("Sample agency names:")
print(df["agency_name"].value_counts().head(10))


# ---------------------------------------------------------------------------
# Rename / select columns
# ---------------------------------------------------------------------------
# Map existing optional columns
rename_map = {
    "current_certificate_status": "employment_status",
}
df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

# Add state column
df["state"] = "az"

# ---------------------------------------------------------------------------
# Deduplicate
# ---------------------------------------------------------------------------
before = len(df)
df = df.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
print(f"Dropped {before - len(df):,} duplicate rows; {len(df):,} remaining")


# ---------------------------------------------------------------------------
# Final column selection and ordering
# ---------------------------------------------------------------------------
required_cols = [
    "person_nbr", "first_name", "middle_name", "last_name",
    "full_name", "agency_name", "rank", "start_date", "end_date",
    "employment_status", "state",
]
# Keep only columns that actually exist
output_cols = [c for c in required_cols if c in df.columns]
df_out = df[output_cols].copy()

# ---------------------------------------------------------------------------
# Validate before writing
# ---------------------------------------------------------------------------
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_cols = [c for c in required if c not in df_out.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

assert (df_out["start_date"] != "").all(), "start_date must not be empty"
assert (df_out["person_nbr"] != "").all(), "person_nbr must not be empty"

print(f"\nFinal output: {len(df_out):,} rows, {len(df_out.columns)} columns")
print(f"Columns: {list(df_out.columns)}")


# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
out_path = os.path.join(output_dir, "az_index.csv")
df_out.to_csv(out_path, index=False)
print(f"\nWrote {len(df_out):,} rows to {out_path}")
