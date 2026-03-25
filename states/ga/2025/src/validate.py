"""
Validation script for Georgia POST data.
Compares output against groundtruth and writes judge_report.md + judge_report.json.
"""

import json
import os
import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

checks = []
overall = "PASS"


def add_check(name, status, message, detail=""):
    """Add a check result. status: PASS | WARN | FAIL"""
    global overall
    checks.append({"name": name, "status": status, "message": message, "detail": detail})
    if status == "FAIL" and overall != "FAIL":
        overall = "FAIL"
    elif status == "WARN" and overall == "PASS":
        overall = "WARN"
    print(f"  [{status}] {name}: {message}")


def safe_pct(a, b):
    return 0.0 if b == 0 else abs(a - b) / b


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
print("Loading output files...")

emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(emp_path):
    add_check("output_files", "FAIL", f"Missing output file: {emp_path}")
    emp_df = None
else:
    emp_df = pd.read_csv(emp_path, dtype=str, keep_default_na=False)
    add_check("output_files_emp", "PASS", f"Employment index loaded: {len(emp_df)} rows")

if not os.path.exists(disc_path):
    add_check("output_files_disc", "FAIL", f"Missing output file: {disc_path}")
    disc_df = None
else:
    disc_df = pd.read_csv(disc_path, dtype=str, keep_default_na=False)
    add_check("output_files_disc", "PASS", f"Discipline index loaded: {len(disc_df)} rows")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
print("Running schema checks...")

EMP_REQUIRED = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
DISC_REQUIRED = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date',
                 'case_id', 'violation', 'violation_date', 'sanction', 'sanction_date']

if emp_df is not None:
    missing = [c for c in EMP_REQUIRED if c not in emp_df.columns]
    if missing:
        add_check("emp_schema", "FAIL", f"Missing required columns: {missing}")
    else:
        add_check("emp_schema", "PASS", "All required employment columns present")

if disc_df is not None:
    missing = [c for c in DISC_REQUIRED if c not in disc_df.columns]
    if missing:
        add_check("disc_schema", "FAIL", f"Missing required columns: {missing}")
    else:
        add_check("disc_schema", "PASS", "All required discipline columns present")

# ---------------------------------------------------------------------------
# person_nbr format checks
# ---------------------------------------------------------------------------
print("Running person_nbr checks...")

if emp_df is not None:
    # person_nbr should be lowercase, no leading/trailing whitespace
    bad_ws = emp_df['person_nbr'].str.strip() != emp_df['person_nbr']
    bad_case = emp_df['person_nbr'] != emp_df['person_nbr'].str.lower()
    empty_pnbr = (emp_df['person_nbr'] == '') | emp_df['person_nbr'].isna()
    if bad_ws.sum() > 0:
        add_check("emp_person_nbr_whitespace", "FAIL", f"{bad_ws.sum()} person_nbr values have whitespace")
    else:
        add_check("emp_person_nbr_whitespace", "PASS", "No whitespace in person_nbr")
    if bad_case.sum() > 0:
        add_check("emp_person_nbr_case", "FAIL", f"{bad_case.sum()} person_nbr values not lowercase")
    else:
        add_check("emp_person_nbr_case", "PASS", "All person_nbr lowercase")
    if empty_pnbr.sum() > 0:
        add_check("emp_person_nbr_empty", "FAIL", f"{empty_pnbr.sum()} empty person_nbr values")
    else:
        add_check("emp_person_nbr_empty", "PASS", "No empty person_nbr")

# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------
print("Running date format checks...")

DATE_RE = r'^\d{4}-\d{2}-\d{2}$|^0000-00-00$|^$'

if emp_df is not None:
    # start_date must not be empty
    empty_start = (emp_df['start_date'] == '') | emp_df['start_date'].isna()
    if empty_start.sum() > 0:
        add_check("emp_start_date_empty", "FAIL", f"{empty_start.sum()} empty start_date values")
    else:
        add_check("emp_start_date_empty", "PASS", "No empty start_date values")

    bad_start = ~emp_df['start_date'].str.match(DATE_RE, na=False)
    if bad_start.sum() > 0:
        add_check("emp_start_date_format", "WARN", f"{bad_start.sum()} start_date values with bad format",
                  str(emp_df.loc[bad_start, 'start_date'].head(5).tolist()))
    else:
        add_check("emp_start_date_format", "PASS", "All start_date values have valid format")

    bad_end = ~emp_df['end_date'].str.match(DATE_RE, na=False)
    if bad_end.sum() > 0:
        add_check("emp_end_date_format", "WARN", f"{bad_end.sum()} end_date values with bad format",
                  str(emp_df.loc[bad_end, 'end_date'].head(5).tolist()))
    else:
        add_check("emp_end_date_format", "PASS", "All end_date values have valid format")

