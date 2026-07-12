from django.db import models
from django.conf import settings
from decimal import Decimal
from shared.validators import validate_cedula_ec

class Brand(models.Model):
    """Marcas de productos. En la plataforma multi-tienda, la marca actúa
    como la "tienda asociada" (vendedor)."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre de marca')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    logo = models.ImageField(upload_to='brands/', blank=True, null=True, max_length=500, verbose_name='Logo')
    whatsapp = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='WhatsApp de la tienda',
        help_text='Con código de país, ej: 593999999999. Recibe los pedidos de esta tienda.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']
    def __str__(self): return self.name

class ProductGroup(models.Model):
    """Grupos/categorías de productos."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre de grupo')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'Grupo de producto'
        verbose_name_plural = 'Grupos de productos'
        ordering = ['name']
    def __str__(self): return self.name

class Supplier(models.Model):
    """Proveedores. M2M con Product."""
    name = models.CharField(max_length=200, verbose_name='Nombre de empresa')
    contact_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='Nombre de contacto')
    email = models.EmailField(blank=True, null=True, verbose_name='Correo electrónico')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Teléfono')
    address = models.TextField(blank=True, null=True, verbose_name='Dirección')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']
    def __str__(self): return self.name

class Product(models.Model):
    """Productos. FK a Brand/Group, M2M a Supplier."""
    name = models.CharField(max_length=200, verbose_name='Nombre de producto')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products', verbose_name='Marca')
    group = models.ForeignKey(ProductGroup, on_delete=models.PROTECT, related_name='products', verbose_name='Grupo')
    suppliers = models.ManyToManyField(Supplier, related_name='products', blank=True, verbose_name='Proveedores')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio unitario')
    stock = models.IntegerField(default=0, verbose_name='Stock')
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Imagen del producto')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']
    def __str__(self): return f'{self.name} ({self.brand.name})'
    
    @property
    def balance(self):
        """Balance calculado: Precio unitario × Stock"""
        price = self.unit_price or 0
        stock = self.stock or 0
        return round(price * stock, 2)

    @property
    def gallery(self):
        """Imágenes para el carrusel: portada (image) primero, luego las extra
        del modelo ProductImage en orden. Devuelve lista de URLs."""
        urls = []
        if self.image:
            urls.append(self.image.url)
        for extra in self.images.all():
            if extra.image:
                urls.append(extra.image.url)
        return urls


