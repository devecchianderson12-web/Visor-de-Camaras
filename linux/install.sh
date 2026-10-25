#!/usr/bin/env bash
# Instala The Watcher solo para tu usuario (no hace falta administrador).
set -eu
SRC="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APP="$DATA/TheWatcher"
APPS="$DATA/applications"

echo "Instalando The Watcher en: $APP"
mkdir -p "$DATA" "$APPS"
if [ "$SRC" != "$APP" ]; then
    rm -rf "$APP"
    mkdir -p "$APP"
    cp -a "$SRC/." "$APP/"
fi
chmod +x "$APP/TheWatcher"

cat > "$APPS/thewatcher.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=The Watcher
Comment=Visor multicámara RTSP / ONVIF
Exec="$APP/TheWatcher"
Icon=$APP/watcher.png
Terminal=false
Categories=AudioVideo;Video;Network;
StartupWMClass=TheWatcher
DESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true

# Comprueba que el sistema tiene las librerías que necesita Qt para abrir ventanas.
QXCB="$(find "$APP" -name 'libqxcb.so' 2>/dev/null | head -n 1)"
if [ -n "$QXCB" ] && command -v ldd >/dev/null 2>&1; then
    QTLIB="$(dirname "$QXCB")/../../lib"
    MISSING="$(LD_LIBRARY_PATH="$QTLIB:$APP/_internal:$APP" ldd "$QXCB" 2>/dev/null | grep 'not found' || true)"
    if [ -n "$MISSING" ]; then
        echo
        echo "ATENCIÓN: faltan librerías del sistema:"
        echo "$MISSING"
        echo
        echo "  Debian / Ubuntu / Mint:  sudo apt install libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \\"
        echo "      libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libxcb-cursor0"
        echo "  Fedora:  sudo dnf install xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11"
        echo "  Arch:    sudo pacman -S xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11"
    fi
fi

echo
echo "Listo. Búscalo como «The Watcher» en el menú de aplicaciones, o ejecuta: $APP/TheWatcher"
echo "Diagnóstico si algo falla:  $APP/TheWatcher --diagnose"
