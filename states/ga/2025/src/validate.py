#!/usr/bin/env python3
"""
Validation script for GA POST 2025 output.
Compares output CSVs against ground truth and checks schema/format.
Writes:
  - output/judge_report.md
  - output/judge_report.json
"""

import json
import os
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

checks = []   # list of (name, status, message) tuples

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def add_check(name, status, message):
    checks.append({"name": name, "status": status, "message": message})
    symbol = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"  {symbol} [{status}] {name}: {message}")


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
print("\n=== Loading output files ===")

idx_path   = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path  = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

if not os.path.exists(idx_path):
    add_check("employment_index_exists", FAIL, f"Missing file: {idx_path}")
    # Write failing report and exit early
    overall = FAIL
    _write_reports(checks, overall, has_groundtruth=False)
    sys.exit(1)

emp_df = pd.read_csv(idx_path, dtype=str)
print(f"  Employment index loaded: {len(emp_df):,} rows")

disc_exists = os.path.exists(disc_path)
if disc_exists:
    disc_df = pd.read_csv(disc_path, dtype=str)
    print(f"  Discipline index loaded: {len(disc_df):,} rows")
else:
    disc_df = None
    add_check("discipline_index_exists", WARN, f"Discipline index not found: {disc_path}")

# ---------------------------------------------------------------------------
# Check ground truth availability
# ---------------------------------------------------------------------------
gt_emp_path  = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")
has_groundtruth = os.path.exists(gt_emp_path)

print(f"\n  Ground truth available: {has_groundtruth}")

# ---------------------------------------------------------------------------
# SCHEMA CHECKS
# ---------------------------------------------------------------------------
print("\n=== Schema checks ===")

REQUIRED_EMP_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
REQUIRED_DISC_COLS = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date',
                      'case_id', 'violation', 'sanction']

missing_emp = [c for c in REQUIRED_EMP_COLS if c not in emp_df.columns]
if missing_emp:
    add_check("emp_required_columns", FAIL, f"Missing columns: {missing_emp}")
else:
    add_check("emp_required_columns", PASS, f"All required columns present: {REQUIRED_EMP_COLS}")

if disc_df is not None:
    missing_disc = [c for c in REQUIRED_DISC_COLS if c not in disc_df.columns]
    if missing_disc:
        add_check("disc_required_columns", FAIL, f"Missing columns: {missing_disc}")
    else:
        add_check("disc_required_columns", PASS, f"All required discipline columns present")

# ---------------------------------------------------------------------------
# person_nbr FORMAT CHECK
# ---------------------------------------------------------------------------
print("\n=== person_nbr format checks ===")

pnbr = emp_df['person_nbr']
bad_upper = (pnbr != pnbr.str.lower()).sum()
bad_ws    = (pnbr != pnbr.str.strip()).sum()
bad_empty = (pnbr.isna() | (pnbr == '')).sum()

if bad_empty > 0:
    add_check("emp_person_nbr_nonempty", FAIL, f"{bad_empty:,} empty person_nbr values")
else:
    add_check("emp_person_nbr_nonempty", PASS, "No empty person_nbr values")

if bad_upper > 0:
    add_check("emp_person_nbr_lowercase", FAIL, f"{bad_upper:,} person_nbr values not lowercase")
else:
    add_check("emp_person_nbr_lowercase", PASS, "All person_nbr values are lowercase")

if bad_ws > 0:
    add_check("emp_person_nbr_no_whitespace", WARN, f"{bad_ws:,} person_nbr values have leading/trailing whitespace")
else:
    add_check("emp_person_nbr_no_whitespace", PASS, "No leading/trailing whitespace in person_nbr")

# Sample person_nbr format (should look like o123456)
sample_pnbr = pnbr.dropna().head(5).tolist()
ga_format_ok = all(str(p).startswith('o') for p in sample_pnbr if p)
if ga_format_ok:
    add_check("emp_person_nbr_ga_format", PASS, f"person_nbr starts with 'o' as expected (sample: {sample_pnbr[:3]})")
