"""Windows: app info, file dialogs, opening / docking windows, closing, theme, zoom,
fullscreen, updates, settings and cleanup."""

import json
import os
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import webview

from phdf import __version__
from phdf.api.base import ApiBase
from phdf.api.core import CLOSE_WAIT, RELEASES_API, RELEASES_PAGE, SESSION_PREFIX
from phdf.paths import data_dir
from phdf.services import (
    titlebar,
    uizoom,
)


class WindowsApi(ApiBase):
    # --- app / windows ----------------------------------------------------------------------

    def app_info(self) -> dict[str, Any]:
        return {
            "name": "PhDF",
            "version": __version__,
            "renderBaseUrl": self._core.render_base_url,
            "windowId": self._window_id,
            "detached": self._window_id.startswith("d"),
            "platform": {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux"),
            "smoke": self._core.smoke,
        }

    def ui_ready(self, report: dict[str, Any]) -> None:
        """`--smoke-ui` only: the page started, opened the file and shows a page image (the
        report says what it saw). Written to `<data dir>/ui-ready.json`, then PhDF quits."""
        if not self._core.smoke:
            return
        ok = bool(report.get("pageImage")) and int(report.get("tabs", 0)) >= 1
        (data_dir() / "ui-ready.json").write_text(json.dumps({**report, "ok": ok}), "utf-8")
        for api in list(self._core.windows.values()):
            api.close_window()

    def startup_paths(self) -> list[str]:
        """Files PhDF was started with; handed to the first window that asks."""
        paths, self._core.startup_paths = self._core.startup_paths, []
        self._core.startup_taken = True
        return paths

    def pick_file(self, kind: str = "document") -> str | None:
        """File dialog. kind: "document" (PDF or Markdown), "pdf" or "md"."""
        window = self._window or webview.active_window()
        if window is None:
            return None
        types = {
            "document": (
                "Documents (*.pdf;*.epub;*.cbz;*.md)",
                "PDF files (*.pdf)",
                "EPUB books (*.epub)",
                "Comics (*.cbz)",
                "Markdown (*.md)",
            ),
            "pdf": ("PDF files (*.pdf)",),
            "md": ("Markdown (*.md)",),
        }[kind] + ("All files (*.*)",)
        result = window.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        return result[0] if result else None

    def pick_pdf(self) -> str | None:
        return self.pick_file("pdf")

    def pick_new_md(self, name: str = "Untitled.md") -> str | None:
        window = self._window or webview.active_window()
        if window is None:
            return None
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=name, file_types=("Markdown (*.md)",)
        )
        if not result:
            return None
        path = result if isinstance(result, str) else result[0]
        return path if path.lower().endswith(".md") else path + ".md"

    def open_window(
        self, paths: list[str], x: int | None = None, y: int | None = None, detached: bool = False
    ) -> str:
        """Open a new window showing `paths` as tabs. A tab dragged out becomes a `detached`
        window (id starts with "d"): just that document, docked back with Dock or at restart."""
        window_id = ("d" if detached else "") + uuid.uuid4().hex[:8]
        session = {"panes": [{"paths": paths, "active": 0, "width": 1}], "focused": 0}
        self._core.store.set_setting(SESSION_PREFIX + window_id, session)
        if self._core.create_window:
            self._core.create_window(window_id, x, y)
            # Take the references now, so a tab with unsaved annotations survives the move
            # while this window releases its own reference.
            if new := self._core.windows.get(window_id):
                for path in paths:
                    if path.lower().endswith(".pdf"):
                        new.open_document(path)
        return window_id

    def check_update(self) -> dict[str, Any]:
        """The latest published release on GitHub (Settings → General lets the user turn this
        off). Sends nothing but the request itself; any failure is just "unknown"."""
        import urllib.request

        request = urllib.request.Request(  # noqa: S310 - fixed https URL
            RELEASES_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"PhDF/{__version__}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=6) as response:  # noqa: S310
                data = json.load(response)
        except Exception:  # noqa: BLE001 - offline, no release yet, rate limit…
            return {"ok": False, "current": __version__}
        latest = str(data.get("tag_name", "")).lstrip("v")

        def parts(v: str) -> tuple[int, ...]:
            return tuple(int(n) for n in re.findall(r"\d+", v)[:3])

        return {
            "ok": bool(latest),
            "current": __version__,
            "latest": latest,
            "newer": bool(latest) and parts(latest) > parts(__version__),
            "url": data.get("html_url") or RELEASES_PAGE,
        }

    def make_default_app(self) -> dict[str, str]:
        """Help make PhDF the default PDF app. Windows doesn't let apps do it themselves: open
        Settings → Default apps (on PhDF's page when the installer registered it). Linux:
        xdg-mime when PhDF's .desktop file is installed. Otherwise: how to do it by hand."""
        if sys.platform == "win32":
            import winreg

            registered = False
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\RegisteredApplications") as key:
                        winreg.QueryValueEx(key, "PhDF")
                        registered = True
                except OSError:
                    pass
            os.startfile(  # noqa: S606
                "ms-settings:defaultapps?registeredAppUser=PhDF"
                if registered
                else "ms-settings:defaultapps"
            )
            return {"result": "settings" if registered else "settings-unregistered"}
        if sys.platform == "darwin":
            return {"result": "howto"}
        desktop = [
            Path.home() / ".local/share/applications/phdf.desktop",
            Path("/usr/share/applications/phdf.desktop"),
        ]
        if shutil.which("xdg-mime") and any(d.exists() for d in desktop):
            import subprocess

            subprocess.run(  # noqa: S603, S607
                ["xdg-mime", "default", "phdf.desktop", "application/pdf"], check=False
            )
            return {"result": "done"}
        return {"result": "howto"}

    def _on_closing(self) -> bool:
        """pywebview `closing` handler: returning False keeps the window open.

        The page always decides: only it knows about notes still being typed, grades, PDF Tools
        work and unsaved marks. It saves (or asks) and then calls `close_window`. Runs on the
        GUI thread, so nothing here may wait; a page that doesn't answer (`close_ack`) within
        CLOSE_WAIT seconds (not loaded yet, hung) is closed anyway."""
        if self._force_close or self._window is None:
            return True
        # evaluate_js would block the GUI thread we are on, so dispatch from a helper thread.
        threading.Thread(
            target=self._window.evaluate_js,
            args=("window.dispatchEvent(new CustomEvent('phdf:close-request'))",),
            daemon=True,
        ).start()
        self.close_ack()
        self._close_timer = threading.Timer(CLOSE_WAIT, self.close_window)
        self._close_timer.daemon = True
        self._close_timer.start()
        return False

    def close_ack(self) -> None:
        """The page took the close request (it may still ask the user, who may cancel)."""
        if self._close_timer is not None:
            self._close_timer.cancel()
            self._close_timer = None

    def window_theme(self, dark: bool) -> None:
        """Match the native title bar to the page's light / dark theme (Windows)."""
        self._dark = dark
        titlebar.apply(self._window, dark, self._fullscreen)

    def ui_zoom(self, factor: float) -> None:
        """Interface size (Settings → Appearance): zoom this window's web view."""
        uizoom.set_zoom(self._window, min(max(float(factor), 0.5), 2.0))

    def epub_text_size(self, size: float) -> list[dict[str, Any]]:
        """Text size of e-books (EPUB): remembered, and every open e-book of this window is laid
        out again. Returns their new page sizes (the page count changes)."""
        size = min(max(float(size), 7), 28)
        self._core.store.set_setting("epub.fontsize", size)
        engine = self._core.engine
        if hasattr(engine, "reflow"):
            engine.reflow = {**engine.reflow, "fontsize": size}
        changed = []
        with self._core.lock:
            for doc_id in self._open:
                doc = self._core.doc(doc_id)
                if not doc.info().reflowable or not hasattr(doc, "relayout"):
                    continue
                doc.relayout(engine.reflow)
                self._core.bump(doc_id)
                change = {
                    "pageSizes": [[round(w, 2), round(h, 2)] for w, h in doc.page_sizes()],
                    "revs": self._core.revs(doc_id),
                }
                changed.append({**change, "docId": doc_id})
                self._core.tell_windows(doc_id, "doc-reflowed", change, skip=self)
        return changed

    def toggle_fullscreen(self) -> None:
        if self._window is not None:
            self._window.toggle_fullscreen()
            # Square corners in full screen (else clicks in a corner reach the window behind);
            # rounded and themed again after it.
            self._fullscreen = not self._fullscreen
            titlebar.apply(self._window, self._dark, self._fullscreen)

    def close_window(self) -> None:
        """Close this window after the page has dealt with unsaved changes."""
        self.close_ack()
        self._force_close = True
        if self._window is not None:
            # A moment later, so this call's answer reaches the page before the webview is gone
            # (else pywebview logs "Cannot access a disposed object").
            later = threading.Timer(0.15, self._window.destroy)
            later.daemon = True
            later.start()

    # --- windows ---------------------------------------------------------------------------------

    def window_at(self, x: float, y: float, scale: float = 1.0) -> str | None:
        """Another PhDF window under a screen point (tab drag between windows). The point is in
        CSS pixels; window geometry may be in device pixels, so both are tried."""
        for wid, api in self._core.windows.items():
            win = api._window
            if wid == self._window_id or win is None:
                continue
            for px, py in ((x, y), (x * scale, y * scale)):
                if win.x <= px < win.x + win.width and win.y <= py < win.y + win.height:
                    return wid
        return None

    def dock(self, paths: list[str]) -> None:
        """A detached window's tabs go back into a main window (a new one if none is open)."""
        main = next((w for w in self._core.windows if not w.startswith("d")), None)
        if main is None:
            self.open_window(paths)
            return
        for path in paths:
            self.send_to_window(main, path)
        target = self._core.windows[main]._window
        if target is not None:
            threading.Thread(target=target.restore, daemon=True).start()

    def send_to_window(self, window_id: str, path: str) -> bool:
        """Move a tab to another open window: it takes its own reference first, then opens it."""
        target = self._core.windows.get(window_id)
        if target is None or target._window is None:
            return False
        if path.lower().endswith(".pdf"):
            target.open_document(path)
        target._show_path(path)
        return True

    def _show_path(self, path: str) -> None:
        """Open `path` as a tab in this window's page (from another thread: evaluate_js waits)."""
        if self._window is None:
            return
        event = f"new CustomEvent('phdf:open-path', {{detail: {json.dumps(path)}}})"
        script = f"window.dispatchEvent({event})"
        threading.Thread(target=self._window.evaluate_js, args=(script,), daemon=True).start()

    # --- settings ---------------------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._core.store.get_setting(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._core.store.set_setting(key, value)

    # --- lifecycle --------------------------------------------------------------------------

    def _on_closed(self) -> None:
        self._core.window_closed(self._window_id)
        # The rest can take a moment (stopping terminals waits for their processes, closing
        # the link preview needs the GUI thread on macOS): never on the thread that closes the
        # window, or the app freezes while quitting.
        threading.Thread(target=self._clean_up, daemon=True).start()

    def _clean_up(self) -> None:
        self.peek_close()
        for tid in list(self._tools):
            self.tools_close(tid)
        self._terminals.close_all()
        for png in list(self._snips):
            self.equation_cleanup(png)
        with self._core.lock:
            for doc_id in self._open:
                self._core.release(doc_id)
            self._open.clear()
