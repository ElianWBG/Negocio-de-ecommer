from django.db import models
from shared.validators import validate_cedula_ec

class Brand(models.Model):
    """Marcas de productos."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre de marca')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
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
    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        ordering = ['-invoice_date']
    def __str__(self): return f'Factura #{self.id} - {self.customer}'

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

class ConfigNegocio(models.Model):
    """Configuración global del negocio — singleton (solo una fila).
    El proveedor la edita desde el panel y el storefront la lee
    automáticamente a través del context processor."""

    # Identidad
    nombre_tienda   = models.CharField(max_length=80, default='Nuestra Tienda', verbose_name='Nombre de la tienda')
    slogan          = models.CharField(max_length=160, blank=True, default='Explora nuestro catálogo y solicita tu pedido en minutos', verbose_name='Slogan')
    logo            = models.ImageField(upload_to='config/', blank=True, null=True, verbose_name='Logo')
    color_primario  = models.CharField(max_length=7, default='#B5441B', verbose_name='Color principal (hex)', help_text='Ej: #B5441B')
    color_oscuro    = models.CharField(max_length=7, default='#231A10', verbose_name='Color oscuro (hex)', help_text='Ej: #231A10')

    # Banner promocional
    banner_activo   = models.BooleanField(default=True, verbose_name='Mostrar banner promocional')
    banner_titulo   = models.CharField(max_length=120, default='Envío gratis en pedidos mayores a $50', verbose_name='Título del banner')
    banner_subtitulo = models.CharField(max_length=200, blank=True, default='Válido para entregas dentro de la ciudad · Coordina con el negocio', verbose_name='Subtítulo del banner')
    banner_cta      = models.CharField(max_length=40, default='Ver productos', verbose_name='Texto del botón del banner')

    # Contacto
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
        # Singleton: siempre usa el id=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        """Devuelve la config actual, creándola con valores por defecto si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
