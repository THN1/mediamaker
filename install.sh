#!/usr/bin/env bash
# install.sh - installs MediaMaker for one user (or, with --prefix, for everybody).
#
# Usage:  bash install.sh [--prefix DIR] [--uninstall]
#   (no option)     installs into ~/.local: the program in ~/.local/share/mediamaker, the command `mediamaker` in ~/.local/bin, the entry in the menu of
#                   the desktop and the icon. Your settings are in ~/.config/MediaMaker and stay when you uninstall.
#   --prefix DIR    another place, e.g. --prefix /usr/local (then run it with sudo)
#   --uninstall     removes what was installed
#
# MediaMaker needs: Python 3.10+, the Python packages in requirements.txt (PySide6, python-vlc, numpy, Pillow), ffmpeg and ffprobe, VLC (libvlc).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HOME/.local"
UNINSTALL=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)    PREFIX="${2:?--prefix needs a folder}"; shift 2 ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help)   awk 'NR > 1 { if (/^#/) { sub(/^# ?/, ""); print } else exit }' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

APP="$PREFIX/share/mediamaker"
BIN="$PREFIX/bin/mediamaker"
DESKTOP="$PREFIX/share/applications/mediamaker.desktop"
ICON="$PREFIX/share/icons/hicolor/256x256/apps/mediamaker.png"

if [ "$UNINSTALL" -eq 1 ]; then
    rm -rf "$APP"
    rm -f "$BIN" "$DESKTOP" "$ICON"
    echo "MediaMaker was removed from $PREFIX (your settings in ~/.config/MediaMaker are still there)."
    exit 0
fi

command -v python3 >/dev/null || { echo "python3 was not found." >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo "Python 3.10 or newer is needed." >&2; exit 1; }

missing=()
for mod in PySide6 vlc numpy PIL; do
    python3 -c "import $mod" 2>/dev/null || missing+=("$mod")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "These Python modules are missing: ${missing[*]}" >&2
    echo "Install them with your package manager (Arch: python-pyside6 python-vlc python-numpy python-pillow; Debian/Ubuntu: python3-pyside6.qtwidgets" >&2
    echo "python3-vlc python3-numpy python3-pil) or with:  python3 -m pip install --user -r requirements.txt" >&2
    echo "Then run this script again." >&2
    exit 1
fi
for tool in ffmpeg ffprobe; do
    command -v "$tool" >/dev/null || echo "Warning: $tool was not found in the PATH; MediaMaker needs it." >&2
done
python3 -c 'import vlc; vlc.libvlc_get_version()' 2>/dev/null || echo "Warning: libvlc was not found (install VLC); without it there is no preview." >&2

echo "== Installing into $PREFIX"
rm -rf "$APP"
mkdir -p "$APP" "$(dirname "$BIN")" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
(cd "$SRC" && tar --exclude='__pycache__' --exclude='./tests' --exclude='./ui/tests' --exclude='./ui/vorschau' --exclude='./tools' --exclude='./packaging' \
     --exclude='./.git' --exclude='MediaMaker.ini' --exclude='MediaMaker.json' --exclude='CHANGELOG_PRIVATE.md' -cf - .) | (cd "$APP" && tar -xf -)
if git -C "$SRC" rev-parse --show-toplevel >/dev/null 2>&1; then          # a clone: About shows the commit, which is read from the file COMMIT here
    git -C "$SRC" log -1 --format='%H%n%cI%n%s' > "$APP/COMMIT" 2>/dev/null || true
fi
cat > "$BIN" <<EOF
#!/usr/bin/env bash
exec python3 "$APP/mediamaker.py" "\$@"
EOF
chmod +x "$BIN"
cp "$SRC/packaging/mediamaker.png" "$ICON"
sed "s|^Exec=.*|Exec=$BIN %F|" "$SRC/packaging/mediamaker.desktop" > "$DESKTOP"
command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
echo "== Done. Start it with:  mediamaker [video.ts ...]   (or from the menu of the desktop)"
case ":$PATH:" in *":$PREFIX/bin:"*) ;; *) echo "   Note: $PREFIX/bin is not in your PATH." ;; esac
