"""
Validation script for GA 2025 POST data cleaning.
Writes output/judge_report.md and output/judge_report.json.
"""

import os
import json
import csv
import re
from collections import defaultdict

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

results = []   # list of (check_name, status, message)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check(name, passed, warn=False, message=""):
    status = "PASS" if passed else ("WARN" if warn else "FAIL")
    results.append((name, status, message))
    print(f"  [{status}] {name}: {message}")
    return passed


def load_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def count_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return sum(1 for _ in f) - 1  # subtract header


# ---------------------------------------------------------------------------
# File existence checks
# ---------------------------------------------------------------------------
print("=== File existence ===")

emp_path  = os.path.join(OUTPUT_DIR, "ga_index.csv")
disc_path = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
gt_emp    = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
gt_disc   = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

has_emp  = os.path.exists(emp_path)
has_disc = os.path.exists(disc_path)
has_gt_emp  = os.path.exists(gt_emp)
has_gt_disc = os.path.exists(gt_disc)
has_groundtruth = has_gt_emp or has_gt_disc

check("employment_index_exists",  has_emp,  message=emp_path)
check("discipline_index_exists",  has_disc, message=disc_path)

# ---------------------------------------------------------------------------
# Schema checks — employment index
# ---------------------------------------------------------------------------
print("\n=== Schema checks — employment index ===")

REQUIRED_EMP = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
OPTIONAL_EMP = ['full_name', 'middle_name', 'suffix', 'rank', 'employment_status',
                'race', 'sex', 'year_of_birth']

if has_emp:
    emp_rows = load_csv(emp_path)
    emp_cols = list(emp_rows[0].keys()) if emp_rows else []

    for col in REQUIRED_EMP:
        check(f"emp_col_{col}", col in emp_cols,
              message=f"column {'present' if col in emp_cols else 'MISSING'}")

    opt_present = [c for c in OPTIONAL_EMP if c in emp_cols]
    check("emp_optional_cols", len(opt_present) >= 4, warn=True,
          message=f"{len(opt_present)}/{len(OPTIONAL_EMP)} optional cols present")

# ---------------------------------------------------------------------------
# Schema checks — discipline index
# ---------------------------------------------------------------------------
print("\n=== Schema checks — discipline index ===")

REQUIRED_DISC = ['person_nbr', 'first_name', 'last_name', 'agency_name',
                 'start_date', 'end_date', 'case_id', 'violation', 'sanction']

if has_disc:
    disc_rows = load_csv(disc_path)
    disc_cols = list(disc_rows[0].keys()) if disc_rows else []

    for col in REQUIRED_DISC:
        check(f"disc_col_{col}", col in disc_cols,
              message=f"column {'present' if col in disc_cols else 'MISSING'}")

# ---------------------------------------------------------------------------
# Row count checks
# ---------------------------------------------------------------------------
print("\n=== Row count checks ===")

if has_emp:
    emp_count = len(emp_rows)
    check("emp_row_count_positive", emp_count > 0, message=f"{emp_count} rows")

if has_disc:
    disc_count = len(disc_rows)
    check("disc_row_count_positive", disc_count > 0, message=f"{disc_count} rows")

# ---------------------------------------------------------------------------
# person_nbr format checks
# ---------------------------------------------------------------------------
print("\n=== person_nbr format ===")

if has_emp and emp_rows:
    pnbr_bad = [r['person_nbr'] for r in emp_rows
                if r.get('person_nbr', '') != r.get('person_nbr', '').lower().strip()
                or not r.get('person_nbr', '').strip()]
    check("emp_person_nbr_lowercase_nospace", len(pnbr_bad) == 0,
          message=f"{len(pnbr_bad)} bad person_nbr values")

    # Should start with a lowercase letter (GA uses 'o' or 'c' prefix)
    pnbr_prefix_bad = [r['person_nbr'] for r in emp_rows[:100]
                       if not re.match(r'^[a-z]\d+', r.get('person_nbr', ''))]
    check("emp_person_nbr_has_letter_prefix", len(pnbr_prefix_bad) == 0,
          message=f"{len(pnbr_prefix_bad)}/100 sampled don't have lowercase letter+digit prefix")

