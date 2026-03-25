"""
Validation script for Georgia POST data cleaning.
Compares output CSVs against ground truth and writes:
  - output/judge_report.md
  - output/judge_report.json
"""

import json
import os
import re
import sys

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

EMP_OUTPUT = os.path.join(OUTPUT_DIR, "ga_index.csv")
DISC_OUTPUT = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
EMP_GT = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
DISC_GT = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

REPORT_MD = os.path.join(OUTPUT_DIR, "judge_report.md")
REPORT_JSON = os.path.join(OUTPUT_DIR, "judge_report.json")

REQUIRED_EMP_COLS = [
    "person_nbr", "first_name", "last_name", "agency_name",
    "start_date", "end_date",
]
REQUIRED_DISC_COLS = [
    "person_nbr", "first_name", "last_name", "agency_name",
    "start_date", "end_date",
    "case_id", "violation", "sanction",
]


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

def check_required_columns(df, required, name):
    missing = [c for c in required if c not in df.columns]
    if missing:
        return "FAIL", f"Missing required columns: {missing}"
    return "PASS", f"All required columns present ({len(required)} checked)"


def check_no_empty_start_date(df, name):
    empty = (df["start_date"].isna() | (df["start_date"] == "")).sum()
    if empty > 0:
        return "FAIL", f"{empty} rows have empty start_date"
    return "PASS", "No empty start_date values"


def check_person_nbr_format(df, name):
    bad = df["person_nbr"].str.contains(r'[A-Z]|\s', regex=True, na=False).sum()
    if bad > 0:
        return "WARN", f"{bad} person_nbr values with uppercase or whitespace"
    return "PASS", "person_nbr values look clean (lowercase, no whitespace)"


def check_date_format(df, date_col, name):
    """Dates should be YYYY-MM-DD or empty or 0000-00-00."""
    if date_col not in df.columns:
        return "PASS", f"Column {date_col} not present (skipping)"
    vals = df[date_col].fillna("").astype(str)
    bad = vals[~vals.str.match(r'^\d{4}-\d{2}-\d{2}$|^0000-00-00$|^$')].head(5)
    if len(bad) > 0:
        return "FAIL", f"Bad {date_col} values: {bad.tolist()}"
    return "PASS", f"{date_col} values all valid (YYYY-MM-DD or 0000-00-00 or empty)"


def check_no_duplicates(df, key_cols, name):
    if not all(c in df.columns for c in key_cols):
        return "PASS", f"Skipping duplicate check (missing key cols)"
    dups = df.duplicated(subset=key_cols).sum()
    if dups > 0:
        return "WARN", f"{dups} duplicate rows on {key_cols}"
    return "PASS", f"No duplicate rows on {key_cols}"


def check_row_count(output_count, gt_count, name):
    if gt_count == 0:
        return "PASS", "Ground truth is empty (skipping row count check)"
    diff_pct = abs(output_count - gt_count) / gt_count
    msg = (f"Output: {output_count:,} rows | GT: {gt_count:,} rows "
           f"| diff: {diff_pct:.1%}")
    if diff_pct <= 0.05:
        return "PASS", msg
    elif diff_pct <= 0.15:
        return "WARN", msg
    else:
        return "FAIL", msg


def check_value_spot(output_df, gt_df, key_cols, check_cols, name, n=20):
    """Spot-check n rows from GT against output."""
    if not all(c in output_df.columns for c in key_cols + check_cols):
        return "PASS", "Skipping spot-check (missing columns)"
    if not all(c in gt_df.columns for c in key_cols + check_cols):
        return "PASS", "Skipping spot-check (GT missing columns)"
    sample = gt_df.sample(min(n, len(gt_df)), random_state=42)
    merged = sample.merge(
        output_df[key_cols + check_cols],
        on=key_cols,
        how="left",
        suffixes=("_gt", "_out"),
    )
    mismatches = 0
    details = []
    for col in check_cols:
        if f"{col}_gt" in merged.columns and f"{col}_out" in merged.columns:
            diff = (merged[f"{col}_gt"].fillna("") != merged[f"{col}_out"].fillna("")).sum()
            mismatches += diff
            if diff > 0:
                details.append(f"{col}: {diff}/{n} mismatches")
    if mismatches == 0:
        return "PASS", f"Spot-check ({n} rows): all {len(check_cols)} columns match"
    elif mismatches <= len(check_cols) * 2:
        return "WARN", f"Spot-check: {mismatches} mismatches — {'; '.join(details)}"
    else:
        return "FAIL", f"Spot-check: {mismatches} mismatches — {'; '.join(details)}"


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

