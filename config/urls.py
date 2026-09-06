from django.contrib import admin
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from shared.seo import robots_txt, sitemap_xml
from shared.auth_views import (
    RateLimitedLoginView,
    RateLimitedPasswordResetView,
    RateLimitedPasswordResetConfirmView,
)


def logout_view(request):
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('accounts/logout/', logout_view, name='logout'),
    # Debe ir ANTES del include de auth.urls: Django usa el primer patrón que
    # coincide, así nuestra vista con rate limiting reemplaza el login por
    # defecto (que no protege contra fuerza bruta) conservando name='login'.
    path('accounts/login/', RateLimitedLoginView.as_view(), name='login'),
    # Mismo motivo: reemplazan las vistas de reset por defecto (sin rate limit)
    # conservando los nombres 'password_reset' y 'password_reset_confirm'.
    path('accounts/password_reset/', RateLimitedPasswordResetView.as_view(), name='password_reset'),
    path('accounts/reset/<uidb64>/<token>/', RateLimitedPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('panel/purchases/', include('purchasing.urls')),
    path('panel/cobros/', include('cobros.urls')),
    path('panel/pagos/', include('pagos.urls')),
    path('panel/creditos-compras/', include('creditos_compras.urls')),
    path('panel/creditos-ventas/', include('creditos_ventas.urls')),
    path('panel/reportes/', include('reportes.urls')),
    path('panel/roles/', include('security.urls')),
    path('panel/', include('billing.urls')),
    path('', include('storefront.urls')),
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

