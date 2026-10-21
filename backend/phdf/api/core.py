"""State shared by all windows: open documents (reference-counted), id aliases after saves,
page render revisions and the engine lock."""

import hashlib
import json
import os
import threading
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from phdf.db import Store
from phdf.docid import document_id
from phdf.engine import PdfDocument, PdfEngine, Rect

if TYPE_CHECKING:
    from phdf.api import Api


FIT_MODES = ("width", "page", "none")
PEEK_SIZE = (560, 460)
CLOSE_WAIT = 4.0  # seconds a page has to answer a close request
RELEASES_PAGE = "https://github.com/barjs-havingfun/PhDF/releases"
RELEASES_API = "https://api.github.com/repos/barjs-havingfun/PhDF/releases/latest"
SESSION_PREFIX = "session."


def same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def copy_id(doc_id: str, path: str) -> str:
    """Id of a file whose content id is taken by another file; 64 hex like a content id."""
    key = os.path.normcase(os.path.realpath(path))
    return hashlib.sha256(f"{doc_id}\n{key}".encode()).hexdigest()


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
        self.smoke = False  # `PhDF --smoke-ui <file>` (release CI): quit once the page reports
        self._docs: dict[str, PdfDocument] = {}
        self._paths: dict[str, str] = {}
        self._refs: Counter[str] = Counter()
        self._aliases: dict[str, str] = {}  # old id -> current id, after saves
        self._revs: defaultdict[str, Counter[int]] = defaultdict(Counter)  # page render revisions
        # Text revision per document: only OCR changes the text (annotations don't), so the AI's
        # Markdown copies are keyed by this, not by the render revisions. "0" (absent) is the
        # text on disk; each unsaved change gets a new random label, so copies made from text
        # that was later discarded (closed unsaved, reverted) never match again.
        self.text_revs: dict[str, str] = {}
        self.md_jobs: dict[str, dict[str, Any]] = {}  # whole-document conversions, by cache file
        # Passwords of encrypted PDFs opened this session (memory only, never stored).
        self.passwords: dict[str, str] = {}

    # All methods below expect the caller to hold `lock`, except `render` and `window_closed`.

    def resolve(self, doc_id: str) -> str:
        while doc_id in self._aliases:
            doc_id = self._aliases[doc_id]
        return doc_id

    def open_id(self, doc_id: str, path: str) -> str:
        """The id `path` opens under: its content hash, unless that would share an open,
        writable document with another file (an identical copy, or a file matching an old id
        of a saved one). Such a file gets an id of its own, else its edits would be saved
        into the other file."""
        current = self.resolve(doc_id)
        held = self._paths.get(current)
        if current == doc_id and (held is None or same_file(held, path)):
            return doc_id
        return copy_id(doc_id, path)

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
            self.passwords.pop(doc_id, None)
            self.text_revs.pop(doc_id, None)  # unsaved OCR text goes with the document
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
        if new != old and (new in self._docs or new in self._aliases):
            new = copy_id(new, self._paths[old])  # another file already has this content
        if new != old:
            for table in (self._docs, self._paths):
                table[new] = table.pop(old)
            self._refs[new] = self._refs.pop(old)
            self._revs[new] = self._revs.pop(old)
            if old in self.passwords:  # Revert reopens it with this
                self.passwords[new] = self.passwords.pop(old)
            self._aliases[old] = new
            self.store.rename_document(old, new)
        return new

    def revert(self, doc_id: str) -> None:
        """Throw away unsaved changes by reopening the file."""
        current = self.resolve(doc_id)
        # Opened first (with its password, if it has one): if that fails, the document stays
        # open as it was instead of closed.
        fresh = self.engine.open(self._paths[current], self.passwords.get(current))
        self._docs[current].close()
        self._docs[current] = fresh
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

    def tell_windows(
        self, doc_id: str, event: str, detail: dict[str, Any], skip: "Api | None"
    ) -> None:
        """Send `phdf:<event>` to the other windows showing this document, each with the id it
        knows the document by, so their views don't go stale. Never waits for a window."""
        current = self.resolve(doc_id)
        for api in list(self.windows.values()):
            if api is skip or api._window is None:
                continue
            for held in api._open:
                if self.resolve(held) != current:
                    continue
                payload = json.dumps({**detail, "docId": held})
                script = (
                    f"window.dispatchEvent(new CustomEvent('phdf:{event}', {{detail: {payload}}}))"
                )
                threading.Thread(
                    target=api._window.evaluate_js, args=(script,), daemon=True
                ).start()

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
