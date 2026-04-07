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
        return f"{self.role.name} → {self.permission.codename}"


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
    registered_from = models.CharField(
        max_length=20,
        choices=REGISTERED_FROM_CHOICES,
        blank=True,
        default=''
    )

    def __str__(self):
        return self.email

    def has_app_permission(self, codename):
        if self.role is None:
            return False
        return self.role.has_permission(codename)
