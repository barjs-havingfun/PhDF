"""Notes: grading folders, Obsidian, parking lot, Markdown files next to PDFs."""

import os
import re
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

import webview

from phdf.api.base import ApiBase
from phdf.paths import data_dir
from phdf.services import (
    grading,
    parking,
)


class NotesApi(ApiBase):
    # --- grading ------------------------------------------------------------------------------

    def grading_scan(self, folder: str) -> dict[str, Any]:
        """The exam PDFs in a folder and where its grades table goes."""
        return {
            "folder": str(Path(folder)),
            # Settings key: case-insensitive only where the file system is (Windows).
            "key": os.path.normcase(str(Path(folder))),
            "title": Path(folder).name,
            "table": str(grading.table_path(folder)),
            "files": grading.scan(folder),
        }

    def grading_copy(self, folder: str, rel: str) -> str:
        """Path of the marked copy of one exam (created from the original on first use)."""
        return str(grading.graded_copy(folder, rel))

    # --- Obsidian -------------------------------------------------------------------------------

    def pick_folder(self) -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    def _vault_note(self, title: str) -> Path:
        store = self._core.store
        vault = store.get_setting("obsidian.vault")
        if not vault:
            raise ValueError("No Obsidian vault chosen")
        folder = (store.get_setting("obsidian.folder") or "PhDF").strip(" /\\")
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f#^\[\]]', "-", title).strip(" .") or "Untitled"
        return Path(vault, folder, f"{name}.md") if folder else Path(vault, f"{name}.md")

    def obsidian_append(self, title: str, block: str) -> str:
        """Append a pin + quote to the book's note in the vault (created with a heading)."""
        path = self._vault_note(title)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n\n"
        if text and not text.endswith("\n\n"):
            text += "\n" if text.endswith("\n") else "\n\n"
        self.write_text(str(path), text + block)
        return str(path)

    def obsidian_write(self, title: str, text: str, overwrite: bool = False) -> dict[str, Any]:
        """Copy a note into the vault. Without `overwrite`, an existing file is left alone."""
        path = self._vault_note(title)
        if path.exists() and not overwrite:
            return {"path": str(path), "written": False, "exists": True}
        self.write_text(str(path), text)
        return {"path": str(path), "written": True, "exists": True}

    # --- parking lot ----------------------------------------------------------------------------

    def parking_path(self, document: str | None = None) -> str:
        """Where thoughts parked while reading `document` (a PDF or .md path) are kept."""
        return str(parking.path_for(document, data_dir()))

    def parking_add(
        self, thought: str, source: str | None = None, document: str | None = None
    ) -> str:
        path = Path(self.parking_path(document))
        title = Path(document).stem if document else None
        parking.add(path, thought, source, title)
        return str(path)

    def parking_list(self, document: str | None = None) -> dict[str, Any]:
        path = Path(self.parking_path(document))
        return {"path": str(path), "items": [asdict(i) for i in parking.items(path)]}

    def parking_done(
        self, line: int, text: str, done: bool = True, document: str | None = None
    ) -> bool:
        return parking.set_done(Path(self.parking_path(document)), line, text, done)

    def open_in_obsidian(self, path: str) -> None:
        webbrowser.open("obsidian://open?path=" + quote(path, safe=""))

    # --- markdown files ---------------------------------------------------------------------

    def md_for_pdf(self, pdf_path: str) -> dict[str, Any]:
        """The Markdown file integrated with a PDF: a linked one, else "<stem>.md" beside it."""
        linked = self._core.store.md_link(pdf_path)
        path = Path(linked) if linked else Path(pdf_path).with_suffix(".md")
        return {"path": str(path), "exists": path.is_file(), "linked": linked is not None}

    def pdf_for_md(self, md_path: str) -> str | None:
        """The PDF a Markdown file is integrated with, if any."""
        if linked := self._core.store.pdf_for_md(md_path):
            return linked
        sibling = Path(md_path).with_suffix(".pdf")
        return str(sibling) if sibling.is_file() else None

    def link_md(self, pdf_path: str, md_path: str) -> None:
        self._core.store.set_md_link(pdf_path, md_path)

    def md_files(self, folder: str) -> list[dict[str, str]]:
        """The Markdown notes in a folder (a standalone note's sidebar), by name. PhDF's own
        side files (parking lots, grades tables) are left out."""
        try:
            found = [p for p in Path(folder).iterdir() if p.suffix.lower() == ".md" and p.is_file()]
        except OSError:
            return []
        own = (".parking.md", ".grades.md")
        found = sorted(
            (p for p in found if not p.name.lower().endswith(own)), key=lambda p: p.name.lower()
        )
        return [{"name": p.name, "path": str(p)} for p in found]

    def read_text(self, path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            return {"exists": False, "text": "", "mtime": None}
        return {"exists": True, "text": p.read_text(encoding="utf-8"), "mtime": p.stat().st_mtime}

    def write_text(self, path: str, text: str) -> float:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".phdf-tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        tmp.replace(p)  # atomic: a crash never leaves a half-written note
        return p.stat().st_mtime

    def rename_file(self, path: str, name: str) -> str:
        """Rename a note in its folder (".md" added if missing); returns the new path. A note
        shown with a PDF stays linked to it."""
        old = Path(path)
        name = name.strip()
        if not name or name in (".", "..") or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
            raise ValueError("That name can't be used for a file.")
        if not name.lower().endswith(".md"):
            name += ".md"
        new = old.with_name(name)
        if new == old:
            return str(old)
        # A case-only change on Windows is the same file, not a clash.
        same = new.exists() and old.exists() and os.path.samefile(old, new)
        if new.exists() and not same:
            raise ValueError(f"“{name}” already exists in this folder.")
        store = self._core.store
        pdf = store.pdf_for_md(str(old))
        if pdf is None and old.with_suffix(".pdf").is_file():
            pdf = str(old.with_suffix(".pdf"))  # the default "<pdf>.md" note
        if old.exists():
            old.rename(new)  # a note never written yet only changes its path
        if pdf:
            store.set_md_link(pdf, str(new))
        return str(new)

    def file_mtime(self, path: str) -> float | None:
        p = Path(path)
        return p.stat().st_mtime if p.is_file() else None
