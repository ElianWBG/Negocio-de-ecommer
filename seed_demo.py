"""Datos demo para el catálogo (marcas=tiendas, categorías, productos). Idempotente."""
import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from billing.models import Brand, ProductGroup, Product

cats = ["Electrónica", "Computación", "Ropa", "Hogar", "Deportes", "Belleza"]
G = {n: ProductGroup.objects.get_or_create(name=n, defaults={"is_active": True})[0] for n in cats}

stores = ["Tecnogamer", "ModaViva", "CasaHogar", "NutriFit", "PixelStore"]
B = {n: Brand.objects.get_or_create(name=n, defaults={"is_active": True})[0] for n in stores}

items = [
    ("Teclado mecánico RGB", "Tecnogamer", "Electrónica", "45.90", 30),
    ("Mouse gamer 16000 DPI", "Tecnogamer", "Electrónica", "29.50", 50),
    ("Auriculares 7.1 Surround", "Tecnogamer", "Electrónica", "59.00", 18),
    ("Monitor 27\" 165Hz", "PixelStore", "Computación", "219.00", 8),
    ("SSD NVMe 1TB", "PixelStore", "Computación", "89.90", 40),
    ("Laptop 14\" Ryzen 5", "PixelStore", "Computación", "640.00", 0),
    ("Webcam Full HD", "PixelStore", "Computación", "34.00", 25),
    ("Camiseta oversize algodón", "ModaViva", "Ropa", "19.99", 60),
    ("Jeans slim fit", "ModaViva", "Ropa", "39.90", 35),
    ("Chaqueta impermeable", "ModaViva", "Ropa", "74.50", 12),
    ("Zapatillas running", "NutriFit", "Deportes", "82.00", 20),
    ("Mancuernas ajustables 20kg", "NutriFit", "Deportes", "120.00", 6),
    ("Proteína whey 2kg", "NutriFit", "Belleza", "48.00", 44),
    ("Botella térmica 1L", "NutriFit", "Deportes", "15.50", 0),
    ("Juego de sábanas king", "CasaHogar", "Hogar", "54.00", 22),
    ("Set ollas antiadherentes", "CasaHogar", "Hogar", "98.90", 14),
    ("Lámpara LED de escritorio", "CasaHogar", "Hogar", "27.30", 33),
    ("Organizador modular x6", "CasaHogar", "Hogar", "21.00", 48),
]

created = 0
for name, store, cat, price, stock in items:
    _, was = Product.objects.get_or_create(
        name=name, brand=B[store],
        defaults={"group": G[cat], "unit_price": Decimal(price), "stock": stock, "is_active": True},
    )
    created += was

print("Categorías:", ProductGroup.objects.count())
print("Tiendas (marcas):", Brand.objects.count())
print("Productos totales:", Product.objects.count(), "| nuevos:", created)
