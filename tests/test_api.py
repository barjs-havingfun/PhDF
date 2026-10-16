from phdf.api import SESSION_PREFIX, Api, Core
from phdf.app import saved_window_ids
from phdf.db import Store
from phdf.engine import default_engine


def make_core(tmp_path):
    return Core(default_engine(), Store(tmp_path / "db.sqlite"))


def test_documents_are_shared_and_refcounted_across_windows(tmp_path, sample_pdf):
    core = make_core(tmp_path)
    a, b = Api(core, "a"), Api(core, "b")
    doc_id = a.open_document(str(sample_pdf))["docId"]
    a.open_document(str(sample_pdf))  # reopening in the same window takes no extra reference
    b.open_document(str(sample_pdf))

    a.close_document(doc_id)
    assert core.render(doc_id, 0, 0.5, None) is not None  # still open for window b
    b.close_document(doc_id)
    assert core.render(doc_id, 0, 0.5, None) is None


def test_closing_a_window_releases_its_documents(tmp_path, sample_pdf):
    core = make_core(tmp_path)
    a = Api(core, "a")
    core.windows["a"] = a
    doc_id = a.open_document(str(sample_pdf))["docId"]
    a._on_closed()
    assert core.render(doc_id, 0, 0.5, None) is None
    assert core.windows == {}


def test_open_window_writes_its_session(tmp_path):
    core = make_core(tmp_path)
    created = []
    core.create_window = lambda wid, x, y: created.append((wid, x, y))
    wid = Api(core, "main").open_window(["/books/a.pdf"], 10, 20)
    assert created == [(wid, 10, 20)]
    session = core.store.get_setting(SESSION_PREFIX + wid)
    assert session["panes"][0]["paths"] == ["/books/a.pdf"]


def test_only_the_last_window_keeps_its_session(tmp_path):
    core = make_core(tmp_path)
    for wid in ("main", "x"):
        core.windows[wid] = Api(core, wid)
        core.store.set_setting(SESSION_PREFIX + wid, {"panes": []})
    core.window_closed("x")
    core.window_closed("main")
    assert list(core.store.settings_with_prefix(SESSION_PREFIX)) == ["session.main"]


def test_saved_window_ids_migrates_legacy_session(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert saved_window_ids(store) == ["main"]
    store.set_setting("session", {"paths": ["/a.pdf"], "active": 0})
    assert saved_window_ids(store) == ["main"]
    assert store.get_setting("session") is None
    assert store.get_setting("session.main") == {"paths": ["/a.pdf"], "active": 0}
    store.set_setting("session.abc", {})
    assert saved_window_ids(store) == ["abc", "main"]


def test_rename_note_keeps_it_with_its_pdf(tmp_path, monkeypatch, sample_pdf):
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine

    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    note = sample_pdf.with_suffix(".md")
    note.write_text("# hi", encoding="utf-8")
    new = api.rename_file(str(note), "  My notes ")
    assert new == str(note.with_name("My notes.md"))
    assert note.with_name("My notes.md").read_text(encoding="utf-8") == "# hi"
    assert api.md_for_pdf(str(sample_pdf))["path"] == new  # still the PDF's note
    other = note.with_name("Other.md")
    other.write_text("x", encoding="utf-8")
    import pytest

    with pytest.raises(ValueError):
        api.rename_file(new, "Other")
    with pytest.raises(ValueError):
        api.rename_file(new, "bad/name")


def test_file_dialog_filters_are_valid_for_pywebview():
    """pywebview rejects filter names with characters like "-" (the Open dialog then fails)."""
    import re
    from pathlib import Path

    from webview.util import parse_file_type

    source = (Path(__file__).parents[1] / "backend" / "phdf" / "api.py").read_text("utf-8")
    filters = re.findall(r'"([^"()]+ \(\*[^"]*\))"', source)
    assert len(filters) >= 5
    for f in filters:
        parse_file_type(f)  # raises ValueError for an invalid filter
