from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_select_related = ('role',)
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
