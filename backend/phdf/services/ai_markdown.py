"""The document's text as Markdown for the AI, with a marker before every PDF page:

    <!-- PDF page 41 -->

pymupdf4llm writes no page numbers, and printed page numbers differ from PDF pages, so the AI is
told that "page" means these markers. A whole-document conversion runs in the background and is
cached (see `Api.ai_markdown_prepare`); page ranges are then cut from it.
"""

import re
from collections.abc import Callable

MARK = "<!-- PDF page {} -->"
_MARK = re.compile(r"^<!-- PDF page (\d+) -->$", re.M)
CHUNK = 8  # pages per conversion call (progress steps)


def converter():
    """pymupdf4llm, imported quietly (it prints an advert for its optional layout add-on)."""
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        import pymupdf4llm
    return pymupdf4llm


def convert(data: bytes, pages: list[int], progress: Callable[[int], object] | None = None) -> str:
    """Pages (0-based) of a PDF given as bytes, as Markdown with page markers."""
    import pymupdf

    pymupdf4llm = converter()
    out: list[str] = []
    with pymupdf.open("pdf", data) as doc:
        for i in range(0, len(pages), CHUNK):
            part = pages[i : i + CHUNK]
            chunks = pymupdf4llm.to_markdown(doc, pages=part, page_chunks=True, show_progress=False)
            for page, chunk in zip(part, chunks, strict=False):
                out.append(f"{MARK.format(page + 1)}\n\n{chunk['text'].strip()}\n")
            if progress:
                progress(min(i + CHUNK, len(pages)))
    return "\n".join(out)


def cut(text: str, first: int, last: int) -> str:
    """Pages first..last (0-based) of a converted document."""
    marks = list(_MARK.finditer(text))
    keep = []
    for n, m in enumerate(marks):
        page = int(m[1]) - 1
        if first <= page <= last:
            end = marks[n + 1].start() if n + 1 < len(marks) else len(text)
            keep.append(text[m.start() : end].rstrip() + "\n")
    return "\n".join(keep)
