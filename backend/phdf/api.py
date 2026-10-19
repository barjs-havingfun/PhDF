"""Backend shared by all windows (`Core`) and the per-window API exposed to the frontend (`Api`).

Each window gets its own `Api`, exposed as `window.pywebview.api.*`; pywebview exposes every
public attribute, so internals are underscore-prefixed. Open documents are shared between windows
and reference-counted, so closing a tab in one window never closes the document in another.
Calls arrive on worker threads; MuPDF is not thread-safe, so engine access is serialized.
Page images are served separately by `RenderServer` (see `Core.render`).

Document ids are content hashes, so saving annotations gives a file a new id. `Core` keeps the
old ids as aliases: the frontend can keep using the id it was given for the whole session.
"""

import base64
import json
import os
import re
import shutil
import sys
import threading
import uuid
import webbrowser
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import webview

from phdf import __version__
from phdf.db import Store
from phdf.docid import document_id
from phdf.engine import PasswordRequired, PdfDocument, PdfEngine, Rect
from phdf.engine.base import EDITABLE_KINDS
from phdf.paths import data_dir
from phdf.services import (
    ai_cache,
    ai_markdown,
    equations,
    grading,
    ocr,
    parking,
    pdftools,
    titlebar,
    uizoom,
    webpeek,
    webview_memory,
)
from phdf.services.terminal import AI_PROCESS_NAMES, Terminals, command_name

FIT_MODES = ("width", "page", "none")
PEEK_SIZE = (560, 460)
RELEASES_PAGE = "https://github.com/barjs-havingfun/PhDF/releases"
RELEASES_API = "https://api.github.com/repos/barjs-havingfun/PhDF/releases/latest"
SESSION_PREFIX = "session."

# (window_id, x, y) -> None; set by app.py so the API can open new windows.
WindowFactory = Callable[[str, int | None, int | None], None]


