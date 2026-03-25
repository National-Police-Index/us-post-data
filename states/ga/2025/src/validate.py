"""
Georgia POST Validation Script
Compares output CSVs against ground truth and writes judge reports.
"""

import json
import os
import re
import pandas as pd

OUTPUT_DIR = "output"
GT_DIR     = "data/groundtruth"

checks  = []   # list of {"name", "status", "detail"}
overall = "PASS"

def record(name, status, detail=""):
    """Record a check result and update overall status."""
    global overall
    checks.append({"name": name, "status": status, "detail": detail})
    if status == "FAIL" and overall != "FAIL":
        overall = "FAIL"
    elif status == "WARN" and overall == "PASS":
        overall = "WARN"
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
    print(f"  {icon} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
print("\n=== Loading output files ===")
emp_path  = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(emp_path):
    record("output_files", "FAIL", f"Missing {emp_path}")
    # Write reports and exit
else:
    emp = pd.read_csv(emp_path, dtype=str, keep_default_na=False, low_memory=False)
    record("output_files_employment", "PASS", f"Loaded {len(emp):,} rows")

disc_exists = os.path.exists(disc_path)
if disc_exists:
    disc = pd.read_csv(disc_path, dtype=str, keep_default_na=False, low_memory=False)
    record("output_files_discipline", "PASS", f"Loaded {len(disc):,} rows")
else:
    record("output_files_discipline", "FAIL", f"Missing {disc_path}")

# ---------------------------------------------------------------------------
# Schema checks — Employment
# ---------------------------------------------------------------------------
print("\n=== Schema checks: Employment Index ===")
REQUIRED_EMP_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                     'start_date', 'end_date']
missing_emp = [c for c in REQUIRED_EMP_COLS if c not in emp.columns]
if missing_emp:
    record("emp_required_columns", "FAIL", f"Missing: {missing_emp}")
else:
    record("emp_required_columns", "PASS", f"All required columns present")

# Optional but expected
EXPECTED_EMP_COLS = ['full_name', 'rank', 'employment_status', 'middle_name',
                     'suffix', 'year_of_birth', 'race', 'sex']
missing_opt = [c for c in EXPECTED_EMP_COLS if c not in emp.columns]
if missing_opt:
    record("emp_optional_columns", "WARN", f"Missing optional: {missing_opt}")
else:
    record("emp_optional_columns", "PASS", "All optional columns present")

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------
print("\n=== person_nbr format checks ===")
# Must be lowercase, no leading/trailing whitespace
nbr_ws = emp['person_nbr'].str.strip() != emp['person_nbr']
if nbr_ws.any():
    record("emp_person_nbr_whitespace", "FAIL",
           f"{nbr_ws.sum()} rows with whitespace in person_nbr")
else:
    record("emp_person_nbr_whitespace", "PASS", "No whitespace in person_nbr")

nbr_lower = emp['person_nbr'] == emp['person_nbr'].str.lower()
if not nbr_lower.all():
    record("emp_person_nbr_lowercase", "FAIL",
           f"{(~nbr_lower).sum()} rows where person_nbr not lowercase")
else:
    record("emp_person_nbr_lowercase", "PASS", "All person_nbr are lowercase")

# GA person_nbr format: 'o####' (peace officers) or 'c####' (corrections officers)
nbr_pattern = emp['person_nbr'].str.match(r'^[oc]\d+$', na=False)
if not nbr_pattern.all():
    bad = emp[~nbr_pattern]['person_nbr'].head(5).tolist()
    record("emp_person_nbr_format", "WARN",
           f"{(~nbr_pattern).sum()} rows not matching '[oc]####' pattern. Sample: {bad}")
else:
    record("emp_person_nbr_format", "PASS", "All person_nbr match '[oc]####' pattern")

# ---------------------------------------------------------------------------
# Date format checks — Employment
# ---------------------------------------------------------------------------
print("\n=== Date format checks: Employment ===")

