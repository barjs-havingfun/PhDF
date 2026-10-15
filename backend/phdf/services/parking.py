"""Parking lot: stray thoughts captured while reading, kept as a Markdown task list.

    - [ ] Look up Eisenstein's montage theory — Film Art, p. 214 · 2026-10-15 14:03

One list per document, next to it: "<name>.parking.md" beside "<name>.pdf" (and its integrated
"<name>.md" note). Thoughts parked with nothing open go to PhDF's data folder.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

HEADER = "# Parking Lot\n\nThoughts parked while reading in PhDF.\n\n"


def path_for(document: str | Path | None, fallback_dir: Path) -> Path:
    """The parking list of a document (PDF or note), or the general one."""
    if not document:
        return fallback_dir / "Parking Lot.md"
    doc = Path(document)
    return doc.with_name(f"{doc.stem}.parking.md")


_ITEM = re.compile(r"^- \[( |x|X)\] (.*)$")


@dataclass(frozen=True)
class Item:
    line: int  # 0-based line in the file
    text: str
    done: bool


def add(path: Path, thought: str, source: str | None = None, title: str | None = None) -> None:
    thought = " ".join(thought.split())  # one line
    if not thought:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    suffix = f" — {source} · {stamp}" if source else f" — {stamp}"
    header = HEADER.replace("# Parking Lot", f"# Parking Lot — {title}") if title else HEADER
    text = path.read_text(encoding="utf-8") if path.exists() else header
    if not text.endswith("\n"):
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + f"- [ ] {thought}{suffix}\n", encoding="utf-8", newline="\n")


def items(path: Path) -> list[Item]:
    if not path.exists():
        return []
    result = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if m := _ITEM.match(line):
            result.append(Item(line=i, text=m[2], done=m[1] != " "))
    return result


def set_done(path: Path, line: int, text: str, done: bool) -> bool:
    """Tick an item. `text` guards against the file having been edited meanwhile."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not 0 <= line < len(lines) or not (m := _ITEM.match(lines[line])) or m[2] != text:
        return False
    lines[line] = f"- [{'x' if done else ' '}] {text}"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return True
