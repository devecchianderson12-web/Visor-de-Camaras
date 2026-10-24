"""Lectura/escritura de config.json (junto al .exe o al script)."""
import json
import os
import sys
import uuid

DEFAULTS = {
    "url_template": (
        "rtsp://{ip}:{port}/user={user}&password={password}"
        "&channel={channel}&stream={stream}.sdp?real_stream"
    ),
    "hwaccel": True,              # intenta decodificar por GPU; si falla, usa CPU
    "fps_grid": 12,               # FPS mostrados en la cuadrícula (menos = menos CPU)
    "fps_zoom": 25,               # FPS al maximizar una cámara
    "auto_quality_on_zoom": True, # al maximizar usa "Convencional"
    "cameras": [],
    "layout_mode": "grid",        # grid | focus | pano | custom
    "layout": None,               # None = cuadrícula automática; ver layout.py
}


def base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


PATH = os.path.join(base_dir(), "config.json")


def resource_path(rel: str) -> str:
    """Archivos incluidos en el .exe (iconos): dentro del paquete de PyInstaller o junto al código."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        cfg.update(raw)
        if "layout_mode" not in raw:      # configs antiguas
            cfg["layout_mode"] = "custom" if raw.get("layout") else "grid"
    except (OSError, ValueError):
        pass
    new_ids = False
    for cam in cfg["cameras"]:          # id estable para referenciar la cámara en la cuadrícula
        if "id" not in cam:
            cam["id"] = uuid.uuid4().hex[:8]
            new_ids = True
    if new_ids:
        try:
            save(cfg)
        except OSError:
            pass
    return cfg


def save(cfg: dict) -> None:
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PATH)