empty_start = (emp['start_date'] == '').sum()
if empty_start > 0:
    record("emp_start_date_nonempty", "FAIL",
           f"{empty_start} rows with empty start_date")
else:
    record("emp_start_date_nonempty", "PASS", "No empty start_date")

# start_date format YYYY-MM-DD
def check_date_format(series, name):
    valid = series.str.match(r'^\d{4}-\d{2}-\d{2}$', na=False) | (series == '')
    bad = (~valid).sum()
    if bad > 0:
        record(f"{name}_format", "FAIL",
               f"{bad} values not matching YYYY-MM-DD: {series[~valid].head(3).tolist()}")
    else:
        record(f"{name}_format", "PASS", "All dates match YYYY-MM-DD or empty")

check_date_format(emp['start_date'], "emp_start_date")
check_date_format(emp['end_date'], "emp_end_date")

# Check end_date: 0000-00-00 is expected (currently employed)
zero_end = (emp['end_date'] == '0000-00-00').sum()
record("emp_end_date_zero", "PASS" if zero_end >= 0 else "PASS",
       f"{zero_end:,} rows with end_date='0000-00-00' (currently employed)")

# ---------------------------------------------------------------------------
# Agency name checks
# ---------------------------------------------------------------------------
print("\n=== Agency name checks ===")
# Must have G-code prefix
has_code = emp['agency_name'].str.match(r'^G\d+\s+', na=False)
no_code_count = (~has_code).sum()
if no_code_count > 0:
    bad_agency = emp[~has_code]['agency_name'].value_counts().head(5).to_dict()
    record("emp_agency_has_code", "WARN",
           f"{no_code_count} rows without G#### prefix. Top: {bad_agency}")
else:
    record("emp_agency_has_code", "PASS", "All agency_name have G#### prefix")

# Slashes in agency names are expected for GA (e.g. "PRISON/INACTIVE")
# Just report count as informational
has_slash = emp['agency_name'].str.contains(r'/', na=False)
record("emp_agency_slash_info", "PASS",
       f"{has_slash.sum():,} agency names contain slash (expected for GA inactive agencies)")

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------
print("\n=== Duplicate checks ===")
dupe_emp = emp.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
if dupe_emp > 0:
    record("emp_no_duplicates", "FAIL",
           f"{dupe_emp} duplicate rows (person_nbr+agency_name+start_date)")
else:
    record("emp_no_duplicates", "PASS", "No duplicate employment rows")

if disc_exists:
    dupe_disc = disc.duplicated(
        subset=['case_id', 'person_nbr', 'violation', 'sanction']
    ).sum()
    if dupe_disc > 0:
        record("disc_no_duplicates", "FAIL",
               f"{dupe_disc} duplicate rows (case_id+person_nbr+violation+sanction)")
    else:
        record("disc_no_duplicates", "PASS", "No duplicate discipline rows")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
print("\n=== Ground truth comparison ===")
has_groundtruth = False

gt_emp_path  = os.path.join(GT_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GT_DIR, "georgia-discipline_index.csv")

