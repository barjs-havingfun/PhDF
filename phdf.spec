# PyInstaller spec — build with: uv run pyinstaller phdf.spec --noconfirm
# Requires the frontend to be built first (npm --prefix frontend run build).
import re
import sys
from pathlib import Path

root = Path(SPECPATH)
version = re.search(r'__version__ = "([^"]+)"', (root / "backend" / "phdf" / "__init__.py").read_text()).group(1)
frontend = root / "frontend" / "dist"
if not (frontend / "index.html").exists():
    raise SystemExit("frontend/dist is missing — run `npm --prefix frontend run build` first.")

a = Analysis(
    [str(root / "backend" / "phdf" / "__main__.py")],
    pathex=[str(root / "backend")],
    datas=[
        (str(frontend), "frontend"),
        (str(root / "packaging" / "icons"), "icons"),
        # The license, the third-party notices and the privacy policy travel with the app.
        *[(str(root / name), ".") for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "PRIVACY.md")],
    ],
    hiddenimports=[],
    excludes=["tkinter"],
)
if sys.platform.startswith("linux"):
    # WebKitGTK always comes from the user's distro (it can't be bundled), and it needs the
    # distro's GLib / GTK stack: older copies from the build machine (Ubuntu 22.04) would load
    # first and lack newer symbols (g_once_init_enter_pointer...). Every distro with WebKitGTK
    # has these, and newer versions still serve code built against older ones.
    system_libs = re.compile(
        r"^lib(glib|gobject|gio|gmodule|gthread)-2\.0\.so|^lib(gtk|gdk|gdk_pixbuf)-[0-9.]+\.so"
        r"|^lib(pango|cairo|harfbuzz|fontconfig|freetype|atk|atspi|epoxy|wayland|xkbcommon"
        r"|X|xcb|gudev|javascriptcoregtk|webkit2gtk|soup|gst|pixman|png16|stdc\+\+|gcc_s)"
    )
    a.binaries = [b for b in a.binaries if not system_libs.match(Path(b[0]).name)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhDF",
    console=False,
    icon=str(root / "packaging" / "icons" / "phdf.ico"),
    # macOS hands double-clicked files over as an "open" event; turn it into argv at launch.
    argv_emulation=sys.platform == "darwin",
)

coll = COLLECT(exe, a.binaries, a.datas, name="PhDF")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PhDF.app",
        icon=str(root / "packaging" / "icons" / "phdf.icns"),
        bundle_identifier="io.github.phdf",
        version=version,
        info_plist={
            "CFBundleName": "PhDF",
            "CFBundleDisplayName": "PhDF",
            "CFBundleShortVersionString": version,
            "NSHighResolutionCapable": True,  # sharp text on Retina screens
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,  # follow dark mode
            # Finder's "Open With" lists PhDF for these; it can be made the default there.
            "CFBundleDocumentTypes": [
                {"CFBundleTypeName": "PDF document", "CFBundleTypeRole": "Viewer",
                 "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]},
                {"CFBundleTypeName": "EPUB book", "CFBundleTypeRole": "Viewer",
                 "LSHandlerRank": "Alternate", "LSItemContentTypes": ["org.idpf.epub-container"]},
                {"CFBundleTypeName": "Markdown note", "CFBundleTypeRole": "Editor",
                 "LSHandlerRank": "Alternate",
                 "LSItemContentTypes": ["net.daringfireball.markdown"]},
            ],
        },
    )
