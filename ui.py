"""Widgets: vídeo por cámara (clic derecho = calidad) y gestor de cámaras."""
import uuid

import time

from qt import (event_pos, pyqtSignal, QAction, QActionGroup, QApplication, QByteArray, QColor,
               QDialog, QDialogButtonBox, QDrag, qexec, QFormLayout, QHBoxLayout, QImage, QLineEdit,
               QListWidget, QMenu, QMimeData, QObject, QPainter, QPen, QPixmap, QPushButton, QRect, QRectF,
               Qt, QTimer, QVBoxLayout, QWidget)

from stream_manager import QUALITIES, QUALITY_SUB, CameraWorker, cover_crop, fit_rect
from sysmon import SysMonitor


PERF_OPACITY = ((1.0, "100 %"), (0.8, "80 %"), (0.6, "60 %"), (0.4, "40 %"), (0.2, "20 %"))
PERF_INTERVALS = ((1.0, "Cada 1 s"), (2.0, "Cada 2 s (recomendado)"), (5.0, "Cada 5 s (mínimo consumo)"))
FPS_OPTIONS = ((8, "8 fps (ahorra CPU)"), (12, "12 fps"), (15, "15 fps"), (20, "20 fps"),
               (25, "25 fps"), (30, "30 fps"), (0, "Todos los fotogramas"))
FIT_OPTIONS = (("stretch", "Estirar (sin barras negras)"), ("fill", "Llenar (recorta los bordes)"),
               ("fit", "Original (con barras negras)"))
RES_OPTIONS = ((0, "Automática"), (720, "720p"), (480, "480p"), (360, "360p"), (240, "240p"))


class _Signals(QObject):
    frame = pyqtSignal(object)
    status = pyqtSignal(str)


