import os
import time
from pathlib import Path

import pymupdf

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import equations


def make_api(tmp_path, monkeypatch):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    return Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")


def test_text_box_font_size_bold_survive_save(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    a = api.add_annotation(
        doc_id, 0, "freetext", [(100, 100, 300, 140)], "#ff375f", "Öğrenci şık 7/10",
        font="serif", font_size=20, bold=True,
    )["annotation"]  # fmt: skip
    assert (a["font"], a["font_size"], a["bold"], a["color"]) == ("serif", 20, True, "#ff375f")
    assert a["contents"] == "Öğrenci şık 7/10"
    api.save_document(doc_id)
    with pymupdf.open(sample_pdf) as d:
        assert "Öğrenci" in d[0].get_text()  # drawn with the Turkish letters
    again = next(x for x in api.annotations(doc_id) if x["kind"] == "freetext")
    assert (again["font"], again["font_size"], again["bold"]) == ("serif", 20, True)


def test_restyle_existing_box_keeps_id_text_and_color(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    a = api.add_annotation(doc_id, 0, "freetext", [(100, 100, 200, 120)], "#0a84ff", "a < b & c")[
        "annotation"
    ]
    assert (a["font"], a["font_size"], a["bold"]) == ("sans", 12, False)
    b = api.update_annotation(
        doc_id, a["id"], font="mono", font_size=28, bold=True, rect=[100, 100, 320, 140]
    )["annotation"]
    assert b["id"] == a["id"] and b["contents"] == "a < b & c" and b["color"] == "#0a84ff"
    assert (b["font"], b["font_size"], b["bold"]) == ("mono", 28, True)
    assert b["rects"][0][2] == 320
    c = api.update_annotation(doc_id, a["id"], color="#34c759")["annotation"]
    assert (c["font"], c["font_size"], c["bold"], c["color"]) == ("mono", 28, True, "#34c759")
    moved = api.move_annotation(doc_id, a["id"], 10, 5)["annotation"]
    assert moved["rects"][0][:2] == (110, 105) and moved["font"] == "mono"


def test_plain_free_text_from_older_versions_is_read(tmp_path, monkeypatch):
    doc = pymupdf.open()
    page = doc.new_page()
    page.add_freetext_annot(
        pymupdf.Rect(50, 50, 200, 80), "old", fontsize=16, fontname="Cour", text_color=(1, 0, 0)
    )
    path = tmp_path / "old.pdf"
    doc.save(path)
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(path))["docId"]
    a = api.annotations(doc_id)[0]
    assert (a["font"], a["font_size"], a["bold"], a["color"]) == ("mono", 16, False, "#ff0000")


def test_equation_files_live_in_a_temp_folder_and_are_removed(tmp_path, monkeypatch, sample_pdf):
    api = make_api(tmp_path, monkeypatch)
    doc_id = api.open_document(str(sample_pdf))["docId"]
    job = api.equation_snip(doc_id, 0, [60, 50, 200, 90], str(tmp_path))
    png, tex = Path(job["png"]), Path(job["tex"])
    assert png.parent == tmp_path / ".phdf-tmp" and png.read_bytes()[:4] == b"\x89PNG"
    assert api.equation_result(job["tex"]) is None  # the AI has not answered yet
    tex.write_text("  \\frac{a}{b}\n", encoding="utf-8")
    assert api.equation_result(job["tex"]) == "\\frac{a}{b}"
    api.equation_cleanup(job["png"])
    assert not png.exists() and not tex.exists() and not png.parent.exists()


def test_equation_cleanup_only_touches_its_own_files(tmp_path):
    keep = tmp_path / "notes.md"
    keep.write_text("x")
    equations.remove(str(keep))
    assert keep.exists()
    folder = tmp_path / ".phdf-tmp"
    folder.mkdir()
    old, new = folder / "eq-old.png", folder / "eq-new.png"
    old.write_bytes(b"1")
    new.write_bytes(b"2")
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    equations.cleanup(folder, older_than=3600)
    assert not old.exists() and new.exists()
