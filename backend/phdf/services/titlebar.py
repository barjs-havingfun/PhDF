"""Windows: color the native title bar like PhDF's toolbar, light or dark.

Keeps the real frame (resize, Snap Layouts, shadows) and only changes it through DWM: caption /
text / border colors and square corners on Windows 11; Windows 10 (2004+) gets the dark bar
only. Other systems keep their native look.

In full screen the corners must be square: a rounded corner leaves pixels that aren't the
window, and a click there reaches the window behind (e.g. its close button).
"""

import ctypes
import sys
from typing import Any

# The toolbar's color over the page area (see --toolbar / --canvas in app.css), and the text.
LIGHT = {"caption": (0xF3, 0xF3, 0xF5), "text": (0x1D, 0x1D, 0x1F)}
DARK = {"caption": (0x29, 0x29, 0x2B), "text": (0xF5, 0xF5, 0xF7)}

_DARK_MODE, _CORNERS, _BORDER, _CAPTION, _TEXT = 20, 33, 34, 35, 36  # DWMWINDOWATTRIBUTE
_SQUARE = 1  # DWMWCP_DONOTROUND
_NO_BORDER = 0xFFFFFFFE  # DWMWA_COLOR_NONE


def _colorref(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return r | (g << 8) | (b << 16)


def os_dark() -> bool:
    """Windows' "apps use dark mode" setting."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def apply(window: Any, dark: bool, fullscreen: bool = False) -> None:
    """Style a pywebview window's frame. Does nothing where it isn't supported."""
    if sys.platform != "win32" or window is None:
        return
    try:
        hwnd = ctypes.c_void_p(window.native.Handle.ToInt64())
    except Exception:  # noqa: BLE001 - not created yet / another GUI backend
        return
    colors = DARK if dark else LIGHT

    def set_attr(attr: int, value: int) -> None:
        v = ctypes.c_uint(value)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))

    set_attr(_DARK_MODE, 1 if dark else 0)
    set_attr(_CORNERS, _SQUARE)  # square corners (owner's choice; and no click-through gaps)
    set_attr(_CAPTION, _colorref(colors["caption"]))
    set_attr(_TEXT, _colorref(colors["text"]))
    set_attr(_BORDER, _NO_BORDER if fullscreen else _colorref(colors["caption"]))
