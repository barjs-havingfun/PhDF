"""Backend shared by all windows (`Core`) and the per-window API exposed to the frontend (`Api`).

Each window gets its own `Api`, exposed as `window.pywebview.api.*`; pywebview exposes every
public attribute, so internals are underscore-prefixed. Open documents are shared between windows
and reference-counted, so closing a tab in one window never closes the document in another.
Calls arrive on worker threads; MuPDF is not thread-safe, so engine access is serialized.
Page images are served separately by `RenderServer` (see `Core.render`).
"""

import threading
import uuid
import webbrowser
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import webview

from phdf import __version__
from phdf.db import Store
from phdf.docid import document_id
from phdf.engine import PdfDocument, PdfEngine, Rect

FIT_MODES = ("width", "page", "none")
PEEK_SIZE = (560, 460)
SESSION_PREFIX = "session."

# (window_id, x, y) -> None; set by app.py so the API can open new windows.
WindowFactory = Callable[[str, int | None, int | None], None]


class Core:
    def __init__(self, engine: PdfEngine, store: Store) -> None:
        self.engine = engine
        self.store = store
        self.lock = threading.Lock()
        self.render_base_url = ""
        self.create_window: WindowFactory | None = None
        self.windows: dict[str, Api] = {}
        self._docs: dict[str, PdfDocument] = {}
        self._refs: Counter[str] = Counter()

    def acquire(self, doc_id: str, path: str) -> PdfDocument:
        """Open (or reuse) a document; pair every call with `release`. Caller holds `lock`."""
        doc = self._docs.get(doc_id)
        if doc is None:
            doc = self._docs[doc_id] = self.engine.open(path)
        self._refs[doc_id] += 1
        return doc

    def release(self, doc_id: str) -> None:
        """Caller holds `lock`."""
        self._refs[doc_id] -= 1
        if self._refs[doc_id] <= 0:
            del self._refs[doc_id]
            if doc := self._docs.pop(doc_id, None):
                doc.close()

    def doc(self, doc_id: str) -> PdfDocument:
        return self._docs[doc_id]

    def render(self, doc_id: str, page: int, scale: float, clip: Rect | None) -> bytes | None:
        """Called by RenderServer threads."""
        with self.lock:
            doc = self._docs.get(doc_id)
            return doc.render_page(page, scale, clip) if doc else None

    def window_closed(self, window_id: str) -> None:
        self.windows.pop(window_id, None)
        # Closing one of several windows discards its tabs (like a browser); the last window's
        # session is kept so it can be restored at the next launch.
        if self.windows:
            self.store.delete_setting(SESSION_PREFIX + window_id)

    def shutdown(self) -> None:
        with self.lock:
            for doc in self._docs.values():
                doc.close()
            self._docs.clear()
            self._refs.clear()


class Api:
    def __init__(self, core: Core, window_id: str) -> None:
        self._core = core
        self._window_id = window_id
        self._window: webview.Window | None = None
        self._open: set[str] = set()  # doc_ids this window holds a reference to
        self._peek: webview.Window | None = None

    # --- app / windows ----------------------------------------------------------------------

    def app_info(self) -> dict[str, Any]:
        return {
            "name": "PhDF",
            "version": __version__,
            "renderBaseUrl": self._core.render_base_url,
            "windowId": self._window_id,
        }

    def pick_pdf(self) -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("PDF files (*.pdf)", "All files (*.*)")
        )
        return result[0] if result else None

    def open_window(self, paths: list[str], x: int | None = None, y: int | None = None) -> str:
        """Open a new window showing `paths` as tabs (used when a tab is dragged out)."""
        window_id = uuid.uuid4().hex[:8]
        session = {"panes": [{"paths": paths, "active": 0, "width": 1}], "focused": 0}
        self._core.store.set_setting(SESSION_PREFIX + window_id, session)
        if self._core.create_window:
            self._core.create_window(window_id, x, y)
        return window_id

    # --- documents --------------------------------------------------------------------------

    def open_document(self, path: str) -> dict[str, Any]:
        doc_id = document_id(path)
        with self._core.lock:
            if doc_id in self._open:
                doc = self._core.doc(doc_id)
            else:
                doc = self._core.acquire(doc_id, path)
                self._open.add(doc_id)
            info = doc.info()
            sizes = doc.page_sizes()
        title = info.title or Path(path).stem
        record = self._core.store.touch_document(doc_id, str(path), title, info.page_count)
        return {
            "docId": doc_id,
            "path": str(path),
            "title": title,
            "info": asdict(info),
            "pageSizes": [[round(w, 2), round(h, 2)] for w, h in sizes],
            "position": {k: record[k] for k in ("page", "scroll", "zoom", "fit")},
        }

    def close_document(self, doc_id: str) -> None:
        with self._core.lock:
            if doc_id in self._open:
                self._open.discard(doc_id)
                self._core.release(doc_id)

    def outline(self, doc_id: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(item) for item in self._core.doc(doc_id).outline()]

    def text_layer(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(line) for line in self._core.doc(doc_id).text_lines(page)]

    def links(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(link) for link in self._core.doc(doc_id).links(page)]

    def search(self, doc_id: str, query: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(hit) for hit in self._core.doc(doc_id).search(query)]

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        fit = fit if fit in FIT_MODES else "none"
        self._core.store.save_position(doc_id, page, scroll, zoom, fit)

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._core.store.recent_documents(limit)

    # --- links ------------------------------------------------------------------------------

    def open_external(self, url: str) -> None:
        """Open a URL in the system browser (or mail client for mailto:)."""
        if urlsplit(url).scheme in ("http", "https", "mailto"):
            webbrowser.open(url)

    def peek_url(self, url: str) -> bool:
        """Show a web link in a small floating preview window (R11)."""
        if urlsplit(url).scheme not in ("http", "https"):
            return False
        if self._peek is not None:
            self._peek.load_url(url)
            self._peek.restore()
            return True
        x = y = None
        if main := self._window:
            x = max(main.x + main.width - PEEK_SIZE[0] - 24, 0)
            y = main.y + 96
        # No js_api here: never expose the app API to third-party pages.
        peek = webview.create_window(
            "Link preview", url, width=PEEK_SIZE[0], height=PEEK_SIZE[1], x=x, y=y, on_top=True
        )
        if peek is None:
            return False
        peek.events.closed += self._on_peek_closed
        self._peek = peek
        return True

    def peek_expand(self) -> None:
        if self._peek is not None:
            self._peek.on_top = False
            self._peek.maximize()

    def peek_close(self) -> None:
        if self._peek is not None:
            self._peek.destroy()

    def _on_peek_closed(self) -> None:
        self._peek = None

    # --- settings ---------------------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._core.store.get_setting(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._core.store.set_setting(key, value)

    # --- lifecycle --------------------------------------------------------------------------

    def _on_closed(self) -> None:
        self.peek_close()
        with self._core.lock:
            for doc_id in self._open:
                self._core.release(doc_id)
            self._open.clear()
        self._core.window_closed(self._window_id)
