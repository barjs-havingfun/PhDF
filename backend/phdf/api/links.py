"""Links: external links and the link preview windows."""

import webbrowser
from urllib.parse import urlsplit

import webview

from phdf.api.base import ApiBase
from phdf.api.core import PEEK_SIZE
from phdf.services import (
    webpeek,
)


class LinksApi(ApiBase):
    # --- links ------------------------------------------------------------------------------

    def open_external(self, url: str) -> None:
        """Open a URL in the system browser (or mail client for mailto:)."""
        if urlsplit(url).scheme in ("http", "https", "mailto"):
            webbrowser.open(url)

    def peek_url(self, url: str, large: bool = False) -> bool:
        """Show a web link in a floating preview window (R11): small beside a PDF, `large`
        (most of the app window, centered) for links in notes. A movable native window with
        a bar on top: Back, Open in Browser, close."""
        if urlsplit(url).scheme not in ("http", "https"):
            return False
        main = self._window
        width, height = PEEK_SIZE
        x = y = None
        if main is not None:
            if large:
                width, height = max(int(main.width * 0.8), 640), max(int(main.height * 0.82), 480)
                x, y = main.x + (main.width - width) // 2, main.y + (main.height - height) // 2
            else:
                x, y = max(main.x + main.width - width - 24, 0), main.y + 96
        if self._peek is not None:
            self._peek.load_url(url)
            self._peek.restore()
            if large and x is not None and y is not None:
                self._peek.resize(width, height)
                self._peek.move(x, y)
            return True
        # Never the app API for third-party pages: only the bar's two actions.
        bridge = webpeek.PeekBridge()
        peek = webview.create_window(
            "Link preview", url, js_api=bridge, width=width, height=height, x=x, y=y, on_top=True
        )
        if peek is None:
            return False
        bridge._window = peek
        peek.events.loaded += lambda: webpeek.add_bar(peek)
        peek.events.closed += self._on_peek_closed
        self._peek = peek
        return True

    def peek_expand(self) -> None:
        if self._peek is not None:
            self._peek.on_top = False
            self._peek.maximize()

    def peek_close(self) -> None:
        if self._peek is not None:
            self._peek.destroy()

    def _on_peek_closed(self) -> None:
        self._peek = None
