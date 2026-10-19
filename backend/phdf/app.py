"""Entry point: creates the window(s) and wires the API.

Set PHDF_DEV=1 to load the Vite dev server (http://localhost:5173) with devtools enabled.
Variables can also come from a `.env` file in the project root (see `.env.example`).
"""

import mimetypes
import os
import shutil
import sys
import threading
from pathlib import Path

import webview

from phdf.api import SESSION_PREFIX, Api, Core
from phdf.db import Store
from phdf.engine import default_engine
from phdf.env import load_dotenv
from phdf.paths import data_dir, frontend_dist, icon_file
from phdf.services import ai_cache, macfiles, titlebar
from phdf.services.render_server import RenderServer

MAIN_WINDOW = "main"


def fix_mimetypes() -> None:
    """Windows registry often maps .js to text/plain, and WebView2 rejects ES modules served
    that way by pywebview's local HTTP server. Python's mimetypes reads the registry, so pin it."""
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    mimetypes.add_type("text/css", ".css")


def drop_stale_page_cache(index: Path, storage: Path) -> None:
    """pywebview serves the page from a fixed local address without cache headers, so WebView2
    may keep showing an old build's index.html. Empty its HTTP cache when the build changes."""
    stamp = storage / "build.txt"
    build = str(index.stat().st_mtime_ns)
    try:
        if stamp.read_text() == build:
            return
    except OSError:
        pass
    for name in ("Cache", "Code Cache"):
        shutil.rmtree(storage / "EBWebView" / "Default" / name, ignore_errors=True)
    storage.mkdir(parents=True, exist_ok=True)
    stamp.write_text(build)


def on_screen(x: int, y: int, width: int) -> bool:
    """Whether a window at x, y has its title bar on a connected monitor (a monitor that was
    unplugged leaves saved positions pointing at nothing)."""
    px, py = x + width // 2, y + 15
    if sys.platform == "darwin":
        # pywebview places windows from the top-left of the main screen; NSScreen frames count
        # from the bottom-left (webview.screens mixes the two), so flip y the same way.
        try:
            from AppKit import NSScreen  # type: ignore[import-not-found]

            height = NSScreen.mainScreen().frame().size.height
            cy = height - py
            return any(
                f.origin.x <= px < f.origin.x + f.size.width
                and f.origin.y <= cy < f.origin.y + f.size.height
                for f in (s.frame() for s in NSScreen.screens())
            )
        except Exception:  # noqa: BLE001 - screens unknown: keep the saved spot
            return True
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        return bool(user32.MonitorFromPoint(wintypes.POINT(px, py), 0))  # MONITOR_DEFAULTTONULL
    try:
        screens = webview.screens
        return any(s.x <= px < s.x + s.width and s.y <= py < s.y + s.height for s in screens)
    except Exception:  # noqa: BLE001 - screens unknown before the GUI starts on some backends
        return True


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

    def on_restored() -> None:
        save(maximized=False)

        # Un-maximizing goes back to the saved spot, which may be on a monitor that is gone.
        def bring_back() -> None:
            try:
                if not on_screen(window.x, window.y, window.width):
                    window.move(80, 80)
            except Exception:  # noqa: BLE001 - window closed meanwhile
                pass

        later = threading.Timer(0.3, bring_back)
        later.daemon = True
        later.start()

    window.events.restored += on_restored

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
        if path.suffix.lower() in (".pdf", ".epub", ".md") and path.is_file():
            paths.append(str(path.resolve()))
    return paths


def saved_window_ids(store: Store) -> list[str]:
    """Windows to restore. Migrates the single-window session format of v0.1.0."""
    if (legacy := store.get_setting("session")) is not None:
        store.delete_setting("session")
        if not store.settings_with_prefix(SESSION_PREFIX):
            store.set_setting(SESSION_PREFIX + MAIN_WINDOW, legacy)
    ids = [key.removeprefix(SESSION_PREFIX) for key in store.settings_with_prefix(SESSION_PREFIX)]
    # Detached windows (a dragged-out tab) don't come back on their own: their tabs dock into
    # a main window.
    main = next((i for i in ids if not i.startswith("d")), MAIN_WINDOW)
    for wid in [i for i in ids if i.startswith("d")]:
        tabs = [p for pane in (store.get_setting(SESSION_PREFIX + wid) or {}).get("panes", [])
                for p in pane.get("paths", [])]  # fmt: skip
        store.delete_setting(SESSION_PREFIX + wid)
        session = store.get_setting(SESSION_PREFIX + main) or {"panes": [], "focused": 0}
        if not session.get("panes"):
            session["panes"] = [{"paths": [], "active": 0, "width": 1}]
        pane = session["panes"][0]
        have = pane.setdefault("paths", [])
        have.extend(p for p in tabs if p not in have)
        store.set_setting(SESSION_PREFIX + main, session)
    ids = [i for i in ids if not i.startswith("d")]
    # Settings → General → "Start with an empty window": one window, its tabs not restored.
    if not store.get_setting("session.restore", True):
        ids = [MAIN_WINDOW] if MAIN_WINDOW in ids else ids[:1]
    return ids or [MAIN_WINDOW]