class VideoWidget(QWidget):
    def __init__(self, cam, app):
        super().__init__()
        self.cam, self.app = cam, app
        self.setMinimumSize(160, 90)
        self.setAcceptDrops(True)
        self._press = None
        self._drop = False
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        f = self.font()
        f.setPointSize(9)
        self._font = f                                  # se crea una vez, no en cada repintado
        self._label_key, self._label, self._label_w = None, "", 0
        self._img = None
        self._arr = None
        self._pending = False                 # ya hay un fotograma esperando a ser dibujado
        self._n, self._t0, self.fps_now = 0, time.monotonic(), 0.0
        self._status = "Conectando…"
        self._sig = _Signals()
        self._sig.frame.connect(self._on_frame)
        self._sig.status.connect(self._on_status)
        cfg = app.cfg
        self.worker = CameraWorker(cam, cfg["url_template"], cfg["hwaccel"], cfg["fps_grid"],
                                   self._emit_frame, self._sig.status.emit)
        self.worker.fit_mode = cfg.get("fit_mode", "stretch")
        self.worker.start()

    def _emit_frame(self, arr):
        """Hilo de la cámara. Si la UI aún no dibujó el anterior, lo descarta: nunca se acumula cola."""
        if self._pending:
            return
        self._pending = True
        self._sig.frame.emit(arr)

    # ---- señales (hilo de la UI) ----
    def _on_frame(self, arr):
        self._pending = False
        self._n += 1
        now = time.monotonic()
        if now - self._t0 >= 1.0:                          # FPS realmente mostrados
            self.fps_now, self._n, self._t0 = self._n / (now - self._t0), 0, now
        h, w, _ = arr.shape
        self._arr = arr  # mantiene vivo el buffer que usa QImage
        self._img = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._status = ""
        self.update()

    def _on_status(self, text):
        self._img, self._arr, self._status = None, None, text
        self._pending, self.fps_now = False, 0.0
        self.update()

    # ---- calidad ----
    def set_quality(self, quality, save=True):
        self.worker.set_quality(quality)
        self.cam["quality"] = quality
        if save:
            self.app.save()
        self.update()

    def set_resolution(self, height):
        """Tope de resolución mostrada. No reconecta: se aplica al siguiente fotograma."""
        self.worker.max_h = height
        if height:
            self.cam["res"] = height
        else:
            self.cam.pop("res", None)
        self.app.save()
        self.update()

    def shutdown(self):
        self.worker.stop()

    # ---- eventos ----
    # ---- arrastrar y soltar: intercambiar posición (sin recargar streams) ----
    MIME = "application/x-icsee-cam"

    def mousePressEvent(self, e):
        self._press = event_pos(e) if e.button() == Qt.MouseButton.LeftButton else None

    def mouseReleaseEvent(self, e):
        self._press = None

    def mouseMoveEvent(self, e):
        if (self._press is None or not (e.buttons() & Qt.MouseButton.LeftButton)
                or self.app.zoomed is not None or len(self.app.widgets) < 2):
            return
        if (event_pos(e) - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        mime = QMimeData()
        mime.setData(self.MIME, QByteArray(str(self.cam["id"]).encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        if self._img is not None:                 # miniatura de un solo fotograma
            pm = QPixmap.fromImage(self._img).scaledToWidth(180)
        else:
            pm = QPixmap(180, 100)
            pm.fill(QColor(30, 30, 30))
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        qexec(drag, Qt.DropAction.MoveAction)

    def _drag_id(self, e):
        m = e.mimeData()
        return bytes(m.data(self.MIME)).decode() if m.hasFormat(self.MIME) else None

    def dragEnterEvent(self, e):
        src = self._drag_id(e)
        if src and src != self.cam["id"]:
            self._drop = True
            self.update()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._drop = False
        self.update()

    def dropEvent(self, e):
        src = self._drag_id(e)
        self._drop = False
        self.update()
        if src and src != self.cam["id"]:
            e.acceptProposedAction()
            self.app.swap_cameras(src, self.cam["id"])

    def resizeEvent(self, e):
        dpr = self.devicePixelRatioF()
        self.worker.target = (max(16, int(self.width() * dpr)), max(16, int(self.height() * dpr)))

    def mouseDoubleClickEvent(self, e):
        self.app.toggle_zoom(self)

    def contextMenuEvent(self, e):
        qexec(self.build_menu(), e.globalPos())

    def build_menu(self):
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        for q in QUALITIES:
            act = QAction(q, menu)
            act.setCheckable(True)
            act.setChecked(q == self.worker.quality)
            act.triggered.connect(lambda _=False, q=q: self.set_quality(q))
            group.addAction(act)
            menu.addAction(act)
        res_menu = menu.addMenu("Resolución")
        rgroup = QActionGroup(res_menu)
        rgroup.setExclusive(True)
        for h, label in RES_OPTIONS:
            ract = QAction(label, res_menu)
            ract.setCheckable(True)
            ract.setChecked(h == self.worker.max_h)
            ract.triggered.connect(lambda _=False, h=h: self.set_resolution(h))
            rgroup.addAction(ract)
            res_menu.addAction(ract)
        fit_menu = menu.addMenu("Ajuste de imagen")
        fgroup = QActionGroup(fit_menu)
        fgroup.setExclusive(True)
        for mode, label in FIT_OPTIONS:
            fact = QAction(label, fit_menu)
            fact.setCheckable(True)
            fact.setChecked(mode == self.app.cfg.get("fit_mode", "stretch"))
            fact.triggered.connect(lambda _=False, m=mode: self.app.set_fit_mode(m))
            fgroup.addAction(fact)
            fit_menu.addAction(fact)
        fps_menu = menu.addMenu("Fluidez (FPS)")
        ggroup = QActionGroup(fps_menu)
        ggroup.setExclusive(True)
        for value, label in FPS_OPTIONS:
            gact = QAction(label, fps_menu)
            gact.setCheckable(True)
            gact.setChecked(value == self.app.cfg.get("fps_grid", 12))
            gact.triggered.connect(lambda _=False, v=value: self.app.set_fps(v))
            ggroup.addAction(gact)
            fps_menu.addAction(gact)
        fps_menu.addSeparator()
        show = fps_menu.addAction("Mostrar FPS reales en la imagen")
        show.setCheckable(True)
        show.setChecked(bool(self.app.cfg.get("show_fps")))
        show.triggered.connect(lambda _=False: self.app.toggle_show_fps())
        pmenu = menu.addMenu("Monitor de rendimiento")
        pshow = pmenu.addAction("Mostrar")
        pshow.setCheckable(True)
        pshow.setChecked(bool(self.app.cfg.get("perf_monitor", True)))
        pshow.triggered.connect(lambda _=False: self.app.toggle_perf())
        op_now = float(self.app.cfg.get("perf_opacity", 0.85))
        omenu = pmenu.addMenu(f"Opacidad ({op_now * 100:.0f} %)")
        ogroup = QActionGroup(omenu)
        ogroup.setExclusive(True)
        for v, label in PERF_OPACITY:
            oact = QAction(label, omenu)
            oact.setCheckable(True)
            oact.setChecked(abs(v - op_now) < 0.01)
            oact.triggered.connect(lambda _=False, v=v: self.app.set_perf_opacity(v))
            ogroup.addAction(oact)
            omenu.addAction(oact)
        omenu.addSeparator()
        omenu.addAction("Aumentar (+10 %)", lambda: self.app.step_perf_opacity(0.1))
        omenu.addAction("Disminuir (−10 %)", lambda: self.app.step_perf_opacity(-0.1))
        imenu = pmenu.addMenu("Actualización")
        igroup = QActionGroup(imenu)
        igroup.setExclusive(True)
        for sec, label in PERF_INTERVALS:
            iact = QAction(label, imenu)
            iact.setCheckable(True)
            iact.setChecked(abs(sec - float(self.app.cfg.get("perf_interval", 2.0))) < 0.01)
            iact.triggered.connect(lambda _=False, sec=sec: self.app.set_perf_interval(sec))
            igroup.addAction(iact)
            imenu.addAction(iact)
        menu.addSeparator()
        if self.app.cfg.get("layout_mode") in ("focus", "pano"):
            menu.addAction("Hacer principal (la grande)", lambda: self.app.make_primary(self.cam))
        menu.addAction("Salir de pantalla completa" if self.app.isFullScreen() else "Pantalla completa (F11)",
                       self.app.toggle_fullscreen)
        menu.addAction("Personalizar cuadrícula…", self.app.customize_layout)
        menu.addAction("Administrar cámaras…", self.app.manage_cameras)
        return menu

    def paintEvent(self, ev):
        p = QPainter(self)
        img = self._img
        mode = self.app.cfg.get("fit_mode", "stretch")
        if img is None or mode == "fit":                       # con «estirar/llenar» la imagen cubre todo:
            p.fillRect(self.rect(), Qt.GlobalColor.black)      # no se pinta el fondo (menos trabajo por cuadro)
        if img is not None:
            iw, ih, W, H = img.width(), img.height(), self.width(), self.height()
            if mode == "fit":                                  # proporción original, con barras
                p.drawImage(QRect(*fit_rect(iw, ih, W, H)), img)
            elif mode == "fill":                               # llena el recuadro recortando los bordes
                p.drawImage(QRect(0, 0, W, H), img, QRect(*cover_crop(iw, ih, W, H)))
            else:                                              # estirar: sin barras negras
                p.drawImage(QRect(0, 0, W, H), img)
        p.setFont(self._font)
        if self._status:
            p.setPen(QColor(170, 170, 170))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._status)
        show = bool(self.app.cfg.get("show_fps") and self.fps_now)
        key = (self.cam.get("name"), self.worker.quality, self.worker.max_h,
               round(self.fps_now) if show else None, round(self.worker.src_fps) if show else None)
        if key != self._label_key:                             # texto y ancho solo se recalculan si cambian
            label = f"{self.cam.get('name', 'Cámara')}  ·  {self.worker.quality}"
            if self.worker.max_h:
                label += f"  ·  {self.worker.max_h}p"
            if show:
                src = self.worker.src_fps
                label += f"  ·  {self.fps_now:.0f}" + (f"/{src:.0f}" if src else "") + " fps"
            self._label_key, self._label = key, label
            self._label_w = p.fontMetrics().horizontalAdvance(label) + 16
        p.fillRect(0, 0, self._label_w, 20, QColor(0, 0, 0, 150))
        p.setPen(QColor(225, 225, 225))
        p.drawText(8, 14, self._label)
        if self._drop:                            # resalta el destino mientras arrastras
            p.setPen(QPen(QColor(110, 170, 255), 4))
            p.drawRect(self.rect().adjusted(2, 2, -2, -2))


class _PerfSignals(QObject):
    sample = pyqtSignal(object)


class PerfBadge(QWidget):
    """Pastilla redondeada arriba al centro con CPU / RAM / GPU del sistema.
    Pensada para gastar casi nada: no tiene temporizador propio (la muestra llega del hilo del monitor),
    solo se redibuja si cambia algún número, y el dibujo se guarda en un pixmap, de modo que cada
    repintado (p. ej. cuando llega un cuadro de la cámara que está debajo) cuesta un único drawPixmap."""
    LABELS = ("CPU", "RAM", "GPU")

    def __init__(self, parent, opacity=0.85, interval=2.0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)   # no estorba los clics
        f = self.font()
        f.setPointSize(9)
        f.setBold(True)
        self.setFont(f)
        self._sig = _PerfSignals()
        self._sig.sample.connect(self._on_sample)
        self.mon = SysMonitor(on_sample=self._emit_sample, interval=interval)
        self._opacity = opacity
        self._vals, self._texts = (0.0, 0.0, None), None
        self._pm, self._pm_dpr = None, 0.0
        self._cell = self.fontMetrics().horizontalAdvance("CPU 100%") + 14
        self.setFixedSize(self._cell * 3 + 18, 24)
        self.hide()

    def _emit_sample(self, vals):                     # se ejecuta en el hilo del monitor
        try:
            self._sig.sample.emit(vals)
        except RuntimeError:                          # la ventana ya se cerró
            pass

    def set_active(self, on):
        """Activo = visible y midiendo. Inactivo = oculto y sin hilo (coste cero)."""
        if on:
            self.mon.start()
            self.reposition()
            self.show()
            self.raise_()
        else:
            self.mon.stop()
            self.hide()

    def set_opacity(self, value):
        self._opacity = value
        self.update()

    def set_interval(self, seconds):
        self.mon.interval = seconds

    def reposition(self):
        p = self.parentWidget()
        if p is not None:
            self.move((p.width() - self.width()) // 2, 6)

    def _on_sample(self, vals):
        texts = tuple("n/d" if v is None else f"{v:.0f}%" for v in vals)
        self._vals = vals
        if texts == self._texts:                      # nada cambió: no se redibuja
            return
        self._texts = texts
        self._pm = None                               # se regenera una sola vez al pintar
        self.update()

    @staticmethod
    def _color(v):
        if v is None:
            return QColor(150, 150, 150)
        v = round(v)
        return QColor(120, 220, 140) if v < 60 else QColor(255, 200, 80) if v < 85 else QColor(255, 100, 100)

    def _render(self, dpr):
        w, h = self.width(), self.height()
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(QColor(10, 10, 14, 225))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), h / 2, h / 2)    # bordes totalmente redondeados
        p.setFont(self.font())
        texts = self._texts or ("--", "--", "--")
        for i, (label, v, t) in enumerate(zip(self.LABELS, self._vals, texts)):
            p.setPen(self._color(v))
            p.drawText(QRect(9 + i * self._cell, 0, self._cell, h), Qt.AlignmentFlag.AlignCenter, f"{label} {t}")
        p.end()
        self._pm, self._pm_dpr = pm, dpr

    def paintEvent(self, ev):
        dpr = self.devicePixelRatioF()
        if self._pm is None or dpr != self._pm_dpr:
            self._render(dpr)
        p = QPainter(self)
        p.setOpacity(self._opacity)                   # opacidad de toda la pastilla
        p.drawPixmap(0, 0, self._pm)


class CamerasDialog(QDialog):
    FIELDS = [("name", "Nombre"), ("ip", "IP"), ("port", "Puerto"), ("user", "Usuario"),
              ("password", "Contraseña"), ("channel", "Canal"),
              ("url_sub", "URL Transmisión (opcional)"), ("url_main", "URL Convencional (opcional)")]

    def __init__(self, cams, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cámaras")
        self.cams = [dict(c) for c in cams]
        self._loading = False

        self.list = QListWidget()
        add, rem = QPushButton("Agregar"), QPushButton("Quitar")
        add.clicked.connect(self._add)
        rem.clicked.connect(self._remove)
        left = QVBoxLayout()
        left.addWidget(self.list)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(rem)
        left.addLayout(row)

        form = QFormLayout()
        self.edits = {}
        for key, label in self.FIELDS:
            ed = QLineEdit()
            if key == "password":
                ed.setEchoMode(QLineEdit.EchoMode.Password)
            ed.textEdited.connect(lambda t, k=key: self._commit(k, t))
            self.edits[key] = ed
            form.addRow(label, ed)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right = QVBoxLayout()
        right.addLayout(form)
        right.addWidget(buttons)

        root = QHBoxLayout(self)
        root.addLayout(left, 1)
        root.addLayout(right, 2)
        self.list.currentRowChanged.connect(self._load)
        self._refresh()
        self.resize(720, 360)

    def _refresh(self, select=0):
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItems([c.get("name", "Cámara") for c in self.cams])
        self.list.blockSignals(False)
        if self.cams:
            self.list.setCurrentRow(min(select, len(self.cams) - 1))
        self._load(self.list.currentRow())

    def _load(self, row):
        self._loading = True
        for key, _ in self.FIELDS:
            self.edits[key].setEnabled(row >= 0)
            self.edits[key].setText(str(self.cams[row].get(key, "")) if row >= 0 else "")
        self._loading = False

    def _commit(self, key, text):
        row = self.list.currentRow()
        if self._loading or row < 0:
            return
        if key in ("port", "channel"):
            text = int(text) if text.isdigit() else text
        self.cams[row][key] = text
        if key == "name":
            self.list.item(row).setText(text)

    def _add(self):
        n = len(self.cams) + 1
        self.cams.append({"id": uuid.uuid4().hex[:8], "name": f"Cámara {n}", "ip": "192.168.1.10", "port": 554,
                          "user": "admin", "password": "", "channel": 1, "quality": QUALITY_SUB})
        self._refresh(len(self.cams) - 1)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            del self.cams[row]
            self._refresh(row)

    def result_cams(self):
        for c in self.cams:                      # limpia vacíos y tipos
            c.setdefault("id", uuid.uuid4().hex[:8])
            for k in ("url_sub", "url_main"):
                if not c.get(k):
                    c.pop(k, None)
            for k, d in (("port", 554), ("channel", 1)):
                if not isinstance(c.get(k), int):
                    c[k] = d
        return self.cams
