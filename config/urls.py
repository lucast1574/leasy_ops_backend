from django.contrib import admin
from django.urls import path, include

from .views import health_check, debug_network

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('debug-network/', debug_network, name='debug_network'),
    path('admin/', admin.site.urls),
    path('api/v1/users/', include('users.urls')),
]
