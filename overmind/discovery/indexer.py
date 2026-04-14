from __future__ import annotations

import json
from pathlib import Path

from overmind.config import AppConfig
from overmind.discovery.project_scanner import ProjectScanner
from overmind.storage.db import StateDatabase
from overmind.storage.models import ProjectRecord

CACHE_VERSION = 8


class ProjectIndexer:
    def __init__(self, config: AppConfig, db: StateDatabase) -> None:
        self.config = config
        self.db = db
        self.scanner = ProjectScanner(config)
        self.cache_path = self.config.data_dir / "cache" / "indexer_state.json"

    def incremental_refresh(self, focus_project_id: str | None = None) -> list[ProjectRecord]:
        cache = self._load_cache()
        if focus_project_id:
            focused_records = self._focused_refresh(focus_project_id, cache)
            if focused_records is not None:
                return focused_records

        next_cache: dict[str, object] = {"cache_version": CACHE_VERSION, "projects": {}}
        records: list[ProjectRecord] = []

        for root in self.scanner.discover_project_roots():
            root_key = str(root)
            signature = self.scanner.compute_signature(root)
            cached = cache.get("projects", {}).get(root_key)
            if cached and cached.get("signature") == signature:
                record = ProjectRecord(**cached["record"])
            else:
                record = self.scanner.scan_project(root)

            next_cache["projects"][root_key] = {
                "signature": signature,
                "record": record.to_dict(),
            }
            if focus_project_id and record.project_id != focus_project_id:
                continue
            records.append(record)
            self.db.upsert_project(record)

        self._save_cache(next_cache)
        return records

    def _focused_refresh(
        self,
        focus_project_id: str,
        cache: dict[str, object],
    ) -> list[ProjectRecord] | None:
        cached_projects = cache.get("projects", {}) if isinstance(cache, dict) else {}
        cache_entry: dict[str, object] | None = None
        root: Path | None = None

        if isinstance(cached_projects, dict):
            for root_key, entry in cached_projects.items():
                if not isinstance(entry, dict):
                    continue
                record = entry.get("record", {})
                if isinstance(record, dict) and record.get("project_id") == focus_project_id:
                    root = Path(root_key)
                    cache_entry = entry
                    break

        if root is None:
            project = self.db.get_project(focus_project_id)
            if project is not None:
                root = Path(project.root_path)

        if root is None or not root.exists():
            return None

        signature = self.scanner.compute_signature(root)
        if cache_entry and cache_entry.get("signature") == signature:
            cached_record = cache_entry.get("record", {})
            if not isinstance(cached_record, dict):
                return None
            record = ProjectRecord(**cached_record)
        else:
            record = self.scanner.scan_project(root)

        if record.project_id != focus_project_id:
            return None

        next_cache = cache if isinstance(cache, dict) else {}
        next_cache["cache_version"] = CACHE_VERSION
        next_cache.setdefault("projects", {})
        next_cache["projects"][str(root)] = {
            "signature": signature,
            "record": record.to_dict(),
        }
        self._save_cache(next_cache)
        self.db.upsert_project(record)
        return [record]

    def _load_cache(self) -> dict[str, object]:
        if not self.cache_path.exists():
            return {}
        with self.cache_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("cache_version") != CACHE_VERSION:
            return {}
        return payload

    def _save_cache(self, payload: dict[str, object]) -> None:
        with self.cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
