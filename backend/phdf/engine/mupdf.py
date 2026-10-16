"""MuPDF (PyMuPDF) implementation of the engine interface."""

import os
import secrets
import string
from pathlib import Path

import pymupdf

from phdf.engine.base import (
    Annotation,
    AnnotKind,
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

_KINDS: dict[int, AnnotKind] = {
    pymupdf.PDF_ANNOT_HIGHLIGHT: "highlight",
    pymupdf.PDF_ANNOT_UNDERLINE: "underline",
    pymupdf.PDF_ANNOT_SQUIGGLY: "underline",
    pymupdf.PDF_ANNOT_STRIKE_OUT: "strikeout",
    pymupdf.PDF_ANNOT_TEXT: "note",
    pymupdf.PDF_ANNOT_FREE_TEXT: "freetext",
    pymupdf.PDF_ANNOT_INK: "ink",
}
_MARKUP = ("highlight", "underline", "strikeout")
_ID_CHARS = string.ascii_lowercase + string.digits


def _rect(r: pymupdf.Rect | tuple) -> Rect:
    r = pymupdf.Rect(r)
    return (round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2))


def _hex(rgb: list[float] | tuple[float, ...] | None) -> str:
    if not rgb or len(rgb) < 3:
        return "#ffd60a"
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb[:3])


def _rgb(color: str) -> tuple[float, float, float]:
    c = color.lstrip("#")
    return (int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255)


def new_annotation_id() -> str:
    return "".join(secrets.choice(_ID_CHARS) for _ in range(5))


