from django.contrib.auth.models import AbstractUser
from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # PE, MX
    domain_suffix = models.CharField(max_length=100, unique=True)  # leasyauto.com, floty.mx

    class Meta:
        verbose_name_plural = "Countries"

    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Cities"

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class Permission(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.codename


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField(
        Permission,
        through='RolePermission',
        related_name='roles'
    )

    def __str__(self):
        return self.name

    def has_permission(self, codename):
        return self.permissions.filter(codename=codename).exists()


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} -> {self.permission.codename}"


class User(AbstractUser):
    REGISTERED_FROM_CHOICES = [
        ('mobile', 'Mobile'),
        ('backoffice', 'Backoffice'),
    ]

    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    city = models.ForeignKey(
        City, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='users'
    )
    is_approved = models.BooleanField(default=False)
    profile_picture = models.URLField(max_length=500, blank=True, default='')
    registered_from = models.CharField(
        max_length=20,
        choices=REGISTERED_FROM_CHOICES,
        blank=True,
        default=''
    )

    def __str__(self):
        return self.email

    def has_perm_code(self, codename):
        """Check if user's role has a specific permission codename."""
        if self.role is None:
            return False
        return self.role.has_permission(codename)

    # Alias for compatibility
    has_app_permission = has_perm_code


class UserLocation(models.Model):
    """Stores the latest known GPS position for a user (one row per user)."""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='location'
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"{self.user.email} ({self.latitude}, {self.longitude})"


class SupervisorAssignment(models.Model):
    """
    Links a supervisor to the operarios they oversee.

    Default behaviour (created automatically):
      All operarios in the same city as the supervisor.

    Adoption:
      A supervisor can "adopt" operarios from other cities **within the
      same country**.  Cross-country adoption is forbidden at the view
      layer.
    """
    supervisor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='supervised_assignments'
    )
    operario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='supervisor_assignments'
    )
    is_adopted = models.BooleanField(
        default=False,
        help_text='True when the supervisor manually adopted this operario '
                  'from another city in the same country.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('supervisor', 'operario')

    def __str__(self):
        tag = ' [adopted]' if self.is_adopted else ''
        return f"{self.supervisor.email} → {self.operario.email}{tag}"
