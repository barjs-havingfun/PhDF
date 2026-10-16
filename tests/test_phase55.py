from pathlib import Path

import pymupdf
import pytest

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import grading


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), path.stem)
    doc.save(path)
    doc.close()


def test_move_note_freetext_and_ink_keep_ids(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    note = api.add_annotation(doc_id, 0, "note", [(100, 100, 120, 120)], "#ffd60a", "hi")
    text = api.add_annotation(doc_id, 0, "freetext", [(100, 200, 250, 230)], "#ff375f", "10/10")
    ink = api.add_annotation(doc_id, 0, "ink", [], "#0a84ff", "", [[(10, 10), (40, 50)]], 4)
    for change in (note, text, ink):
        a = change["annotation"]
        moved = api.move_annotation(doc_id, a["id"], 30, -5)["annotation"]
        assert moved["id"] == a["id"]
        assert moved["rects"][0][0] == pytest.approx(a["rects"][0][0] + 30, abs=0.5)
        assert moved["rects"][0][1] == pytest.approx(a["rects"][0][1] - 5, abs=0.5)
    moved_text = next(a for a in api.annotations(doc_id) if a["kind"] == "freetext")
    assert moved_text["color"] == "#ff375f" and moved_text["contents"] == "10/10"
    moved_ink = next(a for a in api.annotations(doc_id) if a["kind"] == "ink")
    assert moved_ink["strokes"] == [[(40.0, 5.0), (70.0, 45.0)]] and moved_ink["width"] == 4


def test_highlights_cannot_be_moved(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    hl = api.add_annotation(doc_id, 0, "highlight", [(72, 60, 120, 75)], "#ffd60a")["annotation"]
    with pytest.raises(ValueError):
        api.move_annotation(doc_id, hl["id"], 5, 5)


def test_scan_finds_pdfs_in_subfolders_and_names_students(tmp_path):
    root = tmp_path / "Midterm"
    write_pdf(root / "exam10.pdf")
    write_pdf(root / "exam2.pdf")
    write_pdf(root / "Ada Lovelace_123456_assignsubmission_file_" / "answers.pdf")
    write_pdf(root / "graded" / "exam2.pdf")  # earlier marked copy: not an exam
    (root / "notes.txt").write_text("x")
    files = grading.scan(root)
    assert [f["rel"] for f in files] == [
        "Ada Lovelace_123456_assignsubmission_file_/answers.pdf",
        "exam2.pdf",
        "exam10.pdf",
    ]
    assert [f["name"] for f in files] == ["Ada Lovelace", "exam2", "exam10"]
    assert grading.table_path(root) == root / "Midterm.grades.md"


def test_graded_copy_leaves_the_original_alone(tmp_path, monkeypatch):
    root = tmp_path / "Quiz"
    write_pdf(root / "s1" / "quiz.pdf")
    original = (root / "s1" / "quiz.pdf").read_bytes()
    api = make_api(tmp_path, monkeypatch)
    path = api.grading_copy(str(root), "s1/quiz.pdf")
    assert Path(path) == root / "graded" / "s1" / "quiz.pdf"
    doc_id = api.open_document(path)["docId"]
    api.add_annotation(doc_id, 0, "freetext", [(100, 100, 200, 130)], "#ff375f", "7/10")
    api.save_document(doc_id)
    assert (root / "s1" / "quiz.pdf").read_bytes() == original
    assert api.grading_copy(str(root), "s1/quiz.pdf") == path  # the marked copy is reused
    with pytest.raises(ValueError):
        api.grading_copy(str(root), "../outside.pdf")


def test_startup_paths_keep_only_existing_pdfs_and_notes(tmp_path):
    from phdf.app import startup_paths

    pdf, note = tmp_path / "a.PDF", tmp_path / "n.md"
    write_pdf(pdf)
    note.write_text("# n", encoding="utf-8")
    args = [str(pdf), str(note), str(tmp_path / "missing.pdf"), "--flag", str(tmp_path)]
    assert startup_paths(args) == [str(pdf.resolve()), str(note.resolve())]


def test_startup_paths_are_handed_out_once(tmp_path, monkeypatch):
    api = make_api(tmp_path, monkeypatch)
    api._core.startup_paths = ["x.pdf"]
    assert api.startup_paths() == ["x.pdf"]
    assert api.startup_paths() == []


def test_grading_key_ignores_case_only_on_windows(tmp_path, monkeypatch):
    import os

    root = tmp_path / "MixedCase"
    write_pdf(root / "e.pdf")
    key = make_api(tmp_path, monkeypatch).grading_scan(str(root))["key"]
    assert key == os.path.normcase(str(root))