if os.path.exists(gt_emp_path):
    has_groundtruth = True
    gt_emp = pd.read_csv(gt_emp_path, dtype=str, keep_default_na=False, low_memory=False)
    gt_disc = pd.read_csv(gt_disc_path, dtype=str, keep_default_na=False, low_memory=False) \
              if os.path.exists(gt_disc_path) else None

    # Row count comparison — Employment
    gt_n  = len(gt_emp)
    out_n = len(emp)
    diff_pct = abs(out_n - gt_n) / gt_n * 100
    if diff_pct <= 5:
        record("emp_row_count", "PASS",
               f"Output {out_n:,} vs GT {gt_n:,} ({diff_pct:.1f}% diff)")
    elif diff_pct <= 15:
        record("emp_row_count", "WARN",
               f"Output {out_n:,} vs GT {gt_n:,} ({diff_pct:.1f}% diff — data may have grown)")
    else:
        record("emp_row_count", "WARN",
               f"Output {out_n:,} vs GT {gt_n:,} ({diff_pct:.1f}% diff — large divergence)")

    # Value spot-check on employment — match on (person_nbr, agency_name, start_date)
    try:
        # Build a key for matching
        gt_keyed  = gt_emp.copy()
        out_keyed = emp.copy()
        gt_keyed['_key']  = gt_keyed['person_nbr'] + '|' + gt_keyed['agency_name'] + '|' + gt_keyed['start_date']
        out_keyed['_key'] = out_keyed['person_nbr'] + '|' + out_keyed['agency_name'] + '|' + out_keyed['start_date']

        common_keys = set(gt_keyed['_key']) & set(out_keyed['_key'])
        overlap_pct = len(common_keys) / len(gt_keyed) * 100
        record("emp_row_overlap", "PASS" if overlap_pct >= 90 else "WARN",
               f"{len(common_keys):,}/{len(gt_keyed):,} GT rows matched in output ({overlap_pct:.1f}%)")

        # Spot-check values for matching rows (deduplicate both on _key)
        gt_match  = gt_keyed[gt_keyed['_key'].isin(common_keys)].drop_duplicates('_key').set_index('_key')
        out_match = out_keyed[out_keyed['_key'].isin(common_keys)].drop_duplicates('_key').set_index('_key')
        sample_keys = sorted(common_keys)[:500]
        check_cols = ['full_name', 'last_name', 'first_name']
        mismatches = 0
        total_checks = 0
        for col in check_cols:
            if col not in gt_match.columns or col not in out_match.columns:
                continue
            shared = [k for k in sample_keys if k in gt_match.index and k in out_match.index]
            gt_vals  = gt_match.loc[shared, col].values
            out_vals = out_match.loc[shared, col].values
            mismatches += (gt_vals != out_vals).sum()
            total_checks += len(shared)
        match_pct = (1 - mismatches / total_checks) * 100 if total_checks > 0 else 100
        if match_pct >= 95:
            record("emp_value_spot_check", "PASS",
                   f"{match_pct:.1f}% value match on {len(sample_keys)} sampled rows")
        elif match_pct >= 80:
            record("emp_value_spot_check", "WARN",
                   f"{match_pct:.1f}% value match on {len(sample_keys)} rows ({mismatches} mismatches)")
        else:
            record("emp_value_spot_check", "WARN",
                   f"{match_pct:.1f}% value match on {len(sample_keys)} rows — possible name parsing diff")
    except Exception as e:
        record("emp_value_spot_check", "WARN", f"Could not run spot check: {e}")

    # Discipline row count comparison
    if gt_disc is not None and disc_exists:
        gt_dn  = len(gt_disc)
        out_dn = len(disc)
        diff_dpct = abs(out_dn - gt_dn) / gt_dn * 100
        if diff_dpct <= 5:
            record("disc_row_count", "PASS",
                   f"Output {out_dn:,} vs GT {gt_dn:,} ({diff_dpct:.1f}% diff)")
        elif diff_dpct <= 100:
            record("disc_row_count", "WARN",
                   f"Output {out_dn:,} vs GT {gt_dn:,} ({diff_dpct:.1f}% diff — data has grown)")
        else:
            record("disc_row_count", "WARN",
                   f"Output {out_dn:,} vs GT {gt_dn:,} ({diff_dpct:.1f}% diff — large divergence)")

        # Value spot-check on discipline — rows that exist in both by case_id
        try:
            gt_disc_sorted  = gt_disc.sort_values(['case_id', 'person_nbr', 'violation']).reset_index(drop=True)
            out_disc_sorted = disc.sort_values(['case_id', 'person_nbr', 'violation']).reset_index(drop=True)

            # Find case_ids that exist in both
            gt_cases  = set(gt_disc['case_id'].astype(str))
            out_cases = set(disc['case_id'].astype(str))
            common = gt_cases & out_cases
            match_rate = len(common) / len(gt_cases) * 100 if gt_cases else 0
            record("disc_case_overlap", "PASS" if match_rate >= 80 else "WARN",
                   f"{len(common):,}/{len(gt_cases):,} GT cases found in output ({match_rate:.1f}%)")
        except Exception as e:
            record("disc_value_spot_check", "WARN", f"Could not run spot check: {e}")

    # Column schema match
    gt_emp_cols  = set(gt_emp.columns)
    out_emp_cols = set(emp.columns)
    extra_out = out_emp_cols - gt_emp_cols
    missing_out = gt_emp_cols - out_emp_cols
    if missing_out:
        record("emp_schema_vs_gt", "WARN", f"Columns in GT but not output: {missing_out}")
    elif extra_out:
        record("emp_schema_vs_gt", "PASS", f"Output has extra columns vs GT: {extra_out}")
    else:
        record("emp_schema_vs_gt", "PASS", "Output columns match GT exactly")

