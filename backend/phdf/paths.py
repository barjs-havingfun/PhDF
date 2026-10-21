"""Filesystem locations: per-user data dir and bundled frontend."""

import os
import sys
from pathlib import Path

APP_NAME = "PhDF"


def data_dir() -> Path:
    """Per-user, per-OS directory for the database and caches. Override with PHDF_DATA_DIR."""
    if override := os.environ.get("PHDF_DATA_DIR"):
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        xdg = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        base = Path(xdg) / APP_NAME.lower()
    base.mkdir(parents=True, exist_ok=True)
    return base


def frontend_dist() -> Path:
    """Built frontend: bundled by PyInstaller, or `frontend/dist` in a source checkout."""
    if bundle := getattr(sys, "_MEIPASS", None):
        return Path(bundle) / "frontend"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def icon_file(name: str) -> Path:
    """An app icon (packaging/icons, from logo.png via packaging/make_icons.py)."""
    if bundle := getattr(sys, "_MEIPASS", None):
        return Path(bundle) / "icons" / name
    return Path(__file__).resolve().parents[2] / "packaging" / "icons" / name
