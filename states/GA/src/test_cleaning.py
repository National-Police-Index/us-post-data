"""
LLM-as-judge test suite for Georgia POST data cleaning.

Compares agent output against ground-truth reference files when available.
Without ground truth, falls back to schema and quality checks only.

Writes a judge_report.md to states/GA/output/ after running.

Run from repo root:
    python states/GA/src/test_cleaning.py
"""

import os
import re
import sys
from datetime import datetime

import pandas as pd
from pydantic import BaseModel

# Resolve repo root so helpers/ is importable regardless of cwd
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
sys.path.insert(0, REPO_ROOT)

from states.helpers.llm_models import LLM  # noqa: E402

MODEL = "gpt-4.1-mini-2025-04-14"
_llm = LLM(model_name=MODEL)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SRC = os.path.dirname(__file__)
BASE = os.path.join(_SRC, "..")

AGENT_EMP = os.path.join(BASE, "output", "georgia_index.csv")
AGENT_DISC = os.path.join(BASE, "output", "georgia-discipline_index.csv")

REF_EMP = os.path.join(BASE, "data", "groundtruth", "georgia_index.csv")
REF_DISC = os.path.join(
    BASE, "data", "groundtruth", "georgia-discipline_index.csv"
)

OUTPUT_DIR = os.path.join(BASE, "output")

REQUIRED_COLS = [
    "person_nbr", "first_name", "last_name",
    "agency_name", "start_date", "end_date",
]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BAD_DATE_VALUES = {"0000-00-00", "NaT", "None", "nan"}

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"

# ---------------------------------------------------------------------------
# Report accumulator — tees output to both stdout and the report file
# ---------------------------------------------------------------------------

_report: list[str] = []


def _emit(line: str = "") -> None:
    print(line)
    _report.append(line)


# ---------------------------------------------------------------------------
# Pydantic response models for structured LLM output
# ---------------------------------------------------------------------------

class JudgmentResult(BaseModel):
    score: int
    issues: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path, label):
    if not os.path.exists(path):
        _emit(f"  File not found: {path}")
        return None
    df = pd.read_csv(path, low_memory=False)
    _emit(f"  Loaded {label}: {len(df):,} rows, {len(df.columns)} cols")
    return df


