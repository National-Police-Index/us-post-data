import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from pipeline.rclone_client import RcloneClient


FAKE_FILES = json.dumps(
    [
        {
            "Name": "officer_employment.csv",
            "Size": 1000,
            "ModTime": "2026-03-20T10:00:00Z",
            "IsDir": False,
        },
        {
            "Name": "officer_data.csv",
            "Size": 500,
            "ModTime": "2026-03-19T08:00:00Z",
            "IsDir": False,
        },
    ]
)
FAKE_DIRS = json.dumps(
    [
        {"Name": "2024", "IsDir": True},
        {"Name": "2025", "IsDir": True},
    ]
)


FAKE_STATES = json.dumps(
    [
        {"Name": "az", "IsDir": True},
        {"Name": "ga", "IsDir": True},
        {"Name": "ca", "IsDir": True},
        {"Name": "SomeFile.txt", "IsDir": False},
    ]
)


def test_list_states_returns_lowercase_alpha_dirs():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=FAKE_STATES)
        states = client.list_states()
    assert states == ["az", "ga", "ca"]


def test_list_years_returns_directory_names():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=FAKE_DIRS)
        years = client.list_years("ga")
    assert years == ["2024", "2025"]


def test_lsjson_returns_files_only():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=FAKE_FILES)
        entries = client.lsjson("ga", "2025")
    assert len(entries) == 2
    assert all(not e.get("IsDir") for e in entries)


def test_lsjson_raises_on_rclone_error():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="auth failed", stdout=""
        )
        with pytest.raises(RuntimeError, match="rclone lsjson"):
            client.lsjson("ga", "2025")


def test_copy_calls_rclone_with_correct_paths():
    with tempfile.TemporaryDirectory() as d:
        client = RcloneClient(remote="dropbox:post-db-test", states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            client.copy("ga", "2025")
        cmd = mock_run.call_args[0][0]
        assert "copy" in cmd
        assert "dropbox:post-db-test/ga/2025/input/" in cmd
        assert os.path.join(d, "ga", "2025", "data", "input") in cmd


def test_copy_raises_on_rclone_error():
    with tempfile.TemporaryDirectory() as d:
        client = RcloneClient(remote="dropbox:post-db-test", states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="failed")
            with pytest.raises(RuntimeError, match="rclone copy"):
                client.copy("ga", "2025")


def test_copy_creates_dest_dir():
    with tempfile.TemporaryDirectory() as d:
        client = RcloneClient(remote="dropbox:post-db-test", states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            client.copy("ga", "2025")
        assert os.path.isdir(os.path.join(d, "ga", "2025", "data", "input"))


def test_has_groundtruth_true_when_output_dir_exists():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    dirs_with_output = json.dumps(
        [
            {"Name": "input", "IsDir": True},
            {"Name": "output", "IsDir": True},
        ]
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=dirs_with_output)
        assert client.has_groundtruth("ga", "2025") is True


def test_has_groundtruth_false_when_no_output_dir():
    client = RcloneClient(remote="dropbox:post-db-test", states_root="states")
    dirs_no_output = json.dumps([{"Name": "input", "IsDir": True}])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=dirs_no_output)
        assert client.has_groundtruth("ga", "2025") is False


def test_copy_groundtruth_calls_rclone_with_correct_paths():
    with tempfile.TemporaryDirectory() as d:
        client = RcloneClient(remote="dropbox:post-db-test", states_root=d)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            client.copy_groundtruth("ga", "2025")
        cmd = mock_run.call_args[0][0]
        assert "dropbox:post-db-test/ga/2025/output/" in cmd
        assert os.path.join(d, "ga", "2025", "data", "groundtruth") in cmd
