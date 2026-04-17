"""
Public catalog endpoints for the ``tasks`` app (task types).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import TaskType
from ..serializers import TaskTypeSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_task_types(request):
    """List all active task types."""
    return Response(TaskTypeSerializer(
        TaskType.objects.filter(is_active=True), many=True
    ).data)
