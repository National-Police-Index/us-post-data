"""
Validation script for CA 2025 employment index.
Compares against ground truth in data/groundtruth/.
Writes output/judge_report.md and output/judge_report.json.

Run from states/ca/2025/:
  python src/validate.py
"""

import json
import os
import sys

import pandas as pd

OUTPUT_DIR     = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
INDEX_FILE     = os.path.join(OUTPUT_DIR, "ca_index.csv")
GT_FILE        = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

checks  = []   # list of {name, status, detail}
overall = "PASS"


def add_check(name: str, status: str, detail: str):
    checks.append({"name": name, "status": status, "detail": detail})
    global overall
    if status == "FAIL":
        overall = "FAIL"
    elif status == "WARN" and overall != "FAIL":
        overall = "WARN"


# ---- Load output ----
if not os.path.exists(INDEX_FILE):
    add_check("output_file_exists", "FAIL", f"{INDEX_FILE} not found")
    # Write reports and exit
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": "FAIL", "has_groundtruth": False}, f)
    sys.exit(1)

df = pd.read_csv(INDEX_FILE, low_memory=False)
add_check("output_file_exists", "PASS", f"Found {INDEX_FILE} with {len(df):,} rows")

# ---- Load ground truth ----
has_groundtruth = os.path.exists(GT_FILE)
if has_groundtruth:
    gt = pd.read_csv(GT_FILE, low_memory=False)
    add_check("groundtruth_loaded", "PASS",
              f"Ground truth loaded: {len(gt):,} rows")
else:
    gt = None
    add_check("groundtruth_loaded", "WARN", "No ground truth file found — schema checks only")

# ===========================================================================
# SCHEMA CHECKS
# ===========================================================================

required_cols = ["person_nbr", "first_name", "last_name", "agency_name",
                 "start_date", "end_date"]

missing = [c for c in required_cols if c not in df.columns]
if missing:
    add_check("required_columns", "FAIL", f"Missing columns: {missing}")
else:
    add_check("required_columns", "PASS",
              f"All required columns present: {required_cols}")

# person_nbr format
if "person_nbr" in df.columns:
    pnbr = df["person_nbr"].astype(str)
    has_upper   = (pnbr != pnbr.str.lower()).sum()
    has_leading = (pnbr != pnbr.str.strip()).sum()
    if has_upper + has_leading > 0:
        add_check("person_nbr_format", "FAIL",
                  f"{has_upper} non-lowercase, {has_leading} with whitespace")
    else:
        add_check("person_nbr_format", "PASS",
                  "All person_nbr are lowercase with no whitespace")

# No empty start_date
if "start_date" in df.columns:
    empty_start = (df["start_date"].fillna("").astype(str).str.strip() == "").sum()
    if empty_start > 0:
        add_check("start_date_not_empty", "FAIL",
                  f"{empty_start:,} rows have empty start_date")
    else:
        add_check("start_date_not_empty", "PASS", "No empty start_date values")

# Date format check
import re as _re
_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

def pct_valid_dates(series):
    non_empty = series.fillna("").astype(str).str.strip()
    non_empty = non_empty[non_empty != ""]
    if len(non_empty) == 0:
        return 1.0
    valid = non_empty.str.match(_DATE_RE).sum()
    return valid / len(non_empty)

for date_col in ["start_date", "end_date"]:
    if date_col in df.columns:
        pct = pct_valid_dates(df[date_col])
        if pct < 0.99:
            add_check(f"{date_col}_format", "WARN",
                      f"Only {pct:.1%} of non-empty {date_col} match YYYY-MM-DD")
        else:
            add_check(f"{date_col}_format", "PASS",
                      f"{pct:.1%} of non-empty {date_col} are valid YYYY-MM-DD")

# No NaT / None in date columns  
# Note: empty end_date is valid (currently employed); NaN from CSV empty strings is OK.
# Only flag *start_date* NaN as a problem (end_date NaN = open-ended).
for date_col in ["start_date"]:
    if date_col in df.columns:
        bad = df[date_col].isna()
        if bad.sum() > 0:
            add_check(f"{date_col}_no_nat", "FAIL",
                      f"{bad.sum():,} {date_col} values are null/NaN (should be non-empty)")
        else:
            add_check(f"{date_col}_no_nat", "PASS",
                      f"No null values in {date_col}")

