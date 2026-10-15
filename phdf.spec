# PyInstaller spec — build with: uv run pyinstaller phdf.spec --noconfirm
# Requires the frontend to be built first (npm --prefix frontend run build).
import sys
from pathlib import Path

root = Path(SPECPATH)
frontend = root / "frontend" / "dist"
if not (frontend / "index.html").exists():
    raise SystemExit("frontend/dist is missing — run `npm --prefix frontend run build` first.")

a = Analysis(
    [str(root / "backend" / "phdf" / "__main__.py")],
    pathex=[str(root / "backend")],
    datas=[(str(frontend), "frontend")],
    hiddenimports=[],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhDF",
    console=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="PhDF")

if sys.platform == "darwin":
    app = BUNDLE(coll, name="PhDF.app", bundle_identifier="io.github.phdf")
