from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass

from pipeline.judge_parser import JudgeResult, load_judge_report

logger = logging.getLogger(__name__)


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
            err = "validate.py not found — every state/year must have one"
            logger.error("[%s/%s] %s", state, year, err)
            return CleanResult(state=state, year=year, judge=None, error=err)

        logger.info("[%s/%s] running clean.py", state, year)
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
        if proc.stdout:
            logger.debug("[%s/%s] clean.py stdout:\n%s", state, year,
                         proc.stdout)
        if proc.returncode != 0:
            logger.error(
                "[%s/%s] clean.py failed (exit %d):\n%s",
                state, year, proc.returncode,
                proc.stderr or "(no stderr)",
            )
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error=proc.stderr or f"clean.py exited {proc.returncode}",
            )
        logger.info("[%s/%s] clean.py OK", state, year)

        logger.info("[%s/%s] running validate.py", state, year)
        vproc = subprocess.run(
            ["python", os.path.join("src", "validate.py")],
            cwd=year_dir,
            capture_output=True,
            text=True,
        )
        if vproc.stdout:
            logger.debug("[%s/%s] validate.py stdout:\n%s", state, year,
                         vproc.stdout)
        if vproc.returncode != 0:
            logger.warning(
                "[%s/%s] validate.py exited %d:\n%s",
                state, year, vproc.returncode,
                vproc.stderr or "(no stderr)",
            )

        try:
            judge = load_judge_report(os.path.join(year_dir, "output"))
        except FileNotFoundError as e:
            logger.error("[%s/%s] %s", state, year, e)
            return CleanResult(
                state=state, year=year, judge=None, error=str(e)
            )
        logger.info(
            "[%s/%s] judge report: %s", state, year, judge.overall
        )
        return CleanResult(state=state, year=year, judge=judge)
