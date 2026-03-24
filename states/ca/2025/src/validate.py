"""
Validation script for CA 2025 cleaned output.

Compares output/ca_index.csv against data/groundtruth/ca-index.csv (if present).
Writes:
  - output/judge_report.md
  - output/judge_report.json

Run from states/ca/2025/ as cwd:
  python src/validate.py
"""

import json
import os
import re

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
GT_FILE = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ca_index.csv")

REQUIRED_COLS = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

checks = []   # list of {"name": ..., "status": PASS|WARN|FAIL, "detail": ...}
overall = "PASS"


def record(name, status, detail=""):
    global overall
    checks.append({"name": name, "status": status, "detail": detail})
    if status == "FAIL" and overall != "FAIL":
        overall = "FAIL"
    elif status == "WARN" and overall == "PASS":
        overall = "WARN"
    print(f"  [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
print("Loading output file ...")
if not os.path.exists(OUTPUT_FILE):
    record("output_file_exists", "FAIL", f"{OUTPUT_FILE} not found")
    # Write reports and exit
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": "FAIL", "has_groundtruth": False}, f)
    raise SystemExit(1)

df = pd.read_csv(OUTPUT_FILE, dtype=str, low_memory=False)
record("output_file_exists", "PASS", f"{len(df)} rows loaded")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
print("Schema checks ...")
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    record("required_columns", "FAIL", f"Missing: {missing_cols}")
else:
    record("required_columns", "PASS", f"All required columns present: {REQUIRED_COLS}")

# person_nbr format
if "person_nbr" in df.columns:
    bad_case = df["person_nbr"].str.contains(r"[A-Z]", na=False).sum()
    bad_ws   = (df["person_nbr"] != df["person_nbr"].str.strip()).sum()
    if bad_case > 0:
        record("person_nbr_lowercase", "FAIL", f"{bad_case} person_nbr values have uppercase chars")
    else:
        record("person_nbr_lowercase", "PASS", "All person_nbr are lowercase")
    if bad_ws > 0:
        record("person_nbr_no_whitespace", "FAIL", f"{bad_ws} person_nbr values have leading/trailing whitespace")
    else:
        record("person_nbr_no_whitespace", "PASS", "No leading/trailing whitespace in person_nbr")

# start_date: no empty values
if "start_date" in df.columns:
    empty_start = (df["start_date"].isna() | (df["start_date"] == "")).sum()
    if empty_start > 0:
        record("start_date_no_empty", "FAIL", f"{empty_start} rows have empty start_date")
    else:
        record("start_date_no_empty", "PASS", "No empty start_date values")

    # Date format YYYY-MM-DD
    valid_dates = df["start_date"].dropna()
    bad_format = valid_dates[~valid_dates.apply(lambda x: bool(DATE_RE.match(str(x))))].shape[0]
    if bad_format > 0:
        record("start_date_format", "WARN", f"{bad_format} start_date values not in YYYY-MM-DD format")
    else:
        record("start_date_format", "PASS", "All start_date values in YYYY-MM-DD format")

if "end_date" in df.columns:
    # end_date: no invalid placeholder values
    bad_end = df["end_date"].isin(["0000-00-00", "NaT", "None", "nan"]).sum()
    if bad_end > 0:
        record("end_date_no_placeholders", "FAIL", f"{bad_end} end_date values have placeholder values")
    else:
        record("end_date_no_placeholders", "PASS", "No placeholder end_date values")

# No fully duplicate rows
if all(c in df.columns for c in ["person_nbr", "agency_name", "start_date"]):
    n_dupes = df.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
    if n_dupes > 0:
        record("no_duplicate_rows", "WARN", f"{n_dupes} duplicate (person_nbr, agency_name, start_date) rows")
    else:
        record("no_duplicate_rows", "PASS", "No duplicate rows")

# agency_name: no code prefixes
if "agency_name" in df.columns:
    agency_code_prefix = df["agency_name"].str.match(r"^[A-Z]\d{3,}\s+", na=False).sum()
    if agency_code_prefix > 0:
        record("agency_no_code_prefix", "FAIL", f"{agency_code_prefix} agency_name values have code prefixes")
    else:
        record("agency_no_code_prefix", "PASS", "No agency code prefixes found")

# Row count sanity
leo_count = df[df["person_nbr"].str.match(r"^[a-z][0-9]", na=False)].shape[0]
corr_count = df[df["person_nbr"].str.match(r"^\d", na=False)].shape[0]
record("row_count_sanity", "PASS" if len(df) > 500000 else "WARN",
       f"Total: {len(df)}, LEO: {leo_count}, Corrections: {corr_count}")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.exists(GT_FILE)
print(f"Ground truth available: {has_groundtruth}")

if has_groundtruth:
    gt = pd.read_csv(GT_FILE, dtype=str, low_memory=False)
    record("groundtruth_loaded", "PASS", f"{len(gt)} rows in ground truth")

    # Row count comparison
    diff_pct = abs(len(df) - len(gt)) / len(gt) * 100
    if diff_pct > 10:
        status = "WARN"
    else:
        status = "PASS"
    record("row_count_vs_groundtruth", status,
           f"Output: {len(df)}, GT: {len(gt)}, diff: {diff_pct:.1f}%")

    # Column overlap
    gt_cols = set(gt.columns)
    out_cols = set(df.columns)
    in_gt_not_out = gt_cols - out_cols
    if in_gt_not_out:
        record("column_coverage", "WARN",
               f"Columns in GT but not output: {sorted(in_gt_not_out)}")
    else:
        record("column_coverage", "PASS", "All GT columns present in output")

    # person_nbr coverage (LEO)
    # GT stores person_nbr uppercase; output is lowercase
    gt_leo_ids = set(gt.loc[gt["person_nbr"].str.match(r"^[A-Za-z][0-9]", na=False), "person_nbr"].str.lower())
    out_leo_ids = set(df.loc[df["person_nbr"].str.match(r"^[a-z][0-9]", na=False), "person_nbr"])
    overlap = len(gt_leo_ids & out_leo_ids)
    total_gt_leo = len(gt_leo_ids)
    pct = overlap / total_gt_leo * 100 if total_gt_leo > 0 else 0
    if pct < 90:
        record("person_nbr_coverage_leo", "WARN",
               f"LEO person_nbr overlap: {overlap}/{total_gt_leo} ({pct:.1f}%)")
    else:
        record("person_nbr_coverage_leo", "PASS",
               f"LEO person_nbr overlap: {overlap}/{total_gt_leo} ({pct:.1f}%)")

    # Spot-check: first few GT rows exist in output with correct values
    gt_leo = gt[gt["person_nbr"].str.match(r"^[A-Za-z][0-9]", na=False)].copy()
    gt_leo["person_nbr_lower"] = gt_leo["person_nbr"].str.lower()
    
    spot_errors = []
    sample_ids = gt_leo["person_nbr_lower"].dropna().unique()[:20]
    for pid in sample_ids:
        gt_rows = gt_leo[gt_leo["person_nbr_lower"] == pid]
        out_rows = df[df["person_nbr"] == pid]
        if len(out_rows) == 0:
            spot_errors.append(f"person_nbr={pid} in GT but not in output")
        else:
            # Check start_dates match
            gt_starts = set(gt_rows["start_date"].dropna())
            out_starts = set(out_rows["start_date"].dropna())
            missing_starts = gt_starts - out_starts
            if missing_starts:
                spot_errors.append(f"{pid}: GT start_dates {missing_starts} not in output")
    
    if spot_errors:
        record("spot_check_leo", "WARN",
               f"{len(spot_errors)} spot-check failures: {spot_errors[:3]}")
    else:
        record("spot_check_leo", "PASS", f"All {len(sample_ids)} spot-checked LEO persons found")

    # Spot-check corrections
    gt_corr = gt[gt["person_nbr"].str.match(r"^\d", na=False)].copy()
    sample_corr_ids = gt_corr["person_nbr"].dropna().unique()[:20]
    corr_spot_errors = []
    for pid in sample_corr_ids:
        gt_rows = gt_corr[gt_corr["person_nbr"] == pid]
        out_rows = df[df["person_nbr"] == pid]
        if len(out_rows) == 0:
            corr_spot_errors.append(f"person_nbr={pid} in GT but not in output")
        else:
            gt_starts = set(gt_rows["start_date"].dropna())
            out_starts = set(out_rows["start_date"].dropna())
            missing_starts = gt_starts - out_starts
            if missing_starts:
                corr_spot_errors.append(f"{pid}: GT start_dates {missing_starts} not in output")

    if corr_spot_errors:
        record("spot_check_corrections", "WARN",
               f"{len(corr_spot_errors)} spot-check failures: {corr_spot_errors[:3]}")
    else:
        record("spot_check_corrections", "PASS",
               f"All {len(sample_corr_ids)} spot-checked corrections persons found")

    # Agency name quality: check expansions for known LEO agencies
    expected_expansions = {
        "adelanto police department",
        "alpine county sheriff's office",
        "alameda police department",
    }
    out_agencies_lower = set(df["agency_name"].str.lower().unique())
    missing_expansions = expected_expansions - out_agencies_lower
    if missing_expansions:
        record("agency_expansion_check", "WARN",
               f"Expected agency names not found: {missing_expansions}")
    else:
        record("agency_expansion_check", "PASS", "Expected expanded agency names present")

    # Corrections agency format check (should be "NNN: FACILITY NAME")
    corr_out = df[df["person_nbr"].str.match(r"^\d", na=False)]
    if len(corr_out) > 0:
        bad_corr_agency = (~corr_out["agency_name"].str.match(r"^\d{3}:", na=False)).sum()
        if bad_corr_agency > 0:
            record("corrections_agency_format", "WARN",
                   f"{bad_corr_agency} corrections agency_name values don't match 'NNN: FACILITY' format")
        else:
            record("corrections_agency_format", "PASS",
                   "All corrections agency_name values match 'NNN: FACILITY' format")

    # separation_reason quality (LEO should have non-empty values)
    if "separation_reason" in df.columns:
        leo_with_end = df[(df["person_nbr"].str.match(r"^[a-z][0-9]", na=False)) &
                          (df["end_date"] != "")]
        if len(leo_with_end) > 0:
            pct_with_reason = (leo_with_end["separation_reason"] != "").sum() / len(leo_with_end) * 100
            if pct_with_reason < 70:
                record("separation_reason_fill", "WARN",
                       f"Only {pct_with_reason:.1f}% of LEO ended employments have separation_reason")
            else:
                record("separation_reason_fill", "PASS",
                       f"{pct_with_reason:.1f}% of LEO ended employments have separation_reason")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Markdown report
lines = ["# CA 2025 Validation Report\n"]
lines.append(f"**Overall: {overall}**\n")
lines.append(f"**Has groundtruth: {has_groundtruth}**\n\n")
lines.append("## Checks\n")
lines.append("| Check | Status | Detail |")
lines.append("|-------|--------|--------|")
for c in checks:
    lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")

lines.append("\n## Summary Statistics\n")
lines.append(f"- Output rows: {len(df)}")
if has_groundtruth:
    lines.append(f"- Ground truth rows: {len(gt)}")
    lines.append(f"- Row count difference: {abs(len(df) - len(gt))} ({abs(len(df) - len(gt)) / len(gt) * 100:.1f}%)")

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(lines))

# JSON report
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\nOverall: {overall}")
print(f"Written: {md_path}")
print(f"Written: {json_path}")
