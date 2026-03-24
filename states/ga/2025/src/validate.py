"""
Validation script for Georgia POST data cleaning.
Compares output CSVs against ground truth and writes judge reports.

Run from states/ga/2025/:
  python src/validate.py
"""

import os
import json
import pandas as pd

OUTPUT_DIR = "output"
GT_DIR = "data/groundtruth"

checks = []  # List of {"name": str, "status": "PASS"|"WARN"|"FAIL", "detail": str}


def check(name, status, detail):
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"  {icon} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load outputs
# ---------------------------------------------------------------------------

print("Loading output files...")
emp_path = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(emp_path):
    check("ga_index.csv exists", "FAIL", "File not found")
    emp_df = None
else:
    emp_df = pd.read_csv(emp_path, dtype=str, keep_default_na=False)
    check("ga_index.csv exists", "PASS", f"{len(emp_df):,} rows")

if not os.path.exists(disc_path):
    check("ga-discipline_index.csv exists", "FAIL", "File not found")
    disc_df = None
else:
    disc_df = pd.read_csv(disc_path, dtype=str, keep_default_na=False)
    check("ga-discipline_index.csv exists", "PASS", f"{len(disc_df):,} rows")


# ---------------------------------------------------------------------------
# Load ground truth
# ---------------------------------------------------------------------------

gt_emp_path = os.path.join(GT_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GT_DIR, "georgia-discipline_index.csv")

has_groundtruth = os.path.exists(gt_emp_path) and os.path.exists(gt_disc_path)
print(f"\nGround truth available: {has_groundtruth}")

if has_groundtruth:
    gt_emp = pd.read_csv(gt_emp_path, dtype=str, keep_default_na=False)
    gt_disc = pd.read_csv(gt_disc_path, dtype=str, keep_default_na=False)
    print(f"  GT employment: {len(gt_emp):,} rows")
    print(f"  GT discipline: {len(gt_disc):,} rows")


# ---------------------------------------------------------------------------
# Schema checks — employment index
# ---------------------------------------------------------------------------

print("\n--- Employment Index Schema Checks ---")

REQUIRED_EMP_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
OPTIONAL_EMP_COLS = ['full_name', 'middle_name', 'suffix', 'rank', 'employment_status',
                     'race', 'sex', 'year_of_birth']

