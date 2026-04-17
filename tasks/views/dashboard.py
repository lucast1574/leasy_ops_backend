"""
Dashboard / analytics endpoints: summary cards, per-type and per-status
counts, operario ranking, in-progress list and last-7-days completions.
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Task
from ..serializers import TaskListSerializer
from ..selectors import visible_tasks_for

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    """Dashboard metrics for supervisors/admins."""
    if not request.user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    from django.db.models import Count, Avg, F, Q, ExpressionWrapper, DurationField, FloatField
    from django.db.models.functions import TruncDate
    import datetime

    is_admin = request.user.has_perm_code('manage_all_roles')

    # Base queryset (visibility scoping handled centrally)
    tasks = visible_tasks_for(request.user)

    today = timezone.now().date()
    week_ago = today - datetime.timedelta(days=7)
    month_ago = today - datetime.timedelta(days=30)

    # --- Summary cards ---
    total_today = tasks.filter(scheduled_date=today).count()
    pending_today = tasks.filter(scheduled_date=today, status='pending').count()
    in_progress = tasks.filter(status__in=['in_progress', 'rescheduled']).count()
    completed_today = tasks.filter(scheduled_date=today, status='completed').count()
    completed_week = tasks.filter(completed_at__date__gte=week_ago, status='completed').count()
    completed_month = tasks.filter(completed_at__date__gte=month_ago, status='completed').count()
    rejected_month = tasks.filter(completed_at__date__gte=month_ago, status='rejected').count()
    rescheduled_month = tasks.filter(updated_at__date__gte=month_ago, status='rescheduled').count()

    # --- Tasks by type ---
    by_type = list(
        tasks.filter(scheduled_date__gte=month_ago)
        .values('type__name', 'type__slug')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # --- Tasks by status ---
    by_status = list(
        tasks.values('status').annotate(count=Count('id')).order_by('-count')
    )

    # --- Operario ranking (last 30 days) ---
    # Single annotated queryset for counts — avoids N+1
    ranking_qs = list(
        tasks.filter(completed_at__date__gte=month_ago, status='completed')
        .values(
            'assigned_to__id',
            'assigned_to__first_name',
            'assigned_to__last_name',
            'assigned_to__profile_picture',
            'assigned_to__city__name',
        )
        .annotate(
            completed_count=Count('id'),
        )
        .order_by('-completed_count')[:10]
    )

    # Get total assigned per operario in a single query
    op_ids = [r['assigned_to__id'] for r in ranking_qs]
    total_assigned_map = dict(
        tasks.filter(assigned_to_id__in=op_ids, scheduled_date__gte=month_ago)
        .values('assigned_to_id')
        .annotate(total=Count('id'))
        .values_list('assigned_to_id', 'total')
    )

    # Compute average completion time per operario using a single annotated queryset
    # We use ExpressionWrapper to compute duration in seconds at DB level
    duration_expr = ExpressionWrapper(
        F('completed_at') - F('started_at'),
        output_field=DurationField()
    )
    avg_duration_map = dict(
        tasks.filter(
            assigned_to_id__in=op_ids,
            status='completed',
            started_at__isnull=False,
            completed_at__isnull=False,
            completed_at__date__gte=month_ago,
        )
        .annotate(duration=duration_expr)
        .values('assigned_to_id')
        .annotate(avg_duration=Avg('duration'))
        .values_list('assigned_to_id', 'avg_duration')
    )

    ranking = []
    for r in ranking_qs:
        op_id = r['assigned_to__id']
        total = total_assigned_map.get(op_id, 0)
        avg_td = avg_duration_map.get(op_id)
        avg_minutes = round(avg_td.total_seconds() / 60, 1) if avg_td else None
        efficiency = round(r['completed_count'] / total * 100, 1) if total > 0 else 0
        ranking.append({
            **r,
            'avg_minutes': avg_minutes,
            'total_assigned': total,
            'efficiency': efficiency,
        })

    # --- In-progress tasks list ---
    in_progress_tasks = TaskListSerializer(
        tasks.filter(status__in=['in_progress', 'rescheduled'])
        .select_related('type', 'assigned_to')
        .order_by('scheduled_date', 'start_time')[:20],
        many=True
    ).data

    # --- Daily completions (last 7 days) ---
    daily = list(
        tasks.filter(completed_at__date__gte=week_ago, status='completed')
        .annotate(day=TruncDate('completed_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    return Response({
        'summary': {
            'total_today': total_today,
            'pending_today': pending_today,
            'in_progress': in_progress,
            'completed_today': completed_today,
            'completed_week': completed_week,
            'completed_month': completed_month,
            'rejected_month': rejected_month,
            'rescheduled_month': rescheduled_month,
        },
        'by_type': by_type,
        'by_status': by_status,
        'ranking': ranking,
        'in_progress_tasks': in_progress_tasks,
        'daily_completions': [{'day': str(d['day']), 'count': d['count']} for d in daily],
    })
