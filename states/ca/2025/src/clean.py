"""
California POST & CDCR officer employment data cleaning script.

Reads:
  - CPRA_R000301-011425__ADHOC-809.xlsx  (LEO/POST data)
  - PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv  (Corrections data)

Produces:
  - output/ca_index.csv

Run from states/ca/2025/ as cwd:
  python src/clean.py --input-dir data/input --output-dir output
"""

import argparse
import os
import re

import pandas as pd

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean CA officer data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_dates_series(series, fmt="%m/%d/%Y"):
    """Vectorized date parse -> YYYY-MM-DD string series."""
    parsed = pd.to_datetime(series.astype(str).str.strip(), errors="coerce", format=fmt)
    return parsed.dt.strftime("%Y-%m-%d").fillna("")


def safe_date(val):
    """Scalar date parse -> YYYY-MM-DD or empty."""
    s = str(val).strip() if val is not None else ""
    if not s or s.lower() in ("nan", "nat", "none", "0000-00-00", "00/00/0000"):
        return ""
    parsed = pd.to_datetime(s, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# LEO agency name expansion
# ---------------------------------------------------------------------------

LEO_AGENCY_EXPANSIONS = [
    (r"\bCO\b", "COUNTY"),
    (r"\bSD\b", "SHERIFF'S DEPARTMENT"),
    (r"\bSO\b", "SHERIFF'S OFFICE"),
    (r"\bPD\b", "POLICE DEPARTMENT"),
    (r"\bDA\b", "DISTRICT ATTORNEY"),
    (r"\bDEPT\.?\b", "DEPARTMENT"),
    (r"\bDPS\b", "DEPARTMENT OF PUBLIC SAFETY"),
]

_LEO_AGENCY_RE = [(re.compile(p), r) for p, r in LEO_AGENCY_EXPANSIONS]
_TRAILING_CODE_RE = re.compile(r"\s+C-\d+\s*$")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def expand_leo_agency(name):
    if not name or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).strip()
    s = _TRAILING_CODE_RE.sub("", s).strip()
    for pat, repl in _LEO_AGENCY_RE:
        s = pat.sub(repl, s)
    return _MULTI_SPACE_RE.sub(" ", s).strip()


# ---------------------------------------------------------------------------
# Name parsing (LEO: "LAST, FIRST MIDDLE [SUFFIX]")
# ---------------------------------------------------------------------------

SUFFIX_WORDS = {"JR", "SR", "II", "III", "IV", "V", "ESQ"}


def parse_officer_name(s):
    """Parse 'LAST, FIRST MIDDLE [SUFFIX]' → (last, first, middle, suffix)."""
    s = str(s).strip()
    if "," in s:
        last, rest = s.split(",", 1)
        rest = rest.strip()
    else:
        parts = s.split(None, 1)
        last = parts[0] if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

    last = last.strip().upper()
    parts = rest.split()
    if not parts:
        return last, "", "", ""
    first = parts[0].upper()
    suffix = ""
    middle = ""
    if len(parts) > 1:
        last_part = parts[-1].upper().rstrip(".")
        if last_part in SUFFIX_WORDS:
            suffix = parts[-1].upper()
            middle = " ".join(parts[1:-1]).upper()
        else:
            middle = " ".join(parts[1:]).upper()
    return last, first, middle, suffix


# ---------------------------------------------------------------------------
# SECTION 1: LEO (POST) data
# ---------------------------------------------------------------------------
print("Loading LEO (POST) data ...")

LEO_FILE = os.path.join(INPUT_DIR, "CPRA_R000301-011425__ADHOC-809.xlsx")

leo_raw = pd.read_excel(LEO_FILE, sheet_name="Sheet1", dtype=str)
sep_codes = pd.read_excel(LEO_FILE, sheet_name="Separation Codes", dtype=str)
print(f"  LEO raw rows: {len(leo_raw)}")

# Rename
leo = leo_raw.rename(columns={
    "POST_ID": "person_nbr",
    "officer_name": "officer_name_raw",
    "agency": "agency_raw",
    "employment_start_date": "start_date_raw",
    "employment_end_date": "end_date_raw",
    "separation_code": "separation_code",
    "rank": "rank",
})

