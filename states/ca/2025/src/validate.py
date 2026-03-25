"""
Validation script for California officer index (ca_index.csv).
Writes output/judge_report.md and output/judge_report.json.
"""

import json
import os
import re
import sys

import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

# ---------------------------------------------------------------------------
# Load output file
# ---------------------------------------------------------------------------

index_path = os.path.join(OUTPUT_DIR, "ca_index.csv")
if not os.path.exists(index_path):
    print("ERROR: output/ca_index.csv not found.")
    sys.exit(1)

df = pd.read_csv(index_path, low_memory=False, keep_default_na=False)

# Load groundtruth if available
gt_path = os.path.join(GROUNDTRUTH_DIR, "ca-index.csv")
has_groundtruth = os.path.exists(gt_path)
if has_groundtruth:
    gt = pd.read_csv(gt_path, low_memory=False, keep_default_na=False)
    print(f"Groundtruth loaded: {len(gt)} rows")

print(f"Output loaded: {len(df)} rows")

# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

checks = []  # list of (check_name, status, message)


def add_check(name, passed, message, warn_only=False):
    if passed:
        status = "PASS"
    elif warn_only:
        status = "WARN"
    else:
        status = "FAIL"
    checks.append((name, status, message))
    print(f"  [{status}] {name}: {message}")


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------

print("\n--- Schema Checks ---")
required_cols = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
missing_cols = [c for c in required_cols if c not in df.columns]
add_check(
    "required_columns",
    len(missing_cols) == 0,
    f"All required columns present" if not missing_cols else f"Missing: {missing_cols}"
)

# ---------------------------------------------------------------------------
# person_nbr format
# ---------------------------------------------------------------------------

print("\n--- person_nbr Checks ---")
nbr_null = (df['person_nbr'] == '').sum()
add_check(
    "person_nbr_not_empty",
    nbr_null == 0,
    f"{nbr_null} empty person_nbr values"
)

# Check lowercase for LEO (alpha IDs like A52-V94) and numeric for corrections
leo_mask = ~df['person_nbr'].str.match(r'^\d+$', na=False)
corr_mask = df['person_nbr'].str.match(r'^\d+$', na=False)
add_check(
    "person_nbr_leo_format",
    True,  # informational
    f"LEO records: {leo_mask.sum()}, Corrections records: {corr_mask.sum()}"
)

# Check for leading/trailing whitespace
ws_count = df['person_nbr'].str.match(r'^\s|\s$').sum()
add_check(
    "person_nbr_no_whitespace",
    ws_count == 0,
    f"{ws_count} person_nbr values with leading/trailing whitespace"
)

# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------

print("\n--- Date Checks ---")
date_pattern = r'^\d{4}-\d{2}-\d{2}$'

bad_start = df[~df['start_date'].str.match(date_pattern, na=False)]
add_check(
    "start_date_format",
    len(bad_start) == 0,
    f"{len(bad_start)} rows with bad start_date format"
)

empty_start = (df['start_date'] == '').sum()
add_check(
    "start_date_not_empty",
    empty_start == 0,
    f"{empty_start} rows with empty start_date"
)

bad_end = df[
    (df['end_date'] != '') &
    (~df['end_date'].str.match(date_pattern, na=False))
]
add_check(
    "end_date_format",
    len(bad_end) == 0,
    f"{len(bad_end)} rows with bad end_date format (non-empty, non-YYYY-MM-DD)"
)

# Check for invalid date strings
for bad_val in ['0000-00-00', 'NaT', 'None', 'nan']:
    bad_count = (df['start_date'] == bad_val).sum() + (df['end_date'] == bad_val).sum()
    if bad_count > 0:
        add_check(
            f"no_{bad_val}_dates",
            False,
            f"{bad_count} occurrences of '{bad_val}' in date columns"
        )

# ---------------------------------------------------------------------------
# Agency name checks
# ---------------------------------------------------------------------------

print("\n--- Agency Name Checks ---")
empty_agency = (df['agency_name'] == '').sum()
add_check(
    "agency_name_not_empty",
    empty_agency == 0,
    f"{empty_agency} rows with empty agency_name"
)

# Check for agency code prefixes (e.g. "G1720 DEKALB...")
code_prefix = df['agency_name'].str.match(r'^[A-Z]\d{3,}\s+', na=False).sum()
add_check(
    "no_agency_code_prefix",
    code_prefix == 0,
    f"{code_prefix} rows with agency code prefix in agency_name"
)

# Check for non-agency values
non_agency = {'application denied', 'application purged', 'pending', 'unknown', 'n/a'}
bad_agency = df[df['agency_name'].str.lower().isin(non_agency)]
add_check(
    "no_non_agency_values",
    len(bad_agency) == 0,
    f"{len(bad_agency)} rows with non-agency values in agency_name"
)

# Sample agency names - check they look reasonable
unique_agencies = df['agency_name'].nunique()
add_check(
    "agency_name_variety",
    unique_agencies > 100,
    f"{unique_agencies} unique agency names"
)

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------

