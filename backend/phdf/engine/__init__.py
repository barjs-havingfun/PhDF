"""PDF engine abstraction (D3). The rest of the app talks only to `PdfEngine`/`PdfDocument`."""

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


def default_engine() -> PdfEngine:
    from phdf.engine.mupdf import MuPdfEngine

    return MuPdfEngine()


__all__ = [
    "DocumentInfo",
    "Link",
    "OutlineItem",
    "PdfDocument",
    "PdfEngine",
    "Rect",
    "SearchHit",
    "TextLine",
    "TextSpan",
    "default_engine",
]
