from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Role, Permission, RolePermission, Country, City,
    UserLocation, SupervisorAssignment,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'domain_suffix')
    search_fields = ('name', 'code', 'domain_suffix')

#check
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


@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'latitude', 'longitude', 'updated_at')
    search_fields = ('user__email', 'user__first_name')
    list_filter = ('updated_at',)
    readonly_fields = ('updated_at',)


@admin.register(SupervisorAssignment)
class SupervisorAssignmentAdmin(admin.ModelAdmin):
    list_display = ('supervisor', 'operario', 'is_adopted', 'created_at')
    list_filter = ('is_adopted', 'supervisor__city')
    search_fields = (
        'supervisor__email', 'supervisor__first_name',
        'operario__email', 'operario__first_name',
    )
    readonly_fields = ('created_at',)
