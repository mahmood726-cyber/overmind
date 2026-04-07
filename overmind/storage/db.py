from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, TypeVar

from overmind.storage.models import InsightRecord, MemoryRecord, ProjectRecord, RunnerRecord, TaskRecord, utc_now

T = TypeVar("T")

VALID_TABLES = {"projects", "runners", "tasks", "insights", "checkpoints", "memories"}


class StateDatabase:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runners (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS insights (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                scope TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_task_id TEXT,
                source_tick INTEGER DEFAULT 0,
                relevance REAL DEFAULT 1.0,
                confidence REAL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                linked_memories TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT DEFAULT 'active'
            )
            """
        )
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, content, tags,
                content='memories',
                content_rowid='rowid'
            )
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
            END
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
                INSERT INTO memories_fts(rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def _validate_table(self, table: str) -> None:
        if table not in VALID_TABLES:
            raise ValueError(f"Invalid table name: {table!r}")

    def _upsert(self, table: str, record_id: str, payload: dict[str, Any]) -> None:
        self._validate_table(table)
        encoded = json.dumps(payload, sort_keys=True)
        self.connection.execute(
            f"""
            INSERT INTO {table} (id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (record_id, encoded, utc_now()),
        )
        self.connection.commit()

    def _get(self, table: str, record_id: str, factory: Callable[..., T]) -> T | None:
        self._validate_table(table)
        row = self.connection.execute(f"SELECT payload FROM {table} WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        return factory(**payload)

    def _list(self, table: str, factory: Callable[..., T]) -> list[T]:
        self._validate_table(table)
        rows = self.connection.execute(f"SELECT payload FROM {table} ORDER BY updated_at DESC").fetchall()
        return [factory(**json.loads(row["payload"])) for row in rows]

    def upsert_project(self, project: ProjectRecord) -> None:
        self._upsert("projects", project.project_id, project.to_dict())

    def get_project(self, project_id: str) -> ProjectRecord | None:
        return self._get("projects", project_id, ProjectRecord)

    def list_projects(self) -> list[ProjectRecord]:
        return self._list("projects", ProjectRecord)

    def upsert_runner(self, runner: RunnerRecord) -> None:
        self._upsert("runners", runner.runner_id, runner.to_dict())

    def get_runner(self, runner_id: str) -> RunnerRecord | None:
        return self._get("runners", runner_id, RunnerRecord)

    def list_runners(self) -> list[RunnerRecord]:
        return self._list("runners", RunnerRecord)

    def upsert_task(self, task: TaskRecord) -> None:
        self._upsert("tasks", task.task_id, task.to_dict())

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._get("tasks", task_id, TaskRecord)

    def list_tasks(self) -> list[TaskRecord]:
        return self._list("tasks", TaskRecord)

    def add_insight(self, insight: InsightRecord) -> None:
        self._upsert("insights", insight.insight_id, insight.to_dict())

    def list_insights(self) -> list[InsightRecord]:
        return self._list("insights", InsightRecord)

    def write_checkpoint(self, name: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO checkpoints (name, payload, created_at) VALUES (?, ?, ?)",
            (name, json.dumps(payload, sort_keys=True), utc_now()),
        )
        self.connection.commit()

    def upsert_memory(self, memory: MemoryRecord) -> None:
        encoded_tags = json.dumps(memory.tags)
        encoded_linked = json.dumps(memory.linked_memories)
        self.connection.execute(
            """
            INSERT INTO memories (id, memory_type, scope, title, content,
                source_task_id, source_tick, relevance, confidence,
                tags, linked_memories, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                relevance = excluded.relevance,
                confidence = excluded.confidence,
                tags = excluded.tags,
                linked_memories = excluded.linked_memories,
                updated_at = excluded.updated_at,
                status = excluded.status
            """,
            (
                memory.memory_id, memory.memory_type, memory.scope,
                memory.title, memory.content,
                memory.source_task_id, memory.source_tick,
                memory.relevance, memory.confidence,
                encoded_tags, encoded_linked,
                memory.created_at, memory.updated_at, memory.status,
            ),
        )
        self.connection.commit()

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        row = self.connection.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    def list_memories(
        self, status: str = "active", memory_type: str | None = None, scope: str | None = None, limit: int = 100
    ) -> list[MemoryRecord]:
        query = "SELECT * FROM memories WHERE status = ?"
        params: list[object] = [status]
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY relevance DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def search_memories(
        self, query: str, scope: str | None = None, memory_type: str | None = None, limit: int = 10
    ) -> list[MemoryRecord]:
        fts_query = " ".join(f'"{token}"' for token in query.split() if token)
        if not fts_query:
            return []
        sql = """
            SELECT m.* FROM memories m
            JOIN memories_fts f ON m.rowid = f.rowid
            WHERE memories_fts MATCH ? AND m.status = 'active'
        """
        params: list[object] = [fts_query]
        if scope:
            sql += " AND m.scope = ?"
            params.append(scope)
        if memory_type:
            sql += " AND m.memory_type = ?"
            params.append(memory_type)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = self.connection.execute(sql, params).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def decay_memories(self, factor: float = 0.95) -> int:
        cursor = self.connection.execute(
            "UPDATE memories SET relevance = ROUND(relevance * ?, 4), updated_at = ? WHERE status = 'active'",
            (factor, utc_now()),
        )
        self.connection.commit()
        return cursor.rowcount

    def archive_stale_memories(self, threshold: float = 0.1) -> int:
        cursor = self.connection.execute(
            "UPDATE memories SET status = 'archived', updated_at = ? WHERE status = 'active' AND relevance < ?",
            (utc_now(), threshold),
        )
        self.connection.commit()
        return cursor.rowcount

    def delete_memory(self, memory_id: str) -> None:
        self.connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.connection.commit()

    def memory_stats(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT memory_type, status, COUNT(*) as cnt FROM memories GROUP BY memory_type, status"
        ).fetchall()
        stats: dict[str, int] = {}
        for row in rows:
            key = f"{row['memory_type']}:{row['status']}"
            stats[key] = row["cnt"]
        stats["total"] = sum(v for k, v in stats.items() if k != "total")
        return stats

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryRecord:
        tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"]
        linked = json.loads(row["linked_memories"]) if isinstance(row["linked_memories"], str) else row["linked_memories"]
        return MemoryRecord(
            memory_id=row["id"],
            memory_type=row["memory_type"],
            scope=row["scope"],
            title=row["title"],
            content=row["content"],
            source_task_id=row["source_task_id"],
            source_tick=row["source_tick"],
            relevance=row["relevance"],
            confidence=row["confidence"],
            tags=tags,
            linked_memories=linked,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row["status"],
        )

    def latest_checkpoint(self, name: str | None = None) -> dict[str, Any] | None:
        if name:
            row = self.connection.execute(
                "SELECT payload FROM checkpoints WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT payload FROM checkpoints ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])
