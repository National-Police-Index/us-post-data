"""
Validation script for AZ 2025 POST data.
Writes output/judge_report.md and output/judge_report.json.
Run from states/az/2025/ as cwd.
"""

import csv
import json
import os
import re
from datetime import datetime

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "az_index.csv")
GT_CSV = os.path.join(GROUNDTRUTH_DIR, "arizona_index.csv")

checks = []   # list of {"name", "status", "detail"}


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}")
    return passed


def warn(name, detail=""):
    checks.append({"name": name, "status": "WARN", "detail": detail})
    print(f"[WARN] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output CSV
# ---------------------------------------------------------------------------
assert os.path.exists(OUTPUT_CSV), f"Output file not found: {OUTPUT_CSV}"
df = pd.read_csv(OUTPUT_CSV, dtype=str).fillna("")

print(f"\nLoaded output: {len(df):,} rows, columns: {list(df.columns)}\n")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
REQUIRED_COLS = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
check("required_columns_present", len(missing) == 0,
      f"missing: {missing}" if missing else "all required columns present")

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------
if "person_nbr" in df.columns:
    bad_pnbr = df["person_nbr"].str.strip() != df["person_nbr"]
    check("person_nbr_no_whitespace", not bad_pnbr.any(),
          f"{bad_pnbr.sum()} rows have leading/trailing whitespace in person_nbr")

    upper_pnbr = df["person_nbr"].str.contains(r"[A-Z]", na=False)
    check("person_nbr_lowercase", not upper_pnbr.any(),
          f"{upper_pnbr.sum()} rows have uppercase chars in person_nbr" if upper_pnbr.any() else "all lowercase")

    empty_pnbr = (df["person_nbr"] == "").sum()
    check("person_nbr_not_empty", empty_pnbr == 0,
          f"{empty_pnbr} empty person_nbr" if empty_pnbr else "no empty person_nbr")

# ---------------------------------------------------------------------------
# start_date not empty
# ---------------------------------------------------------------------------
if "start_date" in df.columns:
    empty_start = (df["start_date"] == "").sum()
    check("start_date_not_empty", empty_start == 0,
          f"{empty_start} rows with empty start_date" if empty_start else "no empty start_date")

# ---------------------------------------------------------------------------
# Date format YYYY-MM-DD
# ---------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def check_date_format(col):
    if col not in df.columns:
        return
    non_empty = df[col][df[col] != ""]
    bad = non_empty[~non_empty.str.match(DATE_RE)]
    check(f"{col}_format", len(bad) == 0,
          f"{len(bad)} values not in YYYY-MM-DD format" if len(bad) else "all YYYY-MM-DD")

check_date_format("start_date")
check_date_format("end_date")

# ---------------------------------------------------------------------------
# No 0000-00-00 or NaT/None in date columns
# ---------------------------------------------------------------------------
for col in ["start_date", "end_date"]:
    if col not in df.columns:
        continue
    bad_vals = df[col].isin(["0000-00-00", "NaT", "None"])
    check(f"{col}_no_invalid_sentinel", not bad_vals.any(),
          f"{bad_vals.sum()} invalid sentinel values in {col}" if bad_vals.any() else "clean")

# ---------------------------------------------------------------------------
# No duplicate rows
# ---------------------------------------------------------------------------
dupe_cols = ["person_nbr", "agency_name", "start_date"]
if all(c in df.columns for c in dupe_cols):
    dupes = df.duplicated(subset=dupe_cols).sum()
    check("no_duplicate_rows", dupes == 0,
          f"{dupes} duplicate (person_nbr, agency_name, start_date) rows" if dupes else "no duplicates")

# ---------------------------------------------------------------------------
# agency_name quality — no code prefixes
# ---------------------------------------------------------------------------
if "agency_name" in df.columns:
    code_prefix = df["agency_name"].str.match(r"^[A-Z]\d{3,}\s+", na=False)
    check("agency_name_no_code_prefix", not code_prefix.any(),
          f"{code_prefix.sum()} agency names with code prefixes" if code_prefix.any() else "no code prefixes")

    empty_agency = (df["agency_name"] == "").sum()
    check("agency_name_not_empty", empty_agency == 0,
          f"{empty_agency} empty agency names" if empty_agency else "no empty agency names")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.exists(GT_CSV)

if has_groundtruth:
    gt = pd.read_csv(GT_CSV, dtype=str).fillna("")
    print(f"\nGroundtruth loaded: {len(gt):,} rows, columns: {list(gt.columns)}")

    # Row count comparison
    row_diff_pct = abs(len(df) - len(gt)) / max(len(gt), 1) * 100
    if row_diff_pct <= 5:
        check("row_count_within_5pct", True,
              f"output={len(df):,}, gt={len(gt):,}, diff={row_diff_pct:.1f}%")
    else:
        warn("row_count_within_5pct",
             f"output={len(df):,}, gt={len(gt):,}, diff={row_diff_pct:.1f}% (>5% threshold)")

    # Normalize groundtruth dates to YYYY-MM-DD for comparison
    def norm_date(s):
        s = str(s).strip()
        if not s or s in ("nan", "NaT", "None", "0000-00-00"):
            return ""
        try:
            return pd.to_datetime(s, errors="coerce").strftime("%Y-%m-%d")
        except Exception:
            return ""

    gt["start_date"] = gt["start_date"].apply(norm_date)
    gt["end_date"] = gt["end_date"].apply(norm_date)

    # Normalize agency name (lowercase) for comparison
    gt["agency_name_norm"] = gt["agency_name"].str.lower().str.strip()
    df["agency_name_norm"] = df["agency_name"].str.lower().str.strip()

    # Match on person_nbr + start_date
    gt["person_nbr"] = gt["person_nbr"].astype(str).str.strip().str.lower()
    df_key = df.set_index(["person_nbr", "start_date"])
    gt_key = gt.set_index(["person_nbr", "start_date"])

    common_keys = df_key.index.intersection(gt_key.index)
    coverage = len(common_keys) / max(len(gt_key), 1) * 100
    if coverage >= 80:
        check("groundtruth_key_coverage", True,
              f"{len(common_keys):,}/{len(gt_key):,} groundtruth keys found in output ({coverage:.1f}%)")
    else:
        warn("groundtruth_key_coverage",
             f"Only {coverage:.1f}% of groundtruth keys found in output ({len(common_keys):,}/{len(gt_key):,})")

    # Spot-check: first_name / last_name match for common keys (sample 200)
    sample_keys = list(common_keys)[:200]
    name_matches = 0
    name_total = 0
    for key in sample_keys:
        gt_row = gt_key.loc[key]
        df_row = df_key.loc[key]
        # Handle multiple matches (take first)
        if isinstance(gt_row, pd.DataFrame):
            gt_row = gt_row.iloc[0]
        if isinstance(df_row, pd.DataFrame):
            df_row = df_row.iloc[0]
        gt_last = str(gt_row.get("last_name", "")).lower().strip()
        df_last = str(df_row.get("last_name", "")).lower().strip()
        if gt_last and df_last:
            name_total += 1
            if gt_last == df_last:
                name_matches += 1

    if name_total > 0:
        name_match_pct = name_matches / name_total * 100
        if name_match_pct >= 90:
            check("last_name_spot_check", True,
                  f"{name_matches}/{name_total} last names match groundtruth ({name_match_pct:.1f}%)")
        else:
            warn("last_name_spot_check",
                 f"Only {name_match_pct:.1f}% last name match ({name_matches}/{name_total})")

    # Agency name spot-check (sample 200 common keys)
    agency_matches = 0
    agency_total = 0
    for key in sample_keys:
        gt_row = gt_key.loc[key]
        df_row = df_key.loc[key]
        if isinstance(gt_row, pd.DataFrame):
            gt_row = gt_row.iloc[0]
        if isinstance(df_row, pd.DataFrame):
            df_row = df_row.iloc[0]
        gt_agency = str(gt_row.get("agency_name_norm", "")).lower().strip()
        df_agency = str(df_row.get("agency_name_norm", "")).lower().strip()
        if gt_agency and df_agency:
            agency_total += 1
            if gt_agency == df_agency:
                agency_matches += 1

    if agency_total > 0:
        agency_match_pct = agency_matches / agency_total * 100
        if agency_match_pct >= 70:
            check("agency_name_spot_check", True,
                  f"{agency_matches}/{agency_total} agency names match groundtruth ({agency_match_pct:.1f}%)")
        else:
            warn("agency_name_spot_check",
                 f"Only {agency_match_pct:.1f}% agency match ({agency_matches}/{agency_total})")

else:
    warn("groundtruth", "No groundtruth file found — skipping comparison checks")

# ---------------------------------------------------------------------------
# Determine overall result
# ---------------------------------------------------------------------------
statuses = [c["status"] for c in checks]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------
md_lines = [
    "# AZ 2025 — Judge Report",
    f"\nGenerated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    f"\n**Overall: {overall}**",
    f"\n**Ground truth available: {has_groundtruth}**",
    f"\n**Output rows: {len(df):,}**",
    "\n---\n",
    "## Checks\n",
    "| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for c in checks:
    md_lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")

md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write("\n".join(md_lines) + "\n")
print(f"\nWrote {md_path}")

# ---------------------------------------------------------------------------
# Write judge_report.json
# ---------------------------------------------------------------------------
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)
print(f"Wrote {json_path}")

print(f"\n=== OVERALL: {overall} ===")
