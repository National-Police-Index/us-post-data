import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from pipeline.clean_runner import CleanRunner


FAKE_REPORT = {"overall": "PASS", "has_groundtruth": False}


def _make_year_dir(root, state="ga", year="2025"):
    base = os.path.join(root, state, year)
    src = os.path.join(base, "src")
    out = os.path.join(base, "output")
    os.makedirs(src)
    os.makedirs(out)
    return base, src, out


def test_has_clean_script_true():
    with tempfile.TemporaryDirectory() as d:
        _, src, _ = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        assert CleanRunner(states_root=d).has_clean_script("ga", "2025") is True


def test_has_clean_script_false():
    with tempfile.TemporaryDirectory() as d:
        assert (
            CleanRunner(states_root=d).has_clean_script("zz", "2025") is False
        )


def test_run_errors_when_validate_missing():
    with tempfile.TemporaryDirectory() as d:
        _, src, _ = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        # No validate.py
        result = CleanRunner(states_root=d).run("ga", "2025")
        assert result.error is not None
        assert "validate.py" in result.error


def test_run_passes_input_and_output_dirs():
    with tempfile.TemporaryDirectory() as d:
        _, src, out = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        open(os.path.join(src, "validate.py"), "w").close()
        with open(os.path.join(out, "judge_report.json"), "w") as f:
            json.dump(FAKE_REPORT, f)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            CleanRunner(states_root=d).run("ga", "2025")
        cmd = mock_run.call_args_list[0][0][0]
        assert "--input-dir" in cmd
        assert "--output-dir" in cmd


def test_run_returns_passed_result():
    with tempfile.TemporaryDirectory() as d:
        _, src, out = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        open(os.path.join(src, "validate.py"), "w").close()
        with open(os.path.join(out, "judge_report.json"), "w") as f:
            json.dump(FAKE_REPORT, f)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = CleanRunner(states_root=d).run("ga", "2025")
        assert result.judge.passed is True


def test_run_returns_error_when_clean_script_fails():
    with tempfile.TemporaryDirectory() as d:
        _, src, _ = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        open(os.path.join(src, "validate.py"), "w").close()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = CleanRunner(states_root=d).run("ga", "2025")
        assert result.error is not None and result.judge is None
