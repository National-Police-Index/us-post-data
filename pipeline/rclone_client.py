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
            capture_output=True,
            text=True,
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
            capture_output=True,
            text=True,
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
                "rclone",
                "copy",
                f"{self._remote}/{state}/{year}/input/",
                dest,
            ],
            capture_output=True,
            text=True,
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
            capture_output=True,
            text=True,
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
                "rclone",
                "copy",
                f"{self._remote}/{state}/{year}/output/",
                dest,
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"rclone copy_groundtruth failed for {state}/{year}: "
                f"{proc.stderr}"
            )
