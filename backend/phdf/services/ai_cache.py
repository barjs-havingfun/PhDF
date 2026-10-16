"""The AI's Markdown copies of documents (`<data>/ai/<doc>-p<a>-<b>-r<rev>.md` and the whole
document `<doc>-all-r<rev>.md`, see
`Api.ai_context`) and keeping that folder small.

A file's modification time is its last use: a cache hit touches it. Cleaning keeps only the most
recently used revision of each document, drops files unused for `MAX_AGE_DAYS` and then the
least recently used ones until the folder is under `MAX_BYTES`.
"""

import contextlib
import os
import re
import time
from collections import defaultdict
from pathlib import Path

MAX_AGE_DAYS = 30
MAX_BYTES = 500 * 1024 * 1024
_NAME = re.compile(r"^(?P<doc>[0-9a-f]+)-(?:p\d+-\d+|all)-r(?P<rev>\d+)\.md$")


def folder(data: Path) -> Path:
    return data / "ai"


def touch(path: Path) -> None:
    """Mark a cached file as used now."""
    with contextlib.suppress(OSError):
        os.utime(path)


def _files(where: Path) -> list[tuple[Path, os.stat_result]]:
    if not where.is_dir():
        return []
    result = []
    for path in where.iterdir():
        if path.is_file() and _NAME.match(path.name):
            try:
                result.append((path, path.stat()))
            except OSError:  # removed meanwhile
                continue
    return result


def _remove(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except OSError:  # in use (Windows) or already gone
        return False


def cleanup(where: Path, max_age_days: float = MAX_AGE_DAYS, max_bytes: int = MAX_BYTES) -> int:
    """Apply the rules above; returns how many files were deleted."""
    files = _files(where)
    deleted: set[Path] = set()

    # 1. Only the most recently used revision of each document.
    by_doc: defaultdict[str, list[tuple[Path, os.stat_result]]] = defaultdict(list)
    for path, st in files:
        by_doc[_NAME.match(path.name)["doc"]].append((path, st))  # type: ignore[index]
    for entries in by_doc.values():
        newest = max(entries, key=lambda e: e[1].st_mtime)[0]
        keep_rev = _NAME.match(newest.name)["rev"]  # type: ignore[index]
        for path, _ in entries:
            if _NAME.match(path.name)["rev"] != keep_rev and _remove(path):  # type: ignore[index]
                deleted.add(path)

    # 2. Not used for a while.
    cutoff = time.time() - max_age_days * 86400
    for path, st in files:
        if path not in deleted and st.st_mtime < cutoff and _remove(path):
            deleted.add(path)

    # 3. Least recently used first, until the folder fits (never the newest: it is being used).
    left = sorted((e for e in files if e[0] not in deleted), key=lambda e: e[1].st_mtime)
    total = sum(st.st_size for _, st in left)
    for path, st in left[:-1]:
        if total <= max_bytes:
            break
        if _remove(path):
            deleted.add(path)
            total -= st.st_size
    return len(deleted)


def info(where: Path) -> dict[str, int]:
    files = _files(where)
    return {"files": len(files), "bytes": sum(st.st_size for _, st in files)}


def clear(where: Path) -> int:
    return sum(_remove(path) for path, _ in _files(where))
