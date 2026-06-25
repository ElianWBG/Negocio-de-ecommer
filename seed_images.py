"""Imágenes placeholder (Pillow) + galería multi-imagen + WhatsApp demo. Idempotente."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from billing.models import Product, ProductImage, Brand

W, H = 800, 600
OUT = Path(settings.MEDIA_ROOT) / "products"
OUT.mkdir(parents=True, exist_ok=True)

CAT_COLOR = {
    "Electrónica": (79, 70, 229),
    "Computación": (14, 165, 233),
    "Ropa": (236, 72, 153),
    "Hogar": (245, 158, 11),
    "Deportes": (16, 185, 129),
    "Belleza": (168, 85, 247),
}
DEFAULT = (100, 116, 139)
# Tienda (marca) -> WhatsApp demo
STORE_WA = {
    "Tecnogamer": "593990000001",
    "PixelStore": "593990000002",
    "ModaViva": "593990000003",
    "NutriFit": "593990000004",
    "CasaHogar": "593990000005",
}


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


def make_image(p, idx):
    """Genera una imagen para el producto. idx=0 portada; idx>0 variantes."""
    cat = p.group.name if p.group else ""
    base = CAT_COLOR.get(cat, DEFAULT)
    bg = mix(base, 0.10 + 0.16 * idx)  # cada vista un poco más clara

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 90], fill=base)
    d.text((40, 28), cat.upper(), font=f_tag, fill=(255, 255, 255))
    d.ellipse([W - 220, H - 220, W + 40, H + 40], fill=mix(base, 0.22 + 0.10 * idx))

    title = p.name if idx == 0 else f"{p.name}"
    lines = wrap(d, title, f_title, W - 120)
    line_h = 64
    y = (H - line_h * len(lines)) // 2 - 10
    for ln in lines:
        tw = d.textlength(ln, font=f_title)
        d.text(((W - tw) / 2, y), ln, font=f_title, fill=(255, 255, 255))
        y += line_h

    label = f"Vendido por {p.brand.name}" if idx == 0 else f"Vista {idx + 1}"
    d.text((40, H - 64), label, font=f_store, fill=mix(base, 0.55))

    fname = f"demo-{p.pk}-{slug(p.name)}-{idx}.jpg"
    img.save(OUT / fname, "JPEG", quality=88)
    return f"products/{fname}"


EXTRA = 2  # imágenes adicionales por producto (total = 1 portada + EXTRA)
covers = extras = 0
for p in Product.objects.select_related("brand", "group"):
    # Portada
    p.image.name = make_image(p, 0)
    p.save(update_fields=["image"])
    covers += 1
    # Galería (variantes)
    for idx in range(1, EXTRA + 1):
        name = make_image(p, idx)
        ProductImage.objects.update_or_create(
            product=p, order=idx, defaults={"image": name}
        )
        extras += 1

# WhatsApp demo por tienda (marca)
wa = 0
for name, number in STORE_WA.items():
    updated = Brand.objects.filter(name=name).update(whatsapp=number)
    wa += updated

print("Portadas:", covers, "| imágenes de galería:", extras, "| tiendas con WhatsApp:", wa)
print("Carpeta:", OUT)
