import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from pipeline.cc_agent import CCAgent

FAKE_REPORT = {"overall": "PASS", "has_groundtruth": True}


def _make_out(root, state, year):
    out = os.path.join(root, state, year, "output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "judge_report.json"), "w") as f:
        json.dump(FAKE_REPORT, f)


def test_prompt_includes_state_and_year():
    prompt = CCAgent()._build_prompt("ca", "2025", prior_clean_py=None)
    assert "ca" in prompt and "2025" in prompt


def test_prompt_includes_prior_clean_py():
    prompt = CCAgent()._build_prompt(
        "ga", "2025", prior_clean_py="# prior script"
    )
    assert "prior script" in prompt


def test_prompt_references_validate_and_json_schema():
    prompt = CCAgent()._build_prompt("ca", "2025", prior_clean_py=None)
    assert "validate.py" in prompt
    assert "judge_report.json" in prompt


def test_run_invokes_claude_cli():
    with tempfile.TemporaryDirectory() as d:
        _make_out(d, "ca", "2025")
        agent = CCAgent(states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            agent.run("ca", "2025")
        assert mock_run.call_args[0][0][0] == "claude"


def test_run_returns_error_when_claude_missing():
    with tempfile.TemporaryDirectory() as d:
        agent = CCAgent(states_root=d)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = agent.run("ca", "2025")
        assert result.error is not None and "claude" in result.error.lower()


def test_run_finds_prior_year_clean_py():
    with tempfile.TemporaryDirectory() as d:
        prior_src = os.path.join(d, "ga", "2024", "src")
        os.makedirs(prior_src)
        with open(os.path.join(prior_src, "clean.py"), "w") as f:
            f.write("# 2024 clean script")
        _make_out(d, "ga", "2025")
        agent = CCAgent(states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            agent.run("ga", "2025")
        prompt = mock_run.call_args[0][0][-1]
        assert "2024 clean script" in prompt
