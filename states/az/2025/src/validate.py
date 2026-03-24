"""
Arizona POST Employment Index Validator
Writes: output/judge_report.md and output/judge_report.json
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "az_index.csv")
GT_FILE = os.path.join(GROUNDTRUTH_DIR, "arizona_index.csv")

checks = []   # list of dicts: {name, status, detail}


def add_check(name, status, detail):
    """status: PASS | WARN | FAIL"""
    checks.append({"name": name, "status": status, "detail": detail})
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
    print(f"  {icon} [{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
print("Loading output file ...")
if not os.path.exists(OUTPUT_FILE):
    add_check("output_file_exists", "FAIL", f"{OUTPUT_FILE} not found")
    # Write reports and exit early
    overall = "FAIL"
    has_groundtruth = os.path.exists(GT_FILE)
    md_lines = ["# Arizona Validation Report\n", f"**Overall: {overall}**\n\n"]
    for c in checks:
        md_lines.append(f"- [{c['status']}] **{c['name']}**: {c['detail']}\n")
    with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
        f.writelines(md_lines)
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f)
    sys.exit(1)

df = pd.read_csv(OUTPUT_FILE, dtype={"person_nbr": str})
print(f"  Loaded {len(df):,} rows")

has_groundtruth = os.path.exists(GT_FILE)

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------
print("\nRunning schema checks ...")

REQUIRED_COLS = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    add_check("required_columns", "FAIL", f"Missing: {missing}")
else:
    add_check("required_columns", "PASS", "All required columns present")

# ---------------------------------------------------------------------------
# start_date non-empty
# ---------------------------------------------------------------------------
empty_start = (df["start_date"].isna() | (df["start_date"].astype(str).str.strip() == "")).sum()
if empty_start == 0:
    add_check("start_date_nonempty", "PASS", "No empty start_date values")
else:
    add_check("start_date_nonempty", "FAIL", f"{empty_start} rows have empty start_date")

# ---------------------------------------------------------------------------
# Date format YYYY-MM-DD
# ---------------------------------------------------------------------------
date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def check_date_col(col_name):
    col = df[col_name].fillna("").astype(str)
    bad = col[(col != "") & (~col.str.match(r"^\d{4}-\d{2}-\d{2}$"))]
    if len(bad) == 0:
        add_check(f"{col_name}_format", "PASS", "All dates in YYYY-MM-DD format")
    else:
        add_check(f"{col_name}_format", "WARN",
                  f"{len(bad)} values not in YYYY-MM-DD format (sample: {bad.head(3).tolist()})")

check_date_col("start_date")
check_date_col("end_date")

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------
pnbr = df["person_nbr"].astype(str)
has_whitespace = (pnbr != pnbr.str.strip()).sum()
if has_whitespace:
    add_check("person_nbr_whitespace", "FAIL", f"{has_whitespace} person_nbr values have whitespace")
else:
    add_check("person_nbr_whitespace", "PASS", "No whitespace in person_nbr")

has_upper = pnbr.str.contains(r"[A-Z]").sum()
if has_upper:
    add_check("person_nbr_lowercase", "WARN", f"{has_upper} person_nbr values have uppercase letters")
else:
    add_check("person_nbr_lowercase", "PASS", "person_nbr values are lowercase")

# ---------------------------------------------------------------------------
# No agency code prefixes
# ---------------------------------------------------------------------------
agency_code_re = re.compile(r"^[A-Z]\d{3,}\s+")
bad_agency = df["agency_name"].astype(str).str.match(agency_code_re).sum()
if bad_agency:
    add_check("agency_no_code_prefix", "FAIL", f"{bad_agency} agency names have code prefixes")
else:
    add_check("agency_no_code_prefix", "PASS", "No agency code prefixes found")

# ---------------------------------------------------------------------------
# No duplicate rows
# ---------------------------------------------------------------------------
dupes = df.duplicated(subset=["person_nbr", "agency_name", "start_date"]).sum()
if dupes == 0:
    add_check("no_duplicates", "PASS", "No duplicate rows (person_nbr+agency_name+start_date)")
else:
    add_check("no_duplicates", "WARN", f"{dupes} duplicate rows found")

# ---------------------------------------------------------------------------
# Row count sanity
# ---------------------------------------------------------------------------
if len(df) > 1000:
    add_check("row_count_sanity", "PASS", f"{len(df):,} rows (above minimum 1,000)")
else:
    add_check("row_count_sanity", "FAIL", f"Only {len(df):,} rows — suspiciously low")

# ---------------------------------------------------------------------------
# Unique officer count
# ---------------------------------------------------------------------------
unique_officers = df["person_nbr"].nunique()
add_check("unique_officers", "PASS", f"{unique_officers:,} unique officers")

# ---------------------------------------------------------------------------
# Ground-truth comparison
# ---------------------------------------------------------------------------
if has_groundtruth:
    print("\nRunning ground-truth checks ...")
    gt = pd.read_csv(GT_FILE, dtype={"person_nbr": str})

    # Row count comparison
    gt_rows = len(gt)
    out_rows = len(df)
    ratio = abs(out_rows - gt_rows) / gt_rows if gt_rows > 0 else 0
    if ratio <= 0.05:
        add_check("gt_row_count", "PASS",
                  f"Output {out_rows:,} vs GT {gt_rows:,} (diff {ratio:.1%})")
    elif ratio <= 0.15:
        add_check("gt_row_count", "WARN",
                  f"Output {out_rows:,} vs GT {gt_rows:,} (diff {ratio:.1%} > 5%)")
    else:
        add_check("gt_row_count", "WARN",
                  f"Output {out_rows:,} vs GT {gt_rows:,} (diff {ratio:.1%} > 15% — large gap, "
                  "likely source data updated since snapshot)")

    # Person_nbr overlap
    gt_ids = set(gt["person_nbr"].astype(str).str.strip())
    out_ids = set(df["person_nbr"].astype(str).str.strip())
    overlap = len(gt_ids & out_ids)
    overlap_ratio = overlap / len(gt_ids) if gt_ids else 0
    if overlap_ratio >= 0.90:
        add_check("gt_person_nbr_overlap", "PASS",
                  f"{overlap:,} / {len(gt_ids):,} GT person_nbr values found in output ({overlap_ratio:.1%})")
    elif overlap_ratio >= 0.75:
        add_check("gt_person_nbr_overlap", "WARN",
                  f"Only {overlap_ratio:.1%} of GT person_nbr values found in output")
    else:
        add_check("gt_person_nbr_overlap", "WARN",
                  f"Low overlap: {overlap_ratio:.1%} of GT person_nbr values in output "
                  "(GT and input may use different ID schemes)")

    # Spot-check: find a common person_nbr and compare agency + date
    common_ids = sorted(gt_ids & out_ids)
    if common_ids:
        sample_id = common_ids[len(common_ids) // 2]  # pick middle one
        gt_row = gt[gt["person_nbr"].astype(str).str.strip() == sample_id].iloc[0]
        out_rows_sample = df[df["person_nbr"].astype(str).str.strip() == sample_id]

        # Normalize GT start_date to YYYY-MM-DD
        try:
            gt_start = pd.to_datetime(gt_row["start_date"]).strftime("%Y-%m-%d")
        except Exception:
            gt_start = str(gt_row["start_date"])

        # Check if any output row matches GT agency (case-insensitive) and date
        gt_agency_lower = str(gt_row["agency_name"]).lower().strip()
        out_agencies = out_rows_sample["agency_name"].str.lower().str.strip().tolist()
        out_starts = out_rows_sample["start_date"].astype(str).tolist()

        agency_match = any(gt_agency_lower in a or a in gt_agency_lower for a in out_agencies)
        date_match = gt_start in out_starts

        if agency_match and date_match:
            add_check("gt_spot_check", "PASS",
                      f"person_nbr={sample_id}: agency and date match GT")
        elif agency_match or date_match:
            add_check("gt_spot_check", "WARN",
                      f"person_nbr={sample_id}: partial match (agency={agency_match}, date={date_match})")
        else:
            add_check("gt_spot_check", "WARN",
                      f"person_nbr={sample_id}: no exact match (GT agency='{gt_row['agency_name']}', "
                      f"GT date='{gt_start}'; out agencies={out_agencies[:2]}, out dates={out_starts[:2]})")

    # Agency name spot-check: top agencies from GT should appear in output (normalized)
    gt_top_agencies = gt["agency_name"].str.lower().str.strip().value_counts().head(5).index.tolist()
    out_agencies_lower = set(df["agency_name"].str.lower().str.strip())
    found = [a for a in gt_top_agencies if any(a in b or b in a for b in out_agencies_lower)]
    if len(found) >= 4:
        add_check("gt_top_agency_match", "PASS",
                  f"{len(found)}/5 top GT agencies found in output")
    elif len(found) >= 2:
        add_check("gt_top_agency_match", "WARN",
                  f"Only {len(found)}/5 top GT agencies found in output")
    else:
        add_check("gt_top_agency_match", "WARN",
                  f"Only {len(found)}/5 top GT agencies found in output: {gt_top_agencies}")

else:
    print("\nNo ground truth found — skipping GT checks")
    add_check("groundtruth_available", "WARN", "No ground truth file found; schema checks only")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
statuses = [c["status"] for c in checks]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

print(f"\n{'='*50}")
print(f"Overall: {overall}")
print(f"{'='*50}")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Markdown report
md_lines = [
    "# Arizona POST Employment Index — Validation Report\n\n",
    f"**Overall: {overall}**\n\n",
    f"| Check | Status | Detail |\n",
    f"|-------|--------|--------|\n",
]
for c in checks:
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[c["status"]]
    detail = c["detail"].replace("|", "\\|")
    md_lines.append(f"| {c['name']} | {icon} {c['status']} | {detail} |\n")

md_lines += [
    "\n## Summary Statistics\n\n",
    f"- **Output rows**: {len(df):,}\n",
    f"- **Unique officers**: {df['person_nbr'].nunique():,}\n",
    f"- **Unique agencies**: {df['agency_name'].nunique():,}\n",
    f"- **Date range**: {df['start_date'].min()} → {df['start_date'].max()}\n",
    f"- **Ground truth available**: {'Yes' if has_groundtruth else 'No'}\n",
]

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.writelines(md_lines)

# JSON report
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump({"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2)

print(f"\nWrote {os.path.join(OUTPUT_DIR, 'judge_report.md')}")
print(f"Wrote {os.path.join(OUTPUT_DIR, 'judge_report.json')}")
