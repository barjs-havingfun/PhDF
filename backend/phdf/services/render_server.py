"""Local HTTP server that streams rendered pages to the webview as plain <img> URLs.

Faster than pushing base64 through the JS bridge, and lets the browser cache, parallelize
and lazy-load images. Bound to 127.0.0.1 with a random per-session token in every path.

    GET /<token>/page/<doc_id>/<page>.png?s=<scale>[&clip=x0,y0,x1,y1]
"""

import contextlib
import re
import secrets
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from phdf.engine.base import Rect

RenderFn = Callable[[str, int, float, Rect | None], bytes | None]

_PATH = re.compile(r"^/(?P<token>[\w-]+)/page/(?P<doc>[0-9a-f]{64})/(?P<page>\d+)\.png$")
MAX_SCALE = 8.0


class RenderServer:
    def __init__(self, render: RenderFn) -> None:
        self.token = secrets.token_urlsafe(16)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
                server._handle(self, render)

            def log_message(self, *args: object) -> None:  # keep stdout quiet
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/{self.token}"

    def start(self) -> "RenderServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _handle(self, req: BaseHTTPRequestHandler, render: RenderFn) -> None:
        url = urlsplit(req.path)
        match = _PATH.match(url.path)
        if not match or not secrets.compare_digest(match["token"], self.token):
            req.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            query = parse_qs(url.query)
            scale = min(max(float(query.get("s", ["1"])[0]), 0.05), MAX_SCALE)
            clip = None
            if "clip" in query:
                x0, y0, x1, y1 = (float(v) for v in query["clip"][0].split(","))
                clip = (x0, y0, x1, y1)
        except ValueError:
            req.send_error(HTTPStatus.BAD_REQUEST)
            return

        try:
            png = render(match["doc"], int(match["page"]), scale, clip)
        except (IndexError, ValueError):
            png = None
        if png is None:
            req.send_error(HTTPStatus.NOT_FOUND)
            return

        req.send_response(HTTPStatus.OK)
        req.send_header("Content-Type", "image/png")
        req.send_header("Content-Length", str(len(png)))
        # doc_id is a content hash, so a URL's image never changes within a session.
        req.send_header("Cache-Control", "private, max-age=86400, immutable")
        req.send_header("Access-Control-Allow-Origin", "*")
        req.end_headers()
        # The view may have scrolled away and the browser cancelled the request.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            req.wfile.write(png)
