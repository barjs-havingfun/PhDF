from datetime import date, timedelta

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def test_undo_delete_restores_same_id_and_ink(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    ink = api.add_annotation(doc_id, 0, "ink", [], "#ff375f", "", [[(10, 10), (40, 50)]], 4.5)
    ann = ink["annotation"]
    assert ann["strokes"] == [[(10.0, 10.0), (40.0, 50.0)]] and ann["width"] == 4.5
    api.delete_annotation(doc_id, ann["id"])
    again = api.add_annotation(
        doc_id, 0, "ink", [], ann["color"], "", ann["strokes"], ann["width"], ann["id"]
    )["annotation"]
    assert again["id"] == ann["id"] and again["width"] == 4.5


def test_bookmarks_and_previous_visit(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    first = api.open_document(str(sample_pdf))
    assert first["lastOpened"] is None
    doc_id = first["docId"]
    assert api.set_bookmark(doc_id, 2, "Results")[0] == {
        "page": 2,
        "label": "Results",
        "created": api.bookmarks(doc_id)[0]["created"],
    }
    api.set_bookmark(doc_id, 0)
    assert [b["page"] for b in api.bookmarks(doc_id)] == [0, 2]
    assert [b["page"] for b in api.delete_bookmark(doc_id, 0)] == [2]
    assert api.open_document(str(sample_pdf))["lastOpened"] is not None


def test_reading_stats_and_library(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    api.log_reading(doc_id, 120)
    api.log_reading(doc_id, 60)
    api.log_reading(doc_id, 99999)  # ignored: not a believable chunk
    yesterday = (date.today() - timedelta(1)).isoformat()
    api._core.store.log_reading(doc_id, yesterday, 300)

    stats = api.reading_stats()
    assert stats["today"] == 180 and len(stats["days"]) == 14
    assert stats["days"][-1] == {"day": date.today().isoformat(), "seconds": 180}
    assert stats["streak"] == 2

    [item] = api.library()
    assert item["seconds"] == 480 and item["exists"] and item["pageCount"] == 3
    cover = api.library_cover(doc_id, str(sample_pdf))
    assert cover.startswith("data:image/png;base64,")
    assert api.library_cover("nope", str(tmp_path / "missing.pdf")) is None


def test_window_at_and_send(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    core = api._core

    class FakeWindow:
        x, y, width, height = 1000, 100, 800, 600
        scripts: list = []

        def evaluate_js(self, script):
            self.scripts.append(script)

    other = Api(core, "other")
    other._window = FakeWindow()
    core.windows.update({"main": api, "other": other})
    assert api.window_at(1200, 300) == "other"
    assert api.window_at(800, 200, 1.5) == "other"  # CSS px × scale = device px
    assert api.window_at(10, 10) is None
    assert api.send_to_window("other", str(sample_pdf))
    assert other._open  # took its reference before the tab left the source window
