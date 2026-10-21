"""Documents: open / close, outline, text, links, search, positions, bookmarks."""

import os
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import webview

from phdf.api.base import ApiBase
from phdf.api.core import FIT_MODES
from phdf.docid import document_id
from phdf.engine import PasswordRequired
from phdf.services import (
    webview_memory,
)

# Comics opened with guessed page sizes are measured this many seconds later (_measure_pages).
MEASURE_AFTER = 1.0


class DocumentsApi(ApiBase):
    # --- documents --------------------------------------------------------------------------

    def open_document(self, path: str, password: str | None = None) -> dict[str, Any]:
        """Open a document for this window. An encrypted PDF answers `{needsPassword, wrong}`
        until it is called again with the right password."""
        core = self._core
        with core.lock:
            doc_id = core.open_id(document_id(path), path)
            # Already open here, maybe under the id it had before a save: no second reference.
            current = core.resolve(doc_id)
            doc_id = next((held for held in self._open if core.resolve(held) == current), doc_id)
            if doc_id in self._open:
                doc = core.doc(doc_id)
            else:
                if password:
                    core.passwords[doc_id] = password
                try:
                    doc = core.acquire(doc_id, path)
                except PasswordRequired:
                    if password:
                        core.passwords.pop(doc_id, None)
                    return {"needsPassword": True, "wrong": bool(password)}
                self._open.add(doc_id)
            info = doc.info()
            sizes = doc.page_sizes(quick=True)
            measure = not doc.sizes_known()
            dirty = doc.dirty
            revs = core.revs(doc_id)
        if measure:
            threading.Thread(target=self._measure_pages, args=(doc_id, sizes), daemon=True).start()
        title = info.title or Path(path).stem
        previous = core.store.last_opened(doc_id)
        record = core.store.touch_document(doc_id, str(path), title, info.page_count)
        return {
            "docId": doc_id,
            "path": str(path),
            "title": title,
            "info": asdict(info),
            "pageSizes": [[round(w, 2), round(h, 2)] for w, h in sizes],
            "position": {k: record[k] for k in ("page", "scroll", "zoom", "fit")},
            "dirty": dirty,
            "revs": revs,
            "lastOpened": previous,  # unix time of the previous visit, or None
        }

    def _measure_pages(self, doc_id: str, guess: list[tuple[float, float]]) -> None:
        """A comic opened with guessed page sizes: measure them one page at a time, the lock
        released in between so pages keep rendering, then tell the windows if they differ."""
        core = self._core
        sizes: list[tuple[float, float]] = []
        time.sleep(MEASURE_AFTER)  # the first pages are drawn first
        for page in range(len(guess)):
            time.sleep(0.001)  # a waiting render gets the lock (Python's lock isn't fair)
            with core.lock:
                try:
                    doc = core.doc(doc_id)
                except KeyError:
                    return  # closed meanwhile
                if doc.sizes_known():
                    return  # another window measured it
                sizes.append(doc.page_size(page))
        with core.lock:
            doc.remember_sizes(sizes)
        rounded = [[round(w, 2), round(h, 2)] for w, h in sizes]
        if rounded != [[round(w, 2), round(h, 2)] for w, h in guess]:
            core.tell_windows(doc_id, "doc-sizes", {"pageSizes": rounded}, skip=None)

    def close_document(self, doc_id: str) -> None:
        with self._core.lock:
            if doc_id in self._open:
                self._open.discard(doc_id)
                self._core.release(doc_id)
        webview_memory.trim(self._window)  # let the browser drop that document's images

    def outline(self, doc_id: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(item) for item in self._core.doc(doc_id).outline()]

    def text_layer(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(line) for line in self._core.doc(doc_id).text_lines(page)]

    def links(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(link) for link in self._core.doc(doc_id).links(page)]

    def search(self, doc_id: str, query: str, max_hits: int = 1000) -> list[dict[str, Any]]:
        """Page by page, letting go of the lock in between, so rendering in every window goes
        on while a big book is searched. A newer search of the same document stops this one."""
        core = self._core
        with core.lock:
            key = core.resolve(doc_id)
            run = self._searches[key] = self._searches.get(key, 0) + 1
            pages = core.doc(doc_id).info().page_count
        hits: list[dict[str, Any]] = []
        total = 0
        for page in range(pages):
            if self._searches.get(key) != run or total >= max_hits:
                break
            with core.lock:
                doc = core._docs.get(core.resolve(doc_id))
                if doc is None or page >= doc.info().page_count:  # closed, or laid out again
                    break
                hit = doc.search_page(page, query, max_hits - total)
            if hit:
                hits.append(asdict(hit))
                total += len(hit.rects)
        return hits

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        fit = fit if fit in FIT_MODES else "none"
        with self._core.lock:
            current = self._core.resolve(doc_id)
        self._core.store.save_position(current, page, scroll, zoom, fit)

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._core.store.recent_documents(limit)

    def save_page_image(self, doc_id: str, page: int, name: str) -> str | None:
        """Ask where to save one page as a PNG (or JPEG) image at about 200 DPI."""
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=name,
            file_types=("PNG image (*.png)", "JPEG image (*.jpg)"),
        )
        if not result:
            return None
        path = Path(result if isinstance(result, str) else result[0])
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            path = path.with_suffix(".png")
        fmt = "png" if path.suffix.lower() == ".png" else "jpg"
        with self._core.lock:
            doc = self._core.doc(doc_id)
            width, height = doc.page_size(page)
            scale = min(200 / 72, 6000 / max(width, height, 1))  # big pages stay < 6000 px
            data = doc.page_image(page, scale, fmt)
        path.write_bytes(data)
        return str(path)

    def open_in_default_app(self, path: str) -> None:
        """Open a file with the system's default app (e.g. to print from Preview on a Mac)."""
        if not Path(path).is_file():
            return
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            import subprocess

            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])  # noqa: S603

    def open_in_preview(self, path: str) -> None:
        """macOS: open a file in Preview itself (with PhDF as the default PDF app, `open` would
        hand it back to PhDF)."""
        if sys.platform == "darwin" and Path(path).is_file():
            import subprocess

            subprocess.Popen(["open", "-a", "Preview", path])  # noqa: S603, S607

    # --- bookmarks ------------------------------------------------------------------------------

    def bookmarks(self, doc_id: str) -> list[dict[str, Any]]:
        return self._core.store.bookmarks(self._current(doc_id))

    def set_bookmark(self, doc_id: str, page: int, label: str = "") -> list[dict[str, Any]]:
        self._core.store.set_bookmark(self._current(doc_id), page, label)
        return self.bookmarks(doc_id)

    def delete_bookmark(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        self._core.store.delete_bookmark(self._current(doc_id), page)
        return self.bookmarks(doc_id)

    def _current(self, doc_id: str) -> str:
        with self._core.lock:
            return self._core.resolve(doc_id)
