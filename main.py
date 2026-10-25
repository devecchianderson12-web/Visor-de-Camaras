"""The Watcher - punto de entrada (visor multicámara RTSP ultraligero)."""
import sys


def _fatal(text):
    """Mensaje claro (no un traceback) cuando no se puede iniciar."""
    shown = False
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, "The Watcher", 0x10)
            shown = True
        except Exception:
            pass
    else:                                          # Linux: abierto desde el menú no hay consola
        import shutil
        import subprocess
        for cmd in (["zenity", "--error", "--no-markup", "--title=The Watcher", "--text=" + text],
                    ["kdialog", "--error", text], ["xmessage", "-center", text]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, timeout=900)
                    shown = True
                    break
                except Exception:
                    pass
    if not shown and sys.stderr:
        print(text, file=sys.stderr)
    sys.exit(1)


def _qt_help(err):
    if sys.platform == "win32":
        return ("The Watcher no pudo cargar la interfaz (Qt).\n\n"
                "Se necesita Windows 8.1 de 64 bits o superior (Windows 8 original no está soportado).\n"
                "Reinstala con TheWatcher-Setup-Win81.exe o abre «Diagnóstico de The Watcher» desde el menú Inicio.\n\n"
                f"Detalle técnico:\n{err}")
    return ("The Watcher no pudo cargar la interfaz (Qt).\n\n"
            "En Linux suele faltar alguna librería del sistema. En Debian/Ubuntu/Mint:\n"
            "sudo apt install libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 "
            "libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libxcb-cursor0\n\n"
            f"Detalle técnico:\n{err}")


def _run_gui():
    if sys.platform == "win32":                # el icono propio también en la barra de tareas
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TheWatcher.Viewer")
        except Exception:
            pass
    try:
        import config
        from qt import QT_VERSION, QApplication, QIcon, Qt, qexec
        from mainwindow import MainWindow
    except ImportError as e:
        _fatal(_qt_help(e))
    if QT_VERSION == 5:                        # Qt5 pide el escalado HiDPI de forma explícita
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("TheWatcher")          # sin espacio: coincide con WM_CLASS del acceso en Linux
    if sys.platform.startswith("linux"):
        try:
            app.setDesktopFileName("thewatcher")   # une la ventana con thewatcher.desktop (icono)
        except Exception:
            pass
    app.setWindowIcon(QIcon(config.resource_path("assets/watcher.png")))
    win = MainWindow()
    win.resize(1280, 760)
    win.show()
    sys.exit(qexec(app))


def main():
    args = sys.argv[1:]
    if "--selftest" in args:                   # sin ventana: lo usa la compilación automática
        i = args.index("--selftest")
        out = args[i + 1] if len(args) > i + 1 else "selftest.txt"
        import diagnostics
        sys.exit(diagnostics.selftest(out))
    if "--diagnose" in args:                   # informe en ventana (acceso directo del instalador)
        import diagnostics
        sys.exit(diagnostics.show_report())
    _run_gui()


if __name__ == "__main__":
    main()
