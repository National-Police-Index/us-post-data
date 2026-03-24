"""Tests for db/preprocess/src/src.py — year-scoped path support."""
import os
import sys
import tempfile

import pytest

# Make the preprocess module importable
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "..", "db", "preprocess", "src"
    ),
)
import src as preprocess_src  # noqa: E402


def _make_index(root, state, year, filename):
    """Create a fake _index.csv file at states/<state>/<year>/output/<name>."""
    out_dir = os.path.join(root, state, year, "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write("person_nbr,first_name,last_name\n")
    return path


# ---------------------------------------------------------------------------
# find_index_files — year-scoped path
# ---------------------------------------------------------------------------


def test_find_index_files_with_year_finds_csv():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        assert len(result) == 1
        assert result[0][1] == "ga-processed.csv.gz"


def test_find_index_files_with_year_finds_discipline_csv():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        _make_index(d, "ga", "2025", "ga-discipline_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        names = [r[1] for r in result]
        assert "ga-processed.csv.gz" in names
        assert "ga-discipline-processed.csv.gz" in names


def test_find_index_files_wrong_year_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2024")
        assert result == []


def test_find_index_files_missing_state_returns_empty():
    with tempfile.TemporaryDirectory() as d:
        result = preprocess_src.find_index_files(d, "zz", year="2025")
        assert result == []


def test_find_index_files_ignores_non_index_files():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        # Create a non-index file in the same output dir
        out_dir = os.path.join(d, "ga", "2025", "output")
        with open(os.path.join(out_dir, "judge_report.md"), "w") as f:
            f.write("PASS")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        assert len(result) == 1


def test_find_index_files_correct_src_path():
    with tempfile.TemporaryDirectory() as d:
        expected = _make_index(d, "ga", "2025", "ga_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        assert result[0][0] == expected
