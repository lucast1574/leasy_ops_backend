from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Permission, RolePermission, Country, City


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'domain_suffix')
    search_fields = ('name', 'code', 'domain_suffix')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'country')
    list_filter = ('country',)
    search_fields = ('name',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'codename', 'description')
    search_fields = ('codename',)


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 1


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'permission_list')
    inlines = [RolePermissionInline]
    search_fields = ('name',)

    def permission_list(self, obj):
        return ', '.join(obj.permissions.values_list('codename', flat=True))
    permission_list.short_description = 'Permissions'


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'role', 'permission')
    list_filter = ('role',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'id', 'email', 'first_name', 'last_name',
        'role', 'country', 'city', 'is_approved',
        'registered_from', 'is_staff', 'is_active'
    )
    list_filter = ('role', 'country', 'city', 'is_approved', 'registered_from', 'is_staff')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Leasy Ops', {
            'fields': ('role', 'country', 'city', 'is_approved', 'registered_from')
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Leasy Ops', {
            'fields': ('role', 'country', 'city', 'is_approved', 'registered_from')
        }),
    )
