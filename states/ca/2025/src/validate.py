"""
Validation script for California employment index.
Compares output/ca_index.csv against data/groundtruth/ca-index.csv.
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR    = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
OUTPUT_CSV    = os.path.join(OUTPUT_DIR, "ca_index.csv")
GT_CSV        = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load files
# ---------------------------------------------------------------------------
checks = []
overall = "PASS"

def add_check(name, status, detail=""):
    """status: PASS | WARN | FAIL"""
    global overall
    checks.append({"name": name, "status": status, "detail": detail})
    if status == "FAIL" and overall != "FAIL":
        overall = "FAIL"
    elif status == "WARN" and overall == "PASS":
        overall = "WARN"


print("Loading output CSV...")
if not os.path.exists(OUTPUT_CSV):
    add_check("output_exists", "FAIL", f"{OUTPUT_CSV} not found")
    # Write reports and exit
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": "FAIL", "has_groundtruth": False}, f, indent=2)
    with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
        f.write("# CA Validation Report\n\n**FAIL** — output file not found\n")
    sys.exit(1)

df = pd.read_csv(OUTPUT_CSV, low_memory=False, dtype=str)
df = df.fillna('')
print(f"  Output rows: {len(df)}")

has_groundtruth = os.path.exists(GT_CSV)
if has_groundtruth:
    print("Loading groundtruth CSV...")
    gt = pd.read_csv(GT_CSV, low_memory=False, dtype=str)
    gt = gt.fillna('')
    print(f"  Groundtruth rows: {len(gt)}")

# ===========================================================================
# CHECK 1: Required columns present
# ===========================================================================
required_cols = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                 'start_date', 'end_date']
missing = [c for c in required_cols if c not in df.columns]
if missing:
    add_check("required_columns", "FAIL", f"Missing columns: {missing}")
else:
    add_check("required_columns", "PASS",
              f"All required columns present: {required_cols}")

# ===========================================================================
# CHECK 2: No empty start_date
# ===========================================================================
empty_start = (df['start_date'] == '') | df['start_date'].isna()
n_empty = int(empty_start.sum())
if n_empty > 0:
    add_check("no_empty_start_date", "FAIL",
              f"{n_empty} rows have empty start_date")
else:
    add_check("no_empty_start_date", "PASS", "No empty start_date values")

# ===========================================================================
# CHECK 3: person_nbr format (lowercase, no whitespace)
# ===========================================================================
bad_nbr = df['person_nbr'].apply(
    lambda x: str(x) != str(x).lower().strip()
)
n_bad_nbr = int(bad_nbr.sum())
if n_bad_nbr > 0:
    add_check("person_nbr_format", "WARN",
              f"{n_bad_nbr} person_nbr values not lowercase/stripped")
else:
    add_check("person_nbr_format", "PASS",
              "All person_nbr values are lowercase and stripped")

# ===========================================================================
# CHECK 4: Date format YYYY-MM-DD
# ===========================================================================
date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
bad_start = df.loc[df['start_date'] != '', 'start_date'].apply(
    lambda x: not date_re.match(str(x))
)
bad_end = df.loc[df['end_date'] != '', 'end_date'].apply(
    lambda x: not date_re.match(str(x))
)
n_bad_dates = int(bad_start.sum()) + int(bad_end.sum())
if n_bad_dates > 0:
    add_check("date_format", "FAIL",
              f"{n_bad_dates} date values not in YYYY-MM-DD format")
else:
    add_check("date_format", "PASS",
              "All non-empty dates are in YYYY-MM-DD format")

# ===========================================================================
# CHECK 5: No fully duplicate rows
# ===========================================================================
dupe_cols = ['person_nbr', 'agency_name', 'start_date']
n_dupes = int(df.duplicated(subset=dupe_cols).sum())
if n_dupes > 0:
    add_check("no_duplicate_rows", "WARN",
              f"{n_dupes} duplicate rows (person_nbr+agency_name+start_date)")
else:
    add_check("no_duplicate_rows", "PASS", "No duplicate rows")

# ===========================================================================
# CHECK 6: agency_name has no agency code prefix
# ===========================================================================
# LEO rows should not have codes like "G1720 " prefix
# Corrections rows should have "NNN: " prefix (that's correct for CA)
leo_rows = df[~df['person_nbr'].str.match(r'^\d+$')]
code_prefix = leo_rows['agency_name'].str.match(r'^[A-Z]\d{3,}\s+')
n_code = int(code_prefix.sum())
if n_code > 0:
    add_check("agency_no_code_prefix", "WARN",
              f"{n_code} LEO agency_name values have code prefix")
else:
    add_check("agency_no_code_prefix", "PASS",
              "No agency code prefixes found in LEO rows")

# ===========================================================================
# CHECK 7: Row count vs groundtruth
# ===========================================================================
if has_groundtruth:
    gt_count  = len(gt)
    out_count = len(df)
    pct_diff  = abs(out_count - gt_count) / gt_count * 100

    # Split by LEO vs corrections
    out_leo  = df[~df['person_nbr'].str.match(r'^\d+$')]
    out_corr = df[df['person_nbr'].str.match(r'^\d+$')]
    gt_leo   = gt[~gt['person_nbr'].str.match(r'^\d+$')]
    gt_corr  = gt[gt['person_nbr'].str.match(r'^\d+$')]

    leo_pct  = abs(len(out_leo) - len(gt_leo)) / max(len(gt_leo), 1) * 100
    corr_pct = abs(len(out_corr) - len(gt_corr)) / max(len(gt_corr), 1) * 100

    detail = (
        f"Total: output={out_count}, gt={gt_count}, diff={out_count-gt_count} ({pct_diff:.1f}%)\n"
        f"  LEO:  output={len(out_leo)}, gt={len(gt_leo)}, diff={len(out_leo)-len(gt_leo)} ({leo_pct:.1f}%)\n"
        f"  CORR: output={len(out_corr)}, gt={len(gt_corr)}, diff={len(out_corr)-len(gt_corr)} ({corr_pct:.1f}%)"
    )

    if pct_diff <= 5.0:
        add_check("row_count_vs_groundtruth", "PASS", detail)
    elif pct_diff <= 15.0:
        add_check("row_count_vs_groundtruth", "WARN", detail)
    else:
        add_check("row_count_vs_groundtruth", "FAIL", detail)

# ===========================================================================
# CHECK 8: Spot-check key values vs groundtruth
# ===========================================================================
if has_groundtruth:
    # Normalize GT person_nbr to lowercase for comparison
    gt_norm = gt.copy()
    gt_norm['person_nbr'] = gt_norm['person_nbr'].str.lower().str.strip()

    # Spot-check first 5 records from GT (by person_nbr + start_date)
    spot_matches = 0
    spot_total   = 0
    spot_details = []

    sample = gt_norm.head(20).copy()
    for _, row in sample.iterrows():
        pid   = row['person_nbr']
        sdate = row['start_date']
        match = df[
            (df['person_nbr'] == pid) &
            (df['start_date'] == sdate)
        ]
        spot_total += 1
        if len(match) > 0:
            spot_matches += 1
        else:
            spot_details.append(f"  Missing: person_nbr={pid}, start_date={sdate}")

    pct_match = spot_matches / spot_total * 100 if spot_total > 0 else 0
    detail_str = f"{spot_matches}/{spot_total} spot records found ({pct_match:.0f}%)"
    if spot_details:
        detail_str += "\n" + "\n".join(spot_details[:5])

    if pct_match >= 90:
        add_check("spot_check_key_values", "PASS", detail_str)
    elif pct_match >= 70:
        add_check("spot_check_key_values", "WARN", detail_str)
    else:
        add_check("spot_check_key_values", "FAIL", detail_str)

# ===========================================================================
# CHECK 9: Agency name quality — LEO spot-check
# ===========================================================================
if has_groundtruth:
    # Compare top LEO agency names
    top_out = set(df[~df['person_nbr'].str.match(r'^\d+$')]['agency_name']
                  .value_counts().head(10).index)
    top_gt  = set(gt_norm[~gt_norm['person_nbr'].str.match(r'^\d+$')]['agency_name']
                  .value_counts().head(10).index)

    # Normalize for comparison (uppercase)
    top_out_norm = {x.upper() for x in top_out}
    top_gt_norm  = {x.upper() for x in top_gt}
    overlap = top_out_norm & top_gt_norm
    pct_overlap = len(overlap) / len(top_gt_norm) * 100

    detail = (
        f"Top-10 LEO agency overlap: {len(overlap)}/10 ({pct_overlap:.0f}%)\n"
        f"  In GT not output: {top_gt_norm - top_out_norm}\n"
        f"  In output not GT: {top_out_norm - top_gt_norm}"
    )

    if pct_overlap >= 80:
        add_check("agency_name_quality_leo", "PASS", detail)
    elif pct_overlap >= 60:
        add_check("agency_name_quality_leo", "WARN", detail)
    else:
        add_check("agency_name_quality_leo", "FAIL", detail)

# ===========================================================================
# CHECK 10: Separation reason population
# ===========================================================================
if 'separation_reason' in df.columns:
    leo_df  = df[~df['person_nbr'].str.match(r'^\d+$')]
    filled  = (leo_df['separation_reason'] != '').sum()
    total   = len(leo_df)
    pct     = filled / total * 100 if total > 0 else 0
    detail  = f"{filled}/{total} LEO rows have separation_reason ({pct:.1f}%)"
    if pct >= 70:
        add_check("separation_reason_populated", "PASS", detail)
    elif pct >= 50:
        add_check("separation_reason_populated", "WARN", detail)
    else:
        add_check("separation_reason_populated", "WARN",
                  detail + " (rows with empty end_date have no separation)")
else:
    add_check("separation_reason_populated", "WARN",
              "separation_reason column not present")

# ===========================================================================
# CHECK 11: type column
# ===========================================================================
if 'type' in df.columns:
    types = df['type'].value_counts().to_dict()
    add_check("type_column", "PASS", f"type values: {types}")
else:
    add_check("type_column", "WARN", "type column not present")

# ===========================================================================
# CHECK 12: Name parsing quality
# ===========================================================================
empty_first = (df['first_name'] == '').sum()
empty_last  = (df['last_name'] == '').sum()
n_rows      = len(df)
detail = (
    f"Empty first_name: {empty_first}/{n_rows} ({empty_first/n_rows*100:.1f}%)\n"
    f"Empty last_name:  {empty_last}/{n_rows} ({empty_last/n_rows*100:.1f}%)"
)
if empty_first / n_rows < 0.01 and empty_last / n_rows < 0.01:
    add_check("name_parsing_quality", "PASS", detail)
elif empty_first / n_rows < 0.05 and empty_last / n_rows < 0.05:
    add_check("name_parsing_quality", "WARN", detail)
else:
    add_check("name_parsing_quality", "FAIL", detail)

# ===========================================================================
# Write reports
# ===========================================================================
# judge_report.md
md_lines = [
    "# California 2025 — Validation Report",
    "",
    f"**Overall: {overall}**",
    f"**Has groundtruth: {has_groundtruth}**",
    "",
    f"Output rows: {len(df):,}",
]
if has_groundtruth:
    md_lines.append(f"Groundtruth rows: {len(gt):,}")
md_lines += ["", "---", "", "## Checks", ""]

for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["status"], "?")
    md_lines.append(f"### {icon} {c['name']} — {c['status']}")
    if c["detail"]:
        for line in c["detail"].split("\n"):
            md_lines.append(f"  {line}")
    md_lines.append("")

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(md_lines))
print(f"Wrote {md_path}")

# judge_report.json
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump({
        "overall": overall,
        "has_groundtruth": has_groundtruth,
        "checks": checks,
        "output_rows": len(df),
        "groundtruth_rows": len(gt) if has_groundtruth else None,
    }, f, indent=2)
print(f"Wrote {json_path}")

print(f"\n=== Overall: {overall} ===")
for c in checks:
    print(f"  [{c['status']}] {c['name']}: {c['detail'][:80] if c['detail'] else ''}")
