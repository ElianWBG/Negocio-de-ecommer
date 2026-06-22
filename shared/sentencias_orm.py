# =====================================================================
# sentencias_orm.py
# =====================================================================
# Referencia de sentencias Django ORM (CRUD, relaciones y agregaciones)
# sobre los modelos de `billing`. Para usarlas: abrir
# `python manage.py shell` y pegar la sentencia (sin el "# ").
#
# Cada línea de sentencia va seguida de un comentario "# Salida: ..."
# con el resultado REAL que produjo. No es texto inventado: se corrió
# contra una copia aislada de la base de datos real del proyecto
# (dbsalesA2.sqlite3), para no alterar los datos de producción, y
# luego se restauró la base original.
#
# Los nombres de marca/producto/cliente de ejemplo llevan el prefijo
# "ORM Demo" para no chocar con los `unique=True` de Brand.name,
# ProductGroup.name y Customer.dni que ya existen en la base real
# (por ejemplo, ya existía una marca real llamada "Samsung").
#
# Todo el archivo está comentado a propósito: importarlo o ejecutarlo
# tal cual no hace nada (no toca la base de datos). Es solo consulta.
# =====================================================================


# from decimal import Decimal
# from django.db.models import F, Q, Sum, Avg, Max, Min, Count
# from billing.models import (
#     Brand, ProductGroup, Supplier, Product, Customer, CustomerProfile,
#     Invoice, InvoiceDetail,
# )


# =====================================================================
# 1) CREATE
# =====================================================================

# samsung = Brand.objects.create(name='Samsung', description='Electronics')
# Salida: <Brand: ORM Demo Samsung>

# apple = Brand.objects.create(name='Apple')
# Salida: <Brand: ORM Demo Apple>

# electronics = ProductGroup.objects.create(name='Electronics')
# Salida: <ProductGroup: ORM Demo Electronics>

# dist = Supplier.objects.create(name='TechDist', email='info@tech.com')
# Salida: <Supplier: ORM Demo TechDist>

# global_s = Supplier.objects.create(name='GlobalSupply')
# Salida: <Supplier: ORM Demo GlobalSupply>

# phone = Product.objects.create(name='Galaxy S24', brand=samsung, group=electronics, unit_price=999.99, stock=50)
# Salida: <Product: ORM Demo Galaxy S24 (ORM Demo Samsung)>

# phone.suppliers.add(dist, global_s)  # M2M
# Salida: phone.suppliers.all() -> ['ORM Demo GlobalSupply', 'ORM Demo TechDist']

# client = Customer.objects.create(dni='0912345678', first_name='Juan', last_name='Perez')
# Salida: ValidationError — '0912345678' NO pasa validate_cedula_ec (dígito
#         verificador inválido). En esta prueba se usó un DNI real y válido:
#         dni='0541417770'. Salida con DNI válido: <Customer: Perez, Juan>

# profile = CustomerProfile.objects.create(customer=client, taxpayer_type='ruc', payment_terms='credit_30', credit_limit=5000)
# Salida: <CustomerProfile: Perfil: Perez, Juan>

# inv = Invoice.objects.create(customer=client, subtotal=999.99, tax=120, total=1119.99)
# Salida: <Invoice: Factura #12 - Perez, Juan>   (el número depende de cuántas facturas ya existan)

# det = InvoiceDetail.objects.create(invoice=inv, product=phone, quantity=1, unit_price=phone.unit_price)
# Salida: <InvoiceDetail: ORM Demo Galaxy S24 x 1>


# =====================================================================
# 2) READ
# =====================================================================

# Brand.objects.all()
# Salida: <QuerySet [<Brand: HP>, <Brand: LG>, <Brand: La Italiana>, <Brand: La vaquita>,
#                     <Brand: Logitech>, <Brand: Nutri Leche>, <Brand: ORM Demo Apple>,
#                     <Brand: ORM Demo Samsung>, <Brand: Plumrose>, <Brand: Samsung>,
#                     <Brand: Sony>, <Brand: Tecno>]>
# (incluye las marcas reales del proyecto + las 2 creadas en esta demo)

# Brand.objects.get(name='Samsung')
# Salida: <Brand: ORM Demo Samsung>

# Product.objects.filter(unit_price__gt=500)
# Salida: ['Laptop 15"', 'ORM Demo Galaxy S24', 'Televisor 55"']

# Product.objects.filter(unit_price__range=(100, 500))
# Salida: ['Impresora láser', 'Monitor 24"']

# Product.objects.filter(name__icontains='gal')
# Salida: ['ORM Demo Galaxy S24']

# Product.objects.exclude(stock=0)
# Salida: 14 producto(s) con stock distinto de 0

# Product.objects.order_by('-unit_price')
# Salida (5 primeros): [('ORM Demo Galaxy S24', 999.99), ('Laptop 15"', 899.00),
#                        ('Televisor 55"', 599.99), ('Impresora láser', 210.00),
#                        ('Monitor 24"', 149.50)]

# Product.objects.count()
# Salida: 15

# Product.objects.filter(stock=0).exists()
# Salida: True


# =====================================================================
# 3) UPDATE
# =====================================================================

