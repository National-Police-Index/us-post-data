"""Tests for db/helpers/state_names.py."""

import os

from db.helpers.state_names import STATE_NAMES, resolve_state_name


def test_resolves_two_letter_code():
    assert resolve_state_name("ca") == "california"
    assert resolve_state_name("ga") == "georgia"
    assert resolve_state_name("az") == "arizona"


def test_resolves_full_name_unchanged():
    assert resolve_state_name("california") == "california"
    assert resolve_state_name("new-mexico") == "new-mexico"


def test_normalizes_case_whitespace_and_underscores():
    assert resolve_state_name(" CA ") == "california"
    assert resolve_state_name("NEW_MEXICO") == "new-mexico"
    assert resolve_state_name("west virginia") == "west-virginia"


def test_unknown_state_raises():
    for bad in ("zz", "", "californa", "usa"):
        try:
            resolve_state_name(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_full_names_are_hyphenated_lowercase():
    for code, name in STATE_NAMES.items():
        assert code == code.lower(), code
        assert len(code) == 2, code
        assert name == name.lower(), name
        assert " " not in name and "_" not in name, name


def test_full_names_are_unique():
    assert len(set(STATE_NAMES.values())) == len(STATE_NAMES)


def test_states_present_in_repo_are_mapped():
    """Every state directory under states/ must resolve."""
    states_dir = os.path.join(os.path.dirname(__file__), "..", "..", "states")
    for entry in os.listdir(states_dir):
        if entry == "helpers" or not os.path.isdir(
            os.path.join(states_dir, entry)
        ):
            continue
        resolve_state_name(entry)