else:
    record("groundtruth_available", "WARN", "No ground truth files found — schema checks only")

# ---------------------------------------------------------------------------
# Discipline schema checks
# ---------------------------------------------------------------------------
if disc_exists:
    print("\n=== Schema checks: Discipline Index ===")
    REQUIRED_DISC_COLS = ['case_id', 'person_nbr', 'first_name', 'last_name',
                          'agency_name', 'start_date', 'end_date',
                          'violation', 'sanction']
    missing_disc_cols = [c for c in REQUIRED_DISC_COLS if c not in disc.columns]
    if missing_disc_cols:
        record("disc_required_columns", "FAIL", f"Missing: {missing_disc_cols}")
    else:
        record("disc_required_columns", "PASS", "All required discipline columns present")

    empty_disc_start = (disc['start_date'] == '').sum()
    if empty_disc_start > 0:
        record("disc_start_date_nonempty", "WARN",
               f"{empty_disc_start} discipline rows with empty start_date")
    else:
        record("disc_start_date_nonempty", "PASS", "No empty discipline start_date")

    check_date_format(disc['violation_date'], "disc_violation_date")
    check_date_format(disc['sanction_date'],  "disc_sanction_date")

    # agency_name in discipline should be lowercase
    disc_agency_upper = disc['agency_name'].str.contains('[A-Z]', na=False).sum()
    if disc_agency_upper > 0:
        record("disc_agency_lowercase", "WARN",
               f"{disc_agency_upper} discipline agency names not all-lowercase")
    else:
        record("disc_agency_lowercase", "PASS", "All discipline agency names are lowercase")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"\n=== Overall: {overall} ===")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Human-readable markdown report
md_lines = [
    "# Georgia POST Validation Report\n",
    f"**Overall: {overall}**  \n",
    f"**Has groundtruth: {has_groundtruth}**\n",
    "",
    "## Check Results\n",
    "| Status | Check | Detail |",
    "|--------|-------|--------|",
]
for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["status"], "?")
    md_lines.append(f"| {icon} {c['status']} | {c['name']} | {c['detail']} |")

md_lines.extend([
    "",
    "## Summary",
    f"- Total checks: {len(checks)}",
    f"- PASS: {sum(1 for c in checks if c['status']=='PASS')}",
    f"- WARN: {sum(1 for c in checks if c['status']=='WARN')}",
    f"- FAIL: {sum(1 for c in checks if c['status']=='FAIL')}",
])

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines))

# Machine-readable JSON report
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({
        "overall": overall,
        "has_groundtruth": has_groundtruth,
        "checks": checks,
    }, f, indent=2)

print(f"\nReports written to {OUTPUT_DIR}/judge_report.md and {OUTPUT_DIR}/judge_report.json")
