from django.db import models
from django.conf import settings


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
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En curso'),
        ('completed', 'Completada'),
        ('rejected', 'Rechazada'),
        ('rescheduled', 'Reprogramada'),
    ]

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

    # Location
    address = models.CharField(max_length=500, blank=True, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

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
