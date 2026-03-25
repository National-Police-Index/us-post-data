"""
Validate the California POST cleaned output against ground truth and schema rules.
Writes:
  output/judge_report.md   — human-readable report
  output/judge_report.json — machine-readable summary
"""
import json
import os
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

# ---------------------------------------------------------------------------
# Load output
# ---------------------------------------------------------------------------
output_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
if not os.path.exists(output_path):
    print(f"ERROR: Output file not found: {output_path}", file=sys.stderr)
    sys.exit(1)

df = pd.read_csv(output_path, low_memory=False)
df = df.fillna("")

# ---------------------------------------------------------------------------
# Load groundtruth if available
# ---------------------------------------------------------------------------
gt_path = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")
has_groundtruth = os.path.exists(gt_path)
if has_groundtruth:
    gt = pd.read_csv(gt_path, low_memory=False)
    gt = gt.fillna("")
else:
    gt = None

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
checks = []  # list of {name, status, detail}

def add_check(name, passed, warn=False, detail=""):
    if passed:
        status = "PASS"
    elif warn:
        status = "WARN"
    else:
        status = "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}: {detail}")


print("=== CA 2025 Validation ===")
print(f"Output rows: {len(df)}")
print(f"Has groundtruth: {has_groundtruth}")
print()

# ---- Schema checks ----
print("--- Schema checks ---")

REQUIRED_COLS = ["person_nbr", "first_name", "last_name", "agency_name", "start_date", "end_date"]
missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
add_check(
    "Required columns present",
    len(missing_cols) == 0,
    detail=f"Missing: {missing_cols}" if missing_cols else "All present",
)

# start_date not empty
empty_start = (df["start_date"] == "").sum() if "start_date" in df.columns else len(df)
add_check(
    "No empty start_date",
    empty_start == 0,
    detail=f"{empty_start} empty values",
)

# person_nbr format: lowercase, no whitespace
if "person_nbr" in df.columns:
    nbr_ws = df["person_nbr"].str.contains(r"^\s|\s$", na=False).sum()
    add_check(
        "person_nbr no leading/trailing whitespace",
        nbr_ws == 0,
        detail=f"{nbr_ws} values with whitespace",
    )
    # person_nbr should be lowercase (LEO IDs are uppercase letters + hyphens, corrections are numeric)
    # Just check no extra whitespace and not null
    nbr_null = (df["person_nbr"] == "").sum()
    add_check(
        "person_nbr not empty",
        nbr_null == 0,
        detail=f"{nbr_null} empty values",
    )

# Date format YYYY-MM-DD or empty
import re

def check_date_format(series):
    non_empty = series[series != ""]
    bad = non_empty[~non_empty.str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)]
    return bad

if "start_date" in df.columns:
    bad_starts = check_date_format(df["start_date"])
    add_check(
        "start_date format YYYY-MM-DD",
        len(bad_starts) == 0,
        detail=f"{len(bad_starts)} malformed values" if bad_starts.any() else "All valid",
    )

if "end_date" in df.columns:
    bad_ends = check_date_format(df["end_date"])
    add_check(
        "end_date format YYYY-MM-DD or empty",
        len(bad_ends) == 0,
        detail=f"{len(bad_ends)} malformed values" if bad_ends.any() else "All valid",
    )

# No fully duplicate rows
dupe_mask = df.duplicated(subset=["person_nbr", "agency_name", "start_date"])
add_check(
    "No duplicate (person_nbr, agency_name, start_date)",
    not dupe_mask.any(),
    warn=True,
    detail=f"{dupe_mask.sum()} duplicates" if dupe_mask.any() else "None found",
)

# agency_name not empty
if "agency_name" in df.columns:
    empty_agency = (df["agency_name"] == "").sum()
    pct_empty = empty_agency / len(df) * 100
    add_check(
        "agency_name not excessively empty",
        pct_empty < 5.0,
        warn=True,
        detail=f"{empty_agency} empty ({pct_empty:.1f}%)",
    )

# first_name and last_name not excessively empty
for col in ["first_name", "last_name"]:
    if col in df.columns:
        empty_count = (df[col] == "").sum()
        pct = empty_count / len(df) * 100
        add_check(
            f"{col} not excessively empty",
            pct < 10.0,
            warn=True,
            detail=f"{empty_count} empty ({pct:.1f}%)",
        )

print()
print("--- Groundtruth comparison ---")

