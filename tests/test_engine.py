import pymupdf

from phdf.engine import default_engine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_info(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        info = doc.info()
    assert info.page_count == 3
    assert info.title == "Sample"
    assert info.author == "PhDF Tests"
    assert not info.is_encrypted


def test_page_size(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        assert doc.page_size(0) == (595, 842)


def test_render_page_scales(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        small = doc.render_page(0, scale=0.5)
        large = doc.render_page(0, scale=2.0)
    assert small.startswith(PNG_MAGIC)
    assert large.startswith(PNG_MAGIC)
    assert len(large) > len(small)


def test_outline_tree(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        outline = doc.outline()
    assert [i.title for i in outline] == ["Chapter 1", "Chapter 2"]
    assert outline[0].page == 0
    assert outline[1].page == 2
    assert [(c.title, c.page, c.level) for c in outline[0].children] == [("Section 1.1", 1, 2)]


def test_page_sizes(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        assert doc.page_sizes() == [(595, 842)] * 3


def test_render_clip_is_smaller(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        full = doc.render_page(0, 1.0)
        clipped = doc.render_page(0, 1.0, clip=(0, 0, 100, 100))
    assert clipped.startswith(PNG_MAGIC)
    assert len(clipped) < len(full)


def test_text_lines(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        lines = doc.text_lines(1)
    assert [s.text for line in lines for s in line.spans] == ["Page 2"]
    x0, y0, x1, y1 = lines[0].bbox
    assert 70 < x0 < x1 and y0 < 72 < y1


def test_search(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        hits = doc.search("page")
        assert [h.page for h in hits] == [0, 1, 2]
        assert len(hits[0].rects) == 1
        assert doc.search("PAGE 3")[0].page == 2
        assert doc.search("   ") == []
        assert sum(len(h.rects) for h in doc.search("page", max_hits=2)) == 2


def test_links(sample_pdf):
    with default_engine().open(sample_pdf) as doc:
        links = doc.links(0)
    kinds = {link.kind: link for link in links}
    assert kinds["goto"].page == 2
    assert kinds["uri"].uri == "https://example.com/"


def test_photo_pages_render_as_jpeg(tmp_path):
    doc = pymupdf.open()
    text_page = doc.new_page()
    text_page.insert_text((72, 72), "Just text")
    photo_page = doc.new_page()
    noise = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 260), 0)
    noise.clear_with(180)
    photo_page.insert_image(photo_page.rect, pixmap=noise)
    path = tmp_path / "mixed.pdf"
    doc.save(path)
    with default_engine().open(path) as d:
        assert d.render_page(0).startswith(PNG_MAGIC)
        assert d.render_page(1).startswith(b"\xff\xd8")  # JPEG
        assert d.render_page(1, clip=(100, 100, 200, 200)).startswith(b"\xff\xd8")
