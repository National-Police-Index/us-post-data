from __future__ import annotations

import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class RcloneClient:
    def __init__(
        self,
        remote: str = "dropbox:post-db-test",
        states_root: str = "states",
    ):
        self._remote = remote.rstrip("/")
        self._states_root = states_root

    def _dest(self, state: str, year: str) -> str:
        return os.path.join(self._states_root, state, year, "data", "input")

    def list_years(self, state: str) -> list[str]:
        """Return year subdirectories for a state on the remote."""
        path = f"{self._remote}/{state}/"
        logger.debug("rclone lsjson %s", path)
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.error(
                "rclone lsjson failed for %s: %s", state, proc.stderr
            )
            raise RuntimeError(
                f"rclone lsjson failed for {state}: {proc.stderr}"
            )
        entries = json.loads(proc.stdout or "[]")
        years = [e["Name"] for e in entries if e.get("IsDir", False)]
        logger.info("[%s] years on remote: %s", state, years)
        return years

    def lsjson(self, state: str, year: str) -> list[dict]:
        """Return file entries for state/year/input/ on the remote."""
        path = f"{self._remote}/{state}/{year}/input/"
        logger.debug("rclone lsjson %s", path)
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.error(
                "rclone lsjson failed for %s/%s: %s",
                state, year, proc.stderr,
            )
            raise RuntimeError(
                f"rclone lsjson failed for {state}/{year}: {proc.stderr}"
            )
        entries = json.loads(proc.stdout or "[]")
        files = [e for e in entries if not e.get("IsDir", False)]
        logger.info(
            "[%s/%s] %d file(s) on remote: %s",
            state, year, len(files), [f["Name"] for f in files],
        )
        return files

    def copy(self, state: str, year: str) -> None:
        """rclone copy state/year/input/ to local. Raises on failure."""
        dest = self._dest(state, year)
        os.makedirs(dest, exist_ok=True)
        src = f"{self._remote}/{state}/{year}/input/"
        logger.info("[%s/%s] rclone copy %s → %s", state, year, src, dest)
        proc = subprocess.run(
            ["rclone", "copy", src, dest],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.error(
                "[%s/%s] rclone copy failed: %s", state, year, proc.stderr
            )
            raise RuntimeError(
                f"rclone copy failed for {state}/{year}: {proc.stderr}"
            )
        logger.info("[%s/%s] rclone copy complete", state, year)

    def has_groundtruth(self, state: str, year: str) -> bool:
        """Return True if state/year/output/ exists on the remote."""
        path = f"{self._remote}/{state}/{year}/"
        logger.debug("rclone lsjson %s (checking for output/)", path)
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.debug(
                "[%s/%s] has_groundtruth check failed: %s",
                state, year, proc.stderr,
            )
            return False
        entries = json.loads(proc.stdout or "[]")
        result = any(
            e["Name"] == "output" and e.get("IsDir", False)
            for e in entries
        )
        logger.info(
            "[%s/%s] groundtruth on remote: %s", state, year, result
        )
        return result

    def has_readme(self, state: str) -> bool:
        """Return True if state/readme/ exists on the remote."""
        path = f"{self._remote}/{state}/"
        logger.debug("rclone lsjson %s (checking for readme/)", path)
        proc = subprocess.run(
            ["rclone", "lsjson", path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return False
        entries = json.loads(proc.stdout or "[]")
        result = any(
            e["Name"] == "readme" and e.get("IsDir", False)
            for e in entries
        )
        logger.info("[%s] readme on remote: %s", state, result)
        return result

    def copy_readme(self, state: str) -> None:
        """rclone copy state/readme/ → local states/{state}/readme/."""
        dest = os.path.join(self._states_root, state, "readme")
        os.makedirs(dest, exist_ok=True)
        src = f"{self._remote}/{state}/readme/"
        logger.info("[%s] rclone copy readme %s → %s", state, src, dest)
        proc = subprocess.run(
            ["rclone", "copy", src, dest],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.error("[%s] copy_readme failed: %s", state, proc.stderr)
            raise RuntimeError(
                f"rclone copy_readme failed for {state}: {proc.stderr}"
            )
        logger.info("[%s] readme copy complete", state)

    def copy_groundtruth(self, state: str, year: str) -> None:
        """
        rclone copy state/year/output/ → local data/groundtruth/.
        Used to download state-provided groundtruth before cleaning.
        """
        dest = os.path.join(
            self._states_root, state, year, "data", "groundtruth"
        )
        os.makedirs(dest, exist_ok=True)
        src = f"{self._remote}/{state}/{year}/output/"
        logger.info(
            "[%s/%s] rclone copy groundtruth %s → %s",
            state, year, src, dest,
        )
        proc = subprocess.run(
            ["rclone", "copy", src, dest],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.error(
                "[%s/%s] copy_groundtruth failed: %s",
                state, year, proc.stderr,
            )
            raise RuntimeError(
                f"rclone copy_groundtruth failed for {state}/{year}: "
                f"{proc.stderr}"
            )
        logger.info("[%s/%s] groundtruth copy complete", state, year)