if has_groundtruth and gt is not None:
    # Row count comparison
    out_count = len(df)
    gt_count = len(gt)
    pct_diff = abs(out_count - gt_count) / gt_count * 100
    add_check(
        "Row count within 15% of groundtruth",
        pct_diff <= 15.0,
        warn=pct_diff <= 25.0,
        detail=f"Output: {out_count}, GT: {gt_count}, diff: {pct_diff:.1f}%",
    )

    # LEO row count comparison (person_nbr contains '-')
    leo_out = df[df["person_nbr"].str.contains("-", na=False, regex=False)]
    leo_gt = gt[gt["person_nbr"].str.contains("-", na=False, regex=False)]
    leo_pct_diff = abs(len(leo_out) - len(leo_gt)) / max(len(leo_gt), 1) * 100
    add_check(
        "LEO row count matches groundtruth exactly",
        len(leo_out) == len(leo_gt),
        warn=leo_pct_diff <= 5.0,
        detail=f"Output LEO: {len(leo_out)}, GT LEO: {len(leo_gt)}",
    )

    # Corrections row count comparison
    corr_out = df[df["person_nbr"].str.match(r"^\d+$", na=False)]
    corr_gt = gt[gt["person_nbr"].str.match(r"^\d+$", na=False)]
    corr_pct_diff = abs(len(corr_out) - len(corr_gt)) / max(len(corr_gt), 1) * 100
    add_check(
        "Corrections row count within 15% of groundtruth",
        corr_pct_diff <= 15.0,
        warn=corr_pct_diff <= 25.0,
        detail=f"Output: {len(corr_out)}, GT: {len(corr_gt)}, diff: {corr_pct_diff:.1f}%",
    )

    # Spot check: first 5 LEO rows (by person_nbr + start_date)
    if len(leo_out) > 0 and len(leo_gt) > 0:
        # Check that first officer's stints are in output
        sample_nbr = leo_gt["person_nbr"].iloc[0]
        out_sample = leo_out[leo_out["person_nbr"] == sample_nbr].sort_values("start_date")
        gt_sample = leo_gt[leo_gt["person_nbr"] == sample_nbr].sort_values("start_date")

        if len(out_sample) > 0:
            add_check(
                "Sample LEO officer found in output",
                True,
                detail=f"person_nbr={sample_nbr}, rows: output={len(out_sample)}, gt={len(gt_sample)}",
            )
            # Check first agency matches
            if len(out_sample) > 0 and len(gt_sample) > 0:
                out_agency = out_sample.iloc[0]["agency_name"]
                gt_agency = gt_sample.iloc[0]["agency_name"]
                agencies_match = out_agency.strip().upper() == gt_agency.strip().upper()
                add_check(
                    "Sample LEO officer first agency matches",
                    agencies_match,
                    warn=True,
                    detail=f"Output: '{out_agency}' vs GT: '{gt_agency}'",
                )
        else:
            add_check(
                "Sample LEO officer found in output",
                False,
                warn=True,
                detail=f"person_nbr={sample_nbr} not found in output",
            )

    # Check agency name quality (no raw abbreviations)
    sample_agencies = df["agency_name"].dropna().unique()[:20]
    has_raw_pd = any(a.endswith(" PD") for a in sample_agencies if isinstance(a, str))
    has_raw_so = any(a.endswith(" SO") for a in sample_agencies if isinstance(a, str))
    add_check(
        "Agency names expanded (no raw PD/SO abbreviations in sample)",
        not (has_raw_pd or has_raw_so),
        warn=True,
        detail=f"Raw PD: {has_raw_pd}, Raw SO: {has_raw_so}",
    )

    # Unique person count
    out_unique = df["person_nbr"].nunique()
    gt_unique = gt["person_nbr"].nunique()
    person_pct = abs(out_unique - gt_unique) / max(gt_unique, 1) * 100
    add_check(
        "Unique person count within 5% of groundtruth",
        person_pct <= 5.0,
        warn=person_pct <= 15.0,
        detail=f"Output: {out_unique}, GT: {gt_unique}, diff: {person_pct:.1f}%",
    )

    # Separation reason spot check (LEO only)
    if "separation_reason" in df.columns:
        out_leo = df[df["person_nbr"].str.contains("-", na=False, regex=False)]
        out_resigned = (out_leo["separation_reason"] == "Resigned").sum()
        gt_resigned = (leo_gt["separation_reason"] == "Resigned").sum() if "separation_reason" in leo_gt.columns else 0
        add_check(
            "Separation reason 'Resigned' count plausible",
            out_resigned > 100000,
            warn=out_resigned > 50000,
            detail=f"Output Resigned: {out_resigned}, GT Resigned: {gt_resigned}",
        )

