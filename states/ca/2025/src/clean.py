"""
California POST + CDCR Employment Index Cleaner
State: CA  Year: 2025

Sources:
  - CPRA_R000301-011425__ADHOC-809.xlsx  (LEO – law-enforcement officers)
  - PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv  (Corrections officers)

Run from states/ca/2025/:
  python src/clean.py --input-dir data/input --output-dir output
"""

import argparse
import os
import re
import sys

import pandas as pd
from nameparser import HumanName

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Clean CA POST + CDCR data")
parser.add_argument("--input-dir",  default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR  = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_date(val):
    """Return YYYY-MM-DD string or empty string for invalid/missing dates."""
    s = str(val).strip()
    if not s or s.lower() in ("nan", "nat", "none", "0000-00-00", "00/00/0000"):
        return ""
    try:
        return pd.to_datetime(s, errors="coerce").strftime("%Y-%m-%d")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# LEO agency-name expansion
#
# The raw `agency` column uses abbreviated names.  We expand them to match
# the ground-truth canonical names.
# ---------------------------------------------------------------------------

# Ordered list: (compiled regex, replacement string)
_AGENCY_EXPANSIONS = [
    # Specific multi-word abbreviations first
    (re.compile(r"\bUNIF\s+SCHL\s+DIST\b",     re.I), "UNIFIED SCHOOL DISTRICT"),
    (re.compile(r"\bUNIF\s+SCH\s+DIST\b",      re.I), "UNIFIED SCHOOL DISTRICT"),
    (re.compile(r"\bSCHL\s+DIST\b",             re.I), "SCHOOL DISTRICT"),
    (re.compile(r"\bSCH\s+DIST\b",              re.I), "SCHOOL DISTRICT"),
    (re.compile(r"\bCOMM\s+COLLEGE\b",          re.I), "COMMUNITY COLLEGE"),
    (re.compile(r"\bCO\s+SD\b",                 re.I), "COUNTY SHERIFF'S DEPARTMENT"),
    (re.compile(r"\bCO\s+SO\b",                 re.I), "COUNTY SHERIFF'S OFFICE"),
    (re.compile(r"\bCOUNTY\s+SO\b",             re.I), "COUNTY SHERIFF'S OFFICE"),
    # Single-word abbreviations
    (re.compile(r"\bSD\b",                       re.I), "SHERIFF'S DEPARTMENT"),
    (re.compile(r"\bSO\b",                       re.I), "SHERIFF'S OFFICE"),
    (re.compile(r"\bPD\b",                       re.I), "POLICE DEPARTMENT"),
    (re.compile(r"\bDEPT\.?\b",                  re.I), "DEPARTMENT"),
    (re.compile(r"\bDPS\b",                      re.I), "DEPARTMENT OF PUBLIC SAFETY"),
    (re.compile(r"\bDA\b",                       re.I), "DISTRICT ATTORNEY"),
    (re.compile(r"\bSVCS?\b",                    re.I), "SERVICES"),
    (re.compile(r"\bADMIN\.?\b",                 re.I), "ADMINISTRATION"),
]

# Known specific overrides where abbreviation expansion alone is wrong
_AGENCY_OVERRIDES = {
    "CA HIGHWAY PATROL": "CALIFORNIA HIGHWAY PATROL",
    "CA DEPT STATE HOSPITALS – OFC OF SPEC INVEST": "CALIFORNIA DEPARTMENT STATE HOSPITALS – OFFICE OF SPEC INVEST",
    "CAL FIRE": "CAL FIRE",
    "CONTRA COSTA CO SO/CORONER": "CONTRA COSTA COUNTY SHERIFF'S OFFICE/CORONER",
    "ORANGE CO SD/CORONER": "ORANGE COUNTY SHERIFF'S DEPARTMENT/CORONER",
    "ALAMEDA CO SD/CORONER": "ALAMEDA COUNTY SHERIFF'S DEPARTMENT/CORONER",
    "SANTA CLARA CO SO": "SANTA CLARA COUNTY SHERIFF'S OFFICE",
    "KERN COUNTY SO": "KERN COUNTY SHERIFF'S OFFICE",
    "VENTURA CO SO": "VENTURA COUNTY SHERIFF'S OFFICE",
}

_NON_AGENCY_VALUES = {
    "application denied", "application purged", "pending",
    "unknown", "unknown/non-affiliate", "n/a", "",
    "military", "other-in-state", "other-out-of-state",
}


def expand_leo_agency(raw: str) -> str:
    """Expand abbreviated CA POST agency name to canonical form."""
    if pd.isna(raw):
        return ""
    s = str(raw).strip().upper()

    # Direct override
    if s in _AGENCY_OVERRIDES:
        return _AGENCY_OVERRIDES[s]

    # Apply expansion rules
    for pattern, replacement in _AGENCY_EXPANSIONS:
        s = pattern.sub(replacement, s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Separation-code lookup (from the Separation Codes sheet)
# ---------------------------------------------------------------------------

_SEP_CODES = {
    "1": "Resigned",
    "2": "Discharge",
    "3": "Retired",
    "4": "Deceased",
    "5": "Felony",
    "6": "Other",
    "7": "Promotion/Demotion",
    "8": "Involuntary Separation",
    "9": "Separated Pending Complaint, Administrative Charge, or Investigation for serious misconduct",
    "10": "Status Change",
    "11": "Did Not Complete Probation",
    "12": "Cancelled",
    "Z": "Unknown",
}


def map_sep_code(code) -> str:
    if pd.isna(code):
        return ""
    return _SEP_CODES.get(str(code).strip(), str(code).strip())


# ---------------------------------------------------------------------------
# Parse full name  (last, first middle suffix format common in CA)
# ---------------------------------------------------------------------------

def parse_full_name(name_str):
    """Parse 'LAST, FIRST MIDDLE SUFFIX' – fast regex path first, HumanName fallback."""
    s = str(name_str).strip().upper()
    if not s or s == "NAN":
        return {"first_name": "", "middle_name": "", "last_name": "", "suffix": ""}

    # Format: "LAST, FIRST [MIDDLE] [SUFFIX]"
    if "," in s:
        last_part, rest = s.split(",", 1)
        last_name = last_part.strip()
        tokens = rest.strip().split()
        # Check for suffix
        suffix_tokens = {"JR", "SR", "II", "III", "IV", "V"}
        suffix = ""
        if tokens and tokens[-1] in suffix_tokens:
            suffix = tokens[-1]
            tokens = tokens[:-1]
        first_name  = tokens[0] if tokens else ""
        middle_name = " ".join(tokens[1:]) if len(tokens) > 1 else ""
        return {"first_name": first_name, "middle_name": middle_name,
                "last_name": last_name, "suffix": suffix}

    # Fallback to HumanName for other formats
    n = HumanName(s)
    return {
        "first_name":   n.first.upper() if n.first else "",
        "middle_name":  n.middle.upper() if n.middle else "",
        "last_name":    n.last.upper() if n.last else "",
        "suffix":       n.suffix.upper() if n.suffix else "",
    }


# ===========================================================================
# SECTION 1 – Process LEO data
# ===========================================================================

print("Reading LEO data …")
leo_path = os.path.join(INPUT_DIR, "CPRA_R000301-011425__ADHOC-809.xlsx")
leo_raw = pd.read_excel(leo_path)
print(f"  LEO rows: {len(leo_raw):,}")

# Rename columns
leo = leo_raw.rename(columns={
    "POST_ID":               "person_nbr",
    "officer_name":          "full_name_raw",
    "agency":                "agency_raw",
    "employment_start_date": "start_date_raw",
    "employment_end_date":   "end_date_raw",
    "separation_code":       "sep_code",
    "rank":                  "rank",
    "app_status":            "app_status",
}).copy()

# person_nbr – lowercase, strip
leo["person_nbr"] = leo["person_nbr"].astype(str).str.lower().str.strip()

# Drop records with no person_nbr
leo = leo[leo["person_nbr"].notna() & (leo["person_nbr"] != "") & (leo["person_nbr"] != "nan")]

# Parse names (fast vectorised path)
print("  Parsing LEO names …")
name_records = [parse_full_name(n) for n in leo["full_name_raw"]]
name_df = pd.DataFrame(name_records, index=leo.index)
leo = pd.concat([leo, name_df], axis=1)

# Dates
leo["start_date"] = leo["start_date_raw"].apply(safe_date)
leo["end_date"]   = leo["end_date_raw"].apply(safe_date)

# Drop rows with empty start_date
before = len(leo)
leo = leo[leo["start_date"] != ""]
print(f"  Dropped {before - len(leo):,} rows with empty start_date")

# Agency name
leo["agency_name"] = leo["agency_raw"].apply(expand_leo_agency)

# Filter non-agency strings
leo = leo[~leo["agency_name"].str.lower().isin(_NON_AGENCY_VALUES)]

# Separation reason
leo["separation_reason"] = leo["sep_code"].apply(map_sep_code)

# Rank – keep as-is (already short codes; pipeline will handle)
leo["rank"] = leo["rank"].fillna("").astype(str).str.strip().str.upper()

# Type
leo["type"] = "POLICE"

# Build full_name
leo["full_name"] = (
    leo["last_name"].str.strip() + ", " + leo["first_name"].str.strip()
).str.lower()

print(f"  LEO rows after cleaning: {len(leo):,}")

# Select output columns
LEO_COLS = [
    "person_nbr", "first_name", "middle_name", "last_name", "suffix",
    "full_name", "agency_name", "start_date", "end_date",
    "separation_reason", "rank", "type",
]
leo_out = leo[LEO_COLS].copy()


# ===========================================================================
# SECTION 2 – Process Corrections (CDCR) data
# ===========================================================================

print("\nReading CDCR corrections data …")
cdcr_path = os.path.join(INPUT_DIR, "PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv")
cdcr_raw = pd.read_csv(cdcr_path, low_memory=False)
print(f"  CDCR rows: {len(cdcr_raw):,}")

# Standardise column names (strip & lower)
cdcr_raw.columns = [c.strip() for c in cdcr_raw.columns]

# Rename
cdcr = cdcr_raw.rename(columns={
    "UNIQUE ID":            "person_nbr_raw",
    "LAST NAME":            "last_name_raw",
    "FIRST NAME":           "first_middle_raw",
    "DEPARTMENT NAME":      "dept_name",
    "FACILITY NAME":        "facility_raw",
    "TRANS EFF DATE":       "trans_date",
    "TYPE OF TRANSACTION":  "trans_type",
    "POSITION NUMBER":      "position_number",
    "CLASS TITLE":          "class_title",
}).copy()

# person_nbr – use UNIQUE ID as string, lowercase, strip
cdcr["person_nbr"] = cdcr["person_nbr_raw"].astype(str).str.strip().str.lower()

# Drop records with no person_nbr
cdcr = cdcr[cdcr["person_nbr"].notna() & (cdcr["person_nbr"] != "") & (cdcr["person_nbr"] != "nan")]

# ---- Names ----
# LAST NAME and FIRST NAME (which may include middle initial) are separate columns
cdcr["last_name"]  = cdcr["last_name_raw"].fillna("").astype(str).str.strip().str.upper()
# FIRST NAME column format: "PAULINE C" (first + middle initial)
def split_first_middle(val):
    parts = str(val).strip().upper().split()
    if len(parts) == 0:
        return pd.Series({"first_name": "", "middle_name": ""})
    elif len(parts) == 1:
        return pd.Series({"first_name": parts[0], "middle_name": ""})
    else:
        # Last part is middle initial, rest is first name
        return pd.Series({"first_name": " ".join(parts[:-1]), "middle_name": parts[-1]})

name_parts = cdcr["first_middle_raw"].apply(split_first_middle)
cdcr["first_name"]  = name_parts["first_name"]
cdcr["middle_name"] = name_parts["middle_name"]
cdcr["suffix"]      = ""

# ---- Extract agency code from position_number ----
# position_number format: "061-424-9765-116" – first 3 digits are agency code
def extract_agency_code(pos_num):
    s = str(pos_num).strip()
    # Strip leading zeros inconsistency: normalise to 3-digit zero-padded
    m = re.match(r"0*(\d+)-", s)
    if m:
        return m.group(1).zfill(3)
    return ""

cdcr["agency_code"] = cdcr["position_number"].apply(extract_agency_code)

# ---- Build canonical agency name from agency code ----
# Use the most common facility_raw value for each agency_code as the canonical name
def build_agency_name_map(df):
    """Map agency_code -> canonical facility name (most frequent)."""
    mapping = {}
    grp = df[df["agency_code"] != ""].groupby("agency_code")
    for code, group in grp:
        # Get most common facility_raw for this code
        counts = group["facility_raw"].str.strip().str.upper().value_counts()
        if len(counts) > 0:
            mapping[code] = counts.index[0]
    return mapping

print("  Building agency code mapping …")
agency_code_map = build_agency_name_map(cdcr)

_FACILITY_EXPANSIONS = [
    (re.compile(r"\bSVS\b",       re.I), "SERVICES"),
    (re.compile(r"\bSVC\b",       re.I), "SERVICE"),
    (re.compile(r"\bCORR\.?\b",   re.I), "CORRECTIONS"),
    (re.compile(r"\bCNTR\b",      re.I), "CENTER"),
    (re.compile(r"\bCTR\b",       re.I), "CENTER"),
    (re.compile(r"\bTRN\b",       re.I), "TRAINING"),
    (re.compile(r"\bTRAIN\.?\b",  re.I), "TRAINING"),
    (re.compile(r"\bADMIN\.?\b",  re.I), "ADMINISTRATION"),
    (re.compile(r"\bDIV\.?\b",    re.I), "DIVISION"),
    (re.compile(r"\bDEPT\.?\b",   re.I), "DEPARTMENT"),
    (re.compile(r"\bINST\.?\b",   re.I), "INSTITUTION"),
    (re.compile(r"\bCA\.\b",      re.I), "CALIFORNIA"),
]

def expand_facility_name(name: str) -> str:
    s = str(name).strip().upper()
    for pat, repl in _FACILITY_EXPANSIONS:
        s = pat.sub(repl, s)
    return re.sub(r"\s+", " ", s).strip()

def get_corrections_agency(row):
    code = row["agency_code"]
    if code and code in agency_code_map:
        canonical = expand_facility_name(agency_code_map[code])
        return f"{code}: {canonical}"
    # Fallback to facility_raw
    facility = expand_facility_name(str(row["facility_raw"]).strip())
    return facility

cdcr["agency_name"] = cdcr.apply(get_corrections_agency, axis=1)

# ---- Build employment stints ----
# Strategy (per README):
# - Link SEPARATION records to the most recent preceding APPOINTMENT
#   by position_number, then flattened across changes.
# - Use trans_date for APPOINTMENT as start_date, SEPARATION as end_date.

# Parse dates first
cdcr["trans_date_parsed"] = cdcr["trans_date"].apply(safe_date)
# Filter to only rows with valid dates
cdcr = cdcr[cdcr["trans_date_parsed"] != ""]

# Separate appointments+changes vs separations
# NOTE: Some persons have only CHANGE records (no APPOINTMENT) - treat CHANGE as appointment too
appts = cdcr[cdcr["trans_type"].str.upper().str.strip().isin(["APPOINTMENT", "CHANGE"])].copy()
seps  = cdcr[cdcr["trans_type"].str.upper().str.strip() == "SEPARATION"].copy()
chgs  = cdcr[cdcr["trans_type"].str.upper().str.strip() == "CHANGE"].copy()

print(f"  Appointments+Changes: {len(appts):,}  Separations: {len(seps):,}")

# Normalise position_number for joining (strip leading zeros)
def norm_pos(s):
    s = str(s).strip()
    return re.sub(r"^0+(\d)", r"\1", s)

appts = appts.copy()
seps  = seps.copy()
appts["pos_norm"] = appts["position_number"].apply(norm_pos)
seps["pos_norm"]  = seps["position_number"].apply(norm_pos)

# Sort
appts = appts.sort_values(["person_nbr", "trans_date_parsed"])
seps  = seps.sort_values(["person_nbr", "trans_date_parsed"])

# Merge separations onto appointments on (person_nbr, pos_norm)
merged = seps.merge(
    appts[["person_nbr", "pos_norm", "trans_date_parsed", "agency_name",
           "class_title", "last_name", "first_name", "middle_name", "suffix"]],
    on=["person_nbr", "pos_norm"],
    how="left",
    suffixes=("_sep", "_appt"),
)

# Keep only appt.date <= sep.date
merged = merged[
    merged["trans_date_parsed_appt"].fillna("") <= merged["trans_date_parsed_sep"].fillna("")
]
merged = merged[merged["trans_date_parsed_appt"].fillna("") != ""]

# For each separation, take the most recent matching appointment
merged = (
    merged.sort_values("trans_date_parsed_appt", ascending=False)
    .drop_duplicates(subset=["person_nbr", "pos_norm", "trans_date_parsed_sep"])
)

merged.rename(columns={
    "trans_date_parsed_appt": "start_date",
    "trans_date_parsed_sep":  "end_date",
    "agency_name_appt":       "agency_name",
    "class_title_appt":       "rank",
    "last_name_appt":         "last_name",
    "first_name_appt":        "first_name",
    "middle_name_appt":       "middle_name",
    "suffix_appt":            "suffix",
}, inplace=True)

sep_records = merged[
    ["person_nbr", "last_name", "first_name", "middle_name", "suffix",
     "agency_name", "start_date", "end_date", "rank"]
].copy()

# Also include appointments that have NO separation (currently employed)
all_appt = appts.rename(columns={
    "trans_date_parsed": "start_date",
    "class_title":       "rank",
}).copy()
all_appt["end_date"] = ""

# Vectorised: mark appointments that were matched using a merge indicator
matched_appts = merged[["person_nbr", "pos_norm", "start_date"]].copy()
matched_appts["_matched"] = True

all_appt = all_appt.merge(
    matched_appts, on=["person_nbr", "pos_norm", "start_date"], how="left"
)
unmatched_appts = all_appt[all_appt["_matched"].isna()].copy()

unmatched_records = unmatched_appts[
    ["person_nbr", "last_name", "first_name", "middle_name", "suffix",
     "agency_name", "start_date", "end_date", "rank"]
].copy()

# Combine
cdcr_stints = pd.concat([sep_records, unmatched_records], ignore_index=True)

# Drop rows with empty start_date (shouldn't be any, but safety check)
cdcr_stints = cdcr_stints[cdcr_stints["start_date"] != ""]

# Deduplicate
cdcr_stints = cdcr_stints.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])

