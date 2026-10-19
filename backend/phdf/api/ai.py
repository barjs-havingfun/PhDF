"""AI terminal: sessions, equation snips, AI context files and the Markdown cache."""

import os
import shutil
import threading
from pathlib import Path
from typing import Any

from phdf.api.base import ApiBase
from phdf.paths import data_dir
from phdf.services import (
    ai_cache,
    ai_markdown,
    equations,
)
from phdf.services.terminal import AI_PROCESS_NAMES, command_name


class AiApi(ApiBase):
    # --- AI terminal ----------------------------------------------------------------------------

    def term_start(self, cwd: str | None = None, cols: int = 80, rows: int = 24) -> str:
        """Start the user's shell (in `cwd`, e.g. the open PDF's folder). Returns a session id."""
        equations.cleanup(equations.work_dir(cwd), older_than=3600)  # leftovers of earlier runs
        return self._terminals.start(cwd, cols, rows)

    # --- equation → LaTeX (through the AI in the terminal) -----------------------------------

    def equation_snip(
        self,
        doc_id: str,
        page: int,
        rect: list[float],
        folder: str | None = None,
        kind: str = "equation",
    ) -> dict[str, str]:
        """Render a region of a page to a PNG the AI can read (next to where it writes the
        LaTeX, for an equation), in a hidden temp folder inside the terminal's working folder.
        kind "image": Image → AI; the file is also deleted when this window closes."""
        image = kind == "image"
        scale = equations.IMAGE_SCALE if image else equations.SCALE
        with self._core.lock:
            png = self._core.doc(doc_id).render_page(page, scale, tuple(rect))  # type: ignore[arg-type]
        prefix = equations.IMAGE_PREFIX if image else equations.PREFIX
        files = equations.prepare(equations.work_dir(folder), png, prefix)
        if image:
            self._snips.add(files["png"])
        return files

    def equation_result(self, tex_path: str) -> str | None:
        return equations.result(tex_path)

    def equation_cleanup(self, png_path: str) -> None:
        self._snips.discard(png_path)
        equations.remove(png_path)

    def term_read(self, session_id: str, timeout: float = 0.5) -> dict[str, Any]:
        """Long poll: new output (waits up to `timeout`), and whether the shell still runs."""
        session = self._terminals.get(session_id)
        if session is None:
            return {"data": "", "alive": False}
        data, alive = session.read(min(max(timeout, 0.0), 2.0))
        return {"data": data, "alive": alive}

    def term_write(self, session_id: str, data: str) -> None:
        if session := self._terminals.get(session_id):
            session.write(data)

    def term_resize(self, session_id: str, cols: int, rows: int) -> None:
        if session := self._terminals.get(session_id):
            session.resize(cols, rows)

    def term_ai(self, session_id: str) -> str | None:
        """Which AI CLI runs in the terminal (claude, codex, gemini or the default agent)."""
        session = self._terminals.get(session_id)
        if session is None:
            return None
        names = set(AI_PROCESS_NAMES)
        if own := command_name(self._core.store.get_setting("ai.agent") or ""):
            names.add(own)
        return session.running_ai(names)

    def term_close(self, session_id: str) -> None:
        self._terminals.close(session_id)

    def ai_tools(self) -> dict[str, bool]:
        """Which AI command-line tools are installed on this computer (found on PATH)."""
        home = Path.home()
        # A Mac app started from Finder (or a Linux launcher) gets a short PATH, so also look
        # where the installers, Homebrew and npm put these tools.
        extra = [
            home / ".local" / "bin",
            home / ".claude" / "local",
            home / ".npm-global" / "bin",
            home / ".volta" / "bin",
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
        ]
        if appdata := os.environ.get("APPDATA"):
            extra.append(Path(appdata) / "npm")
        found = {}
        for tool in ("claude", "codex", "gemini"):
            found[tool] = bool(shutil.which(tool)) or any(
                (d / name).exists() for d in extra for name in (tool, f"{tool}.exe")
            )
        return found

    def _ai_file(self, doc_id: str, part: str) -> Path:
        """Cache file of the AI's Markdown copy (`part`: "all" or "p<a>-<b>"). Caller holds lock."""
        current = self._core.resolve(doc_id)
        rev = self._core.text_revs[current]
        return ai_cache.folder(data_dir()) / f"{current[:12]}-{part}-r{rev}.md"

    def ai_context(self, doc_id: str, first_page: int, last_page: int) -> dict[str, Any]:
        """Write pages [first_page, last_page] as Markdown (with page markers) for the AI to read;
        returns the file. Cut from the whole-document copy when it is ready, else converted now.
        Cached in PhDF's data folder (not next to the user's PDF); includes unsaved OCR text."""
        with self._core.lock:
            doc = self._core.doc(doc_id)
            count = doc.info().page_count
            first, last = max(0, first_page), min(count - 1, last_page)
            path = self._ai_file(doc_id, f"p{first + 1}-{last + 1}")
            whole = self._ai_file(doc_id, "all")
            data = None if path.exists() or whole.exists() else doc.to_bytes()
        if path.exists():
            ai_cache.touch(path)  # used again: cleaning keeps it longer
        else:
            if data is None:
                text = ai_markdown.cut(whole.read_text(encoding="utf-8"), first, last)
                ai_cache.touch(whole)
            else:
                text = ai_markdown.convert(data, list(range(first, last + 1)))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            ai_cache.cleanup(path.parent)
        return {"path": str(path), "first": first, "last": last, "chars": path.stat().st_size}

    def ai_markdown_status(self, doc_id: str) -> dict[str, Any]:
        """The whole-document Markdown copy: "ready", "working" (done / total pages) or "none"."""
        with self._core.lock:
            whole = self._ai_file(doc_id, "all")
            total = self._core.doc(doc_id).info().page_count
        if whole.exists():
            return {"state": "ready", "done": total, "total": total}
        job = self._core.md_jobs.get(str(whole))
        if job and job["state"] == "working":
            return dict(job)
        if job and job["state"] == "error":
            return dict(job)
        return {"state": "none", "done": 0, "total": total}

    def ai_markdown_prepare(self, doc_id: str) -> dict[str, Any]:
        """Start converting the whole document in the background (once); returns the status."""
        status = self.ai_markdown_status(doc_id)
        if status["state"] in ("ready", "working"):
            return status
        with self._core.lock:
            whole = self._ai_file(doc_id, "all")
            data = self._core.doc(doc_id).to_bytes()
            total = self._core.doc(doc_id).info().page_count
        job = {"state": "working", "done": 0, "total": total}
        self._core.md_jobs[str(whole)] = job

        def work() -> None:
            try:
                text = ai_markdown.convert(
                    data, list(range(total)), lambda done: job.update(done=done)
                )
                whole.parent.mkdir(parents=True, exist_ok=True)
                tmp = whole.with_name(whole.name + ".part")
                tmp.write_text(text, encoding="utf-8")
                tmp.replace(whole)
                job["state"] = "ready"
                ai_cache.cleanup(whole.parent)
            except Exception as e:  # noqa: BLE001 - shown in the menu
                job.update(state="error", error=str(e))

        threading.Thread(target=work, daemon=True).start()
        return dict(job)

    def ai_cache_info(self) -> dict[str, int]:
        return ai_cache.info(ai_cache.folder(data_dir()))

    def ai_cache_clear(self) -> dict[str, int]:
        ai_cache.clear(ai_cache.folder(data_dir()))
        return self.ai_cache_info()
