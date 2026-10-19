import threading
import time

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
    assert core.windows == {}  # right away
    for _ in range(100):  # the rest is cleaned up in the background
        if core.render(doc_id, 0, 0.5, None) is None:
            break
        time.sleep(0.02)
    assert core.render(doc_id, 0, 0.5, None) is None


def test_closing_never_waits_for_a_busy_engine(tmp_path, sample_pdf):
    core = make_core(tmp_path)
    a = Api(core, "a")
    a._window = FakeWindow()
    a.open_document(str(sample_pdf))
    busy = threading.Event()
    done = threading.Event()

    def hold_lock():
        with core.lock:
            busy.set()
            done.wait(5)

    threading.Thread(target=hold_lock, daemon=True).start()
    busy.wait(2)
    start = time.monotonic()
    assert a._on_closing() is False  # the page is asked; the lock isn't needed
    assert time.monotonic() - start < 2
    done.set()


def test_files_from_the_system_wait_for_a_page_then_open_in_a_main_window(tmp_path):
    class FakeWindow:
        def __init__(self):
            self.scripts, self.restored = [], threading.Event()

        def evaluate_js(self, script):
            self.scripts.append(script)

        def restore(self):
            self.restored.set()

    core = make_core(tmp_path)
    detached, main = Api(core, "d1"), Api(core, "main")
    detached._window, main._window = FakeWindow(), FakeWindow()
    core.windows.update({"d1": detached, "main": main})
    core.open_from_system(["/a.pdf"])  # no page has started yet
    assert main.startup_paths() == ["/a.pdf"]
    core.open_from_system(["/b.md"])
    assert main._window.restored.wait(2)
    for _ in range(100):
        if main._window.scripts:
            break
        time.sleep(0.02)
    assert "/b.md" in main._window.scripts[0]
    assert not detached._window.scripts


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

    package = Path(__file__).parents[1] / "backend" / "phdf" / "api"
    source = "\n".join(f.read_text("utf-8") for f in package.glob("*.py"))
    filters = re.findall(r'"([^"()]+ \(\*[^"]*\))"', source)
    assert len(filters) >= 5
    for f in filters:
        parse_file_type(f)  # raises ValueError for an invalid filter


def test_new_build_empties_the_page_cache(tmp_path):
    from phdf.app import drop_stale_page_cache

    index = tmp_path / "index.html"
    index.write_text("v1")
    cache = tmp_path / "webview" / "EBWebView" / "Default" / "Cache"
    cache.mkdir(parents=True)
    drop_stale_page_cache(index, tmp_path / "webview")
    assert not cache.exists()
    cache.mkdir()
    drop_stale_page_cache(index, tmp_path / "webview")  # same build: cache kept
    assert cache.exists()


class FakeWindow:
    def __init__(self):
        self.scripts = []
        self.destroyed = threading.Event()

    def evaluate_js(self, script):
        self.scripts.append(script)

    def destroy(self):
        self.destroyed.set()


def test_identical_copies_are_separate_documents(tmp_path, sample_pdf):
    import shutil

    import pymupdf

    copy = tmp_path / "copy.pdf"
    shutil.copy(sample_pdf, copy)
    original = sample_pdf.read_bytes()
    core = make_core(tmp_path)
    api = Api(core, "main")
    a = api.open_document(str(sample_pdf))["docId"]
    b = api.open_document(str(copy))["docId"]
    assert a != b
    api.add_annotation(b, 0, "note", [[300, 300, 320, 320]], "#34c759", "only in the copy")
    api.save_document(b)
    assert sample_pdf.read_bytes() == original
    with pymupdf.open(copy) as doc:
        assert doc[0].first_annot is not None


def test_changes_reach_other_windows_showing_the_document(tmp_path, sample_pdf):
    core = make_core(tmp_path)
    a, b = Api(core, "a"), Api(core, "b")
    for api in (a, b):
        api._window = FakeWindow()
        core.windows[api._window_id] = api
    doc_id = a.open_document(str(sample_pdf))["docId"]
    b.open_document(str(sample_pdf))
    a.add_annotation(doc_id, 0, "note", [[300, 300, 320, 320]], "#34c759", "hi")
    time.sleep(0.2)  # dispatched on threads
    assert any("phdf:doc-changed" in s and doc_id in s for s in b._window.scripts)
    assert not a._window.scripts


def test_closing_asks_the_page_and_closes_a_silent_one(tmp_path, monkeypatch):
    import phdf.api.windows

    monkeypatch.setattr(phdf.api.windows, "CLOSE_WAIT", 0.1)
    api = Api(make_core(tmp_path), "main")
    api._window = FakeWindow()
    assert api._on_closing() is False  # the page decides
    time.sleep(0.05)
    assert "phdf:close-request" in api._window.scripts[0]
    assert api._window.destroyed.wait(2)  # no answer: closed anyway
    assert api._on_closing() is True

    api = Api(make_core(tmp_path), "main")
    api._window = FakeWindow()
    api._on_closing()
    api.close_ack()  # the page answered and may ask the user: keep the window
    assert not api._window.destroyed.wait(0.4)


def test_image_snips_are_cleaned_up_when_the_window_closes(tmp_path, sample_pdf):
    from pathlib import Path

    api = Api(make_core(tmp_path), "main")
    doc_id = api.open_document(str(sample_pdf))["docId"]
    files = api.equation_snip(doc_id, 0, [0, 0, 200, 200], str(tmp_path), "image")
    png = Path(files["png"])
    assert png.name.startswith("img-") and png.read_bytes()[:4] == b"\x89PNG"
    api._clean_up()
    assert not png.exists()
    assert not png.parent.exists()  # the temp folder goes when empty


def test_linux_build_prefers_the_distros_typelibs(monkeypatch):
    import os
    import sys

    from phdf import app

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(os.path, "isdir", lambda d: d == "/usr/lib64/girepository-1.0")
    monkeypatch.setattr(sys, "_MEIPASS", "/bundle", raising=False)
    monkeypatch.setenv("GI_TYPELIB_PATH", "/bundle/gi_typelibs")
    monkeypatch.setenv("GIO_MODULE_DIR", "/bundle/gio_modules")
    monkeypatch.setenv("GTK_PATH", "/bundle")
    monkeypatch.setenv("PANGO_LIBDIR", "/somewhere/else")  # not the bundle's: kept
    app.system_typelibs()
    assert os.environ["GI_TYPELIB_PATH"].split(os.pathsep) == [
        "/usr/lib64/girepository-1.0",
        "/bundle/gi_typelibs",
    ]
    assert "GIO_MODULE_DIR" not in os.environ and "GTK_PATH" not in os.environ
    assert os.environ["PANGO_LIBDIR"] == "/somewhere/else"
