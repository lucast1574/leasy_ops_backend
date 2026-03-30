from django.db import models
from django.contrib.auth.models import AbstractUser

class Role(models.Model):
    """
    Database driven roles. 
    Common roles: admin, supervisor, motorizado
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    """
    Custom User model for Leasy Ops.
    Supports backoffice-driven user management and role-based access.
    """
    role = models.ForeignKey(
        Role, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="users"
    )

    # Email remains unique, but login will use username (standard Django login)
    email = models.EmailField(unique=True)
    
    # Store plain password for 'non-tech' audience visibility (as requested)
    # WARNING: This is NOT a standard security practice, but fulfills the business requirement.
    plain_password = models.CharField(max_length=128, blank=True, null=True)

    @property
    def has_backoffice_access(self):
        if not self.role: return False
        return self.role.name in ['admin', 'supervisor']

    @property
    def has_mobile_access(self):
        if not self.role: return False
        return self.role.name in ['admin', 'motorizado']

    def __str__(self):
        return f"{self.username} ({self.role.name if self.role else 'Sin rol'})"