if disc_df is not None:
    empty_start = (disc_df['start_date'] == '') | disc_df['start_date'].isna()
    if empty_start.sum() > 0:
        add_check("disc_start_date_empty", "FAIL", f"{empty_start.sum()} empty start_date in discipline")
    else:
        add_check("disc_start_date_empty", "PASS", "No empty start_date in discipline index")

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------
print("Running duplicate checks...")

if emp_df is not None:
    dupes = emp_df.duplicated(subset=['person_nbr', 'agency_name', 'start_date'])
    if dupes.sum() > 0:
        add_check("emp_duplicates", "WARN", f"{dupes.sum()} duplicate rows (person_nbr+agency_name+start_date)")
    else:
        add_check("emp_duplicates", "PASS", "No duplicate employment rows")

if disc_df is not None:
    # Discipline index may have multiple rows per (case_id, person_nbr, violation)
    # because each row represents a different employment period overlap.
    # Check for full-row duplicates instead.
    dupes = disc_df.duplicated()
    if dupes.sum() > 0:
        add_check("disc_duplicates", "FAIL", f"{dupes.sum()} exact duplicate discipline rows")
    else:
        add_check("disc_duplicates", "PASS", "No exact duplicate discipline rows")

# ---------------------------------------------------------------------------
# Groundtruth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.isdir(GROUNDTRUTH_DIR)

if has_groundtruth:
    print("Running groundtruth comparison...")

    gt_emp_path = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
    gt_disc_path = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

    # Employment row count
    if os.path.exists(gt_emp_path) and emp_df is not None:
        gt_emp = pd.read_csv(gt_emp_path, dtype=str, keep_default_na=False)
        gt_count = len(gt_emp)
        out_count = len(emp_df)
        pct_diff = safe_pct(out_count, gt_count)
        msg = f"Output: {out_count}, Groundtruth: {gt_count}, Diff: {pct_diff:.1%}"
        if pct_diff <= 0.05:
            add_check("emp_row_count", "PASS", msg)
        elif pct_diff <= 0.10:
            add_check("emp_row_count", "WARN", msg)
        else:
            add_check("emp_row_count", "FAIL", msg)

        # Spot-check first few rows (person_nbr + agency_name + start_date)
        spot_cols = ['person_nbr', 'agency_name', 'start_date', 'end_date', 'full_name']
        spot_cols = [c for c in spot_cols if c in emp_df.columns and c in gt_emp.columns]
        gt_spot = gt_emp[spot_cols].head(20)
        out_spot = emp_df[spot_cols].head(20)
        if gt_spot.equals(out_spot):
            add_check("emp_spot_check", "PASS", "First 20 rows match groundtruth exactly")
        else:
            mismatches = (gt_spot != out_spot).any(axis=1).sum()
            add_check("emp_spot_check", "WARN", f"{mismatches}/20 spot-check rows differ from groundtruth",
                      f"GT sample:\n{gt_spot.head(3).to_string()}\nOutput sample:\n{out_spot.head(3).to_string()}")

        # Column presence check
        missing_gt_cols = [c for c in gt_emp.columns if c not in emp_df.columns]
        if missing_gt_cols:
            add_check("emp_columns_vs_gt", "WARN", f"Columns in groundtruth but not output: {missing_gt_cols}")
        else:
            add_check("emp_columns_vs_gt", "PASS", "All groundtruth columns present in output")

        # Value spot-check: person_nbr o143810
        if 'o143810' in emp_df['person_nbr'].values:
            sample = emp_df[emp_df['person_nbr'] == 'o143810'].iloc[0]
            gt_sample = gt_emp[gt_emp['person_nbr'] == 'o143810'].iloc[0]
            errors = []
            for col in ['agency_name', 'start_date', 'full_name']:
                if col in sample.index and col in gt_sample.index:
                    if sample[col] != gt_sample[col]:
                        errors.append(f"{col}: got '{sample[col]}' expected '{gt_sample[col]}'")
            if errors:
                add_check("emp_value_spot_o143810", "WARN", f"Value differences: {errors}")
            else:
                add_check("emp_value_spot_o143810", "PASS", "Sample officer o143810 values match groundtruth")

    # Discipline row count
    if os.path.exists(gt_disc_path) and disc_df is not None:
        gt_disc = pd.read_csv(gt_disc_path, dtype=str, keep_default_na=False)
        gt_count = len(gt_disc)
        out_count = len(disc_df)
        pct_diff = safe_pct(out_count, gt_count)
        msg = f"Output: {out_count}, Groundtruth: {gt_count}, Diff: {pct_diff:.1%}"
        if pct_diff <= 0.05:
            add_check("disc_row_count", "PASS", msg)
        elif pct_diff <= 0.15:
            add_check("disc_row_count", "WARN", msg)
        else:
            add_check("disc_row_count", "FAIL", msg)

        # Spot-check: check overlap of (case_id, person_nbr, violation, sanction) tuples
        spot_cols = ['case_id', 'person_nbr', 'violation', 'sanction']
        spot_cols = [c for c in spot_cols if c in disc_df.columns and c in gt_disc.columns]
        gt_tuples = set(gt_disc[spot_cols].apply(tuple, axis=1))
        out_tuples = set(disc_df[spot_cols].apply(tuple, axis=1))
        overlap = len(gt_tuples & out_tuples)
        overlap_pct = overlap / len(gt_tuples) if gt_tuples else 0
        msg = f"Tuple overlap: {overlap}/{len(gt_tuples)} GT tuples found in output ({overlap_pct:.1%})"
        if overlap_pct >= 0.90:
            add_check("disc_spot_check", "PASS", msg)
        elif overlap_pct >= 0.75:
            add_check("disc_spot_check", "WARN", msg)
        else:
            add_check("disc_spot_check", "FAIL", msg)

