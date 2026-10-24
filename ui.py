"""Widgets: vídeo por cámara (clic derecho = calidad) y gestor de cámaras."""
import uuid

from qt import (event_pos, pyqtSignal, QAction, QActionGroup, QApplication, QByteArray, QColor,
               QDialog, QDialogButtonBox, QDrag, qexec, QFormLayout, QHBoxLayout, QImage, QLineEdit,
               QListWidget, QMenu, QMimeData, QObject, QPainter, QPen, QPixmap, QPushButton, QRect,
               Qt, QVBoxLayout, QWidget)

from stream_manager import QUALITIES, QUALITY_SUB, CameraWorker


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
        self._img = None
        self._arr = None
        self._status = "Conectando…"
        self._sig = _Signals()
        self._sig.frame.connect(self._on_frame)
        self._sig.status.connect(self._on_status)
        cfg = app.cfg
        self.worker = CameraWorker(cam, cfg["url_template"], cfg["hwaccel"], cfg["fps_grid"],
                                   self._sig.frame.emit, self._sig.status.emit)
        self.worker.start()

    # ---- señales (hilo de la UI) ----
    def _on_frame(self, arr):
        h, w, _ = arr.shape
        self._arr = arr  # mantiene vivo el buffer que usa QImage
        self._img = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._status = ""
        self.update()

    def _on_status(self, text):
        self._img, self._arr, self._status = None, None, text
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
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._img is not None:
            iw, ih = self._img.width(), self._img.height()
            s = min(self.width() / iw, self.height() / ih)
            w, h = int(iw * s), int(ih * s)
            p.drawImage(QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h), self._img)
        f = p.font()
        f.setPointSize(9)
        p.setFont(f)
        if self._status:
            p.setPen(QColor(170, 170, 170))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._status)
        label = f"{self.cam.get('name', 'Cámara')}  ·  {self.worker.quality}"
        if self.worker.max_h:
            label += f"  ·  {self.worker.max_h}p"
        tw = p.fontMetrics().horizontalAdvance(label) + 16
        p.fillRect(0, 0, tw, 20, QColor(0, 0, 0, 150))
        p.setPen(QColor(225, 225, 225))
        p.drawText(8, 14, label)
        if self._drop:                            # resalta el destino mientras arrastras
            p.setPen(QPen(QColor(110, 170, 255), 4))
            p.drawRect(self.rect().adjusted(2, 2, -2, -2))


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
