"""Annotations: add / change / move / delete, save and revert."""

from dataclasses import asdict
from typing import Any

from phdf.api.base import ApiBase
from phdf.engine import Rect
from phdf.engine.base import EDITABLE_KINDS
from phdf.paths import data_dir
from phdf.services import (
    ai_cache,
)


class AnnotationsApi(ApiBase):
    # --- annotations ------------------------------------------------------------------------

    def annotations(self, doc_id: str) -> list[dict[str, Any]]:
        with self._core.lock:
            return [asdict(a) for a in self._core.doc(doc_id).annotations()]

    def _changed(self, doc_id: str, page: int, extra: dict[str, Any]) -> dict[str, Any]:
        core = self._core
        core.bump(doc_id, page)
        state = {"dirty": core.doc(doc_id).dirty, "revs": core.revs(doc_id)}
        core.tell_windows(doc_id, "doc-changed", state, skip=self)
        return {**extra, **state}

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
            core.tell_windows(doc_id, "doc-changed", result, skip=self)
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
            self._core.tell_windows(doc_id, "doc-changed", result, skip=self)
        return result
