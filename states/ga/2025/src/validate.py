"""
Validation script for Georgia POST data (2025).
Writes:
  output/judge_report.md   — human-readable
  output/judge_report.json — {"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}
"""
import json
import os
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
REPORT_MD = os.path.join(OUTPUT_DIR, "judge_report.md")
REPORT_JSON = os.path.join(OUTPUT_DIR, "judge_report.json")

checks = []   # List of (name, status, message)
# status: PASS | WARN | FAIL


def check(name, status, message):
    checks.append((name, status, message))
    print(f"[{status}] {name}: {message}")


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(emp_path):
    check("employment_file_exists", "FAIL", f"{emp_path} not found")
    # Cannot continue
    checks_summary = "FAIL"
else:
    check("employment_file_exists", "PASS", f"{emp_path} found")

if not os.path.exists(disc_path):
    check("discipline_file_exists", "FAIL", f"{disc_path} not found")
else:
    check("discipline_file_exists", "PASS", f"{disc_path} found")

emp_df = pd.read_csv(emp_path, dtype=str, keep_default_na=False)
disc_df = pd.read_csv(disc_path, dtype=str, keep_default_na=False) if os.path.exists(disc_path) else pd.DataFrame()

# ---------------------------------------------------------------------------
# Schema checks — employment
# ---------------------------------------------------------------------------
REQUIRED_EMP_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_emp = [c for c in REQUIRED_EMP_COLS if c not in emp_df.columns]
if missing_emp:
    check("emp_required_columns", "FAIL", f"Missing columns: {missing_emp}")
else:
    check("emp_required_columns", "PASS", "All required columns present")

# ---------------------------------------------------------------------------
# Schema checks — discipline
# ---------------------------------------------------------------------------
REQUIRED_DISC_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                       'start_date', 'end_date', 'case_id', 'violation',
                       'violation_date', 'sanction', 'sanction_date']
if not disc_df.empty:
    missing_disc = [c for c in REQUIRED_DISC_COLS if c not in disc_df.columns]
    if missing_disc:
        check("disc_required_columns", "FAIL", f"Missing columns: {missing_disc}")
    else:
        check("disc_required_columns", "PASS", "All required discipline columns present")

# ---------------------------------------------------------------------------
# person_nbr format checks
# ---------------------------------------------------------------------------
if 'person_nbr' in emp_df.columns:
    nbr = emp_df['person_nbr']
    bad_ws = (nbr != nbr.str.strip()).sum()
    bad_case = (nbr != nbr.str.lower()).sum()
    empty_nbr = (nbr == '').sum()
    if bad_ws > 0 or bad_case > 0:
        check("emp_person_nbr_format", "FAIL",
              f"person_nbr has {bad_ws} whitespace issues, {bad_case} non-lowercase")
    elif empty_nbr > 0:
        check("emp_person_nbr_format", "WARN", f"{empty_nbr} empty person_nbr values")
    else:
        check("emp_person_nbr_format", "PASS", "person_nbr is lowercase, no whitespace")

# ---------------------------------------------------------------------------
# start_date not empty
# ---------------------------------------------------------------------------
if 'start_date' in emp_df.columns:
    empty_sd = (emp_df['start_date'] == '').sum()
    if empty_sd > 0:
        check("emp_start_date_not_empty", "FAIL", f"{empty_sd} rows with empty start_date")
    else:
        check("emp_start_date_not_empty", "PASS", "No empty start_date values")

# ---------------------------------------------------------------------------
# Date format checks (YYYY-MM-DD or empty or 0000-00-00)
# ---------------------------------------------------------------------------
import re
DATE_PAT = re.compile(r'^\d{4}-\d{2}-\d{2}$|^$|^0000-00-00$')

def check_date_col(df, col, label):
    if col not in df.columns:
        return
    bad = df[col][~df[col].apply(lambda x: bool(DATE_PAT.match(str(x))))].shape[0]
    if bad > 0:
        check(f"{label}_{col}_format", "WARN", f"{bad} values not in YYYY-MM-DD or empty")
    else:
        check(f"{label}_{col}_format", "PASS", f"All {col} values correctly formatted")

check_date_col(emp_df, 'start_date', 'emp')
check_date_col(emp_df, 'end_date', 'emp')
if not disc_df.empty:
    check_date_col(disc_df, 'violation_date', 'disc')
    check_date_col(disc_df, 'sanction_date', 'disc')
    check_date_col(disc_df, 'start_date', 'disc')
    check_date_col(disc_df, 'end_date', 'disc')

