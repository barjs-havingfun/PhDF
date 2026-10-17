"""The web link preview window: a small toolbar shown on top of the page it loads.

Third-party pages get only `PeekBridge` (open the current page in the browser, close the
preview), never the app's API. The bar lives in a shadow root so the page's CSS can't touch it,
and is added again after every page load (pywebview's `evaluate_js` ignores the page's CSP).
"""

import contextlib
import threading
import webbrowser
from typing import Any
from urllib.parse import urlsplit


class PeekBridge:
    """The only JS API a previewed web page gets."""

    def __init__(self) -> None:
        self._window: Any = None

    def open_in_browser(self) -> None:
        url = self._window.get_current_url() if self._window else None
        if url and urlsplit(url).scheme in ("http", "https"):
            webbrowser.open(url)

    def close(self) -> None:
        if self._window is not None:
            # A moment later, so this call can return to the page first.
            later = threading.Timer(0.15, self._window.destroy)
            later.daemon = True
            later.start()


BAR_SCRIPT = r"""
(() => {
  if (document.getElementById("phdf-peek-bar")) return;
  const host = document.createElement("div");
  host.id = "phdf-peek-bar";
  host.style.cssText =
    "position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:2147483647";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `<style>
    div { display:flex; gap:4px; padding:4px; border-radius:12px;
      font:500 13px system-ui,sans-serif; background:rgba(30,30,34,.86);
      backdrop-filter:blur(16px); box-shadow:0 6px 24px rgba(0,0,0,.3) }
    button { all:unset; cursor:pointer; padding:6px 12px; border-radius:8px; color:#fff }
    button:hover { background:rgba(255,255,255,.14) }
    .main { background:#4b6ef5 } .main:hover { background:#5b7cff }
  </style><div>
    <button data-a="back" title="Back">&#8592; Back</button>
    <button data-a="open" class="main">Open in Browser</button>
    <button data-a="close" title="Close the preview">&#10005;</button>
  </div>`;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest && e.target.closest("button");
    const a = btn && btn.dataset.a;
    const py = window.pywebview && window.pywebview.api;
    if (a === "back") history.back();
    else if (a === "open" && py) py.open_in_browser();
    else if (a === "close" && py) py.close();
  });
  (document.body || document.documentElement).appendChild(host);
})();
"""


def add_bar(window: Any) -> None:
    with contextlib.suppress(Exception):  # the preview was closed or navigated meanwhile
        window.evaluate_js(BAR_SCRIPT)
