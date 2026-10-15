"""Methods exposed to the frontend as `window.pywebview.api.*`.

pywebview exposes every public attribute of this object, so internals are underscore-prefixed.
Calls arrive on worker threads; MuPDF is not thread-safe, so engine access is serialized.
Page images are served separately by `RenderServer` (see `_render`).
"""

import threading
import webbrowser
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


class Api:
    def __init__(self, engine: PdfEngine, store: Store) -> None:
        self._engine = engine
        self._store = store
        self._docs: dict[str, PdfDocument] = {}
        self._lock = threading.Lock()
        self._render_base_url = ""
        self._peek: webview.Window | None = None

    # --- app --------------------------------------------------------------------------------

    def app_info(self) -> dict[str, Any]:
        return {"name": "PhDF", "version": __version__, "renderBaseUrl": self._render_base_url}

    def pick_pdf(self) -> str | None:
        window = webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("PDF files (*.pdf)", "All files (*.*)")
        )
        return result[0] if result else None

    # --- documents --------------------------------------------------------------------------

    def open_document(self, path: str) -> dict[str, Any]:
        doc_id = document_id(path)
        with self._lock:
            doc = self._docs.get(doc_id)
            if doc is None:
                doc = self._docs[doc_id] = self._engine.open(path)
            info = doc.info()
            sizes = doc.page_sizes()
        title = info.title or Path(path).stem
        record = self._store.touch_document(doc_id, str(path), title, info.page_count)
        return {
            "docId": doc_id,
            "path": str(path),
            "title": title,
            "info": asdict(info),
            "pageSizes": [[round(w, 2), round(h, 2)] for w, h in sizes],
            "position": {k: record[k] for k in ("page", "scroll", "zoom", "fit")},
        }

    def close_document(self, doc_id: str) -> None:
        with self._lock:
            if doc := self._docs.pop(doc_id, None):
                doc.close()

    def outline(self, doc_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(item) for item in self._docs[doc_id].outline()]

    def text_layer(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(line) for line in self._docs[doc_id].text_lines(page)]

    def links(self, doc_id: str, page: int) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(link) for link in self._docs[doc_id].links(page)]

    def search(self, doc_id: str, query: str) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(hit) for hit in self._docs[doc_id].search(query)]

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        self._store.save_position(doc_id, page, scroll, zoom, fit if fit in FIT_MODES else "none")

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._store.recent_documents(limit)

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
        if main := webview.windows[0] if webview.windows else None:
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
        return self._store.get_setting(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._store.set_setting(key, value)

    # --- internals --------------------------------------------------------------------------

    def _set_render_base_url(self, url: str) -> None:
        self._render_base_url = url

    def _render(self, doc_id: str, page: int, scale: float, clip: Rect | None) -> bytes | None:
        """Called by RenderServer threads."""
        with self._lock:
            doc = self._docs.get(doc_id)
            return doc.render_page(page, scale, clip) if doc else None

    def _shutdown(self) -> None:
        self.peek_close()
        with self._lock:
            for doc in self._docs.values():
                doc.close()
            self._docs.clear()
