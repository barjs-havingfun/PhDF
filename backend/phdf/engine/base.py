"""Engine-neutral interfaces. Implementations: MuPDF (default); PDFium later if needed.

Coordinates are PDF points in the unrotated-to-display page space: origin top-left, y down.
Rects are (x0, y0, x1, y1).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class DocumentInfo:
    page_count: int
    title: str | None = None
    author: str | None = None
    is_encrypted: bool = False
    reflowable: bool = False  # an e-book (EPUB…): laid out into pages; no annotations in the file


@dataclass(frozen=True)
class OutlineItem:
    title: str
    page: int  # 0-based; -1 when the entry has no in-document target
    level: int  # 1 = top level
    children: list["OutlineItem"] = field(default_factory=list)


@dataclass(frozen=True)
class TextSpan:
    text: str
    bbox: Rect
    size: float  # font size in points


@dataclass(frozen=True)
class TextLine:
    """One visual line; used to build the selectable text layer."""

    bbox: Rect
    spans: list[TextSpan]


@dataclass(frozen=True)
class Link:
    rect: Rect
    kind: Literal["goto", "uri", "other"]
    page: int = -1  # target page for "goto"
    y: float | None = None  # target y on that page, when known
    uri: str | None = None  # for "uri"


@dataclass(frozen=True)
class SearchHit:
    page: int
    rects: list[Rect]


class PasswordRequired(Exception):  # noqa: N818 - a state, not an error
    """The PDF is encrypted and needs a (different) password to open."""


AnnotKind = Literal["highlight", "underline", "strikeout", "note", "freetext", "ink", "other"]
EDITABLE_KINDS = ("highlight", "underline", "strikeout", "note", "freetext", "ink")
MOVABLE_KINDS = ("note", "freetext", "ink")


@dataclass(frozen=True)
class Annotation:
    id: str  # our /NM id; "x<xref>" for annotations made elsewhere without one
    page: int
    kind: AnnotKind
    rects: list[Rect]  # one per text line for markup; the icon/box otherwise
    color: str  # "#rrggbb"
    contents: str  # comment / note / free-text body
    quote: str  # text under a markup annotation
    modified: str | None = None
    strokes: list[list[tuple[float, float]]] | None = None  # ink only
    width: float | None = None  # ink line width
    font: str | None = None  # free text: "sans" / "serif" / "mono"
    font_size: float | None = None  # free text, in points
    bold: bool | None = None  # free text


class PdfDocument(ABC):
    """An open document. Page numbers are 0-based."""

    @abstractmethod
    def info(self) -> DocumentInfo: ...

    @abstractmethod
    def page_size(self, page: int) -> tuple[float, float]:
        """Page (width, height) in PDF points, rotation applied."""

    def page_sizes(self) -> list[tuple[float, float]]:
        return [self.page_size(i) for i in range(self.info().page_count)]

    def page_image(self, page: int, scale: float, fmt: str = "png") -> bytes:
        """A whole page as an image file ("png" or "jpg"), for saving."""
        raise NotImplementedError

    @abstractmethod
    def render_page(self, page: int, scale: float = 1.0, clip: Rect | None = None) -> bytes:
        """Render a page (or the `clip` region of it). `scale` 1.0 = 72 DPI.

        Returns PNG bytes, or JPEG for photo-heavy pages (much smaller; text stays crisp PNG).
        Callers tell them apart by the magic bytes."""

    @abstractmethod
    def text_lines(self, page: int) -> list[TextLine]: ...

    @abstractmethod
    def links(self, page: int) -> list[Link]: ...

    @abstractmethod
    def search(self, query: str, max_hits: int = 1000) -> list[SearchHit]:
        """Case-insensitive search over all pages, in page order."""

    @abstractmethod
    def outline(self) -> list[OutlineItem]: ...

    # --- annotations (changes stay in memory until `save`) ---------------------------------

    @abstractmethod
    def annotations(self) -> list[Annotation]: ...

    @abstractmethod
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
        font: str | None = None,
        font_size: float | None = None,
        bold: bool = False,
    ) -> Annotation:
        """`strokes` (lists of points) and `width` are used for "ink" annotations; `font`,
        `font_size` and `bold` for "freetext". `annot_id` re-creates an annotation with its old
        id (undo of a delete keeps note pins working)."""

    @abstractmethod
    def update_annotation(
        self,
        annot_id: str,
        color: str | None = None,
        contents: str | None = None,
        font: str | None = None,
        font_size: float | None = None,
        bold: bool | None = None,
        rect: Rect | None = None,
    ) -> Annotation:
        """Change what is given; `font` / `font_size` / `bold` / `rect` apply to free text."""

    @abstractmethod
    def delete_annotation(self, annot_id: str) -> int:
        """Returns the page the annotation was on."""

    @abstractmethod
    def move_annotation(self, annot_id: str, dx: float, dy: float) -> Annotation:
        """Shift a note, free text or drawing by (dx, dy) points on its page (same id)."""

    @property
    @abstractmethod
    def dirty(self) -> bool: ...

    # --- text layer for scanned pages -----------------------------------------------------

    @abstractmethod
    def has_text(self, page: int) -> bool: ...

    @abstractmethod
    def add_invisible_text(
        self, page: int, words: list[tuple[str, Rect]], fontfile: str | None
    ) -> None:
        """Write OCR'd words as invisible (selectable, searchable) text."""

    @abstractmethod
    def to_bytes(self) -> bytes:
        """The document including unsaved changes."""

    @abstractmethod
    def save(self) -> None:
        """Write changes back to the file the document was opened from."""

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class PdfEngine(ABC):
    name: str

    @abstractmethod
    def open(self, path: str | Path, password: str | None = None) -> PdfDocument: ...

    def trim_cache(self, everything: bool = False) -> None:  # noqa: B027 (optional hook)
        """Let go of some (or all) of the engine's shared cache (decoded images, fonts…)."""