# person_nbr: lowercase + strip
leo["person_nbr"] = leo["person_nbr"].astype(str).str.strip().str.lower()
leo = leo[leo["person_nbr"].notna() & ~leo["person_nbr"].isin(["", "nan"])]

# Parse names (fast vectorized approach)
print("  Parsing LEO names ...")
parsed_tuples = leo["officer_name_raw"].apply(parse_officer_name)
leo["last_name"]   = parsed_tuples.apply(lambda x: x[0])
leo["first_name"]  = parsed_tuples.apply(lambda x: x[1])
leo["middle_name"] = parsed_tuples.apply(lambda x: x[2])
leo["suffix"]      = parsed_tuples.apply(lambda x: x[3])

# Build full_name: "last, first middle [suffix]" (lowercase)
def build_full_name(row):
    parts = [row["first_name"]]
    if row["middle_name"]:
        parts.append(row["middle_name"])
    body = " ".join(parts)
    name = f"{row['last_name']}, {body}"
    if row["suffix"]:
        name += " " + row["suffix"]
    return name.lower()

leo["full_name"] = leo.apply(build_full_name, axis=1)

# Dates (vectorized)
leo["start_date"] = parse_dates_series(leo["start_date_raw"])
leo["end_date"]   = parse_dates_series(leo["end_date_raw"])

# Drop empty start_date
before = len(leo)
leo = leo[leo["start_date"] != ""]
print(f"  Dropped {before - len(leo)} LEO rows with empty start_date")

# Agency names
leo["agency_name"] = leo["agency_raw"].apply(expand_leo_agency)

NON_AGENCY = {"", "nan", "n/a", "unknown", "pending", "application denied", "application purged"}
leo = leo[~leo["agency_name"].str.lower().isin(NON_AGENCY)]

# Separation reason
sep_codes["separation_code"] = sep_codes["separation_code"].astype(str).str.strip()
sep_codes["separation_desc"] = sep_codes["separation_desc"].astype(str).str.strip()
sep_map = dict(zip(sep_codes["separation_code"], sep_codes["separation_desc"]))
leo["separation_reason"] = leo["separation_code"].astype(str).str.strip().map(sep_map).fillna("")

# Rank
leo["rank"] = leo["rank"].astype(str).str.strip().str.upper().replace("NAN", "")
leo["type"] = "POLICE"

# Dedup
before = len(leo)
leo = leo.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
if len(leo) < before:
    print(f"  Dropped {before - len(leo)} duplicate LEO rows")

COMMON_COLS = ["person_nbr", "first_name", "middle_name", "last_name", "suffix",
               "full_name", "agency_name", "rank", "start_date", "end_date",
               "separation_reason", "type"]

leo_out = leo.reindex(columns=COMMON_COLS).fillna("")
print(f"  LEO output rows: {len(leo_out)}")


# ---------------------------------------------------------------------------
# SECTION 2: CDCR corrections data
# ---------------------------------------------------------------------------
print("Loading CDCR corrections data ...")

CDCR_FILE = os.path.join(INPUT_DIR, "PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv")
cdcr_raw = pd.read_csv(CDCR_FILE, dtype=str, low_memory=False)
print(f"  CDCR raw rows: {len(cdcr_raw)}")

# Strip all string columns
for col in cdcr_raw.columns:
    cdcr_raw[col] = cdcr_raw[col].str.strip()

cdcr_raw = cdcr_raw.rename(columns={
    "LAST NAME": "last_name",
    "FIRST NAME": "first_middle",
    "FACILITY NAME": "facility_name",
    "TRANS EFF DATE": "trans_date",
    "TYPE OF TRANSACTION": "trans_type",
    "POSITION NUMBER": "position_number",
    "CLASS TITLE": "class_title",
    "UNIQUE ID": "person_nbr",
})

cdcr_raw = cdcr_raw[cdcr_raw["person_nbr"].notna() & ~cdcr_raw["person_nbr"].isin(["", "nan"])]