print("\n--- Duplicate Checks ---")
dupes = df.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
add_check(
    "no_duplicates",
    dupes == 0,
    f"{dupes} duplicate rows (person_nbr + agency_name + start_date)"
)

# ---------------------------------------------------------------------------
# Name quality checks
# ---------------------------------------------------------------------------

print("\n--- Name Quality Checks ---")
empty_last = (df['last_name'] == '').sum()
empty_first = (df['first_name'] == '').sum()
add_check(
    "last_name_fill_rate",
    empty_last / len(df) < 0.01,
    f"{empty_last} empty last_name ({empty_last/len(df)*100:.2f}%)",
    warn_only=(empty_last / len(df) < 0.05)
)
add_check(
    "first_name_fill_rate",
    empty_first / len(df) < 0.01,
    f"{empty_first} empty first_name ({empty_first/len(df)*100:.2f}%)",
    warn_only=(empty_first / len(df) < 0.05)
)

# ---------------------------------------------------------------------------
# Row count checks
# ---------------------------------------------------------------------------

print("\n--- Row Count Checks ---")
add_check(
    "row_count_positive",
    len(df) > 0,
    f"Total rows: {len(df)}"
)

add_check(
    "leo_corrections_both_present",
    (df['type'] == 'POLICE').sum() > 0 and (df['type'] == 'CORRECTIONS').sum() > 0,
    f"LEO: {(df['type'] == 'POLICE').sum()}, Corrections: {(df['type'] == 'CORRECTIONS').sum()}"
)

# ---------------------------------------------------------------------------
# Groundtruth comparison checks
# ---------------------------------------------------------------------------

if has_groundtruth:
    print("\n--- Groundtruth Comparison ---")

    gt_rows = len(gt)
    out_rows = len(df)
    row_diff_pct = abs(out_rows - gt_rows) / gt_rows * 100
    add_check(
        "row_count_vs_groundtruth",
        row_diff_pct <= 5,
        f"Output: {out_rows}, GT: {gt_rows}, diff: {row_diff_pct:.1f}%",
        warn_only=(row_diff_pct <= 15)
    )

    # LEO row counts
    gt_leo = gt[~gt['person_nbr'].str.match(r'^\d+$', na=False)]
    out_leo = df[~df['person_nbr'].str.match(r'^\d+$', na=False)]
    leo_diff_pct = abs(len(out_leo) - len(gt_leo)) / max(len(gt_leo), 1) * 100
    add_check(
        "leo_row_count_vs_groundtruth",
        leo_diff_pct <= 5,
        f"LEO Output: {len(out_leo)}, GT: {len(gt_leo)}, diff: {leo_diff_pct:.1f}%",
        warn_only=(leo_diff_pct <= 15)
    )

    # Corrections row counts
    gt_corr = gt[gt['person_nbr'].str.match(r'^\d+$', na=False)]
    out_corr = df[df['person_nbr'].str.match(r'^\d+$', na=False)]
    corr_diff_pct = abs(len(out_corr) - len(gt_corr)) / max(len(gt_corr), 1) * 100
    add_check(
        "corr_row_count_vs_groundtruth",
        corr_diff_pct <= 5,
        f"Corrections Output: {len(out_corr)}, GT: {len(gt_corr)}, diff: {corr_diff_pct:.1f}%",
        warn_only=(corr_diff_pct <= 20)
    )

    # Value spot-checks: sample 50 GT rows and check they're in our output
    print("\n  Spot-checking GT records in output...")
    gt_sample = gt.sample(min(50, len(gt)), random_state=42)
    found = 0
    agency_match = 0
    name_match = 0
    for _, row in gt_sample.iterrows():
        pnbr = str(row['person_nbr']).strip()
        start = str(row['start_date']).strip()
        out_match = df[(df['person_nbr'] == pnbr) & (df['start_date'] == start)]
        if len(out_match) > 0:
            found += 1
            m = out_match.iloc[0]
            # Check agency name match
            gt_agency = str(row.get('agency_name', '')).strip().upper()
            out_agency = str(m.get('agency_name', '')).strip().upper()
            if gt_agency == out_agency:
                agency_match += 1
            # Check name match
            gt_last = str(row.get('last_name', '')).strip().upper()
            out_last = str(m.get('last_name', '')).strip().upper()
            if gt_last and out_last and gt_last == out_last:
                name_match += 1

    found_pct = found / len(gt_sample) * 100
    add_check(
        "gt_records_found_in_output",
        found_pct >= 90,
        f"{found}/{len(gt_sample)} GT records found in output ({found_pct:.0f}%)",
        warn_only=(found_pct >= 80)
    )

    if found > 0:
        agency_pct = agency_match / found * 100
        add_check(
            "agency_name_match_rate",
            agency_pct >= 85,
            f"Agency name match: {agency_match}/{found} ({agency_pct:.0f}%)",
            warn_only=(agency_pct >= 70)
        )

        name_pct = name_match / found * 100
        add_check(
            "last_name_match_rate",
            name_pct >= 85,
            f"Last name match: {name_match}/{found} ({name_pct:.0f}%)",
            warn_only=(name_pct >= 70)
        )

    # Separation reason check (LEO only)
    gt_leo_with_reason = gt_leo[gt_leo['separation_reason'].notna() & (gt_leo['separation_reason'] != '')]
    if len(gt_leo_with_reason) > 0:
        gt_reasons = set(gt_leo_with_reason['separation_reason'].unique())
        out_leo_with_reason = out_leo[out_leo['separation_reason'] != '']
        out_reasons = set(out_leo_with_reason['separation_reason'].unique())
        overlap = gt_reasons & out_reasons
        add_check(
            "separation_reason_values",
            len(overlap) >= len(gt_reasons) * 0.8,
            f"Separation reason overlap: {len(overlap)}/{len(gt_reasons)} GT values present"
        )

