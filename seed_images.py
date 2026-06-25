"""Genera imágenes placeholder (Pillow) para los productos demo. Idempotente."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from billing.models import Product

W, H = 800, 600
OUT = Path(settings.MEDIA_ROOT) / "products"
OUT.mkdir(parents=True, exist_ok=True)

# Color de fondo por categoría
CAT_COLOR = {
    "Electrónica": (79, 70, 229),
    "Computación": (14, 165, 233),
    "Ropa": (236, 72, 153),
    "Hogar": (245, 158, 11),
    "Deportes": (16, 185, 129),
    "Belleza": (168, 85, 247),
}
DEFAULT = (100, 116, 139)


def font(size):
    for name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def mix(c, white=0.18):
    return tuple(int(v + (255 - v) * white) for v in c)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def slug(s):
    keep = "abcdefghijklmnopqrstuvwxyz0123456789-"
    s = s.lower().replace(" ", "-")
    return "".join(ch for ch in s if ch in keep) or "prod"


f_tag = font(26)
f_title = font(54)
f_store = font(30)

done = 0
for p in Product.objects.select_related("brand", "group"):
    cat = p.group.name if p.group else ""
    base = CAT_COLOR.get(cat, DEFAULT)
    bg = mix(base, 0.10)

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    # Banda superior con el nombre de categoría
    d.rectangle([0, 0, W, 90], fill=base)
    d.text((40, 28), cat.upper(), font=f_tag, fill=(255, 255, 255))

    # Disco decorativo
    d.ellipse([W - 220, H - 220, W + 40, H + 40], fill=mix(base, 0.22))

    # Título del producto (envuelto, centrado vertical)
    lines = wrap(d, p.name, f_title, W - 120)
    line_h = 64
    total = line_h * len(lines)
    y = (H - total) // 2 - 10
    for ln in lines:
        tw = d.textlength(ln, font=f_title)
        d.text(((W - tw) / 2, y), ln, font=f_title, fill=(255, 255, 255))
        y += line_h

    # Tienda (marca) abajo
    store = f"Vendido por {p.brand.name}" if p.brand else ""
    d.text((40, H - 64), store, font=f_store, fill=mix(base, 0.55))

    fname = f"demo-{p.pk}-{slug(p.name)}.jpg"
    img.save(OUT / fname, "JPEG", quality=88)

    p.image.name = f"products/{fname}"
    p.save(update_fields=["image"])
    done += 1

print("Imágenes generadas y asignadas:", done)
print("Carpeta:", OUT)
