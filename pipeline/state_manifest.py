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
        self,
        state: str,
        year: str,
        filename: str,
        size: int,
        mtime: str,
    ) -> None:
        self._data.setdefault(state, {}).setdefault(year, {})[
            filename
        ] = {"size": size, "mtime": mtime}

    def update_from_lsjson(
        self, state: str, year: str, entries: list[dict]
    ) -> None:
        for e in entries:
            self.set_entry(
                state,
                year,
                e["Name"],
                size=e["Size"],
                mtime=e["ModTime"],
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