# ---------------------------------------------------------------------------
# Duplicate check — employment
# ---------------------------------------------------------------------------
if all(c in emp_df.columns for c in ['person_nbr', 'agency_name', 'start_date']):
    dupes = emp_df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
    if dupes > 0:
        check("emp_duplicates", "WARN", f"{dupes} duplicate (person_nbr, agency_name, start_date) rows")
    else:
        check("emp_duplicates", "PASS", "No duplicate rows")

# ---------------------------------------------------------------------------
# Row count plausibility
# ---------------------------------------------------------------------------
check("emp_row_count", "PASS" if len(emp_df) > 100000 else "WARN",
      f"Employment index has {len(emp_df):,} rows")
if not disc_df.empty:
    check("disc_row_count", "PASS" if len(disc_df) > 10000 else "WARN",
          f"Discipline index has {len(disc_df):,} rows")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.isdir(GROUNDTRUTH_DIR)
gt_emp_path = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

has_groundtruth = os.path.exists(gt_emp_path) or os.path.exists(gt_disc_path)

if has_groundtruth:
    # --- Employment row count vs GT ---
    if os.path.exists(gt_emp_path):
        gt_emp = pd.read_csv(gt_emp_path, dtype=str, keep_default_na=False)
        gt_emp_count = len(gt_emp)
        out_emp_count = len(emp_df)
        pct_diff = abs(out_emp_count - gt_emp_count) / gt_emp_count * 100
        status = "PASS" if pct_diff <= 5 else "WARN"
        check("emp_row_count_vs_gt", status,
              f"Output {out_emp_count:,} vs GT {gt_emp_count:,} ({pct_diff:.1f}% diff)")

        # Spot-check: sample 100 person_nbr values from GT and verify they exist in output
        sample_nbr = gt_emp['person_nbr'].dropna().sample(min(100, len(gt_emp)), random_state=42)
        out_nbr_set = set(emp_df['person_nbr'].unique())
        found = sum(1 for n in sample_nbr if n in out_nbr_set)
        pct_found = found / len(sample_nbr) * 100
        status = "PASS" if pct_found >= 90 else ("WARN" if pct_found >= 75 else "FAIL")
        check("emp_person_nbr_coverage", status,
              f"{found}/{len(sample_nbr)} GT person_nbr values found in output ({pct_found:.1f}%)")

        # Spot-check: compare agency_name values
        sample_agencies = gt_emp['agency_name'].dropna().unique()[:20]
        out_agencies = set(emp_df['agency_name'].str.lower().unique())
        found_agencies = sum(1 for a in sample_agencies if str(a).lower() in out_agencies)
        pct_ag = found_agencies / len(sample_agencies) * 100
        status = "PASS" if pct_ag >= 80 else "WARN"
        check("emp_agency_name_coverage", status,
              f"{found_agencies}/{len(sample_agencies)} GT agency names found in output ({pct_ag:.1f}%)")

        # Spot-check a specific row
        if len(gt_emp) > 0:
            sample_row = gt_emp.iloc[0]
            match = emp_df[
                (emp_df['person_nbr'] == sample_row['person_nbr']) &
                (emp_df['start_date'] == sample_row['start_date'])
            ]
            if len(match) > 0:
                check("emp_spot_check_row", "PASS",
                      f"Sample row person_nbr={sample_row['person_nbr']} start={sample_row['start_date']} found in output")
            else:
                check("emp_spot_check_row", "WARN",
                      f"Sample row person_nbr={sample_row['person_nbr']} start={sample_row['start_date']} NOT found in output")

    # --- Discipline row count vs GT ---
    if os.path.exists(gt_disc_path) and not disc_df.empty:
        gt_disc = pd.read_csv(gt_disc_path, dtype=str, keep_default_na=False)
        gt_disc_count = len(gt_disc)
        out_disc_count = len(disc_df)
        pct_diff = abs(out_disc_count - gt_disc_count) / gt_disc_count * 100
        status = "PASS" if pct_diff <= 10 else "WARN"
        check("disc_row_count_vs_gt", status,
              f"Output {out_disc_count:,} vs GT {gt_disc_count:,} ({pct_diff:.1f}% diff) — data growth expected")

        # Spot-check: GT cases should appear in output
        gt_cases = gt_disc['case_id'].dropna().unique()
        sample_cases = gt_cases[:min(100, len(gt_cases))]
        out_cases = set(disc_df['case_id'].unique())
        found_cases = sum(1 for c in sample_cases if c in out_cases)
        pct_cases = found_cases / len(sample_cases) * 100
        status = "PASS" if pct_cases >= 80 else "WARN"
        check("disc_case_coverage", status,
              f"{found_cases}/{len(sample_cases)} GT case_ids found in output ({pct_cases:.1f}%)")

        # Spot-check a specific discipline row
        if len(gt_disc) > 0:
            sample_row = gt_disc.iloc[0]
            match = disc_df[
                (disc_df['case_id'] == sample_row['case_id']) &
                (disc_df['person_nbr'] == sample_row['person_nbr']) &
                (disc_df['violation'] == sample_row['violation'])
            ]
            if len(match) > 0:
                check("disc_spot_check_row", "PASS",
                      f"Sample disc row case={sample_row['case_id']} violation='{sample_row['violation']}' found")
            else:
                check("disc_spot_check_row", "WARN",
                      f"Sample disc row case={sample_row['case_id']} violation='{sample_row['violation']}' NOT found")

        # Column value checks: verify discipline columns are correctly lowercased
        if 'agency_name' in disc_df.columns:
            all_lower = (disc_df['agency_name'] == disc_df['agency_name'].str.lower()).all()
            check("disc_agency_lowercase", "PASS" if all_lower else "WARN",
                  "agency_name is lowercased in discipline index" if all_lower else "agency_name NOT fully lowercased")

