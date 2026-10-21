"""Interface size (Settings → Appearance): the web view's own zoom, like a browser's.

Browser zoom keeps every coordinate consistent (clicks, selections, page images get sharper
through a higher devicePixelRatio), which CSS `zoom` on the page would not. Each GUI backend
has its own call; anything else is skipped.
"""

import logging
import sys
from typing import Any

log = logging.getLogger(__name__)


def web_view(window: Any) -> Any:
    """The native web view of a pywebview window (pywebview 6). On Windows `window.native` is
    pywebview's form, which holds it; on macOS and Linux `native` is the bare NSWindow /
    Gtk.Window, and the view lives on pywebview's BrowserView for that window."""
    if sys.platform == "win32":
        return window.native.webview
    if sys.platform == "darwin":
        from webview.platforms.cocoa import BrowserView
    else:
        from webview.platforms.gtk import BrowserView
    return BrowserView.instances[window.uid].webview


def set_zoom(window: Any, factor: float) -> None:
    if window is None:
        return
    try:
        view = web_view(window)
        if sys.platform == "win32":  # WebView2 (WinForms)
            from System import Action  # type: ignore[import-not-found]

            view.Invoke(Action(lambda: setattr(view, "ZoomFactor", factor)))
        elif sys.platform == "darwin":  # WKWebView, macOS 11+
            from PyObjCTools import AppHelper  # type: ignore[import-not-found]

            AppHelper.callAfter(view.setPageZoom_, factor)
        else:  # WebKitGTK
            from gi.repository import GLib  # type: ignore[import-not-found]

            GLib.idle_add(view.set_zoom_level, factor)
    except Exception:  # not shown yet, or a pywebview change: keep running, but say so
        log.exception("Interface size: can't reach the web view")