else:
    add_check("groundtruth", "WARN", "No groundtruth directory found — skipping comparison checks")

# ---------------------------------------------------------------------------
# Agency name quality checks
# ---------------------------------------------------------------------------
print("Running agency quality checks...")

if emp_df is not None:
    # Employment index should keep agency code prefix (G####)
    has_prefix = emp_df['agency_name'].str.match(r'^[A-Z]\d+\s+', na=False)
    non_agency = emp_df[~has_prefix]['agency_name'].str.lower().isin(
        {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
    )
    pct_with_prefix = has_prefix.mean()
    if pct_with_prefix >= 0.95:
        add_check("emp_agency_prefix", "PASS", f"{pct_with_prefix:.1%} employment agency names have code prefix")
    else:
        add_check("emp_agency_prefix", "WARN", f"Only {pct_with_prefix:.1%} employment agency names have code prefix")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
print("Writing judge reports...")

# Markdown report
md_lines = ["# GA 2025 Validation Report\n"]
md_lines.append(f"**Overall: {overall}**\n")
md_lines.append(f"Has groundtruth: {has_groundtruth}\n")
md_lines.append("\n## Check Results\n")
md_lines.append("| Check | Status | Message |")
md_lines.append("|-------|--------|---------|")
for c in checks:
    detail = f" ({c['detail'][:80]}...)" if c.get('detail', '') and len(c['detail']) > 80 else (f" ({c['detail']})" if c.get('detail') else "")
    md_lines.append(f"| {c['name']} | {c['status']} | {c['message']}{detail} |")

md_lines.append("\n## Summary\n")
pass_count = sum(1 for c in checks if c['status'] == 'PASS')
warn_count = sum(1 for c in checks if c['status'] == 'WARN')
fail_count = sum(1 for c in checks if c['status'] == 'FAIL')
md_lines.append(f"- PASS: {pass_count}")
md_lines.append(f"- WARN: {warn_count}")
md_lines.append(f"- FAIL: {fail_count}")

if emp_df is not None:
    md_lines.append(f"\n## Output Statistics")
    md_lines.append(f"- Employment index rows: {len(emp_df)}")
    md_lines.append(f"- Unique officers (employment): {emp_df['person_nbr'].nunique()}")
if disc_df is not None:
    md_lines.append(f"- Discipline index rows: {len(disc_df)}")
    md_lines.append(f"- Unique officers (discipline): {disc_df['person_nbr'].nunique()}")

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines) + "\n")

with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\nOverall: {overall}")
print(f"Report written to {OUTPUT_DIR}/judge_report.md and {OUTPUT_DIR}/judge_report.json")
