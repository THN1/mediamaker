#!/usr/bin/env bash
# build.sh - builds MediaMaker-<version>-x86_64.AppImage (Linux, x86_64).
#
# Usage:  bash packaging/appimage/build.sh [--keep]
#   The AppImage is written to packaging/appimage/out/. It contains Python, PySide6 and the Python packages (PyInstaller) and needs on the computer where it
#   runs: ffmpeg + ffprobe and VLC (libvlc with its plug-ins, e.g. the package vlc) from the system - they are NOT included (libvlc with its plug-ins and a ffmpeg cannot be moved without trouble;
#   and a ffmpeg with x264 is under the GPL, which would bring duties of its own).
#   --keep    keep the build folder (packaging/appimage/build/) for a look inside
#
# Needs (on the computer that builds): Python 3.10+ with venv, an internet connection (pip, and appimagetool is downloaded once), FUSE or
#   APPIMAGE_EXTRACT_AND_RUN=1. Build on a not too new distribution (e.g. Ubuntu 22.04 in a container or a virtual machine): an AppImage runs on
#   systems with the same or a newer glibc than the one it was built on.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$SRC/packaging/appimage/build"
OUT="$SRC/packaging/appimage/out"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

VERSION="$(python3 -c "import sys; sys.path.insert(0, '$SRC'); import version; print(version.VERSION)")"
case "$VERSION" in *-dev) echo "Note: this is a development version ($VERSION); public AppImages are built from the release branch." >&2 ;; esac

rm -rf "$WORK"
mkdir -p "$WORK" "$OUT"
cd "$WORK"

echo "== Python environment"
python3 -m venv venv
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r "$SRC/requirements.txt" pyinstaller

echo "== PyInstaller"
HIDDEN=()
for f in "$SRC"/*.py; do                       # the program imports some of its modules by name at run time: take them all
    name="$(basename "$f" .py)"
    [ "$name" = mediamaker ] || HIDDEN+=(--hidden-import "$name")
done
./venv/bin/pyinstaller --noconfirm --clean --name mediamaker --windowed \
    --paths "$SRC" --paths "$SRC/ui" --paths "$SRC/ui/generated" "${HIDDEN[@]}" \
    --hidden-import ui_frmMain --hidden-import vbqt \
    --add-data "$SRC/README.md:." --add-data "$SRC/CHANGELOG.md:." --add-data "$SRC/LICENSE:." --add-data "$SRC/MediaMaker.example.ini:." \
    --add-data "$SRC/icons:icons" --add-data "$SRC/ui/generated/icons:icons" \
    "$SRC/mediamaker.py" >pyinstaller.log 2>&1 || { tail -30 pyinstaller.log >&2; exit 1; }

# PyInstaller takes libvlc and libvlccore of the build computer into the bundle (python-vlc asks for them). VLC looks for its plug-ins next to its own
# libraries, so the copies in the bundle find none ("unknown option --avcodec-hw"): they are removed, the program then uses the VLC of the system.
find dist/mediamaker \( -name 'libvlc.so*' -o -name 'libvlccore.so*' \) -delete

# PyInstaller also copies libstdc++ and libgcc_s of the BUILD computer. They come first in the library path, are older than those of newer distributions, and the system's
# own libraries (VLC and its plugins, loaded into this process) then fail with "version GLIBCXX_3.4.32 not found". The system has them on every desktop, so they are left out.
# (The other libraries of the bundle stay: removing them makes systems without e.g. libgthread fail at the start. The programs we start do not see the bundle at all,
# see restore_library_path in mediamaker.py.)
rm -f dist/mediamaker/_internal/libstdc++.so* dist/mediamaker/_internal/libgcc_s.so*
ls dist/mediamaker/_internal | grep -c '\.so' | sed 's/^/   libraries in the bundle: /'

echo "== AppDir"
APPDIR="$WORK/MediaMaker.AppDir"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a dist/mediamaker "$APPDIR/usr/bin/"
cp "$SRC/packaging/mediamaker.png" "$APPDIR/mediamaker.png"
cp "$SRC/packaging/mediamaker.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/mediamaker.png"
sed 's|^Exec=.*|Exec=mediamaker %F|' "$SRC/packaging/mediamaker.desktop" > "$APPDIR/mediamaker.desktop"
cp "$APPDIR/mediamaker.desktop" "$APPDIR/usr/share/applications/"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/mediamaker/mediamaker" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "== appimagetool"
TOOL="$SRC/packaging/appimage/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
    curl -fL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT/MediaMaker-$VERSION-x86_64.AppImage"
echo "== Done: $OUT/MediaMaker-$VERSION-x86_64.AppImage"
[ "$KEEP" -eq 1 ] || rm -rf "$WORK"
