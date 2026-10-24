"""Modelo de cuadrícula personalizable (sin dependencias de Qt, fácil de probar).

layout = {"rows": R, "cols": C,
          "cells": [{"r":fila, "c":col, "rs":filas_que_ocupa, "cs":cols_que_ocupa, "cam":id|None}, ...]}
Las celdas siempre cubren toda la cuadrícula sin solaparse.
"""
import math


def _sort(cells):
    return sorted(cells, key=lambda x: (x["r"], x["c"]))


def blank_layout(rows, cols, cams):
    """Cuadrícula de celdas 1x1; las cámaras se reparten en orden."""
    cells = []
    for i in range(rows * cols):
        cam = cams[i]["id"] if i < len(cams) else None
        cells.append({"r": i // cols, "c": i % cols, "rs": 1, "cs": 1, "cam": cam})
    return {"rows": rows, "cols": cols, "cells": cells}


def auto_dims(n):
    cols = max(1, math.ceil(math.sqrt(n)))
    return max(1, math.ceil(n / cols)), cols


def auto_layout(cams):
    rows, cols = auto_dims(len(cams))
    return blank_layout(rows, cols, cams)


def default_editor_layout(cams):
    """Punto de partida del editor: 2x2 (o más si hay más de 4 cámaras)."""
    if len(cams) <= 4:
        return blank_layout(2, 2, cams)
    return auto_layout(cams)


def normalize(layout, cams):
    """Valida/repara un layout guardado. Devuelve None si no sirve."""
    try:
        rows, cols = int(layout["rows"]), int(layout["cols"])
    except (TypeError, KeyError, ValueError):
        return None
    if not (1 <= rows <= 8 and 1 <= cols <= 8):
        return None
    ids = {c["id"] for c in cams}
    occ, used, cells = set(), set(), []
    for raw in layout.get("cells", []):
        try:
            r, c, rs, cs = (int(raw[k]) for k in ("r", "c", "rs", "cs"))
        except (TypeError, KeyError, ValueError):
            continue
        if r < 0 or c < 0 or rs < 1 or cs < 1 or r + rs > rows or c + cs > cols:
            continue
        sq = {(r + i, c + j) for i in range(rs) for j in range(cs)}
        if sq & occ:
            continue
        occ |= sq
        cam = raw.get("cam")
        if cam not in ids or cam in used:
            cam = None
        if cam:
            used.add(cam)
        cells.append({"r": r, "c": c, "rs": rs, "cs": cs, "cam": cam})
    for r in range(rows):
        for c in range(cols):
            if (r, c) not in occ:
                cells.append({"r": r, "c": c, "rs": 1, "cs": 1, "cam": None})
    return {"rows": rows, "cols": cols, "cells": _sort(cells)}


def unassigned(layout, cams):
    placed = {c["cam"] for c in layout["cells"] if c["cam"]}
    return [c for c in cams if c["id"] not in placed]


def fill_unassigned(layout, cams):
    """Coloca cámaras nuevas en celdas vacías. Devuelve las que no cupieron."""
    missing = unassigned(layout, cams)
    for cell in layout["cells"]:
        if cell["cam"] is None and missing:
            cell["cam"] = missing.pop(0)["id"]
    return missing


def merge(layout, idxs):
    """Une las celdas seleccionadas. -> (nuevo_layout, indice_nueva_celda, error)"""
    cells = layout["cells"]
    if len(idxs) < 2:
        return None, None, "Selecciona dos o más celdas para unir."
    sel = [cells[i] for i in sorted(idxs)]
    squares = {(c["r"] + i, c["c"] + j) for c in sel for i in range(c["rs"]) for j in range(c["cs"])}
    r0, r1 = min(r for r, _ in squares), max(r for r, _ in squares)
    c0, c1 = min(c for _, c in squares), max(c for _, c in squares)
    if len(squares) != (r1 - r0 + 1) * (c1 - c0 + 1):
        return None, None, "La selección debe formar un rectángulo completo."
    keep = next((c["cam"] for c in sel if c["cam"]), None)
    new = {"r": r0, "c": c0, "rs": r1 - r0 + 1, "cs": c1 - c0 + 1, "cam": keep}
    rest = [c for i, c in enumerate(cells) if i not in idxs]
    out = dict(layout, cells=_sort(rest + [new]))
    return out, out["cells"].index(new), None


def split(layout, idxs):
    """Separa las celdas fusionadas seleccionadas en celdas 1x1."""
    cells = []
    for i, c in enumerate(layout["cells"]):
        if i in idxs and (c["rs"] > 1 or c["cs"] > 1):
            for a in range(c["rs"]):
                for b in range(c["cs"]):
                    cells.append({"r": c["r"] + a, "c": c["c"] + b, "rs": 1, "cs": 1,
                                  "cam": c["cam"] if a == 0 and b == 0 else None})
        else:
            cells.append(c)
    return dict(layout, cells=_sort(cells))
