"""
Validation script for Arizona POST employment index — 2025
Writes output/judge_report.md and output/judge_report.json
"""

import csv
import json
import os
import re
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Paths (run from states/az/2025/)
# ---------------------------------------------------------------------------
OUTPUT_DIR      = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
OUTPUT_FILE     = os.path.join(OUTPUT_DIR, "az_index.csv")
GT_FILE         = os.path.join(GROUNDTRUTH_DIR, "arizona_index.csv")
REPORT_MD       = os.path.join(OUTPUT_DIR, "judge_report.md")
REPORT_JSON     = os.path.join(OUTPUT_DIR, "judge_report.json")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def load_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def is_valid_date(s):
    """Return True if s is YYYY-MM-DD or empty string."""
    if s == '':
        return True
    try:
        datetime.strptime(s, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def parse_gt_date(s):
    """Parse groundtruth date (M/D/YY or M/D/YYYY) → YYYY-MM-DD or ''."""
    s = str(s).strip()
    if not s:
        return ''
    for fmt in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return ''


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_file_exists(checks):
    ok = os.path.isfile(OUTPUT_FILE)
    checks.append({
        'name': 'output_file_exists',
        'status': 'PASS' if ok else 'FAIL',
        'detail': f"{OUTPUT_FILE} {'found' if ok else 'NOT FOUND'}",
    })
    return ok


def check_schema(rows, checks):
    required = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                'start_date', 'end_date']
    if not rows:
        checks.append({'name': 'schema', 'status': 'FAIL', 'detail': 'No rows'})
        return
    cols = list(rows[0].keys())
    missing = [c for c in required if c not in cols]
    status = 'FAIL' if missing else 'PASS'
    checks.append({
        'name': 'schema_required_columns',
        'status': status,
        'detail': f"Missing: {missing}" if missing else f"All required columns present: {required}",
    })


def check_person_nbr(rows, checks):
    bad = [r['person_nbr'] for r in rows
           if r['person_nbr'] != r['person_nbr'].lower().strip()
           or not r['person_nbr']]
    status = 'FAIL' if bad else 'PASS'
    checks.append({
        'name': 'person_nbr_format',
        'status': status,
        'detail': (f"{len(bad)} bad person_nbr values (e.g. {bad[:3]})"
                   if bad else "All person_nbr values are lowercase and non-empty"),
    })


def check_dates(rows, checks):
    bad_start = [i for i, r in enumerate(rows) if not is_valid_date(r.get('start_date', ''))]
    bad_end   = [i for i, r in enumerate(rows) if not is_valid_date(r.get('end_date', ''))]
    empty_start = [i for i, r in enumerate(rows) if r.get('start_date', '') == '']

    status = 'FAIL' if bad_start or bad_end or empty_start else 'PASS'
    details = []
    if bad_start:
        details.append(f"{len(bad_start)} rows with invalid start_date format")
    if bad_end:
        details.append(f"{len(bad_end)} rows with invalid end_date format")
    if empty_start:
        details.append(f"{len(empty_start)} rows with empty start_date (must be 0)")
    if not details:
        details.append("All date values are valid YYYY-MM-DD or empty")

    checks.append({
        'name': 'date_format',
        'status': status,
        'detail': '; '.join(details),
    })


def check_no_duplicates(rows, checks):
    seen = set()
    dupes = 0
    for r in rows:
        key = (r.get('person_nbr',''), r.get('agency_name',''), r.get('start_date',''))
        if key in seen:
            dupes += 1
        seen.add(key)
    status = 'WARN' if dupes > 0 else 'PASS'
    checks.append({
        'name': 'no_duplicate_rows',
        'status': status,
        'detail': (f"{dupes} duplicate (person_nbr, agency_name, start_date) rows"
                   if dupes else "No duplicate rows"),
    })


def check_agency_names(rows, checks):
    """Check for agency code prefixes and non-agency values."""
    code_pattern = re.compile(r'^[A-Z]\d{3,}\s+')
    non_agency = {'application denied', 'application purged', 'pending',
                  'unknown', 'n/a', ''}
    bad_codes = [r['agency_name'] for r in rows
                 if code_pattern.match(r.get('agency_name', ''))]
    bad_vals  = [r['agency_name'] for r in rows
                 if r.get('agency_name', '').lower().strip() in non_agency]
    status = 'FAIL' if bad_codes or bad_vals else 'PASS'
    details = []
    if bad_codes:
        details.append(f"{len(bad_codes)} agency names still have code prefixes (e.g. {bad_codes[:2]})")
    if bad_vals:
        details.append(f"{len(bad_vals)} rows with non-agency values")
    if not details:
        details.append("Agency names look clean")
    checks.append({
        'name': 'agency_name_quality',
        'status': status,
        'detail': '; '.join(details),
    })


def check_row_count(rows, checks):
    n = len(rows)
    checks.append({
        'name': 'row_count',
        'status': 'PASS',
        'detail': f"{n:,} rows in output",
    })


# ---------------------------------------------------------------------------
# Groundtruth comparison
# ---------------------------------------------------------------------------

