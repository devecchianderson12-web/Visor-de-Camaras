"""The Watcher - ventana principal."""
import sys

from qt import (QApplication, QButtonGroup, QCursor, QEvent, qexec, QGridLayout, QHBoxLayout, QIcon,
               QMessageBox, QPushButton, Qt, QTimer, QVBoxLayout, QWidget)

import config
import layout as L
from discovery_dialogs import NetScanDialog, OnvifDialog
from layout_editor import LayoutDialog
from stream_manager import QUALITY_MAIN
from ui import CamerasDialog, VideoWidget

MODES = [
    ("grid", "Cuadrícula", "Todas las cámaras en cuadrícula automática, sin huecos"),
    ("focus", "Destacada", "Una cámara grande y las demás a un costado"),
    ("pano", "Panorámica", "Una cámara grande arriba y las demás en fila debajo"),
    ("custom", "Mi planilla", "Tu propia distribución. Clic: aplicar · otro clic: editarla"),
]

EXIT_STYLE = """
QPushButton { background: rgba(0,0,0,150); color: #e6e6e6; border: 1px solid rgba(255,255,255,60);
              border-radius: 6px; }
QPushButton:hover { background: rgba(31,95,191,230); color: white; }
"""

BAR_STYLE = """
#bar { background: #101010; }
#bar QPushButton { background: #232323; color: #ddd; border: 1px solid #3a3a3a;
                   border-radius: 4px; padding: 5px 12px; }
#bar QPushButton:hover { background: #2f2f2f; }
#bar QPushButton:checked { background: #1f5fbf; border-color: #6aa8ff; color: white; }
"""


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Watcher")
        self.setMinimumSize(480, 260)
        self.setStyleSheet("MainWindow { background: black; }")
        self.cfg = config.load()
        self.widgets, self.zoomed, self._saved_q, self._mini = [], None, None, False
        self._dims, self._unassigned = (0, 0), []
        self._fs = False

        self.stage = QWidget()
        self.grid = QGridLayout(self.stage)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(2)
        self._build_toolbar()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.stage, 1)
        root.addWidget(self.toolbar)
        self._build_exit_button()

        self.rebuild()
        if not self.cfg["cameras"]:
            QTimer.singleShot(300, self.manage_cameras)

    # ---- barra inferior ----
    def _build_toolbar(self):
        self.toolbar = QWidget()
        self.toolbar.setObjectName("bar")
        self.toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.toolbar.setStyleSheet(BAR_STYLE)
        h = QHBoxLayout(self.toolbar)
        h.setContentsMargins(8, 5, 8, 5)
        h.setSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.mode_btns = {}
        for mode, label, tip in MODES:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, m=mode: self._on_mode_click(m))
            group.addButton(b)
            h.addWidget(b)
            self.mode_btns[mode] = b
        h.addStretch(1)
        for label, tip, fn in (
                ("Buscar ONVIF", "Busca dispositivos ONVIF (como VMS Lite)", lambda: self.discover("onvif")),
                ("Buscar en red", "Escanea la red IPv4 buscando cámaras", lambda: self.discover("net")),
                ("Pantalla completa", "Pantalla completa (F11)", self.toggle_fullscreen),
                ("Cámaras", "Agregar, editar o quitar cámaras", self.manage_cameras)):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, f=fn: f())
            h.addWidget(b)
        self._sync_modes()

    def _build_exit_button(self):
        """Botón discreto arriba a la derecha: solo aparece al acercar el mouse (en pantalla completa)."""
        self.exit_btn = QPushButton("✕  Salir", self)
        self.exit_btn.setToolTip("Salir de pantalla completa (Esc)")
        self.exit_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setStyleSheet(EXIT_STYLE)
        self.exit_btn.setFixedSize(92, 32)
        self.exit_btn.clicked.connect(lambda: self._set_fullscreen(False))
        self.exit_btn.hide()
        # consulta la posición del mouse 10 veces/s, solo mientras hay pantalla completa
        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(100)
        self._edge_timer.timeout.connect(self._edge_tick)

    def _edge_tick(self):
        p = self.mapFromGlobal(QCursor.pos())
        near = 0 <= p.y() <= 90 and self.width() - 260 <= p.x() <= self.width()
        if near != self.exit_btn.isVisible():
            self.exit_btn.setVisible(near)
            if near:
                self.exit_btn.raise_()

    def _apply_fs(self, on):
        if on == self._fs:
            return
        self._fs = on
        self.toolbar.setVisible(not on)
        self.exit_btn.hide()
        if on:
            self._edge_timer.start()
        else:
            self._edge_timer.stop()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "exit_btn"):
            self.exit_btn.move(self.width() - self.exit_btn.width() - 12, 12)

    def _sync_modes(self):
        mode = self.cfg.get("layout_mode", "grid")
        for m, b in self.mode_btns.items():
            b.setChecked(m == mode)

    def _on_mode_click(self, mode):
        if mode == "custom" and (self.cfg.get("layout_mode") == "custom" or not self.cfg.get("layout")):
            self.customize_layout()           # sin planilla guardada, o 2.º clic: editar
            return
        self.cfg["layout_mode"] = mode
        self.save()
        self.rebuild()
        self._sync_modes()

    # ---- config ----
    def save(self):
        try:
            config.save(self.cfg)
        except OSError:
            pass

    # ---- cuadrícula ----
    def _set_stretch(self, on):
        rows, cols = self._dims
        for i in range(8):
            self.grid.setRowStretch(i, 1 if on and i < rows else 0)
            self.grid.setColumnStretch(i, 1 if on and i < cols else 0)

    def rebuild(self):
        self.zoomed = None
        for w in self.widgets:
            w.shutdown()
            self.grid.removeWidget(w)
            w.deleteLater()
        self.widgets = []
        cams = self.cfg["cameras"]
        mode = self.cfg.get("layout_mode", "grid")
        lay, self._unassigned = None, []
        if mode == "custom" and self.cfg.get("layout"):
            lay = L.normalize(self.cfg["layout"], cams)
            if lay:
                self._unassigned = L.fill_unassigned(lay, cams)
        if lay is None:
            lay = L.preset(mode, cams)
        self._dims = (lay["rows"], lay["cols"])
        self._set_stretch(True)
        by_id = {c["id"]: c for c in cams}
        for cell in lay["cells"]:
            if cell["cam"]:
                w = VideoWidget(by_id[cell["cam"]], self)
                self.grid.addWidget(w, cell["r"], cell["c"], cell["rs"], cell["cs"])
                self.widgets.append(w)

    def make_primary(self, cam):
        cams = self.cfg["cameras"]
        if cam in cams:
            cams.remove(cam)
            cams.insert(0, cam)
            self.save()
            self.rebuild()

    def swap_cameras(self, id_a, id_b):
        """Intercambia dos cámaras de lugar moviendo sus widgets: los streams no se tocan."""
        if id_a == id_b or self.zoomed is not None:
            return
        wa = next((w for w in self.widgets if w.cam["id"] == id_a), None)
        wb = next((w for w in self.widgets if w.cam["id"] == id_b), None)
        if not (wa and wb):
            return
        pa = self.grid.getItemPosition(self.grid.indexOf(wa))   # (fila, col, filas, cols)
        pb = self.grid.getItemPosition(self.grid.indexOf(wb))
        self.grid.removeWidget(wa)
        self.grid.removeWidget(wb)
        self.grid.addWidget(wa, *pb)
        self.grid.addWidget(wb, *pa)
        cams = self.cfg["cameras"]
        lay = None
        if self.cfg.get("layout_mode") == "custom" and self.cfg.get("layout"):
            lay = L.normalize(self.cfg["layout"], cams)
        if lay:                                  # planilla propia: se intercambian las celdas
            L.fill_unassigned(lay, cams)
            if L.swap_cams(lay, id_a, id_b):
                self.cfg["layout"] = lay
        else:                                    # vistas automáticas: el orden de la lista manda
            ia = next(i for i, c in enumerate(cams) if c["id"] == id_a)
            ib = next(i for i, c in enumerate(cams) if c["id"] == id_b)
            cams[ia], cams[ib] = cams[ib], cams[ia]
        self.save()

    def customize_layout(self):
        cams = self.cfg["cameras"]
        if not cams:
            QMessageBox.information(self, "The Watcher", "Primero agrega al menos una cámara.")
            return
        lay = L.normalize(self.cfg["layout"], cams) if self.cfg.get("layout") else None
        lay = lay or L.default_editor_layout(cams)
        L.fill_unassigned(lay, cams)
        dlg = LayoutDialog(cams, lay, self)
        if qexec(dlg):
            if dlg.auto:
                self.cfg["layout_mode"] = "grid"
            else:
                self.cfg["layout"] = dlg.result_layout()
                self.cfg["layout_mode"] = "custom"
            self.save()
            self.rebuild()
        self._sync_modes()

    # ---- cámaras ----
    def _cameras_changed(self):
        self.save()
        self.rebuild()
        if self._unassigned:              # hay más cámaras que celdas libres (planilla propia)
            QMessageBox.information(self, "The Watcher",
                                    "Hay cámaras sin celda. Amplía o reorganiza tu planilla.")
            self.customize_layout()

    def manage_cameras(self):
        dlg = CamerasDialog(self.cfg["cameras"], self)
        if qexec(dlg):
            self.cfg["cameras"] = dlg.result_cams()
            self._cameras_changed()

    def discover(self, kind):
        existing = {c.get("ip") for c in self.cfg["cameras"]}
        dlg = OnvifDialog(existing, self) if kind == "onvif" else NetScanDialog(existing, self)
        if qexec(dlg) and dlg.cams:
            self.cfg["cameras"] = self.cfg["cameras"] + dlg.cams
            self._cameras_changed()

    # ---- ventana ----
    def _set_fullscreen(self, on):
        self.showFullScreen() if on else self.showNormal()
        self._apply_fs(on)

    def toggle_fullscreen(self):
        self._set_fullscreen(not self._fs)

    def toggle_zoom(self, w):
        """Doble clic: maximiza una cámara y pausa las demás (0 % CPU en ellas)."""
        auto = self.cfg["auto_quality_on_zoom"]
        if self.zoomed is None:
            if len(self.widgets) < 2:
                return
            self.zoomed, self._saved_q = w, w.worker.quality
            self._set_stretch(False)
            for o in self.widgets:
                o.setVisible(o is w)
            w.worker.fps = self.cfg["fps_zoom"]
            if auto:
                w.set_quality(QUALITY_MAIN, save=False)
        else:
            z, self.zoomed = self.zoomed, None
            z.worker.fps = self.cfg["fps_grid"]
            if auto and self._saved_q:
                z.set_quality(self._saved_q, save=False)
            self._set_stretch(True)
            for o in self.widgets:
                o.setVisible(True)
        self._apply_pause()

    def _apply_pause(self):
        for w in self.widgets:
            w.worker.set_paused(self._mini or (self.zoomed is not None and w is not self.zoomed))

    def changeEvent(self, e):
        if e.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() != self._mini:
                self._mini = self.isMinimized()   # minimizada = todo en pausa
                self._apply_pause()
            self._apply_fs(self.isFullScreen())   # por si salen con Win+flechas u otro medio
        super().changeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif e.key() == Qt.Key.Key_Escape:
            if self.zoomed:
                self.toggle_zoom(self.zoomed)
            elif self._fs:
                self._set_fullscreen(False)

    def closeEvent(self, e):
        for w in self.widgets:
            w.shutdown()
        super().closeEvent(e)
