"""Regression checks for the 2026-10-21 code review (R1-R10) and its follow-ups."""

import threading

import pymupdf
import pytest

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.engine import mupdf as engine_mupdf


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def test_r1_ids_starting_with_x_survive_recreation(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    stroke = [[(100, 100), (150, 150)]]
    kept = api.add_annotation(doc_id, 0, "ink", [], "#ff0000", strokes=stroke, annot_id="xabc1")
    assert kept["annotation"]["id"] == "xabc1"  # a PhDF-style id, not a fallback
    fresh = api.add_annotation(doc_id, 0, "ink", [], "#ff0000", strokes=stroke, annot_id="x42")
    assert fresh["annotation"]["id"] != "x42"  # "x" + xref: an unnamed annotation's stand-in
    assert not any(
        engine_mupdf._FALLBACK_ID.fullmatch(engine_mupdf.new_annotation_id()) for _ in range(3000)
    )
    assert not any(engine_mupdf.new_annotation_id().startswith("x") for _ in range(3000))


def test_r2_revert_keeps_a_protected_pdf_open(tmp_path, monkeypatch, sample_pdf):
    locked = tmp_path / "locked.pdf"
    with pymupdf.open(sample_pdf) as doc:
        doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="owner")
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(locked), "pw")["docId"]
    api.add_annotation(doc_id, 0, "note", [[300, 300, 320, 320]], "#34c759", "hi")
    api.revert_document(doc_id)
    assert api.annotations(doc_id) == []
    api.text_layer(doc_id, 0)  # still open
    api._core.passwords[doc_id] = "wrong"  # a failed reopen leaves the document as it was
    api.add_annotation(doc_id, 0, "note", [[300, 300, 320, 320]], "#34c759", "kept")
    from phdf.engine import PasswordRequired

    with pytest.raises(PasswordRequired):
        api.revert_document(doc_id)
    assert len(api.annotations(doc_id)) == 1


def test_r5_concurrent_note_saves_never_collide(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    note = tmp_path / "n.md"
    errors = []

    def save(text):
        try:
            for _ in range(30):
                api.write_text(str(note), text)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=save, args=(t,)) for t in ("one", "two", "three")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert note.read_text(encoding="utf-8") in ("one", "two", "three")
    assert [p.name for p in tmp_path.iterdir() if "phdf-tmp" in p.name] == []


