from unittest.mock import MagicMock, patch

from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import JudgeResult
from pipeline.pr_generator import PRGenerator, build_pr_body


def _r(state, year="2025", overall="PASS", has_gt=True, error=None):
    if error:
        return CleanResult(state=state, year=year, judge=None, error=error)
    return CleanResult(
        state=state,
        year=year,
        judge=JudgeResult(overall, overall != "FAIL", has_gt, ""),
    )


def test_body_includes_state_year_and_result():
    body = build_pr_body([_r("ga")])
    assert "ga" in body and "2025" in body and "PASS" in body


def test_body_flags_no_groundtruth():
    body = build_pr_body([_r("fl", has_gt=False)])
    assert "ground truth" in body.lower()


def test_body_shows_error():
    body = build_pr_body([_r("zz", error="clean.py failed")])
    assert "FAIL" in body or "error" in body.lower()


def test_body_covers_multiple_pairs():
    body = build_pr_body([_r("ga"), _r("ca", overall="WARN")])
    assert "ga" in body and "ca" in body


def test_create_pr_calls_gh():
    gen = PRGenerator(repo_root=".")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        gen.create_pr("data/update/2026-03-22", [_r("ga")])
    assert any("gh" in str(c) for c in mock_run.call_args_list)


def test_commit_outputs_adds_csv_gz_not_raw_output():
    """commit_outputs must stage db/data/output/<state>/, not states/*/output/."""
    gen = PRGenerator(repo_root=".")
    with patch.object(gen, "_git") as mock_git:
        mock_git.return_value = MagicMock(returncode=0)
        gen.commit_outputs([("ga", "2025")], branch="data/test")
    all_args = [str(c) for c in mock_git.call_args_list]
    combined = " ".join(all_args)
    assert "db/data/output/ga" in combined
    assert "states/ga/2025/output" not in combined


def test_commit_outputs_still_adds_clean_and_validate_scripts():
    """clean.py and validate.py must still be staged."""
    gen = PRGenerator(repo_root=".")
    with patch.object(gen, "_git") as mock_git:
        mock_git.return_value = MagicMock(returncode=0)
        gen.commit_outputs([("ga", "2025")], branch="data/test")
    all_args = [str(c) for c in mock_git.call_args_list]
    combined = " ".join(all_args)
    assert "states/ga/2025/src/clean.py" in combined
    assert "states/ga/2025/src/validate.py" in combined