class Core:
    def __init__(self, engine: PdfEngine, store: Store) -> None:
        self.engine = engine
        self.store = store
        self.lock = threading.RLock()
        self.render_base_url = ""
        self.create_window: WindowFactory | None = None
        self.on_closed_document: Callable[[str], None] | None = None  # e.g. drop image cache
        self.windows: dict[str, Api] = {}
        self.startup_paths: list[str] = []  # files from the command line, opened once
        self.startup_taken = False  # a page has asked for them: later files go to a window
        self._docs: dict[str, PdfDocument] = {}
        self._paths: dict[str, str] = {}
        self._refs: Counter[str] = Counter()
        self._aliases: dict[str, str] = {}  # old id -> current id, after saves
        self._revs: defaultdict[str, Counter[int]] = defaultdict(Counter)  # page render revisions
        # Text revision per document: only OCR changes the text (annotations don't), so the AI's
        # Markdown copies are keyed by this, not by the render revisions.
        self.text_revs: Counter[str] = Counter()
        self.md_jobs: dict[str, dict[str, Any]] = {}  # whole-document conversions, by cache file
        # Passwords of encrypted PDFs opened this session (memory only, never stored).
        self.passwords: dict[str, str] = {}

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
            doc = self._docs[doc_id] = self.engine.open(path, self.passwords.get(doc_id))
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
        self.text_revs.pop(current, None)
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

    def open_from_system(self, paths: list[str]) -> None:
        """Files the system hands the running PhDF (macOS Finder: "Open With", double-click):
        a tab each in a main window, which comes to the front. Before any page is ready they
        wait with the start-up files."""
        target = next((a for w, a in self.windows.items() if not w.startswith("d")), None)
        target = target or next(iter(self.windows.values()), None)
        if not self.startup_taken or target is None or target._window is None:
            self.startup_paths += [p for p in paths if p not in self.startup_paths]
            return
        for path in paths:
            target._show_path(path)
        threading.Thread(target=target._window.restore, daemon=True).start()

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
        self._tools: dict[str, pdftools.ToolsSession] = {}  # PDF tools sessions of this window
        self._dark = titlebar.os_dark()  # title bar theme (Windows)
        self._fullscreen = False

    # --- app / windows ----------------------------------------------------------------------

    def app_info(self) -> dict[str, Any]:
        return {
            "name": "PhDF",
            "version": __version__,
            "renderBaseUrl": self._core.render_base_url,
            "windowId": self._window_id,
            "detached": self._window_id.startswith("d"),
            "platform": {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"),
        }

    def startup_paths(self) -> list[str]:
        """Files PhDF was started with; handed to the first window that asks."""
        paths, self._core.startup_paths = self._core.startup_paths, []
        self._core.startup_taken = True
        return paths

    def pick_file(self, kind: str = "document") -> str | None:
        """File dialog. kind: "document" (PDF or Markdown), "pdf" or "md"."""
        window = self._window or webview.active_window()
        if window is None:
            return None
        types = {
            "document": (
                "Documents (*.pdf;*.epub;*.md)",
                "PDF files (*.pdf)",
                "EPUB books (*.epub)",
                "Markdown (*.md)",
            ),
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

    def open_window(
        self, paths: list[str], x: int | None = None, y: int | None = None, detached: bool = False
    ) -> str:
        """Open a new window showing `paths` as tabs. A tab dragged out becomes a `detached`
        window (id starts with "d"): just that document, docked back with Dock or at restart."""
        window_id = ("d" if detached else "") + uuid.uuid4().hex[:8]
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

    def open_document(self, path: str, password: str | None = None) -> dict[str, Any]:
        """Open a document for this window. An encrypted PDF answers `{needsPassword, wrong}`
        until it is called again with the right password."""
        doc_id = document_id(path)
        core = self._core
        with core.lock:
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
            sizes = doc.page_sizes()
            dirty = doc.dirty
            revs = core.revs(doc_id)
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

    def check_update(self) -> dict[str, Any]:
        """The latest published release on GitHub (Settings → General lets the user turn this
        off). Sends nothing but the request itself; any failure is just "unknown"."""
        import urllib.request

        request = urllib.request.Request(  # noqa: S310 - fixed https URL
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"PhDF/{__version__}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=6) as response:  # noqa: S310
                data = json.load(response)
        except Exception:  # noqa: BLE001 - offline, no release yet, rate limit…
            return {"ok": False, "current": __version__}
        latest = str(data.get("tag_name", "")).lstrip("v")

        def parts(v: str) -> tuple[int, ...]:
            return tuple(int(n) for n in re.findall(r"\d+", v)[:3])

        return {
            "ok": bool(latest),
            "current": __version__,
            "latest": latest,
            "newer": bool(latest) and parts(latest) > parts(__version__),
            "url": data.get("html_url") or RELEASES_PAGE,
        }

    def make_default_app(self) -> dict[str, str]:
        """Help make PhDF the default PDF app. Windows doesn't let apps do it themselves: open
        Settings → Default apps (on PhDF's page when the installer registered it). Linux:
        xdg-mime when PhDF's .desktop file is installed. Otherwise: how to do it by hand."""
        if sys.platform == "win32":
            import winreg

            registered = False
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\RegisteredApplications") as key:
                        winreg.QueryValueEx(key, "PhDF")
                        registered = True
                except OSError:
                    pass
            os.startfile(  # noqa: S606
                "ms-settings:defaultapps?registeredAppUser=PhDF"
                if registered
                else "ms-settings:defaultapps"
            )
            return {"result": "settings" if registered else "settings-unregistered"}
        if sys.platform == "darwin":
            return {"result": "howto"}
        desktop = [
            Path.home() / ".local/share/applications/phdf.desktop",
            Path("/usr/share/applications/phdf.desktop"),
        ]
        if shutil.which("xdg-mime") and any(d.exists() for d in desktop):
            import subprocess

            subprocess.run(  # noqa: S603, S607
                ["xdg-mime", "default", "phdf.desktop", "application/pdf"], check=False
            )
            return {"result": "done"}
        return {"result": "howto"}

    def open_in_default_app(self, path: str) -> None:
        """Open a file with the system's default app (e.g. to print from Preview on a Mac)."""
        if not Path(path).is_file():
            return
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            import subprocess

            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])  # noqa: S603

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
        width: float | None = None,
        annot_id: str | None = None,
        font: str | None = None,
        font_size: float | None = None,
        bold: bool = False,
    ) -> dict[str, Any]:
        if kind not in EDITABLE_KINDS:
            raise ValueError(f"unsupported annotation kind {kind!r}")
        rects = [tuple(r) for r in rects]  # type: ignore[misc]
        with self._core.lock:
            doc = self._core.doc(doc_id)
            annot = doc.add_annotation(
                page,
                kind,
                rects,
                color,
                contents,
                strokes,
                width,
                annot_id,  # type: ignore[arg-type]
                font,
                font_size,
                bold,
            )
            return self._changed(doc_id, page, {"annotation": asdict(annot)})

    def update_annotation(
        self,
        doc_id: str,
        annot_id: str,
        color: str | None = None,
        contents: str | None = None,
        font: str | None = None,
        font_size: float | None = None,
        bold: bool | None = None,
        rect: list[float] | None = None,
    ) -> dict[str, Any]:
        with self._core.lock:
            annot = self._core.doc(doc_id).update_annotation(
                annot_id, color, contents, font, font_size, bold, tuple(rect) if rect else None
            )
            return self._changed(doc_id, annot.page, {"annotation": asdict(annot)})

    def delete_annotation(self, doc_id: str, annot_id: str) -> dict[str, Any]:
        with self._core.lock:
            page = self._core.doc(doc_id).delete_annotation(annot_id)
            return self._changed(doc_id, page, {"page": page})

    def move_annotation(self, doc_id: str, annot_id: str, dx: float, dy: float) -> dict[str, Any]:
        with self._core.lock:
            annot = self._core.doc(doc_id).move_annotation(annot_id, dx, dy)
            return self._changed(doc_id, annot.page, {"annotation": asdict(annot)})

    def save_document(self, doc_id: str) -> dict[str, Any]:
        with self._core.lock:
            core = self._core
            old = core.resolve(doc_id)
            text_rev = core.text_revs.pop(old, 0)
            new = core.save(doc_id)
            result = {"dirty": False, "revs": core.revs(doc_id)}
        # Same text under a new id: rename the AI's Markdown copies instead of converting again.
        cache = ai_cache.folder(data_dir())
        if new != old and cache.is_dir():
            for f in cache.glob(f"{old[:12]}-*-r{text_rev}.md"):
                rest = f.name[len(old[:12]) : -len(f"-r{text_rev}.md")]
                target = cache / f"{new[:12]}{rest}-r0.md"
                if not target.exists():
                    f.replace(target)
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
        """pywebview `closing` handler: returning False keeps the window open.

        Runs on the GUI thread, so it must never wait long: if the engine is busy (a big
        render, an e-book layout…), don't wait for it; the page knows its own unsaved tabs and
        closes the window itself when there are none."""
        if self._force_close:
            return True
        if self._core.lock.acquire(timeout=0.5):
            try:
                unsaved = self._has_unsaved()
            finally:
                self._core.lock.release()
        else:
            unsaved = True  # busy: let the page check
        if not unsaved:
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

    def window_theme(self, dark: bool) -> None:
        """Match the native title bar to the page's light / dark theme (Windows)."""
        self._dark = dark
        titlebar.apply(self._window, dark, self._fullscreen)

    def ui_zoom(self, factor: float) -> None:
        """Interface size (Settings → Appearance): zoom this window's web view."""
        uizoom.set_zoom(self._window, min(max(float(factor), 0.5), 2.0))

    def epub_text_size(self, size: float) -> list[dict[str, Any]]:
        """Text size of e-books (EPUB): remembered, and every open e-book of this window is laid
        out again. Returns their new page sizes (the page count changes)."""
        size = min(max(float(size), 7), 28)
        self._core.store.set_setting("epub.fontsize", size)
        engine = self._core.engine
        if hasattr(engine, "reflow"):
            engine.reflow = {**engine.reflow, "fontsize": size}
        changed = []
        with self._core.lock:
            for doc_id in self._open:
                doc = self._core.doc(doc_id)
                if not doc.info().reflowable or not hasattr(doc, "relayout"):
                    continue
                doc.relayout(engine.reflow)
                self._core.bump(doc_id)
                changed.append(
                    {
                        "docId": doc_id,
                        "pageSizes": [[round(w, 2), round(h, 2)] for w, h in doc.page_sizes()],
                        "revs": self._core.revs(doc_id),
                    }
                )
        return changed

    def toggle_fullscreen(self) -> None:
        if self._window is not None:
            self._window.toggle_fullscreen()
            # Square corners in full screen (else clicks in a corner reach the window behind);
            # rounded and themed again after it.
            self._fullscreen = not self._fullscreen
            titlebar.apply(self._window, self._dark, self._fullscreen)

    def close_window(self) -> None:
        """Close this window after the page has dealt with unsaved changes."""
        self._force_close = True
        if self._window is not None:
            # A moment later, so this call's answer reaches the page before the webview is gone
            # (else pywebview logs "Cannot access a disposed object").
            later = threading.Timer(0.15, self._window.destroy)
            later.daemon = True
            later.start()

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
        if document_id(path) != doc_id:
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
        """A small PNG of page 1 (data URL), cached in PhDF's data folder."""
        import pymupdf

        cache = data_dir() / "covers" / f"{doc_id[:16]}.png"
        if not cache.exists():
            if not Path(path).is_file():
                return None
            try:
                with pymupdf.open(path) as doc:
                    page = doc[0]
                    pix = page.get_pixmap(
                        matrix=pymupdf.Matrix(220 / page.rect.width, 220 / page.rect.width)
                    )
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_bytes(pix.tobytes("png"))
            except Exception:  # noqa: BLE001 — unreadable / encrypted: no cover
                return None
        return "data:image/png;base64," + base64.b64encode(cache.read_bytes()).decode()

    # --- windows ---------------------------------------------------------------------------------

    def window_at(self, x: float, y: float, scale: float = 1.0) -> str | None:
        """Another PhDF window under a screen point (tab drag between windows). The point is in
        CSS pixels; window geometry may be in device pixels, so both are tried."""
        for wid, api in self._core.windows.items():
            win = api._window
            if wid == self._window_id or win is None:
                continue
            for px, py in ((x, y), (x * scale, y * scale)):
                if win.x <= px < win.x + win.width and win.y <= py < win.y + win.height:
                    return wid
        return None

    def dock(self, paths: list[str]) -> None:
        """A detached window's tabs go back into a main window (a new one if none is open)."""
        main = next((w for w in self._core.windows if not w.startswith("d")), None)
        if main is None:
            self.open_window(paths)
            return
        for path in paths:
            self.send_to_window(main, path)
        target = self._core.windows[main]._window
        if target is not None:
            threading.Thread(target=target.restore, daemon=True).start()

    def send_to_window(self, window_id: str, path: str) -> bool:
        """Move a tab to another open window: it takes its own reference first, then opens it."""
        target = self._core.windows.get(window_id)
        if target is None or target._window is None:
            return False
        if path.lower().endswith(".pdf"):
            target.open_document(path)
        target._show_path(path)
        return True

    def _show_path(self, path: str) -> None:
        """Open `path` as a tab in this window's page (from another thread: evaluate_js waits)."""
        if self._window is None:
            return
        event = f"new CustomEvent('phdf:open-path', {{detail: {json.dumps(path)}}})"
        script = f"window.dispatchEvent({event})"
        threading.Thread(target=self._window.evaluate_js, args=(script,), daemon=True).start()

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
                self._core.text_revs[self._core.resolve(doc_id)] += 1
            return self._changed(doc_id, page, {"words": len(words)})

    # --- export -------------------------------------------------------------------------------

    def export_markdown(self, doc_id: str) -> str:
        """The document's text as Markdown (headings, lists, tables), including unsaved OCR."""
        import pymupdf

        pymupdf4llm = ai_markdown.converter()

        with self._core.lock:
            data = self._core.doc(doc_id).to_bytes()
        with pymupdf.open("pdf", data) as copy:
            return pymupdf4llm.to_markdown(copy, show_progress=False)

    def save_csv(self, name: str, text: str) -> str | None:
        """Ask where to save a CSV and write it (with a BOM, so Excel reads accents right)."""
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=name, file_types=("CSV (*.csv)",)
        )
        if not result:
            return None
        path = Path(result if isinstance(result, str) else result[0])
        if path.suffix.lower() != ".csv":
            path = path.with_name(path.name + ".csv")
        path.write_text(text, encoding="utf-8-sig", newline="")
        return str(path)

    # --- grading ------------------------------------------------------------------------------

    def grading_scan(self, folder: str) -> dict[str, Any]:
        """The exam PDFs in a folder and where its grades table goes."""
        return {
            "folder": str(Path(folder)),
            # Settings key: case-insensitive only where the file system is (Windows).
            "key": os.path.normcase(str(Path(folder))),
            "title": Path(folder).name,
            "table": str(grading.table_path(folder)),
            "files": grading.scan(folder),
        }

    def grading_copy(self, folder: str, rel: str) -> str:
        """Path of the marked copy of one exam (created from the original on first use)."""
        return str(grading.graded_copy(folder, rel))

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
        equations.cleanup(equations.work_dir(cwd), older_than=3600)  # leftovers of earlier runs
        return self._terminals.start(cwd, cols, rows)

    # --- equation → LaTeX (through the AI in the terminal) -----------------------------------

    def equation_snip(
        self, doc_id: str, page: int, rect: list[float], folder: str | None = None
    ) -> dict[str, str]:
        """Render a region of a page to a PNG the AI can read, next to where it will write the
        LaTeX. Both live in a hidden temp folder inside the terminal's working folder."""
        with self._core.lock:
            png = self._core.doc(doc_id).render_page(page, equations.SCALE, tuple(rect))  # type: ignore[arg-type]
        return equations.prepare(equations.work_dir(folder), png)

    def equation_result(self, tex_path: str) -> str | None:
        return equations.result(tex_path)

    def equation_cleanup(self, png_path: str) -> None:
        equations.remove(png_path)

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
        """Which AI CLI runs in the terminal (claude, codex, gemini or the default agent)."""
        session = self._terminals.get(session_id)
        if session is None:
            return None
        names = set(AI_PROCESS_NAMES)
        if own := command_name(self._core.store.get_setting("ai.agent") or ""):
            names.add(own)
        return session.running_ai(names)

    def term_close(self, session_id: str) -> None:
        self._terminals.close(session_id)

    def ai_tools(self) -> dict[str, bool]:
        """Which AI command-line tools are installed on this computer (found on PATH)."""
        home = Path.home()
        # A Mac app started from Finder (or a Linux launcher) gets a short PATH, so also look
        # where the installers, Homebrew and npm put these tools.
        extra = [
            home / ".local" / "bin",
            home / ".claude" / "local",
            home / ".npm-global" / "bin",
            home / ".volta" / "bin",
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
        ]
        if appdata := os.environ.get("APPDATA"):
            extra.append(Path(appdata) / "npm")
        found = {}
        for tool in ("claude", "codex", "gemini"):
            found[tool] = bool(shutil.which(tool)) or any(
                (d / name).exists() for d in extra for name in (tool, f"{tool}.exe")
            )
        return found

    def _ai_file(self, doc_id: str, part: str) -> Path:
        """Cache file of the AI's Markdown copy (`part`: "all" or "p<a>-<b>"). Caller holds lock."""
        current = self._core.resolve(doc_id)
        rev = self._core.text_revs[current]
        return ai_cache.folder(data_dir()) / f"{current[:12]}-{part}-r{rev}.md"

    def ai_context(self, doc_id: str, first_page: int, last_page: int) -> dict[str, Any]:
        """Write pages [first_page, last_page] as Markdown (with page markers) for the AI to read;
        returns the file. Cut from the whole-document copy when it is ready, else converted now.
        Cached in PhDF's data folder (not next to the user's PDF); includes unsaved OCR text."""
        with self._core.lock:
            doc = self._core.doc(doc_id)
            count = doc.info().page_count
            first, last = max(0, first_page), min(count - 1, last_page)
            path = self._ai_file(doc_id, f"p{first + 1}-{last + 1}")
            whole = self._ai_file(doc_id, "all")
            data = None if path.exists() or whole.exists() else doc.to_bytes()
        if path.exists():
            ai_cache.touch(path)  # used again: cleaning keeps it longer
        else:
            if data is None:
                text = ai_markdown.cut(whole.read_text(encoding="utf-8"), first, last)
                ai_cache.touch(whole)
            else:
                text = ai_markdown.convert(data, list(range(first, last + 1)))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            ai_cache.cleanup(path.parent)
        return {"path": str(path), "first": first, "last": last, "chars": path.stat().st_size}

    def ai_markdown_status(self, doc_id: str) -> dict[str, Any]:
        """The whole-document Markdown copy: "ready", "working" (done / total pages) or "none"."""
        with self._core.lock:
            whole = self._ai_file(doc_id, "all")
            total = self._core.doc(doc_id).info().page_count
        if whole.exists():
            return {"state": "ready", "done": total, "total": total}
        job = self._core.md_jobs.get(str(whole))
        if job and job["state"] == "working":
            return dict(job)
        if job and job["state"] == "error":
            return dict(job)
        return {"state": "none", "done": 0, "total": total}

    def ai_markdown_prepare(self, doc_id: str) -> dict[str, Any]:
        """Start converting the whole document in the background (once); returns the status."""
        status = self.ai_markdown_status(doc_id)
        if status["state"] in ("ready", "working"):
            return status
        with self._core.lock:
            whole = self._ai_file(doc_id, "all")
            data = self._core.doc(doc_id).to_bytes()
            total = self._core.doc(doc_id).info().page_count
        job = {"state": "working", "done": 0, "total": total}
        self._core.md_jobs[str(whole)] = job

        def work() -> None:
            try:
                text = ai_markdown.convert(
                    data, list(range(total)), lambda done: job.update(done=done)
                )
                whole.parent.mkdir(parents=True, exist_ok=True)
                tmp = whole.with_name(whole.name + ".part")
                tmp.write_text(text, encoding="utf-8")
                tmp.replace(whole)
                job["state"] = "ready"
                ai_cache.cleanup(whole.parent)
            except Exception as e:  # noqa: BLE001 - shown in the menu
                job.update(state="error", error=str(e))

        threading.Thread(target=work, daemon=True).start()
        return dict(job)

    def ai_cache_info(self) -> dict[str, int]:
        return ai_cache.info(ai_cache.folder(data_dir()))

    def ai_cache_clear(self) -> dict[str, int]:
        ai_cache.clear(ai_cache.folder(data_dir()))
        return self.ai_cache_info()

    # --- PDF tools (Phase 7) ------------------------------------------------------------------
    # A session edits a copy in memory; its pages are served like a document's (`Core.render`)
    # under the session id. Results are always new files; the original is never written.

    def tools_open(self, path: str) -> dict[str, Any]:
        from phdf.engine.mupdf import MuPdfDocument

        session = pdftools.ToolsSession(path)
        tid = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex, like a document id (render URLs)
        with self._core.lock:
            self._tools[tid] = session
            self._core._docs[tid] = MuPdfDocument(session.doc)
        return self._tools_state(tid)

    def _tools_state(self, tid: str) -> dict[str, Any]:
        session = self._tools[tid]
        doc = session.doc
        return {
            "id": tid,
            "path": str(session.path),
            "name": session.path.name,
            "pages": [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc],
            "annotated": [p.first_annot is not None for p in doc],
            "canUndo": bool(session.ops),
            "revs": self._core.revs(tid),
        }

    def _tools_changed(self, tid: str, pages: list[int] | None = None) -> dict[str, Any]:
        """Caller holds the lock: the session's document may be a new object. Redraw `pages`
        (default: all; pages change places after most operations)."""
        from phdf.engine.mupdf import MuPdfDocument

        self._core._docs[tid] = MuPdfDocument(self._tools[tid].doc)
        for page in pages if pages is not None else [None]:
            self._core.bump(tid, page)
        return self._tools_state(tid)

    def tools_apply(self, tid: str, op: dict[str, Any]) -> dict[str, Any]:
        with self._core.lock:
            self._tools[tid].apply(op)
            rotated = [int(p) for p in op.get("pages", [])] if op.get("kind") == "rotate" else None
            return self._tools_changed(tid, rotated)

    def tools_undo(self, tid: str) -> dict[str, Any]:
        with self._core.lock:
            self._tools[tid].undo()
            return self._tools_changed(tid)

    def tools_chapters(self, tid: str) -> list[int]:
        """First pages (0-based) of the top-level outline entries, for "split at chapters"."""
        with self._core.lock:
            toc = self._tools[tid].doc.get_toc()
        return sorted({page - 1 for level, _, page in toc if level == 1 and page > 0})

    def tools_has_annotations(self, tid: str, pages: list[int] | None = None) -> bool:
        with self._core.lock:
            return self._tools[tid].has_annotations(pages)

    def tools_save(self, tid: str, keep_annotations: bool = True) -> str:
        """The whole edited document as "<name>_phdfE.pdf" next to the original."""
        with self._core.lock:
            session = self._tools[tid]
            return str(session.write(pdftools.copy_path(session.path), None, keep_annotations))

    def tools_extract(
        self, tid: str, pages: list[int], keep_annotations: bool = True
    ) -> str | None:
        """Selected pages as a new PDF; asks where ("<name>_p_3-7_phdf.pdf" suggested)."""
        session = self._tools[tid]
        suggested = pdftools.part_path(session.path, pages)
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=str(suggested.parent),
            save_filename=suggested.name,
            file_types=("PDF files (*.pdf)",),
        )
        if not result:
            return None
        dest = Path(result if isinstance(result, str) else result[0])
        if dest.suffix.lower() != ".pdf":
            dest = dest.with_name(dest.name + ".pdf")
        with self._core.lock:
            return str(session.write(dest, pages, keep_annotations))

    def tools_split(
        self, tid: str, parts: list[list[int]], keep_annotations: bool = True
    ) -> list[str]:
        """Each part as "<name>_p_<a>-<b>_phdf.pdf" next to the original."""
        with self._core.lock:
            session = self._tools[tid]
            return [
                str(session.write(pdftools.part_path(session.path, part), part, keep_annotations))
                for part in parts
                if part
            ]

    def tools_close(self, tid: str) -> None:
        with self._core.lock:
            if session := self._tools.pop(tid, None):
                self._core._docs.pop(tid, None)
                self._core._revs.pop(tid, None)
                session.close()
        if self._core.on_closed_document:
            self._core.on_closed_document(tid)

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

    def md_files(self, folder: str) -> list[dict[str, str]]:
        """The Markdown notes in a folder (a standalone note's sidebar), by name. PhDF's own
        side files (parking lots, grades tables) are left out."""
        try:
            found = [p for p in Path(folder).iterdir() if p.suffix.lower() == ".md" and p.is_file()]
        except OSError:
            return []
        own = (".parking.md", ".grades.md")
        found = sorted(
            (p for p in found if not p.name.lower().endswith(own)), key=lambda p: p.name.lower()
        )
        return [{"name": p.name, "path": str(p)} for p in found]

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

    def rename_file(self, path: str, name: str) -> str:
        """Rename a note in its folder (".md" added if missing); returns the new path. A note
        shown with a PDF stays linked to it."""
        old = Path(path)
        name = name.strip()
        if not name or name in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
            raise ValueError("That name can't be used for a file.")
        if not name.lower().endswith(".md"):
            name += ".md"
        new = old.with_name(name)
        if new == old:
            return str(old)
        # A case-only change on Windows is the same file, not a clash.
        same = new.exists() and old.exists() and os.path.samefile(old, new)
        if new.exists() and not same:
            raise ValueError(f"“{name}” already exists in this folder.")
        store = self._core.store
        pdf = store.pdf_for_md(str(old))
        if pdf is None and old.with_suffix(".pdf").is_file():
            pdf = str(old.with_suffix(".pdf"))  # the default "<pdf>.md" note
        if old.exists():
            old.rename(new)  # a note never written yet only changes its path
        if pdf:
            store.set_md_link(pdf, str(new))
        return str(new)

    def file_mtime(self, path: str) -> float | None:
        p = Path(path)
        return p.stat().st_mtime if p.is_file() else None

    # --- links ------------------------------------------------------------------------------

    def open_external(self, url: str) -> None:
        """Open a URL in the system browser (or mail client for mailto:)."""
        if urlsplit(url).scheme in ("http", "https", "mailto"):
            webbrowser.open(url)

    def peek_url(self, url: str, large: bool = False) -> bool:
        """Show a web link in a floating preview window (R11): small beside a PDF, `large`
        (most of the app window, centered) for links in notes. A movable native window with
        a bar on top: Back, Open in Browser, close."""
        if urlsplit(url).scheme not in ("http", "https"):
            return False
        main = self._window
        width, height = PEEK_SIZE
        x = y = None
        if main is not None:
            if large:
                width, height = max(int(main.width * 0.8), 640), max(int(main.height * 0.82), 480)
                x, y = main.x + (main.width - width) // 2, main.y + (main.height - height) // 2
            else:
                x, y = max(main.x + main.width - width - 24, 0), main.y + 96
        if self._peek is not None:
            self._peek.load_url(url)
            self._peek.restore()
            if large and x is not None and y is not None:
                self._peek.resize(width, height)
                self._peek.move(x, y)
            return True
        # Never the app API for third-party pages: only the bar's two actions.
        bridge = webpeek.PeekBridge()
        peek = webview.create_window(
            "Link preview", url, js_api=bridge, width=width, height=height, x=x, y=y, on_top=True
        )
        if peek is None:
            return False
        bridge._window = peek
        peek.events.loaded += lambda: webpeek.add_bar(peek)
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
        self._core.window_closed(self._window_id)
        # The rest can take a moment (stopping terminals waits for their processes, closing
        # the link preview needs the GUI thread on macOS): never on the thread that closes the
        # window, or the app freezes while quitting.
        threading.Thread(target=self._clean_up, daemon=True).start()

    def _clean_up(self) -> None:
        self.peek_close()
        for tid in list(self._tools):
            self.tools_close(tid)
        self._terminals.close_all()
        with self._core.lock:
            for doc_id in self._open:
                self._core.release(doc_id)
            self._open.clear()
