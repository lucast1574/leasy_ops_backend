from django.contrib import admin
from django.urls import path, include

from .views import health_check, debug_network, debug_db

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('debug-network/', debug_network, name='debug_network'),
    path('debug-db/', debug_db, name='debug_db'),
    path('admin/', admin.site.urls),
    path('api/v1/users/', include('users.urls')),
    path('api/v1/tasks/', include('tasks.urls')),
]
