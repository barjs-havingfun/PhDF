from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """A 3-page PDF with metadata, a two-level outline and two links on page 1."""
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1}")
    first = doc[0]
    first.insert_link(
        {
            "kind": pymupdf.LINK_GOTO,
            "from": pymupdf.Rect(72, 100, 200, 120),
            "page": 2,
            "to": pymupdf.Point(0, 50),
        }
    )
    first.insert_link(
        {
            "kind": pymupdf.LINK_URI,
            "from": pymupdf.Rect(72, 130, 200, 150),
            "uri": "https://example.com/",
        }
    )
    doc.set_metadata({"title": "Sample", "author": "PhDF Tests"})
    doc.set_toc([[1, "Chapter 1", 1], [2, "Section 1.1", 2], [1, "Chapter 2", 3]])
    path = tmp_path / "sample.pdf"
    doc.save(path)
    doc.close()
    return path
