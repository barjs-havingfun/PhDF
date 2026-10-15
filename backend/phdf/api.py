"""Backend shared by all windows (`Core`) and the per-window API exposed to the frontend (`Api`).

Each window gets its own `Api`, exposed as `window.pywebview.api.*`; pywebview exposes every
public attribute, so internals are underscore-prefixed. Open documents are shared between windows
and reference-counted, so closing a tab in one window never closes the document in another.
Calls arrive on worker threads; MuPDF is not thread-safe, so engine access is serialized.
Page images are served separately by `RenderServer` (see `Core.render`).

Document ids are content hashes, so saving annotations gives a file a new id. `Core` keeps the
old ids as aliases: the frontend can keep using the id it was given for the whole session.
"""

import re
import shutil
import sys
import threading
import uuid
import webbrowser
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import webview

from phdf import __version__
from phdf.db import Store
from phdf.docid import document_id
from phdf.engine import PdfDocument, PdfEngine, Rect
from phdf.engine.base import EDITABLE_KINDS
from phdf.paths import data_dir
from phdf.services import ocr, parking, webview_memory
from phdf.services.terminal import Terminals

FIT_MODES = ("width", "page", "none")
PEEK_SIZE = (560, 460)
SESSION_PREFIX = "session."

# (window_id, x, y) -> None; set by app.py so the API can open new windows.
WindowFactory = Callable[[str, int | None, int | None], None]


def _markdown_converter():
    """pymupdf4llm, imported quietly (it prints an advert for its optional layout add-on)."""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        import pymupdf4llm
    return pymupdf4llm


