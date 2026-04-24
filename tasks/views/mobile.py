"""
Mobile endpoints used by the Flutter operario app: list tasks, view detail,
start, photo upload via S3 presigned URLs, submit, and reschedule.
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Task, TaskPhoto, TaskResult
from ..serializers import (
    TaskListSerializer, TaskDetailSerializer,
    TaskSubmitSerializer, TaskPhotoSerializer,
    TaskProgressSerializer,
)
from ..s3 import generate_upload_url, generate_download_url

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_tasks(request):
    """List tasks assigned to the current operario, with optional filters."""
    tasks = Task.objects.filter(
        assigned_to=request.user
    ).select_related('type', 'assigned_to')

    # Filters
    task_status = request.query_params.get('status')
    if task_status:
        tasks = tasks.filter(status=task_status)

    # Filter by main_status (dashboard grouping: pending, in_progress, completed)
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

    from django.db.models import Count
    tasks = tasks.annotate(photo_count=Count('photos'))

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

    if task.status == 'in_progress':
        return Response(TaskDetailSerializer(task).data)

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
def update_progress(request, task_id):
    """Save intermediate progress (current step and draft data)."""
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TaskProgressSerializer(task, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    """
    Reschedule a task by marking the current one as 'rescheduled' (finished)
    and creating a new cloned task for the next day.
    """
    try:
        task = Task.objects.get(id=task_id, assigned_to=request.user)
    except Task.DoesNotExist:
        return Response({'error': 'Tarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if task.status in ('completed', 'rejected', 'rescheduled'):
        return Response({'error': 'Esta tarea ya está finalizada'}, status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason', '')
    
    # 1. Mark original task as finished with 'rescheduled' status
    task.status = 'rescheduled'
    task.observations = reason if reason else task.observations
    task.completed_at = timezone.now()
    task.save(update_fields=['status', 'observations', 'completed_at', 'updated_at'])

    # 2. Create a NEW pending task for the next day
    from datetime import timedelta
    next_day = task.scheduled_date + timedelta(days=1)
    
    # Clone logic
    new_task = Task.objects.get(id=task_id) # Reload to clone fresh
    new_task.pk = None
    new_task.id = None
    new_task.status = 'pending'
    new_task.scheduled_date = next_day
    new_task.observations = f"Reprogramación automática de tarea #{task_id}. {reason}"
    new_task.started_at = None
    new_task.completed_at = None
    new_task.save()

    return Response(TaskDetailSerializer(new_task).data)
