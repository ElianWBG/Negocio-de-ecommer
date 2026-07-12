from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('panel/purchases/', include('purchasing.urls')),
    path('panel/cobros/', include('cobros.urls')),
    path('panel/pagos/', include('pagos.urls')),
    path('panel/creditos-compras/', include('creditos_compras.urls')),
    path('panel/reportes/', include('reportes.urls')),
    path('panel/roles/', include('security.urls')),
    path('panel/', include('billing.urls')),
    path('', include('storefront.urls')),
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

