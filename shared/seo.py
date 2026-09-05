from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse

from billing.models import Product


def robots_txt(request):
    """robots.txt básico: permite indexar el catálogo público, bloquea el
    panel administrativo y apunta al sitemap."""
    site_url = settings.SITE_URL.rstrip('/')
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /panel/',
        'Disallow: /admin/',
        'Disallow: /carrito/',
        'Disallow: /solicitar/',
        'Disallow: /mis-pedidos/',
        'Disallow: /perfil/',
        f'Sitemap: {site_url}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')


def sitemap_xml(request):
    """Sitemap simple del catálogo público: home y ficha de cada producto
    activo. Sin django.contrib.sites (no lo usa el proyecto) — la URL base
    sale de SITE_URL, ya configurada para email/PayPal."""
    site_url = settings.SITE_URL.rstrip('/')
    urls = [site_url + reverse('storefront:catalog_list')]
    product_ids = Product.objects.filter(is_active=True).values_list('pk', flat=True)
    for pk in product_ids:
        urls.append(site_url + reverse('storefront:product_detail', args=[pk]))

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        xml_parts.append(f'<url><loc>{url}</loc></url>')
    xml_parts.append('</urlset>')
    return HttpResponse('\n'.join(xml_parts), content_type='application/xml; charset=utf-8')
