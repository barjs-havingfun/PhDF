"""Local HTTP server that streams rendered pages to the webview as plain <img> URLs.

Faster than pushing base64 through the JS bridge, and lets the browser cache, parallelize
and lazy-load images. Bound to 127.0.0.1 with a random per-session token in every path.

    GET /<token>/page/<doc_id>/<page>.png?s=<scale>[&clip=x0,y0,x1,y1]
"""

import contextlib
import re
import secrets
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from phdf.engine.base import Rect

RenderFn = Callable[[str, int, float, Rect | None], bytes | None]
CACHE_BYTES = 64 * 1024 * 1024  # recently served page images, kept here instead of in the webview

_PATH = re.compile(r"^/(?P<token>[\w-]+)/page/(?P<doc>[0-9a-f]{64})/(?P<page>\d+)\.png$")
MAX_SCALE = 8.0


class RenderServer:
    def __init__(self, render: RenderFn) -> None:
        self.token = secrets.token_urlsafe(16)
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_bytes = 0
        self._cache_lock = threading.Lock()
        self._rendering: dict[str, list[Any]] = {}  # key -> [lock, waiting requests]
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

    def _cached(self, key: str) -> bytes | None:
        with self._cache_lock:
            png = self._cache.get(key)
            if png is not None:
                self._cache.move_to_end(key)
            return png

    def _remember(self, key: str, png: bytes) -> None:
        if len(png) > CACHE_BYTES // 4:
            return
        with self._cache_lock:
            # Two requests for the same image may both miss and render it.
            if (old := self._cache.pop(key, None)) is not None:
                self._cache_bytes -= len(old)
            self._cache[key] = png
            self._cache_bytes += len(png)
            while self._cache_bytes > CACHE_BYTES:
                _, old = self._cache.popitem(last=False)
                self._cache_bytes -= len(old)

    @contextlib.contextmanager
    def _one_render(self, key: str) -> Iterator[None]:
        """Requests for the same image wait for one render instead of each doing it."""
        with self._cache_lock:
            entry = self._rendering.setdefault(key, [threading.Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._cache_lock:
                entry[1] -= 1
                if not entry[1]:
                    del self._rendering[key]

    def forget(self, doc_id: str) -> None:
        """Drop cached images of a closed document."""
        with self._cache_lock:
            for key in [k for k in self._cache if f"/page/{doc_id}/" in k]:
                self._cache_bytes -= len(self._cache.pop(key))

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

        png = self._cached(req.path)
        if png is None:
            with self._one_render(req.path):
                png = self._cached(req.path)  # rendered by a request we waited for
                if png is None:
                    try:
                        png = render(match["doc"], int(match["page"]), scale, clip)
                    except (IndexError, ValueError):
                        png = None
                    if png is not None:
                        self._remember(req.path, png)
        if png is None:
            req.send_error(HTTPStatus.NOT_FOUND)
            return

        req.send_response(HTTPStatus.OK)
        jpeg = png.startswith(b"\xff\xd8")
        req.send_header("Content-Type", "image/jpeg" if jpeg else "image/png")
        req.send_header("Content-Length", str(len(png)))
        # Don't let the webview keep every page it ever showed (hundreds of MB on big books);
        # re-requests are served from the small LRU cache above.
        req.send_header("Cache-Control", "no-store")
        req.send_header("Access-Control-Allow-Origin", "*")
        req.end_headers()
        # The view may have scrolled away and the browser cancelled the request.
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            req.wfile.write(png)
