"""Tests for db/preprocess/src/src.py — year-scoped path support."""

import os
import sys
import tempfile


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
        assert result[0][1] == "georgia-processed.csv.gz"


def test_find_index_files_with_year_finds_discipline_csv():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        _make_index(d, "ga", "2025", "ga-discipline_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        names = [r[1] for r in result]
        assert "georgia-processed.csv.gz" in names
        assert "georgia-discipline-processed.csv.gz" in names


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


# ---------------------------------------------------------------------------
# find_index_files — canonical output naming
# ---------------------------------------------------------------------------


def test_find_index_files_full_name_dir_matches_code_dir():
    """states/california/... and states/ca/... produce the same output name."""
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ca", "2026", "ca_index.csv")
        _make_index(d, "california", "2026", "california_index.csv")
        by_code = preprocess_src.find_index_files(d, "ca", year="2026")
        by_name = preprocess_src.find_index_files(d, "california", year="2026")
        assert by_code[0][1] == "california-processed.csv.gz"
        assert by_name[0][1] == "california-processed.csv.gz"


def test_find_index_files_flags_discipline():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "ga", "2025", "ga_index.csv")
        _make_index(d, "ga", "2025", "ga-discipline_index.csv")
        result = preprocess_src.find_index_files(d, "ga", year="2025")
        flags = {r[1]: r[2] for r in result}
        assert flags["georgia-processed.csv.gz"] is False
        assert flags["georgia-discipline-processed.csv.gz"] is True


def test_find_index_files_unknown_state_with_data_raises():
    with tempfile.TemporaryDirectory() as d:
        _make_index(d, "zz", "2025", "zz_index.csv")
        try:
            preprocess_src.find_index_files(d, "zz", year="2025")
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for unknown state 'zz'")


def test_find_index_files_non_state_dir_does_not_raise():
    """states/helpers/ has no index CSVs, so it must skip, not raise."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "helpers", "2025", "output"))
        assert preprocess_src.find_index_files(d, "helpers", "2025") == []


# ---------------------------------------------------------------------------
# collapse_contiguous_stints — gated by COLLAPSE_STINTS
# ---------------------------------------------------------------------------


def _stint_frame():
    import pandas as pd

    # Two adjacent rows at one agency (should merge) plus one after a real gap
    # (should not).
    return pd.DataFrame(
        {
            "person_nbr": ["a1", "a1", "a1"],
            "first_name": ["jo", "jo", "jo"],
            "last_name": ["doe", "doe", "doe"],
            "agency_name": ["acme pd", "acme pd", "acme pd"],
            "start_date": ["2010-01-01", "2012-01-01", "2020-01-01"],
            "end_date": ["2011-12-31", "2013-06-30", "2021-01-01"],
        }
    )


def test_california_is_in_collapse_set():
    assert "california" in preprocess_src.COLLAPSE_STINTS


def test_collapse_merges_contiguous_and_keeps_gaps():
    out = preprocess_src.collapse_contiguous_stints(_stint_frame())
    assert len(out) == 2
    merged = out[out.start_date == "2010-01-01"].iloc[0]
    assert merged.end_date == "2013-06-30"


def test_apply_transformations_collapse_off_by_default():
    df = _stint_frame()
    assert len(preprocess_src.apply_transformations(df.copy())) == 3


def test_apply_transformations_collapse_on_when_requested():
    df = _stint_frame()
    out = preprocess_src.apply_transformations(df.copy(), collapse_stints=True)
    assert len(out) == 2
