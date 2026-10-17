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
    # 3 — Markdown file linked to a PDF when it is not the default "<pdf stem>.md" next to it
    """
    CREATE TABLE md_links (
        pdf_path TEXT PRIMARY KEY,
        md_path  TEXT NOT NULL
    );
    """,
    # 4 — page bookmarks and reading time (seconds actually spent reading, per document and day)
    """
    CREATE TABLE bookmarks (
        doc_id  TEXT NOT NULL,
        page    INTEGER NOT NULL,
        label   TEXT NOT NULL DEFAULT '',
        created REAL NOT NULL,
        PRIMARY KEY (doc_id, page)
    );
    CREATE TABLE reading_log (
        doc_id  TEXT NOT NULL,
        day     TEXT NOT NULL,             -- YYYY-MM-DD, local time
        seconds INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (doc_id, day)
    );
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

    def delete_setting(self, key: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    def settings_with_prefix(self, prefix: str) -> dict[str, Any]:
        pattern = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM settings WHERE key LIKE ? ESCAPE '\\' ORDER BY key",
                (pattern,),
            ).fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

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

    def last_opened(self, doc_id: str) -> float | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_opened FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
        return row["last_opened"] if row else None

    # --- bookmarks ----------------------------------------------------------------------------

    def bookmarks(self, doc_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT page, label, created FROM bookmarks WHERE doc_id = ? ORDER BY page",
                (doc_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def set_bookmark(self, doc_id: str, page: int, label: str = "") -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO bookmarks (doc_id, page, label, created) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (doc_id, page) DO UPDATE SET label = excluded.label",
                (doc_id, page, label, time.time()),
            )

    def delete_bookmark(self, doc_id: str, page: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM bookmarks WHERE doc_id = ? AND page = ?", (doc_id, page)
            )

    # --- reading time ---------------------------------------------------------------------------

    def log_reading(self, doc_id: str, day: str, seconds: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO reading_log (doc_id, day, seconds) VALUES (?, ?, ?) "
                "ON CONFLICT (doc_id, day) DO UPDATE SET seconds = seconds + excluded.seconds",
                (doc_id, day, seconds),
            )

    def reading_days(self, since: str) -> list[dict[str, Any]]:
        """Seconds read per day since `since` (YYYY-MM-DD), all documents."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, SUM(seconds) AS seconds FROM reading_log WHERE day >= ? "
                "GROUP BY day ORDER BY day",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def reading_by_document(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT doc_id, SUM(seconds) AS seconds FROM reading_log GROUP BY doc_id"
            ).fetchall()
        return {r["doc_id"]: r["seconds"] for r in rows}

    def all_reading_days(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT day FROM reading_log WHERE seconds >= 60 ORDER BY day"
            ).fetchall()
        return [r["day"] for r in rows]

    def forget_document(self, doc_id: str) -> None:
        """Remove a document from the library (the file and its bookmarks stay)."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

    def set_document_path(self, doc_id: str, path: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE documents SET path = ? WHERE doc_id = ?", (path, doc_id))

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE documents SET page = ?, scroll = ?, zoom = ?, fit = ? WHERE doc_id = ?",
                (page, scroll, zoom, fit, doc_id),
            )

    def rename_document(self, old_id: str, new_id: str) -> None:
        """A save changed the file's content hash; keep its history under the new id."""
        if old_id == new_id:
            return
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (new_id,))
            self._conn.execute("UPDATE documents SET doc_id = ? WHERE doc_id = ?", (new_id, old_id))
            for table in ("bookmarks", "reading_log"):
                self._conn.execute(
                    f"UPDATE OR REPLACE {table} SET doc_id = ? WHERE doc_id = ?",  # noqa: S608
                    (new_id, old_id),
                )

    # --- markdown links ---------------------------------------------------------------------

    def md_link(self, pdf_path: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT md_path FROM md_links WHERE pdf_path = ?", (pdf_path,)
            ).fetchone()
        return row["md_path"] if row else None

    def pdf_for_md(self, md_path: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT pdf_path FROM md_links WHERE md_path = ?", (md_path,)
            ).fetchone()
        return row["pdf_path"] if row else None

    def set_md_link(self, pdf_path: str, md_path: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO md_links (pdf_path, md_path) VALUES (?, ?) "
                "ON CONFLICT (pdf_path) DO UPDATE SET md_path = excluded.md_path",
                (pdf_path, md_path),
            )

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM documents ORDER BY last_opened DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
