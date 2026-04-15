from django.urls import path
from .views import (
    google_auth, me, update_user_city, list_users, assign_role, update_user,
    list_countries, list_cities, list_districts, list_roles, check_user_status,
    set_location,
    tracking_locations, my_assignments, adoptable_operarios, adopt_operario,
    release_operario,
)

urlpatterns = [
    # Auth
    path('auth/google/', google_auth, name='google-auth'),
    path('me/', me, name='me'),
    path('me/city/', update_user_city, name='update-my-city'),
    path('me/location/', set_location, name='set-location'),
    path('check-status/', check_user_status, name='check-status'),

    # Backoffice user management
    path('backoffice/list/', list_users, name='list-users'),
    path('backoffice/<int:user_id>/assign-role/', assign_role, name='assign-role'),
    path('backoffice/<int:user_id>/update/', update_user, name='update-user'),

    # Tracking / Monitoring
    path('tracking/locations/', tracking_locations, name='tracking-locations'),
    path('tracking/assignments/', my_assignments, name='my-assignments'),
    path('tracking/adoptable/', adoptable_operarios, name='adoptable-operarios'),
    path('tracking/adopt/', adopt_operario, name='adopt-operario'),
    path('tracking/release/<int:operario_id>/', release_operario, name='release-operario'),

    # Public catalogs
    path('countries/', list_countries, name='list-countries'),
    path('cities/', list_cities, name='list-cities'),
    path('districts/', list_districts, name='list-districts'),
    path('roles/', list_roles, name='list-roles'),
]
