"""Make PhDF's icons from logo.png (1024×1024, transparent). After changing the logo, run:

    uv run python packaging/make_icons.py

Writes packaging/icons/phdf.ico (Windows exe / window), phdf.icns (macOS app), phdf.png (Linux,
512 px) and frontend/src/assets/logo.png (256 px, shown in the app). ICO and ICNS simply hold
PNGs, so no image library is needed beyond PyMuPDF.
"""

import struct
from pathlib import Path

import pymupdf

root = Path(__file__).resolve().parents[1]
logo = pymupdf.Pixmap(str(root / "logo.png"))
out = root / "packaging" / "icons"
out.mkdir(parents=True, exist_ok=True)


def png(size: int) -> bytes:
    return pymupdf.Pixmap(logo, size, size).tobytes("png")


# Windows: a directory of PNG images (Vista+ reads PNG entries).
sizes = [16, 24, 32, 48, 64, 128, 256]
images = [png(s) for s in sizes]
ico = struct.pack("<HHH", 0, 1, len(sizes))
offset = 6 + 16 * len(sizes)
for s, data in zip(sizes, images, strict=True):
    ico += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
(out / "phdf.ico").write_bytes(ico + b"".join(images))

# macOS: typed PNG entries.
entries = b""
ICNS = [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256), ("ic09", 512)]
for kind, s in [*ICNS, ("ic10", 1024)]:
    data = png(s)
    entries += kind.encode() + struct.pack(">I", 8 + len(data)) + data
(out / "phdf.icns").write_bytes(b"icns" + struct.pack(">I", 8 + len(entries)) + entries)

(out / "phdf.png").write_bytes(png(512))
assets = root / "frontend" / "src" / "assets"
assets.mkdir(parents=True, exist_ok=True)
(assets / "logo.png").write_bytes(png(256))
print("icons written to", out, "and", assets / "logo.png")
