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
        return [
            k for k, v in self._rows.items() if v.get("cleaned") == "yes"
        ]

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
                "state": state,
                "year": year,
                "cleaned": "no",
                "firebase_pushed": "no",
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
            year
            for (s, year), row in self._rows.items()
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
