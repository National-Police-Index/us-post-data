"""
Georgia POST 2025 — Validation / LLM-as-judge script
Writes:
  output/judge_report.md   — human-readable
  output/judge_report.json — machine-readable {"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}
"""

import json
import os
import sys

import pandas as pd


OUTPUT_DIR = "output"
GT_DIR = "data/groundtruth"

EMP_CSV = os.path.join(OUTPUT_DIR, "ga_index.csv")
DISC_CSV = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
GT_EMP = os.path.join(GT_DIR, "georgia_index.csv")
GT_DISC = os.path.join(GT_DIR, "georgia-discipline_index.csv")

has_groundtruth = os.path.isfile(GT_EMP) and os.path.isfile(GT_DISC)

checks = []  # list of {"name", "status": PASS/WARN/FAIL, "detail"}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def check(name, status, detail):
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"{icon}  {name}: {detail}")


def pct(a, b):
    return 0.0 if b == 0 else abs(a - b) / b * 100


# ---------------------------------------------------------------------------
# Report writer (defined early so failure paths can call it)
# ---------------------------------------------------------------------------
def _write_report(checks, has_gt):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    statuses = [c["status"] for c in checks]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    # Markdown
    lines = [
        "# Georgia POST 2025 — Judge Report",
        "",
        f"**Overall: {overall}**",
        f"**Ground truth available: {has_gt}**",
        "",
        "| # | Check | Status | Detail |",
        "|---|-------|--------|--------|",
    ]
    for i, c in enumerate(checks, 1):
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c["status"]]
        lines.append(
            f"| {i} | {c['name']} | {icon} {c['status']} | {c['detail']} |"
        )

    lines += [
        "",
        "## Summary",
        f"- Total checks: {len(checks)}",
        f"- PASS: {statuses.count('PASS')}",
        f"- WARN: {statuses.count('WARN')}",
        f"- FAIL: {statuses.count('FAIL')}",
    ]

    md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    # JSON
    json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
    with open(json_path, "w") as f:
        json.dump({"overall": overall, "has_groundtruth": has_gt}, f, indent=2)

    print(f"\nOverall result: {overall}")
    print(f"Reports written to {md_path} and {json_path}")
    return overall


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------
try:
    emp = pd.read_csv(EMP_CSV, dtype=str)
    disc = pd.read_csv(DISC_CSV, dtype=str)
except FileNotFoundError as e:
    check("output_files_exist", "FAIL", str(e))
    _write_report(checks, has_groundtruth)
    sys.exit(1)

check(
    "output_files_exist",
    "PASS",
    f"ga_index.csv ({len(emp):,} rows), ga-discipline_index.csv ({len(disc):,} rows)",
)

# ---------------------------------------------------------------------------
# Schema checks — employment index
# ---------------------------------------------------------------------------
EMP_REQUIRED = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]
missing_emp = [c for c in EMP_REQUIRED if c not in emp.columns]
if missing_emp:
    check("emp_schema", "FAIL", f"Missing columns: {missing_emp}")
else:
    check("emp_schema", "PASS", f"All required columns present: {EMP_REQUIRED}")

# ---------------------------------------------------------------------------
# Schema checks — discipline index
# ---------------------------------------------------------------------------
DISC_REQUIRED = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
    "case_id",
    "violation",
    "sanction",
]
missing_disc = [c for c in DISC_REQUIRED if c not in disc.columns]
if missing_disc:
    check("disc_schema", "FAIL", f"Missing columns: {missing_disc}")
else:
    check("disc_schema", "PASS", "All required columns present")

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------
bad_pnbr_emp = emp["person_nbr"].dropna()
bad_upper = (~bad_pnbr_emp.str.islower()).sum() if len(bad_pnbr_emp) > 0 else 0
bad_ws = bad_pnbr_emp.str.contains(r"^\s|\s$", regex=True).sum()
if bad_upper == 0 and bad_ws == 0:
    check(
        "person_nbr_format", "PASS", "All person_nbr are lowercase and trimmed"
    )
elif bad_upper + bad_ws < 10:
    check(
        "person_nbr_format",
        "WARN",
        f"{bad_upper} uppercase, {bad_ws} whitespace issues in person_nbr",
    )
else:
    check(
        "person_nbr_format",
        "FAIL",
        f"{bad_upper} uppercase, {bad_ws} whitespace issues in person_nbr",
    )


# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------
def check_dates(df, col, label):
    vals = df[col].dropna()
    # Valid: YYYY-MM-DD, 0000-00-00, or empty string
    valid = vals.str.match(r"^\d{4}-\d{2}-\d{2}$") | (vals == "") | vals.isna()
    bad = (~valid).sum()
    if bad == 0:
        check(
            f"{label}_{col}_format",
            "PASS",
            f"All {col} values are valid date strings",
        )
    else:
        sample = vals[~valid].head(3).tolist()
        check(
            f"{label}_{col}_format",
            "WARN",
            f"{bad} invalid {col} values (e.g. {sample})",
        )


check_dates(emp, "start_date", "emp")
check_dates(emp, "end_date", "emp")
check_dates(disc, "start_date", "disc")
check_dates(disc, "end_date", "disc")

# ---------------------------------------------------------------------------
# start_date not empty (after dropping 0000-00-00 rows the pipeline wants non-empty starts)
# Per groundtruth, 0000-00-00 start_dates ARE preserved, so only truly empty is bad
# ---------------------------------------------------------------------------
empty_starts_emp = (emp["start_date"].fillna("") == "").sum()
if empty_starts_emp == 0:
    check(
        "emp_start_date_nonempty",
        "PASS",
        "No empty start_date values in employment index",
    )
else:
    check(
        "emp_start_date_nonempty",
        "WARN",
        f"{empty_starts_emp} empty start_date values in employment index",
    )

empty_starts_disc = (disc["start_date"].fillna("") == "").sum()
if empty_starts_disc == 0:
    check(
        "disc_start_date_nonempty",
        "PASS",
        "No empty start_date in discipline index",
    )
else:
    check(
        "disc_start_date_nonempty",
        "WARN",
        f"{empty_starts_disc} empty start_date in discipline index",
    )

# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------
emp_dupes = emp.duplicated(
    subset=["person_nbr", "agency_name", "start_date"]
).sum()
if emp_dupes == 0:
    check(
        "emp_no_duplicates",
        "PASS",
        "No duplicate (person_nbr, agency_name, start_date) rows",
    )
elif emp_dupes < 100:
    check(
        "emp_no_duplicates",
        "WARN",
        f"{emp_dupes} duplicate rows in employment index",
    )
else:
    check(
        "emp_no_duplicates",
        "FAIL",
        f"{emp_dupes} duplicate rows in employment index",
    )

disc_dupes = disc.duplicated(
    subset=["case_id", "person_nbr", "violation", "sanction"]
).sum()
if disc_dupes == 0:
    check(
        "disc_no_duplicates",
        "PASS",
        "No duplicate (case_id, person_nbr, violation, sanction) rows",
    )
elif disc_dupes < 100:
    check(
        "disc_no_duplicates",
        "WARN",
        f"{disc_dupes} duplicates in discipline index",
    )
else:
    check(
        "disc_no_duplicates",
        "FAIL",
        f"{disc_dupes} duplicates in discipline index",
    )

