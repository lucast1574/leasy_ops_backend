import os
import logging
import math
import requests as http_requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Country, City, Role, UserLocation, SupervisorAssignment
from .serializers import (
    UserSerializer, AssignRoleSerializer,
    CountrySerializer, CitySerializer, RoleSerializer,
    UserLocationSerializer, SupervisorAssignmentSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_WEB_CLIENT_ID = os.environ.get('GOOGLE_WEB_CLIENT_ID', '')
GOOGLE_ANDROID_CLIENT_ID = os.environ.get('GOOGLE_ANDROID_CLIENT_ID', '')
VALID_CLIENT_IDS = [cid for cid in [GOOGLE_CLIENT_ID, GOOGLE_WEB_CLIENT_ID, GOOGLE_ANDROID_CLIENT_ID] if cid]

DOMAIN_TO_COUNTRY = {
    'leasyauto.com': 'PE',
    'floty.mx': 'MX',
}


# ==========================================================================
# Google OAuth helpers
# ==========================================================================

def _get_email_from_id_token(token_str):
    import base64, json as _json
    parts = token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        idinfo = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise ValueError(f'Failed to decode id_token: {e}')
    token_aud = idinfo.get('aud', '')
    if token_aud not in VALID_CLIENT_IDS:
        raise ValueError(f'Token audience {token_aud} not in valid client IDs')
    return {
        'email': idinfo.get('email', '').lower(),
        'first_name': idinfo.get('given_name', ''),
        'last_name': idinfo.get('family_name', ''),
        'picture': idinfo.get('picture', ''),
    }


BACKOFFICE_CLIENT_ID = GOOGLE_WEB_CLIENT_ID or GOOGLE_CLIENT_ID
BACKOFFICE_CLIENT_SECRET = os.environ.get('GOOGLE_WEB_CLIENT_SECRET', '') or GOOGLE_CLIENT_SECRET


def _get_email_from_auth_code(code):
    exchange_client_id = BACKOFFICE_CLIENT_ID
    exchange_client_secret = BACKOFFICE_CLIENT_SECRET
    logger.info(f'[OAUTH] Starting code exchange with client_id={exchange_client_id[:20]}...')
    try:
        token_resp = http_requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': exchange_client_id,
            'client_secret': exchange_client_secret,
            'redirect_uri': 'postmessage',
            'grant_type': 'authorization_code',
        }, timeout=15)
        logger.info(f'[OAUTH] Google token response: status={token_resp.status_code}')
    except http_requests.exceptions.Timeout:
        logger.error('[OAUTH] Timeout calling Google token endpoint')
        raise ValueError('Google token exchange timed out after 15s')
    except http_requests.exceptions.ConnectionError as e:
        logger.error(f'[OAUTH] Connection error: {e}')
        raise ValueError(f'Cannot connect to Google: {e}')
    if token_resp.status_code != 200:
        raise ValueError(f'Failed to exchange code: {token_resp.text}')

    token_data = token_resp.json()
    id_token_str = token_data.get('id_token')
    if not id_token_str:
        raise ValueError('No id_token in response')

    import base64, json as _json
    parts = id_token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        idinfo = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise ValueError(f'Failed to decode id_token: {e}')
    logger.info(f'[OAUTH] Token decoded, email={idinfo.get("email","?")}')
    return {
        'email': idinfo.get('email', '').lower(),
        'first_name': idinfo.get('given_name', ''),
        'last_name': idinfo.get('family_name', ''),
        'picture': idinfo.get('picture', ''),
    }