def _judge(prompt) -> JudgmentResult | None:
    """Run a structured LLM judgment. Returns None if unavailable."""
    try:
        return _llm.run_structured_inference(
            prompt, JudgmentResult, model=MODEL, max_tokens=1024
        )
    except Exception as e:
        _emit(f"  LLM call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------

def check_schema(df, label):
    _emit(f"\n[Schema — {label}]")
    status = PASS
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        _emit(f"  {FAIL}: missing columns: {missing}")
        status = FAIL
    else:
        _emit("  Required columns: present")

    if "start_date" in df.columns:
        empty_sd = (df["start_date"].fillna("") == "").sum()
        if empty_sd:
            _emit(f"  {FAIL}: {empty_sd:,} rows with empty start_date")
            status = FAIL
        else:
            _emit("  start_date: no empty values")
    return status


def check_row_count(agent_df, ref_df, label):
    if ref_df is None:
        _emit(f"\n[Row count — {label}] {SKIP} (no ground truth)")
        return SKIP
    _emit(f"\n[Row count — {label}]")
    a, r = len(agent_df), len(ref_df)
    diff_pct = abs(a - r) / max(r, 1) * 100
    _emit(f"  Agent: {a:,}  |  Reference: {r:,}  |  Diff: {diff_pct:.1f}%")
    if diff_pct > 5:
        _emit(f"  {WARN}: difference > 5%")
        return WARN
    _emit(f"  {PASS}")
    return PASS


def check_dates(df, label):
    _emit(f"\n[Date format — {label}]")
    date_cols = [
        c for c in ("start_date", "end_date", "violation_date", "sanction_date")
        if c in df.columns
    ]
    total_bad = 0
    for col in date_cols:
        vals = df[col].fillna("").astype(str)
        bad_literal = vals.isin(BAD_DATE_VALUES).sum()
        non_empty = vals[vals != ""]
        bad_format = (~non_empty.str.match(DATE_RE)).sum()
        bad = bad_literal + bad_format
        if bad:
            _emit(f"  {col}: {bad:,} invalid values")
        total_bad += bad
    if total_bad == 0:
        _emit(f"  All date values valid  {PASS}")
        return PASS
    return FAIL


def check_person_nbr(df, label):
    _emit(f"\n[person_nbr format — {label}]")
    if "person_nbr" not in df.columns:
        _emit(f"  {SKIP}: column missing")
        return SKIP
    vals = df["person_nbr"].dropna().astype(str)
    has_upper = vals.str.contains(r"[A-Z]").sum()
    has_space = vals.str.contains(r"\s").sum()
    ok = True
    if has_upper:
        _emit(f"  {WARN}: {has_upper:,} values with uppercase characters")
        ok = False
    if has_space:
        _emit(f"  {WARN}: {has_space:,} values with whitespace")
        ok = False
    if ok:
        _emit(f"  {PASS}: all lowercase, no whitespace")
    return PASS if ok else WARN


# ---------------------------------------------------------------------------
# LLM judge checks
# ---------------------------------------------------------------------------

def check_agency_names_llm(agent_df, ref_df, label):
    _emit(f"\n[Agency name quality — {label}]")
    if "agency_name" not in agent_df.columns:
        _emit(f"  {SKIP}: agency_name column missing")
        return SKIP

    agent_agencies = sorted(
        agent_df["agency_name"].dropna().astype(str).unique().tolist()
    )

    # Hard check: agency codes still present
    code_re = re.compile(r"^[A-Z]\d+\s")
    codes_found = [a for a in agent_agencies if code_re.match(a)]
    if codes_found:
        _emit(f"  Agency codes still in {len(codes_found)} names:")
        for c in codes_found[:5]:
            _emit(f"    {c}")

    ref_agencies = (
        sorted(ref_df["agency_name"].dropna().astype(str).unique().tolist())
        if ref_df is not None and "agency_name" in ref_df.columns
        else []
    )

    ref_block = (
        f"Reference agency names (sample of 80):\n"
        f"{ref_agencies[:80]}\n\n"
        if ref_agencies
        else "No reference data available.\n\n"
    )

    prompt = (
        f"You are evaluating agency name cleaning quality for a U.S. police "
        f"officer dataset.\n\n"
        f"Agent-produced agency names (sample of 80):\n"
        f"{agent_agencies[:80]}\n\n"
        f"{ref_block}"
        f"Evaluate:\n"
        f"1. Are raw agency codes still present (e.g. 'G1720 DEKALB...')?\n"
        f"2. Are abbreviations expanded? "
        f"(PD→Police Department, SO→Sheriff's Office, DEPT→Department)\n"
        f"3. Overall similarity to reference list.\n\n"
        f"score: 0-10 (10=perfect). "
        f"issues: list of specific problems found. "
        f"summary: one sentence."
    )

    result = _judge(prompt)
    if result:
        _emit(f"  Score: {result.score}/10 — {result.summary}")
        for issue in result.issues:
            _emit(f"    • {issue}")
        return PASS if result.score >= 6 else WARN
    if codes_found:
        return FAIL
    return PASS


def check_name_parsing_llm(agent_df, ref_df, label):
    _emit(f"\n[Name parsing quality — {label}]")
    name_cols = [
        c for c in ("first_name", "last_name", "middle_name", "suffix")
        if c in agent_df.columns
    ]
    if not name_cols:
        _emit(f"  {SKIP}: no name columns found")
        return SKIP

    extra = ["full_name"] if "full_name" in agent_df.columns else []
    sample = agent_df.sample(min(20, len(agent_df)), random_state=42)
    agent_rows = (
        sample[["person_nbr"] + name_cols + extra]
        .fillna("")
        .to_dict("records")
    )

    ref_rows = []
    if ref_df is not None and "person_nbr" in ref_df.columns:
        ref_name_cols = [c for c in name_cols if c in ref_df.columns]
        ref_extra = ["full_name"] if "full_name" in ref_df.columns else []
        matched = ref_df[ref_df["person_nbr"].isin(sample["person_nbr"])]
        ref_rows = (
            matched[["person_nbr"] + ref_name_cols + ref_extra]
            .head(20)
            .fillna("")
            .to_dict("records")
        )

    ref_block = (
        f"Reference values for same person_nbr:\n{ref_rows}\n\n"
        if ref_rows
        else "No reference data available.\n\n"
    )

    prompt = (
        f"You are evaluating name parsing quality in a U.S. police officer "
        f"dataset.\n\n"
        f"Agent-produced name values (20 sample records):\n{agent_rows}\n\n"
        f"{ref_block}"
        f"Evaluate:\n"
        f"1. Are first_name and last_name correctly separated (not swapped)?\n"
        f"2. Are suffixes (Jr, Sr, II, III) in the suffix column?\n"
        f"3. Is middle_name populated where present, not merged into other cols?\n"
        f"4. Are there obvious parsing errors (punctuation attached to names)?\n\n"
        f"score: 0-10. issues: list of problems. summary: one sentence."
    )

    result = _judge(prompt)
    if result:
        _emit(f"  Score: {result.score}/10 — {result.summary}")
        for issue in result.issues:
            _emit(f"    • {issue}")
        return PASS if result.score >= 6 else WARN
    _emit("  LLM check skipped")
    return SKIP


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_checks(agent_path, ref_path, label):
    _emit(f"\n{'='*55}")
    _emit(f" {label}")
    _emit(f"{'='*55}")

    agent_df = _load(agent_path, "agent output")
    if agent_df is None:
        _emit("\n  Agent output not found — run states/GA/src/clean.py first")
        return {k: FAIL for k in
                ("schema", "rows", "dates", "person_nbr", "agencies", "names")}

    ref_df = _load(ref_path, "reference") if os.path.exists(ref_path) else None
    if ref_df is None:
        _emit("  No ground truth found — running quality-only checks")

    return {
        "schema":     check_schema(agent_df, label),
        "rows":       check_row_count(agent_df, ref_df, label),
        "dates":      check_dates(agent_df, label),
        "person_nbr": check_person_nbr(agent_df, label),
        "agencies":   check_agency_names_llm(agent_df, ref_df, label),
        "names":      check_name_parsing_llm(agent_df, ref_df, label),
    }


def write_report(emp_results, disc_results, overall: str) -> str:
    """Write judge_report.md to OUTPUT_DIR. Returns the report path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "judge_report.md")

    checks = [
        ("Schema",     "schema"),
        ("Row count",  "rows"),
        ("Dates",      "dates"),
        ("person_nbr", "person_nbr"),
        ("Agencies",   "agencies"),
        ("Names",      "names"),
    ]

    lines = [
        "# Georgia POST Data — Judge Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Model:** {MODEL}  ",
        f"**Overall result:** `{overall}`",
        "",
        "## Summary",
        "",
        f"| Check | Employment | Discipline |",
        f"|-------|-----------|------------|",
    ]
    for display, key in checks:
        e = emp_results.get(key, SKIP)
        d = disc_results.get(key, SKIP)
        lines.append(f"| {display} | {e} | {d} |")

    lines += [
        "",
        "## Detailed output",
        "",
        "```",
    ]
    lines += _report
    lines += ["```", ""]

    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    return report_path


if __name__ == "__main__":
    emp_results = run_checks(AGENT_EMP, REF_EMP, "Employment Index")
    disc_results = run_checks(AGENT_DISC, REF_DISC, "Discipline Index")

    _emit(f"\n{'='*55}")
    _emit(" SUMMARY")
    _emit(f"{'='*55}")
    checks = [
        ("Schema",     "schema"),
        ("Row count",  "rows"),
        ("Dates",      "dates"),
        ("person_nbr", "person_nbr"),
        ("Agencies",   "agencies"),
        ("Names",      "names"),
    ]
    _emit(f"  {'Check':<18} {'Employment':<15} Discipline")
    _emit(f"  {'-'*48}")
    for display, key in checks:
        e = emp_results.get(key, SKIP)
        d = disc_results.get(key, SKIP)
        _emit(f"  {display:<18} {e:<15} {d}")

    all_results = list(emp_results.values()) + list(disc_results.values())
    _emit()
    if any(r == FAIL for r in all_results):
        overall = "FAIL"
        _emit("Result: FAIL — one or more required checks failed")
    elif any(r == WARN for r in all_results):
        overall = "WARN"
        _emit("Result: WARN — passed with warnings")
    else:
        overall = "PASS"
        _emit("Result: PASS")

    report_path = write_report(emp_results, disc_results, overall)
    print(f"\nReport written to: {report_path}")

    if overall == "FAIL":
        sys.exit(1)