# Clean rank
cdcr_stints["rank"] = cdcr_stints["rank"].fillna("").astype(str).str.strip().str.upper()

# Type
cdcr_stints["type"] = "CORRECTIONS"

# full_name
cdcr_stints["full_name"] = (
    cdcr_stints["last_name"].str.strip() + ", " + cdcr_stints["first_name"].str.strip()
).str.lower()

# separation_reason – not available in CDCR data
cdcr_stints["separation_reason"] = ""

print(f"  CDCR stints after cleaning: {len(cdcr_stints):,}")

CORR_COLS = [
    "person_nbr", "first_name", "middle_name", "last_name", "suffix",
    "full_name", "agency_name", "start_date", "end_date",
    "separation_reason", "rank", "type",
]
cdcr_out = cdcr_stints[CORR_COLS].copy()


# ===========================================================================
# SECTION 3 – Combine and write output
# ===========================================================================

print("\nCombining LEO + Corrections data …")
combined = pd.concat([leo_out, cdcr_out], ignore_index=True)

# Final checks
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_cols = [c for c in required if c not in combined.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

# Ensure no empty start_date
empty_start = (combined["start_date"].isna() | (combined["start_date"] == "")).sum()
if empty_start > 0:
    print(f"  WARNING: dropping {empty_start} rows with empty start_date")
    combined = combined[combined["start_date"].fillna("") != ""]

# No fully duplicate rows
before = len(combined)
combined = combined.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
if len(combined) < before:
    print(f"  Dropped {before - len(combined):,} duplicate rows")

# Ensure person_nbr is lowercase string with no whitespace
combined["person_nbr"] = combined["person_nbr"].astype(str).str.lower().str.strip()

# Ensure end_date nulls → empty string (not "nan" or "NaT")
combined["end_date"] = combined["end_date"].fillna("").astype(str).str.strip()
combined.loc[combined["end_date"].isin(["nan", "NaT", "None", "NaN"]), "end_date"] = ""

# Also clean up other string columns
combined["separation_reason"] = combined["separation_reason"].fillna("").astype(str).str.strip()
combined.loc[combined["separation_reason"].isin(["nan", "NaT", "None", "NaN"]), "separation_reason"] = ""
combined["middle_name"] = combined["middle_name"].fillna("").astype(str).str.strip()
combined.loc[combined["middle_name"].isin(["nan", "NaT", "None", "NaN"]), "middle_name"] = ""
combined["suffix"] = combined["suffix"].fillna("").astype(str).str.strip()
combined.loc[combined["suffix"].isin(["nan", "NaT", "None", "NaN"]), "suffix"] = ""

print(f"\nTotal rows in output: {len(combined):,}")
print(f"  LEO rows:         {len(leo_out):,}")
print(f"  Corrections rows: {len(cdcr_out):,}")

# Write output
out_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
combined.to_csv(out_path, index=False)
print(f"\nWrote {out_path}")

# Summary stats
print(f"\nColumn null/empty counts:")
for col in required:
    empty = (combined[col].isna() | (combined[col].astype(str).str.strip() == "")).sum()
    pct = empty / len(combined) * 100
    print(f"  {col:20s}: {empty:6,} empty ({pct:.1f}%)")

print("\nDone.")