# Parse first_name / middle from "FIRST MIDDLE_INITIAL"
def split_first_middle(s):
    parts = str(s).strip().split()
    if len(parts) >= 2:
        return parts[0].upper(), parts[-1].upper()
    elif len(parts) == 1:
        return parts[0].upper(), ""
    return "", ""

parsed_fm = cdcr_raw["first_middle"].apply(split_first_middle)
cdcr_raw["first_name"]  = parsed_fm.apply(lambda x: x[0])
cdcr_raw["middle_name"] = parsed_fm.apply(lambda x: x[1])
cdcr_raw["last_name"]   = cdcr_raw["last_name"].str.upper()

# Dates (vectorized)
cdcr_raw["trans_date_parsed"] = parse_dates_series(cdcr_raw["trans_date"], fmt="%m/%d/%Y")
cdcr_valid = cdcr_raw[cdcr_raw["trans_date_parsed"] != ""].copy()
cdcr_valid["trans_date_dt"] = pd.to_datetime(cdcr_valid["trans_date_parsed"])

# Extract agency code from position_number (NNN-xxx...)
_AGENCY_CODE_RE = re.compile(r"^(\d+)-")

def extract_agency_code(pos):
    m = _AGENCY_CODE_RE.match(str(pos).strip())
    return m.group(1).zfill(3) if m else None

cdcr_valid["agency_code"] = cdcr_valid["position_number"].apply(extract_agency_code)

# Canonical agency name: "NNN: MOST COMMON FACILITY NAME"
agency_map_df = (
    cdcr_valid[cdcr_valid["agency_code"].notna()]
    .groupby("agency_code")["facility_name"]
    .agg(lambda x: x.value_counts().index[0])
    .reset_index()
    .rename(columns={"facility_name": "canonical_facility"})
)
code_to_facility = dict(zip(agency_map_df["agency_code"], agency_map_df["canonical_facility"]))

cdcr_valid["agency_name"] = cdcr_valid["agency_code"].apply(
    lambda c: f"{c}: {code_to_facility.get(c, '').upper()}" if c else ""
)

# Normalize position number (strip leading zeros from first segment)
_POS_NORM_RE = re.compile(r"^0*(\d+)(-.+)")

def norm_pos(p):
    m = _POS_NORM_RE.match(str(p).strip())
    return (m.group(1) + m.group(2)) if m else str(p).strip()

cdcr_valid["pos_norm"] = cdcr_valid["position_number"].apply(norm_pos)
cdcr_valid["class_title_clean"] = cdcr_valid["class_title"].fillna("").str.strip()

# Sort
cdcr_valid = cdcr_valid.sort_values(["person_nbr", "trans_date_dt"])

print("  Building CDCR stints ...")


def build_stints_for_person(rows):
    """
    rows: list of tuples (date_str, date_dt, trans_type, pos_norm,
                          agency_code, class_title, agency_name)
    Returns list of (start_date, end_date, agency_name, rank).
    """
    stints = []
    open_appts = []  # [{start_date, start_dt, pos_norm, agency_code, class_title, agency_name}]

    for (date_str, date_dt, ttype, p_norm, acode, ctitle, aname) in rows:
        if ttype in ("APPOINTMENT", "CHANGE"):
            open_appts.append({
                "start_date": date_str,
                "start_dt": date_dt,
                "pos_norm": p_norm,
                "agency_code": acode,
                "class_title": ctitle,
                "agency_name": aname,
            })
        elif ttype == "SEPARATION":
            matched_idx = None
            # Priority 1: exact normalized position_number (most recent first)
            for i in range(len(open_appts) - 1, -1, -1):
                a = open_appts[i]
                if a["start_dt"] <= date_dt and a["pos_norm"] == p_norm:
                    matched_idx = i
                    break
            # Priority 2: same agency_code + class_title
            if matched_idx is None:
                for i in range(len(open_appts) - 1, -1, -1):
                    a = open_appts[i]
                    if (a["start_dt"] <= date_dt and
                            a["agency_code"] == acode and
                            a["class_title"] == ctitle):
                        matched_idx = i
                        break
            # Priority 3: same agency_code only
            if matched_idx is None:
                for i in range(len(open_appts) - 1, -1, -1):
                    a = open_appts[i]
                    if a["start_dt"] <= date_dt and a["agency_code"] == acode:
                        matched_idx = i
                        break

            if matched_idx is not None:
                a = open_appts.pop(matched_idx)
                stints.append((a["start_date"], date_str, a["agency_name"], a["class_title"]))
            else:
                stints.append(("", date_str, aname, ctitle))  # no start -> dropped

    # Remaining open appointments = currently employed
    for a in open_appts:
        stints.append((a["start_date"], "", a["agency_name"], a["class_title"]))

    return stints


