from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Roles (Group)
    path('', views.GroupListView.as_view(), name='group_list'),
    path('create/', views.GroupCreateView.as_view(), name='group_create'),
    path('<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_update'),
    path('<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # Permisos (Permission)
    path('permissions/', views.PermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/edit/', views.PermissionUpdateView.as_view(), name='permission_update'),
    path('permissions/<int:pk>/delete/', views.PermissionDeleteView.as_view(), name='permission_delete'),
]
