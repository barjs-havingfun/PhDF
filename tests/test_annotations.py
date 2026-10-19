import pymupdf
import pytest

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine


@pytest.fixture
def text_pdf(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Attention is all you need", fontsize=12)
    path = tmp_path / "paper.pdf"
    doc.save(path)
    doc.close()
    return path


def word_rect(path, word):
    with pymupdf.open(path) as d:
        return tuple(d[0].search_for(word)[0])


def test_add_update_delete_roundtrip(text_pdf):
    rect = word_rect(text_pdf, "Attention")
    with default_engine().open(text_pdf) as doc:
        assert not doc.dirty
        hl = doc.add_annotation(0, "highlight", [rect], "#ffd60a", "key idea")
        assert hl.kind == "highlight" and hl.quote == "Attention" and hl.contents == "key idea"
        assert hl.color == "#ffd60a" and len(hl.id) == 5
        assert doc.dirty

        note = doc.add_annotation(0, "note", [(300, 300, 320, 320)], "#34c759", "sticky")
        updated = doc.update_annotation(hl.id, color="#ff375f", contents="changed")
        assert (updated.color, updated.contents) == ("#ff375f", "changed")

        assert {a.id for a in doc.annotations()} == {hl.id, note.id}
        assert doc.delete_annotation(note.id) == 0
        assert [a.id for a in doc.annotations()] == [hl.id]
        doc.save()
        assert not doc.dirty

    with default_engine().open(text_pdf) as doc:  # persisted, same id
        [again] = doc.annotations()
        assert (again.id, again.contents, again.quote) == (hl.id, "changed", "Attention")


def test_freetext_color(text_pdf):
    with default_engine().open(text_pdf) as doc:
        ft = doc.add_annotation(0, "freetext", [(72, 200, 300, 230)], "#ff0000", "hello")
        assert ft.color == "#ff0000"
        assert doc.update_annotation(ft.id, contents="bye").color == "#ff0000"


def test_unknown_id(text_pdf):
    with default_engine().open(text_pdf) as doc, pytest.raises(KeyError):
        doc.delete_annotation("nope")


def test_save_keeps_old_id_working(tmp_path, text_pdf):
    core = Core(default_engine(), Store(tmp_path / "db.sqlite"))
    api = Api(core, "main")
    old = api.open_document(str(text_pdf))["docId"]
    api.save_position(old, 0, 0.5, 1.0, "width")

    result = api.add_annotation(old, 0, "highlight", [word_rect(text_pdf, "all")], "#ffd60a")
    assert result["dirty"] and result["revs"] == {0: 1}
    assert api.save_document(old)["dirty"] is False

    # The file's hash changed, but the old id still resolves everywhere.
    assert core.resolve(old) != old
    assert len(api.annotations(old)) == 1
    assert core.render(old, 0, 0.5, None) is not None
    rows = core.store.recent_documents()
    assert [r["doc_id"] for r in rows] == [core.resolve(old)] and rows[0]["scroll"] == 0.5

    api.close_document(old)
    assert core.render(old, 0, 0.5, None) is None


def test_revert_discards_changes(tmp_path, text_pdf):
    core = Core(default_engine(), Store(tmp_path / "db.sqlite"))
    api = Api(core, "main")
    doc_id = api.open_document(str(text_pdf))["docId"]
    api.add_annotation(doc_id, 0, "underline", [word_rect(text_pdf, "need")], "#0a84ff")
    assert api.revert_document(doc_id)["dirty"] is False
    assert api.annotations(doc_id) == []


def test_markdown_files(tmp_path, text_pdf):
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    md = api.md_for_pdf(str(text_pdf))
    assert md == {"path": str(text_pdf.with_suffix(".md")), "exists": False, "linked": False}
    assert api.read_text(md["path"])["exists"] is False

    mtime = api.write_text(md["path"], "# Notes\n⎘ phdf · p.1 · #abcde\n")
    assert api.file_mtime(md["path"]) == mtime
    assert api.read_text(md["path"])["text"].startswith("# Notes\n⎘")

    assert api.pdf_for_md(md["path"]) == str(text_pdf)  # sibling with the same name

    other = tmp_path / "elsewhere" / "mine.md"
    api.link_md(str(text_pdf), str(other))
    assert api.md_for_pdf(str(text_pdf)) == {"path": str(other), "exists": False, "linked": True}
    assert api.pdf_for_md(str(other)) == str(text_pdf)


def test_reopen_after_discard_gets_fresh_page_images(tmp_path, text_pdf):
    core = Core(default_engine(), Store(tmp_path / "db.sqlite"))
    api = Api(core, "main")
    doc_id = api.open_document(str(text_pdf))["docId"]
    api.add_annotation(doc_id, 0, "highlight", [word_rect(text_pdf, "all")], "#ffd60a")
    api.close_document(doc_id)  # "Don't Save"

    reopened = api.open_document(str(text_pdf))
    assert reopened["dirty"] is False
    assert reopened["revs"] == {0: 2}  # new URL: the cached image still had the highlight
    assert api.annotations(doc_id) == []


def test_closing_window_with_unsaved_changes_is_held(tmp_path, text_pdf):
    class Window:
        def evaluate_js(self, script):
            pass

        def destroy(self):
            pass

    core = Core(default_engine(), Store(tmp_path / "db.sqlite"))
    api = Api(core, "main")
    assert api._on_closing() is True  # no window (yet): nothing to ask
    api._window = Window()
    doc_id = api.open_document(str(text_pdf))["docId"]
    api.add_annotation(doc_id, 0, "underline", [word_rect(text_pdf, "need")], "#0a84ff")
    assert api._on_closing() is False  # the page asks Save / Don't Save / Cancel
    api.close_window()  # user answered
    assert api._on_closing() is True