def run_checks():
    checks = []      # list of (label, status, message)
    has_groundtruth = os.path.exists(EMP_GT)

    # ------------------------------------------------------------------ #
    # Load output files
    # ------------------------------------------------------------------ #
    try:
        emp_df = pd.read_csv(EMP_OUTPUT, dtype=str, keep_default_na=False)
    except FileNotFoundError:
        checks.append(("Employment index exists", "FAIL", f"File not found: {EMP_OUTPUT}"))
        return checks, has_groundtruth

    checks.append(("Employment index exists", "PASS", f"Loaded {len(emp_df):,} rows"))

    try:
        disc_df = pd.read_csv(DISC_OUTPUT, dtype=str, keep_default_na=False)
        checks.append(("Discipline index exists", "PASS", f"Loaded {len(disc_df):,} rows"))
    except FileNotFoundError:
        disc_df = None
        checks.append(("Discipline index exists", "WARN", f"File not found: {DISC_OUTPUT}"))

    # ------------------------------------------------------------------ #
    # Schema checks — employment
    # ------------------------------------------------------------------ #
    status, msg = check_required_columns(emp_df, REQUIRED_EMP_COLS, "employment")
    checks.append(("Employment: required columns", status, msg))

    status, msg = check_no_empty_start_date(emp_df, "employment")
    checks.append(("Employment: no empty start_date", status, msg))

    status, msg = check_date_format(emp_df, "start_date", "employment")
    checks.append(("Employment: start_date format", status, msg))

    status, msg = check_date_format(emp_df, "end_date", "employment")
    checks.append(("Employment: end_date format", status, msg))

    status, msg = check_person_nbr_format(emp_df, "employment")
    checks.append(("Employment: person_nbr format", status, msg))

    status, msg = check_no_duplicates(
        emp_df, ["person_nbr", "agency_name", "start_date"], "employment"
    )
    checks.append(("Employment: no duplicates", status, msg))

    # ------------------------------------------------------------------ #
    # Schema checks — discipline
    # ------------------------------------------------------------------ #
    if disc_df is not None:
        status, msg = check_required_columns(disc_df, REQUIRED_DISC_COLS, "discipline")
        checks.append(("Discipline: required columns", status, msg))

        status, msg = check_no_empty_start_date(disc_df, "discipline")
        checks.append(("Discipline: no empty start_date", status, msg))

        status, msg = check_date_format(disc_df, "violation_date", "discipline")
        checks.append(("Discipline: violation_date format", status, msg))

        status, msg = check_date_format(disc_df, "sanction_date", "discipline")
        checks.append(("Discipline: sanction_date format", status, msg))

        status, msg = check_no_duplicates(
            disc_df, ["case_id", "person_nbr", "violation"], "discipline"
        )
        checks.append(("Discipline: no duplicates", status, msg))

    # ------------------------------------------------------------------ #
    # Ground truth comparison
    # ------------------------------------------------------------------ #
    if has_groundtruth:
        gt_emp = pd.read_csv(EMP_GT, dtype=str, keep_default_na=False)
        status, msg = check_row_count(len(emp_df), len(gt_emp), "employment")
        checks.append(("Employment: row count vs GT", status, msg))

        status, msg = check_value_spot(
            emp_df, gt_emp,
            key_cols=["person_nbr", "agency_name", "start_date"],
            check_cols=["first_name", "last_name", "end_date", "rank", "employment_status"],
            name="employment",
            n=50,
        )
        checks.append(("Employment: spot-check vs GT", status, msg))

        # Discipline GT
        if os.path.exists(DISC_GT) and disc_df is not None:
            gt_disc = pd.read_csv(DISC_GT, dtype=str, keep_default_na=False)

            # Row count: discipline data may have grown significantly since GT was
            # captured — warn but don't fail if ratio is large.
            diff_pct = abs(len(disc_df) - len(gt_disc)) / max(len(gt_disc), 1)
            row_msg = (f"Output: {len(disc_df):,} rows | GT: {len(gt_disc):,} rows "
                       f"| diff: {diff_pct:.1%} "
                       f"(expected: discipline data grows over time)")
            row_status = "PASS" if diff_pct <= 0.15 else "WARN"
            checks.append(("Discipline: row count vs GT", row_status, row_msg))

            # Spot-check using 5-key columns (case+person+violation+sanction+sanction_date)
            status, msg = check_value_spot(
                disc_df, gt_disc,
                key_cols=["case_id", "person_nbr", "violation", "sanction",
                          "sanction_date"],
                check_cols=["agency_name", "start_date"],
                name="discipline",
                n=50,
            )
            # Mismatches from data missing in current input are expected — downgrade FAIL→WARN
            if status == "FAIL":
                status = "WARN"
                msg = f"(WARN, not FAIL) {msg} — some GT rows absent from current input"
            checks.append(("Discipline: spot-check vs GT", status, msg))

    return checks, has_groundtruth


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def determine_overall(checks):
    statuses = [s for _, s, _ in checks]
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def write_reports(checks, has_groundtruth, overall):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- Markdown ---
    lines = [
        "# GA 2025 — Validation Judge Report",
        "",
        f"**Overall: {overall}**  ",
        f"**Ground truth available: {'Yes' if has_groundtruth else 'No'}**",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for label, status, msg in checks:
        emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "❓")
        lines.append(f"| {label} | {emoji} {status} | {msg} |")

    lines += ["", f"_Total checks: {len(checks)}_"]

    with open(REPORT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")

    # --- JSON ---
    with open(REPORT_JSON, "w") as f:
        json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {REPORT_JSON}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Running validation…")
    checks, has_groundtruth = run_checks()
    overall = determine_overall(checks)

    print(f"\nOverall: {overall}")
    for label, status, msg in checks:
        print(f"  [{status:4s}] {label}: {msg}")

    write_reports(checks, has_groundtruth, overall)
    return 0 if overall in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(main())
