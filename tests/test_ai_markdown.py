import time
from pathlib import Path

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import ai_markdown


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def wait_ready(api, doc_id):
    for _ in range(200):
        if api.ai_markdown_status(doc_id)["state"] == "ready":
            return
        time.sleep(0.05)
    raise AssertionError(api.ai_markdown_status(doc_id))


def test_pages_have_markers_and_can_be_cut():
    text = "\n".join(f"<!-- PDF page {n} -->\n\nPage {n} text\n" for n in (1, 2, 3))
    part = ai_markdown.cut(text, 1, 2)
    assert "<!-- PDF page 2 -->" in part and "Page 3 text" in part and "Page 1" not in part


def test_whole_document_in_background_serves_ranges(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    assert api.ai_markdown_status(doc_id)["state"] == "none"
    assert api.ai_markdown_prepare(doc_id)["state"] in ("working", "ready")
    wait_ready(api, doc_id)
    ctx = api.ai_context(doc_id, 1, 1)
    text = Path(ctx["path"]).read_text(encoding="utf-8")
    assert text.startswith("<!-- PDF page 2 -->") and "Page 2" in text and "Page 3" not in text


def test_highlights_and_saving_keep_the_copy(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    api.ai_markdown_prepare(doc_id)
    wait_ready(api, doc_id)
    api.add_annotation(doc_id, 0, "highlight", [(60, 50, 200, 70)], "#ffd60a")
    assert api.ai_markdown_status(doc_id)["state"] == "ready"  # text unchanged: still valid
    api.save_document(doc_id)  # new content hash, same text: the copy follows
    assert api.ai_markdown_status(doc_id)["state"] == "ready"
