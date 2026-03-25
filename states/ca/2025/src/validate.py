"""
Validation script for California employment index.

Compares output/ca_index.csv against:
  - data/groundtruth/ca-index.csv  (when present)
  - Schema / format checks (always)

Writes:
  - output/judge_report.md   (human-readable)
  - output/judge_report.json ({"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false})
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ca_index.csv")
GT_FILE = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")

REQUIRED_COLS = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

checks = []   # list of {name, status, detail}


def check(name, status, detail=""):
    """Record a check result. status: PASS | WARN | FAIL"""
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
    print(f"  {icon} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
print("Loading output file...")
if not os.path.exists(OUTPUT_FILE):
    check("Output file exists", "FAIL", f"{OUTPUT_FILE} not found")
    # Write immediate fail
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": "FAIL", "has_groundtruth": False}, f)
    with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
        f.write("# CA 2025 Validation Report\n\n## FAIL\n\nOutput file not found.\n")
    sys.exit(1)

df = pd.read_csv(OUTPUT_FILE, dtype=str)
print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

# ---------------------------------------------------------------------------
# Check 1: Required columns present
# ---------------------------------------------------------------------------
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    check("Required columns", "FAIL", f"Missing: {missing_cols}")
else:
    check("Required columns", "PASS", f"All present: {REQUIRED_COLS}")

# ---------------------------------------------------------------------------
# Check 2: No empty start_date
# ---------------------------------------------------------------------------
empty_start = (df["start_date"].isna() | (df["start_date"] == "")).sum()
if empty_start == 0:
    check("No empty start_date", "PASS", "All start_date values present")
else:
    check("No empty start_date", "FAIL", f"{empty_start:,} rows have empty start_date")

# ---------------------------------------------------------------------------
# Check 3: Date format YYYY-MM-DD
# ---------------------------------------------------------------------------
bad_start = df["start_date"].dropna()
bad_start = bad_start[bad_start != ""]
bad_start_fmt = (~bad_start.str.match(r"^\d{4}-\d{2}-\d{2}$")).sum()

bad_end = df["end_date"].dropna()
bad_end = bad_end[bad_end != ""]
bad_end_fmt = (~bad_end.str.match(r"^\d{4}-\d{2}-\d{2}$")).sum()

if bad_start_fmt == 0 and bad_end_fmt == 0:
    check("Date format YYYY-MM-DD", "PASS", "All non-empty dates are properly formatted")
else:
    check("Date format YYYY-MM-DD", "FAIL",
          f"{bad_start_fmt} bad start_date, {bad_end_fmt} bad end_date")

# ---------------------------------------------------------------------------
# Check 4: person_nbr format (lowercase string, no whitespace)
# ---------------------------------------------------------------------------
# LEO person_nbr format: e.g. "A52-V94" (uppercase from source, kept as-is)
# Corrections: numeric string e.g. "230001"
pnbr = df["person_nbr"].dropna()
has_leading_trailing_ws = (pnbr != pnbr.str.strip()).sum()
is_null_str = (pnbr == "nan").sum()

if has_leading_trailing_ws == 0 and is_null_str == 0:
    check("person_nbr format", "PASS", "No leading/trailing whitespace, no 'nan' strings")
else:
    issues = []
    if has_leading_trailing_ws:
        issues.append(f"{has_leading_trailing_ws} with whitespace")
    if is_null_str:
        issues.append(f"{is_null_str} 'nan' strings")
    check("person_nbr format", "FAIL", "; ".join(issues))

# ---------------------------------------------------------------------------
# Check 5: No fully duplicate rows (person_nbr + agency_name + start_date)
# ---------------------------------------------------------------------------
dupes = df.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
if dupes == 0:
    check("No duplicate rows", "PASS", "No (person_nbr, agency_name, start_date) duplicates")
elif dupes <= 100:
    check("No duplicate rows", "WARN", f"{dupes} duplicate rows found (minor)")
else:
    check("No duplicate rows", "FAIL", f"{dupes} duplicate rows found")

# ---------------------------------------------------------------------------
# Check 6: agency_name not empty
# ---------------------------------------------------------------------------
empty_agency = (df["agency_name"].isna() | (df["agency_name"] == "")).sum()
if empty_agency == 0:
    check("agency_name not empty", "PASS", "All agency_name values present")
elif empty_agency / len(df) < 0.01:
    check("agency_name not empty", "WARN", f"{empty_agency} empty agency_name (<1%)")
else:
    check("agency_name not empty", "FAIL", f"{empty_agency:,} empty agency_name ({empty_agency/len(df):.1%})")

# ---------------------------------------------------------------------------
# Check 7: first_name / last_name not mostly empty
# ---------------------------------------------------------------------------
empty_first = (df["first_name"].isna() | (df["first_name"] == "")).sum()
empty_last = (df["last_name"].isna() | (df["last_name"] == "")).sum()
name_rate_first = empty_first / len(df)
name_rate_last = empty_last / len(df)

if name_rate_first < 0.01 and name_rate_last < 0.01:
    check("Name fields populated", "PASS",
          f"first_name empty: {empty_first} ({name_rate_first:.1%}), "
          f"last_name empty: {empty_last} ({name_rate_last:.1%})")
elif name_rate_first < 0.05 and name_rate_last < 0.05:
    check("Name fields populated", "WARN",
          f"first_name empty: {empty_first} ({name_rate_first:.1%}), "
          f"last_name empty: {empty_last} ({name_rate_last:.1%})")
else:
    check("Name fields populated", "FAIL",
          f"first_name empty: {empty_first} ({name_rate_first:.1%}), "
          f"last_name empty: {empty_last} ({name_rate_last:.1%})")

# ---------------------------------------------------------------------------
# Check 8: Two data types present (POLICE and CORRECTIONS)
# ---------------------------------------------------------------------------
if "type" in df.columns:
    type_counts = df["type"].value_counts()
    has_police = "POLICE" in type_counts.index
    has_corrections = "CORRECTIONS" in type_counts.index
    if has_police and has_corrections:
        check("Both POLICE and CORRECTIONS present", "PASS",
              f"POLICE: {type_counts.get('POLICE', 0):,}, "
              f"CORRECTIONS: {type_counts.get('CORRECTIONS', 0):,}")
    else:
        missing = []
        if not has_police:
            missing.append("POLICE")
        if not has_corrections:
            missing.append("CORRECTIONS")
        check("Both POLICE and CORRECTIONS present", "WARN",
              f"Missing: {missing}")
else:
    check("Both POLICE and CORRECTIONS present", "WARN", "'type' column not present")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.exists(GT_FILE)

if has_groundtruth:
    print("\nLoading groundtruth for comparison...")
    gt = pd.read_csv(GT_FILE, dtype=str)
    print(f"  Groundtruth rows: {len(gt):,}")

    # Check 9: Row count comparison
    output_rows = len(df)
    gt_rows = len(gt)
    row_diff_pct = abs(output_rows - gt_rows) / gt_rows * 100

    if row_diff_pct <= 2:
        check("Row count vs groundtruth", "PASS",
              f"Output: {output_rows:,}, GT: {gt_rows:,}, diff: {row_diff_pct:.1f}%")
    elif row_diff_pct <= 10:
        check("Row count vs groundtruth", "WARN",
              f"Output: {output_rows:,}, GT: {gt_rows:,}, diff: {row_diff_pct:.1f}% (>2%)")
    else:
        check("Row count vs groundtruth", "FAIL",
              f"Output: {output_rows:,}, GT: {gt_rows:,}, diff: {row_diff_pct:.1f}% (>10%)")

    # Check 10: Spot-check known rows from groundtruth against output
    # Sample: first person A52-V94 should have matching records
    test_pid = "A52-V94"
    out_person = df[df["person_nbr"] == test_pid].sort_values("start_date").reset_index(drop=True)
    gt_person = gt[gt["person_nbr"] == test_pid].sort_values("start_date").reset_index(drop=True)

    if len(out_person) == 0:
        check(f"Spot-check person {test_pid}", "FAIL", "Person not found in output")
    elif len(out_person) == len(gt_person):
        # Check agency names match
        agency_match = (out_person["agency_name"].values == gt_person["agency_name"].values).all()
        if agency_match:
            check(f"Spot-check person {test_pid}", "PASS",
                  f"{len(out_person)} matching rows, agencies match")
        else:
            mismatches = sum(
                out_person["agency_name"].values != gt_person["agency_name"].values
            )
            check(f"Spot-check person {test_pid}", "WARN",
                  f"{mismatches} agency name mismatches out of {len(out_person)} rows")
    else:
        check(f"Spot-check person {test_pid}", "WARN",
              f"Row count: output={len(out_person)}, gt={len(gt_person)}")

    # Check 11: Common person_nbr overlap
    out_pids = set(df["person_nbr"].unique())
    gt_pids = set(gt["person_nbr"].unique())
    overlap = len(out_pids & gt_pids)
    overlap_pct = overlap / len(gt_pids) * 100 if gt_pids else 0

    if overlap_pct >= 95:
        check("person_nbr overlap with groundtruth", "PASS",
              f"{overlap:,}/{len(gt_pids):,} ({overlap_pct:.1f}%) GT person_nbrs found in output")
    elif overlap_pct >= 85:
        check("person_nbr overlap with groundtruth", "WARN",
              f"{overlap:,}/{len(gt_pids):,} ({overlap_pct:.1f}%) GT person_nbrs found")
    else:
        check("person_nbr overlap with groundtruth", "FAIL",
              f"Only {overlap:,}/{len(gt_pids):,} ({overlap_pct:.1f}%) GT person_nbrs found")

    # Check 12: Sample value comparison for agency names (top agencies)
    # GT top-5 agency names should appear in output
    gt_top5 = gt["agency_name"].value_counts().head(5).index.tolist()
    out_agencies = set(df["agency_name"].unique())
    missing_top5 = [a for a in gt_top5 if a not in out_agencies]
    if not missing_top5:
        check("Top-5 GT agency names present", "PASS",
              f"All top-5 GT agencies found: {gt_top5}")
    else:
        check("Top-5 GT agency names present", "WARN",
              f"Missing agencies: {missing_top5}")

    # Check 13: Corrections sample
    # Corrections person 230001 should have expected agency name
    corr_test = df[df["person_nbr"] == "230001"]
    if len(corr_test) > 0:
        expected_agency = "061: PAROLE & COMMUNITY SERVICES DIVISION"
        actual_agency = corr_test["agency_name"].iloc[0]
        if actual_agency == expected_agency:
            check("Corrections agency name format", "PASS",
                  f"230001: '{actual_agency}'")
        else:
            check("Corrections agency name format", "WARN",
                  f"230001: expected '{expected_agency}', got '{actual_agency}'")
    else:
        check("Corrections agency name format", "WARN", "Person 230001 not in output")

    # Check 14: Date spot-check for A52-V94 first row
    if len(out_person) > 0 and len(gt_person) > 0:
        out_start = out_person["start_date"].iloc[0]
        gt_start = gt_person["start_date"].iloc[0]
        if out_start == gt_start:
            check("Date spot-check (A52-V94 row 1)", "PASS",
                  f"start_date={out_start}")
        else:
            check("Date spot-check (A52-V94 row 1)", "FAIL",
                  f"Output: {out_start}, GT: {gt_start}")

else:
    check("Groundtruth comparison", "WARN",
          "No groundtruth file found — skipping comparison checks")

# ---------------------------------------------------------------------------
# Determine overall status
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

# judge_report.json
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

# judge_report.md
with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("# CA 2025 Validation Report\n\n")
    f.write(f"**Overall: {overall}**\n\n")
    f.write(f"Output file: `{OUTPUT_FILE}`  \n")
    f.write(f"Rows: {len(df):,}  \n")
    f.write(f"Groundtruth available: {has_groundtruth}  \n\n")
    f.write("## Check Results\n\n")
    f.write("| # | Check | Status | Detail |\n")
    f.write("|---|-------|--------|--------|\n")
    for i, c in enumerate(checks, 1):
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["status"], "?")
        detail = c["detail"].replace("|", "\\|")
        f.write(f"| {i} | {c['name']} | {icon} {c['status']} | {detail} |\n")

    f.write("\n## Summary\n\n")
    pass_ct = statuses.count("PASS")
    warn_ct = statuses.count("WARN")
    fail_ct = statuses.count("FAIL")
    f.write(f"- ✅ PASS: {pass_ct}\n")
    f.write(f"- ⚠️ WARN: {warn_ct}\n")
    f.write(f"- ❌ FAIL: {fail_ct}\n")
    f.write(f"\n**Overall result: {overall}**\n")

print(f"\n{'='*60}")
print(f"Overall: {overall}")
print(f"{'='*60}")
print(f"Wrote output/judge_report.md and output/judge_report.json")
