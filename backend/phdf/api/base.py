"""Per-window state shared by the feature parts of `Api`."""

import threading

import webview

from phdf.api.core import Core
from phdf.services import (
    pdftools,
    titlebar,
)
from phdf.services.terminal import Terminals


class ApiBase:
    """Per-window state; the feature classes below add the methods."""

    def __init__(self, core: Core, window_id: str) -> None:
        self._core = core
        self._window_id = window_id
        self._window: webview.Window | None = None
        self._open: set[str] = set()  # ids (as given to the frontend) this window holds
        self._peek: webview.Window | None = None
        self._force_close = False
        self._close_timer: threading.Timer | None = None
        self._searches: dict[str, int] = {}  # newest search per document (older ones stop)
        self._terminals = Terminals()
        self._tools: dict[str, pdftools.ToolsSession] = {}  # PDF tools sessions of this window
        self._dark = titlebar.os_dark()  # title bar theme (Windows)
        self._fullscreen = False
        self._snips: set[str] = set()  # Image → AI files not deleted yet (removed on close)
