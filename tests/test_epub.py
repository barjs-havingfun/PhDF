import zipfile
from pathlib import Path

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">test</dc:identifier><dc:title>Tiny Book</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="c1"/></spine>
</package>"""


def make_epub(path, paragraphs=60):
    body = "".join(
        f"<p>Paragraph {i} of the tiny book, with some words to fill the page.</p>"
        for i in range(paragraphs)
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("content.opf", OPF)
        z.writestr(
            "c1.xhtml",
            f'<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>One</h1>{body}</body></html>',
        )
    return path


def test_open_read_and_reflow_an_epub(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    book = make_epub(tmp_path / "tiny.epub")
    doc = api.open_document(str(book))
    assert doc["info"]["reflowable"] and doc["info"]["page_count"] >= 1
    assert api.annotations(doc["docId"]) == []
    assert any(
        "Paragraph 1" in s["text"]
        for line in api.text_layer(doc["docId"], 0)
        for s in line["spans"]
    )
    context = Path(api.ai_context(doc["docId"], 0, 0)["path"])
    assert "Paragraph" in context.read_text(encoding="utf-8")
    small = len(doc["pageSizes"])
    [changed] = api.epub_text_size(20)  # bigger text: more pages
    assert changed["docId"] == doc["docId"] and len(changed["pageSizes"]) > small