class ProductImage(models.Model):
    """Imágenes adicionales de un producto (galería / carrusel)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images', verbose_name='Producto'
    )
    image = models.ImageField(upload_to='products/', verbose_name='Imagen', max_length=500)
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Imagen de producto'
        verbose_name_plural = 'Imágenes de producto'
        ordering = ['order', 'id']

    def __str__(self):
        return f'Imagen de {self.product.name} (#{self.order})'


class Customer(models.Model):
    """Clientes. OneToOne con CustomerProfile."""
    dni = models.CharField(
        max_length=13,
        unique=True,
        verbose_name='DNI/RUC',
        validators=[validate_cedula_ec]
    )
    first_name = models.CharField(max_length=100, verbose_name='Nombre')
    last_name = models.CharField(max_length=100, verbose_name='Apellido')
    email = models.EmailField(blank=True, null=True, verbose_name='Correo electrónico')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Teléfono')
    address = models.TextField(blank=True, null=True, verbose_name='Dirección')
    accepts_promotions = models.BooleanField(
        default=True,
        verbose_name='Acepta recibir promociones',
        help_text='Si está marcado, el cliente recibirá correos de promociones y ofertas.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Cuenta de usuario para el catálogo público (opcional: clientes creados
    # desde el panel interno no necesitan cuenta web).
    user = models.OneToOneField(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='customer_profile',
        verbose_name='Cuenta web'
    )
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['last_name', 'first_name']
    def __str__(self): return f'{self.last_name}, {self.first_name}'
    @property
    def full_name(self): return f'{self.first_name} {self.last_name}'

class CustomerProfile(models.Model):
    """Perfil extendido. OneToOne con Customer."""
    TAXPAYER = [('final','Consumidor final'),('ruc','RUC'),('rise','RISE')]
    PAYMENT = [('cash','Contado'),('credit_15','15 días'),('credit_30','30 días'),('credit_60','60 días')]
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='profile', verbose_name='Cliente')
    taxpayer_type = models.CharField(max_length=10, choices=TAXPAYER, default='final', verbose_name='Tipo de contribuyente')
    payment_terms = models.CharField(max_length=15, choices=PAYMENT, default='cash', verbose_name='Condiciones de pago')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Límite de crédito')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    class Meta:
        verbose_name = 'Perfil de cliente'
        verbose_name_plural = 'Perfiles de clientes'
    def __str__(self): return f'Perfil: {self.customer}'

class Invoice(models.Model):
    """Cabecera de factura."""
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices', verbose_name='Cliente')
    invoice_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de factura')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Impuesto')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    estado = models.CharField(
        max_length=10,
        choices=[('pendiente', 'Pendiente'), ('parcial', 'Parcial'), ('pagada', 'Pagada'), ('anulada', 'Anulada')],
        default='pendiente',
        verbose_name='Estado de pago',
    )
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo pendiente')
    tipo_pago = models.CharField(
        max_length=10,
        choices=[('contado', 'Contado'), ('credito', 'Crédito')],
        default='contado',
        verbose_name='Tipo de pago',
    )
    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        ordering = ['-invoice_date']
    def __str__(self): return f'Factura #{self.id} - {self.customer}'
    def save(self, *args, **kwargs):
        if self.tipo_pago == 'contado' and self.estado != 'anulada':
            self.saldo = Decimal('0')
            self.estado = 'pagada'
        super().save(*args, **kwargs)

class InvoiceDetail(models.Model):
    """Líneas de factura."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='details', verbose_name='Factura')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='invoice_details', verbose_name='Producto')
    quantity = models.IntegerField(default=1, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    class Meta:
        verbose_name = 'Detalle de factura'
        verbose_name_plural = 'Detalles de factura'
    def __str__(self): return f'{self.product.name} x {self.quantity}'
    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class InvoicePayment(models.Model):
    """Registro de un pago (total o parcial) aplicado a una factura de crédito."""
    METHOD_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('otro', 'Otro'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments', verbose_name='Factura')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto pagado')
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de pago')
    method = models.CharField(max_length=15, choices=METHOD_CHOICES, verbose_name='Método de pago')
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name='Registrado por'
    )
    notes = models.TextField(blank=True, verbose_name='Notas')

    class Meta:
        verbose_name = 'Pago de factura'
        verbose_name_plural = 'Pagos de facturas'
        ordering = ['-payment_date']

    def __str__(self):
        return f'Pago ${self.amount} — Factura #{self.invoice_id}'


