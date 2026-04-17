"""
Tracking / monitoring views: live locations visible to the current user and
supervisor-assignment management (list / adoptable / adopt / release).
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from ..models import UserLocation, SupervisorAssignment
from ..serializers import UserSerializer, UserLocationSerializer, SupervisorAssignmentSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_locations(request):
    """
    Returns live locations visible to the requesting user.

    Admin      → ALL users with a location record (admins, supervisors, operarios).
    Supervisor → their own location + their assigned operarios.
    """
    user = request.user

    if not user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    is_admin = user.has_perm_code('manage_all_roles')

    if is_admin:
        # Admin sees everyone
        locations = UserLocation.objects.select_related(
            'user', 'user__role', 'user__city', 'user__country'
        ).all()
    else:
        # Supervisor: their assigned operarios + themselves
        assigned_ids = list(
            SupervisorAssignment.objects.filter(
                supervisor=user
            ).values_list('operario_id', flat=True)
        )
        # Include the supervisor's own id so they see their own pin
        assigned_ids.append(user.id)

        locations = UserLocation.objects.filter(
            user_id__in=assigned_ids
        ).select_related(
            'user', 'user__role', 'user__city', 'user__country'
        )

    try:
        return Response(UserLocationSerializer(locations, many=True).data)
    except Exception as e:
        logger.error(f'[TRACKING] Serialization error: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_assignments(request):
    """List operarios assigned to the current supervisor."""
    if not request.user.role or request.user.role.name not in ('supervisor', 'admin'):
        return Response({'error': 'No eres supervisor'}, status=status.HTTP_403_FORBIDDEN)

    assignments = SupervisorAssignment.objects.filter(
        supervisor=request.user
    ).select_related(
        'operario', 'operario__role', 'operario__country', 'operario__city'
    ).order_by('is_adopted', 'operario__first_name')

    return Response(SupervisorAssignmentSerializer(assignments, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def adoptable_operarios(request):
    """
    List operarios from other cities in the supervisor's country that they
    can adopt. Excludes operarios already assigned to this supervisor.
    """
    user = request.user
    if not user.role or user.role.name not in ('supervisor', 'admin'):
        return Response({'error': 'No eres supervisor'}, status=status.HTTP_403_FORBIDDEN)
    if not user.country:
        return Response([])

    already_assigned = SupervisorAssignment.objects.filter(
        supervisor=user
    ).values_list('operario_id', flat=True)

    operarios = User.objects.filter(
        role__name='operario',
        country=user.country,
        is_approved=True,
    ).exclude(
        id__in=already_assigned
    ).exclude(
        city=user.city  # same-city operarios are auto-assigned
    ).select_related('role', 'country', 'city').order_by('city__name', 'first_name')

    return Response(UserSerializer(operarios, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def adopt_operario(request):
    """
    Supervisor adopts an operario from another city in the same country.
    Body: { "operario_id": <int> }
    """
    user = request.user
    if not user.role or user.role.name not in ('supervisor', 'admin'):
        return Response({'error': 'No eres supervisor'}, status=status.HTTP_403_FORBIDDEN)

    operario_id = request.data.get('operario_id')
    if not operario_id:
        return Response({'error': 'operario_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        operario = User.objects.select_related('role', 'country').get(id=operario_id)
    except User.DoesNotExist:
        return Response({'error': 'Operario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if not operario.role or operario.role.name != 'operario':
        return Response({'error': 'El usuario no es operario'}, status=status.HTTP_400_BAD_REQUEST)
    if operario.country_id != user.country_id:
        return Response({'error': 'No puedes adoptar operarios de otro país'}, status=status.HTTP_403_FORBIDDEN)

    _, created = SupervisorAssignment.objects.get_or_create(
        supervisor=user,
        operario=operario,
        defaults={'is_adopted': True},
    )
    if not created:
        return Response({'error': 'Este operario ya está asignado'}, status=status.HTTP_409_CONFLICT)

    return Response({'status': 'ok', 'message': f'{operario.first_name} adoptado exitosamente'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def release_operario(request, operario_id):
    """
    Supervisor releases an adopted operario. Only adopted assignments can be
    removed; same-city auto-assignments are permanent.
    """
    user = request.user
    if not user.role or user.role.name not in ('supervisor', 'admin'):
        return Response({'error': 'No eres supervisor'}, status=status.HTTP_403_FORBIDDEN)

    try:
        assignment = SupervisorAssignment.objects.get(
            supervisor=user, operario_id=operario_id
        )
    except SupervisorAssignment.DoesNotExist:
        return Response({'error': 'Asignación no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if not assignment.is_adopted:
        return Response(
            {'error': 'No puedes liberar operarios de tu ciudad, solo adoptados'},
            status=status.HTTP_400_BAD_REQUEST
        )

    assignment.delete()
    return Response({'status': 'ok'})