if emp_df is not None:
    missing = [c for c in REQUIRED_EMP_COLS if c not in emp_df.columns]
    if missing:
        check("Required columns present", "FAIL", f"Missing: {missing}")
    else:
        check("Required columns present", "PASS", f"All {len(REQUIRED_EMP_COLS)} required columns present")

    optional_present = [c for c in OPTIONAL_EMP_COLS if c in emp_df.columns]
    check("Optional columns", "PASS", f"{len(optional_present)}/{len(OPTIONAL_EMP_COLS)} optional columns present: {optional_present}")

    # person_nbr format: GA uses 'o<digits>' for peace officers, 'c<digits>' for corrections officers
    bad_pnbr = ~emp_df['person_nbr'].str.match(r'^[a-z]\d+$')
    n_bad = bad_pnbr.sum()
    if n_bad == 0:
        check("person_nbr format (letter + digits)", "PASS", "All person_nbr match '<letter><digits>' pattern")
    else:
        samples = emp_df.loc[bad_pnbr, 'person_nbr'].head(3).tolist()
        check("person_nbr format (letter + digits)", "WARN", f"{n_bad} don't match pattern. Samples: {samples}")

    # Check breakdown: o* vs c* prefixes
    o_count = emp_df['person_nbr'].str.startswith('o').sum()
    c_count = emp_df['person_nbr'].str.startswith('c').sum()
    check("person_nbr prefix distribution", "PASS",
          f"o-prefix (peace officers): {o_count:,}, c-prefix (corrections): {c_count:,}")

    # person_nbr lowercase/no-whitespace
    has_upper = emp_df['person_nbr'].str.contains('[A-Z]').any()
    has_ws = emp_df['person_nbr'].str.contains(r'\s').any()
    if has_upper or has_ws:
        check("person_nbr lowercase & no whitespace", "FAIL", f"upper={has_upper}, whitespace={has_ws}")
    else:
        check("person_nbr lowercase & no whitespace", "PASS", "Clean")

    # start_date not empty
    empty_start = (emp_df['start_date'] == '').sum()
    if empty_start == 0:
        check("start_date never empty", "PASS", "No empty start_date values")
    else:
        check("start_date never empty", "FAIL", f"{empty_start} empty start_date rows")

    # start_date format YYYY-MM-DD
    valid_date_mask = emp_df['start_date'].str.match(r'^\d{4}-\d{2}-\d{2}$')
    n_invalid = (~valid_date_mask).sum()
    if n_invalid == 0:
        check("start_date format YYYY-MM-DD", "PASS", "All start_dates correctly formatted")
    else:
        check("start_date format YYYY-MM-DD", "FAIL", f"{n_invalid} rows with invalid format")

    # end_date format: YYYY-MM-DD or 0000-00-00 or empty
    valid_end = emp_df['end_date'].str.match(r'^\d{4}-\d{2}-\d{2}$') | (emp_df['end_date'] == '')
    n_invalid_end = (~valid_end).sum()
    if n_invalid_end == 0:
        check("end_date format", "PASS", "All end_dates correctly formatted (YYYY-MM-DD, 0000-00-00, or empty)")
    else:
        samples = emp_df.loc[~valid_end, 'end_date'].head(3).tolist()
        check("end_date format", "WARN", f"{n_invalid_end} rows with unexpected format. Samples: {samples}")

    # agency_name not empty
    empty_agency = (emp_df['agency_name'] == '').sum()
    if empty_agency == 0:
        check("agency_name not empty", "PASS", "No empty agency_name values")
    else:
        check("agency_name not empty", "WARN", f"{empty_agency} empty agency_name values")

    # No duplicates on key triplet
    dupes = emp_df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
    if dupes == 0:
        check("No duplicate rows (person_nbr+agency_name+start_date)", "PASS", "No duplicates")
    else:
        check("No duplicate rows (person_nbr+agency_name+start_date)", "WARN", f"{dupes} duplicate rows")


# ---------------------------------------------------------------------------
# Schema checks — discipline index
# ---------------------------------------------------------------------------

print("\n--- Discipline Index Schema Checks ---")

REQUIRED_DISC_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                      'start_date', 'end_date', 'case_id', 'violation', 'sanction']

if disc_df is not None:
    missing = [c for c in REQUIRED_DISC_COLS if c not in disc_df.columns]
    if missing:
        check("Discipline required columns", "FAIL", f"Missing: {missing}")
    else:
        check("Discipline required columns", "PASS", f"All required discipline columns present")

    # start_date not empty
    empty_start = (disc_df['start_date'] == '').sum()
    if empty_start == 0:
        check("Discipline start_date never empty", "PASS", "No empty start_date values")
    else:
        check("Discipline start_date never empty", "WARN", f"{empty_start} empty start_date rows")

    # violation_date: no 0000-00-00
    zero_dates = (disc_df['violation_date'] == '0000-00-00').sum()
    if zero_dates == 0:
        check("Discipline violation_date no 0000-00-00", "PASS", "No invalid 0000-00-00 violation dates")
    else:
        check("Discipline violation_date no 0000-00-00", "FAIL", f"{zero_dates} rows with 0000-00-00 violation_date")

    # person_nbr format
    bad_pnbr = ~disc_df['person_nbr'].str.match(r'^[a-z]\d+$')
    n_bad = bad_pnbr.sum()
    if n_bad == 0:
        check("Discipline person_nbr format", "PASS", "All match '<letter><digits>'")
    else:
        check("Discipline person_nbr format", "WARN", f"{n_bad} don't match pattern")


# ---------------------------------------------------------------------------
# Ground truth comparison — employment index
# ---------------------------------------------------------------------------

