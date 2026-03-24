"""
Arizona POST Employment Index Cleaner
Reads: data/input/arizona_index.csv
Writes: output/az_index.csv
"""

import argparse
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean Arizona POST employment data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

input_dir = args.input_dir
output_dir = args.output_dir
os.makedirs(output_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
input_file = os.path.join(input_dir, "arizona_index.csv")
print(f"Reading {input_file} ...")
df = pd.read_csv(input_file, dtype={"person_nbr": str})
print(f"  Loaded {len(df):,} rows, columns: {df.columns.tolist()}")


# ---------------------------------------------------------------------------
# Clean person_nbr
# ---------------------------------------------------------------------------
df["person_nbr"] = df["person_nbr"].astype(str).str.strip().str.lower()
# Drop rows with no person_nbr
df = df[df["person_nbr"].notna() & (df["person_nbr"] != "") & (df["person_nbr"] != "nan")]
print(f"  After person_nbr drop: {len(df):,} rows")

# ---------------------------------------------------------------------------
# Clean names
# ---------------------------------------------------------------------------
for col in ["first_name", "last_name", "middle_name"]:
    df[col] = df[col].astype(str).str.strip()
    df[col] = df[col].replace("nan", "")

# Build full_name as "last, first" (lowercase)
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
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return ""


df["start_date"] = df["start_date"].apply(safe_date)
df["end_date"] = df["end_date"].apply(safe_date)

# Drop rows with empty start_date (pipeline requirement)
before = len(df)
df = df[df["start_date"] != ""]
print(f"  Dropped {before - len(df):,} rows with empty start_date")


# ---------------------------------------------------------------------------
# Clean agency names
# ---------------------------------------------------------------------------
# The input already has readable agency names but uses abbreviations like:
#   "Cty" -> "County"
#   "AZ" stays as-is (it's the state prefix, not an abbreviation to expand)
# We normalize to lowercase to match groundtruth style.

def clean_agency_name(name):
    if pd.isna(name) or str(name).strip() == "":
        return ""
    s = str(name).strip()
    # Expand "Cty" -> "County" (word boundary)
    s = re.sub(r"\bCty\b", "County", s)
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


df["agency_name"] = df["agency_name"].apply(clean_agency_name)

# Filter out non-agency values
NON_AGENCY_VALUES = {"application denied", "application purged", "pending", "unknown", "n/a", ""}
df = df[~df["agency_name"].str.lower().isin(NON_AGENCY_VALUES)]
print(f"  After agency clean: {len(df):,} rows")


# ---------------------------------------------------------------------------
# Rename / select output columns
# ---------------------------------------------------------------------------
# Map current_certificate_status to employment_status
df = df.rename(columns={"current_certificate_status": "employment_status"})

# Select and order required + optional columns
output_cols = [
    "person_nbr",
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "agency_name",
    "rank",
    "start_date",
    "end_date",
    "employment_status",
]

df = df[output_cols]

# ---------------------------------------------------------------------------
# Deduplicate
# ---------------------------------------------------------------------------
before = len(df)
df = df.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
print(f"  Dropped {before - len(df):,} duplicate rows")

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_cols = [c for c in required if c not in df.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

assert (df["start_date"] != "").all(), "start_date must not be empty"
assert (df["person_nbr"].str.strip() == df["person_nbr"]).all(), "person_nbr has whitespace"

print(f"  Final row count: {len(df):,}")
print(f"  Unique officers: {df['person_nbr'].nunique():,}")
print(f"  Unique agencies: {df['agency_name'].nunique():,}")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
out_path = os.path.join(output_dir, "az_index.csv")
df.to_csv(out_path, index=False)
print(f"Wrote {out_path}")
