"""Editor visual de la cuadrícula: selecciona celdas -> Unir / Separar / asignar cámara."""
import copy

from qt import (QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
               QSpinBox, QVBoxLayout, QWidget)

import layout as L

STYLE = ("QPushButton{background:#1c1c1c;color:#ddd;border:1px solid #555;}"
         "QPushButton:checked{background:#1f5fbf;border:2px solid #8ec0ff;color:white;}")


class LayoutDialog(QDialog):
    def __init__(self, cams, lay, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Personalizar cuadrícula")
        self.cams = cams
        self.names = {c["id"]: c.get("name", "Cámara") for c in cams}
        self.lay = copy.deepcopy(lay)
        self.sel = set()
        self.auto = False

        self.rows, self.cols = QSpinBox(), QSpinBox()
        for s in (self.rows, self.cols):
            s.setRange(1, 6)
        self.rows.setValue(self.lay["rows"])
        self.cols.setValue(self.lay["cols"])
        self.rows.valueChanged.connect(self._resize)
        self.cols.valueChanged.connect(self._resize)

        top = QHBoxLayout()
        top.addWidget(QLabel("Filas"))
        top.addWidget(self.rows)
        top.addWidget(QLabel("Columnas"))
        top.addWidget(self.cols)
        top.addStretch(1)
        top.addWidget(QLabel("(cambiar el tamaño reinicia las uniones)"))

        self.board = QWidget()
        self.board_layout = QGridLayout(self.board)
        self.board_layout.setSpacing(4)

        merge_b, split_b = QPushButton("Unir seleccionadas"), QPushButton("Separar seleccionadas")
        merge_b.clicked.connect(self._merge)
        split_b.clicked.connect(self._split)
        self.combo = QComboBox()
        self.combo.activated.connect(self._assign)
        actions = QHBoxLayout()
        actions.addWidget(merge_b)
        actions.addWidget(split_b)
        actions.addStretch(1)
        actions.addWidget(QLabel("Cámara en la celda:"))
        actions.addWidget(self.combo)

        self.info = QLabel("Haz clic en las celdas para seleccionarlas y pulsa «Unir».")
        self.missing = QLabel()
        auto_b = QPushButton("Usar automático")
        auto_b.clicked.connect(self._use_auto)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(auto_b)
        bottom.addStretch(1)
        bottom.addWidget(buttons)

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self.board, 1)
        root.addLayout(actions)
        root.addWidget(self.info)
        root.addWidget(self.missing)
        root.addLayout(bottom)
        self.resize(640, 480)
        self._render()

    # ---- dibujo ----
    def _render(self):
        while self.board_layout.count():
            item = self.board_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, cell in enumerate(self.lay["cells"]):
            b = QPushButton(self.names.get(cell["cam"], "(vacío)"))
            b.setCheckable(True)
            b.setChecked(i in self.sel)
            b.setMinimumSize(90, 56)
            b.setStyleSheet(STYLE)
            b.clicked.connect(lambda _=False, i=i: self._toggle(i))
            self.board_layout.addWidget(b, cell["r"], cell["c"], cell["rs"], cell["cs"])
        for r in range(8):
            self.board_layout.setRowStretch(r, 1 if r < self.lay["rows"] else 0)
            self.board_layout.setColumnStretch(r, 1 if r < self.lay["cols"] else 0)
        self._sync()

    def _sync(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("(vacío)", None)
        for c in self.cams:
            self.combo.addItem(c.get("name", "Cámara"), c["id"])
        one = len(self.sel) == 1
        self.combo.setEnabled(one)
        if one:
            cam = self.lay["cells"][next(iter(self.sel))]["cam"]
            self.combo.setCurrentIndex(max(0, self.combo.findData(cam)))
        self.combo.blockSignals(False)
        miss = L.unassigned(self.lay, self.cams)
        self.missing.setText("Sin asignar: " + ", ".join(c.get("name", "Cámara") for c in miss) if miss else "")

    # ---- acciones ----
    def _toggle(self, i):
        self.sel.symmetric_difference_update({i})
        self._sync()

    def _merge(self):
        new, idx, err = L.merge(self.lay, self.sel)
        if err:
            self.info.setText(err)
            return
        self.lay, self.sel = new, {idx}
        self.info.setText("Celdas unidas.")
        self._render()

    def _split(self):
        self.lay = L.split(self.lay, self.sel)
        self.sel = set()
        self.info.setText("Celdas separadas.")
        self._render()

    def _assign(self, _):
        if len(self.sel) != 1:
            return
        cam = self.combo.currentData()
        if cam is not None:                      # una cámara solo puede estar en una celda
            for c in self.lay["cells"]:
                if c["cam"] == cam:
                    c["cam"] = None
        self.lay["cells"][next(iter(self.sel))]["cam"] = cam
        self._render()

    def _resize(self):
        self.lay = L.blank_layout(self.rows.value(), self.cols.value(), self.cams)
        self.sel = set()
        self._render()

    def _use_auto(self):
        self.auto = True
        self.accept()

    def result_layout(self):
        return self.lay