all_stints = []
for person_nbr, grp in cdcr_valid.groupby("person_nbr"):
    vc_last  = grp["last_name"].value_counts()
    vc_first = grp["first_name"].value_counts()
    vc_mid   = grp["middle_name"].value_counts()
    last_name  = vc_last.index[0]  if len(vc_last)  else ""
    first_name = vc_first.index[0] if len(vc_first) else ""
    middle_name = vc_mid.index[0]  if len(vc_mid)   else ""

    rows = list(zip(
        grp["trans_date_parsed"],
        grp["trans_date_dt"],
        grp["trans_type"],
        grp["pos_norm"],
        grp["agency_code"].fillna(""),
        grp["class_title_clean"],
        grp["agency_name"].fillna(""),
    ))

    for (sd, ed, an, rk) in build_stints_for_person(rows):
        all_stints.append({
            "person_nbr":   person_nbr,
            "first_name":   first_name,
            "middle_name":  middle_name,
            "last_name":    last_name,
            "suffix":       "",
            "agency_name":  an,
            "rank":         rk,
            "start_date":   sd,
            "end_date":     ed,
            "type":         "CORRECTIONS",
        })

cdcr_stints = pd.DataFrame(all_stints)
print(f"  CDCR stints built: {len(cdcr_stints)}")

# Drop empty start_date
before = len(cdcr_stints)
cdcr_stints = cdcr_stints[cdcr_stints["start_date"] != ""]
print(f"  Dropped {before - len(cdcr_stints)} CDCR stints with empty start_date")

# Drop empty agency_name
cdcr_stints = cdcr_stints[cdcr_stints["agency_name"] != ""]

# Clean rank
cdcr_stints["rank"] = cdcr_stints["rank"].astype(str).str.strip().str.upper()
cdcr_stints.loc[cdcr_stints["rank"] == "NAN", "rank"] = ""

# Dedup
before = len(cdcr_stints)
cdcr_stints = cdcr_stints.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
if len(cdcr_stints) < before:
    print(f"  Dropped {before - len(cdcr_stints)} duplicate CDCR rows")

# full_name
cdcr_stints["full_name"] = (
    cdcr_stints["last_name"].str.strip() + ", " +
    cdcr_stints["first_name"].str.strip() + " " +
    cdcr_stints["middle_name"].str.strip()
).str.strip().str.lower()

cdcr_stints["separation_reason"] = ""

cdcr_out = cdcr_stints.reindex(columns=COMMON_COLS).fillna("")
print(f"  CDCR output rows: {len(cdcr_out)}")


# ---------------------------------------------------------------------------
# SECTION 3: Combine and write
# ---------------------------------------------------------------------------
print("Combining LEO + CDCR ...")

combined = pd.concat([leo_out, cdcr_out], ignore_index=True)
print(f"  Combined rows: {len(combined)}")

# Final validation
required = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
for col in required:
    empty = (combined[col].isna() | (combined[col] == "")).sum()
    if empty > 0:
        print(f"  Warning: {col} has {empty} empty values")

combined = combined[combined["start_date"].fillna("") != ""]

before = len(combined)
combined = combined.drop_duplicates(subset=["person_nbr", "agency_name", "start_date"])
if len(combined) < before:
    print(f"  Dropped {before - len(combined)} final duplicate rows")

output_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
combined.to_csv(output_path, index=False)
print(f"\nWrote {len(combined)} rows to {output_path}")
print("Done.")
