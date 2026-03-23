# Automated rclone → Clean → PR → Firebase Pipeline (v2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **Status (2026-03-23):** All 12 tasks implemented + post-implementation fixes + CA end-to-end validated. 56 tests passing.
> Branch: `ai-dropbox-claude-integration` (not yet pushed to origin).
>
> **Original deviations (carried over):**
> - `test_cleaning.py` renamed to `validate.py` throughout
> - `judge_parser.py` reads `judge_report.json` (preferred) with markdown fallback; `validate.py` must write both formats
> - `validate.py` is required (not optional) — `clean_runner.py` errors if missing
> - `pipeline/data/` gitignore exceptions added (was blocked by `data/` and `*.csv`/`*.json` rules)
> - `RcloneClient` default remote changed to `dropbox:post-db-test` for local dev/testing
>
> **Post-implementation fixes (2026-03-22 evening):**
> - **Logging added throughout** — `pipeline/logs/` directory created; all modules use Python `logging`; `pipeline/main.py` sets up FileHandler (DEBUG) + StreamHandler (INFO) writing to `pipeline/logs/pipeline-<timestamp>.log`
> - **CC agent rewritten** — replaced `subprocess.Popen(["claude", "--print", ...])` with Anthropic Python SDK tool-use loop. Root cause: `claude --print` exits 0 with empty stdout when called from within an existing Claude Code session. SDK uses `ANTHROPIC_API_KEY` env var (set in `states/helpers/.env` for local dev, GitHub secret in CI).
> - **SDK tool-use loop** — `cc_agent.py` defines tools (`read_file`, `write_file`, `append_to_file`, `edit_file`, `bash`), `MAX_TURNS=100`, `MAX_TOKENS=16384`, `MODEL=claude-sonnet-4-6`. Each turn streamed to `pipeline/logs/cc-agent-<state>-<year>-<ts>.log` with `buffering=1`.
> - **`pr_generator.py`** — `gh pr create` failure now caught as `CalledProcessError` so pipeline doesn't crash when `gh` isn't authenticated.
> - **`pyproject.toml`** — `anthropic>=0.46.0` added as dependency.
>
> **2026-03-23 fixes:**
> - **`append_to_file` + `edit_file` tools added to CC agent** — agent no longer needs to write the full file in one response; builds scripts incrementally. Prompt updated to enforce writing by turn 3.
> - **`MAX_TOKENS` raised to 16384** — safety net for large responses.
> - **`readmes/<STATE>_README.md` wired into CC agent** — `_has_readme()` checks `readmes/<STATE>_README.md` locally; prompt includes path when present. Previously the agent had no access to state-specific context.
> - **`DATA_PREPROCESSING.md` updated** — paths now include `<year>`, `test_cleaning.py` → `validate.py` throughout, Step 13 shows argparse pattern.
> - **`AGENT_INSTRUCTIONS.md` updated** — dir tree shows `readmes/` at repo root, new "State README" section.
> - **`CLAUDE.md` updated** — reflects automated pipeline, correct paths, CC agent docs, secrets table.
> - **`rclone_client.py`** — added `has_readme()` and `copy_readme()` for potential future Dropbox-hosted readmes (currently unused; local `readmes/` dir takes precedence).
> - **Orchestrator** — fetches Dropbox readme once per unique state if present.
> - **56 tests passing** (added `test_append_to_file_creates_and_appends`, `test_edit_file_replaces_string`, `test_edit_file_errors_when_string_not_found`).
>
> **CA end-to-end validation (2026-03-23):**
> - Both input files present: `CPRA_R000301-011425__ADHOC-809.xlsx` (POST/LEO) + `PDSQ118B-C_CDCR Appts&Seps 2005-2023_Final.csv` (corrections)
> - CC agent finished in 88 turns — PASS, 26/26 checks
> - Output: 595,260 rows (LEO: 451,552 exact match; CDCR: 143,708 / 1.8% diff vs GT)
> - 96.9% key match rate on (person_nbr, agency_name, start_date)
>
> **Current state / next steps:**
> - `states/ca/2025/` — clean.py + validate.py written by agent, output/ has PASS judge report
> - `pipeline/data/registry.csv` — ca/2025 marked cleaned=yes
> - `pipeline/data/manifest.json` — ca/2025 snapshot stored
> - GA not yet tested end-to-end (input dir empty)
> - Branch has uncommitted changes — commit and push when ready
> - To run GA: `set -a && source states/helpers/.env && set +a && RCLONE_REMOTE=dropbox:post-db-test python3 -m pipeline.main --states ga`

**Goal:** Poll Dropbox for new POST data using rclone, detect changes per `(state, year)` pair, run cleaning pipelines (using Claude Code for new state+year combos), open a GitHub PR, and trigger a Firebase upload on merge (latest year only per state).

**Architecture:** A Python `pipeline/` package handles change detection (via `rclone lsjson` + a git-tracked manifest), file syncing, clean-script execution, and PR creation. A `registry.csv` tracks cleaned/firebase status per `(state, year)` and enables manifest pre-seeding for already-processed pairs.

**Tech Stack:** Python 3.11, `rclone` CLI, `gh` CLI, `claude` CLI (headless), existing `db/` Makefile, GitHub Actions.

---

## Directory structure

```
states/ga/
  2025/
    src/
      clean.py           ← year-specific script
      test_cleaning.py
    data/
      input/             ← synced from Dropbox ga/2025/input/ ONLY
      groundtruth/       ← local only, NOT synced from Dropbox
    output/              ← judge_report.md + cleaned CSVs
```

- State codes are **lowercase everywhere** (local dirs, rclone paths, registry)
- Each `(state, year)` is fully self-contained — src scripts are NOT shared across years
- `data/input/` and `output/` are gitignored (raw data / generated files)

---

## pipeline/data/ files (tracked in git)

### manifest.json

Stores rclone lsjson snapshots per `(state, year)`. Auto-managed.

```json
{
  "ga": {
    "2025": {
      "officer_employment.csv": {"size": 100, "mtime": "2025-01-01T00:00:00Z"}
    }
  }
}
```

### registry.csv

Tracks cleaning and Firebase status per `(state, year)`. Human-editable.

