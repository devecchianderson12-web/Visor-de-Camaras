#!/usr/bin/env bash
# Desinstala The Watcher del usuario actual. Tu configuración (~/.config/TheWatcher) se conserva.
set -eu
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DATA/TheWatcher"
rm -f "$DATA/applications/thewatcher.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "The Watcher desinstalado. Configuración conservada en: ${XDG_CONFIG_HOME:-$HOME/.config}/TheWatcher"
