"""MuPDF (PyMuPDF) implementation of the engine interface."""

from pathlib import Path

import pymupdf

from phdf.engine.base import (
    DocumentInfo,
    Link,
    OutlineItem,
    PdfDocument,
    PdfEngine,
    Rect,
    SearchHit,
    TextLine,
    TextSpan,
)


def _rect(r: pymupdf.Rect | tuple) -> Rect:
    r = pymupdf.Rect(r)
    return (round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2))


class MuPdfDocument(PdfDocument):
    def __init__(self, doc: pymupdf.Document) -> None:
        self._doc = doc

    def info(self) -> DocumentInfo:
        meta = self._doc.metadata or {}
        return DocumentInfo(
            page_count=self._doc.page_count,
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            is_encrypted=self._doc.needs_pass,
        )

    def page_size(self, page: int) -> tuple[float, float]:
        rect = self._doc[page].rect
        return rect.width, rect.height

    def render_page(self, page: int, scale: float = 1.0, clip: Rect | None = None) -> bytes:
        pix = self._doc[page].get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False
        )
        return pix.tobytes("png")

    def text_lines(self, page: int) -> list[TextLine]:
        flags = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP
        data = self._doc[page].get_text("dict", flags=flags, sort=True)
        lines: list[TextLine] = []
        for block in data["blocks"]:
            if block.get("type") != 0:  # 0 = text, 1 = image
                continue
            for line in block["lines"]:
                spans = [
                    TextSpan(text=s["text"], bbox=_rect(s["bbox"]), size=round(s["size"], 2))
                    for s in line["spans"]
                    if s["text"].strip()
                ]
                if spans:
                    lines.append(TextLine(bbox=_rect(line["bbox"]), spans=spans))
        return lines

    def links(self, page: int) -> list[Link]:
        result: list[Link] = []
        for link in self._doc[page].get_links():
            rect = _rect(link["from"])
            kind = link["kind"]
            if kind in (pymupdf.LINK_GOTO, pymupdf.LINK_NAMED) and link.get("page", -1) >= 0:
                to = link.get("to")
                y = round(to.y, 2) if isinstance(to, pymupdf.Point) else None
                result.append(Link(rect=rect, kind="goto", page=link["page"], y=y))
            elif kind == pymupdf.LINK_URI and link.get("uri"):
                result.append(Link(rect=rect, kind="uri", uri=link["uri"]))
            else:
                result.append(Link(rect=rect, kind="other"))
        return result

    def search(self, query: str, max_hits: int = 1000) -> list[SearchHit]:
        query = query.strip()
        hits: list[SearchHit] = []
        if not query:
            return hits
        total = 0
        for page in self._doc:
            rects = page.search_for(query)
            if not rects:
                continue
            rects = rects[: max_hits - total]
            hits.append(SearchHit(page=page.number, rects=[_rect(r) for r in rects]))
            total += len(rects)
            if total >= max_hits:
                break
        return hits

    def outline(self) -> list[OutlineItem]:
        # get_toc() is a flat list of [level, title, page(1-based)]; rebuild the tree.
        root: list[OutlineItem] = []
        stack: list[OutlineItem] = []
        for level, title, page in self._doc.get_toc():
            item = OutlineItem(title=title, page=page - 1 if page > 0 else -1, level=level)
            while stack and stack[-1].level >= level:
                stack.pop()
            (stack[-1].children if stack else root).append(item)
            stack.append(item)
        return root

    def close(self) -> None:
        self._doc.close()


class MuPdfEngine(PdfEngine):
    name = "mupdf"

    def open(self, path: str | Path) -> PdfDocument:
        return MuPdfDocument(pymupdf.open(path))