```csv
state,year,cleaned,firebase_pushed
ga,2025,no,no
```

`firebase_pushed` values: `no` / `yes` / `skipped` (cleaned but superseded by a newer year).

---

## How change detection + pre-seeding works

```
startup:
  load registry.csv
  → for each row where cleaned=yes and no manifest entry for (state, year):
      fetch lsjson → seed manifest (no cleaning triggered)

poll loop (per state, per year):
  → list_years(state) via rclone lsjson
  → for each year:
      lsjson(state, year) → compare to manifest
      if changed: rclone copy → clean → update registry
      else: skip

after all states:
  → save manifest.json + registry.csv
  → commit both
  → open PR for changed pairs
```

---

## Firebase push logic

After all cleaning:
- For each state, find the **highest year** where `cleaned=yes` and `firebase_pushed=no`
- Push that year; mark `firebase_pushed=yes`
- Mark all older `firebase_pushed=no` years for that state as `skipped`

---

## CC agent for new (state, year) pairs

- **New state entirely:** fresh prompt with no prior context
- **New year of existing state:** find most recent prior year's `clean.py`, include as context in prompt (adapt, don't blindly copy)
- All `clean.py` scripts accept `--input-dir` and `--output-dir` CLI args
- Scripts run with `cwd=states/<state>/<year>/` so relative paths within scripts resolve naturally

---

## Test scenario

Initial end-to-end test runs against `dropbox:post-db-test` with two states:

| State | Dropbox `input/` | Dropbox `output/` | Local files | Expected path |
|-------|-----------------|-------------------|-------------|---------------|
| `ga` | yes | yes → `data/groundtruth/` | none (removed) | CC agent + CSV groundtruth |
| `ca` | yes | yes → `data/groundtruth/` | none | CC agent + CSV groundtruth |

GA is a complex dataset; CA is simpler. Both go through the CC agent since
neither has a local `clean.py`. Both have Dropbox `output/` which is synced
to `data/groundtruth/` before the agent runs.

Run with:
```bash
RCLONE_REMOTE=dropbox:post-db-test python -m pipeline.main --states ga ca
```

---

## Orientation — existing code

| File | What it does |
|------|-------------|
| `states/helpers/llm_models.py` | Azure OpenAI wrapper used by test suites |
| `db/preprocess/src/src.py` | Normalises cleaned CSVs → `.csv.gz` |
| `db/upload/src/src.py` | Uploads to Firebase `db_launch` |
| `db/Makefile` | `make dry-run STATE=GA`, `make upload STATE=GA` |
| `DATA_PREPROCESSING.md` | Authoritative cleaning spec |
| `states/AGENT_INSTRUCTIONS.md` | Brief for CC agents |
| `pipeline/data/groundtruth.md` | Quality reference for states without CSV groundtruth |

---

## Task 1: StateManifest — persist rclone lsjson snapshots per (state, year) ✅

**Files:**
- Create: `pipeline/__init__.py` (empty)
- Create: `pipeline/state_manifest.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/pipeline/__init__.py` (empty)
- Create: `tests/pipeline/test_state_manifest.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_state_manifest.py
import json, os, tempfile
from pipeline.state_manifest import StateManifest


def test_get_entry_returns_none_for_unknown():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        assert m.get_entry("ga", "2025", "officer_employment.csv") is None


def test_round_trip_single_entry():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "manifest.json")
        m = StateManifest(path)
        m.set_entry("ga", "2025", "officer_employment.csv",
                    size=100, mtime="2026-03-20T10:00:00Z")
        m.save()
        m2 = StateManifest(path)
        entry = m2.get_entry("ga", "2025", "officer_employment.csv")
        assert entry["size"] == 100
        assert entry["mtime"] == "2026-03-20T10:00:00Z"


def test_changed_files_detects_size_change():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry("ga", "2025", "f.csv", size=100, mtime="2026-03-20T10:00:00Z")
        current = [{"Name": "f.csv", "Size": 200, "ModTime": "2026-03-20T10:00:00Z"}]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_changed_files_detects_mtime_change():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry("ga", "2025", "f.csv", size=100, mtime="2026-03-19T10:00:00Z")
        current = [{"Name": "f.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"}]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_unchanged_file_not_returned():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        m.set_entry("ga", "2025", "f.csv", size=50, mtime="2026-03-20T10:00:00Z")
        current = [{"Name": "f.csv", "Size": 50, "ModTime": "2026-03-20T10:00:00Z"}]
        assert m.changed_files("ga", "2025", current) == []


def test_new_file_detected_as_changed():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        current = [{"Name": "f.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"}]
        assert "f.csv" in m.changed_files("ga", "2025", current)


def test_update_from_lsjson_writes_all_entries():
    with tempfile.TemporaryDirectory() as d:
        m = StateManifest(os.path.join(d, "manifest.json"))
        entries = [
            {"Name": "a.csv", "Size": 100, "ModTime": "2026-03-20T10:00:00Z"},
            {"Name": "b.csv", "Size": 50,  "ModTime": "2026-03-20T10:00:00Z"},
        ]
        m.update_from_lsjson("ga", "2025", entries)
        assert m.get_entry("ga", "2025", "a.csv")["size"] == 100
        assert m.get_entry("ga", "2025", "b.csv")["size"] == 50
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_state_manifest.py -v
```
Expected: `ModuleNotFoundError: No module named 'pipeline'`

**Step 3: Implement**

```python
# pipeline/__init__.py
# (empty)

# pipeline/state_manifest.py
from __future__ import annotations
import json
import os


class StateManifest:
    """
    Persists rclone lsjson snapshots per (state, year) for change detection.
    Stored as pipeline/data/manifest.json, tracked in git.
    """

    def __init__(self, path: str):
        self._path = path
        self._data: dict = {}
        if os.path.exists(path):
            with open(path) as f:
                self._data = json.load(f)

    def get_entry(
        self, state: str, year: str, filename: str
    ) -> dict | None:
        return self._data.get(state, {}).get(year, {}).get(filename)

    def set_entry(
        self, state: str, year: str, filename: str, size: int, mtime: str
    ) -> None:
        self._data.setdefault(state, {}).setdefault(year, {})[filename] = {
            "size": size,
            "mtime": mtime,
        }

    def update_from_lsjson(
        self, state: str, year: str, entries: list[dict]
    ) -> None:
        for e in entries:
            self.set_entry(
                state, year, e["Name"], size=e["Size"], mtime=e["ModTime"]
            )

    def changed_files(
        self, state: str, year: str, current: list[dict]
    ) -> list[str]:
        changed = []
        for entry in current:
            name = entry["Name"]
            stored = self.get_entry(state, year, name)
            if stored is None:
                changed.append(name)
            elif (
                stored["size"] != entry["Size"]
                or stored["mtime"] != entry["ModTime"]
            ):
                changed.append(name)
        return changed

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_state_manifest.py -v
```
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add pipeline/__init__.py pipeline/state_manifest.py \
        tests/__init__.py tests/pipeline/__init__.py \
        tests/pipeline/test_state_manifest.py