class ConfigNegocio(models.Model):
    """Configuración global del negocio — singleton (solo una fila).
    El proveedor la edita desde el panel y el storefront la lee
    automáticamente a través del context processor."""

    # Identidad
    nombre_tienda   = models.CharField(max_length=80, default='Nuestra Tienda', verbose_name='Nombre de la tienda')
    slogan          = models.CharField(max_length=160, blank=True, default='Explora nuestro catálogo y solicita tu pedido en minutos', verbose_name='Slogan')
    logo = models.ImageField(upload_to='config/', blank=True, null=True, verbose_name='Logo', max_length=500)
    color_primario  = models.CharField(max_length=7, default='#2563EB', verbose_name='Color principal (hex)', help_text='Ej: #2563EB')
    color_oscuro    = models.CharField(max_length=7, default='#0F1B33', verbose_name='Color oscuro (hex)', help_text='Ej: #0F1B33')
    color_fondo     = models.CharField(max_length=7, default='#F3F6FC', verbose_name='Color de fondo (hex)', help_text='Fondo general de la tienda')
    color_navbar    = models.CharField(max_length=7, default='#0F1B33', verbose_name='Color del navbar (hex)', help_text='Barra de navegación superior')
    color_texto     = models.CharField(max_length=7, default='#0F1B33', verbose_name='Color del texto (hex)', help_text='Color principal del texto en la tienda')

    # Hero
    hero_imagen     = models.ImageField(upload_to='config/', blank=True, null=True, verbose_name='Imagen de fondo del hero', max_length=500)
    hero_titulo     = models.CharField(max_length=100, blank=True, default='Encuentra lo que buscas', verbose_name='Título del hero')

    # Sobre nosotros
    sobre_activo    = models.BooleanField(default=False, verbose_name='Mostrar sección "Sobre nosotros"')
    sobre_titulo    = models.CharField(max_length=100, blank=True, default='Sobre nosotros', verbose_name='Título')
    sobre_texto     = models.TextField(blank=True, verbose_name='Texto')
    sobre_imagen    = models.ImageField(upload_to='config/', blank=True, null=True, verbose_name='Imagen', max_length=500)

    # Por qué elegirnos
    porque_activo   = models.BooleanField(default=False, verbose_name='Mostrar sección "Por qué elegirnos"')
    porque_titulo   = models.CharField(max_length=100, blank=True, default='¿Por qué elegirnos?', verbose_name='Título')
    porque_1_icono  = models.CharField(max_length=50, blank=True, default='bi-truck', verbose_name='Ícono 1 (Bootstrap Icons)')
    porque_1_titulo = models.CharField(max_length=80, blank=True, default='Envío rápido', verbose_name='Título 1')
    porque_1_texto  = models.CharField(max_length=200, blank=True, default='Entrega a domicilio en toda la ciudad.', verbose_name='Texto 1')
    porque_2_icono  = models.CharField(max_length=50, blank=True, default='bi-shield-check', verbose_name='Ícono 2')
    porque_2_titulo = models.CharField(max_length=80, blank=True, default='Garantía', verbose_name='Título 2')
    porque_2_texto  = models.CharField(max_length=200, blank=True, default='Productos con garantía directa del fabricante.', verbose_name='Texto 2')
    porque_3_icono  = models.CharField(max_length=50, blank=True, default='bi-headset', verbose_name='Ícono 3')
    porque_3_titulo = models.CharField(max_length=80, blank=True, default='Soporte', verbose_name='Título 3')
    porque_3_texto  = models.CharField(max_length=200, blank=True, default='Atención personalizada antes y después de tu compra.', verbose_name='Texto 3')

    # Banner promocional
    banner_activo   = models.BooleanField(default=True, verbose_name='Mostrar banner promocional')
    banner_titulo   = models.CharField(max_length=120, default='Envío gratis en pedidos mayores a $50', verbose_name='Título del banner')
    banner_subtitulo = models.CharField(max_length=200, blank=True, default='Válido para entregas dentro de la ciudad · Coordina con el negocio', verbose_name='Subtítulo del banner')
    banner_cta      = models.CharField(max_length=40, default='Ver productos', verbose_name='Texto del botón del banner')

    # Contacto
    ruc              = models.CharField(max_length=13, blank=True, verbose_name='RUC del negocio')
    email_contacto   = models.EmailField(blank=True, verbose_name='Email de contacto')
    telefono         = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    whatsapp         = models.CharField(max_length=20, blank=True, verbose_name='Número WhatsApp (con código de país, ej: 593999999999)')
    direccion        = models.TextField(blank=True, verbose_name='Dirección')

    # Redes sociales
    facebook_url    = models.URLField(blank=True, verbose_name='Facebook')
    instagram_url   = models.URLField(blank=True, verbose_name='Instagram')
    tiktok_url      = models.URLField(blank=True, verbose_name='TikTok')

    class Meta:
        verbose_name = 'Configuración del negocio'
        verbose_name_plural = 'Configuración del negocio'

    def __str__(self):
        return f'Config: {self.nombre_tienda}'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('created',      'Creado'),
        ('updated',      'Actualizado'),
        ('deleted',      'Eliminado'),
        ('confirmed',    'Confirmado'),
        ('rejected',     'Rechazado'),
        ('login',        'Inicio de sesión'),
        ('config_saved', 'Configuración guardada'),
    ]
    user        = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    action      = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name  = models.CharField(max_length=100)
    object_id   = models.IntegerField(null=True, blank=True)
    description = models.TextField()
    timestamp   = models.DateTimeField(auto_now_add=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Registro de actividad'
        verbose_name_plural = 'Registros de actividad'

    def __str__(self):
        return f'[{self.action}] {self.model_name} #{self.object_id} by {self.user}'


class PanelVerificationCode(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='panel_verification_code')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Código de verificación del panel'
        verbose_name_plural = 'Códigos de verificación del panel'

    def __str__(self):
        return f'Código para {self.user.username}'

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=24)

