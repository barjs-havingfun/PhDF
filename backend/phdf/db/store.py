"""SQLite store for settings and documents (D10). Schema changes go in MIGRATIONS, append-only."""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL            -- JSON
    );
    CREATE TABLE documents (
        doc_id      TEXT PRIMARY KEY,  -- content hash, see docid.py
        path        TEXT NOT NULL,     -- last known location
        title       TEXT,
        page_count  INTEGER,
        last_opened REAL,              -- unix time
        page        INTEGER NOT NULL DEFAULT 0,
        scroll      REAL    NOT NULL DEFAULT 0,
        zoom        REAL    NOT NULL DEFAULT 1
    );
    CREATE INDEX documents_last_opened ON documents (last_opened DESC);
    """,
    # 2 — fit mode; `scroll` is now the offset within `page` as a 0..1 fraction of its height
    """
    ALTER TABLE documents ADD COLUMN fit TEXT NOT NULL DEFAULT 'width';  -- width | page | none
    """,
]


class Store:
    def __init__(self, path: str | Path) -> None:
        # pywebview calls the API from worker threads; serialize access to one connection.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._migrate()

    @property
    def schema_version(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        with self._lock:
            current = self.schema_version
            for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
                self._conn.executescript(
                    f"BEGIN; {script}; PRAGMA user_version = {version}; COMMIT;"
                )

    def close(self) -> None:
        self._conn.close()

    # --- settings ---------------------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )

    # --- documents --------------------------------------------------------------------------

    def touch_document(
        self, doc_id: str, path: str, title: str | None, page_count: int
    ) -> dict[str, Any]:
        """Record that a document was opened; returns its stored row (incl. saved position)."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO documents (doc_id, path, title, page_count, last_opened) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (doc_id) DO UPDATE SET path = excluded.path, title = excluded.title, "
                "page_count = excluded.page_count, last_opened = excluded.last_opened",
                (doc_id, path, title, page_count, time.time()),
            )
            row = self._conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return dict(row)

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE documents SET page = ?, scroll = ?, zoom = ?, fit = ? WHERE doc_id = ?",
                (page, scroll, zoom, fit, doc_id),
            )

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM documents ORDER BY last_opened DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