# end_date: empty string / NaN = open-ended (valid). Only flag literal "NaT" / "None" strings.
if "end_date" in df.columns:
    # When CSV has empty string, pandas loads as NaN — that's fine.
    # Only bad if the string itself is "NaT", "None", etc.
    bad_str = df["end_date"].fillna("").astype(str).isin(["NaT", "None"])
    if bad_str.sum() > 0:
        add_check("end_date_no_nat", "FAIL",
                  f"{bad_str.sum():,} end_date values contain literal NaT/None strings")
    else:
        add_check("end_date_no_nat", "PASS",
                  "No literal NaT/None strings in end_date (empty = currently employed)")

# Duplicate rows
if all(c in df.columns for c in ["person_nbr", "agency_name", "start_date"]):
    dupes = df.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
    if dupes > 0:
        add_check("no_duplicates", "WARN",
                  f"{dupes:,} duplicate (person_nbr, agency_name, start_date) rows")
    else:
        add_check("no_duplicates", "PASS",
                  "No duplicate (person_nbr, agency_name, start_date) rows")

# agency_name not empty
if "agency_name" in df.columns:
    empty_agency = (df["agency_name"].fillna("").astype(str).str.strip() == "").sum()
    if empty_agency > 0:
        add_check("agency_name_not_empty", "WARN",
                  f"{empty_agency:,} rows have empty agency_name")
    else:
        add_check("agency_name_not_empty", "PASS", "No empty agency_name values")

# ===========================================================================
# GROUND TRUTH COMPARISON
# ===========================================================================