else:
    check("groundtruth_available", "WARN", "No ground truth found — skipping comparison checks")

# ---------------------------------------------------------------------------
# Content quality checks
# ---------------------------------------------------------------------------
# Check for known bad values in agency_name
BAD_AGENCY_VALS = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
if 'agency_name' in emp_df.columns:
    bad_agency = emp_df['agency_name'].str.lower().isin(BAD_AGENCY_VALS).sum()
    if bad_agency > 0:
        check("emp_no_bad_agency_names", "FAIL", f"{bad_agency} rows with known non-agency values")
    else:
        check("emp_no_bad_agency_names", "PASS", "No known non-agency values in agency_name")

# Check that person_nbr starts with 'o' (Georgia format)
if 'person_nbr' in emp_df.columns:
    starts_with_o = emp_df['person_nbr'].str.startswith('o').sum()
    pct = starts_with_o / len(emp_df) * 100
    status = "PASS" if pct > 95 else "WARN"
    check("emp_person_nbr_ga_format", status,
          f"{pct:.1f}% of person_nbr values start with 'o' (expected for GA)")

# Check for NaT / None strings in date columns
for col in ['start_date', 'end_date']:
    if col in emp_df.columns:
        bad_str = emp_df[col].isin(['NaT', 'None', 'nan', 'NaN']).sum()
        if bad_str > 0:
            check(f"emp_{col}_no_invalid_strings", "FAIL",
                  f"{bad_str} rows with invalid date string '{bad_str}' in {col}")
        else:
            check(f"emp_{col}_no_invalid_strings", "PASS",
                  f"No invalid date strings in {col}")

# ---------------------------------------------------------------------------
# Overall result
# ---------------------------------------------------------------------------
fail_count = sum(1 for _, s, _ in checks if s == "FAIL")
warn_count = sum(1 for _, s, _ in checks if s == "WARN")
pass_count = sum(1 for _, s, _ in checks if s == "PASS")

if fail_count > 0:
    overall = "FAIL"
elif warn_count > 0:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(REPORT_MD, "w") as f:
    f.write("# Georgia POST 2025 — Judge Report\n\n")
    f.write(f"**Overall: {overall}**  \n")
    f.write(f"Checks: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL  \n")
    f.write(f"Ground truth available: {has_groundtruth}  \n\n")
    f.write("## Check Results\n\n")
    f.write("| Check | Status | Message |\n")
    f.write("|-------|--------|--------|\n")
    for name, status, message in checks:
        icon = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
        f.write(f"| {name} | {icon} {status} | {message} |\n")
    f.write("\n## Summary\n\n")
    f.write(f"- Employment index rows: {len(emp_df):,}\n")
    if not disc_df.empty:
        f.write(f"- Discipline index rows: {len(disc_df):,}\n")
    f.write(f"- Total checks: {len(checks)}\n")
    f.write(f"- Overall result: **{overall}**\n")

# ---------------------------------------------------------------------------
# Write judge_report.json
# ---------------------------------------------------------------------------
with open(REPORT_JSON, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\n=== OVERALL: {overall} ===")
print(f"PASS: {pass_count}, WARN: {warn_count}, FAIL: {fail_count}")
print(f"Reports written to {REPORT_MD} and {REPORT_JSON}")
