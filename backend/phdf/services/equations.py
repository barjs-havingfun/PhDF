"""Equation → LaTeX through the AI in the terminal.

A region of a page is saved as a PNG; the AI (Claude Code / Codex) is asked to read it and write
the LaTeX to a .tex file next to it, which the page polls for. Both files sit in a hidden temp
folder inside the terminal's working folder (Codex may only write inside its workspace) and are
deleted as soon as the answer is read, or on cancel.
"""

import contextlib
import os
import sys
import time
import uuid
from pathlib import Path

TEMP_DIR = ".phdf-tmp"
SCALE = 4.0  # 288 DPI: small symbols stay readable for the AI
PREFIX = "eq-"


def work_dir(folder: str | None) -> Path:
    """Where the terminal runs (the shell falls back to the home folder, see terminal.py)."""
    base = Path(folder) if folder and Path(folder).is_dir() else Path.home()
    return base / TEMP_DIR


def _hide(path: Path) -> None:
    """Dot folders are hidden on macOS / Linux; on Windows set the hidden attribute."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)  # FILE_ATTRIBUTE_HIDDEN


def prepare(directory: Path, png: bytes) -> dict[str, str]:
    new = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True)
    if new:
        _hide(directory)
    name = PREFIX + uuid.uuid4().hex[:8]
    png_path = directory / f"{name}.png"
    png_path.write_bytes(png)
    return {"png": str(png_path), "tex": str(directory / f"{name}.tex")}


def _is_ours(path: Path) -> bool:
    return path.parent.name == TEMP_DIR and path.name.startswith(PREFIX)


def result(tex_path: str) -> str | None:
    """The AI's answer, once written (None while waiting)."""
    path = Path(tex_path)
    if not _is_ours(path) or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None  # still being written
    return text or None


def remove(png_path: str) -> None:
    """Delete one job's files (the PNG and its .tex), and the folder when it is empty."""
    path = Path(png_path)
    if not _is_ours(path):
        return
    for p in (path, path.with_suffix(".tex")):
        with contextlib.suppress(OSError):
            p.unlink()
    with contextlib.suppress(OSError):
        path.parent.rmdir()  # only succeeds when empty


def cleanup(directory: Path, older_than: float = 0) -> None:
    """Delete leftover job files (e.g. the app was closed while waiting)."""
    if not directory.is_dir():
        return
    now = time.time()
    for p in directory.glob(PREFIX + "*"):
        with contextlib.suppress(OSError):
            if now - p.stat().st_mtime >= older_than:
                p.unlink()
    with contextlib.suppress(OSError):
        os.rmdir(directory)
