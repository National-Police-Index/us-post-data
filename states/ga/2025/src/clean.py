#!/usr/bin/env python3
"""
Georgia POST data cleaning script.
Produces:
  - output/ga_index.csv            (employment index)
  - output/ga-discipline_index.csv (discipline index)
"""

import argparse
import os

import pandas as pd


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Clean GA POST data")
parser.add_argument("--input-dir", default="data/input")
parser.add_argument("--output-dir", default="output")
args = parser.parse_args()

INPUT_DIR = args.input_dir
OUTPUT_DIR = args.output_dir
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def safe_date(val):
    """Return YYYY-MM-DD string, '0000-00-00', or '' for invalid/missing dates."""
    s = str(val).strip()
    if not s or s in ("nan", "NaT", "None", "00/00/0000"):
        return ""
    if s == "0000-00-00":
        return "0000-00-00"  # Keep raw (means currently employed / missing)
    try:
        parsed = pd.to_datetime(s, errors="coerce")
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return ""


def title_case_str(val):
    """Title-case a string; handle NaN gracefully."""
    if pd.isna(val) or str(val).strip() in ("", "nan"):
        return ""
    return str(val).strip().title()


# ---------------------------------------------------------------------------
# Step 1: Load raw files
# ---------------------------------------------------------------------------
print("Loading officer_employment.csv ...")
emp = pd.read_csv(os.path.join(INPUT_DIR, "officer_employment.csv"), dtype=str)

print("Loading officer_data.csv ...")
demo = pd.read_csv(os.path.join(INPUT_DIR, "officer_data.csv"), dtype=str)

print(f"  emp rows: {len(emp):,}  demo rows: {len(demo):,}")

# ---------------------------------------------------------------------------
# Step 2: Clean employment table
# ---------------------------------------------------------------------------
emp = emp.rename(
    columns={
        "OKEY": "person_nbr",
        "NAME": "full_name_raw",
        "AGENCY": "agency_name",  # keep raw (with code prefix, uppercase)
        "RANK": "rank",
        "STATUS": "employment_status",
        "START DATE": "start_date",
        "END DATE": "end_date",
    }
)

# person_nbr: lowercase, strip
emp["person_nbr"] = emp["person_nbr"].astype(str).str.lower().str.strip()

# Drop rows with no person_nbr
emp = emp[
    emp["person_nbr"].notna()
    & (emp["person_nbr"] != "")
    & (emp["person_nbr"] != "nan")
]

# Dates — keep 0000-00-00 raw (it means currently employed in GT)
emp["start_date"] = emp["start_date"].apply(safe_date)
emp["end_date"] = emp["end_date"].apply(safe_date)

# Drop rows where start_date is truly empty (not 0000-00-00)
before = len(emp)
emp = emp[emp["start_date"] != ""]
print(f"  Dropped {before - len(emp):,} rows with empty start_date")

# Keep rank and employment_status as-is (GT has uppercase rank, title-case status)
emp["rank"] = emp["rank"].astype(str).str.strip()
emp["employment_status"] = emp["employment_status"].astype(str).str.strip()
# Replace nan strings
emp["rank"] = emp["rank"].replace("nan", "")
emp["employment_status"] = emp["employment_status"].replace("nan", "")

