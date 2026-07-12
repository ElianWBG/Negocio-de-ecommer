import logging
import secrets
import uuid
from decimal import Decimal

logger = logging.getLogger(__name__)
from billing.audit import log_action

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from shared.decorators import permission_required_any
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q, Min, Max
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.models import Product, ProductGroup, Customer, Brand
from . import payphone
from .forms import CustomerRegistrationForm, CustomerLoginForm, CustomerRequestForm
from .models import PurchaseRequest, PurchaseRequestDetail, EmailVerificationToken
from .services import confirm_purchase_request, confirm_purchase_request_credito, InsufficientStockError
CART_SESSION_KEY = 'storefront_cart'


# ---------------------------------------------------------------------
# Helpers del carrito
# ---------------------------------------------------------------------

def _get_cart(request):
    return request.session.setdefault(CART_SESSION_KEY, {})


def _cart_items(request):
    cart = _get_cart(request)
    if not cart:
        return [], Decimal('0')
    products = Product.objects.select_related('brand').filter(pk__in=cart.keys(), is_active=True)
    products_by_id = {str(p.pk): p for p in products}
    items = []
    total = Decimal('0')
    for product_id, quantity in cart.items():
        product = products_by_id.get(product_id)
        if not product:
            continue
        subtotal = product.unit_price * quantity
        total += subtotal
        items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return items, total


def _is_customer(user):
    """True si el usuario autenticado es un cliente (tiene perfil Customer)."""
    return user.is_authenticated and hasattr(user, 'customer_profile')


# ---------------------------------------------------------------------
# Registro, verificación de email y login de clientes
# ---------------------------------------------------------------------

def customer_register(request):
    if _is_customer(request.user):
        return redirect('storefront:catalog_list')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            # Si el usuario ya existe, redirigir al login
            if User.objects.filter(email=d['email']).exists():
                messages.error(request, 'Ya existe una cuenta con ese correo.')
                return render(request, 'storefront/register.html', {'form': form})
            user = User.objects.create_user(
                username=d['email'],
                email=d['email'],
                password=d['password1'],
                first_name=d['first_name'],
                last_name=d['last_name'],
                is_active=True,
            )
            Customer.objects.update_or_create(
                dni=d['dni'],
                defaults={
                    'first_name': d['first_name'],
                    'last_name': d['last_name'],
                    'email': d['email'],
                    'phone': d.get('phone', ''),
                    'address': d.get('address', ''),
                    'accepts_promotions': d.get('accepts_promotions', True),
                    'user': user,
                }
            )
            _send_welcome_email(user)
            cart_snapshot = request.session.get(CART_SESSION_KEY)
            login(request, user)
            if cart_snapshot:
                request.session[CART_SESSION_KEY] = cart_snapshot
                request.session.modified = True
            return redirect('storefront:catalog_list')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'storefront/register.html', {'form': form})


