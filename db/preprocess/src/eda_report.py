"""
Generate a concise EDA markdown summary for one or more cleaned state index
CSVs. Designed to be pasted into a GitHub commit message or PR description.

Usage:
    python db/preprocess/src/eda_report.py states/GA/data/output/georgia_index.csv
    python db/preprocess/src/eda_report.py \\
        states/GA/data/output/georgia_index.csv \\
        states/GA/data/output/georgia-discipline_index.csv
"""

from __future__ import annotations

import os
import sys

import pandas as pd


# Columns to show in the coverage table (in order)
COVERAGE_COLS = [
    "person_nbr",
    "full_name",
    "first_name",
    "middle_name",
    "last_name",
    "suffix",
    "agency_name",
    "rank",
    "start_date",
    "end_date",
    "state",
    "employment_status",
    "separation_reason",
    "current_certificate_status",
    "type",
    "offense",
    "violation",
    "sanction",
    "sanction_date",
    "notes",
    "race",
    "sex",
    "year_of_birth",
]

DATE_COLS = ["start_date", "end_date", "violation_date", "sanction_date"]
DISCIPLINE_COLS = ["violation", "sanction"]

SAMPLE_COLS = [
    "person_nbr",
    "first_name",
    "last_name",
    "agency_name",
    "start_date",
    "end_date",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _non_empty_pct(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    filled = series.replace("", pd.NA).notna().sum()
    return filled / len(series) * 100


def _pct(n, total):
    return f"{n / max(total, 1) * 100:.1f}%"


def _top_n(series: pd.Series, n: int = 10) -> pd.DataFrame:
    counts = series.replace("", pd.NA).dropna().value_counts().head(n)
    total = len(series)
    return pd.DataFrame(
        {
            "value": counts.index,
            "count": counts.values,
            "pct": [_pct(c, total) for c in counts.values],
        }
    )


def _md_table(df: pd.DataFrame) -> str:
    """Render a small DataFrame as a GitHub-flavored markdown table."""
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row.values) + " |")
    return "\n".join([header, sep] + rows)


def _date_range(series: pd.Series) -> str:
    parsed = pd.to_datetime(series.replace("", pd.NA), errors="coerce").dropna()
    if parsed.empty:
        return "no valid dates"
    return f"{parsed.min().date()} → {parsed.max().date()}"


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_report(path: str) -> str:
    if not os.path.exists(path):
        return f"_File not found: {path}_\n"

    df = pd.read_csv(path, low_memory=False)
    fname = os.path.basename(path)
    total = len(df)
    lines = []

    lines.append(f"## {fname}\n")
    lines.append(f"**Rows:** {total:,} | **Columns:** {len(df.columns)}\n")

    # --- Coverage table ---
    present_cols = [c for c in COVERAGE_COLS if c in df.columns]
    # Also include any columns not in COVERAGE_COLS
    extra_cols = [c for c in df.columns if c not in COVERAGE_COLS]
    all_cols = present_cols + extra_cols

    cov_rows = []
    for col in all_cols:
        pct = _non_empty_pct(df[col])
        uniq = df[col].replace("", pd.NA).nunique()
        cov_rows.append(
            {"Column": col, "Non-empty": f"{pct:.1f}%", "Unique": f"{uniq:,}"}
        )

    lines.append("### Coverage")
    lines.append(_md_table(pd.DataFrame(cov_rows)))
    lines.append("")

    # --- Date ranges ---
    date_cols_present = [c for c in DATE_COLS if c in df.columns]
    if date_cols_present:
        lines.append("### Date ranges")
        for col in date_cols_present:
            lines.append(f"- **{col}:** {_date_range(df[col])}")
        lines.append("")

    # --- Top agencies ---
    if "agency_name" in df.columns:
        top = _top_n(df["agency_name"], 10)
        top.columns = ["Agency", "Records", "%"]
        lines.append("### Top 10 agency names")
        lines.append(_md_table(top))
        lines.append("")

    # --- Top ranks ---
    if "rank" in df.columns:
        top = _top_n(df["rank"], 10)
        top.columns = ["Rank", "Records", "%"]
        lines.append("### Top 10 ranks")
        lines.append(_md_table(top))
        lines.append("")

    # --- Employment status ---
    if "employment_status" in df.columns:
        dist = _top_n(df["employment_status"], 15)
        dist.columns = ["Status", "Records", "%"]
        lines.append("### Employment status")
        lines.append(_md_table(dist))
        lines.append("")

    # --- Discipline-specific ---
    for col in DISCIPLINE_COLS:
        if col in df.columns:
            top = _top_n(df[col], 10)
            top.columns = [col.capitalize(), "Records", "%"]
            lines.append(f"### Top 10 {col}s")
            lines.append(_md_table(top))
            lines.append("")

    # --- Name stats ---
    name_stats = []
    for col in ("middle_name", "suffix"):
        if col in df.columns:
            pct = _non_empty_pct(df[col])
            name_stats.append(f"- Rows with **{col}:** {pct:.1f}%")
    if name_stats:
        lines.append("### Name completeness")
        lines.extend(name_stats)
        lines.append("")

    # --- Demographics ---
    demo_lines = []
    for col in ("race", "sex"):
        if col in df.columns:
            dist = _top_n(df[col], 8)
            dist.columns = [col.capitalize(), "Records", "%"]
            demo_lines.append(f"#### {col.capitalize()}")
            demo_lines.append(_md_table(dist))
    if demo_lines:
        lines.append("### Demographics")
        lines.extend(demo_lines)
        lines.append("")

    # --- Sample rows ---
    sample_cols_present = [c for c in SAMPLE_COLS if c in df.columns]
    if sample_cols_present:
        sample = (
            df[sample_cols_present]
            .sample(min(5, total), random_state=42)
            .copy()
        )
        if "agency_name" in sample.columns:
            sample["agency_name"] = sample["agency_name"].astype(str).str[:40]
        lines.append("### Sample rows (5 random)")
        lines.append(_md_table(sample.fillna("").reset_index(drop=True)))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print(
            "Usage: python db/preprocess/src/eda_report.py <csv_path> "
            "[<csv_path2> ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    sep = "\n" + "-" * 60 + "\n"
    reports = [build_report(p) for p in paths]
    print(sep.join(reports))
