import json
import os
import tempfile

from pipeline.judge_parser import parse_judge_report, load_judge_report


# ── parse_judge_report (JSON input) ──────────────────────────────────────────

def test_parse_pass_json():
    r = parse_judge_report(
        json.dumps({"overall": "PASS", "has_groundtruth": True})
    )
    assert r.overall == "PASS" and r.passed is True


def test_parse_fail_json():
    r = parse_judge_report(
        json.dumps({"overall": "FAIL", "has_groundtruth": True})
    )
    assert r.overall == "FAIL" and r.passed is False


def test_warn_counts_as_passed_json():
    r = parse_judge_report(
        json.dumps({"overall": "WARN", "has_groundtruth": False})
    )
    assert r.overall == "WARN" and r.passed is True


def test_no_groundtruth_flag_json():
    r = parse_judge_report(
        json.dumps({"overall": "PASS", "has_groundtruth": False})
    )
    assert r.has_groundtruth is False


# ── parse_judge_report (markdown fallback) ────────────────────────────────────

def test_parse_pass_markdown_fallback():
    r = parse_judge_report("**Overall result:** `PASS`\n")
    assert r.overall == "PASS" and r.passed is True


def test_no_groundtruth_markdown_fallback():
    r = parse_judge_report(
        "**Overall result:** `PASS`\nNo ground truth found\n"
    )
    assert r.has_groundtruth is False


# ── load_judge_report ─────────────────────────────────────────────────────────

def test_load_prefers_json_over_md():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "judge_report.json"), "w") as f:
            json.dump({"overall": "PASS", "has_groundtruth": True}, f)
        with open(os.path.join(d, "judge_report.md"), "w") as f:
            f.write("**Overall result:** `FAIL`\n")
        r = load_judge_report(d)
        assert r.overall == "PASS"  # JSON wins


def test_load_falls_back_to_md():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "judge_report.md"), "w") as f:
            f.write("**Overall result:** `WARN`\n")
        r = load_judge_report(d)
        assert r.overall == "WARN"


def test_load_raises_when_neither_exists():
    with tempfile.TemporaryDirectory() as d:
        import pytest
        with pytest.raises(FileNotFoundError):
            load_judge_report(d)
