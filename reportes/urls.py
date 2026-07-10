from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.reportes_index, name='index'),
    path('cuentas-por-cobrar/', views.cuentas_por_cobrar, name='cuentas_por_cobrar'),
    path('cuentas-por-pagar/', views.cuentas_por_pagar, name='cuentas_por_pagar'),
    path('ventas-por-periodo/', views.ventas_por_periodo, name='ventas_por_periodo'),
    path('productos-mas-vendidos/', views.productos_mas_vendidos, name='productos_mas_vendidos'),
    path('stock-bajo/', views.stock_bajo, name='stock_bajo'),
]