if has_disc and disc_rows:
    dpnbr_bad = [r['person_nbr'] for r in disc_rows
                 if r.get('person_nbr', '') != r.get('person_nbr', '').lower().strip()
                 or not r.get('person_nbr', '').strip()]
    check("disc_person_nbr_lowercase_nospace", len(dpnbr_bad) == 0,
          message=f"{len(dpnbr_bad)} bad person_nbr values")

# ---------------------------------------------------------------------------
# start_date non-empty check
# ---------------------------------------------------------------------------
print("\n=== start_date checks ===")

if has_emp and emp_rows:
    empty_start = [r for r in emp_rows if not r.get('start_date', '').strip()]
    check("emp_no_empty_start_date", len(empty_start) == 0,
          message=f"{len(empty_start)} rows with empty start_date")

if has_disc and disc_rows:
    empty_start_d = [r for r in disc_rows if not r.get('start_date', '').strip()]
    check("disc_no_empty_start_date", len(empty_start_d) == 0,
          message=f"{len(empty_start_d)} rows with empty start_date")

# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------
print("\n=== Date format checks ===")

DATE_PAT = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def check_dates(rows, col, name, allow_zero=True):
    bad = []
    for r in rows:
        v = r.get(col, '')
        if not v:
            continue
        if allow_zero and v == '0000-00-00':
            continue
        if not DATE_PAT.match(v):
            bad.append(v)
    pct = len(bad) / max(len(rows), 1)
    passed = pct < 0.01
    check(f"{name}_{col}_format", passed, warn=(not passed),
          message=f"{len(bad)} bad dates ({pct:.1%})" if bad else "OK")

if has_emp and emp_rows:
    check_dates(emp_rows, 'start_date', 'emp')
    check_dates(emp_rows, 'end_date', 'emp')

if has_disc and disc_rows:
    check_dates(disc_rows, 'start_date', 'disc')
    check_dates(disc_rows, 'end_date', 'disc')
    check_dates(disc_rows, 'violation_date', 'disc', allow_zero=True)
    check_dates(disc_rows, 'sanction_date', 'disc')

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------
print("\n=== Duplicate checks ===")

if has_emp and emp_rows:
    seen = set()
    dupes = 0
    for r in emp_rows:
        key = (r.get('person_nbr'), r.get('agency_name'), r.get('start_date'))
        if key in seen:
            dupes += 1
        seen.add(key)
    check("emp_no_duplicate_rows", dupes == 0,
          message=f"{dupes} duplicate (person_nbr, agency_name, start_date) combos")

if has_disc and disc_rows:
    seen = set()
    dupes = 0
    for r in disc_rows:
        key = (r.get('case_id'), r.get('person_nbr'), r.get('violation'))
        if key in seen:
            dupes += 1
        seen.add(key)
    check("disc_no_duplicate_rows", dupes == 0,
          message=f"{dupes} duplicate (case_id, person_nbr, violation) combos")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
print("\n=== Ground truth comparison ===")

if has_gt_emp and has_emp:
    gt_emp_count = count_csv(gt_emp)
    pct_diff = abs(emp_count - gt_emp_count) / max(gt_emp_count, 1)
    check("emp_row_count_vs_groundtruth",
          pct_diff <= 0.10, warn=(0.05 < pct_diff <= 0.10),
          message=f"output={emp_count}, groundtruth={gt_emp_count}, diff={pct_diff:.1%}")

    # Spot-check first 100 rows for person_nbr match
    gt_emp_rows = load_csv(gt_emp)
    gt_pnbrs = {r['person_nbr'] for r in gt_emp_rows[:500]}
    out_pnbrs = {r['person_nbr'] for r in emp_rows[:500]}
    overlap = len(gt_pnbrs & out_pnbrs) / max(len(gt_pnbrs), 1)
    check("emp_person_nbr_overlap_first500", overlap >= 0.90,
          warn=(0.80 <= overlap < 0.90),
          message=f"{overlap:.1%} of first-500 gt person_nbrs in output")

    # Value spot-check on first matching person_nbr
    gt_map = {r['person_nbr']: r for r in gt_emp_rows[:200]}
    out_map = {r['person_nbr']: r for r in emp_rows[:200]}
    matched = 0
    mismatch_agency = 0
    for pnbr in list(gt_map.keys())[:100]:
        if pnbr in out_map:
            matched += 1
            gt_r = gt_map[pnbr]
            out_r = out_map[pnbr]
            if gt_r.get('agency_name', '').strip() != out_r.get('agency_name', '').strip():
                mismatch_agency += 1
    check("emp_agency_name_spot_check", mismatch_agency == 0,
          warn=(mismatch_agency > 0),
          message=f"{mismatch_agency}/{matched} agency_name mismatches in first 100 matched rows")

