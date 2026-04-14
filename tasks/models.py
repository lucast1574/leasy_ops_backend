import math
from django.db import models
from django.conf import settings


class CityGeofence(models.Model):
    """
    Defines a circular geofence around each operational city.
    Tasks can only be created within a city's geofence,
    and only assigned to operarios belonging to that city.
    """
    city = models.OneToOneField(
        'users.City', on_delete=models.CASCADE, related_name='geofence'
    )
    # Center point (defaults to city coordinates)
    center_latitude = models.FloatField()
    center_longitude = models.FloatField()
    # Radius in kilometers
    radius_km = models.FloatField(default=80.0,
        help_text='Geofence radius in km. Large to cover suburban/rural taxi drivers.')
    is_active = models.BooleanField(default=True)

    def contains(self, lat, lng):
        """Check if a point (lat, lng) falls within this geofence."""
        return self._haversine(
            self.center_latitude, self.center_longitude, lat, lng
        ) <= self.radius_km

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Calculate distance in km between two points using Haversine formula."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))

    @classmethod
    def find_geofence(cls, lat, lng):
        """
        Find which active geofence contains the given point.
        Returns the CityGeofence or None.
        """
        for gf in cls.objects.filter(is_active=True).select_related('city', 'city__country'):
            if gf.contains(lat, lng):
                return gf
        return None

    def __str__(self):
        return f"{self.city.name} ({self.radius_km}km)"

    class Meta:
        ordering = ['city__country__code', 'city__name']


class TaskType(models.Model):
    """
    The 8 task types: verificacion, recupero, entrega, conversion,
    traslado, verificar_vehiculo, notaria, gestiones
    """
    SLUG_CHOICES = [
        ('verificacion', 'Verificación'),
        ('recupero', 'Recupero'),
        ('entrega', 'Entrega unidad'),
        ('conversion', 'Conversión'),
        ('traslado', 'Traslado'),
        ('verificar_vehiculo', 'Verificar Vehículo'),
        ('notaria', 'Notaría'),
        ('gestiones', 'Gestiones/Otros'),
    ]

    slug = models.CharField(max_length=30, unique=True, choices=SLUG_CHOICES)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, default='')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Task(models.Model):
    # Main states (for dashboard grouping)
    MAIN_STATE_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En curso'),
        ('completed', 'Completada'),
    ]

    # Sub-states (the actual detailed status)
    STATUS_CHOICES = [
        # pending sub-states
        ('pending', 'Pendiente'),
        # in_progress sub-states
        ('in_progress', 'En curso'),
        ('rescheduled', 'Reprogramada'),
        # completed sub-states
        ('completed', 'Completada'),
        ('rejected', 'Rechazada'),
    ]

    # Mapping: sub-state → main state (for dashboard filtering)
    STATUS_TO_MAIN = {
        'pending': 'pending',
        'in_progress': 'in_progress',
        'rescheduled': 'in_progress',
        'completed': 'completed',
        'rejected': 'completed',
    }

    # Core fields
    type = models.ForeignKey(TaskType, on_delete=models.PROTECT, related_name='tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='assigned_tasks',
        help_text='Operario who performs the task'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_tasks',
        help_text='Supervisor or admin who created/assigned the task'
    )

    # Scheduling
    scheduled_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    # Location (REQUIRED — every task must have coordinates)
    address = models.CharField(max_length=500, blank=True, default='')
    latitude = models.FloatField(
        null=True, blank=True,
        help_text='Required for new tasks. Must fall within an active city geofence.'
    )
    longitude = models.FloatField(
        null=True, blank=True,
        help_text='Required for new tasks. Must fall within an active city geofence.'
    )
    google_maps_link = models.URLField(max_length=500, blank=True, default='',
        help_text='Auto-generated Google Maps link for the task location')

    # The geofence/city this task belongs to (set automatically on creation)
    city_geofence = models.ForeignKey(
        CityGeofence, on_delete=models.PROTECT,
        null=True, blank=True, related_name='tasks',
        help_text='Auto-assigned based on lat/lng on creation'
    )

    # Client info (optional, depends on task type)
    client_name = models.CharField(max_length=200, blank=True, default='')
    client_dni = models.CharField(max_length=20, blank=True, default='')

    # Vehicle info (optional, depends on task type)
    placa = models.CharField(max_length=20, blank=True, default='')
    marca = models.CharField(max_length=100, blank=True, default='')
    modelo = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=50, blank=True, default='')
    vehicle_type = models.CharField(max_length=50, blank=True, default='')

    # Type-specific data (flexible JSON for fields that vary by type)
    metadata = models.JSONField(default=dict, blank=True,
        help_text='Type-specific fields: notary names, management_type, service_type, etc.')

    # Execution timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Observations
    observations = models.TextField(blank=True, default='')

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'start_time']
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['assigned_to', 'scheduled_date']),
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_date']),
        ]

    @property
    def main_status(self):
        """Returns the main state for dashboard grouping."""
        return self.STATUS_TO_MAIN.get(self.status, 'pending')

    def __str__(self):
        return f"{self.type.name} - {self.assigned_to.email} ({self.scheduled_date})"


class TaskPhoto(models.Model):
    """Photos uploaded by the operario during task execution."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='photos')
    label = models.CharField(max_length=100,
        help_text='Category: frontal, trasera, dni, checklist, certificado, etc.')
    s3_key = models.CharField(max_length=500,
        help_text='S3 object key (path within bucket)')
    tag = models.CharField(max_length=200, blank=True, default='',
        help_text='User-provided tag/label for the photo')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.task_id} - {self.label}"


class TaskResult(models.Model):
    """Submitted result when operario completes the task flow."""
    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name='result')

    # The full form data from the flow, serialized as JSON
    result_data = models.JSONField(default=dict, blank=True,
        help_text='All form fields: who_received, housing_type, verification_result, etc.')

    # Checklist data (for traslado/entrega inventory)
    checklist_data = models.JSONField(default=dict, blank=True,
        help_text='Checklist items: { "item_name": true/false }')

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for Task #{self.task_id}"
