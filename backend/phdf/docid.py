"""Stable document identity based on content, so positions survive renames and moves (D11)."""

import hashlib
from pathlib import Path

_HEAD_BYTES = 1024 * 1024


def document_id(path: str | Path) -> str:
    """SHA-256 of the file size plus its first 1 MB."""
    path = Path(path)
    digest = hashlib.sha256()
    digest.update(str(path.stat().st_size).encode())
    with path.open("rb") as f:
        digest.update(f.read(_HEAD_BYTES))
    return digest.hexdigest()
