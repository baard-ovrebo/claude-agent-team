"""
SQLite-backed queue for human-review items.

Schema is minimal: one table, JSON-encoded payloads. No migrations needed.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class QueueStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    check_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    project_root TEXT NOT NULL,
                    files TEXT NOT NULL,
                    findings TEXT NOT NULL,
                    audit TEXT,
                    decision TEXT,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reviews_pending "
                "ON reviews(decision) WHERE decision IS NULL"
            )

    def enqueue(
        self,
        check_id: str,
        session_id: str,
        agent_name: str,
        project_root: str,
        files: list[str],
        findings: list[dict],
        audit: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO reviews
                (check_id, session_id, agent_name, project_root, files, findings, audit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    check_id,
                    session_id,
                    agent_name,
                    project_root,
                    json.dumps(files),
                    json.dumps(findings),
                    audit,
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )

    def list_pending(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE decision IS NULL "
                "ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get(self, check_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reviews WHERE check_id = ?", (check_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def decide(self, check_id: str, decision: str, comment: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE reviews SET decision = ?, comment = ?, resolved_at = ? WHERE check_id = ?",
                (decision, comment, datetime.utcnow().isoformat(timespec="seconds"), check_id),
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        d["files"] = json.loads(d["files"])
        d["findings"] = json.loads(d["findings"])
        return d
