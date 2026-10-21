"""Reading time, statistics, the Library and About."""

import base64
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import webview

from phdf import __version__
from phdf.api.base import ApiBase
from phdf.api.core import copy_id
from phdf.docid import document_id
from phdf.paths import data_dir
from phdf.services import (
    ai_cache,
    ocr,
)


class LibraryApi(ApiBase):
    # --- reading time, library ----------------------------------------------------------------

    def log_reading(self, doc_id: str, seconds: int) -> None:
        """Add seconds actually spent reading (see the frontend's pace tracker) to today."""
        if 0 < seconds <= 3600:
            self._core.store.log_reading(self._current(doc_id), date.today().isoformat(), seconds)

    def reading_stats(self) -> dict[str, Any]:
        store = self._core.store
        today = date.today()
        by_day = {
            d["day"]: d["seconds"] for d in store.reading_days((today - timedelta(13)).isoformat())
        }
        days = [
            {
                "day": (today - timedelta(i)).isoformat(),
                "seconds": by_day.get((today - timedelta(i)).isoformat(), 0),
            }
            for i in range(13, -1, -1)
        ]
        read_days = set(store.all_reading_days())
        streak, cursor = 0, today if today.isoformat() in read_days else today - timedelta(1)
        while cursor.isoformat() in read_days:
            streak += 1
            cursor -= timedelta(1)
        week_start = today - timedelta(today.weekday())
        return {
            "days": days,
            "today": by_day.get(today.isoformat(), 0),
            "week": sum(d["seconds"] for d in days if d["day"] >= week_start.isoformat()),
            "streak": streak,
        }

    def library(self) -> list[dict[str, Any]]:
        """Every document PhDF has opened, most recent first, with progress and reading time."""
        store = self._core.store
        seconds = store.reading_by_document()
        items = []
        for row in store.recent_documents(500):
            items.append(
                {
                    "docId": row["doc_id"],
                    "path": row["path"],
                    "title": row["title"] or Path(row["path"]).stem,
                    "page": row["page"],
                    "pageCount": row["page_count"],
                    "lastOpened": row["last_opened"],
                    "seconds": seconds.get(row["doc_id"], 0),
                    "exists": Path(row["path"]).is_file(),
                }
            )
        return items

    def library_remove(self, doc_id: str) -> None:
        """Take a document out of the library; the file itself is not touched."""
        self._core.store.forget_document(doc_id)

    def library_relink(self, doc_id: str) -> dict[str, Any]:
        """A document's file moved: pick it again. Only the same file (same content) is
        accepted, so bookmarks and reading history still belong to it."""
        path = self.pick_file("document")
        if not path:
            return {"ok": False, "reason": "cancelled"}
        content = document_id(path)
        # An identical copy of another file has an id made from its content and its old path
        # (core.copy_id): the same content is accepted for it too.
        old = self._core.store.document_path(doc_id)
        if content != doc_id and not (old and copy_id(content, old) == doc_id):
            return {"ok": False, "reason": "different"}
        self._core.store.set_document_path(doc_id, str(Path(path)))
        return {"ok": True, "path": str(Path(path))}

    def about(self) -> dict[str, Any]:
        """Versions, platform and storage, for the About section and bug reports."""
        import platform
        from importlib.metadata import PackageNotFoundError, version

        import pymupdf

        def pkg(name: str) -> str:
            try:
                return version(name)
            except PackageNotFoundError:
                return "?"

        def size(folder: Path) -> int:
            if not folder.is_dir():
                return 0
            return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())

        root = data_dir()
        return {
            "version": __version__,
            "python": platform.python_version(),
            "pymupdf": pymupdf.VersionBind,
            "pywebview": pkg("pywebview"),
            "os": platform.platform(),
            "gui": getattr(webview, "renderer", "") or "",
            "frozen": bool(getattr(sys, "frozen", False)),
            "dataDir": str(root),
            "dbBytes": sum(p.stat().st_size for p in root.glob("phdf.db*") if p.is_file()),
            "aiCacheBytes": ai_cache.info(ai_cache.folder(root))["bytes"],
            "coverBytes": size(root / "covers"),
            "ocrLanguages": ocr.installed_languages(),
        }

    def library_cover(self, doc_id: str, path: str) -> str | None:
        """A small JPEG of page 1 (data URL), cached in PhDF's data folder. JPEG: a fifth of a
        PNG's size, and every cover crosses the bridge to the page as text."""
        import pymupdf

        cache = data_dir() / "covers" / f"{doc_id[:16]}.jpg"
        if not cache.exists():
            if not Path(path).is_file():
                return None
            try:
                with self._core.lock, pymupdf.open(path) as doc:  # MuPDF isn't thread-safe
                    page = doc[0]
                    pix = page.get_pixmap(
                        matrix=pymupdf.Matrix(220 / page.rect.width, 220 / page.rect.width),
                        alpha=False,
                    )
                    picture = pix.tobytes("jpg", jpg_quality=82)
            except Exception:  # noqa: BLE001 — unreadable / encrypted: no cover
                return None
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(picture)
            cache.with_suffix(".png").unlink(missing_ok=True)  # made by older versions
        return "data:image/jpeg;base64," + base64.b64encode(cache.read_bytes()).decode()
