"""
CA 2025 validate.py
Compares output/ca_index.csv against groundtruth and schema requirements.
Writes:
  output/judge_report.md  (human-readable)
  output/judge_report.json (machine-readable)
"""

import json
import os
import re

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

checks = []  # list of {name, status, detail}

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}: {detail}")

def warn(name, detail=""):
    checks.append({"name": name, "status": "WARN", "detail": detail})
    print(f"  [WARN] {name}: {detail}")

# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
out_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
if not os.path.exists(out_path):
    checks.append({"name": "output_exists", "status": "FAIL", "detail": f"{out_path} not found"})
    # Write reports and exit
    overall = "FAIL"
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": overall, "has_groundtruth": False}, f)
    with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
        f.write("# CA 2025 Validation Report\n\nFAIL: output file not found\n")
    raise SystemExit(1)

print("Loading output...")
df = pd.read_csv(out_path, dtype=str, low_memory=False)
print(f"  {len(df):,} rows loaded")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
print("\n=== Schema Checks ===")

REQUIRED_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
check("required_columns_present", len(missing_cols) == 0,
      f"missing: {missing_cols}" if missing_cols else "all present")

if not missing_cols:
    # person_nbr: no empty, no whitespace
    bad_pnbr = df['person_nbr'].isna() | (df['person_nbr'].str.strip() != df['person_nbr']) | (df['person_nbr'] == '')
    check("person_nbr_clean", bad_pnbr.sum() == 0,
          f"{bad_pnbr.sum()} rows with bad person_nbr")

    # start_date: no empty values
    empty_start = (df['start_date'].isna() | (df['start_date'] == '')).sum()
    check("start_date_no_empty", empty_start == 0,
          f"{empty_start} rows with empty start_date")

    # Date format YYYY-MM-DD
    date_pat = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    bad_start = df['start_date'].dropna().apply(lambda x: not date_pat.match(str(x))).sum()
    check("start_date_format", bad_start == 0,
          f"{bad_start} rows with bad start_date format")

    bad_end = df['end_date'].dropna().apply(
        lambda x: bool(x) and not date_pat.match(str(x))
    ).sum()
    check("end_date_format", bad_end == 0,
          f"{bad_end} rows with bad end_date format")

    # No 0000-00-00 dates
    zero_dates = (
        (df['start_date'] == '0000-00-00') |
        (df['end_date'] == '0000-00-00')
    ).sum()
    check("no_zero_dates", zero_dates == 0,
          f"{zero_dates} rows with 0000-00-00 dates")

    # No NaT / None in dates
    nat_dates = (
        df['start_date'].isin(['NaT', 'None', 'nan']) |
        df['end_date'].isin(['NaT', 'None', 'nan'])
    ).sum()
    check("no_nat_dates", nat_dates == 0,
          f"{nat_dates} rows with NaT/None dates")

    # Duplicate check: person_nbr + agency_name + start_date
    dupes = df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
    check("no_duplicates", dupes == 0,
          f"{dupes} duplicate rows on person_nbr+agency_name+start_date")

    # agency_name: no code prefixes (e.g. "G1720 ...")
    code_prefix = df['agency_name'].str.match(r'^[A-Z]\d{4,}', na=False).sum()
    check("no_agency_code_prefix", code_prefix == 0,
          f"{code_prefix} rows with agency code prefix")

    # Row counts
    leo_rows = (~df['person_nbr'].str.match(r'^\d+', na=False)).sum()
    corr_rows = df['person_nbr'].str.match(r'^\d+', na=False).sum()
    check("has_leo_rows", leo_rows > 400000,
          f"{leo_rows:,} LEO rows (expected ~456k)")
    check("has_corrections_rows", corr_rows > 100000,
          f"{corr_rows:,} corrections rows (expected ~140k+)")

# ---------------------------------------------------------------------------
# Groundtruth comparison
# ---------------------------------------------------------------------------
print("\n=== Groundtruth Comparison ===")
gt_path = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")
has_groundtruth = os.path.exists(gt_path)