else:
    add_check("emp_person_nbr_ga_format", WARN, f"Unexpected person_nbr format (sample: {sample_pnbr[:3]})")

# ---------------------------------------------------------------------------
# DATE FORMAT CHECKS
# ---------------------------------------------------------------------------
print("\n=== Date format checks ===")

def check_date_col(df, col, label, allow_zero=True):
    """Check that date column contains YYYY-MM-DD, '', or optionally 0000-00-00."""
    vals = df[col].fillna('')
    valid_patterns = {''}
    bad = []
    for v in vals.unique():
        if v == '':
            continue
        if allow_zero and v == '0000-00-00':
            continue
        # Check YYYY-MM-DD
        try:
            pd.to_datetime(v, format='%Y-%m-%d')
        except Exception:
            bad.append(v)
    if bad:
        return WARN, f"{len(bad)} non-standard date values (samples: {bad[:3]})"
    return PASS, f"All {label} values are valid (YYYY-MM-DD or empty)"

# Employment start_date must not be empty
empty_start = (emp_df['start_date'].isna() | (emp_df['start_date'] == '')).sum()
if empty_start > 0:
    add_check("emp_start_date_nonempty", FAIL, f"{empty_start:,} empty start_date values")
else:
    add_check("emp_start_date_nonempty", PASS, "No empty start_date values")

status, msg = check_date_col(emp_df, 'start_date', 'start_date', allow_zero=True)
add_check("emp_start_date_format", status, msg)

status, msg = check_date_col(emp_df, 'end_date', 'end_date', allow_zero=True)
add_check("emp_end_date_format", status, msg)

if disc_df is not None:
    empty_disc_start = (disc_df['start_date'].isna() | (disc_df['start_date'] == '')).sum()
    if empty_disc_start > 0:
        add_check("disc_start_date_nonempty", FAIL, f"{empty_disc_start:,} empty discipline start_date values")
    else:
        add_check("disc_start_date_nonempty", PASS, "No empty discipline start_date values")

    # violation_date: no 0000-00-00 (filtered in clean.py)
    if 'violation_date' in disc_df.columns:
        status, msg = check_date_col(disc_df, 'violation_date', 'violation_date', allow_zero=False)
        add_check("disc_violation_date_format", status, msg)

    # sanction_date: allow 0000-00-00 (GT keeps them for old records)
    if 'sanction_date' in disc_df.columns:
        status, msg = check_date_col(disc_df, 'sanction_date', 'sanction_date', allow_zero=True)
        add_check("disc_sanction_date_format", status, msg)

# ---------------------------------------------------------------------------
# AGENCY NAME CHECKS
# ---------------------------------------------------------------------------
print("\n=== Agency name checks ===")

# Employment index should have agency names WITH code prefix (uppercase, matches GT)
sample_agencies = emp_df['agency_name'].dropna().head(10).tolist()
has_code_prefix = sum(1 for a in sample_agencies if str(a).startswith('G') and len(str(a)) > 5)
if has_code_prefix >= 5:
    add_check("emp_agency_has_code_prefix", PASS, f"Agency names have code prefix as expected (sample: {sample_agencies[:3]})")
else:
    add_check("emp_agency_has_code_prefix", WARN, f"Agency names may be missing code prefix (sample: {sample_agencies[:3]})")

# Check for non-agency values
non_agency_vals = {'application denied', 'application purged', 'pending', 'unknown', 'n/a'}
bad_agency = emp_df['agency_name'].str.lower().isin(non_agency_vals).sum()
if bad_agency > 0:
    add_check("emp_agency_no_noise", WARN, f"{bad_agency:,} non-agency values in agency_name")
else:
    add_check("emp_agency_no_noise", PASS, "No non-agency noise values in agency_name")

# ---------------------------------------------------------------------------
# DUPLICATE CHECK
# ---------------------------------------------------------------------------
print("\n=== Duplicate checks ===")