git commit -m "feat(pipeline): add StateManifest keyed by (state, year)"
```

---

## Task 2: rclone client — list_years, lsjson, copy ✅

**Files:**
- Create: `pipeline/rclone_client.py`
- Create: `tests/pipeline/test_rclone_client.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_rclone_client.py
import json, os, tempfile
import pytest
from unittest.mock import patch, MagicMock
from pipeline.rclone_client import RcloneClient

FAKE_FILES = json.dumps([
    {"Name": "officer_employment.csv", "Size": 1000,
     "ModTime": "2026-03-20T10:00:00Z", "IsDir": False},
    {"Name": "officer_data.csv", "Size": 500,
     "ModTime": "2026-03-19T08:00:00Z", "IsDir": False},
])
FAKE_DIRS = json.dumps([
    {"Name": "2024", "IsDir": True},
    {"Name": "2025", "IsDir": True},
])


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
        mock_run.return_value = MagicMock(returncode=1, stderr="auth failed",
                                          stdout="")
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
    dirs_with_output = json.dumps([
        {"Name": "input",  "IsDir": True},
        {"Name": "output", "IsDir": True},
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0,
                                          stdout=dirs_with_output)
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
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_rclone_client.py -v
```
Expected: `ImportError`

**Step 3: Implement**

```python
# pipeline/rclone_client.py
from __future__ import annotations
import json
import os
import subprocess


class RcloneClient:
    def __init__(
        self,
        remote: str = "dropbox:national-post-db",
        states_root: str = "states",
    ):
        self._remote = remote.rstrip("/")
        self._states_root = states_root

    def _dest(self, state: str, year: str) -> str:
        return os.path.join(self._states_root, state, year, "data", "input")

    def list_years(self, state: str) -> list[str]:
        """Return year subdirectories for a state on the remote."""
        path = f"{self._remote}/{state}/"
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rclone lsjson failed for {state}: {proc.stderr}"
            )
        entries = json.loads(proc.stdout or "[]")
        return [e["Name"] for e in entries if e.get("IsDir", False)]

    def lsjson(self, state: str, year: str) -> list[dict]:
        """Return file entries for state/year/input/ on the remote."""
        path = f"{self._remote}/{state}/{year}/input/"
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rclone lsjson failed for {state}/{year}: {proc.stderr}"
            )
        entries = json.loads(proc.stdout or "[]")
        return [e for e in entries if not e.get("IsDir", False)]

    def copy(self, state: str, year: str) -> None:
        """rclone copy state/year/input/ to local. Raises on failure."""
        dest = self._dest(state, year)
        os.makedirs(dest, exist_ok=True)
        proc = subprocess.run(
            [
                "rclone", "copy",
                f"{self._remote}/{state}/{year}/input/",
                dest,
            ],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rclone copy failed for {state}/{year}: {proc.stderr}"
            )

    def has_groundtruth(self, state: str, year: str) -> bool:
        """Return True if state/year/output/ exists on the remote."""
        path = f"{self._remote}/{state}/{year}/"
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return False
        entries = json.loads(proc.stdout or "[]")
        return any(
            e["Name"] == "output" and e.get("IsDir", False)
            for e in entries
        )

    def copy_groundtruth(self, state: str, year: str) -> None:
        """
        rclone copy state/year/output/ → local data/groundtruth/.
        Used to download state-provided groundtruth before cleaning.
        """
        dest = os.path.join(
            self._states_root, state, year, "data", "groundtruth"
        )
        os.makedirs(dest, exist_ok=True)
        proc = subprocess.run(
            [
                "rclone", "copy",
                f"{self._remote}/{state}/{year}/output/",
                dest,
            ],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rclone copy_groundtruth failed for {state}/{year}: "
                f"{proc.stderr}"
            )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_rclone_client.py -v
```
Expected: 9 PASSED

**Step 5: Commit**

```bash
git add pipeline/rclone_client.py tests/pipeline/test_rclone_client.py
git commit -m "feat(pipeline): add RcloneClient with list_years, lsjson, copy per (state, year)"
```

---

## Task 3: Registry — track (state, year) cleaning and Firebase status ✅

**Files:**
- Create: `pipeline/registry.py`
- Create: `pipeline/data/.gitkeep`
- Create: `pipeline/data/registry.csv` (initial seed)
- Create: `tests/pipeline/test_registry.py`

**Initial `pipeline/data/registry.csv`:**

```csv
state,year,cleaned,firebase_pushed
```

Empty to start — both GA and CA are new and will be added by the pipeline
after cleaning.

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_registry.py
import os, tempfile, textwrap
from pipeline.registry import Registry

def _reg(tmp, content):
    path = os.path.join(tmp, "registry.csv")
    with open(path, "w") as f:
        f.write("state,year,cleaned,firebase_pushed\n" + content)
    return Registry(path)


def test_is_cleaned_true():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,no\n")
        assert r.is_cleaned("xx", "2001") is True


def test_is_cleaned_false():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,no,no\n")
        assert r.is_cleaned("xx", "2001") is False
        assert r.is_cleaned("zz", "2001") is False


def test_firebase_pushed_values():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,yes,skipped\nxx,2003,no,no\n")
        assert r.firebase_pushed("xx", "2001") == "yes"
        assert r.firebase_pushed("xx", "2002") == "skipped"
        assert r.firebase_pushed("xx", "2003") == "no"
        assert r.firebase_pushed("zz", "9999") == "no"  # unknown → default


def test_get_preseed_pairs_returns_cleaned_only():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,no,no\nyy,2001,yes,no\n")
        pairs = r.get_preseed_pairs()
        assert ("xx", "2001") in pairs   # cleaned=yes
        assert ("yy", "2001") in pairs   # cleaned=yes
        assert ("xx", "2002") not in pairs  # cleaned=no


def test_upsert_new_row_persists():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry.csv")
        with open(path, "w") as f:
            f.write("state,year,cleaned,firebase_pushed\n")
        r = Registry(path)
        r.upsert("xx", "2001", cleaned="yes", firebase_pushed="no")
        r.save()
        assert Registry(path).is_cleaned("xx", "2001") is True


def test_get_firebase_target_returns_highest_unpushed():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,yes,no\nxx,2003,yes,no\n")
        assert r.get_firebase_target("xx") == "2003"  # highest unpushed


def test_get_firebase_target_none_when_all_pushed_or_uncleaned():
    with tempfile.TemporaryDirectory() as d:
        r = _reg(d, "xx,2001,yes,yes\nxx,2002,no,no\n")
        assert r.get_firebase_target("xx") is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_registry.py -v
```
Expected: `ImportError`

