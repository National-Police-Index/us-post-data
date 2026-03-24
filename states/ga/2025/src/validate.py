"""
Georgia 2025 — Validation / Judge Script
Writes:
  output/judge_report.md   (human-readable)
  output/judge_report.json ({"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false})
"""

import json
import os
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

checks = []  # list of (name, status, message)


def record(name, status, message):
    """status: PASS | WARN | FAIL"""
    checks.append((name, status, message))
    print(f"[{status}] {name}: {message}")


def load_output(fname):
    path = os.path.join(OUTPUT_DIR, fname)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def load_groundtruth(fname):
    path = os.path.join(GROUNDTRUTH_DIR, fname)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------
# Load outputs
# ---------------------------------------------------------------------------

emp = load_output("ga_index.csv")
disc = load_output("ga-discipline_index.csv")

if emp is None:
    record("output_files", "FAIL", "ga_index.csv not found in output/")
    has_groundtruth = False
else:
    record("output_files", "PASS", "ga_index.csv found")

if disc is None:
    record("discipline_output_files", "WARN", "ga-discipline_index.csv not found in output/")
else:
    record("discipline_output_files", "PASS", "ga-discipline_index.csv found")

# ---------------------------------------------------------------------------
# Ground truth presence check
# ---------------------------------------------------------------------------

gt_emp = load_groundtruth("georgia_index.csv")
gt_disc = load_groundtruth("georgia-discipline_index.csv")
has_groundtruth = gt_emp is not None

if has_groundtruth:
    record("groundtruth_present", "PASS", "Ground truth files found")
else:
    record("groundtruth_present", "WARN", "No ground truth files found — schema checks only")

# ---------------------------------------------------------------------------
# Schema checks — Employment Index
# ---------------------------------------------------------------------------

REQUIRED_EMP_COLS = [
    "person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"
]

if emp is not None:
    missing_cols = [c for c in REQUIRED_EMP_COLS if c not in emp.columns]
    if missing_cols:
        record("emp_required_columns", "FAIL", f"Missing columns: {missing_cols}")
    else:
        record("emp_required_columns", "PASS", f"All required columns present: {REQUIRED_EMP_COLS}")

    # person_nbr format
    bad_nbr = emp[~emp["person_nbr"].str.match(r"^[a-z]", na=False)]
    if len(bad_nbr) > 0:
        record("emp_person_nbr_format", "FAIL",
               f"{len(bad_nbr)} person_nbr values don't start with lowercase letter")
    else:
        record("emp_person_nbr_format", "PASS", "All person_nbr start with lowercase letter")

    # No whitespace in person_nbr
    ws = emp[emp["person_nbr"].str.strip() != emp["person_nbr"]]
    if len(ws) > 0:
        record("emp_person_nbr_whitespace", "FAIL",
               f"{len(ws)} person_nbr values have leading/trailing whitespace")
    else:
        record("emp_person_nbr_whitespace", "PASS", "No whitespace in person_nbr")

    # start_date not empty
    empty_start = (emp["start_date"] == "").sum()
    if empty_start > 0:
        record("emp_start_date_not_empty", "FAIL",
               f"{empty_start} rows have empty start_date")
    else:
        record("emp_start_date_not_empty", "PASS", "No empty start_date values")

    # Date format YYYY-MM-DD or 0000-00-00 or empty
    valid_date_pat = r"^\d{4}-\d{2}-\d{2}$"
    for col in ["start_date", "end_date"]:
        non_empty = emp[emp[col] != ""][col]
        bad_dates = non_empty[~non_empty.str.match(valid_date_pat)]
        if len(bad_dates) > 0:
            record(f"emp_{col}_format", "FAIL",
                   f"{len(bad_dates)} values in {col} don't match YYYY-MM-DD")
        else:
            record(f"emp_{col}_format", "PASS", f"{col} format OK")

    # No fully duplicate rows
    dupes = emp.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
    if dupes > 0:
        record("emp_no_duplicates", "WARN",
               f"{dupes} duplicate (person_nbr, agency_name, start_date) rows")
    else:
        record("emp_no_duplicates", "PASS", "No duplicate rows")

    # Row count
    record("emp_row_count", "PASS", f"Employment index has {len(emp):,} rows")

# ---------------------------------------------------------------------------
# Schema checks — Discipline Index
# ---------------------------------------------------------------------------

REQUIRED_DISC_COLS = [
    "person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date",
    "case_id", "violation", "violation_date", "sanction", "sanction_date"
]

if disc is not None:
    missing_disc = [c for c in REQUIRED_DISC_COLS if c not in disc.columns]
    if missing_disc:
        record("disc_required_columns", "FAIL", f"Missing discipline columns: {missing_disc}")
    else:
        record("disc_required_columns", "PASS", f"All required discipline columns present")

    empty_disc_start = (disc["start_date"] == "").sum()
    if empty_disc_start > 0:
        record("disc_start_date_not_empty", "FAIL",
               f"{empty_disc_start} discipline rows have empty start_date")
    else:
        record("disc_start_date_not_empty", "PASS", "No empty start_date in discipline index")

    record("disc_row_count", "PASS", f"Discipline index has {len(disc):,} rows")

# ---------------------------------------------------------------------------
# Ground truth comparison — Employment Index
# ---------------------------------------------------------------------------

