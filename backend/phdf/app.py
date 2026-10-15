"""Entry point: creates the pywebview window and wires the API.

Set PHDF_DEV=1 to load the Vite dev server (http://localhost:5173) with devtools enabled.
Variables can also come from a `.env` file in the project root (see `.env.example`).
"""

import mimetypes
import os
import sys

import webview

from phdf.api import Api
from phdf.db import Store
from phdf.engine import default_engine
from phdf.env import load_dotenv
from phdf.paths import data_dir, frontend_dist
from phdf.services.render_server import RenderServer


def fix_mimetypes() -> None:
    """Windows registry often maps .js to text/plain, and WebView2 rejects ES modules served
    that way by pywebview's local HTTP server. Python's mimetypes reads the registry, so pin it."""
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/css", ".css")


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
    api = Api(default_engine(), store)
    render_server = RenderServer(api._render).start()
    api._set_render_base_url(render_server.base_url)

    window = webview.create_window(
        "PhDF", url, js_api=api, width=1200, height=800, min_size=(640, 480), text_select=True
    )
    window.events.closed += api._shutdown
    webview.start(debug=dev, private_mode=False, storage_path=str(data_dir() / "webview"))
    render_server.stop()
    store.close()


if __name__ == "__main__":
    main()
