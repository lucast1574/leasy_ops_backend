from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoginView, UserViewSet

router = DefaultRouter()
router.register(r'management', UserViewSet, basename='user-management')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('', include(router.urls)),
]
