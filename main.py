"""iCSee Lite - visor multicámara RTSP ultraligero e independiente (PyAV + PyQt6)."""
import sys

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QGridLayout, QMessageBox, QWidget

import config
import layout as L
from layout_editor import LayoutDialog
from stream_manager import QUALITY_MAIN
from ui import CamerasDialog, VideoWidget


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iCSee Lite")
        self.setMinimumSize(320, 180)
        self.setStyleSheet("MainWindow { background: black; }")
        self.cfg = config.load()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(2)
        self.widgets, self.zoomed, self._saved_q, self._mini = [], None, None, False
        self._dims, self._unassigned = (0, 0), []
        self.rebuild()
        if not self.cfg["cameras"]:
            QTimer.singleShot(300, self.manage_cameras)

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
        lay = L.normalize(self.cfg["layout"], cams) if self.cfg.get("layout") else None
        self._unassigned = []
        if lay:
            self._unassigned = L.fill_unassigned(lay, cams)
        else:
            lay = L.auto_layout(cams)
        self._dims = (lay["rows"], lay["cols"])
        self._set_stretch(True)       # las celdas vacías conservan su espacio
        by_id = {c["id"]: c for c in cams}
        for cell in lay["cells"]:
            if cell["cam"]:
                w = VideoWidget(by_id[cell["cam"]], self)
                self.grid.addWidget(w, cell["r"], cell["c"], cell["rs"], cell["cs"])
                self.widgets.append(w)

    def customize_layout(self):
        cams = self.cfg["cameras"]
        if not cams:
            QMessageBox.information(self, "iCSee Lite", "Primero agrega al menos una cámara.")
            return
        lay = L.normalize(self.cfg["layout"], cams) if self.cfg.get("layout") else None
        lay = lay or L.default_editor_layout(cams)
        L.fill_unassigned(lay, cams)
        dlg = LayoutDialog(cams, lay, self)
        if dlg.exec():
            self.cfg["layout"] = None if dlg.auto else dlg.result_layout()
            self.save()
            self.rebuild()

    def manage_cameras(self):
        dlg = CamerasDialog(self.cfg["cameras"], self)
        if dlg.exec():
            self.cfg["cameras"] = dlg.result_cams()
            self.save()
            self.rebuild()
            if self._unassigned:      # hay más cámaras que celdas libres
                QMessageBox.information(self, "iCSee Lite",
                                        "Hay cámaras sin celda. Amplía o reorganiza la cuadrícula.")
                self.customize_layout()

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

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
        if e.type() == QEvent.Type.WindowStateChange and self.isMinimized() != self._mini:
            self._mini = self.isMinimized()   # minimizada = todo en pausa
            self._apply_pause()
        super().changeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif e.key() == Qt.Key.Key_Escape:
            if self.zoomed:
                self.toggle_zoom(self.zoomed)
            elif self.isFullScreen():
                self.showNormal()

    def closeEvent(self, e):
        for w in self.widgets:
            w.shutdown()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
