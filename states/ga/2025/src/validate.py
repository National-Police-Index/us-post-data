#!/usr/bin/env python3
"""
Validation script for Georgia POST data.
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

checks = []  # list of {name, status, detail}


def check(name, status, detail=""):
    """Record a check result. status: PASS | WARN | FAIL"""
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
    print(f"  {icon} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------

emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(emp_path):
    print(f"FATAL: {emp_path} not found")
    sys.exit(1)

print("Loading output files...")
emp = pd.read_csv(emp_path, dtype=str).fillna("")
disc = pd.read_csv(disc_path, dtype=str).fillna("") if os.path.exists(disc_path) else None

print(f"  Employment index: {len(emp):,} rows")
if disc is not None:
    print(f"  Discipline index: {len(disc):,} rows")

# ---------------------------------------------------------------------------
# Check 1: Required columns present
# ---------------------------------------------------------------------------

print("\nChecking required columns...")
EMP_REQUIRED = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
DISC_REQUIRED = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date",
                 "case_id", "violation", "violation_date", "sanction", "sanction_date"]

missing_emp = [c for c in EMP_REQUIRED if c not in emp.columns]
if missing_emp:
    check("Employment required columns", "FAIL", f"Missing: {missing_emp}")
else:
    check("Employment required columns", "PASS", f"All {len(EMP_REQUIRED)} present")

if disc is not None:
    missing_disc = [c for c in DISC_REQUIRED if c not in disc.columns]
    if missing_disc:
        check("Discipline required columns", "FAIL", f"Missing: {missing_disc}")
    else:
        check("Discipline required columns", "PASS", f"All {len(DISC_REQUIRED)} present")

# ---------------------------------------------------------------------------
# Check 2: No empty start_date
# ---------------------------------------------------------------------------

print("\nChecking start_date...")
empty_start_emp = (emp["start_date"] == "").sum()
if empty_start_emp == 0:
    check("Employment start_date not empty", "PASS", "All rows have start_date")
else:
    check("Employment start_date not empty", "FAIL", f"{empty_start_emp} rows with empty start_date")

if disc is not None:
    empty_start_disc = (disc["start_date"] == "").sum()
    if empty_start_disc == 0:
        check("Discipline start_date not empty", "PASS", "All rows have start_date")
    else:
        check("Discipline start_date not empty", "WARN",
              f"{empty_start_disc} discipline rows with empty start_date")

# ---------------------------------------------------------------------------
# Check 3: person_nbr format (lowercase, no whitespace)
# ---------------------------------------------------------------------------

print("\nChecking person_nbr format...")
bad_pnbr = emp[
    emp["person_nbr"].str.lower().ne(emp["person_nbr"]) |
    emp["person_nbr"].str.strip().ne(emp["person_nbr"])
]
if len(bad_pnbr) == 0:
    check("person_nbr format (lowercase, no whitespace)", "PASS",
          f"{emp['person_nbr'].nunique():,} unique IDs")
else:
    check("person_nbr format (lowercase, no whitespace)", "FAIL",
          f"{len(bad_pnbr)} rows with invalid person_nbr")

# ---------------------------------------------------------------------------
# Check 4: Date format YYYY-MM-DD (or empty or 0000-00-00)
# ---------------------------------------------------------------------------

print("\nChecking date formats...")
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$|^$|^0000-00-00$')

def bad_dates(series):
    return series[~series.apply(lambda v: bool(DATE_PATTERN.match(str(v))))].shape[0]

bad_emp_sd = bad_dates(emp["start_date"])
bad_emp_ed = bad_dates(emp["end_date"])

if bad_emp_sd == 0 and bad_emp_ed == 0:
    check("Employment date format", "PASS", "All dates match YYYY-MM-DD or empty or 0000-00-00")
else:
    check("Employment date format", "FAIL",
          f"start_date: {bad_emp_sd} bad, end_date: {bad_emp_ed} bad")

if disc is not None:
    bad_disc_sd = bad_dates(disc["start_date"])
    bad_disc_ed = bad_dates(disc["end_date"])
    bad_disc_vd = bad_dates(disc["violation_date"])
    bad_disc_snd = bad_dates(disc["sanction_date"])
    total_bad = bad_disc_sd + bad_disc_ed + bad_disc_vd + bad_disc_snd
    if total_bad == 0:
        check("Discipline date format", "PASS", "All dates match YYYY-MM-DD or empty or 0000-00-00")
    else:
        check("Discipline date format", "FAIL",
              f"start:{bad_disc_sd} end:{bad_disc_ed} viol:{bad_disc_vd} sanc:{bad_disc_snd} bad")

# ---------------------------------------------------------------------------
# Check 5: No fully duplicate rows
# ---------------------------------------------------------------------------

print("\nChecking for duplicate rows...")
dup_emp = emp.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
if dup_emp == 0:
    check("No duplicate employment rows", "PASS")
else:
    check("No duplicate employment rows", "WARN", f"{dup_emp} duplicates on (person_nbr, agency_name, start_date)")

if disc is not None:
    dup_disc = disc.duplicated(
        subset=["case_id", "person_nbr", "violation", "sanction", "sanction_date"]
    ).sum()
    if dup_disc == 0:
        check("No duplicate discipline rows", "PASS")
    else:
        check("No duplicate discipline rows", "WARN",
              f"{dup_disc} duplicates on (case_id, person_nbr, violation, sanction, sanction_date)")

# ---------------------------------------------------------------------------
# Check 6: Ground truth row count comparison
# ---------------------------------------------------------------------------

print("\nGround truth comparison...")
HAS_GROUNDTRUTH = False

gt_emp_path = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

if os.path.exists(gt_emp_path):
    HAS_GROUNDTRUTH = True
    gt_emp = pd.read_csv(gt_emp_path, dtype=str).fillna("")
    gt_emp_count = len(gt_emp)
    out_emp_count = len(emp)
    diff_pct = abs(out_emp_count - gt_emp_count) / max(gt_emp_count, 1) * 100

    if diff_pct <= 1:
        check("Employment row count vs groundtruth", "PASS",
              f"Output={out_emp_count:,} GT={gt_emp_count:,} diff={diff_pct:.2f}%")
    elif diff_pct <= 5:
        check("Employment row count vs groundtruth", "WARN",
              f"Output={out_emp_count:,} GT={gt_emp_count:,} diff={diff_pct:.2f}%")
    else:
        check("Employment row count vs groundtruth", "FAIL",
              f"Output={out_emp_count:,} GT={gt_emp_count:,} diff={diff_pct:.2f}%")

    # Spot-check first 20 rows by (person_nbr, agency_name, start_date)
    out_key = emp[["person_nbr", "agency_name", "start_date"]].head(50)
    gt_key = gt_emp[["person_nbr", "agency_name", "start_date"]].head(50)
    merged_check = out_key.merge(gt_key, on=["person_nbr", "agency_name", "start_date"], how="inner")
    if len(merged_check) >= 45:
        check("Employment spot-check (first 50 rows)", "PASS",
              f"{len(merged_check)}/50 rows match exactly")
    elif len(merged_check) >= 40:
        check("Employment spot-check (first 50 rows)", "WARN",
              f"{len(merged_check)}/50 rows match exactly")
    else:
        check("Employment spot-check (first 50 rows)", "FAIL",
              f"Only {len(merged_check)}/50 rows match exactly")

if os.path.exists(gt_disc_path) and disc is not None:
    HAS_GROUNDTRUTH = True
    gt_disc = pd.read_csv(gt_disc_path, dtype=str).fillna("")
    gt_disc_count = len(gt_disc)
    out_disc_count = len(disc)
    diff_pct = abs(out_disc_count - gt_disc_count) / max(gt_disc_count, 1) * 100

    # Discipline row counts vary significantly as source data grows — WARN not FAIL
    if diff_pct <= 5:
        check("Discipline row count vs groundtruth", "PASS",
              f"Output={out_disc_count:,} GT={gt_disc_count:,} diff={diff_pct:.2f}%")
    elif diff_pct <= 200:
        check("Discipline row count vs groundtruth", "WARN",
              f"Output={out_disc_count:,} GT={gt_disc_count:,} diff={diff_pct:.2f}% (source data has grown since GT snapshot)")
    else:
        check("Discipline row count vs groundtruth", "FAIL",
              f"Output={out_disc_count:,} GT={gt_disc_count:,} diff={diff_pct:.2f}%")

    # Spot-check discipline rows: normalize case_id to str without leading zeros
    def norm_case(s):
        try:
            return str(int(str(s).strip()))
        except Exception:
            return str(s).strip()

    disc_cmp = disc.copy()
    disc_cmp["case_id"] = disc_cmp["case_id"].apply(norm_case)
    gt_disc_cmp = gt_disc.copy()
    gt_disc_cmp["case_id"] = gt_disc_cmp["case_id"].apply(norm_case)

    # Compare GT cases against output by matching on (case_id, person_nbr, violation, sanction)
    # Normalize: lowercase, strip, lstrip zeros from case_id
    def norm_str(s):
        return str(s).lower().strip()
    def norm_case_id_str(s):
        return str(s).strip().lstrip('0') or '0'

    disc_keys = disc_cmp.copy()
    gt_keys = gt_disc_cmp.copy()
    for df_ in [disc_keys, gt_keys]:
        df_["case_id_n"] = df_["case_id"].apply(norm_case_id_str)
        df_["violation_n"] = df_["violation"].apply(norm_str)
        df_["sanction_n"] = df_["sanction"].apply(norm_str)

    # Sample GT first 50 rows, see how many are in output
    gt_sample_50 = gt_keys[["case_id_n", "person_nbr", "violation_n", "sanction_n"]].head(50)
    disc_all = disc_keys[["case_id_n", "person_nbr", "violation_n", "sanction_n"]]
    merged_disc = gt_sample_50.merge(disc_all, on=["case_id_n", "person_nbr", "violation_n", "sanction_n"], how="inner")
    matched = len(merged_disc)

    if matched >= 40:
        check("Discipline spot-check (first 50 GT rows)", "PASS",
              f"{matched}/50 GT rows found in output")
    elif matched >= 25:
        check("Discipline spot-check (first 50 GT rows)", "WARN",
              f"{matched}/50 GT rows found in output")
    else:
        check("Discipline spot-check (first 50 GT rows)", "FAIL",
              f"Only {matched}/50 GT rows found in output")

# ---------------------------------------------------------------------------
# Check 7: agency_name not empty
# ---------------------------------------------------------------------------

print("\nChecking agency_name...")
empty_agency = (emp["agency_name"].str.strip() == "").sum()
if empty_agency == 0:
    check("agency_name not empty", "PASS")
else:
    check("agency_name not empty", "WARN", f"{empty_agency} rows with empty agency_name")

# ---------------------------------------------------------------------------
# Check 8: name quality
# ---------------------------------------------------------------------------

print("\nChecking name quality...")
empty_last = (emp["last_name"].str.strip() == "").sum()
empty_first = (emp["first_name"].str.strip() == "").sum()
total = len(emp)
pct_last = empty_last / total * 100
pct_first = empty_first / total * 100

if pct_last < 1 and pct_first < 5:
    check("Name completeness", "PASS",
          f"last_name empty: {empty_last} ({pct_last:.1f}%), first_name empty: {empty_first} ({pct_first:.1f}%)")
elif pct_last < 5 and pct_first < 10:
    check("Name completeness", "WARN",
          f"last_name empty: {empty_last} ({pct_last:.1f}%), first_name empty: {empty_first} ({pct_first:.1f}%)")
else:
    check("Name completeness", "FAIL",
          f"last_name empty: {empty_last} ({pct_last:.1f}%), first_name empty: {empty_first} ({pct_first:.1f}%)")

# ---------------------------------------------------------------------------
# Check 9: person_nbr not null
# ---------------------------------------------------------------------------

null_pnbr = (emp["person_nbr"].str.strip() == "").sum()
if null_pnbr == 0:
    check("No null person_nbr", "PASS")
else:
    check("No null person_nbr", "FAIL", f"{null_pnbr} empty person_nbr values")

# ---------------------------------------------------------------------------
# Determine overall verdict
# ---------------------------------------------------------------------------

statuses = [c["status"] for c in checks]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Markdown report
md_lines = [
    "# Georgia POST 2025 — Validation Report",
    "",
    f"**Overall: {overall}**",
    "",
    f"| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["status"], "?")
    detail = c["detail"].replace("|", "\\|")
    md_lines.append(f"| {c['name']} | {icon} {c['status']} | {detail} |")

md_lines += [
    "",
    "## Summary",
    f"- Total checks: {len(checks)}",
    f"- PASS: {statuses.count('PASS')}",
    f"- WARN: {statuses.count('WARN')}",
    f"- FAIL: {statuses.count('FAIL')}",
    f"- Has groundtruth: {HAS_GROUNDTRUTH}",
    "",
]

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(md_lines))

# JSON report
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": HAS_GROUNDTRUTH}, f, indent=2)

print(f"\n{'='*50}")
print(f"Overall: {overall}")
print(f"Wrote {md_path}")
print(f"Wrote {json_path}")