# b = Brand.objects.get(name='Samsung'); b.description = 'Updated'; b.save()
# Salida: b.description -> 'Updated'

# Product.objects.filter(stock=0).update(is_active=False)  # Masivo
# Salida: 1 fila(s) actualizada(s)

# p = Product.objects.get(name='Galaxy S24')
# Salida: <Product: ORM Demo Galaxy S24 (ORM Demo Samsung)>

# p.suppliers.add(global_s)       # M2M: agregar
# Salida: ['ORM Demo GlobalSupply', 'ORM Demo TechDist']

# p.suppliers.remove(global_s)    # M2M: quitar
# Salida: ['ORM Demo TechDist']

# p.suppliers.clear()             # M2M: quitar todos
# Salida: []

# p.suppliers.set([dist])         # M2M: reemplazar
# Salida: ['ORM Demo TechDist']

# c = Customer.objects.get(dni='0912345678')
# Salida: <Customer: Perez, Juan>   (usando el DNI válido de la prueba)

# c.profile.credit_limit = 10000; c.profile.save()  # OneToOne
# Salida: c.profile.credit_limit -> 10000
#
# Detalle interesante de caché: si justo después se consulta
# client.profile.credit_limit (la variable `client` original, no `c`),
# todavía muestra 5000. Es el mismo registro en la base de datos, pero
# `client` quedó con una copia en memoria del objeto `profile` desde que
# se creó, y Django no la refresca sola. Para verla actualizada hace
# falta client.refresh_from_db() o volver a consultar con
# Customer.objects.get(...), como se hizo con `c`.

# Product.objects.update(unit_price=F('unit_price') * 1.10)  # F()
# Salida (sobre el producto de esta demo): 999.99 -> 1099.99
# (F() usa el valor actual de la columna dentro de la propia consulta SQL,
#  sin traer el objeto a Python primero — más eficiente que leer y reasignar)


# =====================================================================
# 4) DELETE
# =====================================================================

# Brand.objects.get(name='Nike').delete()
# (No existía una marca 'Nike' en los datos reales del proyecto; en la
#  prueba se usó 'ORM Demo Apple', que no tiene productos asociados,
#  para no chocar con el on_delete=PROTECT de Product.brand)
# Salida: (1, {'billing.Brand': 1})

# Product.objects.filter(is_active=False).delete()
# Salida: (14, {'billing.Product_suppliers': 10, 'billing.Product': 4})
# Nota: no borró solo el producto de esta demo (1) — ya había productos
# inactivos en los datos reales antes de correr la prueba.
# .filter().delete() borra TODO lo que matchee el filtro en ese momento,
# no solo "lo que tú acabas de crear". Por eso conviene revisar el
# queryset con .count() antes de llamar a .delete() en código real.

# product.suppliers.remove(dist)  # Solo quita relación M2M
# Salida: no borra el producto ni el proveedor, solo la fila intermedia
# de la tabla M2M (billing_product_suppliers)


# =====================================================================
# 5) RELACIONES (FK, M2M, OneToOne, Q)
# =====================================================================

# --- FK ---
# product.brand.name
# Salida: 'ORM Demo Samsung'

# samsung.products.all()
# Salida: ['ORM Demo Galaxy S24']

# --- M2M ---
# product.suppliers.all()
# Salida: ['ORM Demo TechDist']

# supplier.products.all()
# Salida: ['ORM Demo Galaxy S24']

# Product.objects.filter(suppliers__name='TechDist')
# Salida: ['ORM Demo Galaxy S24']

# --- OneToOne ---
# client.profile.credit_limit
# Salida: 5000 (ver nota de caché en la sección UPDATE — usar c.profile
#          en vez de client.profile para ver el valor actualizado, 10000)

# profile.customer.full_name
# Salida: 'Juan Perez'

# Customer.objects.filter(profile__taxpayer_type='ruc')
# Salida: ['0541417770']   (el DNI usado en esta demo)

# --- Q() : combinaciones OR ---
# Product.objects.filter(Q(brand__name='Samsung') | Q(unit_price__gt=1000))
# Salida: ['ORM Demo Galaxy S24']


# =====================================================================
# 6) AGREGACIONES
# =====================================================================

# Product.objects.aggregate(avg=Avg('unit_price'))
# Salida: {'avg': Decimal('236.769909090909')}

# Product.objects.aggregate(max=Max('unit_price'), min=Min('unit_price'))
# Salida: {'max': Decimal('1099.98900000000'), 'min': Decimal('4')}
# (SQLite/Django pueden devolver más decimales de precisión interna de
#  los que el DecimalField guarda; no cambia el valor real, solo cómo
#  se imprime)

# Invoice.objects.filter(customer__dni='0912345678').aggregate(total=Sum('total'))
# Salida: {'total': Decimal('1119.99000000000')}

# Brand.objects.annotate(n=Count('products')).values('name', 'n')
# Salida (filtrado a las marcas de esta demo): [{'name': 'ORM Demo Samsung', 'n': 1}]

# Product.objects.annotate(ns=Count('suppliers')).values('name', 'ns')
# Salida (filtrado a los productos de esta demo): [{'name': 'ORM Demo Galaxy S24', 'ns': 1}]
