import sys
import time
from pathlib import Path

import pytest

from phdf.services.terminal import Terminals


@pytest.mark.skipif(sys.platform != "win32", reason="checks PowerShell output")
def test_shell_runs_commands_in_cwd(tmp_path):
    terms = Terminals()
    sid = terms.start(str(tmp_path), 100, 30)
    session = terms.get(sid)
    out = ""
    deadline = time.time() + 15
    session.write("Write-Output ('PH' + 'DF-' + (Get-Location).Path)\r\n")
    while time.time() < deadline and f"PHDF-{tmp_path}" not in out:
        out += session.read(0.5)[0]
    assert f"PHDF-{tmp_path}" in out
    assert session.running_ai() is None
    session.resize(120, 40)
    terms.close(sid)
    assert terms.get(sid) is None


def test_unknown_session_is_harmless(tmp_path):
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine

    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    assert api.term_read("nope", 0) == {"data": "", "alive": False}
    api.term_write("nope", "x")
    api.term_resize("nope", 10, 10)
    assert api.term_ai("nope") is None


def test_ai_context_writes_requested_pages(tmp_path, sample_pdf, monkeypatch):
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine

    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    doc_id = api.open_document(str(sample_pdf))["docId"]
    ctx = api.ai_context(doc_id, 1, 2)
    text = Path(ctx["path"]).read_text(encoding="utf-8")
    assert (ctx["first"], ctx["last"]) == (1, 2)
    assert "Page 2" in text and "Page 3" in text and "Page 1" not in text
    assert api.ai_context(doc_id, 1, 2)["path"] == ctx["path"]  # cached
    assert set(api.ai_tools()) == {"claude", "codex", "gemini"}
    assert api.app_info()["platform"] in {"windows", "macos", "linux"}


def test_command_name_of_an_agent():
    from phdf.services.terminal import command_name

    assert command_name("claude") == "claude"
    assert command_name("  aider --model sonnet ") == "aider"
    assert command_name(r'"C:\Program Files\Gemini\gemini.exe" --yolo') == "gemini"
    assert command_name("/usr/local/bin/Codex") == "codex"
    assert command_name("") is None


def test_term_ai_also_looks_for_the_default_agent(tmp_path, monkeypatch):
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine
    from phdf.services.terminal import Session

    seen = []
    monkeypatch.setattr(Session, "__init__", lambda self, *a: setattr(self, "id", "s1"))
    monkeypatch.setattr(Session, "running_ai", lambda self, names: seen.append(names))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    sid = api._terminals.start(None, 80, 24)
    api.term_ai(sid)
    api.set_setting("ai.agent", "aider --model x")
    api.term_ai(sid)
    known = {"claude", "codex", "gemini"}
    assert seen == [known, known | {"aider"}]