**Step 3: Implement**

```python
# pipeline/registry.py
from __future__ import annotations
import csv
import os

_FIELDS = ["state", "year", "cleaned", "firebase_pushed"]


class Registry:
    """
    Tracks per-(state, year) cleaning and Firebase push status.
    Backed by pipeline/data/registry.csv, tracked in git.
    Human-editable to override pipeline decisions.
    """

    def __init__(self, path: str):
        self._path = path
        self._rows: dict[tuple[str, str], dict] = {}
        if os.path.exists(path):
            with open(path, newline="") as f:
                for row in csv.DictReader(f):
                    self._rows[(row["state"], row["year"])] = dict(row)

    def _get(self, state: str, year: str) -> dict | None:
        return self._rows.get((state, year))

    def is_cleaned(self, state: str, year: str) -> bool:
        row = self._get(state, year)
        return row is not None and row.get("cleaned") == "yes"

    def firebase_pushed(self, state: str, year: str) -> str:
        row = self._get(state, year)
        return row["firebase_pushed"] if row else "no"

    def get_preseed_pairs(self) -> list[tuple[str, str]]:
        """Return (state, year) pairs that are cleaned (seed manifest)."""
        return [k for k, v in self._rows.items() if v.get("cleaned") == "yes"]

    def upsert(
        self,
        state: str,
        year: str,
        cleaned: str | None = None,
        firebase_pushed: str | None = None,
    ) -> None:
        key = (state, year)
        if key not in self._rows:
            self._rows[key] = {
                "state": state, "year": year,
                "cleaned": "no", "firebase_pushed": "no",
            }
        if cleaned is not None:
            self._rows[key]["cleaned"] = cleaned
        if firebase_pushed is not None:
            self._rows[key]["firebase_pushed"] = firebase_pushed

    def get_firebase_target(self, state: str) -> str | None:
        """
        Return the highest year for a state where cleaned=yes and
        firebase_pushed=no. Returns None if nothing is pending.
        """
        candidates = [
            year for (s, year), row in self._rows.items()
            if s == state
            and row.get("cleaned") == "yes"
            and row.get("firebase_pushed") == "no"
        ]
        return max(candidates) if candidates else None

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDS)
            writer.writeheader()
            for row in sorted(
                self._rows.values(),
                key=lambda r: (r["state"], r["year"]),
            ):
                writer.writerow(row)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_registry.py -v
```
Expected: 8 PASSED

**Step 5: Create initial registry and commit**

```bash
mkdir -p pipeline/data
printf 'state,year,cleaned,firebase_pushed\n' > pipeline/data/registry.csv
touch pipeline/data/.gitkeep
git add pipeline/registry.py pipeline/data/.gitkeep \
        pipeline/data/registry.csv pipeline/data/groundtruth.md \
        tests/pipeline/test_registry.py
git commit -m "feat(pipeline): add Registry, groundtruth.md quality reference"
```

---

## Task 4: Judge report parser ✅

**Files:**
- Create: `pipeline/judge_parser.py`
- Create: `tests/pipeline/test_judge_parser.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_judge_parser.py
from pipeline.judge_parser import parse_judge_report


def test_parse_pass():
    r = parse_judge_report("**Overall result:** `PASS`\n")
    assert r.overall == "PASS" and r.passed is True


def test_parse_fail():
    r = parse_judge_report("**Overall result:** `FAIL`\n")
    assert r.overall == "FAIL" and r.passed is False


def test_warn_counts_as_passed():
    r = parse_judge_report("**Overall result:** `WARN`\n")
    assert r.overall == "WARN" and r.passed is True


def test_no_groundtruth_flag():
    r = parse_judge_report("**Overall result:** `PASS`\nNo ground truth found\n")
    assert r.has_groundtruth is False


def test_groundtruth_present():
    r = parse_judge_report("**Overall result:** `PASS`\n")
    assert r.has_groundtruth is True
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_judge_parser.py -v
```

**Step 3: Implement**

```python
# pipeline/judge_parser.py
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class JudgeResult:
    overall: str
    passed: bool
    has_groundtruth: bool
    raw: str = field(repr=False)


def parse_judge_report(text: str) -> JudgeResult:
    m = re.search(r"\*\*Overall result:\*\*\s*`(\w+)`", text)
    overall = m.group(1).upper() if m else "FAIL"
    return JudgeResult(
        overall=overall,
        passed=overall in ("PASS", "WARN"),
        has_groundtruth="No ground truth found" not in text,
        raw=text,
    )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_judge_parser.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add pipeline/judge_parser.py tests/pipeline/test_judge_parser.py
git commit -m "feat(pipeline): add judge_parser"
```

---

## Task 5: Clean runner — run clean.py + validate.py per (state, year) ✅

Scripts run with `cwd=states/<state>/<year>/`. `clean.py` receives
`--input-dir data/input --output-dir output` so all relative paths resolve.

