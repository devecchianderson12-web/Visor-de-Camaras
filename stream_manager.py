"""Lectura RTSP + decodificación con PyAV (FFmpeg incluido). Sin dependencias externas."""
import threading
import time

import av
import numpy as np

try:
    from av.codec.hwaccel import HWAccel, hwdevices_available
except Exception:  # versión de PyAV sin soporte hwaccel
    HWAccel = None

QUALITY_SUB = "Transmisión"    # substream: fluido, baja resolución
QUALITY_MAIN = "Convencional"  # mainstream: alta definición
QUALITIES = (QUALITY_SUB, QUALITY_MAIN)


def build_url(cam: dict, quality: str, template: str) -> str:
    """iCSee/XM: stream=0 principal, stream=1 secundario."""
    sub = quality == QUALITY_SUB
    custom = cam.get("url_sub" if sub else "url_main")
    if custom:
        return custom
    return template.format(
        ip=cam.get("ip", ""), port=cam.get("port", 554),
        user=cam.get("user", "admin"), password=cam.get("password", ""),
        channel=cam.get("channel", 1), stream=1 if sub else 0,
    )


def fit_size(fw, fh, tw, th, max_h=0):
    """Tamaño de salida: cabe en el widget, nunca amplía y respeta el tope de resolución."""
    s = min(tw / fw, th / fh, 1.0)
    if max_h:
        s = min(s, max_h / fh)
    return max(16, int(fw * s)), max(16, int(fh * s))


def _pick_hw():
    if HWAccel is None:
        return None
    try:
        available = set(hwdevices_available())
    except Exception:
        return None
    for name in ("d3d11va", "dxva2", "videotoolbox", "vaapi", "cuda"):
        if name in available:
            return name
    return None


class CameraWorker(threading.Thread):
    """Un hilo por cámara. Cambiar calidad = reabrir el stream dentro del hilo,
    así la interfaz nunca se bloquea."""

    def __init__(self, cam, template, use_hw, fps, on_frame, on_status):
        super().__init__(daemon=True)
        self.cam, self.template = cam, template
        self.use_hw = use_hw
        self.fps = fps
        self.target = (640, 360)          # tamaño del widget (px); lo actualiza la UI
        self.max_h = int(cam.get("res", 0) or 0)   # tope de resolución mostrada (0 = automática)
        self.on_frame, self.on_status = on_frame, on_status
        q = cam.get("quality", QUALITY_SUB)
        self.quality = q if q in QUALITIES else QUALITY_SUB
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._paused = False

    # ---- control desde la UI (no bloqueante) ----
    def set_quality(self, quality):
        self.quality = quality
        self._reload.set()

    def set_paused(self, paused):
        self._paused = paused
        self._reload.set()

    def stop(self):
        self._stop.set()
        self._reload.set()

    # ---- hilo ----
    def run(self):
        backoff = 1.0
        while not self._stop.is_set():
            if self._paused:
                self._stop.wait(0.2)
                continue
            self._reload.clear()
            got = False
            try:
                got = self._session(build_url(self.cam, self.quality, self.template))
            except Exception:
                pass
            if self._stop.is_set():
                break
            if self._reload.is_set() or self._paused:
                backoff = 1.0
                continue
            self.on_status("Sin señal · reconectando…")
            backoff = 1.0 if got else min(backoff * 2, 15.0)
            self._reload.wait(backoff)

    def _session(self, url) -> bool:
        sub = self.quality == QUALITY_SUB
        self.on_status("Conectando…")
        options = {"rtsp_transport": "tcp", "fflags": "nobuffer",
                   "flags": "low_delay", "max_delay": "500000"}
        kwargs = {}
        hw_name = _pick_hw() if self.use_hw else None
        if hw_name:
            kwargs["hwaccel"] = HWAccel(device_type=hw_name, allow_software_fallback=True)
        try:
            container = av.open(url, options=options, timeout=(8.0, 8.0), **kwargs)
        except TypeError:                       # PyAV sin parámetro hwaccel
            container = av.open(url, options=options, timeout=(8.0, 8.0))
        got = False
        last = 0.0
        try:
            vs = container.streams.video[0]
            vs.codec_context.thread_count = 2 if sub else 0
            for packet in container.demux(vs):
                if self._stop.is_set() or self._reload.is_set():
                    break
                try:
                    frames = packet.decode()
                except av.error.FFmpegError:
                    if hw_name and not got:      # la GPU no pudo: reintenta en CPU
                        self.use_hw = False
                        return False
                    continue
                for frame in frames:
                    now = time.monotonic()
                    if now - last < 1.0 / max(self.fps, 1):
                        continue                 # descarta sin convertir = ahorra CPU
                    last = now
                    w, h = fit_size(frame.width, frame.height, *self.target, self.max_h)
                    arr = frame.to_ndarray(width=w, height=h, format="rgb24")
                    if not arr.flags["C_CONTIGUOUS"]:
                        arr = np.ascontiguousarray(arr)
                    self.on_frame(arr)
                    got = True
        finally:
            container.close()
        return got
