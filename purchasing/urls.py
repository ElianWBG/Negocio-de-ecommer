from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    path('', views.purchase_list, name='purchase_list'),
    path('create/', views.purchase_create, name='purchase_create'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    path('<int:pk>/edit/', views.purchase_update, name='purchase_update'),
    path('<int:pk>/delete/', views.purchase_delete, name='purchase_delete'),
    path('api/update-visible-columns/', views.purchase_update_visible_columns, name='purchase_update_visible_columns'),
]
