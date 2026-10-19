"""OCR and export (Markdown, CSV)."""

from pathlib import Path
from typing import Any

import webview

from phdf.api.base import ApiBase
from phdf.services import (
    ai_markdown,
    ocr,
)


class OcrExportApi(ApiBase):
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
