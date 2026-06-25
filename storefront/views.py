import secrets
import uuid
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q, Min, Max
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from billing.models import Product, ProductGroup, Customer, Brand
from . import payphone
from .forms import CustomerRegistrationForm, CustomerLoginForm, CustomerRequestForm
from .models import PurchaseRequest, PurchaseRequestDetail, EmailVerificationToken
from .services import confirm_purchase_request, InsufficientStockError
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
    products = Product.objects.filter(pk__in=cart.keys(), is_active=True)
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
                    'user': user,
                }
            )
            login(request, user)
            return redirect('storefront:catalog_list')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'storefront/register.html', {'form': form})

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

    login(request, user)
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
                login(request, user)
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
    sidebar_brands = (Brand.objects.filter(is_active=True, products__is_active=True)
                      .distinct().order_by('name')[:8])

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
        if new_quantity > product.stock:
            messages.warning(request, f'Solo hay {product.stock} unidades de "{product.name}".')
            new_quantity = product.stock
        if new_quantity > 0:
            cart[str(product.pk)] = new_quantity
        request.session.modified = True
        messages.success(request, f'"{product.name}" agregado al carrito.')
    return redirect('storefront:cart_view')


def cart_remove(request, pk):
    cart = _get_cart(request)
    cart.pop(str(pk), None)
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

@login_required
def purchase_request_list(request):
    status = request.GET.get('status', 'pendiente')
    requests_qs = PurchaseRequest.objects.select_related('customer').prefetch_related('details')
    if status in dict(PurchaseRequest.STATUS_CHOICES):
        requests_qs = requests_qs.filter(status=status)
    return render(request, 'storefront/purchase_request_list.html', {
        'requests': requests_qs, 'status': status, 'status_choices': PurchaseRequest.STATUS_CHOICES,
    })


@login_required
def purchase_request_detail(request, pk):
    purchase_request = get_object_or_404(
        PurchaseRequest.objects.select_related('customer').prefetch_related('details__product'), pk=pk
    )
    return render(request, 'storefront/purchase_request_detail.html', {'purchase_request': purchase_request})


@login_required
def purchase_request_confirm(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method == 'POST':
        try:
            invoice = confirm_purchase_request(purchase_request)
        except InsufficientStockError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f'Solicitud #{purchase_request.id} confirmada. Factura #{invoice.id} creada.')
    return redirect('storefront:purchase_request_detail', pk=purchase_request.pk)


@login_required
def purchase_request_reject(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    if request.method == 'POST':
        purchase_request.status = 'rechazada'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.save()
        messages.success(request, f'Solicitud #{purchase_request.id} rechazada.')
    return redirect('storefront:purchase_request_detail', pk=purchase_request.pk)

# PayPal
# ---------------------------------------------------------------------

def pay_with_paypal(request, pk):
    """Muestra la página con el botón de PayPal."""
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')
    paypal_client_id = settings.PAYPAL_CLIENT_ID
    paypal_total = '{:.2f}'.format(purchase_request.total_estimado)
    return render(request, 'storefront/payment_paypal.html', {
        'purchase_request': purchase_request,
        'paypal_client_id': paypal_client_id,
        'paypal_total': paypal_total,
    })


def paypal_capture(request, pk):
    """Captura el pago después de que PayPal lo aprueba."""
    import json, urllib.request, urllib.parse, base64
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk, status='pendiente')

    if request.method != 'POST':
        return redirect('storefront:payment_choice', pk=pk)

    data = json.loads(request.body)
    order_id = data.get('orderID')

    # Obtener access token
    client_id = settings.PAYPAL_CLIENT_ID
    secret = settings.PAYPAL_SECRET
    credentials = base64.b64encode(f'{client_id}:{secret}'.encode()).decode()

    token_req = urllib.request.Request(
        'https://api-m.sandbox.paypal.com/v1/oauth2/token',
        data=b'grant_type=client_credentials',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
    )
    try:
        with urllib.request.urlopen(token_req) as resp:
            token_data = json.loads(resp.read())
            access_token = token_data['access_token']
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    # Capturar el pago
    capture_req = urllib.request.Request(
        f'https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture',
        data=b'{}',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
    )
    try:
        with urllib.request.urlopen(capture_req) as resp:
            capture_data = json.loads(resp.read())
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    status = capture_data.get('status')
    if status == 'COMPLETED':
        purchase_request.payment_method = 'tarjeta'
        purchase_request.payphone_transaction_id = order_id
        try:
            confirm_purchase_request(purchase_request)
        except InsufficientStockError as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'status': 'ok', 'redirect': request.build_absolute_uri(
            reverse('storefront:payment_success', args=[purchase_request.pk])
        )})
    else:
        return JsonResponse({'error': 'Pago no completado', 'status': status}, status=400)


def payment_success(request, pk):
    purchase_request = get_object_or_404(PurchaseRequest, pk=pk)
    return render(request, 'storefront/payment_success.html', {'purchase_request': purchase_request})

