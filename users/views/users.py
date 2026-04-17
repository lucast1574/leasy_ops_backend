"""
User views: self-service (`me`, `update_user_city`) and backoffice user
management (`list_users`, `assign_role`, `update_user`).
"""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from ..models import Country, City, Role
from ..serializers import UserSerializer, AssignRoleSerializer
from ._assignments import _rebuild_assignments_for_user

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user_city(request):
    city_id = request.data.get('city_id')
    if not city_id:
        return Response({'error': 'city_id requerido'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        city = City.objects.get(id=city_id)
    except City.DoesNotExist:
        return Response({'error': 'Ciudad no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    if request.user.country and city.country != request.user.country:
        return Response({'error': 'La ciudad no pertenece a tu pais'}, status=status.HTTP_400_BAD_REQUEST)
    request.user.city = city
    request.user.save(update_fields=['city'])
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    if not request.user.has_perm_code('manage_users'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    users = User.objects.select_related('role', 'country', 'city').prefetch_related('role__permissions').all().order_by('-date_joined')

    is_admin = request.user.has_perm_code('manage_all_roles')

    if is_admin:
        # Admins see everyone
        pass
    else:
        # Supervisors: only see users from their own country (never cross-country)
        if request.user.country:
            users = users.filter(country=request.user.country)
        # And never see admins
        users = users.exclude(role__name='admin')

    return Response(UserSerializer(users, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role(request, user_id):
    if request.user.id == user_id:
        return Response({'error': 'No puedes cambiar tu propio rol'}, status=status.HTTP_400_BAD_REQUEST)
    if not request.user.has_perm_code('assign_operario_role'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.has_perm_code('manage_all_roles'):
        if target.role and target.role.name in ('admin', 'supervisor'):
            return Response({'error': 'No tienes permiso para modificar este usuario'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AssignRoleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Datos inválidos', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        new_role = Role.objects.get(id=serializer.validated_data['role_id'])
    except Role.DoesNotExist:
        return Response({'error': 'Rol no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if new_role.name == 'admin' and not request.user.has_perm_code('manage_all_roles'):
        return Response({'error': 'Solo admins pueden asignar rol admin'}, status=status.HTTP_403_FORBIDDEN)
    if new_role.name == 'supervisor' and not request.user.has_perm_code('assign_supervisor_role'):
        return Response({'error': 'No tienes permiso para asignar supervisor'}, status=status.HTTP_403_FORBIDDEN)

    old_role_name = target.role.name if target.role else None
    target.role = new_role
    target.is_approved = True
    target.save(update_fields=['role', 'is_approved'])

    # Rebuild supervisor assignments when role changes
    try:
        _rebuild_assignments_for_user(target, old_role_name)
    except Exception as e:
        logger.warning(f'[ASSIGN_ROLE] rebuild_assignments failed: {e}')

    # Refresh from DB to get updated related objects for serializer
    target.refresh_from_db()
    return Response(UserSerializer(target).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    if request.user.id == user_id:
        return Response({'error': 'Usa tu perfil para cambiar tu propia info'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    is_admin = request.user.has_perm_code('manage_all_roles')
    is_supervisor = request.user.has_perm_code('assign_operario_role')

    if not is_admin and not is_supervisor:
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)
    if not is_admin:
        if target.role and target.role.name in ('admin', 'supervisor'):
            return Response({'error': 'No tienes permiso para modificar este usuario'}, status=status.HTTP_403_FORBIDDEN)

    changed = []
    old_city = target.city

    if 'country_id' in request.data:
        country_id = request.data['country_id']
        if country_id:
            try:
                target.country = Country.objects.get(id=country_id)
                changed.append('country')
            except Country.DoesNotExist:
                return Response({'error': 'País no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        else:
            target.country = None
            changed.append('country')

    if 'city_id' in request.data:
        city_id = request.data['city_id']
        if city_id:
            try:
                city = City.objects.get(id=city_id)
                if target.country and city.country_id != target.country_id:
                    return Response({'error': 'La ciudad no pertenece al país del usuario'}, status=status.HTTP_400_BAD_REQUEST)
                target.city = city
                changed.append('city')
            except City.DoesNotExist:
                return Response({'error': 'Ciudad no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        else:
            target.city = None
            changed.append('city')

    if 'is_approved' in request.data and is_admin:
        target.is_approved = bool(request.data['is_approved'])
        changed.append('is_approved')

    if changed:
        target.save(update_fields=changed)

    # If city changed, rebuild supervisor assignments
    if 'city' in changed and target.city != old_city:
        if target.role:
            _rebuild_assignments_for_user(target, target.role.name)

    return Response(UserSerializer(target).data)