if has_groundtruth:
    gt = pd.read_csv(gt_path, dtype=str, low_memory=False)
    print(f"  Groundtruth: {len(gt):,} rows")
    print(f"  Output:      {len(df):,} rows")

    # Row count comparison
    gt_count = len(gt)
    out_count = len(df)
    pct_diff = abs(out_count - gt_count) / gt_count * 100
    if pct_diff <= 5:
        check("row_count_within_5pct", True,
              f"output={out_count:,}, gt={gt_count:,}, diff={pct_diff:.1f}%")
    elif pct_diff <= 15:
        warn("row_count_within_15pct",
             f"output={out_count:,}, gt={gt_count:,}, diff={pct_diff:.1f}% (>5% but within 15%)")
    else:
        check("row_count_reasonable", False,
              f"output={out_count:,}, gt={gt_count:,}, diff={pct_diff:.1f}% exceeds 15%")

    # Match on shared key: person_nbr + agency_name + start_date
    out_key = set(zip(df['person_nbr'], df['agency_name'], df['start_date']))
    gt_key = set(zip(gt['person_nbr'], gt['agency_name'], gt['start_date']))
    matched = len(out_key & gt_key)
    gt_total = len(gt_key)
    match_pct = matched / gt_total * 100 if gt_total > 0 else 0
    if match_pct >= 90:
        check("key_match_90pct", True,
              f"{matched:,}/{gt_total:,} GT keys matched ({match_pct:.1f}%)")
    elif match_pct >= 75:
        warn("key_match_75pct",
             f"{matched:,}/{gt_total:,} GT keys matched ({match_pct:.1f}%)")
    else:
        check("key_match_below_75pct", False,
              f"Only {matched:,}/{gt_total:,} GT keys matched ({match_pct:.1f}%)")

    # Spot-check: first 10 GT rows should be in output
    spot_ok = 0
    spot_total = min(10, len(gt))
    for _, row in gt.head(spot_total).iterrows():
        mask = (
            (df['person_nbr'] == row['person_nbr']) &
            (df['agency_name'] == row['agency_name']) &
            (df['start_date'] == row['start_date'])
        )
        if mask.any():
            spot_ok += 1
    check("spot_check_first_10_gt_rows", spot_ok == spot_total,
          f"{spot_ok}/{spot_total} GT spot-check rows found in output")

    # Agency name quality: compare unique agency names
    gt_agencies = set(gt['agency_name'].dropna().str.strip())
    out_agencies = set(df['agency_name'].dropna().str.strip())
    agency_overlap = len(gt_agencies & out_agencies) / len(gt_agencies) * 100 if gt_agencies else 0
    if agency_overlap >= 80:
        check("agency_name_overlap_80pct", True,
              f"{agency_overlap:.1f}% of GT agency names appear in output ({len(gt_agencies)} GT, {len(out_agencies)} output)")
    else:
        warn("agency_name_overlap_below_80pct",
             f"Only {agency_overlap:.1f}% of GT agency names in output")

    # Missing from output vs GT (agencies in GT but not output)
    gt_only = gt_agencies - out_agencies
    if gt_only:
        print(f"  Agencies in GT but NOT in output (sample 5): {list(gt_only)[:5]}")

    # Date sanity: check a few specific values
    # Person A52-V94 first row
    test_pid = 'A52-V94'
    out_pid = df[df['person_nbr'] == test_pid].sort_values('start_date')
    gt_pid = gt[gt['person_nbr'] == test_pid].sort_values('start_date')
    if len(out_pid) > 0 and len(gt_pid) > 0:
        check("leo_spot_person_date",
              out_pid.iloc[0]['start_date'] == gt_pid.iloc[0]['start_date'],
              f"A52-V94 first start_date: output={out_pid.iloc[0]['start_date']}, gt={gt_pid.iloc[0]['start_date']}")

    # Corrections person 230001
    test_cid = '230001'
    out_cid = df[df['person_nbr'] == test_cid].sort_values('start_date')
    gt_cid = gt[gt['person_nbr'] == test_cid].sort_values('start_date')
    if len(out_cid) > 0 and len(gt_cid) > 0:
        check("corrections_spot_person_date",
              out_cid.iloc[0]['start_date'] == gt_cid.iloc[0]['start_date'],
              f"230001 first start_date: output={out_cid.iloc[0]['start_date']}, gt={gt_cid.iloc[0]['start_date']}")

    # Separation reason check
    if 'separation_reason' in df.columns and 'separation_reason' in gt.columns:
        # Sample: check that separation reasons are correctly mapped
        leo_with_sep = df[
            df['separation_reason'].notna() & (df['separation_reason'] != '')
        ]
        check("separation_reason_populated",
              len(leo_with_sep) > 100000,
              f"{len(leo_with_sep):,} rows with separation_reason")

else:
    warn("no_groundtruth", "No groundtruth found — schema checks only")

# ---------------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------------
print("\n=== Data Quality Checks ===")

# Empty last_name
empty_last = (df['last_name'].isna() | (df['last_name'] == '')).sum()
pct_empty_last = empty_last / len(df) * 100
if pct_empty_last < 1:
    check("last_name_populated", True,
          f"{empty_last} empty ({pct_empty_last:.2f}%)")
else:
    warn("last_name_mostly_populated",
         f"{empty_last} empty last_name ({pct_empty_last:.1f}%)")

# Empty first_name
empty_first = (df['first_name'].isna() | (df['first_name'] == '')).sum()
pct_empty_first = empty_first / len(df) * 100
if pct_empty_first < 1:
    check("first_name_populated", True,
          f"{empty_first} empty ({pct_empty_first:.2f}%)")
else:
    warn("first_name_mostly_populated",
         f"{empty_first} empty first_name ({pct_empty_first:.1f}%)")

# Sample output
print("\nSample output rows (first 3):")
print(df.head(3).to_string())

# ---------------------------------------------------------------------------
# Determine overall result
# ---------------------------------------------------------------------------
statuses = [c["status"] for c in checks]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

print(f"\n=== Overall: {overall} ===")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# judge_report.json
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

# judge_report.md
lines = [
    "# CA 2025 Validation Report",
    "",
    f"**Overall: {overall}**",
    f"**Has Groundtruth: {has_groundtruth}**",
    "",
    f"Output rows: {len(df):,}",
    "",
    "## Check Results",
    "",
    "| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for c in checks:
    lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")

if has_groundtruth:
    lines += [
        "",
        "## Groundtruth Summary",
        f"- GT rows: {len(gt):,}",
        f"- Output rows: {len(df):,}",
        f"- Row count diff: {pct_diff:.1f}%",
        f"- Key match: {match_pct:.1f}%",
        f"- Agency overlap: {agency_overlap:.1f}%",
    ]

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"\nWrote judge_report.md and judge_report.json to {OUTPUT_DIR}/")
