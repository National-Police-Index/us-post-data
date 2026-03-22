from __future__ import annotations

import os
import subprocess

from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import load_judge_report


class CCAgent:
    def __init__(
        self, states_root: str = "states", repo_root: str = "."
    ):
        self._states_root = states_root
        self._repo_root = repo_root

    def _find_prior_clean_py(self, state: str, year: str) -> str | None:
        state_dir = os.path.join(self._states_root, state)
        if not os.path.isdir(state_dir):
            return None
        prior_years = sorted(
            y
            for y in os.listdir(state_dir)
            if os.path.isdir(os.path.join(state_dir, y)) and y < year
        )
        for prior_year in reversed(prior_years):
            path = os.path.join(state_dir, prior_year, "src", "clean.py")
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()
        return None

    def _has_csv_groundtruth(self, state: str, year: str) -> bool:
        gt_dir = os.path.join(
            self._states_root, state, year, "data", "groundtruth"
        )
        return os.path.isdir(gt_dir) and any(
            f.endswith(".csv") for f in os.listdir(gt_dir)
        )

    def _build_prompt(
        self, state: str, year: str, prior_clean_py: str | None
    ) -> str:
        has_gt = self._has_csv_groundtruth(state, year)
        groundtruth_note = (
            f"CSV groundtruth files are available in "
            f"states/{state}/{year}/data/groundtruth/ — use them in "
            f"validate.py for row count and value comparison."
            if has_gt
            else (
                f"No CSV groundtruth exists for this state. Use "
                f"pipeline/data/groundtruth.md as your quality reference "
                f"when writing validate.py."
            )
        )
        base = (
            f"Read states/AGENT_INSTRUCTIONS.md and DATA_PREPROCESSING.md. "
            f"Process state {state}, year {year}: "
            f"inspect states/{state}/{year}/data/input/, "
            f"write states/{state}/{year}/src/clean.py accepting "
            f"--input-dir and --output-dir CLI args, "
            f"run it from states/{state}/{year}/ as cwd "
            f"(python src/clean.py --input-dir data/input "
            f"--output-dir output), "
            f"then write and run src/validate.py. "
            f"validate.py must write both output/judge_report.md "
            f"(human-readable) and output/judge_report.json "
            f'(machine-readable, schema: {{"overall": "PASS|WARN|FAIL", '
            f'"has_groundtruth": true|false}}). '
            f"If judge report is FAIL, fix clean.py and re-run. "
            f"{groundtruth_note}"
        )
        if prior_clean_py:
            base += (
                f"\n\nPrior year's clean.py for reference "
                f"(adapt as needed — do not copy blindly):\n\n"
                f"```python\n{prior_clean_py}\n```"
            )
        return base

    def run(self, state: str, year: str) -> CleanResult:
        prior = self._find_prior_clean_py(state, year)
        prompt = self._build_prompt(state, year, prior_clean_py=prior)
        try:
            proc = subprocess.run(
                ["claude", "--print", prompt],
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error="claude CLI not found",
            )
        except Exception as e:
            return CleanResult(
                state=state, year=year, judge=None, error=str(e)
            )

        if proc.returncode != 0:
            return CleanResult(
                state=state,
                year=year,
                judge=None,
                error=proc.stderr or f"claude exited {proc.returncode}",
            )

        output_dir = os.path.join(
            self._states_root, state, year, "output"
        )
        try:
            judge = load_judge_report(output_dir)
        except FileNotFoundError as e:
            return CleanResult(
                state=state, year=year, judge=None, error=str(e)
            )
        return CleanResult(state=state, year=year, judge=judge)
