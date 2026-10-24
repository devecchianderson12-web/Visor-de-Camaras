"""Diálogos: 'Buscar ONVIF' y 'Buscar en red (IPv4)'. El trabajo de red va en hilos."""
import threading
import uuid

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QVBoxLayout)

import discovery as D
from stream_manager import QUALITY_SUB


class _Sig(QObject):
    found = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object, object)   # cámaras nuevas, mensajes


def new_cam(name, ip, user, pw, urls=None):
    cam = {"id": uuid.uuid4().hex[:8], "name": name, "ip": ip, "port": 554, "user": user,
           "password": pw, "channel": 1, "quality": QUALITY_SUB}
    if urls:
        cam["url_main"], cam["url_sub"] = urls["url_main"], urls["url_sub"]
    return cam


class _Base(QDialog):
    def __init__(self, title, existing_ips, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.existing = set(existing_ips)
        self.cams = []
        self._stop = threading.Event()
        self.sig = _Sig()
        self.sig.found.connect(self._on_found)
        self.sig.progress.connect(self._on_progress)
        self.sig.finished.connect(self._on_finished)

        self.user = QLineEdit("admin")
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.form = QFormLayout()
        self.list = QListWidget()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1)
        self.search_b = QPushButton("Buscar")
        self.add_b = QPushButton("Agregar seleccionadas")
        self.add_b.setEnabled(False)
        self.close_b = QPushButton("Cerrar")
        self.close_b.clicked.connect(self.reject)

    def _build(self, hint):
        self.form.addRow("Usuario", self.user)
        self.form.addRow("Contraseña", self.pw)
        row = QHBoxLayout()
        row.addWidget(self.search_b)
        row.addStretch(1)
        row.addWidget(self.add_b)
        row.addWidget(self.close_b)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(hint))
        root.addLayout(self.form)
        root.addWidget(self.list, 1)
        root.addWidget(self.bar)
        root.addWidget(self.status)
        root.addLayout(row)
        self.resize(560, 460)

    def _emit(self, sig, *args):
        try:
            sig.emit(*args)
        except RuntimeError:        # el diálogo ya se cerró
            pass

    def _busy(self, on, msg=""):
        self.bar.setRange(0, 0 if on else 1)
        self.search_b.setEnabled(not on)
        self.add_b.setEnabled(not on and self.list.count() > 0)
        self.status.setText(msg)

    def _fill(self, entries):
        self.list.clear()
        for text, dev in entries:
            dup = dev["ip"] in self.existing
            it = QListWidgetItem(text + ("   (ya agregada)" if dup else ""))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked if dup else Qt.CheckState.Checked)
            it.setData(Qt.ItemDataRole.UserRole, dev)
            self.list.addItem(it)

    def _checked(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def _on_progress(self, done, total):
        self.bar.setRange(0, total)
        self.bar.setValue(done)

    def _on_finished(self, cams, msgs):
        self._busy(False)
        if msgs:
            QMessageBox.information(self, "Resultado", "\n".join(msgs))
        if cams:
            self.cams = cams
            self.accept()

    def done(self, r):
        self._stop.set()
        super().done(r)


class OnvifDialog(_Base):
    def __init__(self, existing_ips, parent=None):
        super().__init__("Buscar dispositivos ONVIF", existing_ips, parent)
        self._build("Dispositivos ONVIF de tu red (los mismos que ve VMS Lite). "
                    "Indica el usuario y contraseña de las cámaras.")
        self.search_b.setText("Buscar de nuevo")
        self.search_b.clicked.connect(self.search)
        self.add_b.clicked.connect(self.add)
        QTimer.singleShot(150, self.search)

    def search(self):
        self._busy(True, "Buscando dispositivos ONVIF…")

        def work():
            try:
                res = D.discover_onvif(4.0)
            except Exception:
                res = []
            self._emit(self.sig.found, res)
        threading.Thread(target=work, daemon=True).start()

    def _on_found(self, res):
        self._fill([(f"{d['ip']}    {d['name']}", d) for d in res])
        n = len(res)
        self._busy(False, f"{n} dispositivo(s) encontrado(s)." if n else
                   "No se encontró ninguno. Comprueba que estén en la misma red. Si Windows pide "
                   "permiso de red, acepta «Redes privadas». También puedes probar «Buscar en red».")

    def add(self):
        devs, user, pw = self._checked(), self.user.text().strip(), self.pw.text()
        if not devs:
            return
        self._busy(True, "Consultando perfiles de video de cada cámara…")

        def work():
            cams, msgs = [], []
            for d in devs:
                try:
                    urls = D.resolve_streams(d["xaddr"], user, pw)
                    cams.append(new_cam(f"{d['name']} {d['ip']}", d["ip"], user, pw, urls))
                except D.OnvifError as e:
                    msgs.append(f"{d['ip']}: {e}")
                except Exception as e:
                    msgs.append(f"{d['ip']}: error ({e.__class__.__name__})")
            self._emit(self.sig.finished, cams, msgs)
        threading.Thread(target=work, daemon=True).start()


class NetScanDialog(_Base):
    def __init__(self, existing_ips, parent=None):
        super().__init__("Buscar cámaras en la red (IPv4)", existing_ips, parent)
        subnets = D.local_subnets()
        self.range = QLineEdit(", ".join(subnets[:1]) or "192.168.1.0/24")
        self.form.addRow("Rango a escanear", self.range)
        self._build("Escanea la red buscando equipos con puertos de cámara abiertos "
                    "(RTSP 554, ONVIF 8899, iCSee 34567). Formato: 192.168.1.0/24 o 192.168.1.10-50")
        self.search_b.setText("Escanear")
        self.search_b.clicked.connect(self.search)
        self.add_b.clicked.connect(self.add)

    def search(self):
        try:
            hosts = D.parse_hosts(self.range.text())
        except ValueError as e:
            self.status.setText(str(e))
            return
        self.list.clear()
        self._stop.clear()
        self._busy(True, f"Escaneando {len(hosts)} direcciones…")

        def work():
            try:
                res = D.scan_network(hosts, progress_cb=lambda d, t: self._emit(self.sig.progress, d, t),
                                     stop=self._stop)
            except Exception:
                res = []
            self._emit(self.sig.found, res)
        threading.Thread(target=work, daemon=True).start()

    def _on_found(self, res):
        def label(d):
            ports = ", ".join(f"{p} ({D.PORT_NAMES.get(p, '?')})" for p in d["ports"])
            return f"{d['ip']}    puertos: {ports}"
        self._fill([(label(d), d) for d in res])
        n = len(res)
        self._busy(False, f"{n} posible(s) cámara(s) encontrada(s)." if n else
                   "No se encontró ninguna en ese rango.")
        self.bar.setRange(0, 1)

    def add(self):
        devs, user, pw = self._checked(), self.user.text().strip(), self.pw.text()
        if not devs:
            return
        self._busy(True, "Agregando cámaras…")

        def work():
            cams, msgs = [], []
            for d in devs:
                urls = None
                for xaddr in D.onvif_candidates(d):
                    try:
                        urls = D.resolve_streams(xaddr, user, pw)
                        break
                    except Exception:
                        continue
                cams.append(new_cam(f"Cámara {d['ip']}", d["ip"], user, pw, urls))
                if not urls:
                    msgs.append(f"{d['ip']}: no respondió ONVIF; se agregó con la ruta iCSee por defecto. "
                                "Si no se ve, revisa usuario/contraseña o edítala en «Cámaras».")
            self._emit(self.sig.finished, cams, msgs)
        threading.Thread(target=work, daemon=True).start()
