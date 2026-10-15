from phdf.db import Store
from phdf.db.store import MIGRATIONS


def test_migrates_to_latest(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert store.schema_version == len(MIGRATIONS)
    store.close()
    # Reopening must not re-run migrations.
    assert Store(tmp_path / "db.sqlite").schema_version == len(MIGRATIONS)


def test_settings_roundtrip(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert store.get_setting("theme", "system") == "system"
    store.set_setting("theme", "dark")
    store.set_setting("panel", {"open": True, "width": 320})
    store.set_setting("theme", "light")
    assert store.get_setting("theme") == "light"
    assert store.get_setting("panel") == {"open": True, "width": 320}


def test_document_position_and_recents(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    first = store.touch_document("a", "/books/a.pdf", "A", 10)
    assert (first["page"], first["scroll"], first["zoom"], first["fit"]) == (0, 0, 1, "width")

    store.save_position("a", page=7, scroll=0.25, zoom=1.5, fit="none")
    store.touch_document("b", "/books/b.pdf", "B", 3)
    # Re-opening from a new path keeps the saved position.
    again = store.touch_document("a", "/moved/a.pdf", "A", 10)
    assert (again["page"], again["scroll"], again["zoom"], again["fit"]) == (7, 0.25, 1.5, "none")
    assert again["path"] == "/moved/a.pdf"

    assert [d["doc_id"] for d in store.recent_documents()] == ["a", "b"]