if has_gt_disc and has_disc:
    gt_disc_count = count_csv(gt_disc)
    pct_diff_d = abs(disc_count - gt_disc_count) / max(gt_disc_count, 1)
    # Discipline data grows significantly as new cases are added — always WARN not FAIL
    check("disc_row_count_vs_groundtruth",
          pct_diff_d <= 0.10, warn=True,
          message=f"output={disc_count}, groundtruth={gt_disc_count}, diff={pct_diff_d:.1%} (data may have grown since snapshot)")

    # Spot-check: case_ids from groundtruth should appear in output
    gt_disc_rows = load_csv(gt_disc)
    gt_cases = {r['case_id'] for r in gt_disc_rows[:200]}
    out_cases = {r['case_id'] for r in disc_rows}
    case_overlap = len(gt_cases & out_cases) / max(len(gt_cases), 1)
    check("disc_case_id_overlap", case_overlap >= 0.80,
          warn=(0.60 <= case_overlap < 0.80),
          message=f"{case_overlap:.1%} of first-200 gt case_ids in output")

# ---------------------------------------------------------------------------
# agency_name quality check
# ---------------------------------------------------------------------------
print("\n=== Agency name quality ===")

if has_emp and emp_rows:
    # Check for stripped non-agency noise strings
    BAD_AGENCY_LOWER = {'application denied', 'application purged', 'pending', 'unknown', 'n/a', ''}
    bad_agency = [r for r in emp_rows if r.get('agency_name', '').lower().strip() in BAD_AGENCY_LOWER]
    check("emp_no_bad_agency_values", len(bad_agency) == 0,
          message=f"{len(bad_agency)} rows with non-agency agency_name")

    # Employment index keeps the agency code prefix (per groundtruth)
    sample = emp_rows[:200]
    has_code = sum(1 for r in sample if re.match(r'^[A-Z]\d+\s+', r.get('agency_name', '')))
    check("emp_agency_has_code_prefix", has_code > 150,
          message=f"{has_code}/200 sampled rows have agency code prefix (expected)")

if has_disc and disc_rows:
    sample_d = disc_rows[:200]
    has_code_d = sum(1 for r in sample_d if re.match(r'^[a-z]\d+\s+', r.get('agency_name', '')))
    check("disc_agency_lowercase_with_code", has_code_d > 100,
          message=f"{has_code_d}/200 sampled disc rows have lowercase code prefix (expected)")

# ---------------------------------------------------------------------------
# Compute overall status
# ---------------------------------------------------------------------------
statuses = [s for _, s, _ in results]
if any(s == 'FAIL' for s in statuses):
    overall = 'FAIL'
elif any(s == 'WARN' for s in statuses):
    overall = 'WARN'
else:
    overall = 'PASS'

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------
md_lines = [
    "# GA 2025 — Judge Report",
    "",
    f"**Overall: {overall}**",
    f"**Has groundtruth: {has_groundtruth}**",
    "",
    "## Check Results",
    "",
    "| Check | Status | Message |",
    "|-------|--------|---------|",
]
for name, status, message in results:
    emoji = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
    md_lines.append(f"| {name} | {emoji} {status} | {message} |")

md_lines += [
    "",
    "## Summary",
    "",
    f"- Total checks: {len(results)}",
    f"- PASS: {statuses.count('PASS')}",
    f"- WARN: {statuses.count('WARN')}",
    f"- FAIL: {statuses.count('FAIL')}",
]

os.makedirs(OUTPUT_DIR, exist_ok=True)
md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, 'w') as f:
    f.write('\n'.join(md_lines) + '\n')

json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, 'w') as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\n=== OVERALL: {overall} ===")
print(f"Wrote {md_path}")
print(f"Wrote {json_path}")
