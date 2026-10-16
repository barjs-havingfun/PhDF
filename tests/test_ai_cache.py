import os
import time

from phdf.api import Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.services import ai_cache

DAY = 86400


def make(folder, name, size=10, age_days=0.0):
    path = folder / name
    path.write_bytes(b"x" * size)
    t = time.time() - age_days * DAY
    os.utime(path, (t, t))
    return path


def test_keeps_only_the_most_recently_used_revision(tmp_path):
    old = make(tmp_path, "aaaa-p1-5-r7.md", age_days=2)  # higher number, used earlier
    new = make(tmp_path, "aaaa-p1-5-r0.md", age_days=1)
    other_range = make(tmp_path, "aaaa-p6-9-r0.md", age_days=1)
    other_doc = make(tmp_path, "bbbb-p1-1-r3.md", age_days=3)
    stranger = make(tmp_path, "notes.md", age_days=90)  # not ours: never touched
    assert ai_cache.cleanup(tmp_path) == 1
    assert not old.exists()
    assert new.exists() and other_range.exists() and other_doc.exists() and stranger.exists()


def test_drops_unused_files_and_caps_the_size(tmp_path):
    stale = make(tmp_path, "aaaa-p1-1-r0.md", age_days=31)
    a = make(tmp_path, "bbbb-p1-1-r0.md", size=400, age_days=3)
    b = make(tmp_path, "cccc-p1-1-r0.md", size=400, age_days=2)
    c = make(tmp_path, "dddd-p1-1-r0.md", size=400, age_days=1)
    ai_cache.cleanup(tmp_path, max_bytes=900)
    assert not stale.exists() and not a.exists()  # too old; least recently used
    assert b.exists() and c.exists()
    # The newest file stays even when it alone is over the limit.
    ai_cache.cleanup(tmp_path, max_bytes=100)
    assert c.exists() and not b.exists()


def test_ai_context_reuses_touches_and_clears(tmp_path, monkeypatch, sample_pdf):
    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    doc_id = api.open_document(str(sample_pdf))["docId"]
    first = api.ai_context(doc_id, 0, 0)
    t = time.time() - 5 * DAY
    os.utime(first["path"], (t, t))
    again = api.ai_context(doc_id, 0, 0)
    assert again["path"] == first["path"]
    assert os.path.getmtime(again["path"]) > t + DAY  # a hit counts as use
    assert api.ai_cache_info()["files"] == 1
    assert api.ai_cache_clear() == {"files": 0, "bytes": 0}