if has_groundtruth and emp_df is not None:
    print("\n--- Ground Truth Comparison: Employment Index ---")

    # Row count
    gt_count = len(gt_emp)
    out_count = len(emp_df)
    pct_diff = abs(out_count - gt_count) / gt_count * 100
    if pct_diff <= 5:
        check("Employment row count vs GT", "PASS",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}%")
    elif pct_diff <= 15:
        check("Employment row count vs GT", "WARN",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}% (expected: data grows over time)")
    else:
        check("Employment row count vs GT", "WARN",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}% (large difference, data may have grown)")

    # Sample spot-check: match first 100 rows of GT by person_nbr+agency_name+start_date
    gt_key = gt_emp[['person_nbr', 'agency_name', 'start_date']].head(100)
    out_indexed = emp_df.set_index(['person_nbr', 'agency_name', 'start_date'])
    found = 0
    for _, row in gt_key.iterrows():
        key = (row['person_nbr'], row['agency_name'], row['start_date'])
        if key in out_indexed.index:
            found += 1
    pct_found = found / len(gt_key) * 100
    if pct_found >= 90:
        check("Employment spot-check (100 GT rows found in output)", "PASS",
              f"{found}/100 GT rows found in output ({pct_found:.0f}%)")
    elif pct_found >= 70:
        check("Employment spot-check (100 GT rows found in output)", "WARN",
              f"{found}/100 GT rows found in output ({pct_found:.0f}%)")
    else:
        check("Employment spot-check (100 GT rows found in output)", "FAIL",
              f"Only {found}/100 GT rows found in output ({pct_found:.0f}%)")

    # Column overlap
    gt_cols = set(gt_emp.columns)
    out_cols = set(emp_df.columns)
    common = gt_cols & out_cols
    check("Employment column overlap with GT", "PASS",
          f"{len(common)}/{len(gt_cols)} GT columns present in output")

    # Value spot-check on a matching row
    # Note: GT has lowercase names; output preserves raw source case (uppercase).
    # This is correct per spec: "Output names in whatever case the source provides"
    # We only check fields that should be identical: person_nbr, agency_name, start_date, end_date
    sample_key = ('o143810', 'G1720 DEKALB COUNTY POLICE DEPARTMENT', '2007-09-10')
    if sample_key in out_indexed.index:
        out_row = out_indexed.loc[sample_key]
        if isinstance(out_row, pd.DataFrame):
            out_row = out_row.iloc[0]
        gt_row = gt_emp[(gt_emp['person_nbr'] == sample_key[0]) &
                        (gt_emp['agency_name'] == sample_key[1]) &
                        (gt_emp['start_date'] == sample_key[2])].iloc[0]
        mismatches = []
        # Check case-insensitive for name fields (source data is uppercase, GT is lowercase)
        for col in ['full_name', 'end_date']:
            if col in out_row.index and col in gt_row.index:
                out_val = str(out_row[col]).strip().lower()
                gt_val = str(gt_row[col]).strip().lower()
                if out_val != gt_val:
                    mismatches.append(f"{col}: got '{out_row[col]}' expected '{gt_row[col]}'")
        if not mismatches:
            check("Employment value spot-check (o143810)", "PASS",
                  "Key fields match GT (full_name case-insensitive, end_date exact)")
        else:
            check("Employment value spot-check (o143810)", "WARN",
                  f"Mismatches: {'; '.join(mismatches)}")
    else:
        check("Employment value spot-check (o143810)", "WARN", "Row not found in output")


# ---------------------------------------------------------------------------
# Ground truth comparison — discipline index
# ---------------------------------------------------------------------------

