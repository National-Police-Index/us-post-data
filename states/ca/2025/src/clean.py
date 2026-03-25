"""
California POST & CDCR officer employment index cleaner.
Processes:
  1. LEO data:  CPRA_R000301-011425__ADHOC-809.xlsx
  2. Corrections data: PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv
Outputs: ca_index.csv
"""
import argparse
import os
import re

import pandas as pd
from nameparser import HumanName

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean California POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def vec_date(series, fmt="%m/%d/%Y"):
    """Vectorized date parse → YYYY-MM-DD string or ''."""
    parsed = pd.to_datetime(series, format=fmt, errors="coerce")
    result = parsed.dt.strftime("%Y-%m-%d")
    result = result.fillna("")
    # Guard against NaT string
    result = result.replace("NaT", "")
    return result


def parse_full_name(name_str):
    """Parse 'LAST, FIRST MIDDLE SUFFIX' into components."""
    s = str(name_str).strip()
    if not s or s.lower() in ("nan", "none", ""):
        return pd.Series(
            {"last_name": "", "first_name": "", "middle_name": "", "suffix": ""}
        )
    name = HumanName(s)
    return pd.Series(
        {
            "last_name": name.last.strip(),
            "first_name": name.first.strip(),
            "middle_name": name.middle.strip(),
            "suffix": name.suffix.strip(),
        }
    )


# ---------------------------------------------------------------------------
# Separation code → reason (LEO data)
# ---------------------------------------------------------------------------
SEP_CODE_MAP = {
    "1": "Resigned",
    "2": "Discharged",
    "3": "Retired",
    "4": "Deceased",
    "5": "Felony",
    "6": "Other",
    "7": "Promotion/Demotion",
    "8": "Involuntary Separation",
    "9": "Separated Pending Complaint, Administrative Charge, or Investigation for Serious Misconduct",
    "10": "Status Change",
    "11": "Did Not Complete Probation",
    "Z": "Unknown",
    " ": "",
    "": "",
}

# ---------------------------------------------------------------------------
# Rank abbreviation map (LEO data)
# ---------------------------------------------------------------------------
RANK_MAP = {
    "PO": "POLICE OFFICER",
    "RI": "RESERVE/INTERMITTENT",
    "DPTY": "DEPUTY",
    "TRN": "TRAINEE",
    "RANG": "RANGER",
    "DMAR": "DEPUTY MARSHAL",
    "INV": "INVESTIGATOR",
    "CPL": "CORPORAL",
    "JDEP": "JAILER/DEPUTY",
    "SGT": "SERGEANT",
    "LT": "LIEUTENANT",
    "CAPT": "CAPTAIN",
    "CMD": "COMMANDER",
    "CHIF": "CHIEF",
    "DIR": "DIRECTOR",
    "SPEC": "SPECIALIST",
    "SUPV": "SUPERVISOR",
    "DET": "DETECTIVE",
    "MAR": "MARSHAL",
}

# ---------------------------------------------------------------------------
# Agency abbreviation expansions for LEO data
# ---------------------------------------------------------------------------
LEO_AGENCY_EXPANSIONS = [
    (r"\bUC\b", "UNIVERSITY OF CALIFORNIA"),
    (r"\bCSU\b", "CALIFORNIA STATE UNIVERSITY"),
    # Leading CA → CALIFORNIA
    (r"^CA\b", "CALIFORNIA"),
    (r"\bCA\b", "CALIFORNIA"),          # catch remaining mid-word CA
    (r"\bDEPT\b", "DEPARTMENT"),
    (r"\bDPS\b", "DEPARTMENT OF PUBLIC SAFETY"),
    # Sheriff
    (r"\bSD\b", "SHERIFF'S DEPARTMENT"),
    (r"\bSO\b", "SHERIFF'S OFFICE"),
    # Police
    (r"\bPD\b", "POLICE DEPARTMENT"),
    # County
    (r"\bCO\b", "COUNTY"),
    # Other
    (r"\bDA\b", "DISTRICT ATTORNEY"),
    (r"\bOFC\b", "OFFICE"),
    (r"\bINVEST\b", "INVESTIGATIONS"),
    (r"\bENF\b", "ENFORCEMENT"),
    (r"\bDIV\b", "DIVISION"),
    (r"\bASST\b", "ASSISTANT"),
    (r"\bSVCS\b", "SERVICES"),
    (r"\bSVC\b", "SERVICE"),
    (r"\bCNTL\b", "CONTROL"),
    (r"\bCTRL\b", "CONTROL"),
    (r"\bPUB\b", "PUBLIC"),
    (r"\bINST\b", "INSTITUTION"),
    (r"\bUNIF\b", "UNIFIED"),
    (r"\bSCHL\b", "SCHOOL"),
    (r"\bDIST\b", "DISTRICT"),
    (r"\bAUTH\b", "AUTHORITY"),
    (r"\bCMTY\b", "COMMUNITY"),
    (r"\bCOLL\b", "COLLEGE"),
    (r"\bSPEC\b", "SPECIAL"),
    (r"\bHWY\b", "HIGHWAY"),
]


