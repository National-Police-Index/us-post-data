"""
Georgia POST 2025 — Validation / Judge Script
Writes:
  output/judge_report.md   — human-readable
  output/judge_report.json — {"overall": "PASS|WARN|FAIL", "has_groundtruth": true|false}
"""

import json
import os
import sys

import pandas as pd

OUTPUT_DIR = "output"
GT_DIR = "data/groundtruth"

EMPLOYMENT_OUT = os.path.join(OUTPUT_DIR, "ga_index.csv")
DISCIPLINE_OUT = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
GT_EMPLOYMENT = os.path.join(GT_DIR, "georgia_index.csv")
GT_DISCIPLINE = os.path.join(GT_DIR, "georgia-discipline_index.csv")

checks = []   # list of (name, status, detail)


def check(name, passed, warn=False, detail=""):
    status = "PASS" if passed else ("WARN" if warn else "FAIL")
    checks.append((name, status, detail))
    return passed


def load_csv(path, label):
    try:
        df = pd.read_csv(path, dtype=str)
        print(f"  Loaded {label}: {len(df)} rows")
        return df
    except Exception as e:
        checks.append((f"Load {label}", "FAIL", str(e)))
        return None


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------
print("Checking file existence...")
emp_exists = os.path.exists(EMPLOYMENT_OUT)
disc_exists = os.path.exists(DISCIPLINE_OUT)
check("ga_index.csv exists", emp_exists, detail=EMPLOYMENT_OUT)
check("ga-discipline_index.csv exists", disc_exists, detail=DISCIPLINE_OUT)

# ---------------------------------------------------------------------------
# 2. Load outputs
# ---------------------------------------------------------------------------
print("Loading output files...")
emp_df = load_csv(EMPLOYMENT_OUT, "ga_index") if emp_exists else None
disc_df = load_csv(DISCIPLINE_OUT, "ga-discipline_index") if disc_exists else None

