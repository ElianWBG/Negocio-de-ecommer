from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    # Autenticación
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.SecurityLoginView.as_view(), name='login'),
    path('logout/', views.SecurityLogoutView.as_view(), name='logout'),

    # Usuarios
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),

    # Roles (Group)
    path('roles/', views.GroupListView.as_view(), name='group_list'),
    path('roles/create/', views.GroupCreateView.as_view(), name='group_create'),
    path('roles/<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_update'),
    path('roles/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # Permisos (Permission)
    path('permissions/', views.PermissionListView.as_view(), name='permission_list'),
    path('permissions/create/', views.PermissionCreateView.as_view(), name='permission_create'),
    path('permissions/<int:pk>/edit/', views.PermissionUpdateView.as_view(), name='permission_update'),
    path('permissions/<int:pk>/delete/', views.PermissionDeleteView.as_view(), name='permission_delete'),
]
