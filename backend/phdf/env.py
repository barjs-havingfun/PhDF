"""Minimal `.env` loader for source checkouts (no dependency needed for a few KEY=VALUE lines)."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load KEY=VALUE pairs into os.environ without overriding variables that are already set.
    Skipped in packaged builds, which have no project root."""
    if getattr(sys, "frozen", False) or not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
