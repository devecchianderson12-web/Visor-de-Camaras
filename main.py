"""The Watcher - punto de entrada (visor multicámara RTSP ultraligero)."""
import sys


def _fatal(text):
    """Mensaje claro (no un traceback) cuando no se puede iniciar."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "The Watcher", 0x10)
    except Exception:
        if sys.stderr:
            print(text, file=sys.stderr)
    sys.exit(1)


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
        _fatal("The Watcher no pudo cargar la interfaz (Qt).\n\n"
               "• Windows 8.1: usa la versión «Win81» (TheWatcher-Setup-Win81.exe). Esta otra es para Windows 10/11.\n"
               "• Windows 8 original (6.2) no está soportado: se necesita 8.1 de 64 bits o superior.\n\n"
               f"Detalle técnico:\n{e}")
    if QT_VERSION == 5:                        # Qt5 pide el escalado HiDPI de forma explícita
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("The Watcher")
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
