from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from billing.models import Product, Supplier
from shared.decorators import audit_action, permission_required_any
from shared.column_export import export_visible_columns_excel, export_visible_columns_pdf

from .column_config import (
    get_purchase_visible_columns, get_all_purchase_columns,
    validate_purchase_visible_columns, PURCHASE_DEFAULT_VISIBLE_COLUMNS
)
from .forms import PurchaseForm, PurchaseDetailFormSet
from .models import Purchase


# =============================================
# CRUD DE PURCHASE - VISTAS BASADAS EN FUNCIONES
# (mismo patrón que billing.views.invoice_*)
# =============================================

def _get_export_value(obj, col_key):
    if col_key == 'id':
        return obj.id
    elif col_key == 'supplier':
        return obj.supplier.name
    elif col_key == 'document_number':
        return obj.document_number
    elif col_key == 'purchase_date':
        return obj.purchase_date.strftime('%d/%m/%Y %H:%M') if obj.purchase_date else '-'
    elif col_key == 'num_items':
        return obj.details.count()
    elif col_key == 'subtotal':
        return obj.subtotal
    elif col_key == 'tax':
        return obj.tax
    elif col_key == 'total':
        return obj.total
    elif col_key == 'is_active':
        return 'Activo' if obj.is_active else 'Inactivo'
    return getattr(obj, col_key, '-')


@permission_required_any('purchasing.view_purchase')
@audit_action('LIST_PURCHASES')
def purchase_list(request):
    """Lista todas las compras con su proveedor y total."""
    purchases = Purchase.objects.select_related('supplier').all()
    g = request.GET

    if supplier := g.get('supplier', ''):
        purchases = purchases.filter(supplier_id=supplier)
    if document := g.get('document_number', '').strip():
        purchases = purchases.filter(document_number__icontains=document)
    if date_from := g.get('date_from', '').strip():
        purchases = purchases.filter(purchase_date__date__gte=date_from)
    if date_to := g.get('date_to', '').strip():
        purchases = purchases.filter(purchase_date__date__lte=date_to)

    # Columnas visibles (selector de columnas)
    visible_columns_list = request.session.get('purchase_visible_columns', PURCHASE_DEFAULT_VISIBLE_COLUMNS)
    is_valid, visible_columns_list = validate_purchase_visible_columns(visible_columns_list)

    # Export (respeta las columnas visibles seleccionadas)
    export = g.get('export')
    if export in ('excel', 'pdf'):
        all_columns = get_all_purchase_columns()
        if export == 'excel':
            return export_visible_columns_excel(purchases, visible_columns_list, all_columns, _get_export_value, 'Compras', 'Compras')
        return export_visible_columns_pdf(purchases, visible_columns_list, all_columns, _get_export_value, 'Listado de Compras', 'Compras')

    paginator = Paginator(purchases, 10)
    page_obj = paginator.get_page(g.get('page'))

    params = g.copy()
    params.pop('page', None)

    return render(request, 'purchasing/purchase_list.html', {
        'items': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'paginator': paginator,
        'search_params': params.urlencode(),
        'suppliers': Supplier.objects.order_by('name'),
        'visible_columns': get_purchase_visible_columns(visible_columns_list),
        'all_columns': get_all_purchase_columns(),
        'visible_columns_list': visible_columns_list,
    })


@permission_required_any('purchasing.add_purchase')
@audit_action('CREATE_PURCHASE')
def purchase_create(request):
    """Crea una compra con sus líneas de detalle, calcula IVA 15% y
    reto opcional: reabastece el stock de cada producto comprado."""
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        formset = PurchaseDetailFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardar cabecera (sin commit para poder asignar totales después)
                    purchase = form.save(commit=False)
                    purchase.save()

                    # Asignar la compra al formset y guardar las líneas
                    formset.instance = purchase
                    formset.save()

                    # Calcular totales a partir de las líneas guardadas
                    subtotal = sum(d.subtotal for d in purchase.details.all())
                    purchase.subtotal = subtotal
                    purchase.tax = subtotal * Decimal('0.15')   # IVA 15%
                    purchase.total = purchase.subtotal + purchase.tax
                    purchase.save()

                    # Reto opcional: la compra reabastece inventario (la venta resta, la compra suma)
                    for detail in purchase.details.all():
                        Product.objects.filter(pk=detail.product_id).update(
                            stock=F('stock') + detail.quantity
                        )
            except IntegrityError:
                messages.error(
                    request,
                    f'Ya existe una compra con el documento '
                    f'"{form.cleaned_data.get("document_number")}" para este proveedor.'
                )
            else:
                messages.success(
                    request,
                    f'Compra #{purchase.id} registrada. Total: ${purchase.total}'
                )
                return redirect('purchasing:purchase_list')
    else:
        form = PurchaseForm()
        formset = PurchaseDetailFormSet()

    return render(request, 'purchasing/purchase_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Nueva compra',
    })


@permission_required_any('purchasing.view_purchase')
@audit_action('VIEW_PURCHASE')
def purchase_detail(request, pk):
    """Muestra el detalle completo de una compra."""
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier')
                        .prefetch_related('details__product', 'details__product__brand'),
        pk=pk
    )
    details = purchase.details.all()
    return render(request, 'purchasing/purchase_detail.html', {
        'purchase': purchase,
        'details': details,
        'total_units': sum(d.quantity for d in details),
    })


@permission_required_any('purchasing.delete_purchase')
@audit_action('DELETE_PURCHASE')
def purchase_delete(request, pk):
    """Elimina una compra y todas sus líneas (CASCADE). Solo personal staff."""
    purchase = get_object_or_404(Purchase, pk=pk)

    if not request.user.is_staff:
        messages.error(request, 'No tienes permiso para eliminar compras. Se requiere acceso de staff.')
        return redirect('purchasing:purchase_list')

    if request.method == 'POST':
        purchase_id = purchase.id
        purchase.delete()
        messages.success(request, f'Compra #{purchase_id} eliminada.')
        return redirect('purchasing:purchase_list')

    return render(request, 'purchasing/purchase_confirm_delete.html', {'object': purchase})


@login_required
def purchase_update_visible_columns(request):
    """Actualizar columnas visibles para el listado de compras"""
    import json

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        visible_columns = data.get('visible_columns', [])
        is_valid, validated_columns = validate_purchase_visible_columns(visible_columns)
        request.session['purchase_visible_columns'] = validated_columns
        request.session.modified = True
        return JsonResponse({
            'success': True,
            'visible_columns': validated_columns,
            'message': f'Mostrando {len(validated_columns)} de {len(get_all_purchase_columns())} columnas'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

