"""The Watcher - punto de entrada (visor multicámara RTSP ultraligero)."""
import sys


def _run_gui():
    if sys.platform == "win32":                # el icono propio también en la barra de tareas
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TheWatcher.Viewer")
        except Exception:
            pass
    import config
    from qt import QT_VERSION, QApplication, QIcon, Qt, qexec
    if QT_VERSION == 5:                        # Qt5 pide el escalado HiDPI de forma explícita
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    from mainwindow import MainWindow
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
