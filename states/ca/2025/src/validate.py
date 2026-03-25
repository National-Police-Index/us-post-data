"""
validate.py — Validation for California POST employment index
Run from states/ca/2025/ as cwd:
    python src/validate.py
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR = "output"
GT_PATH = os.path.join("data", "groundtruth", "ca-index.csv")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "ca_index.csv")

checks = []  # list of {"name": str, "status": "PASS"|"WARN"|"FAIL", "detail": str}

def check(name, status, detail):
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"  {icon} {name}: {detail}")

# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
print("Loading output CSV...")
if not os.path.exists(OUTPUT_CSV):
    checks.append({"name": "output_file_exists", "status": "FAIL",
                   "detail": f"File not found: {OUTPUT_CSV}"})
    _write_reports(checks, has_gt=False)
    sys.exit(1)

df = pd.read_csv(OUTPUT_CSV, low_memory=False, keep_default_na=False, na_values=[''])
print(f"  Output rows: {len(df)}")

has_gt = os.path.exists(GT_PATH)

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
print("\nSchema checks...")
REQUIRED_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    check("required_columns", "FAIL", f"Missing columns: {missing_cols}")
else:
    check("required_columns", "PASS", "All required columns present")

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------
print("\nperson_nbr checks...")
nbr_empty = (df['person_nbr'].isna() | (df['person_nbr'].astype(str).str.strip() == '')).sum()
if nbr_empty > 0:
    check("person_nbr_nonempty", "FAIL", f"{nbr_empty} rows have empty person_nbr")
else:
    check("person_nbr_nonempty", "PASS", "No empty person_nbr values")

# Lowercase check
uppercase_mask = df['person_nbr'].astype(str).str.contains(r'[A-Z]', regex=True, na=False)
if uppercase_mask.sum() > 0:
    check("person_nbr_lowercase", "FAIL",
          f"{uppercase_mask.sum()} person_nbr values contain uppercase letters")
else:
    check("person_nbr_lowercase", "PASS", "All person_nbr values are lowercase")

# Whitespace check
ws_mask = df['person_nbr'].astype(str).str.startswith(' ') | df['person_nbr'].astype(str).str.endswith(' ')
if ws_mask.sum() > 0:
    check("person_nbr_whitespace", "FAIL",
          f"{ws_mask.sum()} person_nbr values have leading/trailing whitespace")
else:
    check("person_nbr_whitespace", "PASS", "No leading/trailing whitespace in person_nbr")

# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------
print("\nDate checks...")
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def check_dates(col):
    # Drop true NaN (empty/null = currently employed for end_date, valid absence for others)
    non_empty = df[col].dropna()
    non_empty = non_empty[non_empty.astype(str).str.strip() != '']
    bad = non_empty[~non_empty.astype(str).str.match(DATE_RE)]
    return len(bad), bad.head(5).tolist()

sd_bad, sd_samples = check_dates('start_date')
if sd_bad > 0:
    check("start_date_format", "FAIL", f"{sd_bad} bad start_date values. Samples: {sd_samples}")
else:
    check("start_date_format", "PASS", "All start_date values are YYYY-MM-DD or empty")

ed_bad, ed_samples = check_dates('end_date')
if ed_bad > 0:
    check("end_date_format", "FAIL", f"{ed_bad} bad end_date values. Samples: {ed_samples}")
else:
    check("end_date_format", "PASS", "All end_date values are YYYY-MM-DD or empty")

# No empty start_date
empty_sd = (df['start_date'].isna() | (df['start_date'].astype(str) == '')).sum()
if empty_sd > 0:
    check("start_date_nonempty", "FAIL", f"{empty_sd} rows have empty start_date")
else:
    check("start_date_nonempty", "PASS", "No empty start_date values")

# No 0000-00-00 or similar invalid dates in start_date
# end_date NaN/null is valid (currently employed); only flag literal bad strings
for bad_val in ['0000-00-00', 'NaT', 'None']:
    sd_bad = (df['start_date'].astype(str) == bad_val).sum()
    ed_bad = (df['end_date'].fillna('').astype(str) == bad_val).sum()
    if sd_bad > 0:
        check(f"no_invalid_start_date_{bad_val}", "FAIL",
              f"{sd_bad} start_date rows contain invalid value '{bad_val}'")
    if ed_bad > 0:
        check(f"no_invalid_end_date_{bad_val}", "FAIL",
              f"{ed_bad} end_date rows contain invalid value '{bad_val}'")

# ---------------------------------------------------------------------------
# Agency name checks
# ---------------------------------------------------------------------------
print("\nAgency checks...")
agency_empty = (df['agency_name'].isna() | (df['agency_name'].astype(str).str.strip() == '')).sum()
if agency_empty > 0:
    check("agency_name_nonempty", "WARN", f"{agency_empty} rows have empty agency_name")
else:
    check("agency_name_nonempty", "PASS", "No empty agency_name values")

# Check for agency code prefixes in LEO records (non-numeric person_nbr)
leo_mask = pd.to_numeric(df['person_nbr'], errors='coerce').isna()
leo_df = df[leo_mask]
code_prefix = leo_df['agency_name'].astype(str).str.match(r'^[A-Z]\d{3,}\s')
if code_prefix.sum() > 0:
    check("agency_code_prefix", "FAIL",
          f"{code_prefix.sum()} LEO agency names still have code prefix")
else:
    check("agency_code_prefix", "PASS", "No agency code prefixes in LEO agency names")

NON_AGENCY = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
non_agency_mask = df['agency_name'].astype(str).str.lower().isin(NON_AGENCY)
if non_agency_mask.sum() > 0:
    check("agency_non_agency_values", "WARN",
          f"{non_agency_mask.sum()} rows have non-agency values in agency_name")
else:
    check("agency_non_agency_values", "PASS", "No non-agency strings in agency_name")

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------
print("\nDuplicate checks...")
dupes = df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
if dupes > 0:
    check("no_duplicates", "WARN", f"{dupes} duplicate (person_nbr, agency_name, start_date) rows")
else:
    check("no_duplicates", "PASS", "No duplicate (person_nbr, agency_name, start_date) rows")

# ---------------------------------------------------------------------------
# Name checks
# ---------------------------------------------------------------------------
print("\nName checks...")
empty_last = (df['last_name'].isna() | (df['last_name'].astype(str).str.strip() == '')).sum()
empty_first = (df['first_name'].isna() | (df['first_name'].astype(str).str.strip() == '')).sum()
if empty_last > 0:
    check("last_name_nonempty", "WARN", f"{empty_last} rows have empty last_name")
else:
    check("last_name_nonempty", "PASS", "No empty last_name values")
if empty_first > 0:
    check("first_name_nonempty", "WARN", f"{empty_first} rows have empty first_name")
else:
    check("first_name_nonempty", "PASS", "No empty first_name values")

# ---------------------------------------------------------------------------
# Row count
# ---------------------------------------------------------------------------
print("\nRow count checks...")
check("row_count", "PASS" if len(df) > 100000 else "WARN",
      f"Output has {len(df):,} rows (minimum expected: 100,000)")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
if has_gt:
    print("\nGround truth comparison...")
    gt = pd.read_csv(GT_PATH, low_memory=False)
    gt_rows = len(gt)
    out_rows = len(df)
    pct_diff = abs(out_rows - gt_rows) / gt_rows * 100

    if pct_diff <= 5:
        check("gt_row_count", "PASS",
              f"Output {out_rows:,} vs GT {gt_rows:,} ({pct_diff:.1f}% diff)")
    elif pct_diff <= 20:
        check("gt_row_count", "WARN",
              f"Output {out_rows:,} vs GT {gt_rows:,} ({pct_diff:.1f}% diff — within tolerance)")
    else:
        check("gt_row_count", "WARN",
              f"Output {out_rows:,} vs GT {gt_rows:,} ({pct_diff:.1f}% diff — large but GT may be stale)")

    # Column presence match
    gt_cols = set(gt.columns)
    out_cols = set(df.columns)
    extra_cols = out_cols - gt_cols
    missing_gt_cols = gt_cols - out_cols
    if missing_gt_cols:
        check("gt_column_match", "WARN",
              f"Columns in GT but not output: {missing_gt_cols}")
    else:
        check("gt_column_match", "PASS",
              f"All GT columns present in output. Extra in output: {extra_cols}")

    # Spot-check first officer from LEO data
    first_leo_nbr = gt[pd.to_numeric(gt['person_nbr'], errors='coerce').isna()]['person_nbr'].iloc[0]
    gt_sample = gt[gt['person_nbr'] == first_leo_nbr].copy()
    out_sample = df[df['person_nbr'] == first_leo_nbr.lower()].copy()

    if len(out_sample) == 0:
        check("gt_spot_check_leo", "WARN", f"Officer {first_leo_nbr} not found in output")
    else:
        # Check agency names match
        gt_agencies = set(gt_sample['agency_name'].tolist())
        out_agencies = set(out_sample['agency_name'].tolist())
        if gt_agencies == out_agencies:
            check("gt_spot_check_leo", "PASS",
                  f"Officer {first_leo_nbr}: agency names match ({len(gt_agencies)} agencies)")
        else:
            diff = gt_agencies.symmetric_difference(out_agencies)
            check("gt_spot_check_leo", "WARN",
                  f"Officer {first_leo_nbr}: agency name differences: {list(diff)[:5]}")

    # Spot-check first corrections officer
    first_corr_nbr = gt[pd.to_numeric(gt['person_nbr'], errors='coerce').notna()]['person_nbr'].iloc[0]
    gt_corr = gt[gt['person_nbr'] == first_corr_nbr].copy()
    out_corr = df[df['person_nbr'] == str(first_corr_nbr)].copy()

    if len(out_corr) == 0:
        check("gt_spot_check_corrections", "WARN",
              f"Corrections officer {first_corr_nbr} not found in output")
    else:
        gt_dates = set(gt_corr['start_date'].tolist())
        out_dates = set(out_corr['start_date'].tolist())
        if gt_dates == out_dates:
            check("gt_spot_check_corrections", "PASS",
                  f"Corrections officer {first_corr_nbr}: start_dates match")
        else:
            extra = out_dates - gt_dates
            missing = gt_dates - out_dates
            check("gt_spot_check_corrections", "WARN",
                  f"Corrections officer {first_corr_nbr}: "
                  f"extra dates in output: {list(extra)[:3]}, "
                  f"missing: {list(missing)[:3]}")

    # Agency name quality check: % of LEO records with expanded agency names
    leo_out = df[pd.to_numeric(df['person_nbr'], errors='coerce').isna()]
    pd_count = leo_out['agency_name'].str.contains('POLICE DEPARTMENT', na=False).sum()
    pd_pct = pd_count / len(leo_out) * 100 if len(leo_out) > 0 else 0
    check("leo_agency_expansion_quality",
          "PASS" if pd_pct > 20 else "WARN",
          f"{pd_count:,} ({pd_pct:.1f}%) LEO records have 'POLICE DEPARTMENT' in agency_name")

else:
    print("\nNo ground truth found — skipping comparison checks")
    check("groundtruth_available", "WARN", "No ground truth file found")

# ---------------------------------------------------------------------------
# Overall result
# ---------------------------------------------------------------------------
def compute_overall(checks):
    statuses = [c['status'] for c in checks]
    if 'FAIL' in statuses:
        return 'FAIL'
    if 'WARN' in statuses:
        return 'WARN'
    return 'PASS'

overall = compute_overall(checks)
print(f"\nOverall: {overall}")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Human-readable markdown
md_lines = [
    "# CA 2025 Validation Report\n",
    f"**Overall: {overall}**\n",
    f"**Has ground truth: {has_gt}**\n",
    f"**Output rows: {len(df):,}**\n",
    "---\n",
    "## Check Results\n",
    "| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c['status']]
    detail = c['detail'].replace("|", "\\|")
    md_lines.append(f"| {c['name']} | {icon} {c['status']} | {detail} |")

md_lines.append("\n## Sample Output\n")
md_lines.append("```")
md_lines.append(df.head(5).to_string())
md_lines.append("```")

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines))

# Machine-readable JSON
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({
        "overall": overall,
        "has_groundtruth": has_gt,
        "output_rows": len(df),
        "checks": checks,
    }, f, indent=2)

print(f"\nReports written to {OUTPUT_DIR}/judge_report.md and judge_report.json")
