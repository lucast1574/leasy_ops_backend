import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import TaskType, Task, TaskPhoto, TaskResult
from .serializers import (
    TaskTypeSerializer, TaskListSerializer, TaskDetailSerializer,
    TaskCreateSerializer, TaskSubmitSerializer, TaskPhotoSerializer,
)
from .s3 import generate_upload_url, generate_download_url

logger = logging.getLogger(__name__)


# ==========================================================================
# Mobile endpoints (operario)
# ==========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_tasks(request):
    """List tasks assigned to the current operario, with optional filters."""
    tasks = Task.objects.filter(
        assigned_to=request.user
    ).select_related('type')

    # Filters
    task_status = request.query_params.get('status')
    if task_status:
        tasks = tasks.filter(status=task_status)

    task_type = request.query_params.get('type')
    if task_type:
        tasks = tasks.filter(type__slug=task_type)

    date = request.query_params.get('date')
    if date:
        tasks = tasks.filter(scheduled_date=date)

    return Response(TaskListSerializer(tasks, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_detail(request, task_id):
    """Get full task detail including photos and result."""
    try:
        task = Task.objects.select_related(
            'type', 'assigned_to', 'assigned_by', 'result'
        ).prefetch_related('photos').get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    # Operarios can only see their own tasks
    if not request.user.has_perm_code('backoffice_access') and task.assigned_to_id != request.user.id:
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    data = TaskDetailSerializer(task).data

    # Add presigned download URLs for photos
    for photo in data.get('photos', []):
        photo['download_url'] = generate_download_url(photo['s3_key'])

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_task(request, task_id):
    """Mark task as in_progress."""
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if task.status not in ('pending', 'rescheduled'):
        return Response({'error': f'No se puede iniciar una tarea con estado "{task.status}"'},
                        status=status.HTTP_400_BAD_REQUEST)

    task.status = 'in_progress'
    task.started_at = timezone.now()
    task.save(update_fields=['status', 'started_at', 'updated_at'])

    return Response(TaskDetailSerializer(task).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_upload_url(request, task_id):
    """
    Generate a presigned S3 URL for the operario to upload a photo.
    Body: { "label": "frontal", "content_type": "image/jpeg" }
    """
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    label = request.data.get('label', 'photo')
    content_type = request.data.get('content_type', 'image/jpeg')

    try:
        result = generate_upload_url(task.id, label, content_type)
    except Exception as e:
        logger.error(f'[S3] Failed to generate presigned URL: {e}')
        return Response({'error': 'Error generando URL de subida'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_upload(request, task_id):
    """
    Confirm that a photo was uploaded to S3 and save the reference.
    Body: { "s3_key": "tasks/1/frontal/abc.jpg", "label": "frontal", "tag": "Foto frontal" }
    """
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    s3_key = request.data.get('s3_key')
    label = request.data.get('label', 'photo')
    tag = request.data.get('tag', '')

    if not s3_key:
        return Response({'error': 's3_key requerido'}, status=status.HTTP_400_BAD_REQUEST)

    photo = TaskPhoto.objects.create(
        task=task, label=label, s3_key=s3_key, tag=tag,
    )

    return Response(TaskPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_task(request, task_id):
    """
    Submit the complete task result. Marks task as completed.
    Body: { "result_data": {...}, "checklist_data": {...}, "observations": "..." }
    """
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if task.status == 'completed':
        return Response({'error': 'Tarea ya completada'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = TaskSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    # Create or update result
    TaskResult.objects.update_or_create(
        task=task,
        defaults={
            'result_data': data.get('result_data', {}),
            'checklist_data': data.get('checklist_data', {}),
        }
    )

    # Update task
    task.status = 'completed'
    task.completed_at = timezone.now()
    task.observations = data.get('observations', task.observations)
    task.save(update_fields=['status', 'completed_at', 'observations', 'updated_at'])

    return Response(TaskDetailSerializer(task).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reschedule_task(request, task_id):
    """Reschedule a task (e.g. nobody home during verification)."""
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    reason = request.data.get('reason', '')
    task.status = 'rescheduled'
    task.observations = reason if reason else task.observations
    task.save(update_fields=['status', 'observations', 'updated_at'])

    return Response(TaskDetailSerializer(task).data)


# ==========================================================================
# Backoffice endpoints (supervisor / admin)
# ==========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def backoffice_tasks(request):
    """List tasks visible to the supervisor/admin."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    tasks = Task.objects.select_related('type', 'assigned_to').all()

    is_admin = request.user.has_perm_code('manage_all_roles')
    if not is_admin:
        # Supervisors see only their assigned operarios' tasks
        from users.models import SupervisorAssignment
        operario_ids = list(
            SupervisorAssignment.objects.filter(
                supervisor=request.user
            ).values_list('operario_id', flat=True)
        )
        tasks = tasks.filter(assigned_to_id__in=operario_ids)

    # Filters
    task_status = request.query_params.get('status')
    if task_status:
        tasks = tasks.filter(status=task_status)

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

    serializer = TaskCreateSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response({'error': 'Datos inválidos', 'details': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    task = serializer.save()
    return Response(TaskDetailSerializer(task).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def backoffice_update_task(request, task_id):
    """Update a task from backoffice."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    allowed_fields = [
        'scheduled_date', 'start_time', 'end_time', 'address',
        'latitude', 'longitude', 'client_name', 'client_dni',
        'placa', 'marca', 'modelo', 'color', 'vehicle_type',
        'metadata', 'observations', 'status',
    ]

    changed = []
    for field in allowed_fields:
        if field in request.data:
            setattr(task, field, request.data[field])
            changed.append(field)

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


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def backoffice_delete_task(request, task_id):
    """Delete a task (only if pending)."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if task.status != 'pending':
        return Response({'error': 'Solo se pueden eliminar tareas pendientes'},
                        status=status.HTTP_400_BAD_REQUEST)

    task.delete()
    return Response({'status': 'ok'})


# ==========================================================================
# Catalogs
# ==========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_task_types(request):
    """List all active task types."""
    return Response(TaskTypeSerializer(
        TaskType.objects.filter(is_active=True), many=True
    ).data)
