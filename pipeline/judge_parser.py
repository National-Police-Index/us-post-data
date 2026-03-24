from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class JudgeResult:
    overall: str
    passed: bool
    has_groundtruth: bool
    raw: str = field(repr=False)


def parse_judge_report(text: str) -> JudgeResult:
    """Parse judge_report.json (preferred) or fall back to markdown regex."""
    try:
        data = json.loads(text)
        overall = data["overall"].upper()
        has_groundtruth = data.get("has_groundtruth", True)
    except (json.JSONDecodeError, KeyError):
        m = re.search(r"\*\*Overall result:\*\*\s*`(\w+)`", text)
        overall = m.group(1).upper() if m else "FAIL"
        has_groundtruth = "No ground truth found" not in text
    return JudgeResult(
        overall=overall,
        passed=overall in ("PASS", "WARN"),
        has_groundtruth=has_groundtruth,
        raw=text,
    )


def load_judge_report(output_dir: str) -> JudgeResult:
    """
    Read judge_report.json if present, else fall back to judge_report.md.
    Raises FileNotFoundError if neither exists.
    """
    import os

    json_path = os.path.join(output_dir, "judge_report.json")
    md_path = os.path.join(output_dir, "judge_report.md")

    if os.path.exists(json_path):
        with open(json_path) as f:
            result = parse_judge_report(f.read())
        if os.path.exists(md_path):
            with open(md_path) as f:
                result.raw = f.read()
        return result
    if os.path.exists(md_path):
        with open(md_path) as f:
            return parse_judge_report(f.read())
    raise FileNotFoundError(
        f"No judge_report.json or judge_report.md in {output_dir}"
    )
