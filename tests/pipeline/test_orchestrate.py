import tempfile
from unittest.mock import patch, MagicMock

from pipeline.orchestrate import Orchestrator
from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import JudgeResult


def _orch(tmp):
    return Orchestrator(
        rclone_remote="dropbox:post-db-test",
        states_root="states",
        repo_root=".",
        manifest_path=f"{tmp}/manifest.json",
        registry_path=f"{tmp}/registry.csv",
    )


def test_no_changes_makes_no_pr():
    with tempfile.TemporaryDirectory() as d:
        orch = _orch(d)
        with patch.object(orch._rclone, "list_years", return_value=["2025"]):
            with patch.object(orch._rclone, "lsjson", return_value=[]):
                with patch.object(orch._pr_gen, "create_pr") as mock_pr:
                    orch.run(states=["ga"])
        mock_pr.assert_not_called()


def test_changed_files_trigger_clean_and_pr():
    with tempfile.TemporaryDirectory() as d:
        orch = _orch(d)
        fake_lsjson = [
            {
                "Name": "officer_employment.csv",
                "Size": 100,
                "ModTime": "2026-03-21T10:00:00Z",
            }
        ]
        fake_result = CleanResult(
            state="ga",
            year="2025",
            judge=JudgeResult("PASS", True, True, raw=""),
        )
        with patch.object(orch._rclone, "list_years", return_value=["2025"]):
            with patch.object(
                orch._rclone, "lsjson", return_value=fake_lsjson
            ):
                with patch.object(orch._rclone, "copy"):
                    with patch.object(
                        orch._rclone, "has_groundtruth", return_value=False
                    ):
                        with patch.object(
                            orch._runner,
                            "has_clean_script",
                            return_value=True,
                        ):
                            with patch.object(
                                orch._runner, "run", return_value=fake_result
                            ):
                                with patch.object(
                                    orch._pr_gen, "commit_outputs"
                                ):
                                    with patch.object(
                                        orch._pr_gen, "create_pr"
                                    ) as mock_pr:
                                        orch.run(states=["ga"])
        mock_pr.assert_called_once()
