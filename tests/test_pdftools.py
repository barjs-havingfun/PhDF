import pymupdf
import pytest

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import pdftools


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def texts(path):
    with pymupdf.open(path) as doc:
        return [p.get_text().strip().splitlines()[0] if p.get_text().strip() else "" for p in doc]


def test_edit_undo_and_save_a_copy(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    original = sample_pdf.read_bytes()
    s = api.tools_open(str(sample_pdf))
    n = len(s["pages"])
    s = api.tools_apply(s["id"], {"kind": "rotate", "pages": [0], "by": 90})
    s = api.tools_apply(s["id"], {"kind": "duplicate", "pages": [0]})
    assert len(s["pages"]) == n + 1
    s = api.tools_apply(s["id"], {"kind": "move", "pages": [n], "to": 0})  # last page first
    s = api.tools_apply(s["id"], {"kind": "blank", "at": 1})
    s = api.tools_apply(s["id"], {"kind": "delete", "pages": [1]})  # the blank page again
    assert s["canUndo"] and len(s["pages"]) == n + 1
    s = api.tools_undo(s["id"])
    assert len(s["pages"]) == n + 2  # the blank page is back
    s = api.tools_undo(s["id"])
    out = api.tools_save(s["id"])
    assert out.endswith("_phdfE.pdf") and sample_pdf.read_bytes() == original  # never the original
    with pymupdf.open(out) as doc:
        assert doc.page_count == n + 1 and doc[1].rotation == 90
    assert texts(out)[0] == texts(sample_pdf)[-1]
    assert api.tools_save(s["id"]).endswith("_phdfE_2.pdf")  # never overwrites a copy
    with pytest.raises(ValueError):
        api.tools_apply(s["id"], {"kind": "delete", "pages": list(range(n + 1))})
    api.tools_close(s["id"])


def test_merge_split_and_annotations(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    api.add_annotation(doc_id, 0, "highlight", [(60, 50, 200, 70)], "#ffd60a")
    api.save_document(doc_id)
    s = api.tools_open(str(sample_pdf))
    n = len(s["pages"])
    assert s["annotated"][0] and api.tools_has_annotations(s["id"], [0])
    s = api.tools_apply(s["id"], {"kind": "insert_pdf", "path": str(sample_pdf), "at": n})
    assert len(s["pages"]) == 2 * n
    paths = api.tools_split(
        s["id"], [list(range(n)), list(range(n, 2 * n))], keep_annotations=False
    )
    assert [p.split("_p_")[1] for p in paths] == [f"1-{n}_phdf.pdf", f"{n + 1}-{2 * n}_phdf.pdf"]
    with pymupdf.open(paths[0]) as doc:
        assert doc.page_count == n and doc[0].first_annot is None  # annotations removed


def test_names():
    assert pdftools.pages_label([2, 3, 4, 6]) == "3-5,7"
    assert pdftools.pages_label([0]) == "1"


def test_thumbnails_are_served_like_documents(tmp_path, monkeypatch, sample_pdf):
    from phdf.services.render_server import _PATH

    api = make_api(tmp_path, monkeypatch)
    s = api.tools_open(str(sample_pdf))
    assert _PATH.match(f"/tok/page/{s['id']}/0.png")
    assert api._core.render(s["id"], 0, 0.5, None)[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0")


def test_rejected_operation_keeps_rendering(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    s = api.tools_open(str(sample_pdf))
    with pytest.raises(ValueError):
        api.tools_apply(s["id"], {"kind": "delete", "pages": list(range(100))})
    assert api._core.render(s["id"], 0, 0.5, None)[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0")


def test_merge_undo_does_not_need_the_inserted_file(tmp_path, monkeypatch, sample_pdf):
    import shutil

    other = tmp_path / "other.pdf"
    shutil.copy(sample_pdf, other)
    api = make_api(tmp_path, monkeypatch)
    s = api.tools_open(str(sample_pdf))
    api.tools_apply(s["id"], {"kind": "insert_pdf", "path": str(other), "at": 0})
    api.tools_apply(s["id"], {"kind": "rotate", "pages": [0], "by": 90})
    other.unlink()
    assert len(api.tools_undo(s["id"])["pages"]) == 6


def test_extract_never_overwrites_the_original(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    s = api.tools_open(str(sample_pdf))

    class Dialog:
        def create_file_dialog(self, *args, **kwargs):
            return str(sample_pdf)

    api._window = Dialog()
    with pytest.raises(ValueError):
        api.tools_extract(s["id"], [0])