emp_dupes = emp_df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
if emp_dupes > 0:
    add_check("emp_no_duplicates", WARN, f"{emp_dupes:,} duplicate rows (person_nbr + agency_name + start_date)")
else:
    add_check("emp_no_duplicates", PASS, "No duplicate rows in employment index")

if disc_df is not None and 'case_id' in disc_df.columns:
    disc_dupes = disc_df.duplicated(subset=['case_id', 'person_nbr', 'violation', 'sanction']).sum()
    if disc_dupes > 0:
        add_check("disc_no_duplicates", WARN, f"{disc_dupes:,} duplicate rows in discipline index")
    else:
        add_check("disc_no_duplicates", PASS, "No duplicate rows in discipline index")

# ---------------------------------------------------------------------------
# GROUND TRUTH COMPARISON
# ---------------------------------------------------------------------------
if has_groundtruth:
    print("\n=== Ground truth comparison ===")

    gt_emp  = pd.read_csv(gt_emp_path,  dtype=str)
    gt_disc = pd.read_csv(gt_disc_path, dtype=str) if os.path.exists(gt_disc_path) else None

    # Row count comparison — employment index
    gt_emp_rows  = len(gt_emp)
    out_emp_rows = len(emp_df)
    emp_pct_diff = abs(out_emp_rows - gt_emp_rows) / gt_emp_rows * 100
    msg = f"GT={gt_emp_rows:,} OUT={out_emp_rows:,} diff={out_emp_rows-gt_emp_rows:+,} ({emp_pct_diff:.1f}%)"
    if emp_pct_diff <= 1.0:
        add_check("emp_row_count", PASS, msg)
    elif emp_pct_diff <= 5.0:
        add_check("emp_row_count", WARN, msg)
    else:
        add_check("emp_row_count", WARN, f"Row count diff >5%: {msg}")

    # Row count comparison — discipline index
    if gt_disc is not None and disc_df is not None:
        gt_disc_rows  = len(gt_disc)
        out_disc_rows = len(disc_df)
        disc_pct_diff = abs(out_disc_rows - gt_disc_rows) / gt_disc_rows * 100
        msg = f"GT={gt_disc_rows:,} OUT={out_disc_rows:,} diff={out_disc_rows-gt_disc_rows:+,} ({disc_pct_diff:.1f}%)"
        if disc_pct_diff <= 5.0:
            add_check("disc_row_count", PASS, msg)
        elif disc_pct_diff <= 20.0:
            add_check("disc_row_count", WARN, msg)
        else:
            add_check("disc_row_count", WARN, f"Row count diff >20%: {msg}")

    # Column presence match
    gt_emp_cols  = set(gt_emp.columns)
    out_emp_cols = set(emp_df.columns)
    extra   = out_emp_cols - gt_emp_cols
    missing = gt_emp_cols - out_emp_cols
    if not extra and not missing:
        add_check("emp_column_match", PASS, "Output columns match ground truth exactly")
    else:
        msg_parts = []
        if missing: msg_parts.append(f"missing: {sorted(missing)}")
        if extra:   msg_parts.append(f"extra: {sorted(extra)}")
        add_check("emp_column_match", WARN, "; ".join(msg_parts))

    # Value spot-checks on employment index
    # Check first few rows match by person_nbr
    gt_emp_sorted  = gt_emp.sort_values('person_nbr').head(20)
    out_emp_sorted = emp_df.sort_values('person_nbr').head(20)

    # Spot-check: merge on person_nbr + agency_name + start_date
    common_key = ['person_nbr', 'agency_name', 'start_date']
    gt_sample = gt_emp.head(100).set_index(common_key)
    out_sample = emp_df.head(100).set_index(common_key)

    shared_idx = gt_sample.index.intersection(out_sample.index)
    match_rate = len(shared_idx) / len(gt_sample) * 100 if len(gt_sample) > 0 else 0
    if match_rate >= 90:
        add_check("emp_value_spot_check", PASS, f"{match_rate:.0f}% of sample rows match GT on (person_nbr, agency, start_date)")
    elif match_rate >= 70:
        add_check("emp_value_spot_check", WARN, f"Only {match_rate:.0f}% of sample rows match GT on key columns")
    else:
        add_check("emp_value_spot_check", WARN, f"Low match rate: {match_rate:.0f}% of sample rows match GT")

    # Name format check: GT has lowercase last_name
    if 'last_name' in gt_emp.columns and 'last_name' in emp_df.columns:
        gt_upper = (gt_emp['last_name'].dropna() != gt_emp['last_name'].dropna().str.lower()).sum()
        out_upper = (emp_df['last_name'].dropna() != emp_df['last_name'].dropna().str.lower()).sum()
        if out_upper == 0:
            add_check("emp_last_name_lowercase", PASS, "last_name is lowercase (matches GT convention)")
        else:
            add_check("emp_last_name_lowercase", WARN, f"{out_upper:,} last_name values are not lowercase")

    # Discipline value spot-check
    if gt_disc is not None and disc_df is not None:
        disc_key = ['case_id', 'person_nbr', 'violation', 'sanction']
        if all(c in disc_df.columns for c in disc_key) and all(c in gt_disc.columns for c in disc_key):
            gt_disc_keys = set(zip(gt_disc['case_id'], gt_disc['person_nbr'],
                                   gt_disc['violation'], gt_disc['sanction']))
            out_disc_keys = set(zip(disc_df['case_id'], disc_df['person_nbr'],
                                    disc_df['violation'], disc_df['sanction']))
            overlap = len(gt_disc_keys & out_disc_keys)
            coverage = overlap / len(gt_disc_keys) * 100 if gt_disc_keys else 0
            add_check("disc_key_coverage",
                      PASS if coverage >= 85 else WARN,
                      f"{coverage:.1f}% of GT discipline (case,person,viol,sanc) tuples found in output "
                      f"({overlap:,}/{len(gt_disc_keys):,})")

