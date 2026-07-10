from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Count
from django.shortcuts import render

from billing.models import Invoice, InvoiceDetail, Product
from purchasing.models import Purchase


@login_required
def reportes_index(request):
    """Página de inicio del área de reportes: enlaces a cada reporte."""
    return render(request, 'reportes/index.html')


@login_required
def cuentas_por_cobrar(request):
    """Resumen de cuánto le deben a la empresa: facturas a crédito pendientes."""
    facturas = Invoice.objects.filter(
        tipo_pago='credito', estado='pendiente'
    ).select_related('customer').order_by('-invoice_date')
    total_por_cobrar = facturas.aggregate(t=Sum('saldo'))['t'] or Decimal('0')
    return render(request, 'reportes/cuentas_por_cobrar.html', {
        'facturas': facturas, 'total_por_cobrar': total_por_cobrar,
    })


@login_required
def cuentas_por_pagar(request):
    """Resumen de cuánto debe la empresa a proveedores: compras a crédito pendientes."""
    compras = Purchase.objects.filter(
        tipo_pago='credito', estado='pendiente'
    ).select_related('supplier').order_by('-purchase_date')
    total_por_pagar = compras.aggregate(t=Sum('saldo'))['t'] or Decimal('0')
    return render(request, 'reportes/cuentas_por_pagar.html', {
        'compras': compras, 'total_por_pagar': total_por_pagar,
    })


@login_required
def ventas_por_periodo(request):
    """Total vendido en un rango de fechas (por defecto, todo el historial)."""
    g = request.GET
    facturas = Invoice.objects.filter(is_active=True).select_related('customer')

    date_from = g.get('date_from', '').strip()
    date_to = g.get('date_to', '').strip()
    if date_from:
        facturas = facturas.filter(invoice_date__date__gte=date_from)
    if date_to:
        facturas = facturas.filter(invoice_date__date__lte=date_to)

    facturas = facturas.order_by('-invoice_date')
    totales = facturas.aggregate(
        total_ventas=Sum('total'), cantidad_facturas=Count('id')
    )
    return render(request, 'reportes/ventas_por_periodo.html', {
        'facturas': facturas,
        'total_ventas': totales['total_ventas'] or Decimal('0'),
        'cantidad_facturas': totales['cantidad_facturas'] or 0,
        'date_from': date_from, 'date_to': date_to,
    })


@login_required
def productos_mas_vendidos(request):
    """Ranking de productos por unidades vendidas (sumando todas las facturas activas)."""
    ranking = (
        InvoiceDetail.objects
        .filter(invoice__is_active=True)
        .values('product__id', 'product__name')
        .annotate(unidades_vendidas=Sum('quantity'), total_vendido=Sum('subtotal'))
        .order_by('-unidades_vendidas')[:20]
    )
    return render(request, 'reportes/productos_mas_vendidos.html', {'ranking': ranking})


@login_required
def stock_bajo(request):
    """Productos cuyo stock está por debajo de un umbral configurable (?umbral=10)."""
    try:
        umbral = int(request.GET.get('umbral', 10))
    except ValueError:
        umbral = 10
    productos = Product.objects.filter(is_active=True, stock__lt=umbral).order_by('stock')
    return render(request, 'reportes/stock_bajo.html', {'productos': productos, 'umbral': umbral})