**Files:**
- Create: `pipeline/clean_runner.py`
- Create: `tests/pipeline/test_clean_runner.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_clean_runner.py
import os, tempfile
from unittest.mock import patch, MagicMock
from pipeline.clean_runner import CleanRunner, CleanResult

FAKE_REPORT = "**Overall result:** `PASS`\nNo ground truth found\n"


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
        assert CleanRunner(states_root=d).has_clean_script("zz", "2025") is False


def test_run_passes_input_and_output_dirs():
    with tempfile.TemporaryDirectory() as d:
        _, src, out = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        with open(os.path.join(out, "judge_report.md"), "w") as f:
            f.write(FAKE_REPORT)
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
        with open(os.path.join(out, "judge_report.md"), "w") as f:
            f.write(FAKE_REPORT)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = CleanRunner(states_root=d).run("ga", "2025")
        assert result.judge.passed is True


def test_run_returns_error_when_clean_script_fails():
    with tempfile.TemporaryDirectory() as d:
        _, src, _ = _make_year_dir(d)
        open(os.path.join(src, "clean.py"), "w").close()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error")
            result = CleanRunner(states_root=d).run("ga", "2025")
        assert result.error is not None and result.judge is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_clean_runner.py -v
```

**Step 3: Implement**

```python
# pipeline/clean_runner.py
from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass
from pipeline.judge_parser import JudgeResult, parse_judge_report


@dataclass
class CleanResult:
    state: str
    year: str
    judge: JudgeResult | None
    error: str | None = None

    @property
    def success(self) -> bool:
        return (
            self.error is None
            and self.judge is not None
            and self.judge.passed
        )


class CleanRunner:
    def __init__(self, states_root: str = "states"):
        self._states_root = states_root

    def _year_dir(self, state: str, year: str) -> str:
        return os.path.join(self._states_root, state, year)

    def has_clean_script(self, state: str, year: str) -> bool:
        return os.path.exists(
            os.path.join(self._year_dir(state, year), "src", "clean.py")
        )

    def run(self, state: str, year: str) -> CleanResult:
        year_dir = self._year_dir(state, year)
        proc = subprocess.run(
            [
                "python", os.path.join("src", "clean.py"),
                "--input-dir", os.path.join("data", "input"),
                "--output-dir", "output",
            ],
            cwd=year_dir, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return CleanResult(
                state=state, year=year, judge=None,
                error=proc.stderr or f"clean.py exited {proc.returncode}",
            )

        test_script = os.path.join(year_dir, "src", "test_cleaning.py")
        if os.path.exists(test_script):
            subprocess.run(
                ["python", os.path.join("src", "test_cleaning.py")],
                cwd=year_dir, capture_output=True, text=True,
            )

        report_path = os.path.join(year_dir, "output", "judge_report.md")
        if not os.path.exists(report_path):
            return CleanResult(
                state=state, year=year, judge=None,
                error="judge_report.md not found",
            )
        with open(report_path) as f:
            return CleanResult(
                state=state, year=year, judge=parse_judge_report(f.read())
            )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_clean_runner.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add pipeline/clean_runner.py tests/pipeline/test_clean_runner.py
git commit -m "feat(pipeline): add CleanRunner with (state, year) paths and CLI args"
```

---

## Task 6: CC agent — Anthropic SDK tool-use loop for new (state, year) pairs ✅

> **DEVIATION:** Original plan used `claude --print <prompt>` via subprocess.
> This was replaced with the **Anthropic Python SDK tool-use loop** because
> `claude --print` exits 0 with empty stdout when invoked from inside a Claude
> Code session. The SDK approach also works correctly in GitHub Actions CI
> (just needs `ANTHROPIC_API_KEY`).

