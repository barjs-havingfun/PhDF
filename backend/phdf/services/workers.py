"""Slow PyMuPDF work (OCR, Markdown conversion) runs in worker processes.

MuPDF must not be used from two threads at once, and holding the engine lock for this work
(seconds to minutes) would stop page drawing; a process has a MuPDF of its own. Arguments and
results are plain data; a document goes over once as a temporary file (`snapshot`). The built
app needs `multiprocessing.freeze_support()` first thing (`__main__.py`).
"""

import contextlib
import multiprocessing
import os
import tempfile
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any

WORKERS = 2  # a long conversion doesn't hold up OCR
inline = False  # tests: run in this process (stand-ins can't be sent to another one)

_pool: ProcessPoolExecutor | None = None
_guard = threading.Lock()


def run(fn: Callable[..., Any], *args: Any) -> Any:
    """`fn(*args)` in a worker process; `fn` must be a module-level function."""
    global _pool
    if inline:
        return fn(*args)
    with _guard:
        if _pool is None:
            _pool = ProcessPoolExecutor(WORKERS, mp_context=multiprocessing.get_context("spawn"))
        pool = _pool
    try:
        return pool.submit(fn, *args).result()
    except BrokenProcessPool:
        with _guard:  # a worker died (out of memory, a crash in MuPDF): fresh ones next time
            if _pool is pool:
                _pool = None
        raise


@contextlib.contextmanager
def snapshot(data: bytes) -> Iterator[str]:
    """A document's bytes as a temporary file for the workers, removed afterwards."""
    fd, name = tempfile.mkstemp(prefix="phdf-", suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield name
    finally:
        with contextlib.suppress(OSError):
            os.unlink(name)


def shutdown() -> None:
    """Stop the workers, also in the middle of a long job (PhDF is closing)."""
    global _pool
    with _guard:
        pool, _pool = _pool, None
    if pool is None:
        return
    for process in list(getattr(pool, "_processes", {}).values()):
        with contextlib.suppress(Exception):
            process.terminate()
    pool.shutdown(wait=False, cancel_futures=True)


def pid() -> int:
    """For the self-test: the worker's process id."""
    return os.getpid()