class MuPdfDocument(PdfDocument):
    def __init__(self, doc: pymupdf.Document, path: str | Path | None = None) -> None:
        self._doc = doc
        self._path = Path(path) if path else None
        # Tracked ourselves: PyMuPDF's is_dirty stays set after an incremental save.
        self._dirty = False

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
        p = self._doc[page]
        pix = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
        if self._photo_heavy(p, pymupdf.Rect(clip) if clip else p.rect):
            return pix.tobytes("jpg", jpg_quality=88)
        return pix.tobytes("png")

    @staticmethod
    def _photo_heavy(page: pymupdf.Page, area: pymupdf.Rect) -> bool:
        """More than half of the area covered by images (scans, photos, covers)."""
        if area.is_empty:
            return False
        covered = 0.0
        for info in page.get_image_info():
            covered += abs(pymupdf.Rect(info["bbox"]) & area)
        return covered > 0.5 * abs(area)

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

    # --- annotations ----------------------------------------------------------------------

    def _annot_id(self, annot: pymupdf.Annot) -> str:
        nm = annot.info.get("id") or ""
        # MuPDF's own "fitz-…" names are not stable across sessions; fall back to the xref.
        return nm if nm and not nm.startswith("fitz-") else f"x{annot.xref}"

    def _to_model(self, page: pymupdf.Page, annot: pymupdf.Annot) -> Annotation:
        kind = _KINDS.get(annot.type[0], "other")
        rects: list[Rect]
        if kind in _MARKUP and annot.vertices:
            v = annot.vertices  # 4 points per quad: ul, ur, ll, lr
            rects = [_rect(pymupdf.Quad(v[i : i + 4]).rect) for i in range(0, len(v) - 3, 4)]
        else:
            rects = [_rect(annot.rect)]
        quote = ""
        if kind in _MARKUP:
            quote = " ".join(page.get_textbox(r).strip() for r in rects).strip()
        if kind == "freetext":
            color = self._freetext_color(annot)
        else:
            colors = annot.colors or {}
            color = _hex(colors.get("stroke") or colors.get("fill"))
        info = annot.info
        strokes = width = None
        if kind == "ink":
            strokes = [[(round(x, 2), round(y, 2)) for x, y in s] for s in (annot.vertices or [])]
            width = (annot.border or {}).get("width") or 2
        return Annotation(
            id=self._annot_id(annot),
            page=page.number,
            kind=kind,
            rects=rects,
            color=color,
            contents=info.get("content", ""),
            quote=" ".join(quote.split()),
            modified=info.get("modDate") or None,
            strokes=strokes,
            width=width,
        )

    def _freetext_color(self, annot: pymupdf.Annot) -> str:
        """Free text stores its colour in the /DA string, e.g. "1 0 0 rg /Helv 12 Tf"."""
        kind, da = self._doc.xref_get_key(annot.xref, "DA")
        parts = da.strip("()").split() if kind == "string" else []
        if "rg" in parts and (i := parts.index("rg")) >= 3:
            try:
                return _hex([float(v) for v in parts[i - 3 : i]])
            except ValueError:
                pass
        return "#000000"

    def _find(self, annot_id: str) -> tuple[pymupdf.Page, pymupdf.Annot]:
        for page in self._doc:
            for annot in page.annots():
                if self._annot_id(annot) == annot_id:
                    return page, annot
        raise KeyError(annot_id)

    def annotations(self) -> list[Annotation]:
        return [self._to_model(page, a) for page in self._doc for a in page.annots()]

    def add_annotation(
        self,
        page: int,
        kind: AnnotKind,
        rects: list[Rect],
        color: str,
        contents: str = "",
        strokes: list[list[tuple[float, float]]] | None = None,
        width: float | None = None,
        annot_id: str | None = None,
    ) -> Annotation:
        p = self._doc[page]
        rgb = _rgb(color)
        boxes = [pymupdf.Rect(r) for r in rects]
        if kind == "highlight":
            annot = p.add_highlight_annot(boxes)
        elif kind == "underline":
            annot = p.add_underline_annot(boxes)
        elif kind == "strikeout":
            annot = p.add_strikeout_annot(boxes)
        elif kind == "note":
            annot = p.add_text_annot(boxes[0].tl, contents, icon="Note")
        elif kind == "freetext":
            annot = p.add_freetext_annot(
                boxes[0], contents, fontsize=12, text_color=rgb, border_width=0
            )
        elif kind == "ink":
            if not strokes:
                raise ValueError("ink annotations need strokes")
            annot = p.add_ink_annot([[tuple(pt) for pt in stroke] for stroke in strokes])
            annot.set_border(width=width or 2)
        else:
            raise ValueError(f"cannot create {kind!r} annotations")
        if kind != "freetext":
            annot.set_colors(stroke=rgb)
        annot.set_info(content=contents)
        annot.update()
        nm = annot_id if annot_id and not annot_id.startswith("x") else new_annotation_id()
        self._doc.xref_set_key(annot.xref, "NM", pymupdf.get_pdf_str(nm))
        self._dirty = True
        return self._to_model(p, annot)

    def update_annotation(
        self, annot_id: str, color: str | None = None, contents: str | None = None
    ) -> Annotation:
        page, annot = self._find(annot_id)
        kind = _KINDS.get(annot.type[0], "other")
        if contents is not None:
            annot.set_info(content=contents)
        if kind == "freetext":
            # Free text keeps its colour in the appearance string; re-apply it on every update.
            rgb = _rgb(color) if color else _rgb(self._to_model(page, annot).color)
            annot.update(text_color=rgb)
        else:
            if color is not None:
                annot.set_colors(stroke=_rgb(color))
            annot.update()
        self._dirty = True
        return self._to_model(page, annot)

    def delete_annotation(self, annot_id: str) -> int:
        page, annot = self._find(annot_id)
        page.delete_annot(annot)
        self._dirty = True
        return page.number

    def move_annotation(self, annot_id: str, dx: float, dy: float) -> Annotation:
        page, annot = self._find(annot_id)
        model = self._to_model(page, annot)
        if model.kind == "ink":
            # Ink points can't be edited in place: re-create the drawing, shifted, with its id.
            strokes = [[(x + dx, y + dy) for x, y in s] for s in model.strokes or []]
            page.delete_annot(annot)
            return self.add_annotation(
                page.number, "ink", [], model.color, model.contents, strokes, model.width, model.id
            )
        if model.kind not in ("note", "freetext"):
            raise ValueError(f"cannot move {model.kind!r} annotations")
        annot.set_rect(annot.rect + (dx, dy, dx, dy))
        if model.kind == "freetext":
            annot.update(text_color=_rgb(model.color))
        else:
            annot.update()
        self._dirty = True
        return self._to_model(page, annot)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def has_text(self, page: int) -> bool:
        return bool(self._doc[page].get_text("text").strip())

    def add_invisible_text(
        self, page: int, words: list[tuple[str, Rect]], fontfile: str | None
    ) -> None:
        p = self._doc[page]
        fontname = "helv"
        font = pymupdf.Font("helv")
        if fontfile:
            fontname = "phdf-ocr"
            p.insert_font(fontname=fontname, fontfile=fontfile)
            font = pymupdf.Font(fontfile=fontfile)
        for text, (x0, y0, x1, y1) in words:
            height = y1 - y0
            if height <= 0 or x1 <= x0:
                continue
            size = height * 0.85
            natural = font.text_length(text, fontsize=size)
            stretch = (x1 - x0) / natural if natural else 1
            baseline = pymupdf.Point(x0, y1 - height * 0.2)
            p.insert_text(
                baseline,
                text,
                fontsize=size,
                fontname=fontname,
                render_mode=3,  # invisible
                morph=(baseline, pymupdf.Matrix(stretch, 1)),
            )
        self._dirty = True

    def to_bytes(self) -> bytes:
        return self._doc.tobytes()

    def save(self) -> None:
        if self._path is None:
            raise ValueError("document has no file to save to")
        if self._doc.can_save_incrementally():
            self._doc.saveIncr()  # appends changes; fast and keeps the original bytes intact
            self._dirty = False
            return
        # Fallback: write a full copy next to the file, then swap it in.
        tmp = self._path.with_name(self._path.name + ".phdf-tmp")
        self._doc.save(tmp, garbage=1, deflate=True)
        self._doc.close()
        os.replace(tmp, self._path)
        self._doc = pymupdf.open(self._path)
        self._dirty = False

    def close(self) -> None:
        self._doc.close()


class MuPdfEngine(PdfEngine):
    name = "mupdf"

    _TRIM_EVERY = 4  # renders between trims (scanned books decode ~20 MB images per page)

    def __init__(self) -> None:
        self._renders = 0

    def trim_cache(self, everything: bool = False) -> None:
        # MuPDF's store grows to 256 MB by default; PyMuPDF can't read its size or set a limit,
        # so halve it every few renders and empty it when no document is open.
        if everything:
            pymupdf.TOOLS.store_shrink(100)
            return
        self._renders += 1
        if self._renders % self._TRIM_EVERY == 0:
            pymupdf.TOOLS.store_shrink(100)

    def open(self, path: str | Path) -> PdfDocument:
        return MuPdfDocument(pymupdf.open(path), path)