class Core:
    def __init__(self, engine: PdfEngine, store: Store) -> None:
        self.engine = engine
        self.store = store
        self.lock = threading.RLock()
        self.render_base_url = ""
        self.create_window: WindowFactory | None = None
        self.on_closed_document: Callable[[str], None] | None = None  # e.g. drop image cache
        self.windows: dict[str, Api] = {}
        self._docs: dict[str, PdfDocument] = {}
        self._paths: dict[str, str] = {}
        self._refs: Counter[str] = Counter()
        self._aliases: dict[str, str] = {}  # old id -> current id, after saves
        self._revs: defaultdict[str, Counter[int]] = defaultdict(Counter)  # page render revisions

    # All methods below expect the caller to hold `lock`, except `render` and `window_closed`.

    def resolve(self, doc_id: str) -> str:
        while doc_id in self._aliases:
            doc_id = self._aliases[doc_id]
        return doc_id

    def acquire(self, doc_id: str, path: str) -> PdfDocument:
        """Open (or reuse) a document; pair every call with `release`."""
        doc_id = self.resolve(doc_id)
        doc = self._docs.get(doc_id)
        if doc is None:
            doc = self._docs[doc_id] = self.engine.open(path)
            self._paths[doc_id] = path
            # Page images cached earlier this session may show edits that were never saved.
            revs = self._revs.get(doc_id)
            for page in list(revs or ()):
                revs[page] += 1
        self._refs[doc_id] += 1
        return doc

    def release(self, doc_id: str) -> None:
        doc_id = self.resolve(doc_id)
        self._refs[doc_id] -= 1
        if self._refs[doc_id] <= 0:
            del self._refs[doc_id]
            self._paths.pop(doc_id, None)
            if doc := self._docs.pop(doc_id, None):
                doc.close()  # unsaved changes are discarded with the last reference
            if self.on_closed_document:
                for alias in [
                    doc_id,
                    *(old for old, new in self._aliases.items() if new == doc_id),
                ]:
                    self.on_closed_document(alias)
            if not self._docs:
                self.engine.trim_cache(everything=True)

    def doc(self, doc_id: str) -> PdfDocument:
        return self._docs[self.resolve(doc_id)]

    def revs(self, doc_id: str) -> dict[int, int]:
        return dict(self._revs[self.resolve(doc_id)])

    def bump(self, doc_id: str, page: int | None = None) -> None:
        """Invalidate rendered images of one page (or all pages) of a document."""
        revs = self._revs[self.resolve(doc_id)]
        pages = [page] if page is not None else range(self.doc(doc_id).info().page_count)
        for p in pages:
            revs[p] += 1

    def save(self, doc_id: str) -> str:
        """Write annotations to disk. Returns the document's new id."""
        old = self.resolve(doc_id)
        doc = self._docs[old]
        doc.save()
        new = document_id(self._paths[old])
        if new != old:
            for table in (self._docs, self._paths):
                table[new] = table.pop(old)
            self._refs[new] = self._refs.pop(old)
            self._revs[new] = self._revs.pop(old)
            self._aliases[old] = new
            self.store.rename_document(old, new)
        return new

    def revert(self, doc_id: str) -> None:
        """Throw away unsaved changes by reopening the file."""
        current = self.resolve(doc_id)
        self._docs[current].close()
        self._docs[current] = self.engine.open(self._paths[current])
        self.bump(current)

    def render(self, doc_id: str, page: int, scale: float, clip: Rect | None) -> bytes | None:
        """Called by RenderServer threads."""
        with self.lock:
            doc = self._docs.get(self.resolve(doc_id))
            png = doc.render_page(page, scale, clip) if doc else None
            self.engine.trim_cache()
            return png

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
        self._open: set[str] = set()  # ids (as given to the frontend) this window holds
        self._peek: webview.Window | None = None
        self._force_close = False
        self._terminals = Terminals()

    # --- app / windows ----------------------------------------------------------------------

    def app_info(self) -> dict[str, Any]:
        return {
            "name": "PhDF",
            "version": __version__,
            "renderBaseUrl": self._core.render_base_url,
            "windowId": self._window_id,
            "platform": {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"),
        }

    def pick_file(self, kind: str = "document") -> str | None:
        """File dialog. kind: "document" (PDF or Markdown), "pdf" or "md"."""
        window = self._window or webview.active_window()
        if window is None:
            return None
        types = {
            "document": ("Documents (*.pdf;*.md)", "PDF files (*.pdf)", "Markdown (*.md)"),
            "pdf": ("PDF files (*.pdf)",),
            "md": ("Markdown (*.md)",),
        }[kind] + ("All files (*.*)",)
        result = window.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        return result[0] if result else None

    def pick_pdf(self) -> str | None:
        return self.pick_file("pdf")

    def pick_new_md(self, name: str = "Untitled.md") -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=name, file_types=("Markdown (*.md)",)
        )
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        return path if path.lower().endswith(".md") else path + ".md"

    def open_window(self, paths: list[str], x: int | None = None, y: int | None = None) -> str:
        """Open a new window showing `paths` as tabs (used when a tab is dragged out)."""
        window_id = uuid.uuid4().hex[:8]
        session = {"panes": [{"paths": paths, "active": 0, "width": 1}], "focused": 0}
        self._core.store.set_setting(SESSION_PREFIX + window_id, session)
        if self._core.create_window:
            self._core.create_window(window_id, x, y)
            # Take the references now, so a tab with unsaved annotations survives the move
            # while this window releases its own reference.
            if new := self._core.windows.get(window_id):
                for path in paths:
                    if path.lower().endswith(".pdf"):
                        new.open_document(path)
        return window_id

    # --- documents --------------------------------------------------------------------------

    def open_document(self, path: str) -> dict[str, Any]:
        doc_id = document_id(path)
        core = self._core
        with core.lock:
            if doc_id in self._open:
                doc = core.doc(doc_id)
            else:
                doc = core.acquire(doc_id, path)
                self._open.add(doc_id)
            info = doc.info()
            sizes = doc.page_sizes()
            dirty = doc.dirty
            revs = core.revs(doc_id)
        title = info.title or Path(path).stem
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
        }

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

    def search(self, doc_id: str, query: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(hit) for hit in self._core.doc(doc_id).search(query)]

    def save_position(
        self, doc_id: str, page: int, scroll: float, zoom: float, fit: str = "width"
    ) -> None:
        fit = fit if fit in FIT_MODES else "none"
        with self._core.lock:
            current = self._core.resolve(doc_id)
        self._core.store.save_position(current, page, scroll, zoom, fit)

    def recent_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._core.store.recent_documents(limit)

    # --- annotations ------------------------------------------------------------------------

    def annotations(self, doc_id: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(a) for a in self._core.doc(doc_id).annotations()]

    def _changed(self, doc_id: str, page: int, extra: dict[str, Any]) -> dict[str, Any]:
        core = self._core
        core.bump(doc_id, page)
        result = {**extra, "dirty": core.doc(doc_id).dirty, "revs": core.revs(doc_id)}
        return result

    def add_annotation(
        self,
        doc_id: str,
        page: int,
        kind: str,
        rects: list[Rect],
        color: str,
        contents: str = "",
        strokes: list[list[tuple[float, float]]] | None = None,
    ) -> dict[str, Any]:
        if kind not in EDITABLE_KINDS:
            raise ValueError(f"unsupported annotation kind {kind!r}")
        rects = [tuple(r) for r in rects]  # type: ignore[misc]
        with self._core.lock:
            doc = self._core.doc(doc_id)
            annot = doc.add_annotation(page, kind, rects, color, contents, strokes)  # type: ignore[arg-type]
            return self._changed(doc_id, page, {"annotation": asdict(annot)})

    def update_annotation(
        self, doc_id: str, annot_id: str, color: str | None = None, contents: str | None = None
    ) -> dict[str, Any]:
        with self._core.lock:
            annot = self._core.doc(doc_id).update_annotation(annot_id, color, contents)
            return self._changed(doc_id, annot.page, {"annotation": asdict(annot)})

    def delete_annotation(self, doc_id: str, annot_id: str) -> dict[str, Any]:
        with self._core.lock:
            page = self._core.doc(doc_id).delete_annotation(annot_id)
            return self._changed(doc_id, page, {"page": page})

    def save_document(self, doc_id: str) -> dict[str, Any]:
        with self._core.lock:
            self._core.save(doc_id)
            result = {"dirty": False, "revs": self._core.revs(doc_id)}
        return result

    def revert_document(self, doc_id: str) -> dict[str, Any]:
        with self._core.lock:
            self._core.revert(doc_id)
            result = {"dirty": False, "revs": self._core.revs(doc_id)}
        return result

    def _has_unsaved(self) -> bool:
        with self._core.lock:
            return any(
                self._core.doc(d).dirty
                for d in self._open
                if self._core.resolve(d) in self._core._docs
            )

    def _on_closing(self) -> bool:
        """pywebview `closing` handler: returning False keeps the window open."""
        if self._force_close or not self._has_unsaved():
            return True
        # Let the page show its Save / Don't Save / Cancel sheet. evaluate_js would block the
        # GUI thread we are on, so dispatch from a helper thread.
        window = self._window
        if window is not None:
            threading.Thread(
                target=window.evaluate_js,
                args=("window.dispatchEvent(new CustomEvent('phdf:close-request'))",),
                daemon=True,
            ).start()
        return False

    def toggle_fullscreen(self) -> None:
        if self._window is not None:
            self._window.toggle_fullscreen()

    def close_window(self) -> None:
        """Close this window after the page has dealt with unsaved changes."""
        self._force_close = True
        if self._window is not None:
            self._window.destroy()

    # --- OCR ----------------------------------------------------------------------------------

    def ocr_info(self) -> dict[str, Any]:
        return {"installed": ocr.installed_languages(), "common": ocr.COMMON_LANGUAGES}

    def ocr_download(self, lang: str) -> list[str]:
        ocr.download_language(lang)
        return ocr.installed_languages()

    def page_has_text(self, doc_id: str, page: int) -> bool:
        with self._core.lock:
            return self._core.doc(doc_id).has_text(page)

    def pages_without_text(self, doc_id: str) -> list[int]:
        """Scans every page; the lock is taken per page so rendering is not held up."""
        with self._core.lock:
            count = self._core.doc(doc_id).info().page_count
        missing = []
        for page in range(count):
            with self._core.lock:
                if not self._core.doc(doc_id).has_text(page):
                    missing.append(page)
                self._core.engine.trim_cache()
        return missing

    def ocr_page(self, doc_id: str, page: int, languages: list[str]) -> dict[str, Any]:
        """Recognize one page and add its invisible text layer (an unsaved change)."""
        scale = ocr.OCR_DPI / 72
        with self._core.lock:
            png = self._core.doc(doc_id).render_page(page, scale)
        words = ocr.recognize(png, scale, languages)  # slow part, without the lock
        with self._core.lock:
            doc = self._core.doc(doc_id)
            if words:
                doc.add_invisible_text(page, [(w.text, w.bbox) for w in words], ocr.unicode_font())
            return self._changed(doc_id, page, {"words": len(words)})

    # --- export -------------------------------------------------------------------------------

    def export_markdown(self, doc_id: str) -> str:
        """The document's text as Markdown (headings, lists, tables), including unsaved OCR."""
        import pymupdf

        pymupdf4llm = _markdown_converter()

        with self._core.lock:
            data = self._core.doc(doc_id).to_bytes()
        with pymupdf.open("pdf", data) as copy:
            return pymupdf4llm.to_markdown(copy, show_progress=False)

    # --- Obsidian -------------------------------------------------------------------------------

    def pick_folder(self) -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    def _vault_note(self, title: str) -> Path:
        store = self._core.store
        vault = store.get_setting("obsidian.vault")
        if not vault:
            raise ValueError("No Obsidian vault chosen")
        folder = (store.get_setting("obsidian.folder") or "PhDF").strip(" /\\")
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f#^\[\]]', "-", title).strip(" .") or "Untitled"
        return Path(vault, folder, f"{name}.md") if folder else Path(vault, f"{name}.md")

    def obsidian_append(self, title: str, block: str) -> str:
        """Append a pin + quote to the book's note in the vault (created with a heading)."""
        path = self._vault_note(title)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n\n"
        if text and not text.endswith("\n\n"):
            text += "\n" if text.endswith("\n") else "\n\n"
        self.write_text(str(path), text + block)
        return str(path)

    def obsidian_write(self, title: str, text: str, overwrite: bool = False) -> dict[str, Any]:
        """Copy a note into the vault. Without `overwrite`, an existing file is left alone."""
        path = self._vault_note(title)
        if path.exists() and not overwrite:
            return {"path": str(path), "written": False, "exists": True}
        self.write_text(str(path), text)
        return {"path": str(path), "written": True, "exists": True}

    # --- AI terminal ----------------------------------------------------------------------------

    def term_start(self, cwd: str | None = None, cols: int = 80, rows: int = 24) -> str:
        """Start the user's shell (in `cwd`, e.g. the open PDF's folder). Returns a session id."""
        return self._terminals.start(cwd, cols, rows)

    def term_read(self, session_id: str, timeout: float = 0.5) -> dict[str, Any]:
        """Long poll: new output (waits up to `timeout`), and whether the shell still runs."""
        session = self._terminals.get(session_id)
        if session is None:
            return {"data": "", "alive": False}
        data, alive = session.read(min(max(timeout, 0.0), 2.0))
        return {"data": data, "alive": alive}

    def term_write(self, session_id: str, data: str) -> None:
        if session := self._terminals.get(session_id):
            session.write(data)

    def term_resize(self, session_id: str, cols: int, rows: int) -> None:
        if session := self._terminals.get(session_id):
            session.resize(cols, rows)

    def term_ai(self, session_id: str) -> str | None:
        """Which AI CLI runs in the terminal ('claude' / 'codex'), if any."""
        session = self._terminals.get(session_id)
        return session.running_ai() if session else None

    def term_close(self, session_id: str) -> None:
        self._terminals.close(session_id)

    def ai_tools(self) -> dict[str, bool]:
        """Which AI command-line tools are installed on this computer (found on PATH)."""
        home = Path.home()
        extra = [home / ".local" / "bin"]  # the native installers put them here
        found = {}
        for tool in ("claude", "codex"):
            found[tool] = bool(shutil.which(tool)) or any(
                (d / name).exists() for d in extra for name in (tool, f"{tool}.exe")
            )
        return found

    def ai_context(self, doc_id: str, first_page: int, last_page: int) -> dict[str, Any]:
        """Write pages [first_page, last_page] as Markdown for the AI to read; returns the file.

        Cached per document revision and page range in PhDF's data folder (not next to the
        user's PDF), and includes unsaved OCR text."""
        import pymupdf

        pymupdf4llm = _markdown_converter()

        with self._core.lock:
            doc = self._core.doc(doc_id)
            count = doc.info().page_count
            first, last = max(0, first_page), min(count - 1, last_page)
            current = self._core.resolve(doc_id)
            rev = sum(self._core.revs(doc_id).values())
            path = data_dir() / "ai" / f"{current[:12]}-p{first + 1}-{last + 1}-r{rev}.md"
            data = None if path.exists() else doc.to_bytes()
        if data is not None:
            with pymupdf.open("pdf", data) as copy:
                text = pymupdf4llm.to_markdown(
                    copy, pages=list(range(first, last + 1)), show_progress=False
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return {"path": str(path), "first": first, "last": last, "chars": path.stat().st_size}

    # --- parking lot ----------------------------------------------------------------------------

    def parking_path(self, document: str | None = None) -> str:
        """Where thoughts parked while reading `document` (a PDF or .md path) are kept."""
        return str(parking.path_for(document, data_dir()))

    def parking_add(
        self, thought: str, source: str | None = None, document: str | None = None
    ) -> str:
        path = Path(self.parking_path(document))
        title = Path(document).stem if document else None
        parking.add(path, thought, source, title)
        return str(path)

    def parking_list(self, document: str | None = None) -> dict[str, Any]:
        path = Path(self.parking_path(document))
        return {"path": str(path), "items": [asdict(i) for i in parking.items(path)]}

    def parking_done(
        self, line: int, text: str, done: bool = True, document: str | None = None
    ) -> bool:
        return parking.set_done(Path(self.parking_path(document)), line, text, done)

    def open_in_obsidian(self, path: str) -> None:
        webbrowser.open("obsidian://open?path=" + quote(path, safe=""))

    # --- markdown files ---------------------------------------------------------------------

    def md_for_pdf(self, pdf_path: str) -> dict[str, Any]:
        """The Markdown file integrated with a PDF: a linked one, else "<stem>.md" beside it."""
        linked = self._core.store.md_link(pdf_path)
        path = Path(linked) if linked else Path(pdf_path).with_suffix(".md")
        return {"path": str(path), "exists": path.is_file(), "linked": linked is not None}

    def pdf_for_md(self, md_path: str) -> str | None:
        """The PDF a Markdown file is integrated with, if any."""
        if linked := self._core.store.pdf_for_md(md_path):
            return linked
        sibling = Path(md_path).with_suffix(".pdf")
        return str(sibling) if sibling.is_file() else None

    def link_md(self, pdf_path: str, md_path: str) -> None:
        self._core.store.set_md_link(pdf_path, md_path)

    def read_text(self, path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            return {"exists": False, "text": "", "mtime": None}
        return {"exists": True, "text": p.read_text(encoding="utf-8"), "mtime": p.stat().st_mtime}

    def write_text(self, path: str, text: str) -> float:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".phdf-tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(p)  # atomic: a crash never leaves a half-written note
        return p.stat().st_mtime

    def file_mtime(self, path: str) -> float | None:
        p = Path(path)
        return p.stat().st_mtime if p.is_file() else None

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
        self._terminals.close_all()
        with self._core.lock:
            for doc_id in self._open:
                self._core.release(doc_id)
            self._open.clear()
        self._core.window_closed(self._window_id)
