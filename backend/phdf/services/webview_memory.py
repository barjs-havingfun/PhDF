"""Ask the embedded browser to give memory back (WebView2 on Windows).

Chromium keeps decoded page images and caches around long after a document is closed. Setting
WebView2's MemoryUsageTargetLevel to Low makes it drop them; we switch back to Normal shortly
after so scrolling stays smooth. Elsewhere this is a no-op.
"""

import contextlib
import sys
import threading
from typing import Any

RESTORE_AFTER_S = 2.0


def trim(window: Any) -> bool:
    if sys.platform != "win32" or window is None:
        return False
    try:
        from Microsoft.Web.WebView2.Core import (  # type: ignore[import-not-found]
            CoreWebView2MemoryUsageTargetLevel as Level,
        )
        from System import Action  # type: ignore[import-not-found]

        webview = window.native.webview

        def set_level(level: Any) -> None:
            webview.Invoke(
                Action(lambda: setattr(webview.CoreWebView2, "MemoryUsageTargetLevel", level))
            )

        def restore() -> None:
            with contextlib.suppress(Exception):  # the window was closed meanwhile
                set_level(Level.Normal)

        set_level(Level.Low)
        threading.Timer(RESTORE_AFTER_S, restore).start()
        return True
    except Exception:  # noqa: BLE001 — older runtimes / other GUI backends: just skip
        return False
