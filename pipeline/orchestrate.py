from __future__ import annotations

import os
from datetime import date

from pipeline.cc_agent import CCAgent
from pipeline.clean_runner import CleanResult, CleanRunner
from pipeline.pr_generator import PRGenerator
from pipeline.rclone_client import RcloneClient
from pipeline.registry import Registry
from pipeline.state_manifest import StateManifest


class Orchestrator:
    def __init__(
        self,
        rclone_remote: str = "dropbox:post-db-test",
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

        # 3. Copy input (and groundtruth if available on remote)
        for state, year in changed_pairs:
            try:
                self._rclone.copy(state, year)
            except RuntimeError as e:
                print(f"  [{state}/{year}] copy error: {e}")
            if self._rclone.has_groundtruth(state, year):
                print(
                    f"  [{state}/{year}] Dropbox output/ found"
                    f" — syncing groundtruth"
                )
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
                "OK"
                if result.success
                else (result.error or result.judge.overall)
            )
            print(f"  [{state}/{year}] {status}")
            if result.success:
                self._registry.upsert(state, year, cleaned="yes")

        # 5. Update manifest + registry and save both
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
            d
            for d in os.listdir(self._states_root)
            if os.path.isdir(os.path.join(self._states_root, d))
            and d.islower()
            and d.isalpha()
        ]
