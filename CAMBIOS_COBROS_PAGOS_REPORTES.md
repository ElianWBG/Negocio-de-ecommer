# Cambios agregados a tu proyecto sales_a2

Este zip es tu proyecto original **con 3 módulos nuevos ya integrados y
probados**, basados en el caso de estudio "Integración de Pagos de
Créditos" (`CASO_DE_ESTUDIO_PRACTICO_2`) más un área de reportes.

Todo fue probado de extremo a extremo antes de entregártelo: `check`,
`makemigrations`, `migrate`, y flujos completos reales vía POST (crear
factura/compra a crédito, registrar pagos parciales, editar, eliminar,
intentar sobrepagar, intentar pagar una factura anulada, pagos negativos
y en cero) — incluyendo un bug real que encontré y corregí en el camino
(ver sección "Bug encontrado y corregido" más abajo).

## 1. Campos nuevos en `Invoice` y `Purchase`

El caso de estudio asume que tus facturas/compras ya tienen `tipo_pago`,
`saldo` y `estado` — tu proyecto no los tenía, así que se agregaron:

- `tipo_pago`: `'contado'` / `'credito'`
- `saldo`: lo que falta por cobrar/pagar
- `estado`: `'pendiente'` / `'pagada'` / `'anulada'`

Al crear una factura o compra **a crédito**, el saldo inicial es el total
y queda `pendiente`. Al contado, queda con saldo 0 y `pagada` de una vez.
Los registros históricos que ya tenías (todos "al contado" por defecto)
se corrigieron a `estado='pagada'`, `saldo=0` para que queden consistentes.

## 2. App `cobros` — cuentas por cobrar

- Lista de facturas a crédito pendientes (`/cobros/`)
- Registrar un pago sobre una factura específica
- Historial de pagos por factura
- Editar / eliminar un pago (recalcula el saldo automáticamente)
- Reglas de negocio aplicadas: no pagar de más, no pagos negativos/cero,
  no pagar facturas anuladas, todo dentro de `transaction.atomic()`

## 3. App `pagos` — cuentas por pagar

Exactamente el mismo patrón que `cobros`, pero para compras a proveedores
(`/pagos/`).

## 4. App `reportes`

Un panel (`/reportes/`) con 5 reportes:
- Cuentas por cobrar (total pendiente + detalle)
- Cuentas por pagar (total pendiente + detalle)
- Ventas por periodo (filtro de fechas)
- Productos más vendidos (ranking por unidades)
- Stock bajo (umbral configurable)

## 5. Navbar actualizado

Se agregaron los enlaces "Cobros", "Pagos" y "Reportes" en
`billing/templates/billing/base.html`, respetando los mismos grupos de
permisos que ya tenía el proyecto (Vendedor/Analista de Compras/Administrador).

## Bug encontrado y corregido (vale la pena que lo leas)

Al probar la edición de un pago, encontré que el saldo no se recalculaba
bien. La causa: `form.is_valid()` en Django **ya modifica el objeto
`instance` internamente** con los datos nuevos del formulario, antes de
que se llame a `.save()`. El código original capturaba el "valor
anterior" *después* de `is_valid()`, así que en realidad ya estaba
capturando el valor nuevo, no el viejo — el saldo terminaba mal
calculado. La corrección: capturar `valor_anterior` **antes** de
construir el formulario, apenas se carga el objeto desde la base de
datos. Está corregido en `cobros/views.py` y `pagos/views.py`
(`cobro_update` / `pago_update`). Es un buen ejemplo de un bug de Django
poco obvio — no duele en la creación, solo en la edición.

## Cómo correrlo

```powershell
.\ent_sales_a2\Scripts\Activate.ps1     # si conservas tu venv
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Las migraciones de los campos nuevos y de las 2 apps ya vienen generadas
dentro del zip — solo falta aplicarlas con `migrate`.

## Simplificaciones a propósito

- El campo `factura`/`compra` en el formulario de pago va oculto — se fija
  desde la URL (siempre registras un pago PARA una factura específica que
  ya elegiste en la lista de pendientes), el usuario no la selecciona en
  un desplegable.
- "Eliminar pago" siempre repone el saldo automáticamente. El documento
  original decía "no permitir eliminar cuando deje inconsistente el
  saldo" — la interpretación implementada es que reponer el saldo *es*
  la forma de mantenerlo consistente, así que eliminar siempre está
  permitido mientras la factura no esté anulada.
