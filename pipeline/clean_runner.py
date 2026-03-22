from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from pipeline.judge_parser import JudgeResult, load_judge_report


@dataclass
class CleanResult:
    state: str
    year: str
    judge: JudgeResult | None
    error: str | None = None

    @property
    def success(self) -> bool:
        return (
            self.error is None
            and self.judge is not None
            and self.judge.passed
        )


class CleanRunner:
    def __init__(self, states_root: str = "states"):
        self._states_root = states_root

    def _year_dir(self, state: str, year: str) -> str:
        return os.path.join(self._states_root, state, year)

    def has_clean_script(self, state: str, year: str) -> bool:
        return os.path.exists(
            os.path.join(self._year_dir(state, year), "src", "clean.py")
        )

    def run(self, state: str, year: str) -> CleanResult:
        year_dir = self._year_dir(state, year)

        validate_script = os.path.join(year_dir, "src", "validate.py")
        if not os.path.exists(validate_script):
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error="validate.py not found — every state/year must have one",
            )

        proc = subprocess.run(
            [
                "python",
                os.path.join("src", "clean.py"),
                "--input-dir",
                os.path.join("data", "input"),
                "--output-dir",
                "output",
            ],
            cwd=year_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error=proc.stderr or f"clean.py exited {proc.returncode}",
            )

        subprocess.run(
            ["python", os.path.join("src", "validate.py")],
            cwd=year_dir,
            capture_output=True,
            text=True,
        )

        try:
            judge = load_judge_report(os.path.join(year_dir, "output"))
        except FileNotFoundError as e:
            return CleanResult(
                state=state, year=year, judge=None, error=str(e)
            )
        return CleanResult(state=state, year=year, judge=judge)
