"""
Backoffice endpoints for supervisors and admins: list, create, update,
reassign and delete tasks. Geofence / cross-country / operario-city rules
live in ``tasks.validators``.
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Task
from ..serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateSerializer,
)
from ..validators import (
    validate_task_location,
    validate_task_assignment,
    validate_task_reassignment,
    TaskValidationError,
)
from ..selectors import visible_tasks_for, build_maps_link
from ..s3 import generate_download_url

logger = logging.getLogger(__name__)

# Task types that must have a real customer attached.
# Process-type tasks (conversion, traslado, verificar_vehiculo, notaria,
# gestiones) can be created without one since they represent internal
# vehicle/administrative work rather than a customer-facing visit.
REQUIRES_CLIENT = ('verificacion', 'recupero', 'entrega')

# Conversion tasks must specify the service type upfront (from backoffice).
# The operario sees it read-only in the mobile app.
CONVERSION_SERVICE_TYPES = ('GNV', 'Revisión Técnica')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backoffice_tasks(request):
    """List tasks visible to the supervisor/admin."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    from django.db.models import Count
    tasks = visible_tasks_for(request.user).select_related(
        'type', 'assigned_to'
    ).annotate(photo_count=Count('photos'))

    # Filters
    task_status = request.query_params.get('status')
    if task_status:
        tasks = tasks.filter(status=task_status)

    main_status = request.query_params.get('main_status')
    if main_status:
        sub_statuses = [k for k, v in Task.STATUS_TO_MAIN.items() if v == main_status]
        tasks = tasks.filter(status__in=sub_statuses)

    task_type = request.query_params.get('type')
    if task_type:
        tasks = tasks.filter(type__slug=task_type)

    date = request.query_params.get('date')
    if date:
        tasks = tasks.filter(scheduled_date=date)

    assigned_to = request.query_params.get('assigned_to')
    if assigned_to:
        tasks = tasks.filter(assigned_to_id=assigned_to)

    return Response(TaskListSerializer(tasks.order_by('-scheduled_date', '-start_time'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backoffice_create_task(request):
    """Create and assign a task to an operario."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    # 1. Validate geofence
    lat = request.data.get('latitude')
    lng = request.data.get('longitude')
    try:
        geofence = validate_task_location(lat, lng)
    except TaskValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Validate operario assignment
    assigned_to_id = request.data.get('assigned_to_id')
    if not assigned_to_id:
        return Response({'error': 'assigned_to_id es obligatorio'}, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        operario = User.objects.select_related('city', 'country', 'role').get(id=assigned_to_id)
    except User.DoesNotExist:
        return Response({'error': 'Operario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    try:
        validate_task_assignment(request.user, operario, geofence)
    except TaskValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 2.5. Validate client_name and vehicle data for customer-facing task types.
    type_slug = (request.data.get('type_slug') or '').strip()
    if type_slug in REQUIRES_CLIENT:
        client_name = (request.data.get('client_name') or '').strip()
        if not client_name:
            return Response(
                {'error': 'El nombre del cliente es obligatorio para tareas de '
                          'verificación, recupero y entrega.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # For 'verificacion', only client_name is strictly mandatory in this context.
        pass

    # 2.6. Conversion tasks require a service type in metadata.
    if type_slug == 'conversion':
        metadata = request.data.get('metadata') or {}
        svc_type = (metadata.get('service_type') or '').strip()
        if svc_type not in CONVERSION_SERVICE_TYPES:
            return Response(
                {'error': f'Tipo de servicio obligatorio para conversión. '
                          f'Opciones: {", ".join(CONVERSION_SERVICE_TYPES)}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # 3. Create the task
    serializer = TaskCreateSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response({'error': 'Datos invalidos', 'details': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    # Auto-generate google maps link
    lat = float(request.data.get('latitude'))
    lng = float(request.data.get('longitude'))
    maps_link = build_maps_link(lat, lng, request.data.get('google_maps_link', ''))

    task = serializer.save(city_geofence=geofence, google_maps_link=maps_link)
    return Response(TaskDetailSerializer(task).data, status=status.HTTP_201_CREATED)


# Valid status transitions for backoffice updates
VALID_STATUS_TRANSITIONS = {
    'pending': ['pending', 'rescheduled'],
    'rescheduled': ['pending', 'rescheduled'],
    'in_progress': ['in_progress', 'rescheduled', 'pending'],
    'completed': ['completed', 'rescheduled'],
    'rejected': ['rejected'],
}


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def backoffice_task_detail(request, task_id):
    """
    GET    → full task detail (with photos + presigned download URLs + result).
    PATCH  → update task fields / status.
    DELETE → remove task permanently.
    """
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    # ---- GET: return full detail with photos (presigned URLs) and result ----
    if request.method == 'GET':
        task = Task.objects.select_related(
            'type', 'assigned_to', 'assigned_by', 'result'
        ).prefetch_related('photos').get(id=task_id)
        data = TaskDetailSerializer(task).data
        for photo in data.get('photos', []):
            photo['download_url'] = generate_download_url(photo['s3_key'])
        return Response(data)

    # ---- DELETE: remove task ----
    if request.method == 'DELETE':
        task.delete()
        return Response({'status': 'ok'})

    # ---- PATCH: update fields (below) ----

    # Fields that can be freely updated (status excluded — handled separately with validation)
    allowed_fields = [
        'scheduled_date', 'start_time', 'end_time', 'address',
        'latitude', 'longitude', 'client_name', 'client_dni',
        'placa', 'marca', 'modelo', 'color', 'vehicle_type',
        'metadata', 'observations',
    ]

    changed = []
    for field in allowed_fields:
        if field in request.data:
            setattr(task, field, request.data[field])
            changed.append(field)

    # Status change requires validation against allowed transitions
    if 'status' in request.data:
        new_status = request.data['status']
        valid_choices = [choice[0] for choice in Task.STATUS_CHOICES]
        if new_status not in valid_choices:
            return Response(
                {'error': f'Estado no valido. Opciones: {", ".join(valid_choices)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        allowed_next = VALID_STATUS_TRANSITIONS.get(task.status, [])
        if new_status not in allowed_next:
            return Response(
                {'error': f'No se puede cambiar el estado de "{task.status}" a "{new_status}". '
                          f'Transiciones permitidas: {", ".join(allowed_next)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = new_status
        changed.append('status')

    # Allow reassigning operario
    if 'assigned_to_id' in request.data:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            new_operario = User.objects.get(id=request.data['assigned_to_id'])
            task.assigned_to = new_operario
            changed.append('assigned_to')
        except User.DoesNotExist:
            return Response({'error': 'Operario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if changed:
        changed.append('updated_at')
        task.save(update_fields=changed)

    return Response(TaskDetailSerializer(task).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def backoffice_reassign_task(request, task_id):
    """Reassign a task to a different operario."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if task.status in ('completed', 'rejected'):
        return Response({'error': 'No se puede reasignar una tarea finalizada'},
                        status=status.HTTP_400_BAD_REQUEST)

    new_operario_id = request.data.get('assigned_to_id')
    if not new_operario_id:
        return Response({'error': 'assigned_to_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        new_operario = User.objects.get(id=new_operario_id)
    except User.DoesNotExist:
        return Response({'error': 'Operario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if not new_operario.role or new_operario.role.name != 'operario':
        return Response({'error': 'El usuario debe ser operario'}, status=status.HTTP_400_BAD_REQUEST)

    # Validate geofence rules
    try:
        validate_task_reassignment(request.user, new_operario, task)
    except TaskValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    old_operario = task.assigned_to
    task.assigned_to = new_operario
    # Reset to pending if it was in progress
    if task.status in ('in_progress', 'rescheduled'):
        task.status = 'pending'
        task.started_at = None
    task.save(update_fields=['assigned_to', 'status', 'started_at', 'updated_at'])

    return Response({
        'status': 'ok',
        'message': f'Tarea reasignada de {old_operario.first_name} a {new_operario.first_name}',
        'task': TaskDetailSerializer(task).data,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def backoffice_delete_task(request, task_id):
    """Delete a task. Any status is allowed — the backoffice user takes
    responsibility via the confirmation dialog in the frontend."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    task.delete()
    return Response({'status': 'ok'})
