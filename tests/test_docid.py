import shutil

from phdf.docid import document_id


def test_same_content_same_id_after_move(sample_pdf, tmp_path):
    moved = tmp_path / "renamed" / "other-name.pdf"
    moved.parent.mkdir()
    shutil.copy(sample_pdf, moved)
    assert document_id(sample_pdf) == document_id(moved)


def test_different_content_different_id(sample_pdf, tmp_path):
    other = tmp_path / "other.pdf"
    other.write_bytes(sample_pdf.read_bytes() + b"\n% changed")
    assert document_id(sample_pdf) != document_id(other)
