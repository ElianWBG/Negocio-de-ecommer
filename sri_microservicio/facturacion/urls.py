from django.urls import path

from .views import EmitirFacturaView, FacturaEstadoView

app_name = "facturacion"

urlpatterns = [
    path("facturas/", EmitirFacturaView.as_view(), name="emitir"),
    path("facturas/<int:pk>/", FacturaEstadoView.as_view(), name="estado"),
]
