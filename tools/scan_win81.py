"""Informativo: busca en los binarios importaciones de funciones que NO existen en Windows 8.1.
Uso: python tools/scan_win81.py dist/TheWatcher     (siempre termina con código 0)"""
import os
import sys

import pefile

WIN10_ONLY = {n.lower() for n in (
    "ProcessPrng", "SetThreadDescription", "GetThreadDescription", "SetProcessDpiAwarenessContext",
    "GetDpiForWindow", "GetDpiForSystem", "GetSystemMetricsForDpi", "AdjustWindowRectExForDpi",
    "EnableNonClientDpiScaling", "GetThreadDpiAwarenessContext", "SetThreadDpiAwarenessContext",
    "AreDpiAwarenessContextsEqual", "GetWindowDpiAwarenessContext", "SystemParametersInfoForDpi",
    "IsValidDpiAwarenessContext", "GetAwarenessFromDpiAwarenessContext")}


def scan(root):
    found = {}
    checked = 0
    for dp, _, files in os.walk(root):
        for f in files:
            if not f.lower().endswith((".dll", ".pyd", ".exe")):
                continue
            path = os.path.join(dp, f)
            try:
                pe = pefile.PE(path, fast_load=True)
                pe.parse_data_directories(directories=[
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                    pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
            except Exception:
                continue
            checked += 1
            for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
                for entry in getattr(pe, attr, []):
                    for imp in entry.imports:
                        name = (imp.name or b"").decode("ascii", "ignore")
                        if name.lower() in WIN10_ONLY:
                            found.setdefault(os.path.relpath(path, root), set()).add(name)
            pe.close()
    return checked, found


if __name__ == "__main__":
    checked, found = scan(sys.argv[1] if len(sys.argv) > 1 else "dist")
    print(f"Archivos revisados: {checked}")
    if not found:
        print("Sin importaciones exclusivas de Windows 10 (las cargadas dinámicamente no se detectan).")
    for f, names in sorted(found.items()):
        print(f"AVISO {f}: {', '.join(sorted(names))}")
    sys.exit(0)
