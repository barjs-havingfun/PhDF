import pymupdf

from phdf import selftest
from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine


def test_self_test_checks_documents_and_the_terminal(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    assert "comic" in selftest.check_documents(tmp_path)
    selftest.check_terminal(tmp_path)


def test_real_worker_processes_convert_pages(tmp_path, monkeypatch):
    from phdf.services import workers

    monkeypatch.setattr(workers, "inline", False)  # conftest runs them inline elsewhere
    assert "worker" in selftest.check_workers(tmp_path)


def test_comics_open_in_natural_order_and_keep_no_annotations(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    cbz = selftest.make_cbz(tmp_path / "c.cbz", ((600, 900), (1200, 900), (300, 900)))
    doc = api.open_document(str(cbz))
    assert doc["info"]["kind"] == "comic" and not doc["info"]["reflowable"]
    assert [round(w) for w, _ in doc["pageSizes"]] == [450, 900, 225]  # page 2, 10, 11
    assert api.annotations(doc["docId"]) == []
    with pytest.raises(ValueError):
        api.add_annotation(doc["docId"], 0, "highlight", [[0, 0, 50, 50]], "#ffd60a")
    with pymupdf.open(cbz) as again:
        assert again.page_count == 3


def test_a_long_comic_opens_with_guessed_sizes_then_measures_them(tmp_path, monkeypatch):
    import threading
    import time

    from phdf.engine import mupdf

    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    import phdf.api.documents

    monkeypatch.setattr(mupdf, "QUICK_SIZES_FROM", 1)
    monkeypatch.setattr(phdf.api.documents, "MEASURE_AFTER", 0)
    core = Core(default_engine(), Store(tmp_path / "db.sqlite"))
    api = Api(core, "main")
    told = threading.Event()
    sent = {}

    def tell(doc_id, event, detail, skip):
        sent.update(detail, event=event)
        told.set()

    core.tell_windows = tell
    cbz = selftest.make_cbz(tmp_path / "c.cbz", ((600, 900), (1200, 900), (300, 900)))
    doc = api.open_document(str(cbz))
    assert [round(w) for w, _ in doc["pageSizes"]] == [450, 450, 450]  # all like page 1
    assert told.wait(5)
    assert sent["event"] == "doc-sizes"
    assert [round(w) for w, _ in sent["pageSizes"]] == [450, 900, 225]
    time.sleep(0.05)
    again = api.open_document(str(cbz))  # measured once: right from now on
    assert [round(w) for w, _ in again["pageSizes"]] == [450, 900, 225]


def test_comic_pages_go_out_as_their_original_picture(tmp_path):
    from phdf.engine import default_engine

    cbz = selftest.make_cbz(tmp_path / "c.cbz", ((600, 900),))
    with default_engine().open(cbz) as doc:  # page: 450 x 675 pt (96 dpi)
        original = doc.render_page(0, 1.0)
        assert original[:3] == b"\xff\xd8\xff" and len(original) > 0
        thumb = doc.render_page(0, 0.2)  # much smaller than the picture: scaled down
        assert thumb != original and len(thumb) < len(original)
        assert doc.render_page(0, 1.0, (0, 0, 100, 100)) != original  # a clip is drawn
