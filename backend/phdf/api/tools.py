"""PhDF Tools: page editing sessions (rotate, delete, merge, split...)."""

import uuid
from pathlib import Path
from typing import Any

import webview

from phdf.api.base import ApiBase
from phdf.api.core import same_file
from phdf.services import (
    pdftools,
)


class ToolsApi(ApiBase):
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
            try:
                self._tools[tid].apply(op)
            except Exception:
                self._tools_changed(tid)  # the session rebuilt its document: render that one
                raise
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
        if same_file(str(dest), str(session.path)):
            raise ValueError("PhDF Tools never changes the original: choose another name.")
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