def expand_leo_agency(name):
    if not name or pd.isna(name):
        return ""
    s = str(name).strip().upper()
    s = re.sub(r"\s+", " ", s).strip()
    for pattern, replacement in LEO_AGENCY_EXPANSIONS:
        s = re.sub(pattern, replacement, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Position number helpers (corrections)
# ---------------------------------------------------------------------------
_POS_NORM_RE = re.compile(r"^0+(\d)")
_AGENCY_CODE_RE = re.compile(r"^0*(\d{3})")
_CLASS_CODE_RE = re.compile(r"^\d+-\d+-(\d+)-")


def normalize_pos(pos):
    if not pos or pos == "nan":
        return ""
    return _POS_NORM_RE.sub(r"\1", pos.strip())


def extract_agency_code(pos):
    if not pos or pos == "nan":
        return ""
    # Match 2 or 3 leading digits (some position numbers drop leading zero)
    m = re.match(r"^0*(\d{2,3})", pos.strip())
    return m.group(1).zfill(3) if m else ""


def extract_class_code(pos):
    if not pos or pos == "nan":
        return ""
    m = _CLASS_CODE_RE.match(pos.strip())
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# LEO DATA
# ---------------------------------------------------------------------------
print("Loading LEO data...")
leo_path = os.path.join(INPUT_DIR, "CPRA_R000301-011425__ADHOC-809.xlsx")
leo = pd.read_excel(leo_path, dtype=str)
print(f"  LEO raw shape: {leo.shape}")

# Strip all string columns
for col in leo.columns:
    leo[col] = leo[col].astype(str).str.strip()

leo.rename(
    columns={
        "POST_ID": "person_nbr",
        "officer_name": "full_name_raw",
        "agency": "agency_raw",
        "employment_start_date": "start_date_raw",
        "employment_end_date": "end_date_raw",
        "separation_code": "sep_code",
        "rank": "rank_raw",
        "app_status": "app_status",
    },
    inplace=True,
)

# Clean person_nbr
leo["person_nbr"] = leo["person_nbr"].str.strip()
leo = leo[leo["person_nbr"].notna() & (leo["person_nbr"] != "") & (leo["person_nbr"] != "nan")]

# Parse names
print("  Parsing LEO names...")
name_parts = leo["full_name_raw"].apply(parse_full_name)
leo = pd.concat([leo.reset_index(drop=True), name_parts.reset_index(drop=True)], axis=1)

# Vectorized dates
leo["start_date"] = vec_date(leo["start_date_raw"])
leo["end_date"] = vec_date(leo["end_date_raw"])

# Separation reason
leo["sep_code_clean"] = leo["sep_code"].str.strip()
leo["separation_reason"] = leo["sep_code_clean"].map(SEP_CODE_MAP).fillna("")

# Agency expansion
print("  Expanding LEO agency names...")
leo["agency_name"] = leo["agency_raw"].apply(expand_leo_agency)

# Rank expansion
leo["rank"] = leo["rank_raw"].map(RANK_MAP).fillna(leo["rank_raw"])

# Build full_name
def build_full_name(row):
    ln = str(row["last_name"]).strip()
    fn = str(row["first_name"]).strip()
    mn = str(row["middle_name"]).strip()
    sx = str(row["suffix"]).strip()
    rest_parts = [fn]
    if mn:
        rest_parts.append(mn)
    if sx:
        rest_parts.append(sx)
    rest = " ".join(rest_parts)
    return (f"{ln}, {rest}").upper() if ln else ""

leo["full_name"] = leo.apply(build_full_name, axis=1)

# Select & filter
leo_out = leo[
    ["person_nbr", "full_name", "first_name", "middle_name", "last_name", "suffix",
     "agency_name", "start_date", "end_date", "rank", "separation_reason"]
].copy()

leo_out = leo_out[leo_out["start_date"] != ""]

print(f"  LEO cleaned shape: {leo_out.shape}")


# ---------------------------------------------------------------------------
# CORRECTIONS DATA
# ---------------------------------------------------------------------------
print("Loading corrections data...")
corr_path = os.path.join(INPUT_DIR, "PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv")
corr = pd.read_csv(corr_path, dtype=str, low_memory=False)
for col in corr.columns:
    corr[col] = corr[col].astype(str).str.strip()
print(f"  Corrections raw shape: {corr.shape}")

# Extract codes
corr["pos_norm"] = corr["POSITION NUMBER"].apply(normalize_pos)
corr["agency_code"] = corr["POSITION NUMBER"].apply(extract_agency_code)
corr["class_code"] = corr["POSITION NUMBER"].apply(extract_class_code)

# Vectorized dates
corr["trans_date"] = vec_date(corr["TRANS EFF DATE"])
corr["trans_type"] = corr["TYPE OF TRANSACTION"].str.strip().str.upper()

# person_nbr from UNIQUE ID
corr["person_nbr"] = corr["UNIQUE ID"].str.strip()

# ---- Names ----
corr["last_name"] = corr["LAST NAME"].str.upper()

def parse_first_middle(val):
    val = str(val).strip()
    if not val or val == "nan":
        return pd.Series({"first_name": "", "middle_name": ""})
    parts = val.split()
    first = parts[0].upper() if parts else ""
    middle = parts[1].upper() if len(parts) > 1 else ""
    return pd.Series({"first_name": first, "middle_name": middle})

print("  Parsing corrections names...")
nm = corr["FIRST NAME"].apply(parse_first_middle)
corr = pd.concat([corr.reset_index(drop=True), nm.reset_index(drop=True)], axis=1)
corr["suffix"] = ""


def build_corr_full_name(row):
    ln = str(row["last_name"]).strip()
    fn = str(row["first_name"]).strip()
    mn = str(row["middle_name"]).strip()
    rest = " ".join(p for p in [fn, mn] if p)
    return f"{ln}, {rest}".upper() if ln else ""

corr["full_name"] = corr.apply(build_corr_full_name, axis=1)

# ---- Agency name lookup ----
print("  Building corrections agency name lookup...")
code_facility_counts = (
    corr[corr["agency_code"] != ""]
    .groupby(["agency_code", "FACILITY NAME"])
    .size()
    .reset_index(name="cnt")
    .sort_values(["agency_code", "cnt"], ascending=[True, False])
)

_CORR_EXPANSIONS = [
    (r"\bCA\.\b", "CALIFORNIA"),
    (r"\bCALIF\b", "CALIFORNIA"),
    (r"\bCORR\b", "CORRECTIONS"),
    (r"\bFACIL\b", "FACILITY"),
    (r"\bCNTR\b", "CENTER"),
    (r"\bCTR\b", "CENTER"),
    (r"\bYTH\b", "YOUTH"),
    (r"\bSVS\b", "SERVICES"),
    (r"\bTRAIN\b", "TRAINING"),
]

def expand_corr_facility(name):
    s = str(name).strip()
    for pat, rep in _CORR_EXPANSIONS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s+", " ", s).strip()

agency_lookup = {}
for code, grp in code_facility_counts.groupby("agency_code"):
    names = [expand_corr_facility(n) for n in grp["FACILITY NAME"].tolist()]
    if len(names) == 1:
        agency_lookup[code] = f"{code}: {names[0]}"
    else:
        agency_lookup[code] = f"{code}: {' -AKA- '.join(names)}"

corr["agency_name"] = corr["agency_code"].map(agency_lookup).fillna("")

# ---- Class title (rank) lookup ----
class_title_counts = (
    corr[corr["class_code"] != ""]
    .groupby(["class_code", "CLASS TITLE"])
    .size()
    .reset_index(name="cnt")
    .sort_values(["class_code", "cnt"], ascending=[True, False])
)
class_title_lookup = {
    code: grp.iloc[0]["CLASS TITLE"].strip()
    for code, grp in class_title_counts.groupby("class_code")
}
corr["rank"] = corr["class_code"].map(class_title_lookup).fillna(corr["CLASS TITLE"].str.strip())

# ---- Build employment history (vectorized) ----
print("  Building corrections employment history (vectorized)...")

NAME_COLS = [
    "person_nbr", "last_name", "first_name", "middle_name", "suffix",
    "full_name", "agency_name", "agency_code", "class_code", "rank",
]

# Include CHANGE records as potential stint starts (per README: flattened same-rank stints)
appts_changes = corr[corr["trans_type"].isin(["APPOINTMENT", "CHANGE"])].copy()
appts_only = corr[corr["trans_type"] == "APPOINTMENT"].copy()
seps = corr[corr["trans_type"] == "SEPARATION"].copy()

# Canonical: earliest record per (person_nbr, pos_norm) from both APPOINTMENT and CHANGE
canonical = (
    appts_changes.sort_values("trans_date")
    .groupby(["person_nbr", "pos_norm"])
    .first()
    .reset_index()
)
print(f"  Canonical appts/changes: {len(canonical)}")

# Pass 1: match canonical to seps on pos_norm — use EARLIEST sep after canonical date
m1 = canonical.merge(
    seps[["person_nbr", "pos_norm", "trans_date"]].rename(columns={"trans_date": "sep_date"}),
    on=["person_nbr", "pos_norm"],
    how="left",
)
m1 = m1[m1["sep_date"].fillna("") >= m1["trans_date"].fillna("")]
# Earliest sep per canonical (person, pos_norm, start_date)
m1 = m1.sort_values("sep_date").drop_duplicates(
    subset=["person_nbr", "pos_norm", "trans_date"], keep="first"
)

# Pass 2: unmatched canonical → fallback on agency_code + class_code using APPOINTMENTS only
matched_p1 = set(zip(m1["person_nbr"], m1["pos_norm"], m1["trans_date"]))
canonical2 = canonical[
    ~pd.Series(
        list(zip(canonical["person_nbr"], canonical["pos_norm"], canonical["trans_date"])),
        index=canonical.index,
    ).isin(matched_p1)
].copy()

# Earliest appointment per (person, agency_code, class_code) for fallback
earliest_appts_ac = (
    appts_only.sort_values("trans_date")
    .groupby(["person_nbr", "agency_code", "class_code"])
    .first()
    .reset_index()
)

m2 = canonical2.merge(
    seps[["person_nbr", "agency_code", "class_code", "trans_date"]].rename(
        columns={"trans_date": "sep_date"}
    ),
    on=["person_nbr", "agency_code", "class_code"],
    how="left",
)
m2 = m2[m2["sep_date"].fillna("") >= m2["trans_date"].fillna("")]
m2 = m2.sort_values("sep_date").drop_duplicates(
    subset=["person_nbr", "agency_code", "class_code", "trans_date"], keep="first"
)

# Build matched sep records (start=canonical_date, end=sep_date)
def make_sep_emp_records(df, sep_col="sep_date"):
    out = df[NAME_COLS].copy()
    out = out.reset_index(drop=True)
    out["start_date"] = df["trans_date"].values
    out["end_date"] = df[sep_col].values
    return out

sep_records = pd.concat(
    [make_sep_emp_records(m1), make_sep_emp_records(m2)], ignore_index=True
)

# All unmatched canonical records → open-ended (currently employed)
matched_all = matched_p1 | set(zip(m2["person_nbr"], m2["pos_norm"], m2["trans_date"]))
canonical_open = canonical[
    ~pd.Series(
        list(zip(canonical["person_nbr"], canonical["pos_norm"], canonical["trans_date"])),
        index=canonical.index,
    ).isin(matched_all)
].copy()
open_records = canonical_open[NAME_COLS].copy()
open_records = open_records.reset_index(drop=True)
open_records["start_date"] = canonical_open["trans_date"].values
open_records["end_date"] = ""

corr_emp = pd.concat([sep_records, open_records], ignore_index=True)

print(f"  Corrections employment records (pre-dedup): {len(corr_emp)}")

# Drop rows with no start_date
corr_emp = corr_emp[corr_emp["start_date"].fillna("") != ""]

# Deduplicate on (person_nbr, agency_name, start_date), prefer rows with end_date
corr_emp = corr_emp.sort_values(
    ["person_nbr", "agency_name", "start_date", "end_date"],
    ascending=[True, True, True, False],
)
corr_emp = corr_emp.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
corr_emp["separation_reason"] = ""

print(f"  Corrections employment cleaned shape: {corr_emp.shape}")


# ---------------------------------------------------------------------------
# Combine LEO and Corrections
# ---------------------------------------------------------------------------
print("Combining LEO and corrections data...")

FINAL_COLS = [
    "person_nbr", "full_name", "first_name", "middle_name", "last_name", "suffix",
    "agency_name", "start_date", "end_date", "rank", "separation_reason",
]

for col in FINAL_COLS:
    if col not in leo_out.columns:
        leo_out[col] = ""
    if col not in corr_emp.columns:
        corr_emp[col] = ""

leo_final = leo_out[FINAL_COLS].copy()
corr_final = corr_emp[FINAL_COLS].copy()

for df in [leo_final, corr_final]:
    for col in FINAL_COLS:
        df[col] = df[col].astype(str).str.strip().replace("nan", "")

combined = pd.concat([leo_final, corr_final], ignore_index=True)

# Final dedup
dupe_check = combined.duplicated(subset=["person_nbr", "agency_name", "start_date"])
if dupe_check.any():
    print(f"  Warning: dropping {dupe_check.sum()} duplicate rows")
    combined = combined.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])

combined = combined[combined["start_date"] != ""]

# Validate required columns
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_cols = [c for c in required if c not in combined.columns]
assert not missing_cols, f"Missing required columns: {missing_cols}"

print(f"Final combined shape: {combined.shape}")
print(f"  LEO rows: {len(leo_final)}, Corrections rows: {len(corr_final)}")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
output_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
combined.to_csv(output_path, index=False)
print(f"Wrote {output_path}")
