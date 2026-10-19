"""macOS: files opened from Finder while PhDF is running ("Open With", a double-click).

macOS doesn't start a second PhDF: it sends the running one an "open files" event, which
pywebview doesn't handle (PyInstaller's argv emulation only covers the launch). Add the
handler to pywebview's application delegate.
"""

import logging
import sys
from collections.abc import Callable

log = logging.getLogger(__name__)


def listen(on_files: Callable[[list[str]], None]) -> None:
    """Call before `webview.start`: NSApplication checks which methods its delegate has when
    the delegate is set."""
    if sys.platform != "darwin":
        return
    try:
        import objc  # type: ignore[import-not-found]
        from webview.platforms.cocoa import BrowserView  # type: ignore[import-not-found]

        def open_files(self: object, app: object, filenames: object) -> None:
            try:
                on_files([str(f) for f in filenames])  # type: ignore[attr-defined]
            finally:
                app.replyToOpenOrPrint_(0)  # type: ignore[attr-defined]  # success

        objc.classAddMethods(
            BrowserView.AppDelegate,
            [objc.selector(open_files, selector=b"application:openFiles:", signature=b"v@:@@")],
        )
    except Exception:  # noqa: BLE001 - another pywebview version: files open only at launch
        log.exception("Can't receive files from Finder")
