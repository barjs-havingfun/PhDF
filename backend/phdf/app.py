"""Entry point: creates the window(s) and wires the API.

Set PHDF_DEV=1 to load the Vite dev server (http://localhost:5173) with devtools enabled.
Variables can also come from a `.env` file in the project root (see `.env.example`).
"""

import mimetypes
import os
import sys
import threading
from pathlib import Path

import webview

from phdf.api import SESSION_PREFIX, Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.env import load_dotenv
from phdf.paths import data_dir, frontend_dist
from phdf.services import ai_cache
from phdf.services.render_server import RenderServer

MAIN_WINDOW = "main"


def fix_mimetypes() -> None:
    """Windows registry often maps .js to text/plain, and WebView2 rejects ES modules served
    that way by pywebview's local HTTP server. Python's mimetypes reads the registry, so pin it."""
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/css", ".css")


def remember_geometry(window: webview.Window, key: str, store: Store) -> None:
    """Save a window's size, position and maximized state as it changes."""
    geo = dict(store.get_setting(key) or {})
    timer: threading.Timer | None = None

    def save(**changes: object) -> None:
        # Dragging a window fires many events: write once it has settled.
        nonlocal timer
        geo.update(changes)
        if timer:
            timer.cancel()
        timer = threading.Timer(0.4, store.set_setting, args=(key, dict(geo)))
        timer.daemon = True
        timer.start()

    def on_resized(width: int, height: int) -> None:
        if not geo.get("maximized") and width > 200 and height > 200:
            save(width=width, height=height)

    def on_moved(x: int, y: int) -> None:
        if not geo.get("maximized") and x > -10000 and y > -10000:
            save(x=x, y=y)

    window.events.resized += on_resized
    window.events.moved += on_moved
    window.events.maximized += lambda: save(maximized=True)
    window.events.restored += lambda: save(maximized=False)

    def flush() -> None:
        if timer and timer.is_alive():
            timer.cancel()
            store.set_setting(key, dict(geo))

    window.events.closed += flush


def startup_paths(argv: list[str]) -> list[str]:
    """PDF / Markdown files given on the command line ("Open with", a Linux .desktop file)."""
    paths = []
    for arg in argv:
        path = Path(arg)
        if path.suffix.lower() in (".pdf", ".md") and path.is_file():
            paths.append(str(path.resolve()))
    return paths


def saved_window_ids(store: Store) -> list[str]:
    """Windows to restore. Migrates the single-window session format of v0.1.0."""
    if (legacy := store.get_setting("session")) is not None:
        store.delete_setting("session")
        if not store.settings_with_prefix(SESSION_PREFIX):
            store.set_setting(SESSION_PREFIX + MAIN_WINDOW, legacy)
    ids = [key.removeprefix(SESSION_PREFIX) for key in store.settings_with_prefix(SESSION_PREFIX)]
    return ids or [MAIN_WINDOW]


def main() -> None:
    load_dotenv()
    fix_mimetypes()
    dev = os.environ.get("PHDF_DEV") == "1"

    if dev:
        url = os.environ.get("PHDF_DEV_URL") or "http://localhost:5173"
    else:
        index = frontend_dist() / "index.html"
        if not index.exists():
            sys.exit(f"Frontend not built ({index} missing). Run: npm --prefix frontend run build")
        url = str(index)

    store = Store(data_dir() / "phdf.db")
    threading.Thread(
        target=ai_cache.cleanup, args=(ai_cache.folder(data_dir()),), daemon=True
    ).start()
    core = Core(default_engine(), store)
    render_server = RenderServer(core.render).start()
    core.render_base_url = render_server.base_url
    core.on_closed_document = render_server.forget
    core.startup_paths = startup_paths(sys.argv[1:])

    def create_window(window_id: str, x: int | None = None, y: int | None = None) -> None:
        api = Api(core, window_id)
        key = f"window.{window_id}"
        geo = store.get_setting(key) or {}
        window = webview.create_window(
            "PhDF", url, js_api=api,
            width=geo.get("width", 1200), height=geo.get("height", 800),
            x=x if x is not None else geo.get("x"), y=y if y is not None else geo.get("y"),
            maximized=bool(geo.get("maximized")), min_size=(640, 480), text_select=True,
        )  # fmt: skip
        if window is None:
            return
        api._window = window
        core.windows[window_id] = api
        window.events.closing += api._on_closing
        window.events.closed += api._on_closed
        remember_geometry(window, key, store)

    core.create_window = create_window
    for window_id in saved_window_ids(store):
        create_window(window_id)

    webview.start(
        debug=dev,
        private_mode=False,
        storage_path=str(data_dir() / "webview"),
    )
    core.shutdown()
    render_server.stop()
    store.close()


if __name__ == "__main__":
    main()
