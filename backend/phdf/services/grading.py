"""Grading mode: a folder of exam PDFs marked one by one.

The originals are never written to: each PDF is copied to `<folder>/graded/<same relative path>`
the first time it is opened, and the marks are saved into that copy. The grades table lives in
`<folder>/<folder name>.grades.md` (written by the frontend).
"""

import re
import shutil
from pathlib import Path

GRADED_DIR = "graded"

# LMS exports put each submission in a folder named after the student, e.g. Moodle's
# "Ada Lovelace_123456_assignsubmission_file_".
_LMS_SUFFIX = re.compile(r"_\d+_assignsubmission_\w*$", re.IGNORECASE)


def _natural(text: str) -> list[object]:
    """Sort key: "exam2" before "exam10"."""
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]


def default_name(rel: str) -> str:
    """The student's folder name when the PDF is in a subfolder, else the file name."""
    parts = Path(rel).parts
    name = parts[0] if len(parts) > 1 else Path(rel).stem
    return _LMS_SUFFIX.sub("", name).strip() or name


def scan(folder: str | Path) -> list[dict[str, str]]:
    """Every PDF under `folder` (subfolders included, the graded copies excluded)."""
    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(folder)
    found = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if rel.parts[0] == GRADED_DIR or any(p.startswith(".") for p in rel.parts):
            continue
        if path.suffix.lower() == ".pdf" and path.is_file():
            found.append(rel.as_posix())
    found.sort(key=_natural)
    return [{"rel": rel, "name": default_name(rel)} for rel in found]


def table_path(folder: str | Path) -> Path:
    root = Path(folder)
    return root / f"{root.name or 'Grades'}.grades.md"


def graded_copy(folder: str | Path, rel: str) -> Path:
    """The marked copy of `rel`, created from the original on first use."""
    root = Path(folder).resolve()
    source = (root / rel).resolve()
    if root not in source.parents or source.suffix.lower() != ".pdf":
        raise ValueError(f"not a PDF in the grading folder: {rel}")
    target = root / GRADED_DIR / rel
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return target
