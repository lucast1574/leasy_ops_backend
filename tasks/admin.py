from django.contrib import admin
from .models import CityGeofence, TaskType, Task, TaskPhoto, TaskResult


@admin.register(CityGeofence)
class CityGeofenceAdmin(admin.ModelAdmin):
    list_display = ['city', 'center_latitude', 'center_longitude', 'radius_km', 'is_active']
    list_filter = ['is_active', 'city__country']


@admin.register(TaskType)
class TaskTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_filter = ['is_active']


class TaskPhotoInline(admin.TabularInline):
    model = TaskPhoto
    extra = 0
    readonly_fields = ['uploaded_at']


class TaskResultInline(admin.StackedInline):
    model = TaskResult
    extra = 0
    readonly_fields = ['submitted_at']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'assigned_to', 'status', 'scheduled_date', 'start_time', 'city_geofence']
    list_filter = ['status', 'type', 'scheduled_date', 'city_geofence__city']
    search_fields = ['assigned_to__email', 'client_name', 'placa']
    raw_id_fields = ['assigned_to', 'assigned_by']
    inlines = [TaskPhotoInline, TaskResultInline]
    readonly_fields = ['created_at', 'updated_at']