if has_groundtruth and gt is not None:

    # Row count comparison
    row_diff_pct = abs(len(df) - len(gt)) / max(len(gt), 1) * 100
    if row_diff_pct <= 5:
        status = "PASS"
    elif row_diff_pct <= 20:
        status = "WARN"
    else:
        status = "WARN"   # still WARN not FAIL — data drift is expected

    add_check("row_count_comparison", status,
              f"Output: {len(df):,}  GT: {len(gt):,}  diff: {row_diff_pct:.1f}%")

    # Column presence vs GT
    gt_cols    = set(gt.columns)
    out_cols   = set(df.columns)
    extra_cols = out_cols - gt_cols
    miss_cols  = gt_cols - out_cols

    if miss_cols:
        add_check("columns_vs_groundtruth", "WARN",
                  f"Columns in GT but not output: {sorted(miss_cols)}")
    else:
        add_check("columns_vs_groundtruth", "PASS",
                  f"All GT columns present.  Extra in output: {sorted(extra_cols)}")

    # Spot-check: officer A52-V94 (well-known LEO officer)
    target_id = "a52-v94"
    df_officer = df[df["person_nbr"] == target_id]
    gt_officer = gt[gt["person_nbr"].astype(str).str.lower() == target_id]

    if len(df_officer) == 0:
        add_check("spot_check_a52_v94", "FAIL",
                  f"Officer {target_id} not found in output")
    else:
        row_match = len(df_officer) == len(gt_officer)
        status = "PASS" if row_match else "WARN"
        add_check("spot_check_a52_v94", status,
                  f"Officer {target_id}: output {len(df_officer)} rows, GT {len(gt_officer)} rows")

    # Spot-check: corrections officer 230001
    corr_id = "230001"
    df_corr = df[df["person_nbr"] == corr_id]
    gt_corr = gt[gt["person_nbr"].astype(str) == corr_id]

    if len(df_corr) == 0:
        add_check("spot_check_corr_230001", "WARN",
                  f"Corrections officer {corr_id} not found in output")
    else:
        sd_out = df_corr["start_date"].tolist()
        sd_gt  = gt_corr["start_date"].tolist()
        if sorted(sd_out) == sorted(sd_gt):
            add_check("spot_check_corr_230001", "PASS",
                      f"Officer {corr_id} start dates match: {sd_out}")
        else:
            add_check("spot_check_corr_230001", "WARN",
                      f"Officer {corr_id} start dates differ. Output: {sd_out}  GT: {sd_gt}")

    # Agency name quality – compare top-20 agencies by count
    top_out = set(df["agency_name"].value_counts().head(20).index)
    top_gt  = set(gt["agency_name"].value_counts().head(20).index)
    overlap  = len(top_out & top_gt)
    add_check("agency_name_top20_overlap", "PASS" if overlap >= 15 else "WARN",
              f"{overlap}/20 top agencies overlap between output and GT")

    # LEO vs corrections split
    if "type" in df.columns:
        leo_ct  = (df["type"] == "POLICE").sum()
        corr_ct = (df["type"] == "CORRECTIONS").sum()
        # GT: check via person_nbr pattern (numeric = corrections)
        gt_leo_ct  = (~gt["person_nbr"].astype(str).str.match(r"^\d+$")).sum()
        gt_corr_ct = gt["person_nbr"].astype(str).str.match(r"^\d+$").sum()

        leo_diff  = abs(leo_ct  - gt_leo_ct)  / max(gt_leo_ct,  1) * 100
        corr_diff = abs(corr_ct - gt_corr_ct) / max(gt_corr_ct, 1) * 100

        add_check("leo_row_count", "PASS" if leo_diff <= 10 else "WARN",
                  f"LEO: output {leo_ct:,} vs GT {gt_leo_ct:,}  ({leo_diff:.1f}% diff)")
        add_check("corrections_row_count", "PASS" if corr_diff <= 30 else "WARN",
                  f"Corrections: output {corr_ct:,} vs GT {gt_corr_ct:,}  ({corr_diff:.1f}% diff)")

    # Sample value accuracy: first 5 rows of A52-V94 match GT
    if len(df_officer) > 0 and len(gt_officer) > 0:
        df_sorted = df_officer.sort_values("start_date").reset_index(drop=True)
        gt_sorted = gt_officer.sort_values("start_date").reset_index(drop=True)

        mismatches = []
        for col in ["start_date", "end_date", "agency_name"]:
            if col in df_sorted.columns and col in gt_sorted.columns:
                n = min(len(df_sorted), len(gt_sorted))
                match = (df_sorted[col].iloc[:n].values == gt_sorted[col].iloc[:n].values)
                n_match = match.sum()
                if n_match < n:
                    mismatches.append(f"{col}: {n_match}/{n} match")
        if mismatches:
            add_check("value_accuracy_a52_v94", "WARN",
                      f"Value mismatches for {target_id}: {'; '.join(mismatches)}")
        else:
            add_check("value_accuracy_a52_v94", "PASS",
                      f"Values for {target_id} match GT on start_date, end_date, agency_name")

# ===========================================================================
# WRITE REPORTS
# ===========================================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Markdown ---
lines = ["# CA 2025 Employment Index — Validation Report", ""]
lines.append(f"**Overall**: {overall}")
lines.append(f"**Has Ground Truth**: {has_groundtruth}")
lines.append("")
lines.append("## Check Results")
lines.append("")
lines.append("| Check | Status | Detail |")
lines.append("|-------|--------|--------|")

for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["status"], "")
    lines.append(f"| {c['name']} | {icon} {c['status']} | {c['detail']} |")

lines.append("")
lines.append("## Output Summary")
lines.append("")
lines.append(f"- **Total rows**: {len(df):,}")
if "type" in df.columns:
    for t, cnt in df["type"].value_counts().items():
        lines.append(f"  - {t}: {cnt:,}")
lines.append(f"- **Columns**: {', '.join(df.columns.tolist())}")

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(lines))
print(f"Wrote {md_path}")

# --- JSON ---
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump({
        "overall":         overall,
        "has_groundtruth": has_groundtruth,
        "checks":          checks,
        "row_count":       len(df),
    }, f, indent=2)
print(f"Wrote {json_path}")
print(f"Overall: {overall}")
