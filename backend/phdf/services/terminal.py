"""Terminal sessions for the AI panel: the user's shell in a pseudo-terminal.

Windows uses ConPTY through pywinpty, other systems ptyprocess. A reader thread collects output;
the page fetches it with a long poll (`read` waits up to `timeout` for new output), which keeps
the JS bridge simple and still feels instant.
"""

import contextlib
import os
import shutil
import sys
import threading
import uuid
from pathlib import Path

import psutil

AI_PROCESS_NAMES = {"claude", "codex"}  # matched against child process names (no extension)
MAX_BUFFER = 1 << 20  # unread output kept if the page stops polling (1 MB)


def default_shell() -> list[str]:
    if sys.platform == "win32":
        exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
        return [exe, "-NoLogo"]
    return [os.environ.get("SHELL") or "/bin/bash", "-l"]


class Session:
    def __init__(self, cwd: str | None, cols: int, rows: int) -> None:
        self.id = uuid.uuid4().hex[:12]
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor"}
        workdir = cwd if cwd and Path(cwd).is_dir() else str(Path.home())
        argv = default_shell()
        if sys.platform == "win32":
            from winpty import PtyProcess

            self._proc = PtyProcess.spawn(argv, cwd=workdir, env=env, dimensions=(rows, cols))
        else:
            from ptyprocess import PtyProcessUnicode

            self._proc = PtyProcessUnicode.spawn(
                argv, cwd=workdir, env=env, dimensions=(rows, cols)
            )
        self._buffer: list[str] = []
        self._size = 0
        self._cond = threading.Condition()
        self._alive = True
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        while True:
            try:
                chunk = self._proc.read(4096)
            except (EOFError, OSError):
                break
            if not chunk:
                if not self._proc.isalive():
                    break
                continue
            with self._cond:
                self._buffer.append(chunk)
                self._size += len(chunk)
                while self._size > MAX_BUFFER and len(self._buffer) > 1:
                    self._size -= len(self._buffer.pop(0))
                self._cond.notify_all()
        with self._cond:
            self._alive = False
            self._cond.notify_all()

    def read(self, timeout: float) -> tuple[str, bool]:
        with self._cond:
            if not self._buffer and self._alive:
                self._cond.wait(timeout)
            data = "".join(self._buffer)
            self._buffer.clear()
            self._size = 0
            return data, self._alive

    def write(self, data: str) -> None:
        if self._alive:
            self._proc.write(data)

    def resize(self, cols: int, rows: int) -> None:
        if self._alive and cols > 0 and rows > 0:
            self._proc.setwinsize(rows, cols)

    def running_ai(self) -> str | None:
        """'claude' / 'codex' if one of them runs inside this shell."""
        try:
            for child in psutil.Process(self._proc.pid).children(recursive=True):
                name = Path(child.name()).stem.lower()
                if name in AI_PROCESS_NAMES:
                    return name
                # npm-installed CLIs run as node with the tool's script on the command line
                if name == "node":
                    cmd = " ".join(child.cmdline()).lower()
                    for ai in AI_PROCESS_NAMES:
                        if ai in cmd:
                            return ai
        except (psutil.Error, OSError):
            pass
        return None

    def close(self) -> None:
        self._alive = False
        with contextlib.suppress(Exception):  # already gone
            self._proc.terminate(force=True)


class Terminals:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def start(self, cwd: str | None, cols: int, rows: int) -> str:
        session = Session(cwd, cols, rows)
        self._sessions[session.id] = session
        return session.id

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def close(self, session_id: str) -> None:
        if session := self._sessions.pop(session_id, None):
            session.close()

    def close_all(self) -> None:
        for session_id in list(self._sessions):
            self.close(session_id)
