from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from billing.models import Product, Supplier
from shared.decorators import audit_action, permission_required_any, user_can_export
from shared.column_export import export_visible_columns_excel, export_visible_columns_pdf
from shared.validators import parse_date_param

from creditos_compras.services import generar_cuotas

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
    elif col_key == 'tipo_pago':
        return obj.get_tipo_pago_display()
    elif col_key == 'estado':
        return obj.get_estado_display()
    elif col_key == 'saldo':
        return obj.saldo
    return getattr(obj, col_key, '-')


@permission_required_any('purchasing.view_purchase')
@audit_action('LIST_PURCHASES')
def purchase_list(request):
    """Lista todas las compras con su proveedor y total."""
    purchases = Purchase.objects.select_related('supplier').all()
    g = request.GET

    if (supplier := g.get('supplier', '')) and supplier.isdigit():
        purchases = purchases.filter(supplier_id=supplier)
    if document := g.get('document_number', '').strip():
        purchases = purchases.filter(document_number__icontains=document)
    if parsed_from := parse_date_param(g.get('date_from', '')):
        purchases = purchases.filter(purchase_date__date__gte=parsed_from)
    if parsed_to := parse_date_param(g.get('date_to', '')):
        purchases = purchases.filter(purchase_date__date__lte=parsed_to)

    # Columnas visibles (selector de columnas)
    visible_columns_list = request.session.get('purchase_visible_columns', PURCHASE_DEFAULT_VISIBLE_COLUMNS)
    is_valid, visible_columns_list = validate_purchase_visible_columns(visible_columns_list)

    # Export (respeta las columnas visibles seleccionadas)
    export = g.get('export')
    if export in ('excel', 'pdf') and not user_can_export(request, 'purchasing.export_purchase'):
        messages.error(request, 'No tienes permiso para exportar esta información.')
        export = None
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

                    if purchase.tipo_pago == 'credito':
                        purchase.saldo = purchase.total
                        purchase.estado = 'pendiente'

                    purchase.save()

                    # Reto opcional: la compra reabastece inventario (la venta resta, la compra suma)
                    for detail in purchase.details.all():
                        Product.objects.filter(pk=detail.product_id).update(
                            stock=F('stock') + detail.quantity
                        )

                    # Si es a crédito y se indicó número de cuotas, se genera
                    # el cronograma de una vez (si no, queda pendiente y se
                    # puede generar después desde el detalle de la compra).
                    numero_cuotas = form.cleaned_data.get('numero_cuotas')
                    if purchase.tipo_pago == 'credito' and numero_cuotas:
                        generar_cuotas(purchase, numero_cuotas)
            except IntegrityError:
                messages.error(
                    request,
                    f'Ya existe una compra con el documento '
                    f'"{form.cleaned_data.get("document_number")}" para este proveedor.'
                )
            else:
                mensaje = f'Compra #{purchase.id} registrada. Total: ${purchase.total}'
                if purchase.tipo_pago == 'credito' and form.cleaned_data.get('numero_cuotas'):
                    mensaje += f'. Se generaron {form.cleaned_data["numero_cuotas"]} cuotas.'
                messages.success(request, mensaje)
                return redirect('purchasing:purchase_list')
    else:
        siguiente_numero = f'OC-{Purchase.objects.count() + 1:06d}'
        form = PurchaseForm(initial={'document_number': siguiente_numero})
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
        'tiene_cuotas': purchase.cuotas.exists(),
        'tiene_pagos_libres': purchase.pagos.exists(),
    })


@permission_required_any('purchasing.delete_purchase')
@audit_action('DELETE_PURCHASE')
def purchase_delete(request, pk):
    """Elimina una compra y todas sus líneas (CASCADE). Solo personal staff.

    Revierte el stock que la compra sumó al inventario: la compra suma stock al
    crearse, así que borrarla debe restarlo para no dejar unidades fantasma
    (simétrico a cómo la anulación de una factura repone el stock vendido).
    """
    from django.db.models.deletion import ProtectedError
    from django.db.models.functions import Greatest

    purchase = get_object_or_404(Purchase, pk=pk)

    if request.method == 'POST':
        purchase_id = purchase.id
        try:
            with transaction.atomic():
                # Restar el stock que se sumó al crear la compra. Greatest evita
                # dejar stock negativo si parte de esas unidades ya se vendió.
                for detail in purchase.details.select_related('product').all():
                    Product.objects.filter(pk=detail.product_id).update(
                        stock=Greatest(F('stock') - detail.quantity, 0)
                    )
                purchase.delete()
        except ProtectedError:
            messages.error(
                request,
                'No se puede eliminar esta compra porque tiene cuotas o pagos '
                'registrados. Elimínalos primero.'
            )
            return redirect('purchasing:purchase_detail', pk=purchase_id)
        messages.success(request, f'Compra #{purchase_id} eliminada y stock revertido.')
        return redirect('purchasing:purchase_list')

    return render(request, 'purchasing/purchase_confirm_delete.html', {'object': purchase})


@permission_required_any('purchasing.view_purchase')
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

