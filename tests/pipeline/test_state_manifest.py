import os
import tempfile

from pipeline.state_manifest import StateManifest


def test_get_entry_returns_none_for_unknown():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        assert m.get_entry("ga", "2025", "officer_employment.csv") is None


def test_round_trip_single_entry():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "manifest.json")
        m = StateManifest(path)
        m.set_entry(
            "ga",
            "2025",
            "officer_employment.csv",
            size=100,
            mtime="2026-03-20T10:00:00Z",
        )
        m.save()
        m2 = StateManifest(path)
        entry = m2.get_entry("ga", "2025", "officer_employment.csv")
        assert entry["size"] == 100
        assert entry["mtime"] == "2026-03-20T10:00:00Z"


def test_changed_files_detects_size_change():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry(
            "ga", "2025", "f.csv", size=100, mtime="2026-03-20T10:00:00Z"
        )
        current = [
            {"Name": "f.csv", "Size": 200, "ModTime": "2026-03-20T10:00:00Z"}
        ]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_changed_files_detects_mtime_change():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry(
            "ga", "2025", "f.csv", size=100, mtime="2026-03-19T10:00:00Z"
        )
        current = [
            {"Name": "f.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"}
        ]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_unchanged_file_not_returned():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry(
            "ga", "2025", "f.csv", size=50, mtime="2026-03-20T10:00:00Z"
        )
        current = [
            {"Name": "f.csv", "Size": 50, "ModTime": "2026-03-20T10:00:00Z"}
        ]
        assert m.changed_files("ga", "2025", current) == []


def test_new_file_detected_as_changed():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        current = [
            {"Name": "f.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"}
        ]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_update_from_lsjson_writes_all_entries():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        entries = [
            {"Name": "a.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"},
            {"Name": "b.csv", "Size": 50, "ModTime": "2026-03-20T10:00:00Z"},
        ]
        m.update_from_lsjson("ga", "2025", entries)
        assert m.get_entry("ga", "2025", "a.csv")["size"] == 100
        assert m.get_entry("ga", "2025", "b.csv")["size"] == 50