if emp is not None and gt_emp is not None:
    # Row count comparison
    gt_count = len(gt_emp)
    out_count = len(emp)
    diff_pct = abs(out_count - gt_count) / gt_count * 100 if gt_count > 0 else 0

    if diff_pct <= 1.0:
        record("emp_row_count_vs_gt", "PASS",
               f"Row count: output={out_count:,}, groundtruth={gt_count:,} ({diff_pct:.1f}% diff)")
    elif diff_pct <= 5.0:
        record("emp_row_count_vs_gt", "WARN",
               f"Row count diff {diff_pct:.1f}%: output={out_count:,}, groundtruth={gt_count:,}")
    else:
        record("emp_row_count_vs_gt", "WARN",
               f"Row count diff {diff_pct:.1f}% (>5%): output={out_count:,}, groundtruth={gt_count:,}")

    # Spot-check: first 5 rows of groundtruth should appear in output
    gt_sample = gt_emp.head(10)[["person_nbr", "agency_name", "start_date"]].copy()
    out_check = emp[["person_nbr", "agency_name", "start_date"]].copy()

    matched = 0
    for _, row in gt_sample.iterrows():
        hit = out_check[
            (out_check["person_nbr"] == row["person_nbr"]) &
            (out_check["agency_name"] == row["agency_name"]) &
            (out_check["start_date"] == row["start_date"])
        ]
        if len(hit) > 0:
            matched += 1

    if matched >= 8:
        record("emp_spot_check", "PASS", f"Spot-check: {matched}/10 groundtruth rows found in output")
    elif matched >= 5:
        record("emp_spot_check", "WARN", f"Spot-check: only {matched}/10 groundtruth rows matched")
    else:
        record("emp_spot_check", "FAIL", f"Spot-check: only {matched}/10 groundtruth rows matched")

    # Verify agency_name format (should have code prefix like "G1720 ...")
    code_prefix_pct = emp["agency_name"].str.match(r"^[A-Z]\d+\s").mean()
    record("emp_agency_name_format", "PASS" if code_prefix_pct > 0.90 else "WARN",
           f"{code_prefix_pct:.1%} of agency_names have code prefix (e.g. G1720 DEKALB...)")

    # Check names are lowercase
    ln_lower_pct = emp["last_name"][emp["last_name"] != ""].str.match(r"^[a-z]").mean()
    record("emp_names_lowercase", "PASS" if ln_lower_pct > 0.90 else "WARN",
           f"{ln_lower_pct:.1%} of last_names start with lowercase letter")

# ---------------------------------------------------------------------------
# Ground truth comparison — Discipline Index
# ---------------------------------------------------------------------------

if disc is not None and gt_disc is not None:
    gt_disc_count = len(gt_disc)
    out_disc_count = len(disc)
    diff_pct_d = abs(out_disc_count - gt_disc_count) / gt_disc_count * 100 if gt_disc_count > 0 else 0

    if diff_pct_d <= 1.0:
        record("disc_row_count_vs_gt", "PASS",
               f"Discipline row count: output={out_disc_count:,}, gt={gt_disc_count:,} ({diff_pct_d:.1f}%)")
    elif diff_pct_d <= 10.0:
        record("disc_row_count_vs_gt", "WARN",
               f"Discipline row count diff {diff_pct_d:.1f}%: output={out_disc_count:,}, gt={gt_disc_count:,}")
    else:
        record("disc_row_count_vs_gt", "WARN",
               f"Discipline row count diff {diff_pct_d:.1f}% (>10%): output={out_disc_count:,}, gt={gt_disc_count:,}")

    # Spot-check discipline records
    gt_disc_sample = gt_disc.head(10)[["person_nbr", "case_id", "violation"]].copy()
    out_disc_check = disc[["person_nbr", "case_id", "violation"]].copy()

    # Normalize case_id (gt has int-like strings, output may differ)
    def norm_case(s):
        return str(s).strip().lstrip('0')

    gt_disc_sample["case_id_n"] = gt_disc_sample["case_id"].apply(norm_case)
    out_disc_check["case_id_n"] = out_disc_check["case_id"].apply(norm_case)

    disc_matched = 0
    for _, row in gt_disc_sample.iterrows():
        hit = out_disc_check[
            (out_disc_check["person_nbr"] == row["person_nbr"]) &
            (out_disc_check["case_id_n"] == row["case_id_n"])
        ]
        if len(hit) > 0:
            disc_matched += 1

    if disc_matched >= 8:
        record("disc_spot_check", "PASS", f"Discipline spot-check: {disc_matched}/10 found")
    elif disc_matched >= 5:
        record("disc_spot_check", "WARN", f"Discipline spot-check: {disc_matched}/10 found")
    else:
        record("disc_spot_check", "FAIL", f"Discipline spot-check: only {disc_matched}/10 found")

# ---------------------------------------------------------------------------
# Determine overall result
# ---------------------------------------------------------------------------

statuses = [s for (_, s, _) in checks]
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
    "# Georgia 2025 — Validation Report\n",
    f"**Overall: {overall}**\n",
    f"**Has groundtruth: {has_groundtruth}**\n",
    "",
    "| Check | Status | Message |",
    "|-------|--------|---------|",
]
for name, status, message in checks:
    md_lines.append(f"| {name} | {status} | {message} |")

md_lines += [
    "",
    "## Summary",
    f"- Total checks: {len(checks)}",
    f"- PASS: {statuses.count('PASS')}",
    f"- WARN: {statuses.count('WARN')}",
    f"- FAIL: {statuses.count('FAIL')}",
]

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines) + "\n")

# JSON report
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\n=== Overall: {overall} ===")
print(f"Wrote output/judge_report.md and output/judge_report.json")

if overall == "FAIL":
    sys.exit(1)