else:
    print("\n=== No ground truth — skipping comparison checks ===")
    add_check("no_groundtruth", WARN, "Ground truth not available; skipping comparison checks")

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print("\n=== Summary ===")

status_counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
for c in checks:
    status_counts[c["status"]] += 1

print(f"  PASS: {status_counts['PASS']}  WARN: {status_counts['WARN']}  FAIL: {status_counts['FAIL']}")

if status_counts["FAIL"] > 0:
    overall = FAIL
elif status_counts["WARN"] > 0:
    overall = WARN
else:
    overall = PASS

print(f"  Overall: {overall}")


# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
def write_reports(checks_list, overall_status, has_gt):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- Markdown ---
    md_lines = [
        "# GA POST 2025 — Validation Report\n",
        f"**Overall: {overall_status}**\n",
        f"**Ground truth available: {has_gt}**\n",
        "\n## Check Results\n",
        "| Check | Status | Message |",
        "|-------|--------|---------|",
    ]
    for c in checks_list:
        symbol = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c["status"]]
        md_lines.append(f"| {c['name']} | {symbol} {c['status']} | {c['message']} |")

    md_lines.append("\n## Row Counts\n")
    md_lines.append(f"- Employment index: {len(emp_df):,} rows")
    if disc_df is not None:
        md_lines.append(f"- Discipline index: {len(disc_df):,} rows")

    md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"\nWrote {md_path}")

    # --- JSON ---
    json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
    with open(json_path, "w") as f:
        json.dump({
            "overall": overall_status,
            "has_groundtruth": has_gt,
            "checks": checks_list,
            "row_counts": {
                "employment_index": len(emp_df),
                "discipline_index": len(disc_df) if disc_df is not None else None,
            }
        }, f, indent=2)
    print(f"Wrote {json_path}")


write_reports(checks, overall, has_groundtruth)
print(f"\nValidation complete — {overall}")