else:
    add_check("Groundtruth comparison", True, detail="Groundtruth not available — skipped")

print()
print("--- Data quality spot checks ---")

# Check for 'POST ID Withheld' in person_nbr
withheld_count = df["person_nbr"].str.lower().str.contains("withheld", na=False).sum()
add_check(
    "Withheld person_nbr records present (expected)",
    True,
    detail=f"{withheld_count} records with 'Withheld' in person_nbr",
)

# Corrections agency name format check (should have 'NNN: ' prefix)
corr_rows = df[df["person_nbr"].str.match(r"^\d+$", na=False)]
if len(corr_rows) > 0:
    code_prefix = corr_rows["agency_name"].str.match(r"^\d{3}:", na=False).mean()
    add_check(
        "Corrections agency names have NNN: prefix",
        code_prefix > 0.8,
        warn=code_prefix > 0.5,
        detail=f"{code_prefix:.1%} have prefix",
    )

# LEO agency names should not start with numeric code
leo_rows = df[df["person_nbr"].str.contains("-", na=False, regex=False)]
if len(leo_rows) > 0:
    leo_no_code = ~leo_rows["agency_name"].str.match(r"^\d", na=False)
    add_check(
        "LEO agency names don't start with numeric code",
        leo_no_code.mean() > 0.99,
        detail=f"{leo_no_code.mean():.1%} pass",
    )

# Date range sanity
if "start_date" in df.columns:
    non_empty_starts = df["start_date"][df["start_date"] != ""]
    try:
        min_date = non_empty_starts.min()
        max_date = non_empty_starts.max()
        # Dates can go back to early 1900s for historical LEO data; just check not future-dated
        add_check(
            "Date range sanity",
            "1900" <= min_date[:4] and max_date[:4] <= "2030",
            warn="1900" <= min_date[:4] and max_date[:4] <= "2030",
            detail=f"start_date range: {min_date} to {max_date}",
        )
    except Exception as e:
        add_check("Date range sanity", False, warn=True, detail=str(e))

# ---------------------------------------------------------------------------
# Compute overall status
# ---------------------------------------------------------------------------
fail_count = sum(1 for c in checks if c["status"] == "FAIL")
warn_count = sum(1 for c in checks if c["status"] == "WARN")
pass_count = sum(1 for c in checks if c["status"] == "PASS")

if fail_count > 0:
    overall = "FAIL"
elif warn_count > 0:
    overall = "WARN"
else:
    overall = "PASS"

print()
print(f"=== RESULT: {overall} ===")
print(f"PASS: {pass_count}, WARN: {warn_count}, FAIL: {fail_count}")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Markdown report
md_lines = [
    "# California 2025 — Judge Report",
    "",
    f"**Overall: {overall}**",
    f"- PASS: {pass_count}",
    f"- WARN: {warn_count}",
    f"- FAIL: {fail_count}",
    "",
    f"Has groundtruth: {has_groundtruth}",
    f"Output rows: {len(df)}",
    "",
    "## Check Results",
    "",
    "| Status | Check | Detail |",
    "|--------|-------|--------|",
]
for c in checks:
    md_lines.append(f"| {c['status']} | {c['name']} | {c['detail']} |")

md_lines += [
    "",
    "## Column Summary",
    "",
    f"Columns: {', '.join(df.columns.tolist())}",
    f"Rows: {len(df)}",
    f"Unique person_nbr: {df['person_nbr'].nunique() if 'person_nbr' in df.columns else 'N/A'}",
    "",
    "## Sample Rows",
    "",
    "```",
    df.head(5).to_string(index=False),
    "```",
]

with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write("\n".join(md_lines))

# JSON report
json_report = {
    "overall": overall,
    "has_groundtruth": has_groundtruth,
    "pass": pass_count,
    "warn": warn_count,
    "fail": fail_count,
    "checks": checks,
}
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump(json_report, f, indent=2)

print(f"Wrote {os.path.join(OUTPUT_DIR, 'judge_report.md')}")
print(f"Wrote {os.path.join(OUTPUT_DIR, 'judge_report.json')}")

if overall == "FAIL":
    sys.exit(1)