# ---------------------------------------------------------------------------
# Step 3: Clean demographics table
# ---------------------------------------------------------------------------
demo = demo.rename(
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

demo["person_nbr"] = demo["person_nbr"].astype(str).str.lower().str.strip()

for col in ["last_name", "first_name", "middle_name", "suffix"]:
    demo[col] = demo[col].astype(str).str.strip().str.lower()
    demo[col] = demo[col].replace("nan", "")

# year_of_birth, sex, race keep as-is
demo["year_of_birth"] = (
    demo["year_of_birth"].astype(str).str.strip().replace("nan", "")
)
demo["sex"] = demo["sex"].astype(str).str.strip().replace("nan", "")
demo["race"] = demo["race"].astype(str).str.strip().replace("nan", "")

# ---------------------------------------------------------------------------
# Step 4: Merge employment + demographics
# ---------------------------------------------------------------------------
merged = emp.merge(
    demo[
        [
            "person_nbr",
            "last_name",
            "first_name",
            "middle_name",
            "suffix",
            "year_of_birth",
            "race",
            "sex",
        ]
    ],
    on="person_nbr",
    how="left",
)
print(f"  Merged employment+demo rows: {len(merged):,}")


# Build full_name: "last_name, first_name middle_name suffix" (lowercase)
def build_full_name(row):
    last = str(row.get("last_name", "") or "").strip()
    first = str(row.get("first_name", "") or "").strip()
    middle = str(row.get("middle_name", "") or "").strip()
    suffix = str(row.get("suffix", "") or "").strip()
    for v in ["nan"]:
        last = "" if last == v else last
        first = "" if first == v else first
        middle = "" if middle == v else middle
        suffix = "" if suffix == v else suffix

    right_parts = [p for p in [first, middle, suffix] if p]
    right = " ".join(right_parts)
    if right:
        full = f"{last}, {right}"
    else:
        full = last
    return full  # already lowercase (names lowercased in demo step)


merged["full_name"] = merged.apply(build_full_name, axis=1)

# ---------------------------------------------------------------------------
# Step 5: Dedup employment index
# ---------------------------------------------------------------------------
before = len(merged)
merged = merged.drop_duplicates(
    subset=["person_nbr", "agency_name", "start_date"]
)
print(f"  Dropped {before - len(merged):,} duplicate employment rows")

# ---------------------------------------------------------------------------
# Step 6: Select & order columns for employment index
# ---------------------------------------------------------------------------
INDEX_COLS = [
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

ga_index = merged[[c for c in INDEX_COLS if c in merged.columns]].copy()

# Fill NaN strings
for col in [
    "last_name",
    "first_name",
    "middle_name",
    "suffix",
    "year_of_birth",
    "race",
    "sex",
]:
    if col in ga_index.columns:
        ga_index[col] = ga_index[col].fillna("").replace("nan", "")

print(f"  Employment index rows: {len(ga_index):,}")

# ---------------------------------------------------------------------------
# Step 7: Discipline index — load violation/sanction/investigation files
# ---------------------------------------------------------------------------
print("\nLoading discipline files ...")
viol = pd.read_csv(os.path.join(INPUT_DIR, "officer_violations.csv"), dtype=str)
sanc = pd.read_csv(os.path.join(INPUT_DIR, "officer_sanctions.csv"), dtype=str)
inv = pd.read_csv(
    os.path.join(INPUT_DIR, "officer_investigations.csv"), dtype=str
)

print(
    f"  violations: {len(viol):,}  sanctions: {len(sanc):,}  investigations: {len(inv):,}"
)

# Rename
viol = viol.rename(
    columns={
        "CASE": "case_id",
        "OKEY": "person_nbr",
        "NAME": "name_raw_v",
        "VIOLATION": "violation",
        "VIOLATION DATE": "violation_date",
    }
)
sanc = sanc.rename(
    columns={
        "CASE": "case_id",
        "OKEY": "person_nbr",
        "NAME": "name_raw_s",
        "SANCTION": "sanction",
        "DATE": "sanction_date",
    }
)
inv = inv.rename(
    columns={
        "CASE": "case_id",
        "OKEY": "person_nbr",
        "NAME": "name_raw_i",
        "AGENCY": "inv_agency",
        "DATE OPENED": "date_opened",
    }
)

# Lowercase person_nbr and strip
for df_ in [viol, sanc, inv]:
    df_["person_nbr"] = df_["person_nbr"].astype(str).str.lower().str.strip()
    df_["case_id"] = df_["case_id"].astype(str).str.strip()

# Lowercase investigation agency (GT uses lowercase agency with code prefix)
inv["inv_agency"] = inv["inv_agency"].astype(str).str.lower().str.strip()

# Clean dates
viol["violation_date"] = viol["violation_date"].apply(safe_date)
sanc["sanction_date"] = sanc["sanction_date"].apply(safe_date)

# Filter violations to those with valid (non-zero) violation_date — GT excludes 0000-00-00
viol_valid = viol[viol["violation_date"] != "0000-00-00"].copy()
print(
    f"  Violations with valid date: {len(viol_valid):,} (dropped {len(viol) - len(viol_valid):,} with 0000-00-00)"
)

# Title-case violation and sanction strings (matches GT)
viol_valid["violation"] = (
    viol_valid["violation"].astype(str).apply(title_case_str)
)
sanc["sanction"] = sanc["sanction"].astype(str).apply(title_case_str)

# ---------------------------------------------------------------------------
# Step 8: Join violations × sanctions per case (full cartesian per case)
# GT format: one row per (violation, sanction) combination per case
# Use investigation agency as the authoritative agency for discipline
# ---------------------------------------------------------------------------
disc = viol_valid.merge(
    sanc[["case_id", "person_nbr", "sanction", "sanction_date"]],
    on=["case_id", "person_nbr"],
    how="inner",
)
print(f"  After inner join violations×sanctions (valid dates): {len(disc):,}")

# Attach investigation agency (one row per case in investigations)
disc = disc.merge(
    inv[["case_id", "person_nbr", "inv_agency"]].drop_duplicates(),
    on=["case_id", "person_nbr"],
    how="left",
)
print(f"  After investigation agency join: {len(disc):,}")

# ---------------------------------------------------------------------------
# Step 9: Attach employment context to discipline
# Use investigation agency to find the specific employment period
# ---------------------------------------------------------------------------
# Build employment lookup: (person_nbr, agency_name) → (rank, start_date, end_date)
emp_ctx = emp[
    ["person_nbr", "agency_name", "rank", "start_date", "end_date"]
].copy()
emp_ctx["agency_name_lc"] = emp_ctx["agency_name"].str.lower()

# Deduplicate employment by (person, agency, start_date)
emp_dedup = emp_ctx.drop_duplicates(
    subset=["person_nbr", "agency_name_lc", "start_date"]
)

# Join discipline to employment on (person_nbr, agency from investigation)
disc_emp = disc.merge(
    emp_dedup[
        ["person_nbr", "agency_name_lc", "rank", "start_date", "end_date"]
    ].rename(columns={"agency_name_lc": "inv_agency"}),
    on=["person_nbr", "inv_agency"],
    how="left",
)
print(f"  After discipline+employment join (inv agency): {len(disc_emp):,}")


# Score each employment period match against violation_date
def score_period(row):
    """Lower score = better match. 0 = violation_date within period."""
    vdate = row["violation_date"]
    sd = row["start_date"]
    ed = row["end_date"]
    if not vdate or vdate == "0000-00-00" or not sd:
        return 9999
    try:
        vd = pd.to_datetime(vdate)
        s = (
            pd.to_datetime(sd)
            if sd != "0000-00-00"
            else pd.Timestamp("1900-01-01")
        )
        # end_date 0000-00-00 means currently employed → far future
        if not ed or ed == "0000-00-00":
            e = pd.Timestamp("2099-12-31")
        else:
            e = pd.to_datetime(ed)
        if s <= vd <= e:
            return 0
        elif vd < s:
            return (s - vd).days
        else:
            return (vd - e).days
    except Exception:
        return 9999


disc_emp["_score"] = disc_emp.apply(score_period, axis=1)
disc_emp["_min_score"] = disc_emp.groupby(
    ["case_id", "person_nbr", "violation", "sanction"]
)["_score"].transform("min")
# Keep all rows tied at the minimum score (there may be multiple employment periods)
disc_emp = disc_emp[disc_emp["_score"] == disc_emp["_min_score"]].copy()
# Then dedup to one row per (case, person, violation, sanction)
disc_emp = disc_emp.drop_duplicates(
    subset=["case_id", "person_nbr", "violation", "sanction"]
)
disc_emp = disc_emp.drop(columns=["_score", "_min_score"])
# Rename inv_agency to agency_name
disc_emp = disc_emp.rename(columns={"inv_agency": "agency_name"})
print(f"  After employment period scoring+dedup: {len(disc_emp):,}")

# ---------------------------------------------------------------------------
# Step 10: Add demographics to discipline
# ---------------------------------------------------------------------------
disc_final = disc_emp.merge(
    demo[
        [
            "person_nbr",
            "last_name",
            "first_name",
            "middle_name",
            "suffix",
            "year_of_birth",
            "race",
            "sex",
        ]
    ],
    on="person_nbr",
    how="left",
)

# Build full_name for discipline (lowercase, matching GT)
disc_final["full_name"] = disc_final.apply(build_full_name, axis=1)

# Lowercase the agency_name and rank for discipline (matches groundtruth format)
disc_final["agency_name"] = disc_final["agency_name"].astype(str).str.lower()
disc_final["rank"] = (
    disc_final["rank"].astype(str).str.lower().replace("nan", "")
)

# Drop rows with empty start_date (no valid employment match)
# Note: keep 0000-00-00 start_date rows (GT keeps those for some old records)
before = len(disc_final)
disc_final = disc_final[disc_final["start_date"].fillna("") != ""]
print(
    f"  Dropped {before - len(disc_final):,} discipline rows with no employment match"
)
print(f"  Discipline index rows: {len(disc_final):,}")

# Clean string columns
for col in [
    "last_name",
    "first_name",
    "middle_name",
    "suffix",
    "year_of_birth",
    "race",
    "sex",
]:
    if col in disc_final.columns:
        disc_final[col] = disc_final[col].fillna("").astype(str).str.strip()
        disc_final[col] = disc_final[col].replace("nan", "")

# ---------------------------------------------------------------------------
# Step 11: Select & order columns for discipline index
# ---------------------------------------------------------------------------
DISC_COLS = [
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

ga_disc = disc_final[[c for c in DISC_COLS if c in disc_final.columns]].copy()

# ---------------------------------------------------------------------------
# Step 12: Validate & write output
# ---------------------------------------------------------------------------
required_index = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]
required_disc = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]

for col in required_index:
    assert col in ga_index.columns, f"Employment index missing column: {col}"
for col in required_disc:
    assert col in ga_disc.columns, f"Discipline index missing column: {col}"

# start_date should not be truly empty
empty_start = (
    ga_index["start_date"].isna() | (ga_index["start_date"] == "")
).sum()
assert empty_start == 0, (
    f"Employment index has {empty_start} empty start_date rows!"
)

empty_disc_start = (
    ga_disc["start_date"].isna() | (ga_disc["start_date"] == "")
).sum()
assert empty_disc_start == 0, (
    f"Discipline index has {empty_disc_start} empty start_date rows!"
)

# Write employment index
idx_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
ga_index.to_csv(idx_path, index=False)
print(f"\nWrote {idx_path}  ({len(ga_index):,} rows)")

# Write discipline index
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
ga_disc.to_csv(disc_path, index=False)
print(f"Wrote {disc_path}  ({len(ga_disc):,} rows)")
print("\nDone.")
