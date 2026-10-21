"""The document's text as Markdown for the AI, with a marker before every PDF page:

    <!-- PDF page 41 -->

pymupdf4llm writes no page numbers, and printed page numbers differ from PDF pages, so the AI is
told that "page" means these markers. A whole-document conversion runs in the background and is
cached (see `Api.ai_markdown_prepare`); page ranges are then cut from it.
"""

import re
from collections.abc import Callable

from phdf.services import workers

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
    """Pages (0-based) of a PDF given as bytes, as Markdown with page markers. Converted in a
    worker process (MuPDF isn't thread-safe), CHUNK pages at a time for the progress."""
    out: list[str] = []
    with workers.snapshot(data) as path:
        for i in range(0, len(pages), CHUNK):
            out.append(workers.run(convert_part, path, pages[i : i + CHUNK]))
            if progress:
                progress(min(i + CHUNK, len(pages)))
    return "\n".join(out)


def convert_part(path: str, part: list[int]) -> str:
    """In a worker: some pages of the PDF file at `path`."""
    import pymupdf

    with pymupdf.open(path) as doc:
        chunks = converter().to_markdown(doc, pages=part, page_chunks=True, show_progress=False)
    return "\n".join(
        f"{MARK.format(page + 1)}\n\n{chunk['text'].strip()}\n"
        for page, chunk in zip(part, chunks, strict=False)
    )


def whole(path: str) -> str:
    """In a worker: the whole PDF file at `path` as Markdown (Export as Markdown)."""
    import pymupdf

    with pymupdf.open(path) as doc:
        return converter().to_markdown(doc, show_progress=False)


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
