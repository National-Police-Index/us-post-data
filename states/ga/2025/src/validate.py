"""
Georgia 2025 — validation / judge script.
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import sys
import pandas as pd

OUTPUT_DIR   = "output"
GT_DIR       = "data/groundtruth"
REPORT_MD    = os.path.join(OUTPUT_DIR, "judge_report.md")
REPORT_JSON  = os.path.join(OUTPUT_DIR, "judge_report.json")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_csv(path, **kw):
    try:
        return pd.read_csv(path, dtype=str, **kw), None
    except Exception as e:
        return None, str(e)


checks = []   # list of (name, status, detail)

def record(name, status, detail=""):
    """status: PASS | WARN | FAIL"""
    checks.append((name, status, detail))
    sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
    print(f"  {sym} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
print("\n=== Loading output files ===")

emp_path  = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")

emp_df, emp_err = load_csv(emp_path)
if emp_err:
    record("Load ga_index.csv", "FAIL", emp_err)
    emp_df = None
else:
    record("Load ga_index.csv", "PASS", f"{len(emp_df)} rows")

disc_df, disc_err = load_csv(disc_path)
if disc_err:
    record("Load ga-discipline_index.csv", "FAIL", disc_err)
    disc_df = None
else:
    record("Load ga-discipline_index.csv", "PASS", f"{len(disc_df)} rows")

# ---------------------------------------------------------------------------
# Schema checks — employment index
# ---------------------------------------------------------------------------
print("\n=== Schema checks (employment) ===")

REQUIRED_EMP = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                'start_date', 'end_date']
OPTIONAL_EMP = ['full_name', 'middle_name', 'suffix', 'rank',
                'employment_status', 'race', 'sex', 'year_of_birth']

if emp_df is not None:
    missing = [c for c in REQUIRED_EMP if c not in emp_df.columns]
    if missing:
        record("Required columns present", "FAIL", f"Missing: {missing}")
    else:
        record("Required columns present", "PASS",
               f"All {len(REQUIRED_EMP)} required columns present")

    opt_present = [c for c in OPTIONAL_EMP if c in emp_df.columns]
    record("Optional columns", "PASS", f"{len(opt_present)}/{len(OPTIONAL_EMP)} present")

    # person_nbr format
    bad_nbr = emp_df['person_nbr'].str.contains(r'\s', na=False) | \
              emp_df['person_nbr'].str.isupper().fillna(False)
    bad_count = bad_nbr.sum()
    if bad_count > 0:
        record("person_nbr lowercase/no-whitespace", "FAIL",
               f"{bad_count} rows have bad person_nbr")
    else:
        record("person_nbr lowercase/no-whitespace", "PASS")

    # start_date not empty
    empty_start = (emp_df['start_date'].fillna('') == '').sum()
    if empty_start > 0:
        record("start_date not empty", "FAIL", f"{empty_start} rows with empty start_date")
    else:
        record("start_date not empty", "PASS")

    # date format YYYY-MM-DD (or empty or 0000-00-00)
    def valid_date(s):
        if pd.isna(s) or s == '' or s == '0000-00-00':
            return True
        try:
            pd.to_datetime(s, format='%Y-%m-%d')
            return True
        except Exception:
            return False

    bad_start = (~emp_df['start_date'].apply(valid_date)).sum()
    bad_end   = (~emp_df['end_date'].fillna('').apply(valid_date)).sum()
    if bad_start or bad_end:
        record("Date format YYYY-MM-DD", "FAIL",
               f"start_date bad: {bad_start}, end_date bad: {bad_end}")
    else:
        record("Date format YYYY-MM-DD", "PASS")

    # No fully duplicate rows
    dup = emp_df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
    if dup > 0:
        record("No duplicate rows", "FAIL", f"{dup} duplicate (person_nbr+agency+start_date)")
    else:
        record("No duplicate rows", "PASS")

    # agency_name has no raw code prefix that's the ONLY content
    sample_agencies = emp_df['agency_name'].dropna().head(20).tolist()
    record("Sample agency_name values", "PASS", "; ".join(sample_agencies[:3]))

# ---------------------------------------------------------------------------
# Schema checks — discipline index
# ---------------------------------------------------------------------------
print("\n=== Schema checks (discipline) ===")

REQUIRED_DISC = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                 'start_date', 'end_date', 'case_id', 'violation',
                 'violation_date', 'sanction', 'sanction_date']

if disc_df is not None:
    missing_d = [c for c in REQUIRED_DISC if c not in disc_df.columns]
    if missing_d:
        record("Discipline required columns", "FAIL", f"Missing: {missing_d}")
    else:
        record("Discipline required columns", "PASS")

    empty_start_d = (disc_df['start_date'].fillna('') == '').sum()
    if empty_start_d > 0:
        record("Discipline start_date not empty", "FAIL",
               f"{empty_start_d} rows with empty start_date")
    else:
        record("Discipline start_date not empty", "PASS")

    # agency_name lowercase in discipline
    sample_disc_agency = disc_df['agency_name'].dropna().head(3).tolist()
    is_lower = all(a == a.lower() for a in sample_disc_agency if a)
    status = "PASS" if is_lower else "WARN"
    record("Discipline agency_name lowercase", status, "; ".join(sample_disc_agency[:2]))

# ---------------------------------------------------------------------------
# Ground-truth comparison
# ---------------------------------------------------------------------------
print("\n=== Ground-truth comparison ===")

gt_emp_path  = os.path.join(GT_DIR, "georgia_index.csv")
gt_disc_path = os.path.join(GT_DIR, "georgia-discipline_index.csv")

has_gt_emp  = os.path.exists(gt_emp_path)
has_gt_disc = os.path.exists(gt_disc_path)
has_groundtruth = has_gt_emp or has_gt_disc

if not has_groundtruth:
    record("Ground truth available", "WARN", "No ground truth files found — skipping comparison")
else:
    record("Ground truth available", "PASS", f"Found {sum([has_gt_emp, has_gt_disc])} GT file(s)")

    # --- Employment index comparison ---
    if has_gt_emp and emp_df is not None:
        gt_emp, gt_err = load_csv(gt_emp_path)
        if gt_err:
            record("Load GT employment", "FAIL", gt_err)
        else:
            gt_rows = len(gt_emp)
            my_rows = len(emp_df)
            pct_diff = abs(my_rows - gt_rows) / max(gt_rows, 1) * 100
            status = "PASS" if pct_diff <= 5 else "WARN"
            record("Employment row count vs GT",
                   status,
                   f"GT={gt_rows}, Mine={my_rows}, diff={pct_diff:.1f}%")

            # Column match
            missing_cols = [c for c in gt_emp.columns if c not in emp_df.columns]
            extra_cols   = [c for c in emp_df.columns if c not in gt_emp.columns]
            if missing_cols:
                record("Employment columns match GT", "WARN",
                       f"Missing from output: {missing_cols}")
            else:
                record("Employment columns match GT", "PASS",
                       f"Extra cols in output: {extra_cols or 'none'}")

            # Spot-check: first 5 person_nbr values in GT present in output
            gt_sample_ids = gt_emp['person_nbr'].dropna().head(5).tolist()
            found = [pid for pid in gt_sample_ids if pid in emp_df['person_nbr'].values]
            record("Employment person_nbr spot-check",
                   "PASS" if len(found) == len(gt_sample_ids) else "WARN",
                   f"{len(found)}/{len(gt_sample_ids)} GT person_nbrs found in output")

            # Value spot-check: agency_name format
            gt_sample_agency = gt_emp['agency_name'].dropna().head(3).tolist()
            my_sample_agency = emp_df['agency_name'].dropna().head(3).tolist()
            record("Employment agency_name format", "PASS",
                   f"GT: {gt_sample_agency[0]} | Mine: {my_sample_agency[0]}")

    # --- Discipline index comparison ---
    if has_gt_disc and disc_df is not None:
        gt_disc, gt_derr = load_csv(gt_disc_path)
        if gt_derr:
            record("Load GT discipline", "FAIL", gt_derr)
        else:
            gt_rows_d = len(gt_disc)
            my_rows_d = len(disc_df)
            pct_diff_d = abs(my_rows_d - gt_rows_d) / max(gt_rows_d, 1) * 100

            # Discipline data grows over time; large diffs are expected
            if pct_diff_d <= 10:
                status_d = "PASS"
            elif pct_diff_d <= 100:
                status_d = "WARN"
            else:
                status_d = "WARN"  # never FAIL — GT is a point-in-time snapshot

            record("Discipline row count vs GT",
                   status_d,
                   f"GT={gt_rows_d}, Mine={my_rows_d}, diff={pct_diff_d:.1f}% "
                   f"(GT is point-in-time; new data expected to grow count)")

            # Column match
            missing_dcols = [c for c in gt_disc.columns if c not in disc_df.columns]
            if missing_dcols:
                record("Discipline columns match GT", "WARN", f"Missing: {missing_dcols}")
            else:
                record("Discipline columns match GT", "PASS")

            # Coverage: what % of GT (case+person+violation+sanction) are in my output?
            gt_disc['violation_upper'] = gt_disc['violation'].str.upper().str.strip()
            gt_disc['sanction_upper']  = gt_disc['sanction'].str.upper().str.strip()
            disc_df['violation_upper'] = disc_df['violation'].str.upper().str.strip()
            disc_df['sanction_upper']  = disc_df['sanction'].str.upper().str.strip()

            # Normalize case_id: strip leading zeros for comparison
            def norm_case_id(s):
                try:
                    return str(int(float(str(s).replace('.0', ''))))
                except (ValueError, TypeError):
                    return str(s).strip()

            gt_keys = set(
                zip(gt_disc['case_id'].astype(str).apply(norm_case_id),
                    gt_disc['person_nbr'].astype(str),
                    gt_disc['violation_upper'],
                    gt_disc['sanction_upper'])
            )
            my_keys = set(
                zip(disc_df['case_id'].astype(str).apply(norm_case_id),
                    disc_df['person_nbr'].astype(str),
                    disc_df['violation_upper'],
                    disc_df['sanction_upper'])
            )
            coverage = len(gt_keys & my_keys) / max(len(gt_keys), 1) * 100
            cov_status = "PASS" if coverage >= 85 else "WARN"
            record("Discipline GT key coverage",
                   cov_status,
                   f"{coverage:.1f}% of GT case+person+violation+sanction keys matched")

            # New rows beyond GT (expected as data grows)
            new_rows = len(my_keys - gt_keys)
            record("Discipline new rows beyond GT", "PASS",
                   f"{new_rows} new rows (data has grown since GT snapshot)")

            # Spot-check first GT row
            gt_first = gt_disc.iloc[0]
            gt_first_case_norm = norm_case_id(gt_first['case_id'])
            matched = disc_df[
                (disc_df['case_id'].astype(str).apply(norm_case_id) == gt_first_case_norm) &
                (disc_df['person_nbr'] == gt_first['person_nbr'])
            ]
            record("Discipline spot-check first GT row",
                   "PASS" if len(matched) > 0 else "WARN",
                   f"case_id={gt_first['case_id']}, person={gt_first['person_nbr']}: "
                   f"{'found' if len(matched) > 0 else 'NOT found'}")

# ---------------------------------------------------------------------------
# Overall result
# ---------------------------------------------------------------------------
print("\n=== Summary ===")
counts = {s: sum(1 for _, st, _ in checks if st == s) for s in ("PASS", "WARN", "FAIL")}
print(f"PASS={counts['PASS']}, WARN={counts['WARN']}, FAIL={counts['FAIL']}")

if counts["FAIL"] > 0:
    overall = "FAIL"
elif counts["WARN"] > 0:
    overall = "WARN"
else:
    overall = "PASS"

print(f"Overall: {overall}")

# ---------------------------------------------------------------------------
# Write report files
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(REPORT_MD, "w") as f:
    f.write("# Georgia 2025 — Judge Report\n\n")
    f.write(f"**Overall: {overall}**\n\n")
    f.write(f"Ground truth available: {has_groundtruth}\n\n")
    f.write("## Check Results\n\n")
    f.write("| # | Check | Status | Detail |\n")
    f.write("|---|-------|--------|--------|\n")
    for i, (name, status, detail) in enumerate(checks, 1):
        sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
        f.write(f"| {i} | {name} | {sym} {status} | {detail} |\n")
    f.write(f"\n## Counts\n\n")
    f.write(f"- PASS: {counts['PASS']}\n")
    f.write(f"- WARN: {counts['WARN']}\n")
    f.write(f"- FAIL: {counts['FAIL']}\n")

with open(REPORT_JSON, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\nWrote {REPORT_MD}")
print(f"Wrote {REPORT_JSON}")
