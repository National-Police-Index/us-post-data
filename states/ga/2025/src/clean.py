"""
Georgia POST data cleaning script — 2025
Produces:
  - output/ga_index.csv              (employment index)
  - output/ga-discipline_index.csv   (discipline index)
"""

import argparse
import os

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helper: vectorized date cleaning
# ---------------------------------------------------------------------------
INVALID_DATES = {"nan", "NaT", "None", ""}


def clean_date_series(series):
    """
    Return a string series with YYYY-MM-DD dates or empty string.
    Preserves '0000-00-00' as-is (groundtruth uses it for open-ended records).
    Strips obvious invalid values to empty string.
    """
    s = series.astype(str).str.strip()
    # Mark invalid values as empty
    invalid_mask = s.isin(INVALID_DATES)
    s = s.where(~invalid_mask, "")
    # Rows that are not empty and not already 0000-00-00 — parse and reformat
    need_parse = (s != "") & (s != "0000-00-00")
    if need_parse.any():
        parsed = pd.to_datetime(s[need_parse], errors="coerce")
        formatted = parsed.dt.strftime("%Y-%m-%d").fillna("")
        s = s.copy()
        s.loc[need_parse] = formatted
    return s


# ---------------------------------------------------------------------------
# Load raw files
# ---------------------------------------------------------------------------
print("Loading raw files...")

emp = pd.read_csv(os.path.join(INPUT_DIR, "officer_employment.csv"), dtype=str)
od = pd.read_csv(os.path.join(INPUT_DIR, "officer_data.csv"), dtype=str)
viol = pd.read_csv(os.path.join(INPUT_DIR, "officer_violations.csv"), dtype=str)
sanc = pd.read_csv(os.path.join(INPUT_DIR, "officer_sanctions.csv"), dtype=str)

print(f"  Employment rows:  {len(emp):,}")
print(f"  Officer data:     {len(od):,}")
print(f"  Violations:       {len(viol):,}")
print(f"  Sanctions:        {len(sanc):,}")

# ---------------------------------------------------------------------------
# Clean officer demographics (officer_data.csv)
# ---------------------------------------------------------------------------
od = od.copy()
od["person_nbr"] = od["OKEY"].astype(str).str.lower().str.strip()
od["last_name"] = od["LAST NAME"].astype(str).str.strip()
od["first_name"] = od["FIRST NAME"].astype(str).str.strip()
od["middle_name"] = od["MIDDLE"].astype(str).str.strip().replace({"nan": ""})
od["suffix"] = od["SUFFIX"].astype(str).str.strip().replace({"nan": ""})
od["year_of_birth"] = od["YOB"].astype(str).str.strip().replace({"nan": ""})
od["sex"] = od["SEX"].astype(str).str.strip()
od["race"] = od["RACE"].astype(str).str.strip()


# Build full_name vectorized: "last, first [middle] [suffix]" (lowercase)
def _build_full_name_vec(df):
    last = df["last_name"].str.lower().str.strip()
    first = df["first_name"].str.lower().str.strip()
    mid = df["middle_name"].str.lower().str.strip()
    suf = df["suffix"].str.lower().str.strip()

    name = last + ", " + first
    has_mid = mid.notna() & (mid != "") & (mid != "nan")
    name = name.where(~has_mid, name + " " + mid)
    has_suf = suf.notna() & (suf != "") & (suf != "nan")
    name = name.where(~has_suf, name + " " + suf)
    return name


od["full_name"] = _build_full_name_vec(od)

# Columns to carry into merged tables
OD_COLS = [
    "person_nbr",
    "last_name",
    "first_name",
    "middle_name",
    "suffix",
    "year_of_birth",
    "race",
    "sex",
    "full_name",
]

# ---------------------------------------------------------------------------
# Build employment index
# ---------------------------------------------------------------------------
print("Building employment index...")

emp = emp.copy()
emp["person_nbr"] = emp["OKEY"].astype(str).str.lower().str.strip()
emp["agency_name"] = emp["AGENCY"].astype(str).str.strip()
emp["rank"] = emp["RANK"].astype(str).str.strip()
emp["employment_status"] = emp["STATUS"].astype(str).str.strip()
emp["start_date"] = clean_date_series(emp["START DATE"])
emp["end_date"] = clean_date_series(emp["END DATE"])

