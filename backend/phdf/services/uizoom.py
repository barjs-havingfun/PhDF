"""Interface size (Settings → Appearance): the web view's own zoom, like a browser's.

Browser zoom keeps every coordinate consistent (clicks, selections, page images get sharper
through a higher devicePixelRatio), which CSS `zoom` on the page would not. Each GUI backend
has its own call; anything else is skipped.
"""

import contextlib
import sys
from typing import Any


def set_zoom(window: Any, factor: float) -> None:
    if window is None:
        return
    with contextlib.suppress(Exception):  # not shown yet / another GUI backend: skip
        view = window.native.webview
        if sys.platform == "win32":  # WebView2 (WinForms)
            from System import Action  # type: ignore[import-not-found]

            view.Invoke(Action(lambda: setattr(view, "ZoomFactor", factor)))
        elif sys.platform == "darwin":  # WKWebView, macOS 11+
            from PyObjCTools import AppHelper  # type: ignore[import-not-found]

            AppHelper.callAfter(view.setPageZoom_, factor)
        else:  # WebKitGTK
            from gi.repository import GLib  # type: ignore[import-not-found]

            GLib.idle_add(view.set_zoom_level, factor)
