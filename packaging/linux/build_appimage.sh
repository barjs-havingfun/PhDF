#!/usr/bin/env bash
# Make PhDF-<version>-x86_64.AppImage from the PyInstaller build in dist/PhDF.
# Usage (after `uv run pyinstaller phdf.spec`): packaging/linux/build_appimage.sh 0.7.0
# Needs GTK and WebKitGTK 4.1 on the user's system (like any pywebview app on Linux).
set -euo pipefail
version="${1:?version}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
appdir="$root/dist/PhDF.AppDir"

rm -rf "$appdir"
mkdir -p "$appdir/usr/lib"
cp -r "$root/dist/PhDF" "$appdir/usr/lib/phdf"
cp "$root/packaging/linux/phdf.desktop" "$appdir/phdf.desktop"
cp "$root/packaging/icons/phdf.png" "$appdir/phdf.png"
cat > "$appdir/AppRun" <<'RUN'
#!/bin/sh
here="$(dirname "$(readlink -f "$0")")"
exec "$here/usr/lib/phdf/PhDF" "$@"
RUN
chmod +x "$appdir/AppRun"

tool="$root/dist/appimagetool"
if [ ! -x "$tool" ]; then
  curl -fsSL -o "$tool" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$tool"
fi
ARCH=x86_64 "$tool" --appimage-extract-and-run "$appdir" "$root/dist/PhDF-$version-x86_64.AppImage"