def test_r5_a_newer_file_is_not_overwritten(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    note = tmp_path / "n.md"
    seen = api.write_text(str(note), "first")
    import os

    os.utime(note, (seen + 5, seen + 5))  # written elsewhere meanwhile
    with pytest.raises(ValueError, match="PHDF_CHANGED_ELSEWHERE"):
        api.write_text(str(note), "stale", seen)
    assert note.read_text(encoding="utf-8") == "first"
    api.write_text(str(note), "forced")  # Keep Mine: no expected time
    assert note.read_text(encoding="utf-8") == "forced"


def test_r3_reopening_a_saved_open_file_takes_no_second_reference(
    tmp_path, monkeypatch, sample_pdf
):
    api = make_api(tmp_path, monkeypatch)
    core = api._core
    first = api.open_document(str(sample_pdf))["docId"]
    api.add_annotation(first, 0, "note", [[300, 300, 320, 320]], "#34c759", "hi")
    api.save_document(first)
    again = api.open_document(str(sample_pdf))["docId"]
    assert core.resolve(again) == core.resolve(first)
    assert core._refs[core.resolve(first)] == 1
    api.close_document(first)
    assert core.render(first, 0, 0.5, None) is None  # really closed


def _plain_convert(data, pages, progress=None):
    """Stand-in for the Markdown converter: the pages' plain text."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(doc[p].get_text() for p in pages)


def test_r6_discarded_ocr_text_never_reaches_the_ai(tmp_path, monkeypatch, sample_pdf):
    from pathlib import Path

    import phdf.api.ai
    import phdf.api.ocr_export
    from phdf.services.ocr import OcrWord

    monkeypatch.setattr(phdf.api.ai.ai_markdown, "convert", _plain_convert)
    word = [OcrWord(text="Zebrafish", bbox=(300, 400, 380, 420))]
    monkeypatch.setattr(phdf.api.ocr_export.ocr, "recognize", lambda *a: word)
    monkeypatch.setattr(phdf.api.ocr_export.ocr, "unicode_font", lambda: None)
    api = make_api(tmp_path, monkeypatch)
    for _ in range(2):  # the second round: a cache from the first must not match either
        doc_id = api.open_document(str(sample_pdf))["docId"]
        api.ocr_page(doc_id, 0, ["eng"])
        ocr_text = Path(api.ai_context(doc_id, 0, 0)["path"]).read_text(encoding="utf-8")
        assert "Zebrafish" in ocr_text
        api.close_document(doc_id)  # closed without saving: the OCR text is gone
        doc_id = api.open_document(str(sample_pdf))["docId"]
        disk_text = Path(api.ai_context(doc_id, 0, 0)["path"]).read_text(encoding="utf-8")
        assert "Zebrafish" not in disk_text
        api.close_document(doc_id)


def test_r7_epub_text_size_changes_the_ai_pages(tmp_path, monkeypatch):
    from pathlib import Path

    from test_epub import make_epub

    api = make_api(tmp_path, monkeypatch)
    book = make_epub(tmp_path / "tiny.epub")
    doc_id = api.open_document(str(book))["docId"]
    before = Path(api.ai_context(doc_id, 0, 0)["path"])
    api.epub_text_size(24)
    after = Path(api.ai_context(doc_id, 0, 0)["path"])
    assert before != after
    first_page = "".join(s["text"] for line in api.text_layer(doc_id, 0) for s in line["spans"])
    assert first_page.split()[-1] in after.read_text(encoding="utf-8")


def test_r4_extracting_separate_pages_keeps_links_between_them(tmp_path, sample_pdf):
    from phdf.services.pdftools import ToolsSession

    session = ToolsSession(str(sample_pdf))  # page 1 links to page 3 (conftest)
    try:
        part = session._part([0, 2])
        links = [link for link in part[0].get_links() if link["kind"] == pymupdf.LINK_GOTO]
        assert [link["page"] for link in links] == [1]  # page 3 is now page 2
        part = session._part([0, 1])  # target left out: no link to a missing page
        assert not [link for link in part[0].get_links() if link["kind"] == pymupdf.LINK_GOTO]
    finally:
        session.close()


def test_r10_a_moved_identical_copy_can_be_relinked(tmp_path, monkeypatch, sample_pdf):
    import shutil

    api = make_api(tmp_path, monkeypatch)
    copy = tmp_path / "copy.pdf"
    shutil.copy(sample_pdf, copy)
    api.open_document(str(sample_pdf))
    copy_id = api.open_document(str(copy))["docId"]  # an id of its own (identical content)
    api.close_document(copy_id)
    moved = copy.rename(tmp_path / "moved.pdf")
    monkeypatch.setattr(api, "pick_file", lambda kind="document": str(moved))
    assert api.library_relink(copy_id) == {"ok": True, "path": str(moved)}
    other = tmp_path / "other.pdf"
    with pymupdf.open(sample_pdf) as doc:
        doc[0].insert_text((72, 300), "changed")
        doc.save(other)
    monkeypatch.setattr(api, "pick_file", lambda kind="document": str(other))
    assert api.library_relink(copy_id)["reason"] == "different"


def test_open_in_vault_uses_the_markdown_app(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    opened = []
    monkeypatch.setattr(api, "open_in_default_app", lambda path: opened.append(path))
    api.open_in_vault(str(tmp_path / "a.md"))
    assert opened == [str(tmp_path / "a.md")]


def test_vault_settings_move_to_their_new_names(tmp_path):
    from phdf.app import migrate_settings
    from phdf.db import Store

    store = Store(tmp_path / "db.sqlite")
    store.set_setting("obsidian.vault", "/notes")
    store.set_setting("obsidian.folder", "Books")
    migrate_settings(store)
    assert store.get_setting("vault.path") == "/notes"
    assert store.get_setting("vault.folder") == "Books"
    assert store.get_setting("obsidian.vault") is None


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_interface_size_reaches_the_web_view_on_mac_and_linux(platform, monkeypatch):
    """pywebview 6: window.native is the bare NSWindow / Gtk.Window there; the web view lives on
    BrowserView.instances[window.uid] (it used to be looked up on window.native: no zoom)."""
    import sys
    import types

    from phdf.services import uizoom

    calls = []

    class View:  # WKWebView / WebKit2.WebView stand-in
        def setPageZoom_(self, factor):
            calls.append(factor)

        def set_zoom_level(self, factor):
            calls.append(factor)

    class Window:
        uid = "master"
        native = object()  # no .webview, like the real NSWindow / Gtk.Window

    browser = types.SimpleNamespace(instances={"master": types.SimpleNamespace(webview=View())})
    monkeypatch.setattr(sys, "platform", platform)
    if platform == "darwin":
        monkeypatch.setitem(
            sys.modules, "webview.platforms.cocoa", types.SimpleNamespace(BrowserView=browser)
        )
        helper = types.SimpleNamespace(callAfter=lambda fn, *args: fn(*args))
        monkeypatch.setitem(sys.modules, "PyObjCTools", types.SimpleNamespace(AppHelper=helper))
        monkeypatch.setitem(sys.modules, "PyObjCTools.AppHelper", helper)
    else:
        monkeypatch.setitem(
            sys.modules, "webview.platforms.gtk", types.SimpleNamespace(BrowserView=browser)
        )
        glib = types.SimpleNamespace(idle_add=lambda fn, *args: fn(*args))
        monkeypatch.setitem(sys.modules, "gi.repository", types.SimpleNamespace(GLib=glib))
    uizoom.set_zoom(Window(), 1.25)
    assert calls == [1.25]
