from django.urls import path
from .views import GoogleAuthView, me, list_users, toggle_approval

urlpatterns = [
    path('auth/google/', GoogleAuthView.as_view(), name='google-login'),
    path('me/', me, name='me'),
    path('backoffice/list/', list_users, name='list-users'),
    path('backoffice/<int:user_id>/toggle-approval/', toggle_approval, name='toggle-approval'),
]