# Drop rows where start_date is truly empty (null → '') but keep 0000-00-00
before = len(emp)
emp = emp[emp["start_date"] != ""].copy()
print(f"  Dropped {before - len(emp):,} rows with empty start_date")

# Merge demographics
emp_merged = emp.merge(od[OD_COLS], on="person_nbr", how="left")

# Drop exact duplicates on (person_nbr, agency_name, start_date)
before = len(emp_merged)
emp_merged = emp_merged.drop_duplicates(
    subset=["person_nbr", "agency_name", "start_date"]
)
print(f"  Dropped {before - len(emp_merged):,} duplicate rows")

EMP_OUT_COLS = [
    "person_nbr",
    "full_name",
    "agency_name",
    "rank",
    "employment_status",
    "start_date",
    "end_date",
    "last_name",
    "first_name",
    "middle_name",
    "suffix",
    "year_of_birth",
    "race",
    "sex",
]
emp_out = emp_merged[EMP_OUT_COLS].copy()
print(f"  Employment index rows: {len(emp_out):,}")

# ---------------------------------------------------------------------------
# Build discipline index
# ---------------------------------------------------------------------------
print("Building discipline index...")


# Clean case IDs — strip internal spaces, keep as zero-padded string (matches groundtruth)
def clean_case_series(series):
    # Remove internal spaces, then zero-pad to 10 digits
    cleaned = series.str.replace(" ", "", regex=False).str.strip()
    # Convert to numeric and back to get consistent zero-padded 10-digit string
    numeric = pd.to_numeric(cleaned, errors="coerce")
    # Format as 10-digit zero-padded string; invalid → empty string
    return numeric.apply(lambda x: "" if pd.isna(x) else str(int(x)).zfill(10))


viol = viol.copy()
sanc = sanc.copy()

viol["case_id"] = clean_case_series(viol["CASE"])
sanc["case_id"] = clean_case_series(sanc["CASE"])

viol["person_nbr"] = viol["OKEY"].astype(str).str.lower().str.strip()
sanc["person_nbr"] = sanc["OKEY"].astype(str).str.lower().str.strip()

viol["violation"] = viol["VIOLATION"].str.strip()
viol["violation_date_raw"] = viol["VIOLATION DATE"].astype(str).str.strip()
sanc["sanction"] = sanc["SANCTION"].str.strip()
sanc["sanction_date_raw"] = sanc["DATE"].astype(str).str.strip()

# Deduplicate before joining
viol_d = viol.drop_duplicates(subset=["case_id", "person_nbr", "violation"])
sanc_d = sanc.drop_duplicates(subset=["case_id", "person_nbr", "sanction"])

# Inner join violations × sanctions on case_id + person_nbr
disc = viol_d.merge(
    sanc_d[["case_id", "person_nbr", "sanction", "sanction_date_raw"]],
    on=["case_id", "person_nbr"],
    how="inner",
)
print(f"  After violations × sanctions join: {len(disc):,}")

# Clean and title-case text + dates
disc["violation"] = disc["violation"].str.title()
disc["sanction"] = disc["sanction"].str.title()
disc["violation_date"] = clean_date_series(disc["violation_date_raw"])
disc["sanction_date"] = clean_date_series(disc["sanction_date_raw"])

# 0000-00-00 in violation/sanction dates → empty string
disc["violation_date"] = disc["violation_date"].replace("0000-00-00", "")
disc["sanction_date"] = disc["sanction_date"].replace("0000-00-00", "")

# ---------------------------------------------------------------------------
# Attach employment context — vectorized scoring
# ---------------------------------------------------------------------------

# Prepare employment for discipline join (only rows with real start_date)
emp_disc = emp[
    ["person_nbr", "agency_name", "rank", "start_date", "end_date"]
].copy()
emp_disc = emp_disc[emp_disc["start_date"] != ""].copy()
# Parse start/end for scoring
emp_disc["_sd"] = pd.to_datetime(emp_disc["start_date"], errors="coerce")
emp_disc["_ed"] = pd.to_datetime(
    emp_disc["end_date"].replace("0000-00-00", pd.NaT), errors="coerce"
)

