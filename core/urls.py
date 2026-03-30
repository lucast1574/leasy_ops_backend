from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.views import HealthCheckView

api_v1_urlpatterns = [
    path('users/', include('apps.users.urls')),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API V1
    path('api/v1/', include(api_v1_urlpatterns)),
]