def check_groundtruth(rows, checks):
    if not os.path.isfile(GT_FILE):
        checks.append({
            'name': 'groundtruth_comparison',
            'status': 'SKIP',
            'detail': 'No groundtruth file found',
        })
        return False

    gt_rows = load_csv(GT_FILE)
    print(f"  Groundtruth: {len(gt_rows):,} rows; Output: {len(rows):,} rows")

    # Row count comparison
    diff = abs(len(rows) - len(gt_rows))
    pct  = diff / max(len(gt_rows), 1) * 100
    rc_status = 'PASS' if pct <= 5 else 'WARN'
    checks.append({
        'name': 'groundtruth_row_count',
        'status': rc_status,
        'detail': (f"Output {len(rows):,} rows vs groundtruth {len(gt_rows):,} rows "
                   f"(diff {diff:,}, {pct:.1f}%)"),
    })

    # Spot-check: build index from output keyed by (person_nbr, agency_name_lower)
    # Groundtruth uses person_nbr as plain numeric string and lower-case agency names
    out_index = {}
    for r in rows:
        key = (r['person_nbr'].strip(), r['agency_name'].lower().strip())
        if key not in out_index:
            out_index[key] = r

    # Compare a sample of groundtruth rows
    matched = 0
    mismatched_names = 0
    mismatched_dates = 0
    checked = 0
    sample_mismatches = []

    for gt in gt_rows:
        gt_nbr    = str(gt.get('person_nbr', '')).strip()
        gt_agency = gt.get('agency_name', '').lower().strip()
        key = (gt_nbr, gt_agency)
        if key not in out_index:
            continue
        checked += 1
        out = out_index[key]

        # Compare first/last name (case-insensitive)
        gt_first = gt.get('first_name', '').strip().lower()
        gt_last  = gt.get('last_name', '').strip().lower()
        out_first = out.get('first_name', '').strip().lower()
        out_last  = out.get('last_name', '').strip().lower()

        name_ok = (gt_first == out_first and gt_last == out_last)
        if not name_ok:
            mismatched_names += 1
            if len(sample_mismatches) < 3:
                sample_mismatches.append(
                    f"person_nbr={gt_nbr}: GT=({gt_first},{gt_last}) "
                    f"OUT=({out_first},{out_last})"
                )

        # Compare start_date (parse GT's M/D/YY format)
        gt_start  = parse_gt_date(gt.get('start_date', ''))
        out_start = out.get('start_date', '').strip()
        date_ok = (gt_start == out_start) or (not gt_start and not out_start)
        if not date_ok:
            mismatched_dates += 1

        if name_ok and date_ok:
            matched += 1

    if checked == 0:
        checks.append({
            'name': 'groundtruth_value_spot_check',
            'status': 'WARN',
            'detail': 'No matching keys found between output and groundtruth',
        })
    else:
        name_pct = mismatched_names / checked * 100
        date_pct = mismatched_dates / checked * 100
        status = 'PASS'
        if name_pct > 10 or date_pct > 10:
            status = 'WARN'
        if name_pct > 30 or date_pct > 30:
            status = 'FAIL'
        detail = (f"Checked {checked:,} matching keys: "
                  f"{mismatched_names} name mismatches ({name_pct:.1f}%), "
                  f"{mismatched_dates} date mismatches ({date_pct:.1f}%)")
        if sample_mismatches:
            detail += f"; e.g. {sample_mismatches[0]}"
        checks.append({
            'name': 'groundtruth_value_spot_check',
            'status': status,
            'detail': detail,
        })

    return True


# ---------------------------------------------------------------------------
# Determine overall result
# ---------------------------------------------------------------------------

def overall_status(checks):
    statuses = [c['status'] for c in checks]
    if 'FAIL' in statuses:
        return 'FAIL'
    if 'WARN' in statuses:
        return 'WARN'
    return 'PASS'


# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------

def write_reports(checks, has_gt):
    status = overall_status(checks)

    # --- Markdown ---
    lines = [
        "# Arizona POST Employment Index — Validation Report",
        "",
        f"**Overall: {status}**  ",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"Ground truth available: {'Yes' if has_gt else 'No'}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for c in checks:
        lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")

    lines += ["", "## Summary", ""]
    pass_n = sum(1 for c in checks if c['status'] == 'PASS')
    warn_n = sum(1 for c in checks if c['status'] == 'WARN')
    fail_n = sum(1 for c in checks if c['status'] == 'FAIL')
    lines.append(f"- PASS: {pass_n}  WARN: {warn_n}  FAIL: {fail_n}")

    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    # --- JSON ---
    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump({"overall": status, "has_groundtruth": has_gt}, f, indent=2)
        f.write('\n')

    print(f"\nValidation complete: {status}")
    print(f"  Report written to {REPORT_MD}")
    print(f"  JSON written to   {REPORT_JSON}")
    return status


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    checks = []

    # File exists?
    if not check_file_exists(checks):
        write_reports(checks, has_gt=False)
        sys.exit(1)

    rows = load_csv(OUTPUT_FILE)
    print(f"Loaded {len(rows):,} rows from {OUTPUT_FILE}")

    check_schema(rows, checks)
    check_row_count(rows, checks)
    check_person_nbr(rows, checks)
    check_dates(rows, checks)
    check_no_duplicates(rows, checks)
    check_agency_names(rows, checks)
    has_gt = check_groundtruth(rows, checks)

    status = write_reports(checks, has_gt=has_gt)
    sys.exit(0 if status in ('PASS', 'WARN') else 1)


if __name__ == "__main__":
    main()
