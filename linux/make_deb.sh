#!/usr/bin/env bash
# Crea el paquete .deb (Debian / Ubuntu / antiX / Mint).
# Uso: linux/make_deb.sh <version> <carpeta_de_PyInstaller> <archivo_salida.deb>
set -euo pipefail
[ "$#" -eq 3 ] || { echo "Uso: $0 <version> <carpeta_pyinstaller> <salida.deb>"; exit 2; }
VERSION="$1"; DIST="$2"; OUT="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
ICONS="$HERE/../assets/icons"
[ -x "$DIST/TheWatcher" ] || { echo "No existe $DIST/TheWatcher"; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

install -d "$STAGE/DEBIAN" "$STAGE/opt" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
           "$STAGE/usr/share/pixmaps" "$STAGE/usr/share/doc/thewatcher"
cp -a "$DIST" "$STAGE/opt/thewatcher"
chmod -R u+rwX,go+rX,go-w "$STAGE/opt/thewatcher"          # archivos legibles por todos, escribibles solo por root
ln -s /opt/thewatcher/TheWatcher "$STAGE/usr/bin/thewatcher"
install -m 644 "$HERE/deb/thewatcher.desktop" "$STAGE/usr/share/applications/thewatcher.desktop"
install -m 644 "$HERE/deb/copyright" "$STAGE/usr/share/doc/thewatcher/copyright"
for s in 48 64 128 256; do
    install -D -m 644 "$ICONS/thewatcher-$s.png" "$STAGE/usr/share/icons/hicolor/${s}x${s}/apps/thewatcher.png"
done
install -m 644 "$ICONS/thewatcher-48.png" "$STAGE/usr/share/pixmaps/thewatcher.png"   # menús antiguos (IceWM, JWM...)

install -m 755 "$HERE/deb/postinst" "$STAGE/DEBIAN/postinst"
install -m 755 "$HERE/deb/postrm" "$STAGE/DEBIAN/postrm"
SIZE="$(du -sk "$STAGE" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" -e "s/@SIZE@/$SIZE/" "$HERE/deb/control.in" > "$STAGE/DEBIAN/control"
chmod 644 "$STAGE/DEBIAN/control"

dpkg-deb --root-owner-group -Zxz -z6 --build "$STAGE" "$OUT" >/dev/null
echo "Creado: $OUT ($(du -h "$OUT" | cut -f1))"