# ==========================================================================
# Auth views
# ==========================================================================

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def google_auth(request):
    token = request.data.get('token')
    code = request.data.get('code')
    source = request.data.get('source', 'mobile')
    city_id = request.data.get('city_id')

    if not token and not code:
        return Response({'error': 'Se requiere token o code'}, status=status.HTTP_400_BAD_REQUEST)
    if source not in ('mobile', 'backoffice'):
        return Response({'error': 'source debe ser "mobile" o "backoffice"'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if token:
            google_user = _get_email_from_id_token(token)
        else:
            google_user = _get_email_from_auth_code(code)
    except ValueError as e:
        return Response({'error': 'Token invalido', 'details': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        import traceback
        logger.error(f'[OAUTH] Unexpected error in auth: {traceback.format_exc()}')
        return Response({'error': 'Error interno', 'details': str(e), 'trace': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        return _process_google_auth(google_user, source, city_id)
    except Exception as e:
        import traceback
        logger.error(f'[OAUTH] Error processing auth: {traceback.format_exc()}')
        return Response({'error': 'Error interno', 'details': str(e), 'trace': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _process_google_auth(google_user, source, city_id):
    email = google_user['email']
    first_name = google_user['first_name']
    last_name = google_user['last_name']
    picture = google_user.get('picture', '')

    domain = email.split('@')[1] if '@' in email else ''
    country_code = DOMAIN_TO_COUNTRY.get(domain)
    if not country_code:
        return Response(
            {'error': 'Dominio no permitido. Solo se aceptan correos de leasyauto.com y floty.mx'},
            status=status.HTTP_403_FORBIDDEN
        )

    country = Country.objects.filter(code=country_code).first()

    city = None
    if city_id:
        try:
            city = City.objects.get(id=city_id, country=country)
        except City.DoesNotExist:
            pass

    is_new = False
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        is_new = True
        username = email.split('@')[0]
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            email=email, username=username,
            first_name=first_name, last_name=last_name,
            profile_picture=picture, country=country,
            city=city, registered_from=source,
        )
        if source == 'mobile':
            operario = Role.objects.filter(name='operario').first()
            user.role = operario
            user.is_approved = True
        else:
            user.role = None
            user.is_approved = False
        user.set_unusable_password()
        user.save()

        # Auto-assign supervisors for new operarios
        if user.role and user.role.name == 'operario' and user.city:
            _auto_assign_supervisors(user)

    if not is_new:
        changed = False
        if not user.country and country:
            user.country = country
            changed = True
        if not user.city and city:
            user.city = city
            changed = True
        if picture and user.profile_picture != picture:
            user.profile_picture = picture
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            user.save()

    if source == 'backoffice':
        if not user.is_approved or not user.role:
            return Response({
                'status': 'pending_approval',
                'message': 'Tu cuenta esta pendiente de asignacion de rol',
                'user': UserSerializer(user).data,
            })
        if not user.has_perm_code('backoffice_access'):
            return Response({
                'status': 'no_access',
                'message': 'Tu rol no tiene acceso al backoffice. Solo puedes usar la app movil.',
                'user': UserSerializer(user).data,
            })

    if source == 'mobile':
        if not user.is_approved:
            return Response({'error': 'Tu cuenta esta pendiente de aprobacion'},
                            status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    return Response({
        'status': 'ok',
        'token': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    })


# ==========================================================================
# User views
# ==========================================================================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_user_status(request):
    email = request.query_params.get('email')
    if not email:
        return Response({'error': 'email requerido'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email=email)
        return Response({
            'is_approved': user.is_approved,
            'has_backoffice_access': user.has_perm_code('backoffice_access') if user.role else False,
            'role': user.role.name if user.role else None,
        })
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)


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
    serializer.is_valid(raise_exception=True)
    new_role = Role.objects.get(id=serializer.validated_data['role_id'])

    if new_role.name == 'admin' and not request.user.has_perm_code('manage_all_roles'):
        return Response({'error': 'Solo admins pueden asignar rol admin'}, status=status.HTTP_403_FORBIDDEN)
    if new_role.name == 'supervisor' and not request.user.has_perm_code('assign_supervisor_role'):
        return Response({'error': 'No tienes permiso para asignar supervisor'}, status=status.HTTP_403_FORBIDDEN)

    old_role_name = target.role.name if target.role else None
    target.role = new_role
    target.is_approved = True
    target.save(update_fields=['role', 'is_approved'])

    # Rebuild supervisor assignments when role changes
    _rebuild_assignments_for_user(target, old_role_name)

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


# ==========================================================================
# Location
# ==========================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_location(request):
    """
    Receive user's lat/lng coordinates, update UserLocation (real-time tracking),
    and also assign nearest city if not already set.
    """
    lat = request.data.get('latitude')
    lng = request.data.get('longitude')

    if lat is None or lng is None:
        return Response({'error': 'latitude and longitude required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid coordinates'}, status=status.HTTP_400_BAD_REQUEST)

    # Upsert the live location
    UserLocation.objects.update_or_create(
        user=request.user,
        defaults={'latitude': lat, 'longitude': lng},
    )

    # Assign nearest city (existing logic)
    user = request.user
    cities_with_coords = City.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).select_related('country')

    if cities_with_coords.exists():
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
            return R * 2 * math.asin(math.sqrt(a))

        nearest = min(cities_with_coords, key=lambda c: haversine(lat, lng, c.latitude, c.longitude))
        min_dist = haversine(lat, lng, nearest.latitude, nearest.longitude)

        old_city = user.city
        user.city = nearest
        user.country = nearest.country
        user.save(update_fields=['city', 'country'])

        # If city changed, rebuild supervisor assignments
        if old_city != nearest and user.role and user.role.name == 'operario':
            _rebuild_assignments_for_user(user, 'operario')

        return Response({
            'city': CitySerializer(nearest).data,
            'distance_km': round(min_dist, 1),
            'user': UserSerializer(user).data,
        })

    return Response({'status': 'location_saved'})


# ==========================================================================
# Tracking / Monitoring
# ==========================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_locations(request):
    """
    Returns live locations visible to the requesting user.

    Admin  → all users with a location record.
    Supervisor → only their assigned operarios (same-city auto + adopted).
    """
    user = request.user

    if not user.has_perm_code('backoffice_access'):
        return Response({'error': 'No tienes permiso'}, status=status.HTTP_403_FORBIDDEN)

    is_admin = user.has_perm_code('manage_all_roles')

    if is_admin:
        locations = UserLocation.objects.select_related(
            'user', 'user__role', 'user__city', 'user__country'
        ).all()
    else:
        # Supervisor: get operario ids from assignments
        assigned_ids = SupervisorAssignment.objects.filter(
            supervisor=user
        ).values_list('operario_id', flat=True)

        locations = UserLocation.objects.filter(
            user_id__in=assigned_ids
        ).select_related(
            'user', 'user__role', 'user__city', 'user__country'
        )

    return Response(UserLocationSerializer(locations, many=True).data)


# ==========================================================================
# Supervisor assignment management
# ==========================================================================

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


# ==========================================================================
# Public / Catalog
# ==========================================================================

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def list_countries(request):
    return Response(CountrySerializer(Country.objects.all(), many=True).data)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def list_cities(request):
    cities = City.objects.select_related('country').all()
    country_id = request.query_params.get('country_id')
    country_code = request.query_params.get('country_code')
    if country_id:
        cities = cities.filter(country_id=country_id)
    elif country_code:
        cities = cities.filter(country__code=country_code.upper())
    return Response(CitySerializer(cities, many=True).data)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def list_roles(request):
    return Response(RoleSerializer(Role.objects.prefetch_related('permissions').all(), many=True).data)


# ==========================================================================
# Internal helpers
# ==========================================================================

def _auto_assign_supervisors(operario):
    """
    Auto-assign all supervisors in the operario's city to this operario.
    Called when a new operario registers or changes city.
    """
    if not operario.city:
        return

    supervisors = User.objects.filter(
        role__name='supervisor',
        city=operario.city,
        is_approved=True,
    )
    for sup in supervisors:
        SupervisorAssignment.objects.get_or_create(
            supervisor=sup,
            operario=operario,
            defaults={'is_adopted': False},
        )


def _auto_assign_operarios(supervisor):
    """
    Auto-assign all operarios in the supervisor's city to this supervisor.
    Called when a user becomes a supervisor or changes city.
    """
    if not supervisor.city:
        return

    operarios = User.objects.filter(
        role__name='operario',
        city=supervisor.city,
        is_approved=True,
    )
    for op in operarios:
        SupervisorAssignment.objects.get_or_create(
            supervisor=supervisor,
            operario=op,
            defaults={'is_adopted': False},
        )


def _rebuild_assignments_for_user(user, old_role_name):
    """
    Rebuild SupervisorAssignment rows when a user's role or city changes.
    """
    role_name = user.role.name if user.role else None

    if old_role_name == 'operario' and role_name != 'operario':
        # Was operario, no longer → remove all assignments where they are the operario
        SupervisorAssignment.objects.filter(operario=user).delete()

    if old_role_name == 'supervisor' and role_name != 'supervisor':
        # Was supervisor, no longer → remove all assignments where they are supervisor
        SupervisorAssignment.objects.filter(supervisor=user).delete()

    if role_name == 'operario':
        # Remove old auto-assignments (keep adopted ones)
        SupervisorAssignment.objects.filter(operario=user, is_adopted=False).delete()
        # Re-create auto-assignments for new city
        _auto_assign_supervisors(user)

    if role_name == 'supervisor':
        # Remove old auto-assignments (keep adopted ones within same country)
        SupervisorAssignment.objects.filter(supervisor=user, is_adopted=False).delete()
        # Remove adopted ones from other countries (safety)
        if user.country:
            SupervisorAssignment.objects.filter(
                supervisor=user, is_adopted=True
            ).exclude(operario__country=user.country).delete()
        # Re-create auto-assignments for new city
        _auto_assign_operarios(user)
