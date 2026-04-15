from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from .views import health_check, debug_network, debug_db

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/v1/users/', include('users.urls')),
    path('api/v1/tasks/', include('tasks.urls')),
]

# Debug endpoints: only available when DEBUG=True (never in production)
if settings.DEBUG:
    urlpatterns += [
        path('debug-network/', debug_network, name='debug_network'),
        path('debug-db/', debug_db, name='debug_db'),
    ]
