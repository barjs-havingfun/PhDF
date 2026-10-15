"""Entry point: creates the window(s) and wires the API.

Set PHDF_DEV=1 to load the Vite dev server (http://localhost:5173) with devtools enabled.
Variables can also come from a `.env` file in the project root (see `.env.example`).
"""

import mimetypes
import os
import sys

import webview

from phdf.api import SESSION_PREFIX, Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.env import load_dotenv
from phdf.paths import data_dir, frontend_dist
from phdf.services.render_server import RenderServer

MAIN_WINDOW = "main"


def fix_mimetypes() -> None:
    """Windows registry often maps .js to text/plain, and WebView2 rejects ES modules served
    that way by pywebview's local HTTP server. Python's mimetypes reads the registry, so pin it."""
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/css", ".css")


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
    core = Core(default_engine(), store)
    render_server = RenderServer(core.render).start()
    core.render_base_url = render_server.base_url

    def create_window(window_id: str, x: int | None = None, y: int | None = None) -> None:
        api = Api(core, window_id)
        window = webview.create_window(
            "PhDF", url, js_api=api, width=1200, height=800, x=x, y=y,
            min_size=(640, 480), text_select=True,
        )  # fmt: skip
        if window is None:
            return
        api._window = window
        core.windows[window_id] = api
        window.events.closed += api._on_closed

    core.create_window = create_window
    for window_id in saved_window_ids(store):
        create_window(window_id)

    webview.start(debug=dev, private_mode=False, storage_path=str(data_dir() / "webview"))
    core.shutdown()
    render_server.stop()
    store.close()


if __name__ == "__main__":
    main()
