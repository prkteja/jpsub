#!/bin/sh
# Install or remove the jpsub binary for the current user.
#
#   ./install.sh               install to ~/.local/bin (or $PREFIX/bin)
#   ./install.sh --uninstall   remove it again
#
# Run it from an extracted release, or from a source checkout after ./build.sh.
set -eu

PREFIX="${PREFIX:-$HOME/.local}"
BIN_DIR="$PREFIX/bin"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/jpsub"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$BIN_DIR/jpsub"
  echo "Removed $BIN_DIR/jpsub."
  if [ -d "$DATA_DIR" ]; then
    echo "Models, dictionary and settings are still in $DATA_DIR"
    echo "(about 330 MB); delete that folder to remove them too."
  fi
  exit 0
fi

if [ -f "$HERE/jpsub" ] && [ -x "$HERE/jpsub" ]; then
  binary="$HERE/jpsub"
elif [ -x "$HERE/dist/jpsub" ]; then
  binary="$HERE/dist/jpsub"
else
  echo "No jpsub binary next to this script. In a source checkout, run ./build.sh first." >&2
  exit 1
fi

mkdir -p "$BIN_DIR"
install -m 755 "$binary" "$BIN_DIR/jpsub"
echo "Installed jpsub to $BIN_DIR/jpsub"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Note: $BIN_DIR is not on your PATH; add it, or run $BIN_DIR/jpsub directly." ;;
esac

# Report missing system programs; jpsub itself does not need root.
missing=0
if ! command -v parec >/dev/null 2>&1; then
  missing=1
  echo
  echo "Missing: parec (captures system audio). Install it with one of:"
  echo "  Fedora: sudo dnf install pulseaudio-utils"
  echo "  Debian/Ubuntu: sudo apt install pulseaudio-utils"
  echo "  Arch: sudo pacman -S libpulse"
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo
  echo "Optional: ffmpeg, needed only for 'jpsub --file'."
fi
if ! /usr/bin/python3 -c 'import gi, cairo; gi.require_version("Gtk", "3.0"); gi.require_version("WebKit2", "4.1")' >/dev/null 2>&1; then
  echo
  echo "Optional: the floating subtitle window (jpsub --overlay) needs GTK and WebKitGTK:"
  echo "  Fedora: sudo dnf install python3-gobject gtk3 webkit2gtk4.1 gtk-layer-shell"
  echo "  Debian/Ubuntu: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-gtklayershell-0.1"
  echo "  Arch: sudo pacman -S python-gobject python-cairo gtk3 webkit2gtk-4.1 gtk-layer-shell"
fi

echo
if [ "$missing" = 0 ]; then
  echo "Start it with:  jpsub --overlay"
else
  echo "Once parec is installed, start it with:  jpsub --overlay"
fi
echo "The first run downloads the speech model and dictionary (about 250 MB) after asking."
