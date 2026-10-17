"""Password-protected PDFs, saving a page as an image, library remove / relink, About."""

import shutil

import pymupdf

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def locked_pdf(path, password="secret"):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Hidden")
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    return path


def test_encrypted_pdf_asks_for_the_password(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    path = str(locked_pdf(tmp_path / "locked.pdf"))
    assert api.open_document(path) == {"needsPassword": True, "wrong": False}
    assert api.open_document(path, "nope") == {"needsPassword": True, "wrong": True}
    doc = api.open_document(path, "secret")
    assert doc["info"]["page_count"] == 1
    # A second window opens it without asking again (the password is kept for the session).
    other = Api(api._core, "other")
    assert "docId" in other.open_document(path)


def test_encrypted_pdf_keeps_working_after_save(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    path = str(locked_pdf(tmp_path / "locked.pdf"))
    doc_id = api.open_document(path, "secret")["docId"]
    api.add_annotation(doc_id, 0, "highlight", [[72, 60, 140, 76]], "#ffd60a")
    api.save_document(doc_id)
    with pymupdf.open(path) as saved:
        assert saved.needs_pass  # still protected
        assert saved.authenticate("secret")


def test_page_image_png_and_jpg(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    with api._core.lock:
        doc = api._core.doc(doc_id)
        png = doc.page_image(0, 2.0)
        jpg = doc.page_image(0, 2.0, "jpg")
    assert png.startswith(b"\x89PNG") and jpg.startswith(b"\xff\xd8")
    assert pymupdf.Pixmap(png).width == round(595 * 2)


def test_library_remove_and_relink(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    api.close_document(doc_id)
    moved = tmp_path / "moved" / "book.pdf"
    moved.parent.mkdir()
    shutil.move(sample_pdf, moved)
    assert not api.library()[0]["exists"]

    other = tmp_path / "other.pdf"
    locked_pdf(other)
    monkeypatch.setattr(api, "pick_file", lambda kind="document": str(other))
    assert api.library_relink(doc_id) == {"ok": False, "reason": "different"}
    monkeypatch.setattr(api, "pick_file", lambda kind="document": str(moved))
    assert api.library_relink(doc_id)["ok"]
    assert api.library()[0]["exists"] and api.library()[0]["path"] == str(moved)

    api.library_remove(doc_id)
    assert api.library() == []
    assert moved.exists()


def test_about_lists_versions_and_storage(tmp_path, monkeypatch):
    info = make_api(tmp_path, monkeypatch).about()
    assert info["version"] and info["pymupdf"] and info["dataDir"].endswith("data")


def test_start_with_an_empty_window_keeps_one_window(tmp_path):
    from phdf.app import saved_window_ids

    store = Store(tmp_path / "db.sqlite")
    for wid in ("main", "abc12345"):
        store.set_setting(f"session.{wid}", {"panes": [{"paths": ["a.pdf"]}], "focused": 0})
    assert sorted(saved_window_ids(store)) == ["abc12345", "main"]
    store.set_setting("session.restore", False)
    assert saved_window_ids(store) == ["main"]


def test_ui_zoom_without_a_window_is_a_no_op(tmp_path, monkeypatch):
    make_api(tmp_path, monkeypatch).ui_zoom(1.25)


def test_check_update_compares_versions(tmp_path, monkeypatch):
    import io
    import json
    import urllib.request

    api = make_api(tmp_path, monkeypatch)

    def fake(tag):
        body = json.dumps({"tag_name": tag, "html_url": "https://example.org/r"}).encode()
        return lambda request, timeout: io.BytesIO(body)

    monkeypatch.setattr("phdf.api.__version__", "0.7.0")
    monkeypatch.setattr(urllib.request, "urlopen", fake("v0.10.0"))
    assert api.check_update()["newer"] is True  # 10 > 7, not text order
    monkeypatch.setattr(urllib.request, "urlopen", fake("v0.7.0"))
    assert api.check_update()["newer"] is False

    def offline(request, timeout):
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    assert api.check_update() == {"ok": False, "current": "0.7.0"}
