"""
Validation script for California employment index.
Compares output/ca_index.csv against data/groundtruth/ca-index.csv.
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import re

import pandas as pd


OUTPUT_DIR = "output"
GT_DIR = "data/groundtruth"
INDEX_FILE = os.path.join(OUTPUT_DIR, "ca_index.csv")
GT_FILE = os.path.join(GT_DIR, "ca-index.csv")


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_csv(path, **kwargs):
    return pd.read_csv(path, dtype=str, low_memory=False, **kwargs)


results = []  # list of (check_name, status, detail)


def record(name, status, detail):
    results.append((name, status, detail))
    print(f"[{status}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Check: output file exists
# ---------------------------------------------------------------------------
if not os.path.exists(INDEX_FILE):
    record("output_exists", "FAIL", f"{INDEX_FILE} not found")
    out = pd.DataFrame()
else:
    out = load_csv(INDEX_FILE)
    record("output_exists", "PASS", f"{len(out)} rows loaded")

# ---------------------------------------------------------------------------
# Check: required columns
# ---------------------------------------------------------------------------
REQUIRED_COLS = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]
if len(out) > 0:
    missing = [c for c in REQUIRED_COLS if c not in out.columns]
    if missing:
        record("required_columns", "FAIL", f"Missing: {missing}")
    else:
        record(
            "required_columns",
            "PASS",
            f"All required columns present: {REQUIRED_COLS}",
        )

# ---------------------------------------------------------------------------
# Check: person_nbr format (lowercase, no leading/trailing whitespace)
# ---------------------------------------------------------------------------
if len(out) > 0:
    nbr = out["person_nbr"].fillna("")
    has_upper = (nbr != nbr.str.lower()).sum()
    has_whitespace = (nbr != nbr.str.strip()).sum()
    if has_upper > 0 or has_whitespace > 0:
        record(
            "person_nbr_format",
            "FAIL",
            f"{has_upper} rows with uppercase, {has_whitespace} rows with whitespace",
        )
    else:
        record(
            "person_nbr_format", "PASS", "All person_nbr lowercase and trimmed"
        )

# ---------------------------------------------------------------------------
# Check: start_date not empty
# ---------------------------------------------------------------------------
if len(out) > 0:
    empty_start = (out["start_date"].fillna("") == "").sum()
    if empty_start > 0:
        record(
            "start_date_not_empty",
            "FAIL",
            f"{empty_start} rows with empty start_date",
        )
    else:
        record("start_date_not_empty", "PASS", "No empty start_date values")

# ---------------------------------------------------------------------------
# Check: date format YYYY-MM-DD
# ---------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
if len(out) > 0:
    invalid_starts = (
        out["start_date"]
        .fillna("")
        .apply(lambda x: bool(x) and not DATE_RE.match(x))
        .sum()
    )
    invalid_ends = (
        out["end_date"]
        .fillna("")
        .apply(lambda x: bool(x) and not DATE_RE.match(x))
        .sum()
    )
    if invalid_starts > 0 or invalid_ends > 0:
        record(
            "date_format",
            "FAIL",
            f"{invalid_starts} invalid start_date, {invalid_ends} invalid end_date",
        )
    else:
        record(
            "date_format", "PASS", "All non-empty dates in YYYY-MM-DD format"
        )

# ---------------------------------------------------------------------------
# Check: no fully duplicate rows
# ---------------------------------------------------------------------------
if len(out) > 0:
    dupes = out.duplicated(
        subset=["person_nbr", "agency_name", "start_date"]
    ).sum()
    if dupes > 0:
        record(
            "no_duplicates",
            "WARN",
            f"{dupes} duplicate (person_nbr, agency_name, start_date) rows",
        )
    else:
        record("no_duplicates", "PASS", "No duplicate rows")

# ---------------------------------------------------------------------------
# Check: agency_name has no raw code prefixes (like "G1720 ...")
# ---------------------------------------------------------------------------
if len(out) > 0:
    code_prefix = (
        out["agency_name"].fillna("").str.match(r"^[A-Z]\d{4}\s").sum()
    )
    if code_prefix > 0:
        record(
            "agency_no_code_prefix",
            "WARN",
            f"{code_prefix} agency names appear to have code prefixes",
        )
    else:
        record(
            "agency_no_code_prefix", "PASS", "No agency code prefixes detected"
        )

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------
has_groundtruth = os.path.exists(GT_FILE)

if has_groundtruth:
    gt = load_csv(GT_FILE)
    record("groundtruth_loaded", "PASS", f"{len(gt)} rows in ground truth")

    # Row count comparison
    row_diff_pct = abs(len(out) - len(gt)) / max(len(gt), 1) * 100
    row_status = (
        "PASS"
        if row_diff_pct <= 5
        else "WARN"
        if row_diff_pct <= 15
        else "FAIL"
    )
    record(
        "row_count",
        row_status,
        f"Output={len(out)}, GT={len(gt)}, diff={row_diff_pct:.1f}%",
    )

    # LEO vs corrections breakdown — use type column if present, else use dash heuristic
    if "type" in out.columns:
        out_leo = out[out["type"] == "POLICE"]
        out_corr = out[out["type"] == "CORRECTIONS"]
    else:
        out_leo = out[out["person_nbr"].str.contains("-", na=False)]
        out_corr = out[~out["person_nbr"].str.contains("-", na=False)]
    gt_leo = gt[gt["person_nbr"].str.contains("-", na=False)]
    gt_corr = gt[~gt["person_nbr"].str.contains("-", na=False)]

    leo_diff = abs(len(out_leo) - len(gt_leo)) / max(len(gt_leo), 1) * 100
    corr_diff = abs(len(out_corr) - len(gt_corr)) / max(len(gt_corr), 1) * 100

    leo_status = (
        "PASS" if leo_diff <= 5 else "WARN" if leo_diff <= 15 else "FAIL"
    )
    corr_status = (
        "PASS" if corr_diff <= 5 else "WARN" if corr_diff <= 15 else "FAIL"
    )

    record(
        "leo_row_count",
        leo_status,
        f"LEO Output={len(out_leo)}, GT={len(gt_leo)}, diff={leo_diff:.1f}%",
    )
    record(
        "corrections_row_count",
        corr_status,
        f"Corrections Output={len(out_corr)}, GT={len(gt_corr)}, diff={corr_diff:.1f}%",
    )

    # Spot-check: agency name accuracy for LEO records
    # Compare first 500 matching records (exclude POST ID Withheld)
    gt_leo_upper = gt_leo.copy()
    gt_leo_upper["person_nbr_lower"] = gt_leo_upper["person_nbr"].str.lower()
    out_leo_sample = out_leo[
        ~out_leo["person_nbr"].str.lower().str.contains("withheld", na=False)
    ].head(500)
    matched = out_leo_sample.merge(
        gt_leo_upper[["person_nbr_lower", "start_date", "agency_name"]].rename(
            columns={
                "person_nbr_lower": "person_nbr",
                "agency_name": "gt_agency",
            }
        ),
        on=["person_nbr", "start_date"],
        how="inner",
    )
    if len(matched) > 0:
        agency_match_pct = (
            matched["agency_name"] == matched["gt_agency"]
        ).mean() * 100
        agency_status = (
            "PASS"
            if agency_match_pct >= 90
            else "WARN"
            if agency_match_pct >= 75
            else "FAIL"
        )
        record(
            "agency_name_accuracy",
            agency_status,
            f"{agency_match_pct:.1f}% agency names match groundtruth "
            f"({len(matched)} matched rows checked)",
        )
    else:
        record(
            "agency_name_accuracy",
            "WARN",
            "Could not match rows for agency spot-check",
        )

    # Spot-check: first/last name accuracy
    if len(matched) > 0:
        # Normalize: strip and compare case-insensitively
        fn_match = (
            matched["first_name"].str.strip().str.upper()
            == matched["gt_agency"]
            .apply(lambda x: "")
            .str.upper()  # placeholder
        )
        # Compare with GT first_name
        gt_names = gt_leo_upper[
            ["person_nbr_lower", "start_date", "first_name", "last_name"]
        ].rename(
            columns={
                "person_nbr_lower": "person_nbr",
                "first_name": "gt_first",
                "last_name": "gt_last",
            }
        )
        matched2 = out_leo_sample.merge(
            gt_names, on=["person_nbr", "start_date"], how="inner"
        )
        if len(matched2) > 0:
            fn_acc = (
                matched2["first_name"].str.strip().str.upper()
                == matched2["gt_first"].str.strip().str.upper()
            ).mean() * 100
            ln_acc = (
                matched2["last_name"].str.strip().str.upper()
                == matched2["gt_last"].str.strip().str.upper()
            ).mean() * 100
            name_status = (
                "PASS"
                if min(fn_acc, ln_acc) >= 90
                else "WARN"
                if min(fn_acc, ln_acc) >= 75
                else "FAIL"
            )
            record(
                "name_accuracy",
                name_status,
                f"first_name {fn_acc:.1f}%, last_name {ln_acc:.1f}% match groundtruth",
            )
        else:
            record(
                "name_accuracy",
                "WARN",
                "Could not match rows for name spot-check",
            )

    # Spot-check: separation_reason
    if "separation_reason" in out.columns and "separation_reason" in gt.columns:
        gt_sep = gt_leo_upper[
            ["person_nbr_lower", "start_date", "separation_reason"]
        ].rename(
            columns={
                "person_nbr_lower": "person_nbr",
                "separation_reason": "gt_sep",
            }
        )
        matched3 = out_leo_sample.merge(
            gt_sep, on=["person_nbr", "start_date"], how="inner"
        )
        if len(matched3) > 0:
            both_filled = matched3[
                matched3["separation_reason"].fillna("").ne("")
                & matched3["gt_sep"].fillna("").ne("")
            ]
            if len(both_filled) > 0:
                sep_acc = (
                    both_filled["separation_reason"].str.strip()
                    == both_filled["gt_sep"].str.strip()
                ).mean() * 100
                sep_status = (
                    "PASS"
                    if sep_acc >= 90
                    else "WARN"
                    if sep_acc >= 75
                    else "FAIL"
                )
                record(
                    "separation_reason_accuracy",
                    sep_status,
                    f"{sep_acc:.1f}% separation_reason matches groundtruth "
                    f"({len(both_filled)} rows with data in both)",
                )

    # Spot-check corrections agency format
    out_corr_sample = out_corr.head(200)
    # GT format: "NNN: NAME"
    gt_format_match = out_corr_sample["agency_name"].str.match(r"^\d{3}:").sum()
    corr_agency_pct = gt_format_match / max(len(out_corr_sample), 1) * 100
    corr_agency_status = "PASS" if corr_agency_pct >= 90 else "WARN"
    record(
        "corrections_agency_format",
        corr_agency_status,
        f"{corr_agency_pct:.1f}% corrections agency names match 'NNN: NAME' format",
    )

else:
    record(
        "groundtruth",
        "WARN",
        "No groundtruth found — skipping comparison checks",
    )

# ---------------------------------------------------------------------------
# Schema type checks
# ---------------------------------------------------------------------------
if len(out) > 0:
    # Type column if present
    if "type" in out.columns:
        valid_types = {"POLICE", "CORRECTIONS"}
        bad_types = (~out["type"].isin(valid_types)).sum()
        if bad_types > 0:
            record(
                "type_column",
                "WARN",
                f"{bad_types} rows with unexpected type values",
            )
        else:
            record(
                "type_column",
                "PASS",
                f"All type values are valid: {valid_types}",
            )

    # No person_nbr that is NaN / empty
    empty_nbr = (out["person_nbr"].fillna("") == "").sum()
    if empty_nbr > 0:
        record(
            "person_nbr_not_empty",
            "FAIL",
            f"{empty_nbr} rows with empty person_nbr",
        )
    else:
        record("person_nbr_not_empty", "PASS", "No empty person_nbr values")

    # Summary statistics
    leo_pct = out["person_nbr"].str.contains("-", na=False).mean() * 100
    record(
        "data_composition",
        "PASS",
        f"LEO: {leo_pct:.1f}%, Corrections: {100 - leo_pct:.1f}%",
    )

# ---------------------------------------------------------------------------
# Determine overall status
# ---------------------------------------------------------------------------
statuses = [s for _, s, _ in results]
if "FAIL" in statuses:
    overall = "FAIL"
elif "WARN" in statuses:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

md_lines = [
    "# California 2025 — Validation Report",
    "",
    f"**Overall: {overall}**",
    f"**Has groundtruth: {has_groundtruth}**",
    "",
    "## Check Results",
    "",
    "| Check | Status | Detail |",
    "|-------|--------|--------|",
]
for name, status, detail in results:
    # Escape pipe chars in detail
    detail_escaped = detail.replace("|", "\\|")
    md_lines.append(f"| {name} | {status} | {detail_escaped} |")

md_lines += [
    "",
    "## Summary",
    "",
    f"- Total checks: {len(results)}",
    f"- PASS: {statuses.count('PASS')}",
    f"- WARN: {statuses.count('WARN')}",
    f"- FAIL: {statuses.count('FAIL')}",
    "",
]

if len(out) > 0:
    md_lines += [
        "## Output Stats",
        "",
        f"- Total rows: {len(out):,}",
        f"- Unique person_nbr: {out['person_nbr'].nunique():,}",
        f"- Unique agencies: {out['agency_name'].nunique():,}",
        f"- Date range: {out['start_date'].min()} to {out['start_date'].max()}",
        "",
    ]

report_md = "\n".join(md_lines)
with open(os.path.join(OUTPUT_DIR, "judge_report.md"), "w") as f:
    f.write(report_md)
print("\nWrote judge_report.md")

# ---------------------------------------------------------------------------
# Write judge_report.json
# ---------------------------------------------------------------------------
report_json = {
    "overall": overall,
    "has_groundtruth": has_groundtruth,
    "checks": [
        {"name": name, "status": status, "detail": detail}
        for name, status, detail in results
    ],
}
with open(os.path.join(OUTPUT_DIR, "judge_report.json"), "w") as f:
    json.dump(report_json, f, indent=2)
print("Wrote judge_report.json")
print(f"\nOverall: {overall}")
