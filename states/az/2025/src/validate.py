"""
Arizona 2025 — validate.py
Compares output/az_index.csv against groundtruth and schema rules.
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import re

import pandas as pd


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

OUTPUT_DIR = "output"
GROUNDTRUTH_PATH = "data/groundtruth/arizona_index.csv"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "az_index.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

checks = []  # list of {"name", "status", "detail"}


def check(name, status, detail):
    """Record a check result. status = PASS | WARN | FAIL"""
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------

if not os.path.exists(OUTPUT_PATH):
    check("output_exists", "FAIL", f"{OUTPUT_PATH} not found")
    overall = "FAIL"
    # Write minimal report and exit
    with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
        f.write(
            "# AZ 2025 Validation Report\n\n**FAIL** — output file not found.\n"
        )
    with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
        json.dump({"overall": "FAIL", "has_groundtruth": False}, f, indent=2)
    raise SystemExit(1)

df = pd.read_csv(OUTPUT_PATH, dtype=str)
check("output_exists", "PASS", f"Found {len(df):,} rows in {OUTPUT_PATH}")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------

REQUIRED_COLS = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]

missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
if missing_cols:
    check("required_columns", "FAIL", f"Missing columns: {missing_cols}")
else:
    check(
        "required_columns",
        "PASS",
        f"All required columns present: {REQUIRED_COLS}",
    )

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------

bad_pnbr = df[
    df["person_nbr"].isna()
    | (df["person_nbr"].str.strip() == "")
    | (df["person_nbr"] != df["person_nbr"].str.lower().str.strip())
]
if len(bad_pnbr) > 0:
    check(
        "person_nbr_format",
        "FAIL",
        f"{len(bad_pnbr):,} rows with bad person_nbr (not lowercase/stripped)",
    )
else:
    check(
        "person_nbr_format",
        "PASS",
        "All person_nbr are lowercase and non-empty",
    )

# ---------------------------------------------------------------------------
# start_date non-empty
# ---------------------------------------------------------------------------

empty_start = df[df["start_date"].isna() | (df["start_date"].str.strip() == "")]
if len(empty_start) > 0:
    check(
        "start_date_nonempty",
        "FAIL",
        f"{len(empty_start):,} rows with empty start_date",
    )
else:
    check("start_date_nonempty", "PASS", "No empty start_date values")

# ---------------------------------------------------------------------------
# Date format YYYY-MM-DD
# ---------------------------------------------------------------------------

date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def bad_dates(series, col_name):
    non_empty = series.dropna().loc[series.dropna() != ""]
    bad = non_empty[~non_empty.str.match(r"^\d{4}-\d{2}-\d{2}$")]
    return bad


bad_start = bad_dates(df["start_date"], "start_date")
bad_end = bad_dates(df["end_date"], "end_date")

if len(bad_start) > 0 or len(bad_end) > 0:
    check(
        "date_format",
        "FAIL",
        f"Bad date formats — start_date: {len(bad_start)}, end_date: {len(bad_end)}",
    )
else:
    check("date_format", "PASS", "All dates are YYYY-MM-DD or empty")

# ---------------------------------------------------------------------------
# No invalid date sentinels
# ---------------------------------------------------------------------------

bad_sentinels = []
for col in ["start_date", "end_date"]:
    if col in df.columns:
        bad = df[df[col].isin(["0000-00-00", "NaT", "None", "nan"])]
        bad_sentinels.append(len(bad))

if any(b > 0 for b in bad_sentinels):
    check(
        "no_date_sentinels",
        "FAIL",
        f"Found invalid date sentinels: {bad_sentinels}",
    )
else:
    check("no_date_sentinels", "PASS", "No invalid date sentinels found")

# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------

dupes = df.duplicated(subset=["person_nbr", "agency_name", "start_date"])
if dupes.sum() > 0:
    check(
        "no_duplicates",
        "WARN",
        f"{dupes.sum():,} duplicate rows on (person_nbr, agency_name, start_date)",
    )
else:
    check("no_duplicates", "PASS", "No duplicate rows found")

# ---------------------------------------------------------------------------
# agency_name quality check (no code prefixes)
# ---------------------------------------------------------------------------

code_prefix = df["agency_name"].str.match(r"^[A-Z]\d{3,}\s+", na=False)
if code_prefix.sum() > 0:
    check(
        "agency_no_code_prefix",
        "FAIL",
        f"{code_prefix.sum():,} agency names still have code prefixes",
    )
else:
    check("agency_no_code_prefix", "PASS", "No agency code prefixes found")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------

has_groundtruth = os.path.exists(GROUNDTRUTH_PATH)

if has_groundtruth:
    gt = pd.read_csv(GROUNDTRUTH_PATH, dtype=str)
    print(f"\nGroundtruth loaded: {len(gt):,} rows")

    # --- Row count comparison ---
    row_diff_pct = abs(len(df) - len(gt)) / max(len(gt), 1) * 100
    if row_diff_pct <= 5:
        check(
            "row_count",
            "PASS",
            f"Output {len(df):,} vs GT {len(gt):,} ({row_diff_pct:.1f}% diff)",
        )
    elif row_diff_pct <= 20:
        check(
            "row_count",
            "WARN",
            f"Output {len(df):,} vs GT {len(gt):,} ({row_diff_pct:.1f}% diff) — within tolerance",
        )
    else:
        check(
            "row_count",
            "WARN",
            f"Output {len(df):,} vs GT {len(gt):,} ({row_diff_pct:.1f}% diff) — larger than expected but may reflect data refresh",
        )

    # --- person_nbr overlap ---
    out_ids = set(df["person_nbr"].str.strip().str.lower())
    gt_ids = set(gt["person_nbr"].astype(str).str.strip().str.lower())
    overlap = len(out_ids & gt_ids)
    overlap_pct = overlap / max(len(gt_ids), 1) * 100
    if overlap_pct >= 70:
        check(
            "person_nbr_overlap",
            "PASS",
            f"{overlap:,} / {len(gt_ids):,} GT person_nbrs found in output ({overlap_pct:.1f}%)",
        )
    else:
        check(
            "person_nbr_overlap",
            "WARN",
            f"Only {overlap:,} / {len(gt_ids):,} GT person_nbrs in output ({overlap_pct:.1f}%)",
        )

    # --- agency name spot-check (normalize both to uppercase, strip spaces) ---
    def normalize_agency(s):
        if pd.isna(s):
            return ""
        return re.sub(r"\s+", " ", str(s).strip().upper())

    out_agencies = set(df["agency_name"].apply(normalize_agency))
    gt_agencies = set(gt["agency_name"].apply(normalize_agency))
    common = out_agencies & gt_agencies
    agency_overlap_pct = len(common) / max(len(gt_agencies), 1) * 100
    if agency_overlap_pct >= 50:
        check(
            "agency_name_overlap",
            "PASS",
            f"{len(common)} / {len(gt_agencies)} GT agency names match output ({agency_overlap_pct:.1f}%)",
        )
    else:
        check(
            "agency_name_overlap",
            "WARN",
            f"Only {len(common)} / {len(gt_agencies)} GT agency names match output ({agency_overlap_pct:.1f}%) — likely due to case/abbrev differences",
        )

    # --- Date value spot-check on shared person_nbrs ---
    shared_ids = list(out_ids & gt_ids)[:100]
    if shared_ids:
        out_sub = df[df["person_nbr"].isin(shared_ids)].copy()
        gt_sub = gt[
            gt["person_nbr"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(shared_ids)
        ].copy()
        gt_sub["person_nbr"] = (
            gt_sub["person_nbr"].astype(str).str.strip().str.lower()
        )

        # Normalize GT dates to YYYY-MM-DD
        def normalize_date(s):
            if pd.isna(s) or str(s).strip() == "":
                return ""
            try:
                return pd.to_datetime(str(s).strip(), errors="coerce").strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                return ""

        gt_sub["start_date_norm"] = gt_sub["start_date"].apply(normalize_date)
        gt_sub["end_date_norm"] = gt_sub["end_date"].apply(normalize_date)

        # Merge on person_nbr
        merged = out_sub.merge(
            gt_sub[["person_nbr", "start_date_norm", "end_date_norm"]],
            on="person_nbr",
            how="inner",
        )
        if len(merged) > 0:
            start_match = (
                merged["start_date"] == merged["start_date_norm"]
            ).mean()
            end_match = (
                merged["end_date"].fillna("")
                == merged["end_date_norm"].fillna("")
            ).mean()
            if start_match >= 0.5:
                check(
                    "date_value_spot_check",
                    "PASS",
                    f"start_date match: {start_match:.1%}, end_date match: {end_match:.1%}",
                )
            else:
                check(
                    "date_value_spot_check",
                    "WARN",
                    f"start_date match: {start_match:.1%}, end_date match: {end_match:.1%}",
                )

else:
    check(
        "groundtruth",
        "WARN",
        "No groundtruth directory found — skipping comparison checks",
    )

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

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------

md_lines = [
    "# AZ 2025 Validation Report\n",
    f"**Overall: {overall}**\n",
    f"- Output rows: {len(df):,}",
    f"- Has groundtruth: {has_groundtruth}\n",
    "## Check Results\n",
    "| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for c in checks:
    md_lines.append(f"| {c['name']} | {c['status']} | {c['detail']} |")

md_lines += [
    "\n## Sample Output Rows\n",
    "```",
    df.head(5).to_string(index=False),
    "```",
]

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines))

# ---------------------------------------------------------------------------
# Write judge_report.json
# ---------------------------------------------------------------------------

with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump(
        {"overall": overall, "has_groundtruth": has_groundtruth}, f, indent=2
    )

print(f"\n{'=' * 50}")
print(f"Overall: {overall}")
print(f"Report written to {OUTPUT_DIR}/judge_report.md and judge_report.json")
