import os
import shutil
from pathlib import Path

import pymupdf
import pytest

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import ocr


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


@pytest.fixture
def scanned_pdf(tmp_path):
    """A page that is only an image of text (like a scan)."""
    src = pymupdf.open()
    page = src.new_page()
    page.insert_text((72, 100), "Reading is to the mind", fontsize=24)
    image = page.get_pixmap(dpi=200)
    scan = pymupdf.open()
    sp = scan.new_page(width=page.rect.width, height=page.rect.height)
    sp.insert_image(sp.rect, pixmap=image)
    path = tmp_path / "scan.pdf"
    scan.save(path)
    return path


def test_ink_annotation(api, sample_pdf):
    doc_id = api.open_document(str(sample_pdf))["docId"]
    strokes = [[(100, 100), (120, 130), (150, 110)], [(200, 200), (220, 220)]]
    change = api.add_annotation(doc_id, 0, "ink", [], "#ff375f", "", strokes)
    ink = change["annotation"]
    assert ink["kind"] == "ink" and ink["color"] == "#ff375f"
    x0, y0, x1, y1 = ink["rects"][0]
    assert x0 <= 100 and y0 <= 100 and x1 >= 220 and y1 >= 220


def test_pages_without_text(api, scanned_pdf, sample_pdf):
    assert api.pages_without_text(api.open_document(str(scanned_pdf))["docId"]) == [0]
    assert api.pages_without_text(api.open_document(str(sample_pdf))["docId"]) == []


def _install_test_languages() -> bool:
    """Language files come from PHDF_TEST_TESSDATA or an installed Tesseract (no downloads)."""
    source = os.environ.get("PHDF_TEST_TESSDATA")
    if source and Path(source, "eng.traineddata").exists():
        shutil.copy(Path(source, "eng.traineddata"), ocr.own_tessdata())
    return "eng" in ocr.installed_languages()


def test_ocr_adds_searchable_text(api, scanned_pdf):
    if not _install_test_languages():
        pytest.skip("no OCR language data available")
    doc_id = api.open_document(str(scanned_pdf))["docId"]
    result = api.ocr_page(doc_id, 0, ["eng"])
    assert result["words"] >= 4 and result["dirty"] and result["revs"] == {0: 1}
    assert api.pages_without_text(doc_id) == []
    assert api.search(doc_id, "mind")[0]["page"] == 0
    lines = api.text_layer(doc_id, 0)
    assert "Reading" in " ".join(s["text"] for line in lines for s in line["spans"])


def test_export_markdown(api, sample_pdf):
    doc_id = api.open_document(str(sample_pdf))["docId"]
    md = api.export_markdown(doc_id)
    assert "Page 1" in md and "Page 3" in md


def test_obsidian_notes(api, tmp_path):
    with pytest.raises(ValueError):
        api.obsidian_append("Book", "x")
    vault = tmp_path / "Vault"
    api.set_setting("obsidian.vault", str(vault))

    path = api.obsidian_append('A: "Weird"/Title?', "⎘ phdf · p.1 · #abcde\n> “quote”\n\n")
    assert Path(path) == vault / "PhDF" / "A- -Weird--Title-.md"
    api.obsidian_append('A: "Weird"/Title?', "second\n")
    assert Path(path).read_text(encoding="utf-8") == (
        '# A: "Weird"/Title?\n\n⎘ phdf · p.1 · #abcde\n> “quote”\n\nsecond\n'
    )

    first = api.obsidian_write("Notes", "one")
    assert first["written"]
    assert api.obsidian_write("Notes", "two")["written"] is False
    assert api.obsidian_write("Notes", "two", overwrite=True)["written"]
    assert (vault / "PhDF" / "Notes.md").read_text(encoding="utf-8") == "two"
