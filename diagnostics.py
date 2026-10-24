"""Autodiagnóstico.
  TheWatcher.exe --diagnose            -> informe en una ventana (acceso directo del instalador)
  TheWatcher.exe --selftest <archivo>  -> prueba completa sin ventana (la usa la compilación automática)"""
import io
import os
import platform
import time
import sys
import traceback

from version import VERSION


def _winver():
    try:
        v = sys.getwindowsversion()
        return f"{v.major}.{v.minor}.{v.build}  (SP{v.service_pack_major})"
    except AttributeError:
        return platform.platform()


def _decode_test():
    """Codifica y decodifica unos fotogramas en memoria: comprueba que FFmpeg funciona."""
    import av
    import numpy as np
    buf = io.BytesIO()
    out = av.open(buf, "w", format="mpegts")
    st = out.add_stream("mpeg4", rate=10)
    st.width, st.height, st.pix_fmt = 64, 48, "yuv420p"
    for i in range(10):
        fr = av.VideoFrame.from_ndarray(np.full((48, 64, 3), i * 20, dtype=np.uint8), format="rgb24")
        for p in st.encode(fr):
            out.mux(p)
    for p in st.encode():
        out.mux(p)
    out.close()
    n = 0
    inp = av.open(io.BytesIO(buf.getvalue()), format="mpegts")
    for fr in inp.decode(video=0):
        fr.to_ndarray(width=32, height=24, format="rgb24")
        n += 1
    inp.close()
    return n


def _gui_check():
    """Crea las ventanas reales con Qt «offscreen» y las dibuja una vez."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    import layout as LY
    import qt
    from discovery_dialogs import NetScanDialog, OnvifDialog
    from layout_editor import LayoutDialog
    from mainwindow import MainWindow
    from ui import CamerasDialog

    app = qt.QApplication.instance() or qt.QApplication([])
    win = MainWindow()
    cam = {"id": "t1", "name": "Prueba", "ip": "127.0.0.1", "port": 554, "user": "a",
           "password": "", "channel": 1}
    win.cfg["cameras"] = [cam]
    win.rebuild()
    w = win.widgets[0]
    w._on_frame(np.zeros((48, 64, 3), np.uint8))
    win.resize(640, 360)
    win.show()
    app.processEvents()
    assert not win.grab().isNull()
    for mode in ("fill", "fit", "stretch"):               # los 3 ajustes de imagen
        win.set_fit_mode(mode)
        assert not win.grab().isNull()
    win.perf.set_active(True)                             # monitor de rendimiento
    win.perf._tick()
    assert not win.perf.grab().isNull()
    win.perf.set_active(False)
    assert w.build_menu().actions()                       # menú de calidad / resolución
    for dlg in (CamerasDialog([cam]), LayoutDialog([cam], LY.default_editor_layout([cam])),
                OnvifDialog(set()), NetScanDialog(set())):
        assert not dlg.grab().isNull()
        dlg._stop.set() if hasattr(dlg, "_stop") else None
    for x in list(win.widgets):
        x.shutdown()
    return "OK (Qt %s)" % qt.QT_VERSION_STR


def report(deep=False):
    """-> (texto, ok)"""
    lines, ok = [], True

    def add(k, v):
        lines.append(f"{k:<18}{v}")

    add("The Watcher", VERSION)
    add("Windows", _winver())
    add("Python", sys.version.split()[0] + (" (empaquetado)" if getattr(sys, "frozen", False) else ""))
    try:
        import numpy
        add("NumPy", numpy.__version__)
    except Exception as e:
        ok = False
        add("NumPy", "ERROR " + repr(e))
    try:
        import av
        add("PyAV", av.__version__)
        try:
            add("FFmpeg", ", ".join(f"{k} {'.'.join(map(str, v))}"
                                    for k, v in sorted(av.library_versions.items())[:3]))
        except Exception:
            pass
        import stream_manager
        add("Decod. por GPU", stream_manager._pick_hw() or "no disponible (decodifica por CPU)")
    except Exception as e:
        ok = False
        add("PyAV", "ERROR " + repr(e))
    try:
        import qt
        add("Qt", f"PyQt{qt.QT_VERSION}  (Qt {qt.QT_VERSION_STR})")
    except Exception as e:
        ok = False
        add("Qt", "ERROR " + repr(e))
    try:
        import sysmon
        b = sysmon._make_backend()
        b.cpu()
        time.sleep(0.4)
        c, r, g = b.cpu(), b.ram(), b.gpu()
        add("Monitor", f"CPU {c:.0f}%  RAM {r:.0f}%  GPU " + (f"{g:.0f}%" if g is not None else "n/d")
            + f"  [{b.gpu_source}]")
        b.close()
    except Exception as e:                                # aviso, no es fatal
        add("Monitor", "AVISO " + repr(e))
    if deep and ok:
        try:
            add("Ventanas (GUI)", _gui_check())
        except Exception:
            ok = False
            add("Ventanas (GUI)", "ERROR\n" + traceback.format_exc())
        try:
            add("Decodificación", f"OK ({_decode_test()} fotogramas)")
        except Exception as e:                            # aviso, no es fatal
            add("Decodificación", "AVISO " + repr(e))
    add("Resultado", "TODO CORRECTO" if ok else "HAY PROBLEMAS (envía este informe)")
    return "\n".join(lines), ok


def selftest(out_path):
    text, ok = report(deep=True)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    return 0 if ok else 1


def show_report():
    import config
    from qt import QApplication, QMessageBox
    app = QApplication.instance() or QApplication(sys.argv)
    text, ok = report(deep=False)
    path = os.path.join(config.data_dir(), "diagnostico.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        text += f"\n\nGuardado en:\n{path}"
    except OSError:
        pass
    QMessageBox.information(None, "The Watcher - Diagnóstico", text)
    return 0