# ---------------------------------------------------------------------------
# 3. Employment index schema checks
# ---------------------------------------------------------------------------
if emp_df is not None:
    print("Checking employment index schema...")
    required_cols = ["person_nbr", "first_name", "last_name", "agency_name",
                     "start_date", "end_date"]
    missing_cols = [c for c in required_cols if c not in emp_df.columns]
    check("All required columns present (employment)", not missing_cols,
          detail=f"Missing: {missing_cols}" if missing_cols else "All present")

    # person_nbr format: lowercase, no whitespace
    pnbr_ok = emp_df["person_nbr"].str.match(r"^[a-z]\d+$", na=False).all()
    bad_pnbr = emp_df[~emp_df["person_nbr"].str.match(r"^[a-z]\d+$", na=False)]["person_nbr"].head(3).tolist()
    check("person_nbr format (lowercase, o-prefix)", pnbr_ok,
          warn=not pnbr_ok,
          detail=f"Bad samples: {bad_pnbr}" if not pnbr_ok else "OK")

    # start_date not empty
    empty_start = (emp_df["start_date"].isna() | (emp_df["start_date"] == "")).sum()
    check("No empty start_date (employment)", empty_start == 0,
          detail=f"{empty_start} empty start_dates" if empty_start else "0 empty")

    # start_date format
    valid_dates = emp_df["start_date"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
    bad_dates = (~valid_dates & emp_df["start_date"].notna() & (emp_df["start_date"] != "")).sum()
    check("start_date format YYYY-MM-DD (employment)", bad_dates == 0,
          detail=f"{bad_dates} malformed start_dates")

    # end_date format (can be empty or 0000-00-00 or YYYY-MM-DD)
    valid_end = emp_df["end_date"].str.match(r"^(\d{4}-\d{2}-\d{2}|0000-00-00|)$", na=True)
    bad_end = (~valid_end).sum()
    check("end_date format valid (employment)", bad_end == 0, warn=bad_end > 0,
          detail=f"{bad_end} malformed end_dates")

    # No duplicate rows
    dupes = emp_df.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
    check("No duplicate rows (employment)", dupes == 0, warn=dupes > 0,
          detail=f"{dupes} duplicate rows" if dupes else "0 duplicates")

    # Row count sanity
    row_count = len(emp_df)
    check("Employment row count reasonable (>400k)", row_count > 400_000,
          detail=f"{row_count:,} rows")

# ---------------------------------------------------------------------------
# 4. Discipline index schema checks
# ---------------------------------------------------------------------------
if disc_df is not None:
    print("Checking discipline index schema...")
    required_disc = ["person_nbr", "first_name", "last_name", "agency_name",
                     "start_date", "end_date", "case_id", "violation", "sanction"]
    missing_disc = [c for c in required_disc if c not in disc_df.columns]
    check("All required columns present (discipline)", not missing_disc,
          detail=f"Missing: {missing_disc}" if missing_disc else "All present")

    # case_id format (zero-padded 10-digit string)
    cid_ok = disc_df["case_id"].str.match(r"^\d{10}$", na=False).all()
    bad_cid = disc_df[~disc_df["case_id"].str.match(r"^\d{10}$", na=False)]["case_id"].head(3).tolist()
    check("case_id format (10-digit zero-padded)", cid_ok, warn=not cid_ok,
          detail=f"Bad samples: {bad_cid}" if not cid_ok else "OK")

    # start_date not empty
    empty_disc_start = (disc_df["start_date"].isna() | (disc_df["start_date"] == "")).sum()
    check("No empty start_date (discipline)", empty_disc_start == 0,
          detail=f"{empty_disc_start} empty start_dates" if empty_disc_start else "0 empty")

    # Discipline row count
    disc_rows = len(disc_df)
    check("Discipline row count reasonable (>30k)", disc_rows > 30_000,
          detail=f"{disc_rows:,} rows")

# ---------------------------------------------------------------------------
# 5. Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.exists(GT_EMPLOYMENT) and os.path.exists(GT_DISCIPLINE)
print(f"Ground truth available: {has_groundtruth}")

if has_groundtruth:
    gt_emp = load_csv(GT_EMPLOYMENT, "gt_employment")
    gt_disc = load_csv(GT_DISCIPLINE, "gt_discipline")

    if gt_emp is not None and emp_df is not None:
        # Row count comparison (allow up to 5% drift)
        emp_count = len(emp_df)
        gt_emp_count = len(gt_emp)
        pct_diff_emp = abs(emp_count - gt_emp_count) / gt_emp_count
        check(
            f"Employment row count within 5% of GT ({gt_emp_count:,})",
            pct_diff_emp <= 0.05,
            warn=pct_diff_emp <= 0.20,
            detail=f"Ours: {emp_count:,}, GT: {gt_emp_count:,} ({pct_diff_emp:.1%} diff)"
        )

        # Spot-check first row values
        if len(emp_df) > 0 and len(gt_emp) > 0:
            # Sort both by person_nbr + start_date for comparison
            our_sorted = emp_df.sort_values(["person_nbr", "start_date"]).reset_index(drop=True)
            gt_sorted = gt_emp.sort_values(["person_nbr", "start_date"]).reset_index(drop=True)
            # Check first 100 person_nbr values match
            our_pnbr = set(our_sorted["person_nbr"].head(200))
            gt_pnbr = set(gt_sorted["person_nbr"].head(200))
            overlap = len(our_pnbr & gt_pnbr) / max(len(our_pnbr | gt_pnbr), 1)
            check("person_nbr overlap in first 200 rows (employment)", overlap > 0.8,
                  warn=overlap > 0.5,
                  detail=f"Overlap: {overlap:.1%}")

        # Check agency_name format matches GT (first 5 rows)
        if len(emp_df) >= 5 and len(gt_emp) >= 5:
            # Find matching rows
            our_match = emp_df[emp_df["person_nbr"] == gt_emp.iloc[0]["person_nbr"]]
            if len(our_match) > 0:
                our_agency = our_match.iloc[0]["agency_name"]
                gt_agency = gt_emp.iloc[0]["agency_name"]
                agency_match = (our_agency == gt_agency)
                check("Agency name format matches GT (sample)", agency_match,
                      warn=not agency_match,
                      detail=f"Ours: {our_agency!r}, GT: {gt_agency!r}")

        # full_name format check
        our_fn = emp_df.sort_values(["person_nbr","start_date"])["full_name"].head(3).tolist()
        gt_fn = gt_emp.sort_values(["person_nbr","start_date"])["full_name"].head(3).tolist()
        fn_match = (our_fn == gt_fn)
        check("full_name format matches GT (first 3)", fn_match, warn=not fn_match,
              detail=f"Ours: {our_fn}, GT: {gt_fn}")

    if gt_disc is not None and disc_df is not None:
        # Row count comparison
        disc_count = len(disc_df)
        gt_disc_count = len(gt_disc)
        pct_diff_disc = abs(disc_count - gt_disc_count) / gt_disc_count
        # Allow larger drift for discipline (data has grown significantly)
        check(
            f"Discipline row count within 200% of GT ({gt_disc_count:,})",
            pct_diff_disc <= 2.0,
            warn=pct_diff_disc <= 3.0,
            detail=f"Ours: {disc_count:,}, GT: {gt_disc_count:,} ({pct_diff_disc:.1%} diff)"
        )

        # Check that our discipline cases overlap with GT cases
        our_cases = set(disc_df["case_id"].unique())
        gt_cases = set(gt_disc["case_id"].unique())
        case_overlap = len(our_cases & gt_cases) / max(len(gt_cases), 1)
        check("Discipline case_id overlap with GT (>80%)", case_overlap > 0.80,
              warn=case_overlap > 0.60,
              detail=f"Overlap: {case_overlap:.1%} ({len(our_cases & gt_cases)} of {len(gt_cases)} GT cases)")

        # Check person_nbr overlap
        our_persons = set(disc_df["person_nbr"].unique())
        gt_persons = set(gt_disc["person_nbr"].unique())
        person_overlap = len(our_persons & gt_persons) / max(len(gt_persons), 1)
        check("Discipline person_nbr overlap with GT (>80%)", person_overlap > 0.80,
              warn=person_overlap > 0.60,
              detail=f"Overlap: {person_overlap:.1%}")

# ---------------------------------------------------------------------------
# 6. Determine overall result
# ---------------------------------------------------------------------------
statuses = [s for _, s, _ in checks]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# 7. Write judge_report.md
# ---------------------------------------------------------------------------
md_lines = [
    "# Georgia POST 2025 — Judge Report",
    "",
    f"**Overall: {overall}**",
    f"**Ground truth available: {has_groundtruth}**",
    "",
    "## Check Results",
    "",
    "| Status | Check | Detail |",
    "|--------|-------|--------|",
]
for name, status, detail in checks:
    emoji = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
    md_lines.append(f"| {emoji} {status} | {name} | {detail} |")

if emp_df is not None:
    md_lines += [
        "",
        "## Employment Index Summary",
        "",
        f"- **Rows**: {len(emp_df):,}",
        f"- **Unique officers**: {emp_df['person_nbr'].nunique():,}",
        f"- **Unique agencies**: {emp_df['agency_name'].nunique():,}",
        f"- **Date range**: {emp_df['start_date'].min()} — {emp_df['start_date'].max()}",
    ]

if disc_df is not None:
    md_lines += [
        "",
        "## Discipline Index Summary",
        "",
        f"- **Rows**: {len(disc_df):,}",
        f"- **Unique cases**: {disc_df['case_id'].nunique():,}",
        f"- **Unique officers**: {disc_df['person_nbr'].nunique():,}",
        f"- **Top violations**: {', '.join(disc_df['violation'].value_counts().head(3).index.tolist())}",
    ]

md_out = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_out, "w") as f:
    f.write("\n".join(md_lines) + "\n")
print(f"\nWrote: {md_out}")

# ---------------------------------------------------------------------------
# 8. Write judge_report.json
# ---------------------------------------------------------------------------
json_out = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_out, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)
print(f"Wrote: {json_out}")

# ---------------------------------------------------------------------------
# 9. Print summary
# ---------------------------------------------------------------------------
print(f"\n{'='*50}")
print(f"OVERALL: {overall}")
print(f"{'='*50}")
for name, status, detail in checks:
    print(f"  [{status:4s}] {name}: {detail}")