_WELCOME_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bienvenido a __STORE_NAME__</title>
    <style>
        body { margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5; color: #333333; }
        .container { max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .header { background-color: __COLOR__; padding: 30px 20px; text-align: center; color: #ffffff; }
        .header h1 { margin: 0; font-size: 28px; letter-spacing: 1px; }
        .content { padding: 30px 20px; text-align: left; line-height: 1.6; }
        .content h2 { color: __COLOR__; margin-top: 0; font-size: 22px; }
        .button-container { text-align: center; margin: 30px 0; }
        .button { background-color: __COLOR__; color: #ffffff; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; font-size: 16px; }
        .footer { background-color: #eeeeee; padding: 20px; text-align: center; font-size: 12px; color: #666666; line-height: 1.5; }
        .footer a { color: __COLOR__; text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>__STORE_NAME_UPPER__</h1>
        </div>

        <div class="content">
            <h2>¡Tu aventura acaba de comenzar! 🚀🎮</h2>

            <p>Hola, <strong>__NAME__</strong>,</p>
            <p>Nos emociona muchísimo darte la bienvenida. Tu cuenta ha sido creada con éxito usando el correo <strong>__EMAIL__</strong>.</p>

            <p>Ya puedes iniciar sesión y explorar nuestro catálogo, armar tu carrito y hacer tu primer pedido en minutos.</p>

            <div class="button-container">
                <a href="__LOGIN_URL__" class="button">INICIAR SESIÓN Y EXPLORAR</a>
            </div>

            <p>Si tienes alguna duda o necesitas ayuda, simplemente responde a este correo. ¡Estamos aquí para ayudarte!</p>
            <p>¡Que empiecen las partidas!<br><strong>El equipo de __STORE_NAME__</strong></p>
        </div>

        <div class="footer">
            <p>Recibes este correo porque creaste una cuenta en nuestra tienda online __STORE_NAME__.</p>
            <p><strong>__STORE_NAME__</strong>__ADDRESS_LINE__</p>
        </div>
    </div>
</body>
</html>
"""


def _send_welcome_email(user):
    """Envía un correo de bienvenida cuando un cliente se registra.
    Si falla el envío, no interrumpe el registro (fail_silently)."""
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags
    from django.conf import settings
    from billing.models import ConfigNegocio

    if not user.email:
        return
    config = ConfigNegocio.objects.first()
    store_name = (config.nombre_tienda if config else None) or 'Nuestra Tienda'
    color = (config.color_primario if config else None) or '#d84315'
    address_line = f'<br>{config.direccion}' if (config and config.direccion) else ''
    site_url = getattr(settings, 'SITE_URL', 'https://web-production-667ad.up.railway.app')
    login_url = f'{site_url.rstrip("/")}/login/'

    html_content = (
        _WELCOME_EMAIL_TEMPLATE
        .replace('__COLOR__', color)
        .replace('__STORE_NAME_UPPER__', store_name.upper())
        .replace('__STORE_NAME__', store_name)
        .replace('__NAME__', user.first_name or user.email)
        .replace('__EMAIL__', user.email)
        .replace('__LOGIN_URL__', login_url)
        .replace('__ADDRESS_LINE__', address_line)
    )
    try:
        message = EmailMultiAlternatives(
            subject=f'¡Bienvenido/a a {store_name}!',
            body=strip_tags(html_content),
            from_email=None,
            to=[user.email],
        )
        message.attach_alternative(html_content, 'text/html')
        message.send(fail_silently=False)
    except Exception:
        logger.exception('Error sending welcome email to %s', user.email)
        pass

def verify_email_sent(request):
    return render(request, 'storefront/verify_email_sent.html')


def verify_email(request, token):
    try:
        verification = EmailVerificationToken.objects.select_related('user').get(token=token)
    except EmailVerificationToken.DoesNotExist:
        return render(request, 'storefront/verify_email_invalid.html')

    if verification.is_expired:
        verification.delete()
        return render(request, 'storefront/verify_email_invalid.html', {'expired': True})

    user = verification.user
    user.is_active = True
    user.save()
    verification.delete()

    cart_snapshot = request.session.get(CART_SESSION_KEY)
    login(request, user)
    if cart_snapshot:
        request.session[CART_SESSION_KEY] = cart_snapshot
        request.session.modified = True
    messages.success(request, f'¡Bienvenido, {user.first_name}! Tu cuenta está activa.')
    next_url = request.session.pop('next_after_login', None)
    return redirect(next_url or 'storefront:catalog_list')


def customer_login(request):
    if _is_customer(request.user):
        return redirect('storefront:catalog_list')

    if request.method == 'POST':
        form = CustomerLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                username = User.objects.get(email=email).username
            except User.DoesNotExist:
                username = None

            user = authenticate(request, username=username, password=password) if username else None

            if user is None:
                form.add_error(None, 'Correo o contraseña incorrectos.')
            elif not user.is_active:
                form.add_error(None, 'Tu cuenta no está verificada. Revisa tu correo.')
            elif not hasattr(user, 'customer_profile'):
                form.add_error(None, 'Esta cuenta no es de cliente. Usa el panel de administración.')
            else:
                cart_snapshot = request.session.get(CART_SESSION_KEY)
                login(request, user)
                if cart_snapshot:
                    request.session[CART_SESSION_KEY] = cart_snapshot
                    request.session.modified = True
                next_url = request.session.pop('next_after_login', None)
                return redirect(next_url or 'storefront:catalog_list')
    else:
        form = CustomerLoginForm()

    return render(request, 'storefront/login.html', {'form': form})


def customer_logout(request):
    logout(request)
    return redirect('storefront:catalog_list')


# ---------------------------------------------------------------------
# Catálogo público
# ---------------------------------------------------------------------

def catalog_list(request):
    products = (Product.objects.filter(is_active=True)
                .select_related('brand', 'group')
                .prefetch_related('images'))
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(group__name__icontains=query)
        )
    group_id = request.GET.get('group', '').strip()
    if group_id:
        products = products.filter(group_id=group_id)
    # Filtro por "tienda": la marca actúa como vendedor/tienda asociada
    brand_id = request.GET.get('brand', '').strip()
    selected_brand = None
    if brand_id:
        products = products.filter(brand_id=brand_id)
        selected_brand = Brand.objects.filter(pk=brand_id).first()
    cart_count = sum(_get_cart(request).values())

    # Límites de precio para el slider (sobre el conjunto ya filtrado).
    # El slider filtra en vivo del lado cliente; aquí solo damos el rango.
    bounds = products.aggregate(lo=Min('unit_price'), hi=Max('unit_price'))
    price_min = int(bounds['lo'] or 0)
    price_max = int((bounds['hi'] or 0)) + (1 if bounds['hi'] else 0)

    has_filter = bool(query or group_id or brand_id)

    # "Productos totales": TODO el catálogo activo, paginado (solo en portada).
    # Se arma antes de recortar "products" a los 10 de "Lo más vendido".
    todos_page = None
    if not has_filter:
        todos_paginator = Paginator(products.order_by('name'), 12)
        todos_page = todos_paginator.get_page(request.GET.get('pt'))

    # En portada, "Lo más vendido" muestra máximo 10 productos.
    if not has_filter:
        products = products[:10]

    # Novedades: últimos 4 productos con stock, solo en la vista principal
    novedades = []
    recommended = []
    if not has_filter:
        novedades = list(
            Product.objects.filter(is_active=True, stock__gt=0)
            .select_related('brand', 'group')
            .order_by('-id')[:4]
        )
        # "Recomendados para ti": muestra aleatoria de productos activos
        recommended = list(
            Product.objects.filter(is_active=True)
            .select_related('brand', 'group')
            .prefetch_related('images')
            .order_by('?')[:8]
        )

    # Carrito (para el panel lateral derecho del shell)
    cart_items, cart_subtotal = _cart_items(request)

    # Tiendas (marcas) con productos, para el nav lateral izquierdo
    sidebar_brands = list(Brand.objects.filter(is_active=True, products__is_active=True)
                          .distinct().order_by('name')[:8])
    # Color fijo por marca (mismo color en el original y en el duplicado del marquee)
    _brand_palette = ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#0ea5e9', '#8b5cf6']
    for _i, _b in enumerate(sidebar_brands):
        _b.logo_color = _brand_palette[_i % len(_brand_palette)]

    # Rotación destacada del hero: 1 producto por marca, en bucle (solo portada)
    featured_rotation = []
    if not has_filter:
        seen_brands = set()
        for p in (Product.objects.filter(is_active=True, stock__gt=0)
                  .select_related('brand', 'group')
                  .order_by('brand__name', '-id')):
            if p.brand_id in seen_brands:
                continue
            seen_brands.add(p.brand_id)
            featured_rotation.append(p)

    return render(request, 'storefront/catalog.html', {
        'products': products,
        'groups': ProductGroup.objects.filter(is_active=True),
        'query': query,
        'selected_group': group_id,
        'selected_brand': selected_brand,
        'has_filter': has_filter,
        'price_min': price_min,
        'price_max': price_max,
        'cart_count': cart_count,
        'cart_items': cart_items,
        'cart_subtotal': cart_subtotal,
        'novedades': novedades,
        'recommended': recommended,
        'sidebar_brands': sidebar_brands,
        'featured_rotation': featured_rotation,
        'todos_page': todos_page,
    })


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.prefetch_related('images'), pk=pk, is_active=True
    )
    cart_count = sum(_get_cart(request).values())
    return render(request, 'storefront/product_detail.html', {
        'product': product, 'cart_count': cart_count,
    })


# ---------------------------------------------------------------------
# Carrito (sin login requerido)
# ---------------------------------------------------------------------

def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
        quantity = max(1, quantity)
        cart = _get_cart(request)
        current = cart.get(str(product.pk), 0)
        new_quantity = current + quantity
        warning = None
        if new_quantity > product.stock:
            warning = f'Solo hay {product.stock} unidades de "{product.name}".'
            new_quantity = product.stock
        if new_quantity > 0:
            cart[str(product.pk)] = new_quantity
        request.session.modified = True

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            fresh_items, subtotal = _cart_items(request)
            return JsonResponse({
                'status': 'ok',
                'cart_count': sum(cart.values()),
                'cart_subtotal': str(subtotal),
                'cart_items': [
                    {
                        'pk': it['product'].pk,
                        'name': it['product'].name,
                        'store': it['product'].brand.name,
                        'subtotal': str(it['subtotal']),
                        'quantity': it['quantity'],
                        'image': it['product'].image.url if it['product'].image else None,
                        'remove_url': reverse('storefront:cart_remove', args=[it['product'].pk]),
                    }
                    for it in fresh_items
                ],
                'warning': warning,
            })

        if warning:
            messages.warning(request, warning)
        else:
            messages.success(request, f'"{product.name}" agregado al carrito.')

        # El botón "Pagar con PayPal" del detalle de producto manda directo
        # a checkout en vez de dejar al cliente en la página del carrito.
        if request.POST.get('next') == 'checkout':
            return redirect('storefront:checkout')
    return redirect('storefront:cart_view')


def cart_remove(request, pk):
    cart = _get_cart(request)
    cart.pop(str(pk), None)
    request.session.modified = True
    return redirect('storefront:cart_view')


def cart_update(request, pk):
    """Fija la cantidad exacta de un producto en el carrito."""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            quantity = 1
        cart = _get_cart(request)
        if quantity <= 0:
            cart.pop(str(product.pk), None)
        else:
            if quantity > product.stock:
                messages.warning(request, f'Solo hay {product.stock} unidades de "{product.name}".')
                quantity = product.stock
            cart[str(product.pk)] = quantity
        request.session.modified = True
    return redirect('storefront:cart_view')


def cart_view(request):
    items, total = _cart_items(request)
    return render(request, 'storefront/cart.html', {'items': items, 'total': total})


# ---------------------------------------------------------------------
# Checkout (requiere login de cliente)
# ---------------------------------------------------------------------

def checkout(request):
    # Si no está autenticado como cliente, guardamos la intención y lo
    # mandamos a login.
    if not _is_customer(request.user):
        request.session['next_after_login'] = reverse('storefront:checkout')
        messages.info(request, 'Inicia sesión o regístrate para continuar con tu compra.')
        return redirect('storefront:customer_login')

    items, total = _cart_items(request)
    if not items:
        messages.info(request, 'Tu carrito está vacío.')
        return redirect('storefront:catalog_list')

    customer = request.user.customer_profile

    if request.method == 'POST':
        form = CustomerRequestForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            purchase_request = PurchaseRequest.objects.create(
                customer=customer,
                notes=request.POST.get('notes', '').strip(),
            )
            for item in items:
                PurchaseRequestDetail.objects.create(
                    request=purchase_request,
                    product=item['product'],
                    quantity=item['quantity'],
                    unit_price=item['product'].unit_price,
                )
            request.session[CART_SESSION_KEY] = {}
            request.session.modified = True

            # Notificación al proveedor
            _notify_provider_new_order(request, purchase_request)

            return redirect('storefront:payment_choice', pk=purchase_request.pk)
    else:
        form = CustomerRequestForm(instance=customer)

    return render(request, 'storefront/checkout.html', {
        'form': form, 'items': items, 'total': total,
    })


def request_success(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
    return render(request, 'storefront/request_success.html', {
        'purchase_request': purchase_request,
        'whatsapp_links': _whatsapp_links(request, purchase_request),
    })


def _whatsapp_links(request, purchase_request):
    """Arma un enlace wa.me por cada tienda (marca) presente en el pedido.

    El mensaje va preformateado: cliente, productos de esa tienda con precio,
    total de la tienda y un enlace directo al pedido en el panel para gestión.
    El destino es el WhatsApp configurado en la marca; si la marca no tiene,
    cae al WhatsApp global de la configuración del negocio.
    """
    from urllib.parse import quote
    from billing.models import ConfigNegocio

    config = ConfigNegocio.objects.first()
    fallback = (config.whatsapp if config else '') or ''

    def normalize_ec(raw):
        """Normaliza a formato internacional para wa.me (solo dígitos, con
        código de país). Ecuador: 09XXXXXXXX -> 5939XXXXXXXX."""
        digits = ''.join(ch for ch in (raw or '') if ch.isdigit())
        if not digits:
            return ''
        if digits.startswith('593'):
            return digits
        if digits.startswith('0'):            # 0991509228 -> 593991509228
            return '593' + digits[1:]
        if len(digits) == 9:                  # 991509228  -> 593991509228
            return '593' + digits
        return digits

    panel_url = request.build_absolute_uri(
        reverse('storefront:purchase_request_detail', args=[purchase_request.pk])
    )
    customer = purchase_request.customer

    # Agrupar líneas por marca/tienda
    by_brand = {}
    for d in purchase_request.details.select_related('product__brand'):
        brand = d.product.brand
        by_brand.setdefault(brand, []).append(d)

    links = []
    for brand, details in by_brand.items():
        number = normalize_ec(brand.whatsapp or fallback)
        if not number:
            continue

        lines = [
            f'*Nuevo pedido #{purchase_request.id}*',
            f'Tienda: {brand.name}',
            '',
            f'*Cliente:* {customer.full_name}',
        ]
        if getattr(customer, 'phone', ''):
            lines.append(f'*Teléfono:* {customer.phone}')
        lines.append('')
        lines.append('*Productos:*')
        subtotal = 0
        for d in details:
            lines.append(f'• {d.product.name} x{d.quantity} — ${d.subtotal}')
            subtotal += d.subtotal
        lines.append('')
        lines.append(f'*Total de esta tienda:* ${round(subtotal, 2)}')
        lines.append('')
        lines.append(f'Gestionar pedido: {panel_url}')

        message = '\n'.join(lines)
        links.append({
            'brand': brand.name,
            'url': f'https://wa.me/{number}?text={quote(message)}',
        })

    return links


def _notify_provider_new_order(request, purchase_request):
    """Envía un email al proveedor cuando llega una solicitud nueva.
    Si ADMIN_NOTIFICATION_EMAIL no está configurado, no hace nada."""
    from django.conf import settings
    recipient = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', '')
    if not recipient:
        return
    panel_url = request.build_absolute_uri(
        reverse('storefront:purchase_request_detail', args=[purchase_request.pk])
    )
    items_text = '\n'.join(
        f'  - {d.product.name} x{d.quantity} = ${d.subtotal}'
        for d in purchase_request.details.all()
    )
    try:
        send_mail(
            subject=f'[Tienda] Nueva solicitud #{purchase_request.id} de {purchase_request.customer.full_name}',
            message=(
                f'Llegó una nueva solicitud de compra.\n\n'
                f'Cliente : {purchase_request.customer.full_name}\n'
                f'Email   : {purchase_request.customer.email or "—"}\n'
                f'Teléfono: {purchase_request.customer.phone or "—"}\n\n'
                f'Productos:\n{items_text}\n\n'
                f'Total estimado: ${purchase_request.total_estimado}\n\n'
                f'Ver en el panel: {panel_url}'
            ),
            from_email=None,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------
# Cliente: mis pedidos
# ---------------------------------------------------------------------

def my_orders(request):
    if not _is_customer(request.user):
        request.session['next_after_login'] = reverse('storefront:my_orders')
        return redirect('storefront:customer_login')
    customer = request.user.customer_profile
    status_filter = request.GET.get('status', 'todos')

    all_requests = PurchaseRequest.objects.filter(customer=customer).prefetch_related('details__product')

    # Contadores por estado para el sidebar
    counts = {s: all_requests.filter(status=s).count() for s, _ in PurchaseRequest.STATUS_CHOICES}

    if status_filter in dict(PurchaseRequest.STATUS_CHOICES):
        requests_qs = all_requests.filter(status=status_filter).order_by('-created_at')
    else:
        requests_qs = all_requests.order_by('-created_at')

    return render(request, 'storefront/my_orders.html', {
        'requests':      requests_qs,
        'status':        status_filter,
        'status_choices': PurchaseRequest.STATUS_CHOICES,
        'counts':        counts,
        'total_count':   all_requests.count(),
        'cart_count':    sum(_get_cart(request).values()),
    })


@require_POST
def cancel_purchase_request(request, pk):
    if not _is_customer(request.user):
        return redirect('storefront:customer_login')
    purchase_request = get_object_or_404(
        PurchaseRequest, pk=pk, customer=request.user.customer_profile
    )
    if not purchase_request.can_be_cancelled():
        messages.error(request, 'Este pedido ya no puede cancelarse porque ya fue revisado.')
        return redirect('storefront:my_orders')
    purchase_request.status = 'cancelada'
    purchase_request.reviewed_at = timezone.now()
    purchase_request.save()
    log_action(request, 'updated', 'PurchaseRequest', purchase_request.pk,
               f'Pedido #{pk} cancelado por el cliente')
    messages.success(request, f'Pedido #{pk} cancelado correctamente.')
    return redirect('storefront:my_orders')


def customer_invoice_pdf(request, pk):
    """Download a PDF of an invoice the logged-in customer owns."""
    from django.http import HttpResponse, Http404
    from billing.models import Invoice
    from billing.services import build_invoice_pdf

    if not _is_customer(request.user):
        return redirect('storefront:customer_login')

    invoice = get_object_or_404(
        Invoice.objects.select_related('customer').prefetch_related(
            'details__product__brand', 'payments__registered_by'
        ),
        pk=pk,
    )
    if not invoice.customer.user or invoice.customer.user != request.user:
        raise Http404

    buffer = build_invoice_pdf(invoice)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="factura_{invoice.id:05d}.pdf"'
    return response


def change_password(request):
    """Permite al cliente cambiar su contraseña desde el perfil."""
    if not _is_customer(request.user):
        request.session['next_after_login'] = reverse('storefront:change_password')
        return redirect('storefront:customer_login')

    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password1', '')
        new2 = request.POST.get('new_password2', '')
        errors = []

        if not request.user.check_password(current):
            errors.append('La contraseña actual no es correcta.')
        if len(new1) < 8:
            errors.append('La nueva contraseña debe tener al menos 8 caracteres.')
        if new1 != new2:
            errors.append('Las contraseñas nuevas no coinciden.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            request.user.set_password(new1)
            request.user.save()
            # Mantener la sesión activa después del cambio
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            messages.success(request, '¡Contraseña actualizada correctamente!')
            return redirect('storefront:change_password')

    return render(request, 'storefront/change_password.html', {
        'cart_count': sum(_get_cart(request).values()),
    })


def profile(request):
    """Perfil del cliente — ver y editar datos personales."""
    if not _is_customer(request.user):
        request.session['next_after_login'] = reverse('storefront:profile')
        return redirect('storefront:customer_login')

    customer = request.user.customer_profile

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        phone      = request.POST.get('phone', '').strip()
        address    = request.POST.get('address', '').strip()

        if not first_name or not last_name:
            messages.error(request, 'Nombre y apellido son obligatorios.')
        else:
            customer.first_name = first_name
            customer.last_name  = last_name
            customer.phone      = phone or None
            customer.address    = address or None
            customer.save()
            request.user.first_name = first_name
            request.user.last_name  = last_name
            request.user.save()
            messages.success(request, 'Datos actualizados correctamente.')
            return redirect('storefront:profile')

    return render(request, 'storefront/profile.html', {
        'customer':     customer,
        'cart_count':   sum(_get_cart(request).values()),
        'total_orders': PurchaseRequest.objects.filter(customer=customer).count(),
        'confirmed':    PurchaseRequest.objects.filter(customer=customer, status='confirmada').count(),
    })


# ---------------------------------------------------------------------
# Pago con tarjeta (PayPhone)
# ---------------------------------------------------------------------

def payment_choice(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    return render(request, 'storefront/payment_choice.html', {'purchase_request': purchase_request})


def pay_manual(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method == 'POST':
        purchase_request.payment_method = 'manual'
        purchase_request.save()
    return redirect('storefront:request_success', pk=purchase_request.pk)


def pay_with_credit(request, pk):
    """Confirma el pedido a crédito directo: genera la Factura real y su
    cronograma de cuotas de una sola vez."""
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method != 'POST':
        return redirect('storefront:payment_choice', pk=purchase_request.pk)

    try:
        numero_cuotas = int(request.POST.get('numero_cuotas', 0))
    except ValueError:
        numero_cuotas = 0

    try:
        confirm_purchase_request_credito(purchase_request, numero_cuotas)
    except (InsufficientStockError, ValueError) as e:
        messages.error(request, str(e))
        return redirect('storefront:payment_choice', pk=purchase_request.pk)

    return redirect('storefront:payment_success', pk=purchase_request.pk)


def pay_with_card(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method != 'POST':
        return redirect('storefront:payment_choice', pk=purchase_request.pk)

    client_tx_id = purchase_request.payphone_client_transaction_id or uuid.uuid4().hex[:12]
    purchase_request.payphone_client_transaction_id = client_tx_id
    purchase_request.payment_method = 'tarjeta'
    purchase_request.save()

    amount_cents = int(round(purchase_request.total_estimado * 100))
    response_url = request.build_absolute_uri(reverse('storefront:payphone_response'))
    cancellation_url = request.build_absolute_uri(reverse('storefront:payment_choice', args=[purchase_request.pk]))

    try:
        result = payphone.prepare_payment(
            amount_cents=amount_cents,
            client_transaction_id=client_tx_id,
            reference=f'Solicitud #{purchase_request.id}',
            response_url=response_url,
            cancellation_url=cancellation_url,
        )
    except payphone.PayphoneError as e:
        messages.error(request, f'No se pudo iniciar el pago: {e}')
        return redirect('storefront:payment_choice', pk=purchase_request.pk)

    return redirect(result['payWithCard'])


def payphone_response(request):
    transaction_id = request.GET.get('id')
    client_tx_id = request.GET.get('clientTransactionId')
    purchase_request = get_object_or_404(PurchaseRequest, payphone_client_transaction_id=client_tx_id)

    if purchase_request.status == 'confirmada':
        return render(request, 'storefront/payment_success.html', {'purchase_request': purchase_request})

    try:
        result = payphone.confirm_payment(transaction_id=transaction_id, client_transaction_id=client_tx_id)
    except payphone.PayphoneError as e:
        messages.error(request, f'No se pudo verificar el pago: {e}')
        return render(request, 'storefront/payment_error.html', {'purchase_request': purchase_request})

    if result.get('statusCode') == payphone.STATUS_APPROVED:
        purchase_request.payphone_transaction_id = result.get('transactionId')
        try:
            confirm_purchase_request(purchase_request)
        except InsufficientStockError as e:
            purchase_request.notes = (purchase_request.notes or '') + f'\n[ATENCIÓN] {e}'
            purchase_request.save()
            return render(request, 'storefront/payment_error.html', {'purchase_request': purchase_request, 'stock_issue': True})
        return render(request, 'storefront/payment_success.html', {'purchase_request': purchase_request})
    else:
        purchase_request.status = 'rechazada'
        purchase_request.notes = (purchase_request.notes or '') + f'\nPago no aprobado: {result.get("transactionStatus")}'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.save()
        return render(request, 'storefront/payment_error.html', {'purchase_request': purchase_request})


# ---------------------------------------------------------------------
# Panel interno (requiere login de staff)
# ---------------------------------------------------------------------

@permission_required_any('storefront.view_purchaserequest')
def purchase_request_list(request):
    from django.db.models import Count, Sum, F, Q as DQ
    from storefront.models import PurchaseRequestDetail

    status = request.GET.get('status', 'pendiente')
    q = request.GET.get('q', '').strip()

    # Summary counts per status
    status_counts = {s: 0 for s, _ in PurchaseRequest.STATUS_CHOICES}
    for row in PurchaseRequest.objects.values('status').annotate(n=Count('id')):
        status_counts[row['status']] = row['n']

    # Estimated revenue from pending requests (sum of detail lines)
    ingresos_pendiente = (
        PurchaseRequestDetail.objects
        .filter(request__status='pendiente')
        .aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
    )

    # Main queryset
    requests_qs = PurchaseRequest.objects.select_related('customer').prefetch_related('details')
    if status in dict(PurchaseRequest.STATUS_CHOICES):
        requests_qs = requests_qs.filter(status=status)
    if q:
        requests_qs = requests_qs.filter(
            DQ(customer__first_name__icontains=q) | DQ(customer__last_name__icontains=q)
        )

    status_tabs = [
        {'value': s, 'label': l, 'count': status_counts.get(s, 0)}
        for s, l in PurchaseRequest.STATUS_CHOICES
    ]

    return render(request, 'storefront/purchase_request_list.html', {
        'requests': requests_qs,
        'status': status,
        'status_choices': PurchaseRequest.STATUS_CHOICES,
        'status_tabs': status_tabs,
        'status_counts': status_counts,
        'ingresos_pendiente': ingresos_pendiente,
        'q': q,
    })


@permission_required_any('storefront.view_purchaserequest')
def purchase_request_detail(request, pk):
    purchase_request = get_object_or_404(
        PurchaseRequest.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    return render(request, 'storefront/purchase_request_detail.html', {'purchase_request': purchase_request})


@permission_required_any('storefront.change_purchaserequest')
def purchase_request_confirm(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method == 'POST':
        try:
            invoice = confirm_purchase_request(purchase_request)
        except InsufficientStockError as e:
            messages.error(request, str(e))
        else:
            log_action(request, 'confirmed', 'PurchaseRequest', purchase_request.pk,
                       f'Solicitud #{purchase_request.id} confirmada → Factura #{invoice.id}')
            messages.success(request, f'Solicitud #{purchase_request.id} confirmada. Factura #{invoice.id} creada.')
    return redirect('storefront:purchase_request_detail', pk=purchase_request.pk)


@permission_required_any('storefront.change_purchaserequest')
def purchase_request_reject(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method == 'POST':
        purchase_request.status = 'rechazada'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.save()
        log_action(request, 'rejected', 'PurchaseRequest', purchase_request.pk,
                   f'Solicitud #{purchase_request.id} rechazada')
        messages.success(request, f'Solicitud #{purchase_request.id} rechazada.')
    return redirect('storefront:purchase_request_detail', pk=purchase_request.pk)

# PayPal
# ---------------------------------------------------------------------

def _paypal_request(url, data, headers, timeout=None, attempts=None):
    """Hace un POST a PayPal y devuelve el JSON. Reintenta ante fallos
    transitorios (timeout, 5xx, red caída), causa típica del error
    intermitente. Timeout y nº de intentos configurables por env
    (PAYPAL_TIMEOUT, PAYPAL_MAX_ATTEMPTS). Lanza Exception si falla todo."""
    import json, time, urllib.request, urllib.error, socket
    if timeout is None:
        timeout = getattr(settings, 'PAYPAL_TIMEOUT', 20)
    if attempts is None:
        attempts = max(1, getattr(settings, 'PAYPAL_MAX_ATTEMPTS', 3))
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            # 4xx (ej. pago rechazado) no se reintenta; 5xx sí.
            if e.code < 500:
                raise Exception(f'PayPal {e.code}: {body}')
            last_error = Exception(f'PayPal {e.code}: {body}')
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            last_error = e
        if attempt < attempts - 1:
            # Backoff exponencial: 0.5s, 1s, 2s...
            time.sleep(0.5 * (2 ** attempt))
    raise last_error


def _paypal_access_token():
    """Obtiene un access token de la API de PayPal sandbox."""
    import base64
    credentials = base64.b64encode(
        f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_SECRET}'.encode()
    ).decode()
    data = _paypal_request(
        f'{settings.PAYPAL_API_BASE}/v1/oauth2/token',
        data=b'grant_type=client_credentials',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    return data['access_token']


def pay_with_paypal(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    return render(request, 'storefront/payment_paypal.html', {
        'purchase_request': purchase_request,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
        'paypal_sdk_base': settings.PAYPAL_SDK_BASE,
    })


@require_POST
def paypal_create_order(request, pk):
    """Crea una orden en PayPal server-side y devuelve el order ID."""
    import json
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    total = '{:.2f}'.format(purchase_request.total_estimado)
    try:
        token = _paypal_access_token()
        order = _paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders',
            data=json.dumps({
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {'currency_code': 'USD', 'value': total},
                    'description': f'Pedido #{purchase_request.pk}',
                }],
            }).encode(),
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
        return JsonResponse({'id': order['id']})
    except Exception as e:
        logger.exception('PayPal error: %s', e)
        return JsonResponse({'error': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)


def paypal_capture(request, pk):
    """Captura el pago después de que PayPal lo aprueba."""
    import json
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')

    if request.method != 'POST':
        return redirect('storefront:payment_choice', pk=pk)

    try:
        order_id = json.loads(request.body).get('orderID')
        if not order_id:
            return JsonResponse({'error': 'Falta el identificador de la orden.'}, status=400)
        token = _paypal_access_token()
        capture_data = _paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture',
            data=b'{}',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Solicitud inválida.'}, status=400)
    except Exception as e:
        logger.exception('PayPal error: %s', e)
        return JsonResponse({'error': 'No se pudo procesar el pago. Intenta de nuevo.'}, status=502)

    if capture_data.get('status') == 'COMPLETED':
        purchase_request.payment_method = 'tarjeta'
        purchase_request.paypal_order_id = order_id
        try:
            confirm_purchase_request(purchase_request)
        except InsufficientStockError as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'status': 'ok', 'redirect': request.build_absolute_uri(
            reverse('storefront:payment_success', args=[purchase_request.pk])
        )})
    return JsonResponse({'error': 'Pago no completado', 'status': capture_data.get('status')}, status=400)


def payment_success(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
    return render(request, 'storefront/payment_success.html', {'purchase_request': purchase_request})