disc["_vd"] = pd.to_datetime(
    disc["violation_date"].replace({"": None}), errors="coerce"
)

# Left join disc → all employment periods for that person
disc_emp = disc.merge(emp_disc, on="person_nbr", how="left")
print(f"  After employment join: {len(disc_emp):,}")

# Vectorized score: days off from the best employment period
vd_ns = disc_emp["_vd"].values.view("int64")
sd_ns = disc_emp["_sd"].values.view("int64")
ed_ns = disc_emp["_ed"].values.view("int64")

NAT = np.iinfo(np.int64).min  # pandas NaT as int64
NS_PER_DAY = 86_400_000_000_000

no_data = (vd_ns == NAT) | (sd_ns == NAT)
ongoing_good = (ed_ns == NAT) & (vd_ns >= sd_ns)
bounded_good = (ed_ns != NAT) & (vd_ns >= sd_ns) & (vd_ns <= ed_ns)
before_start = (vd_ns < sd_ns) & (sd_ns != NAT)
after_end = (vd_ns > ed_ns) & (ed_ns != NAT)

score = np.where(
    no_data,
    9_999 * NS_PER_DAY,
    np.where(
        ongoing_good | bounded_good,
        0,
        np.where(
            before_start,
            sd_ns - vd_ns,
            np.where(after_end, vd_ns - ed_ns, 9_999 * NS_PER_DAY),
        ),
    ),
)

disc_emp["_score"] = score

# Keep best-scoring employment period for each (case_id, person_nbr, violation, sanction)
disc_best = disc_emp.sort_values("_score").drop_duplicates(
    subset=["case_id", "person_nbr", "violation", "sanction"], keep="first"
)
print(f"  After best employment selection: {len(disc_best):,}")

# Drop rows with no employment context
disc_best = disc_best[
    disc_best["start_date"].notna() & (disc_best["start_date"] != "")
].copy()
print(f"  After dropping no-employment rows: {len(disc_best):,}")

# Merge demographics
disc_best = disc_best.merge(od[OD_COLS], on="person_nbr", how="left")

# Lowercase agency_name (matches groundtruth for discipline index)
disc_best["agency_name"] = disc_best["agency_name"].str.lower()

DISC_OUT_COLS = [
    "case_id",
    "person_nbr",
    "sanction",
    "sanction_date",
    "violation",
    "violation_date",
    "full_name",
    "agency_name",
    "rank",
    "start_date",
    "end_date",
    "last_name",
    "first_name",
    "middle_name",
    "suffix",
    "year_of_birth",
    "race",
    "sex",
]
disc_out = disc_best[DISC_OUT_COLS].copy()
print(f"  Discipline index rows: {len(disc_out):,}")

# ---------------------------------------------------------------------------
# Quick validation
# ---------------------------------------------------------------------------
print("Validating output...")

for col in [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]:
    assert col in emp_out.columns, (
        f"Missing required column in employment index: {col}"
    )
    assert col in disc_out.columns, (
        f"Missing required column in discipline index: {col}"
    )

assert (emp_out["person_nbr"].str.lower() == emp_out["person_nbr"]).all(), (
    "person_nbr has uppercase values"
)
assert (
    not emp_out["person_nbr"]
    .str.contains(r"^\s|\s$", regex=True, na=False)
    .any()
), "person_nbr has leading/trailing whitespace"

empty_starts = (emp_out["start_date"] == "").sum()
if empty_starts > 0:
    print(
        f"  WARNING: {empty_starts} rows with empty start_date in employment index"
    )
print("  Validation passed.")

# ---------------------------------------------------------------------------
# Write output
# ---------------------------------------------------------------------------
print("Writing output files...")

emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

emp_out.to_csv(emp_path, index=False)
disc_out.to_csv(disc_path, index=False)

print(f"  Wrote {len(emp_out):,} rows  → {emp_path}")
print(f"  Wrote {len(disc_out):,} rows  → {disc_path}")
print("Done.")