# ---------------------------------------------------------------------------
# Ground-truth comparison
# ---------------------------------------------------------------------------
if has_groundtruth:
    print("\nRunning ground-truth comparisons...")
    gt_emp = pd.read_csv(GT_EMP, dtype=str)
    gt_disc = pd.read_csv(GT_DISC, dtype=str)

    # --- Row count comparison ---
    emp_pct = pct(len(emp), len(gt_emp))
    disc_pct = pct(len(disc), len(gt_disc))

    if emp_pct <= 5:
        check(
            "gt_emp_row_count",
            "PASS",
            f"Employment rows: {len(emp):,} vs GT {len(gt_emp):,} ({emp_pct:.1f}% diff)",
        )
    elif emp_pct <= 20:
        check(
            "gt_emp_row_count",
            "WARN",
            f"Employment rows: {len(emp):,} vs GT {len(gt_emp):,} ({emp_pct:.1f}% diff) — "
            f"GT may be older snapshot",
        )
    else:
        check(
            "gt_emp_row_count",
            "WARN",
            f"Employment rows: {len(emp):,} vs GT {len(gt_emp):,} ({emp_pct:.1f}% diff) — "
            f"large diff, likely newer data",
        )

    if disc_pct <= 20:
        check(
            "gt_disc_row_count",
            "PASS" if disc_pct <= 5 else "WARN",
            f"Discipline rows: {len(disc):,} vs GT {len(gt_disc):,} ({disc_pct:.1f}% diff)",
        )
    else:
        check(
            "gt_disc_row_count",
            "WARN",
            f"Discipline rows: {len(disc):,} vs GT {len(gt_disc):,} ({disc_pct:.1f}% diff) — "
            f"GT is older snapshot",
        )

    # --- Schema column overlap ---
    gt_emp_cols = set(gt_emp.columns)
    gt_disc_cols = set(gt_disc.columns)
    out_emp_cols = set(emp.columns)
    out_disc_cols = set(disc.columns)

    missing_in_emp = gt_emp_cols - out_emp_cols
    missing_in_disc = gt_disc_cols - out_disc_cols
    extra_in_emp = out_emp_cols - gt_emp_cols
    extra_in_disc = out_disc_cols - gt_disc_cols

    if not missing_in_emp:
        check(
            "gt_emp_columns",
            "PASS",
            f"All GT columns present; extra cols: {sorted(extra_in_emp) or 'none'}",
        )
    else:
        check(
            "gt_emp_columns",
            "WARN",
            f"Columns in GT but not output: {sorted(missing_in_emp)}",
        )

    if not missing_in_disc:
        check(
            "gt_disc_columns",
            "PASS",
            f"All GT columns present; extra cols: {sorted(extra_in_disc) or 'none'}",
        )
    else:
        check(
            "gt_disc_columns",
            "WARN",
            f"Columns in GT but not output: {sorted(missing_in_disc)}",
        )

    # --- Spot-check: person_nbr values ---
    gt_persons = set(gt_emp["person_nbr"].dropna().unique())
    out_persons = set(emp["person_nbr"].dropna().unique())
    overlap = len(gt_persons & out_persons)
    overlap_pct = overlap / len(gt_persons) * 100 if gt_persons else 0

    if overlap_pct >= 95:
        check(
            "gt_person_overlap",
            "PASS",
            f"{overlap_pct:.1f}% of GT persons present in output "
            f"({overlap:,}/{len(gt_persons):,})",
        )
    elif overlap_pct >= 85:
        check(
            "gt_person_overlap",
            "WARN",
            f"Only {overlap_pct:.1f}% of GT persons in output",
        )
    else:
        check(
            "gt_person_overlap",
            "FAIL",
            f"Only {overlap_pct:.1f}% of GT persons in output — data may be missing",
        )

    # --- Spot-check a sample of rows ---
    SAMPLE_PERSONS = ["o143810", "o255181", "o095227", "o206100"]
    for pid in SAMPLE_PERSONS:
        gt_rows = gt_emp[gt_emp["person_nbr"] == pid]
        out_rows = emp[emp["person_nbr"] == pid]
        if len(gt_rows) == 0:
            continue
        if len(out_rows) == 0:
            check(
                f"spot_{pid}", "WARN", f"Person {pid} in GT but not in output"
            )
            continue
        # Check agency_name and start_date match
        gt_agencies = set(gt_rows["agency_name"].tolist())
        out_agencies = set(out_rows["agency_name"].tolist())
        match = len(gt_agencies & out_agencies) / len(gt_agencies) * 100
        status = "PASS" if match >= 80 else "WARN"
        check(
            f"spot_{pid}",
            status,
            f"Agency overlap {match:.0f}% | GT rows: {len(gt_rows)}, out rows: {len(out_rows)}",
        )

    # --- Discipline spot-check ---
    gt_cases = set(gt_disc["case_id"].dropna().astype(str).unique())
    out_cases = set(disc["case_id"].dropna().astype(str).unique())
    case_overlap = len(gt_cases & out_cases)
    case_pct = case_overlap / len(gt_cases) * 100 if gt_cases else 0

    if case_pct >= 95:
        check(
            "gt_disc_case_overlap",
            "PASS",
            f"{case_pct:.1f}% of GT cases present in output "
            f"({case_overlap:,}/{len(gt_cases):,})",
        )
    elif case_pct >= 80:
        check(
            "gt_disc_case_overlap",
            "WARN",
            f"{case_pct:.1f}% of GT cases in output",
        )
    else:
        check(
            "gt_disc_case_overlap",
            "WARN",
            f"Only {case_pct:.1f}% of GT cases in output — GT may be older snapshot",
        )

    # --- Agency name sanity check ---
    sample_agencies_emp = emp["agency_name"].dropna().unique()[:10]
    has_bare_code = any(
        a.strip().upper().startswith("G") and " " not in a
        for a in sample_agencies_emp
    )
    if not has_bare_code:
        check(
            "emp_agency_name_format",
            "PASS",
            "agency_name values look like full names (not bare codes)",
        )
    else:
        check(
            "emp_agency_name_format",
            "WARN",
            f"Some agency_name values may be bare codes: {list(sample_agencies_emp)[:5]}",
        )

else:
    # No ground truth — schema + format checks only (already done above)
    check(
        "no_groundtruth",
        "WARN",
        "No ground truth files found — running schema and format checks only",
    )

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
overall = _write_report(checks, has_groundtruth)
sys.exit(0 if overall in ("PASS", "WARN") else 1)
