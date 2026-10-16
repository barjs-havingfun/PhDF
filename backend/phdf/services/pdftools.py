"""PDF tools (Phase 7): rotate, delete, duplicate, insert blank pages, reorder, merge, extract,
split.

All work happens on a copy in memory; the original file is never written. A session keeps the
original bytes and the list of operations, so undo simply rebuilds without the last one. Results
are always new files: "<name>_phdfE.pdf", extracts / splits "<name>_p_3-7_phdf.pdf".
"""

from pathlib import Path
from typing import Any

import pymupdf

Op = dict[str, Any]


def apply(doc: pymupdf.Document, op: Op) -> None:
    """One operation on a document. Page numbers are 0-based, in the document's current order."""
    n = doc.page_count
    kind = op["kind"]
    pages = sorted({int(p) for p in op.get("pages", []) if 0 <= int(p) < n})
    if kind == "rotate":
        for p in pages:
            page = doc[p]
            page.set_rotation((page.rotation + int(op["by"])) % 360)
    elif kind == "delete":
        keep = [i for i in range(n) if i not in pages]
        if not keep:
            raise ValueError("A PDF needs at least one page: you can't delete them all.")
        doc.select(keep)
    elif kind == "move":
        # Move the selected pages, in order, to just before page `to` (n = the end).
        rest = [i for i in range(n) if i not in pages]
        at = sum(1 for i in rest if i < int(op["to"]))
        doc.select(rest[:at] + pages + rest[at:])
    elif kind == "duplicate":
        for p in reversed(pages):  # from the back, so earlier numbers stay valid
            doc.fullcopy_page(p, p + 1 if p + 1 < n else -1)
    elif kind == "blank":
        at = min(max(int(op["at"]), 0), n)
        ref = doc[min(at, n - 1)].rect
        doc.new_page(pno=at if at < n else -1, width=ref.width, height=ref.height)
    elif kind == "insert_pdf":
        at = min(max(int(op["at"]), 0), n)
        with pymupdf.open(op["path"]) as other:
            doc.insert_pdf(other, start_at=at if at < n else -1)
    else:
        raise ValueError(f"unknown operation {kind!r}")


class ToolsSession:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.original = self.path.read_bytes()
        self.ops: list[Op] = []
        self.doc = self._build()

    def _build(self) -> pymupdf.Document:
        doc = pymupdf.open("pdf", self.original)
        for op in self.ops:
            apply(doc, op)
        return doc

    def apply(self, op: Op) -> None:
        try:
            apply(self.doc, op)
        except Exception:
            self.doc.close()  # it may be half changed: back to the last good state
            self.doc = self._build()
            raise
        self.ops.append(op)

    def undo(self) -> None:
        if self.ops:
            self.ops.pop()
            self.doc.close()
            self.doc = self._build()

    def has_annotations(self, pages: list[int] | None = None) -> bool:
        numbers = range(self.doc.page_count) if pages is None else pages
        return any(self.doc[p].first_annot is not None for p in numbers)

    def write(self, dest: Path, pages: list[int] | None, keep_annotations: bool) -> Path:
        """Save the current state (or some of its pages) as a new PDF."""
        with pymupdf.open("pdf", self.doc.tobytes()) as out:
            if pages is not None:
                out.select(pages)
            if not keep_annotations:
                for page in out:
                    while (annot := page.first_annot) is not None:
                        page.delete_annot(annot)
            out.save(dest, garbage=3, deflate=True)
        return dest

    def close(self) -> None:
        self.doc.close()


# --- file names -------------------------------------------------------------------------------


def free_name(folder: Path, base: str) -> Path:
    """`base`.pdf, or base_2.pdf, base_3.pdf … if taken."""
    path = folder / f"{base}.pdf"
    n = 2
    while path.exists():
        path = folder / f"{base}_{n}.pdf"
        n += 1
    return path


def copy_path(original: Path) -> Path:
    return free_name(original.parent, f"{original.stem}_phdfE")


def pages_label(pages: list[int]) -> str:
    """1-based, ranges compressed: [2, 3, 4, 6] -> "3-5,7"."""
    parts: list[str] = []
    nums = sorted({p + 1 for p in pages})
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ",".join(parts)


def part_path(original: Path, pages: list[int], folder: Path | None = None) -> Path:
    return free_name(folder or original.parent, f"{original.stem}_p_{pages_label(pages)}_phdf")
