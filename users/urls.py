from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # Auth
    path('auth/google/', views.google_auth, name='google_auth'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # User profile
    path('me/', views.me, name='me'),
    path('me/city/', views.update_user_city, name='update_user_city'),

    # User management (requires manage_users permission)
    path('users/', views.list_users, name='list_users'),

    # Role assignment (backoffice)
    path('backoffice/<int:user_id>/assign-role/', views.assign_role, name='assign_role'),

    # Public reference data
    path('countries/', views.list_countries, name='list_countries'),
    path('cities/', views.list_cities, name='list_cities'),
]