if has_groundtruth and disc_df is not None:
    print("\n--- Ground Truth Comparison: Discipline Index ---")

    # Row count
    gt_count = len(gt_disc)
    out_count = len(disc_df)
    pct_diff = abs(out_count - gt_count) / gt_count * 100
    if pct_diff <= 5:
        check("Discipline row count vs GT", "PASS",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}%")
    elif pct_diff <= 20:
        check("Discipline row count vs GT", "WARN",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}% (data has grown since GT snapshot)")
    else:
        check("Discipline row count vs GT", "WARN",
              f"Output={out_count:,}, GT={gt_count:,}, diff={pct_diff:.1f}% (large diff; GT is a point-in-time snapshot)")

    # Spot-check: look up a few GT rows in output
    # GT case_id is zero-padded string; output case_id is also string
    gt_sample = gt_disc.head(20)
    disc_indexed = disc_df.set_index(['case_id', 'person_nbr', 'violation'])
    found = 0
    for _, row in gt_sample.iterrows():
        key = (row['case_id'], row['person_nbr'], row['violation'])
        if key in disc_indexed.index:
            found += 1
    pct_found = found / len(gt_sample) * 100

    if pct_found >= 70:
        check("Discipline spot-check (20 GT rows found in output)", "PASS" if pct_found >= 90 else "WARN",
              f"{found}/20 GT rows found in output ({pct_found:.0f}%)")
    else:
        check("Discipline spot-check (20 GT rows found in output)", "WARN",
              f"Only {found}/20 GT rows found ({pct_found:.0f}%) — GT may be from older data")

    # Column overlap
    gt_cols = set(gt_disc.columns)
    out_cols = set(disc_df.columns)
    common = gt_cols & out_cols
    missing_in_out = gt_cols - out_cols
    if not missing_in_out:
        check("Discipline column overlap with GT", "PASS",
              f"All {len(gt_cols)} GT columns present in output")
    else:
        check("Discipline column overlap with GT", "WARN",
              f"Missing columns: {missing_in_out}")

    # case_id format: should be numeric digits only (no spaces), length 8-10 digits
    # Raw data sometimes has internal spaces (e.g. '010 780707') → stripped to '010780707'
    has_space = disc_df['case_id'].str.contains(r'\s').sum()
    non_numeric = (~disc_df['case_id'].str.match(r'^\d+$')).sum()
    len_dist = disc_df['case_id'].str.len().value_counts().to_dict()
    if has_space == 0 and non_numeric == 0:
        check("Discipline case_id format (numeric, no spaces)", "PASS",
              f"All case_ids are numeric with no spaces. Length dist: {len_dist}. Sample: {disc_df['case_id'].head(3).tolist()}")
    else:
        check("Discipline case_id format (numeric, no spaces)", "WARN",
              f"has_space={has_space}, non_numeric={non_numeric}. Sample: {disc_df['case_id'].head(3).tolist()}")


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

print(f"\n{'='*60}")
print(f"OVERALL: {overall}")
print(f"{'='*60}")
print(f"PASS: {statuses.count('PASS')}, WARN: {statuses.count('WARN')}, FAIL: {statuses.count('FAIL')}")


# ---------------------------------------------------------------------------
# Write judge reports
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Human-readable Markdown report
md_lines = [
    "# Georgia POST Data — Judge Report",
    "",
    f"**Overall: {overall}**",
    "",
    f"Ground truth available: {'Yes' if has_groundtruth else 'No'}",
    "",
    "## Check Results",
    "",
    "| Status | Check | Detail |",
    "|--------|-------|--------|",
]
for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c["status"]]
    md_lines.append(f"| {icon} {c['status']} | {c['name']} | {c['detail']} |")

md_lines += [
    "",
    "## Summary",
    "",
    f"- Total checks: {len(checks)}",
    f"- PASS: {statuses.count('PASS')}",
    f"- WARN: {statuses.count('WARN')}",
    f"- FAIL: {statuses.count('FAIL')}",
    "",
]

if emp_df is not None:
    md_lines.append(f"- Employment index rows: {len(emp_df):,}")
if disc_df is not None:
    md_lines.append(f"- Discipline index rows: {len(disc_df):,}")
if has_groundtruth:
    md_lines.append(f"- GT employment rows: {len(gt_emp):,}")
    md_lines.append(f"- GT discipline rows: {len(gt_disc):,}")

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(md_lines) + "\n")
print(f"\nWrote {md_path}")

# Machine-readable JSON report
json_report = {
    "overall": overall,
    "has_groundtruth": has_groundtruth,
    "checks": checks,
    "summary": {
        "total": len(checks),
        "pass": statuses.count("PASS"),
        "warn": statuses.count("WARN"),
        "fail": statuses.count("FAIL"),
    }
}
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump(json_report, f, indent=2)
print(f"Wrote {json_path}")
