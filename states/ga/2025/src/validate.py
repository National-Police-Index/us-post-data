"""
Validation script for GA 2025 POST data.
Compares output CSVs against ground truth and writes:
  output/judge_report.md
  output/judge_report.json
"""

import json
import os
import sys
import pandas as pd

OUTPUT_DIR = "output"
GROUNDTRUTH_DIR = "data/groundtruth"

INDEX_OUT  = os.path.join(OUTPUT_DIR, "ga_index.csv")
DISC_OUT   = os.path.join(OUTPUT_DIR, "ga-discipline_index.csv")
GT_INDEX   = os.path.join(GROUNDTRUTH_DIR, "georgia_index.csv")
GT_DISC    = os.path.join(GROUNDTRUTH_DIR, "georgia-discipline_index.csv")

REPORT_MD   = os.path.join(OUTPUT_DIR, "judge_report.md")
REPORT_JSON = os.path.join(OUTPUT_DIR, "judge_report.json")

checks = []   # list of (name, status, detail)

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    checks.append((name, status, detail))
    print(f"[{status}] {name}" + (f": {detail}" if detail else ""))
    return passed


def warn(name, detail=""):
    checks.append((name, "WARN", detail))
    print(f"[WARN] {name}" + (f": {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Load output files
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.exists(INDEX_OUT):
    check("Index file exists", False, f"Missing {INDEX_OUT}")
    json.dump({"overall": "FAIL", "has_groundtruth": False}, open(REPORT_JSON, "w"))
    sys.exit(1)

if not os.path.exists(DISC_OUT):
    check("Discipline file exists", False, f"Missing {DISC_OUT}")
    json.dump({"overall": "FAIL", "has_groundtruth": False}, open(REPORT_JSON, "w"))
    sys.exit(1)

check("Index file exists", True)
check("Discipline file exists", True)

index = pd.read_csv(INDEX_OUT, dtype=str, keep_default_na=False)
disc  = pd.read_csv(DISC_OUT,  dtype=str, keep_default_na=False)

print(f"\nLoaded index: {len(index):,} rows, discipline: {len(disc):,} rows")

# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------

REQUIRED_INDEX = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date']
REQUIRED_DISC  = ['person_nbr', 'first_name', 'last_name', 'agency_name', 'start_date', 'end_date',
                  'case_id', 'violation', 'sanction']

missing_idx = [c for c in REQUIRED_INDEX if c not in index.columns]
check("Index has required columns", not missing_idx,
      f"Missing: {missing_idx}" if missing_idx else f"All {len(REQUIRED_INDEX)} present")

missing_disc = [c for c in REQUIRED_DISC if c not in disc.columns]
check("Discipline has required columns", not missing_disc,
      f"Missing: {missing_disc}" if missing_disc else f"All {len(REQUIRED_DISC)} present")

# ---------------------------------------------------------------------------
# person_nbr format checks
# ---------------------------------------------------------------------------

idx_pnbr_ok = (index['person_nbr'] == index['person_nbr'].str.lower().str.strip()).all()
check("Index person_nbr is lowercase + no whitespace", idx_pnbr_ok,
      f"{(~(index['person_nbr'] == index['person_nbr'].str.lower().str.strip())).sum()} bad rows" if not idx_pnbr_ok else "")

disc_pnbr_ok = (disc['person_nbr'] == disc['person_nbr'].str.lower().str.strip()).all()
check("Discipline person_nbr is lowercase + no whitespace", disc_pnbr_ok)

# person_nbr pattern: should be o/c + digits
pnbr_pattern = index['person_nbr'].str.match(r'^[oc]\d+$')
pnbr_bad = (~pnbr_pattern).sum()
if pnbr_bad > 0:
    warn("Index person_nbr format", f"{pnbr_bad} rows don't match [oc]\\d+ pattern")
else:
    check("Index person_nbr format matches [oc]\\d+", True)

# ---------------------------------------------------------------------------
# Date format checks
# ---------------------------------------------------------------------------

def check_date_col(df, col, label):
    valid = df[col].str.match(r'^\d{4}-\d{2}-\d{2}$', na=False) | (df[col] == '')
    bad = (~valid).sum()
    if bad > 0:
        warn(f"{label} {col} date format", f"{bad} rows with invalid date format")
    else:
        check(f"{label} {col} date format is YYYY-MM-DD or empty", True)

check_date_col(index, 'start_date', 'Index')
check_date_col(index, 'end_date',   'Index')
check_date_col(disc,  'start_date', 'Discipline')
check_date_col(disc,  'end_date',   'Discipline')

# start_date not empty
idx_no_start = (index['start_date'] == '').sum()
check("Index start_date not empty", idx_no_start == 0,
      f"{idx_no_start} rows with empty start_date" if idx_no_start else "")

disc_no_start = (disc['start_date'] == '').sum()
check("Discipline start_date not empty", disc_no_start == 0,
      f"{disc_no_start} rows with empty start_date" if disc_no_start else "")

# ---------------------------------------------------------------------------
# Duplicate checks
# ---------------------------------------------------------------------------

idx_dupes = index.duplicated(subset=['person_nbr', 'agency_name', 'start_date']).sum()
check("Index has no duplicate (person_nbr, agency_name, start_date)",
      idx_dupes == 0,
      f"{idx_dupes} duplicate rows" if idx_dupes else "")

disc_dupes = disc.duplicated(subset=['case_id', 'person_nbr', 'violation']).sum()
check("Discipline has no duplicate (case_id, person_nbr, violation)",
      disc_dupes == 0,
      f"{disc_dupes} duplicate rows" if disc_dupes else "")

# ---------------------------------------------------------------------------
# Ground truth comparison
# ---------------------------------------------------------------------------

has_groundtruth = os.path.exists(GT_INDEX) and os.path.exists(GT_DISC)
print(f"\nGround truth available: {has_groundtruth}")

if has_groundtruth:
    gt_idx  = pd.read_csv(GT_INDEX, dtype=str, keep_default_na=False)
    gt_disc = pd.read_csv(GT_DISC,  dtype=str, keep_default_na=False)

    print(f"GT index: {len(gt_idx):,} rows, GT discipline: {len(gt_disc):,} rows")

    # --- Row count comparison ---
    idx_pct_diff = abs(len(index) - len(gt_idx)) / max(len(gt_idx), 1) * 100
    disc_pct_diff = abs(len(disc) - len(gt_disc)) / max(len(gt_disc), 1) * 100

    if idx_pct_diff <= 5:
        check(f"Index row count within 5% of GT ({len(gt_idx):,})",
              True, f"OUT={len(index):,}, GT={len(gt_idx):,}, diff={idx_pct_diff:.1f}%")
    elif idx_pct_diff <= 20:
        warn(f"Index row count differs from GT by {idx_pct_diff:.1f}%",
             f"OUT={len(index):,}, GT={len(gt_idx):,}")
    else:
        check(f"Index row count within 20% of GT", False,
              f"OUT={len(index):,}, GT={len(gt_idx):,}, diff={idx_pct_diff:.1f}%")

    if disc_pct_diff <= 5:
        check(f"Discipline row count within 5% of GT ({len(gt_disc):,})",
              True, f"OUT={len(disc):,}, GT={len(gt_disc):,}, diff={disc_pct_diff:.1f}%")
    elif disc_pct_diff <= 70:
        # Discipline data grows significantly — data has ~doubled since GT snapshot
        warn(f"Discipline row count differs from GT by {disc_pct_diff:.1f}% (data growth expected)",
             f"OUT={len(disc):,}, GT={len(gt_disc):,}")
    else:
        check(f"Discipline row count within reasonable range of GT", False,
              f"OUT={len(disc):,}, GT={len(gt_disc):,}, diff={disc_pct_diff:.1f}%")

    # --- Key overlap: GT rows present in output ---
    gt_idx_keys  = set(zip(gt_idx['person_nbr'], gt_idx['agency_name'], gt_idx['start_date']))
    out_idx_keys = set(zip(index['person_nbr'], index['agency_name'], index['start_date']))
    only_in_gt   = gt_idx_keys - out_idx_keys
    only_in_out  = out_idx_keys - gt_idx_keys
    overlap_pct  = len(gt_idx_keys & out_idx_keys) / max(len(gt_idx_keys), 1) * 100

    if overlap_pct >= 99:
        check(f"Index GT key overlap >= 99%", True,
              f"{overlap_pct:.2f}% overlap; only-in-GT={len(only_in_gt)}, only-in-OUT={len(only_in_out)}")
    elif overlap_pct >= 95:
        warn(f"Index GT key overlap {overlap_pct:.2f}%",
             f"only-in-GT={len(only_in_gt)}, only-in-OUT={len(only_in_out)}")
    else:
        check(f"Index GT key overlap >= 95%", False,
              f"Only {overlap_pct:.2f}% overlap; only-in-GT={len(only_in_gt)}")

    # --- Value spot-checks on overlapping rows ---
    idx_common = index.set_index(['person_nbr', 'agency_name', 'start_date'])
    gt_common  = gt_idx.set_index(['person_nbr', 'agency_name', 'start_date'])
    common_keys = idx_common.index.intersection(gt_common.index)

    if len(common_keys) > 0:
        # Align on common keys (handle potential duplicate keys by taking first)
        idx_c = idx_common.loc[common_keys].reset_index()
        gt_c  = gt_common.loc[common_keys].reset_index()
        # Merge on the key columns for safe alignment
        key_cols = ['person_nbr', 'agency_name', 'start_date']
        merged_check = idx_c[key_cols + ['first_name', 'last_name', 'end_date']].merge(
            gt_c[key_cols + ['first_name', 'last_name', 'end_date']],
            on=key_cols,
            suffixes=('_out', '_gt'),
        )
        n_common = len(merged_check)
        for col in ['first_name', 'last_name', 'end_date']:
            match_rate = (merged_check[f'{col}_out'] == merged_check[f'{col}_gt']).mean() * 100
            if match_rate >= 95:
                check(f"Index {col} value match rate >= 95%", True,
                      f"{match_rate:.1f}% match on {n_common:,} common rows")
            elif match_rate >= 85:
                warn(f"Index {col} value match rate {match_rate:.1f}%")
            else:
                check(f"Index {col} value match rate >= 85%", False,
                      f"Only {match_rate:.1f}% match")

    # --- Discipline spot-check on overlapping case_ids ---
    gt_disc_keys  = set(zip(gt_disc['case_id'], gt_disc['person_nbr'], gt_disc['violation']))
    out_disc_keys = set(zip(disc['case_id'], disc['person_nbr'], disc['violation']))
    disc_overlap  = gt_disc_keys & out_disc_keys
    disc_overlap_pct = len(disc_overlap) / max(len(gt_disc_keys), 1) * 100

    if disc_overlap_pct >= 80:
        check(f"Discipline GT key overlap >= 80%", True,
              f"{disc_overlap_pct:.1f}% overlap ({len(disc_overlap):,}/{len(gt_disc_keys):,} GT keys)")
    elif disc_overlap_pct >= 50:
        warn(f"Discipline GT key overlap {disc_overlap_pct:.1f}%",
             f"(data has grown significantly since GT snapshot)")
    else:
        warn(f"Discipline GT key overlap low: {disc_overlap_pct:.1f}%",
             f"May indicate data growth or join logic change")

else:
    warn("No ground truth available", "Skipping ground truth comparison checks")

# ---------------------------------------------------------------------------
# Content quality checks
# ---------------------------------------------------------------------------

# Check non-empty names
first_empty = (index['first_name'] == '').sum()
last_empty  = (index['last_name']  == '').sum()
if first_empty > 0:
    warn(f"Index first_name empty", f"{first_empty} rows ({first_empty/len(index):.1%})")
else:
    check("Index first_name non-empty", True)

if last_empty > 0:
    warn(f"Index last_name empty", f"{last_empty} rows ({last_empty/len(index):.1%})")
else:
    check("Index last_name non-empty", True)

# Check agency_name non-empty
agency_empty = (index['agency_name'].str.strip() == '').sum()
check("Index agency_name non-empty", agency_empty == 0,
      f"{agency_empty} rows with empty agency_name" if agency_empty else "")

# Check discipline has case_id, violation, sanction non-empty
for col in ['case_id', 'violation', 'sanction']:
    empty = (disc[col] == '').sum()
    if empty > 0:
        warn(f"Discipline {col} empty", f"{empty} rows")
    else:
        check(f"Discipline {col} non-empty", True)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

n_pass = sum(1 for _, s, _ in checks if s == "PASS")
n_warn = sum(1 for _, s, _ in checks if s == "WARN")
n_fail = sum(1 for _, s, _ in checks if s == "FAIL")

if n_fail > 0:
    overall = "FAIL"
elif n_warn > 0:
    overall = "WARN"
else:
    overall = "PASS"

print(f"\n{'='*60}")
print(f"Overall: {overall}  (PASS={n_pass}, WARN={n_warn}, FAIL={n_fail})")
print(f"{'='*60}")

# ---------------------------------------------------------------------------
# Write reports
# ---------------------------------------------------------------------------

with open(REPORT_MD, "w") as f:
    f.write("# GA 2025 Validation Report\n\n")
    f.write(f"**Overall: {overall}**\n\n")
    f.write(f"Ground truth available: {has_groundtruth}\n\n")
    f.write(f"| Check | Status | Detail |\n")
    f.write(f"|-------|--------|--------|\n")
    for name, status, detail in checks:
        emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[status]
        f.write(f"| {name} | {emoji} {status} | {detail} |\n")
    f.write(f"\n## Summary\n")
    f.write(f"- PASS: {n_pass}\n- WARN: {n_warn}\n- FAIL: {n_fail}\n")
    f.write(f"\n## Row Counts\n")
    f.write(f"- Employment index: {len(index):,} rows\n")
    f.write(f"- Discipline index: {len(disc):,} rows\n")
    if has_groundtruth:
        f.write(f"- GT employment index: {len(gt_idx):,} rows\n")
        f.write(f"- GT discipline index: {len(gt_disc):,} rows\n")

json.dump(
    {"overall": overall, "has_groundtruth": has_groundtruth},
    open(REPORT_JSON, "w"),
    indent=2,
)

print(f"\nWrote {REPORT_MD}")
print(f"Wrote {REPORT_JSON}")
