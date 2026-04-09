from django.urls import path
from .views import (
    google_auth, me, update_user_city, list_users, assign_role, update_user,
    list_countries, list_cities, list_roles, check_user_status, set_location,
)

urlpatterns = [
    # Auth
    path('auth/google/', google_auth, name='google-auth'),
    path('me/', me, name='me'),
    path('me/city/', update_user_city, name='update-my-city'),
    path('check-status/', check_user_status, name='check-status'),

    # Backoffice
    path('backoffice/list/', list_users, name='list-users'),
    path('backoffice/<int:user_id>/assign-role/', assign_role, name='assign-role'),
    path('backoffice/<int:user_id>/update/', update_user, name='update-user'),

    # Public
    path('countries/', list_countries, name='list-countries'),
    path('cities/', list_cities, name='list-cities'),
    path('roles/', list_roles, name='list-roles'),
    path('me/location/', set_location, name='set-location'),
]
