"""`PhDF --self-test`: checks a built app without opening a window. The release workflow runs it
on every platform before a release is drafted. The report goes to stdout and to
`<data dir>/self-test.txt` (a Windows app has no console); the exit code is 0 when all passed."""

import sys
import tempfile
import time
import traceback
import zipfile
from collections.abc import Callable
from pathlib import Path

import pymupdf

from phdf.paths import data_dir, frontend_dist

EPUB_CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="book.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
EPUB_OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">self-test</dc:identifier><dc:title>Self-test</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>
  <spine><itemref idref="c1"/></spine>
</package>"""


def make_pdf(path: Path) -> Path:
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "PhDF self-test")
        doc.save(path)
    return path


def make_epub(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", EPUB_CONTAINER)
        z.writestr("book.opf", EPUB_OPF)
        z.writestr(
            "c1.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>PhDF self-test</p></body></html>',
        )
    return path


def make_cbz(path: Path, sizes: tuple[tuple[int, int], ...] = ((600, 900), (1200, 900))) -> Path:
    """A comic: one JPEG per page, named so that natural order matters (2 before 10)."""
    names = ["page 2.jpg", "page 10.jpg", "page 11.jpg"]
    with zipfile.ZipFile(path, "w") as z:
        for name, (w, h) in zip(names, sizes, strict=False):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
            pix.clear_with(180)
            z.writestr(name, pix.tobytes("jpg"))
    return path


def check_frontend() -> str:
    index = frontend_dist() / "index.html"
    assert index.is_file(), f"{index} is missing"
    return str(index.parent)


def check_documents(folder: Path) -> str:
    """Opens a PDF, an EPUB and a CBZ, renders a page of each, annotates and saves the PDF."""
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine

    api = Api(Core(default_engine(), Store(folder / "db.sqlite")), "self-test")
    kinds = []
    for path, kind in (
        (make_pdf(folder / "test.pdf"), "pdf"),
        (make_epub(folder / "test.epub"), "ebook"),
        (make_cbz(folder / "test.cbz"), "comic"),
    ):
        doc = api.open_document(str(path))
        assert doc["info"]["kind"] == kind, f"{path.name}: kind {doc['info']['kind']}"
        image = api._core.render(doc["docId"], 0, 1.0, None)
        # PNG, or JPEG for pages that are mostly pictures (comics, scans)
        assert image and image[:3] in (b"\x89PN", b"\xff\xd8\xff"), f"{path.name}: no page image"
        kinds.append(kind)
    pdf = api.open_document(str(folder / "test.pdf"))["docId"]
    api.add_annotation(pdf, 0, "highlight", [(72, 60, 200, 76)], "#ffd60a")
    api.save_document(pdf)
    with pymupdf.open(folder / "test.pdf") as saved:
        assert saved[0].first_annot is not None, "the saved PDF has no annotation"
    return ", ".join(kinds) + "; annotation saved"


def check_terminal(folder: Path, timeout: float = 30) -> str:
    """The AI panel's shell starts and answers (0.8.1: the installed Windows app's did not)."""
    from phdf.services.terminal import Session, default_shell

    session = Session(str(folder), 80, 24)
    try:
        # The typed command doesn't contain the answer, so only the shell's output matches.
        if sys.platform == "win32":
            command, answer = "Write-Output ('phdf' + '-ok')\r", "phdf-ok"
        else:
            command, answer = "echo phdf-$((40+2))\r", "phdf-42"
        session.write(command)
        output, end = "", time.monotonic() + timeout
        while answer not in output and time.monotonic() < end:
            data, alive = session.read(0.5)
            output += data
            assert alive or answer in output, f"the shell exited: {output[-300:]!r}"
        assert answer in output, f"no answer from the shell in {timeout:.0f} s: {output[-300:]!r}"
    finally:
        session.close()
    return default_shell()[0]


def check_workers(folder: Path) -> str:
    """OCR and Markdown conversion run in worker processes; in the built app those start
    through multiprocessing.freeze_support (`__main__.py`)."""
    import os

    from phdf.services import ai_markdown, workers

    try:
        assert workers.run(workers.pid) != os.getpid(), "the worker is this process"
        text = ai_markdown.convert(make_pdf(folder / "md.pdf").read_bytes(), [0])
        assert "PhDF self-test" in text, f"conversion gave {text[:200]!r}"
    finally:
        workers.shutdown()
    return "a worker process converted a page"


def check_webview() -> str:
    """Linux: GTK and WebKit2 come from the distro (app.system_typelibs)."""
    if not sys.platform.startswith("linux"):
        return "not needed here"
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk, WebKit2  # noqa: F401

    return f"GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, WebKit2 4.1"


def run() -> int:
    from phdf import __version__

    lines = [f"PhDF {__version__} self-test ({sys.platform})"]
    failed = False
    with tempfile.TemporaryDirectory(prefix="phdf-self-test-", ignore_cleanup_errors=True) as tmp:
        checks: list[tuple[str, Callable[[], str]]] = [
            ("frontend", check_frontend),
            ("documents", lambda: check_documents(Path(tmp))),
            ("terminal", lambda: check_terminal(Path(tmp))),
            ("workers", lambda: check_workers(Path(tmp))),
            ("webview", check_webview),
        ]
        for name, check in checks:
            try:
                lines.append(f"ok    {name}: {check()}")
            except Exception:
                failed = True
                lines.append(f"FAIL  {name}:\n{traceback.format_exc()}")
    try:  # a document for the next release step, `PhDF --smoke-ui <data dir>/smoke.pdf`
        make_pdf(data_dir() / "smoke.pdf")
    except Exception:  # noqa: BLE001 - only that step needs it
        lines.append("note  could not write smoke.pdf")
    lines.append("FAILED" if failed else "ALL OK")
    report = "\n".join(lines) + "\n"
    try:
        out = data_dir() / "self-test.txt"
        out.write_text(report, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout:
        sys.stdout.write(report)
        sys.stdout.flush()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
