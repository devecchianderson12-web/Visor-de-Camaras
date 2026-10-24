"""Genera assets/watcher.png y assets/watcher.ico (icono 'The Watcher': un ojo vigilante).
Uso (opcional, el icono ya viene generado):  pip install pillow  &&  python tools/make_icon.py"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024                     # lienzo de trabajo (se reduce con suavizado)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def almond_points(cx, cy, w, h, n=240):
    pts_top, pts_bot = [], []
    for i in range(n + 1):
        x = -1 + 2 * i / n
        y = h * (1 - abs(x) ** 2.0) ** 0.9
        pts_top.append((cx + x * w, cy - y))
        pts_bot.append((cx + x * w, cy + y))
    return pts_top + pts_bot[::-1]


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # fondo: cuadrado redondeado con degradado vertical azul noche
    bg = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(bg)
    for y in range(S):
        d.line([(0, y), (S, y)], fill=lerp((22, 34, 62), (7, 11, 22), y / S) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(bg, (0, 0), mask)

    cx, cy = S / 2, S / 2
    w, h = S * 0.40, S * 0.235
    almond = almond_points(cx, cy, w, h)

    # resplandor exterior
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(almond, fill=(60, 190, 255, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.035))
    img.alpha_composite(glow)

    # contorno del ojo (almendra más grande en cian) y esclerótica
    outer = almond_points(cx, cy, w * 1.04, h * 1.12)
    ImageDraw.Draw(img).polygon(outer, fill=(72, 205, 255, 255))
    inner = almond_points(cx, cy, w * 0.96, h * 0.93)
    sclera = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sclera)
    sd.polygon(inner, fill=(236, 243, 252, 255))
    amask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(amask).polygon(inner, fill=255)

    # iris con degradado radial + anillo + pupila + brillo, recortados a la almendra
    iris_r = h * 0.98
    iris = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    idr = ImageDraw.Draw(iris)
    steps = 60
    for i in range(steps):
        t = i / (steps - 1)
        r = iris_r * (1 - t)
        idr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=lerp((14, 70, 170), (40, 190, 255), t) + (255,))
    ring = iris_r * 0.97
    idr.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=(8, 30, 80, 255), width=int(S * 0.012))
    pr = iris_r * 0.42
    idr.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(3, 6, 14, 255))
    hr = iris_r * 0.15
    hx, hy = cx - iris_r * 0.28, cy - iris_r * 0.30
    idr.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(255, 255, 255, 235))
    sclera.alpha_composite(iris)
    img.paste(sclera, (0, 0), amask)

    # pestañas/párpado: sombra suave arriba para dar profundidad
    shade = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shade).polygon(almond_points(cx, cy - h * 0.55, w * 0.9, h * 0.55), fill=(0, 20, 50, 70))
    shade = shade.filter(ImageFilter.GaussianBlur(S * 0.02))
    shade.putalpha(ImageChops.multiply(shade.getchannel("A"), amask))   # solo dentro del ojo
    img.alpha_composite(shade)
    return img


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    big = build()
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "watcher.png"))
    big.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT, "watcher.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # vista previa para revisar
    prev = Image.new("RGBA", (256 + 16 + 64 + 32, 256), (40, 40, 40, 255))
    prev.alpha_composite(big.resize((256, 256), Image.LANCZOS), (0, 0))
    prev.alpha_composite(big.resize((64, 64), Image.LANCZOS), (272, 8))
    prev.alpha_composite(big.resize((32, 32), Image.LANCZOS), (344, 8))
    prev.save("/tmp/preview.png")
    print("ok")