# ---------------------------------------------------------------------------
# Compute overall result
# ---------------------------------------------------------------------------

fail_count = sum(1 for _, s, _ in checks if s == "FAIL")
warn_count = sum(1 for _, s, _ in checks if s == "WARN")
pass_count = sum(1 for _, s, _ in checks if s == "PASS")

if fail_count > 0:
    overall = "FAIL"
elif warn_count > 0:
    overall = "WARN"
else:
    overall = "PASS"

# ---------------------------------------------------------------------------
# Write judge_report.md
# ---------------------------------------------------------------------------

md_lines = [
    "# CA 2025 Validation Report",
    "",
    f"**Overall: {overall}**",
    f"- PASS: {pass_count}",
    f"- WARN: {warn_count}",
    f"- FAIL: {fail_count}",
    "",
    f"**Has groundtruth**: {'Yes' if has_groundtruth else 'No'}",
    "",
    f"**Output rows**: {len(df)}",
    f"- LEO: {(df.get('type', pd.Series()) == 'POLICE').sum()}",
    f"- Corrections: {(df.get('type', pd.Series()) == 'CORRECTIONS').sum()}",
    "",
    "## Check Results",
    "",
    "| Check | Status | Message |",
    "|-------|--------|---------|",
]

for name, status, message in checks:
    emoji = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
    md_lines.append(f"| {name} | {emoji} {status} | {message} |")

if has_groundtruth:
    md_lines += [
        "",
        "## Groundtruth Summary",
        "",
        f"| Metric | Output | GT | Diff |",
        f"|--------|--------|-----|------|",
        f"| Total rows | {len(df)} | {len(gt)} | {len(df)-len(gt):+d} ({(len(df)/len(gt)-1)*100:+.1f}%) |",
        f"| LEO rows | {(df['type']=='POLICE').sum()} | {len(gt_leo)} | {(df['type']=='POLICE').sum()-len(gt_leo):+d} |",
        f"| Corrections rows | {(df['type']=='CORRECTIONS').sum()} | {len(gt_corr)} | {(df['type']=='CORRECTIONS').sum()-len(gt_corr):+d} |",
    ]

md_lines += [
    "",
    "## Data Quality Summary",
    "",
    f"- Unique persons: {df['person_nbr'].nunique()}",
    f"- Unique agencies: {df['agency_name'].nunique()}",
    f"- Date range: {df['start_date'].min()} to {df['start_date'].max()}",
    f"- Empty first_name: {(df['first_name']=='').sum()} ({(df['first_name']=='').sum()/len(df)*100:.2f}%)",
    f"- Empty last_name: {(df['last_name']=='').sum()} ({(df['last_name']=='').sum()/len(df)*100:.2f}%)",
    f"- Empty end_date (currently employed): {(df['end_date']=='').sum()} ({(df['end_date']=='').sum()/len(df)*100:.1f}%)",
    "",
    "## Sample Rows",
    "",
    "```",
    df.head(5).to_string(index=False),
    "```",
]

md_content = "\n".join(md_lines)
md_path = os.path.join(OUTPUT_DIR, "judge_report.md")
with open(md_path, "w") as f:
    f.write(md_content)
print(f"\nWritten: {md_path}")

# ---------------------------------------------------------------------------
# Write judge_report.json
# ---------------------------------------------------------------------------

json_content = {
    "overall": overall,
    "has_groundtruth": has_groundtruth,
    "pass_count": pass_count,
    "warn_count": warn_count,
    "fail_count": fail_count,
    "output_rows": len(df),
    "checks": [{"name": n, "status": s, "message": m} for n, s, m in checks],
}
json_path = os.path.join(OUTPUT_DIR, "judge_report.json")
with open(json_path, "w") as f:
    json.dump(json_content, f, indent=2)
print(f"Written: {json_path}")

print(f"\n=== OVERALL: {overall} ===")