def per_monitor_dpi() -> None:
    """Windows: be DPI aware per monitor (before pywebview makes the process "system" aware).

    With monitors at different scaling (e.g. 150 % and 100 %), a system-aware window is
    stretched by Windows on the other monitor: blurry, and the stretched edges leave pixels
    where a click reaches the window behind (the owner's maximized window's top-right corner
    closed the app behind it). Must run before any window exists; later calls are ignored."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PMv2


def system_typelibs() -> None:
    """Linux app build: PyInstaller points GObject at its own typelibs only, and those lack
    WebKit2, which then is found only where Debian / Ubuntu keep it. Also look where Fedora,
    openSUSE and Arch do (the bundled ones stay first). Before pywebview loads GTK."""
    if not sys.platform.startswith("linux") or not getattr(sys, "frozen", False):
        return
    dirs = [
        d
        for d in (
            "/usr/lib/x86_64-linux-gnu/girepository-1.0",  # Debian, Ubuntu
            "/usr/lib64/girepository-1.0",  # Fedora, openSUSE
            "/usr/lib/girepository-1.0",  # Arch
        )
        if os.path.isdir(d)
    ]
    current = os.environ.get("GI_TYPELIB_PATH")
    os.environ["GI_TYPELIB_PATH"] = os.pathsep.join([current, *dirs] if current else dirs)


def main() -> None:
    system_typelibs()
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
        drop_stale_page_cache(index, data_dir() / "webview")

    store = Store(data_dir() / "phdf.db")
    if store.get_setting("window.perMonitorDpi", True):  # Settings → Appearance
        per_monitor_dpi()
    titlebar.app_id()
    engine = default_engine()
    if size := store.get_setting("epub.fontsize"):  # e-book text size (Read menu)
        engine.reflow = {**engine.reflow, "fontsize": float(size)}
    threading.Thread(
        target=ai_cache.cleanup, args=(ai_cache.folder(data_dir()),), daemon=True
    ).start()
    core = Core(engine, store)
    render_server = RenderServer(core.render).start()
    core.render_base_url = render_server.base_url
    core.on_closed_document = render_server.forget
    core.startup_paths = startup_paths(sys.argv[1:])

    def create_window(window_id: str, x: int | None = None, y: int | None = None) -> None:
        api = Api(core, window_id)
        key = f"window.{window_id}"
        detached = window_id.startswith("d")
        geo = {} if detached else store.get_setting(key) or {}
        title = "PhDF"
        if detached:  # a dragged-out tab: a smaller window named after its document
            session = store.get_setting(SESSION_PREFIX + window_id) or {}
            paths = [p for pane in session.get("panes", []) for p in pane.get("paths", [])]
            geo = {"width": 1000, "height": 760}
            title = f"{Path(paths[0]).name} - PhDF" if paths else "PhDF"
        lost = "x" in geo and not on_screen(geo["x"], geo.get("y", 0), geo.get("width", 1200))
        if x is None and lost:
            geo = {k: v for k, v in geo.items() if k not in ("x", "y")}  # centered instead
        window = webview.create_window(
            title, url, js_api=api,
            width=geo.get("width", 1200), height=geo.get("height", 800),
            x=x if x is not None else geo.get("x"), y=y if y is not None else geo.get("y"),
            maximized=bool(geo.get("maximized")), min_size=(640, 480), text_select=True,
        )  # fmt: skip
        if window is None:
            return
        api._window = window
        core.windows[window_id] = api
        # The native title bar in PhDF's colors (Windows), before the page sets it exactly.
        window.events.shown += lambda: titlebar.apply(window, titlebar.os_dark())
        window.events.closing += api._on_closing
        window.events.closed += api._on_closed
        if not detached:
            remember_geometry(window, key, store)

    core.create_window = create_window
    macfiles.listen(lambda paths: core.open_from_system(startup_paths(paths)))
    for window_id in saved_window_ids(store):
        create_window(window_id)

    webview.start(
        # Window / taskbar icon: Windows (WinForms) needs the .ico, GTK takes a PNG.
        icon=str(icon_file("phdf.ico" if sys.platform == "win32" else "phdf.png")),
        debug=dev,
        private_mode=False,
        storage_path=str(data_dir() / "webview"),
    )
    # Last window closed. Clean up, but never hang on the way out: if something is stuck (a
    # terminal process, a long engine call), leave anyway after a few seconds.
    finished = threading.Event()

    def clean_up() -> None:
        core.shutdown()
        render_server.stop()
        store.close()
        finished.set()

    threading.Thread(target=clean_up, daemon=True).start()
    if not finished.wait(5):
        os._exit(0)


if __name__ == "__main__":
    main()