For a new year of an existing state: find the most recent prior year's
`clean.py` and include it as context in the prompt (adapt, don't copy blindly).
For a brand-new state: fresh prompt.

**Key design:**
- `anthropic.Anthropic()` client, model `claude-sonnet-4-6`, `MAX_TURNS=100`
- Tools: `read_file`, `write_file`, `bash` (cwd=repo_root)
- Each turn streamed to `pipeline/logs/cc-agent-<state>-<year>-<ts>.log` with `buffering=1`
- Prompt tells agent: sample files with `head`/bash, do NOT read full CSVs, write clean.py early, stop on PASS/WARN
- Requires `ANTHROPIC_API_KEY` in env (`states/helpers/.env` locally, GitHub secret in CI)
- `pyproject.toml`: `anthropic>=0.46.0` added

**Files:**
- Create: `pipeline/cc_agent.py`
- Create: `tests/pipeline/test_cc_agent.py`
- Update: `pyproject.toml` (add `anthropic>=0.46.0`)

**Tests (53 total, patch target: `pipeline.cc_agent.anthropic.Anthropic`):**
- `test_prompt_includes_state_and_year`
- `test_prompt_includes_prior_clean_py`
- `test_prompt_references_validate_and_json_schema`
- `test_run_invokes_sdk_client`
- `test_run_returns_error_on_api_error`
- `test_run_finds_prior_year_clean_py`
- `test_run_tool_use_loop_executes_two_turns`
- `test_run_max_turns_returns_gracefully`

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_cc_agent.py -v
```

**Step 3: Implement**

```python
# pipeline/cc_agent.py
from __future__ import annotations
import os
import subprocess
from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import parse_judge_report


class CCAgent:
    def __init__(self, states_root: str = "states", repo_root: str = "."):
        self._states_root = states_root
        self._repo_root = repo_root

    def _find_prior_clean_py(self, state: str, year: str) -> str | None:
        state_dir = os.path.join(self._states_root, state)
        if not os.path.isdir(state_dir):
            return None
        prior_years = sorted(
            y for y in os.listdir(state_dir)
            if os.path.isdir(os.path.join(state_dir, y)) and y < year
        )
        for prior_year in reversed(prior_years):
            path = os.path.join(state_dir, prior_year, "src", "clean.py")
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()
        return None

    def _has_csv_groundtruth(self, state: str, year: str) -> bool:
        gt_dir = os.path.join(
            self._states_root, state, year, "data", "groundtruth"
        )
        return os.path.isdir(gt_dir) and any(
            f.endswith(".csv") for f in os.listdir(gt_dir)
        )

    def _build_prompt(
        self, state: str, year: str, prior_clean_py: str | None
    ) -> str:
        has_gt = self._has_csv_groundtruth(state, year)
        groundtruth_note = (
            f"CSV groundtruth files are available in "
            f"states/{state}/{year}/data/groundtruth/ — use them in "
            f"test_cleaning.py for row count and value comparison."
            if has_gt else
            f"No CSV groundtruth exists for this state. Use "
            f"pipeline/data/groundtruth.md as your quality reference "
            f"when writing test_cleaning.py."
        )
        base = (
            f"Read states/AGENT_INSTRUCTIONS.md and DATA_PREPROCESSING.md. "
            f"Process state {state}, year {year}: "
            f"inspect states/{state}/{year}/data/input/, "
            f"write states/{state}/{year}/src/clean.py accepting "
            f"--input-dir and --output-dir CLI args, "
            f"run it from states/{state}/{year}/ as cwd "
            f"(python src/clean.py --input-dir data/input "
            f"--output-dir output), "
            f"then write and run src/test_cleaning.py. "
            f"If judge report is FAIL, fix clean.py and re-run. "
            f"{groundtruth_note}"
        )
        if prior_clean_py:
            base += (
                f"\n\nPrior year's clean.py for reference "
                f"(adapt as needed — do not copy blindly):\n\n"
                f"```python\n{prior_clean_py}\n```"
            )
        return base

    def run(self, state: str, year: str) -> CleanResult:
        prior = self._find_prior_clean_py(state, year)
        prompt = self._build_prompt(state, year, prior_clean_py=prior)
        try:
            proc = subprocess.run(
                ["claude", "--print", prompt],
                cwd=self._repo_root, capture_output=True,
                text=True, timeout=600,
            )
        except FileNotFoundError:
            return CleanResult(state=state, year=year, judge=None,
                               error="claude CLI not found")
        except Exception as e:
            return CleanResult(state=state, year=year, judge=None,
                               error=str(e))

        if proc.returncode != 0:
            return CleanResult(
                state=state, year=year, judge=None,
                error=proc.stderr or f"claude exited {proc.returncode}",
            )

        report_path = os.path.join(
            self._states_root, state, year, "output", "judge_report.md"
        )
        if not os.path.exists(report_path):
            return CleanResult(state=state, year=year, judge=None,
                               error="judge_report.md not found")
        with open(report_path) as f:
            return CleanResult(
                state=state, year=year, judge=parse_judge_report(f.read())
            )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_cc_agent.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add pipeline/cc_agent.py tests/pipeline/test_cc_agent.py
git commit -m "feat(pipeline): add CCAgent with prior-year context for new (state, year)"
```

---

## Task 7: PR generator — commit outputs and open a GitHub PR ✅

`CleanResult` now carries `year`; PR body rows show `state/year`.

**Files:**
- Create: `pipeline/pr_generator.py`
- Create: `tests/pipeline/test_pr_generator.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_pr_generator.py
from unittest.mock import patch, MagicMock
from pipeline.pr_generator import build_pr_body, PRGenerator
from pipeline.clean_runner import CleanResult
from pipeline.judge_parser import JudgeResult


def _r(state, year="2025", overall="PASS", has_gt=True, error=None):
    if error:
        return CleanResult(state=state, year=year, judge=None, error=error)
    return CleanResult(
        state=state, year=year,
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
        gen.create_pr("data/update/2026-03-21", [_r("ga")])
    assert any("gh" in str(c) for c in mock_run.call_args_list)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_pr_generator.py -v
```

**Step 3: Implement**

```python
# pipeline/pr_generator.py
from __future__ import annotations
import subprocess
from datetime import date
from pipeline.clean_runner import CleanResult


def build_pr_body(results: list[CleanResult]) -> str:
    lines = [
        "## Automated POST Data Update",
        "",
        f"**Date:** {date.today().isoformat()}",
        "",
        "| State | Year | Result | Ground Truth | Notes |",
        "|-------|------|--------|-------------|-------|",
    ]
    for r in results:
        if r.error:
            lines.append(
                f"| {r.state} | {r.year} | FAIL | — "
                f"| `{r.error[:80]}` |"
            )
        else:
            gt = "Yes" if r.judge.has_groundtruth else "⚠️ No ground truth"
            lines.append(
                f"| {r.state} | {r.year} | {r.judge.overall} | {gt} | |"
            )

    for r in results:
        if r.judge and not r.judge.has_groundtruth:
            lines.append(
                f"\n> **{r.state}/{r.year}:** "
                f"No ground truth — manual review recommended."
            )

    lines += ["", "---", "_Generated by the automated rclone pipeline._"]
    return "\n".join(lines)


class PRGenerator:
    def __init__(self, repo_root: str = "."):
        self._repo_root = repo_root

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self._repo_root,
            capture_output=True, text=True,
        )

    def commit_outputs(
        self, pairs: list[tuple[str, str]], branch: str
    ) -> None:
        self._git("checkout", "-b", branch)
        for state, year in pairs:
            self._git(
                "add",
                f"states/{state}/{year}/output/",
                f"states/{state}/{year}/src/clean.py",
            )
        self._git("add", "pipeline/data/manifest.json",
                  "pipeline/data/registry.csv")
        label = ", ".join(f"{s}/{y}" for s, y in pairs)
        self._git("commit", "-m", f"data: automated POST update for {label}")

    def create_pr(
        self,
        branch: str,
        results: list[CleanResult],
        base: str = "main",
    ) -> None:
        label = ", ".join(f"{r.state}/{r.year}" for r in results)
        subprocess.run(
            [
                "gh", "pr", "create",
                "--title", f"data: automated POST update — {label}",
                "--body", build_pr_body(results),
                "--base", base,
                "--head", branch,
            ],
            cwd=self._repo_root, check=True,
        )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_pr_generator.py -v
```
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add pipeline/pr_generator.py tests/pipeline/test_pr_generator.py
git commit -m "feat(pipeline): add PRGenerator (state/year aware)"
```

---

## Task 8: Orchestrator — wire everything together ✅

**Files:**
- Create: `pipeline/orchestrate.py`
- Create: `tests/pipeline/test_orchestrate.py`

**Step 1: Write the failing tests**

```python
# tests/pipeline/test_orchestrate.py
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
            {"Name": "officer_employment.csv", "Size": 100,
             "ModTime": "2026-03-21T10:00:00Z"}
        ]
        fake_result = CleanResult(
            state="ga", year="2025",
            judge=JudgeResult("PASS", True, True, raw=""),
        )
        with patch.object(orch._rclone, "list_years", return_value=["2025"]):
            with patch.object(orch._rclone, "lsjson",
                               return_value=fake_lsjson):
                with patch.object(orch._rclone, "copy"):
                    with patch.object(orch._runner, "has_clean_script",
                                       return_value=True):
                        with patch.object(orch._runner, "run",
                                           return_value=fake_result):
                            with patch.object(orch._pr_gen,
                                               "commit_outputs"):
                                with patch.object(
                                    orch._pr_gen, "create_pr"
                                ) as mock_pr:
                                    orch.run(states=["ga"])
        mock_pr.assert_called_once()
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/pipeline/test_orchestrate.py -v
```

**Step 3: Implement**

```python
# pipeline/orchestrate.py
from __future__ import annotations
import os
from datetime import date
from pipeline.rclone_client import RcloneClient
from pipeline.state_manifest import StateManifest
from pipeline.registry import Registry
from pipeline.clean_runner import CleanRunner, CleanResult
from pipeline.cc_agent import CCAgent
from pipeline.pr_generator import PRGenerator


class Orchestrator:
    def __init__(
        self,
        rclone_remote: str = "dropbox:national-post-db",
        states_root: str = "states",
        repo_root: str = ".",
        manifest_path: str = "pipeline/data/manifest.json",
        registry_path: str = "pipeline/data/registry.csv",
    ):
        self._rclone = RcloneClient(
            remote=rclone_remote, states_root=states_root
        )
        self._manifest = StateManifest(manifest_path)
        self._registry = Registry(registry_path)
        self._runner = CleanRunner(states_root=states_root)
        self._cc_agent = CCAgent(
            states_root=states_root, repo_root=repo_root
        )
        self._pr_gen = PRGenerator(repo_root=repo_root)
        self._states_root = states_root

    def run(self, states: list[str] | None = None) -> None:
        all_states = states or self._discover_states()

        # 1. Pre-seed manifest from registry (no cleaning for these)
        self._preseed_manifest(all_states)

        # 2. Detect changed (state, year) pairs
        changed_pairs: list[tuple[str, str]] = []
        lsjson_cache: dict[tuple[str, str], list[dict]] = {}

        for state in all_states:
            try:
                years = self._rclone.list_years(state)
            except RuntimeError as e:
                print(f"  [{state}] list_years error: {e}")
                continue
            for year in years:
                try:
                    entries = self._rclone.lsjson(state, year)
                except RuntimeError as e:
                    print(f"  [{state}/{year}] lsjson error: {e}")
                    continue
                lsjson_cache[(state, year)] = entries
                if self._manifest.changed_files(state, year, entries):
                    changed_pairs.append((state, year))

        if not changed_pairs:
            print("No changes detected.")
            return

        print(f"Changed pairs: {changed_pairs}")

        # 3. Copy changed pairs from Dropbox (input + groundtruth if available)
        for state, year in changed_pairs:
            try:
                self._rclone.copy(state, year)
            except RuntimeError as e:
                print(f"  [{state}/{year}] copy error: {e}")
            if self._rclone.has_groundtruth(state, year):
                print(f"  [{state}/{year}] Dropbox output/ found — syncing groundtruth")
                try:
                    self._rclone.copy_groundtruth(state, year)
                except RuntimeError as e:
                    print(f"  [{state}/{year}] groundtruth copy error: {e}")

        # 4. Clean each changed (state, year)
        results: list[CleanResult] = []
        for state, year in changed_pairs:
            print(f"  Cleaning {state}/{year}...")
            if self._runner.has_clean_script(state, year):
                result = self._runner.run(state, year)
            else:
                print(f"    No clean.py — invoking CC agent")
                result = self._cc_agent.run(state, year)
            results.append(result)
            status = (
                "OK" if result.success
                else (result.error or result.judge.overall)
            )
            print(f"  [{state}/{year}] {status}")
            if result.success:
                self._registry.upsert(state, year, cleaned="yes")

        # 5. Update manifest and save both manifest + registry
        for (state, year), entries in lsjson_cache.items():
            self._manifest.update_from_lsjson(state, year, entries)
        self._manifest.save()
        self._registry.save()

        # 6. Commit outputs + open PR
        branch = f"data/dropbox-update/{date.today().isoformat()}"
        self._pr_gen.commit_outputs(
            [(r.state, r.year) for r in results], branch
        )
        self._pr_gen.create_pr(branch, results)

    def _preseed_manifest(self, all_states: list[str]) -> None:
        """Seed manifest for cleaned pairs that have no manifest entry yet."""
        for state, year in self._registry.get_preseed_pairs():
            if state not in all_states:
                continue
            try:
                entries = self._rclone.lsjson(state, year)
                self._manifest.update_from_lsjson(state, year, entries)
            except RuntimeError as e:
                print(f"  [preseed {state}/{year}] {e}")

    def _discover_states(self) -> list[str]:
        return [
            d for d in os.listdir(self._states_root)
            if os.path.isdir(os.path.join(self._states_root, d))
            and d.islower() and d.isalpha()
        ]
```

**Step 4: Run all tests**

```bash
pytest tests/pipeline/ -v
```
Expected: all tests PASS

**Step 5: Commit**

```bash
git add pipeline/orchestrate.py tests/pipeline/test_orchestrate.py
git commit -m "feat(pipeline): add Orchestrator with preseed, (state, year) processing"
```

---

## Task 9: CLI entry point ✅

**File:** Create `pipeline/main.py`

```python
# pipeline/main.py
"""
Usage:
    python -m pipeline.main
    python -m pipeline.main --states ga ca
"""
import argparse
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", nargs="+",
                        help="Lowercase state codes to poll (default: all)")
    args = parser.parse_args()

    from pipeline.orchestrate import Orchestrator
    Orchestrator(
        rclone_remote=os.environ.get(
            "RCLONE_REMOTE", "dropbox:national-post-db"
        ),
    ).run(states=args.states)


if __name__ == "__main__":
    main()
```

```bash
python -c "from pipeline.main import main; print('OK')"
git add pipeline/main.py
git commit -m "feat(pipeline): add CLI entry point"
```

---

## Task 10: GitHub Action — scheduled rclone poller ✅

**File:** Create `.github/workflows/dropbox-poll.yaml`

```yaml
name: Dropbox Poll

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:
    inputs:
      states:
        description: "Space-separated state codes to poll (blank = all)"
        required: false

jobs:
  poll:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Install rclone
        run: curl https://rclone.org/install.sh | sudo bash

      - name: Configure rclone
        run: |
          mkdir -p ~/.config/rclone
          echo "${{ secrets.RCLONE_CONFIG }}" > ~/.config/rclone/rclone.conf

      - name: Install Claude Code CLI
        run: npm install -g @anthropic-ai/claude-code

      - name: Configure git
        run: |
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"

      - name: Run pipeline
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AZURE_ENDPOINT: ${{ secrets.AZURE_ENDPOINT }}
          AZURE_API_KEY: ${{ secrets.AZURE_API_KEY }}
          API_VERSION: ${{ secrets.API_VERSION }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          RCLONE_REMOTE: ${{ secrets.RCLONE_REMOTE }}
        run: |
          if [ -n "${{ github.event.inputs.states }}" ]; then
            python -m pipeline.main --states ${{ github.event.inputs.states }}
          else
            python -m pipeline.main
          fi
```

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/dropbox-poll.yaml'))" \
    && echo "YAML OK"
git add .github/workflows/dropbox-poll.yaml
git commit -m "ci: add scheduled rclone polling workflow"
```

---

## Task 11: GitHub Action — Firebase upload on merge ✅

Detects which states changed, determines the latest year per state from
`registry.csv`, and uploads only that year.

**File:** Create `.github/workflows/firebase-upload.yaml`

```yaml
name: Firebase Upload

on:
  push:
    branches: [main]
    paths:
      - "pipeline/data/registry.csv"

jobs:
  upload:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Write Firebase service account key
        run: |
          echo '${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}' \
            > db/upload/serviceAccountKey.json

      - name: Upload latest year per changed state
        env:
          AZURE_ENDPOINT: ${{ secrets.AZURE_ENDPOINT }}
          AZURE_API_KEY: ${{ secrets.AZURE_API_KEY }}
          API_VERSION: ${{ secrets.API_VERSION }}
        run: |
          python - <<'EOF'
          import csv, subprocess, sys

          with open("pipeline/data/registry.csv") as f:
              rows = list(csv.DictReader(f))

          # Find latest cleaned+unpushed year per state
          targets = {}
          for row in rows:
              if row["cleaned"] == "yes" and row["firebase_pushed"] == "no":
                  state = row["state"]
                  year = row["year"]
                  if state not in targets or year > targets[state]:
                      targets[state] = year

          if not targets:
              print("Nothing to upload.")
              sys.exit(0)

          for state, year in targets.items():
              print(f"Uploading {state}/{year}...")
              subprocess.run(
                  ["make", "upload", f"STATE={state.upper()}",
                   f"YEAR={year}"],
                  cwd="db", check=True,
              )
          EOF

      - name: Remove service account key
        if: always()
        run: rm -f db/upload/serviceAccountKey.json
```

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/firebase-upload.yaml'))" \
    && echo "YAML OK"
git add .github/workflows/firebase-upload.yaml
git commit -m "ci: add Firebase upload workflow (latest year per state)"
```

---

## Task 12: README ✅

**File:** Create `pipeline/README.md`

```markdown
# Pipeline — Setup & Secrets

## Directory structure

Each `(state, year)` is fully self-contained:

```
states/ga/
  2025/
    src/clean.py          # year-specific script (--input-dir / --output-dir args)
    src/test_cleaning.py
    data/input/           # synced from Dropbox ga/2025/input/ only
    data/groundtruth/     # local only — NOT from Dropbox
    output/               # cleaned CSVs + judge_report.md
```

State codes are **lowercase everywhere**.

## pipeline/data/ files

| File | Purpose |
|------|---------|
| `manifest.json` | rclone lsjson snapshots per (state, year) — auto-managed |
| `registry.csv` | Clean/Firebase status per (state, year) — human-editable |

### registry.csv columns

| Column | Values |
|--------|--------|
| `state` | lowercase state code |
| `year` | 4-digit year string |
| `cleaned` | `yes` / `no` |
| `firebase_pushed` | `no` / `yes` / `skipped` |

`skipped` = cleaned but intentionally not pushed (superseded by newer year).

## Required GitHub Secrets

| Secret | How to get it |
|--------|--------------|
| `RCLONE_CONFIG` | `rclone config` locally → copy `~/.config/rclone/rclone.conf` |
| `RCLONE_REMOTE` | e.g. `dropbox:national-post-db` (override for testing) |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `AZURE_ENDPOINT` | Azure portal → OpenAI resource |
| `AZURE_API_KEY` | Azure portal → OpenAI resource |
| `API_VERSION` | e.g. `2024-02-01` |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase console → Service Accounts → Generate key |

## Local usage

```bash
brew install rclone
rclone config   # create remote, authorize via browser

# Test against post-db-test folder:
RCLONE_REMOTE=dropbox:post-db-test python -m pipeline.main --states ga ca

# Production:
python -m pipeline.main --states ga
python -m pipeline.main          # all states
```

## Pre-seeding already-processed pairs

Add rows to `pipeline/data/registry.csv` with `cleaned=yes` before the
first run. The pipeline will seed `manifest.json` from Dropbox for those
pairs on startup — so they won't be re-downloaded or re-cleaned unless
their files actually change on Dropbox.
```

```bash
git add pipeline/README.md
git commit -m "docs(pipeline): add README with directory structure and secrets guide"
```

---

## Final verification

```bash
pytest tests/pipeline/ -v
python -c "from pipeline.orchestrate import Orchestrator; print('OK')"
python -c "
import yaml
for f in ['.github/workflows/dropbox-poll.yaml',
          '.github/workflows/firebase-upload.yaml']:
    yaml.safe_load(open(f))
    print(f, 'OK')
"
make lint
```
