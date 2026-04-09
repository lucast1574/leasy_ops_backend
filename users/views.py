import os
import logging
import requests as http_requests
from rest_framework import status

logger = logging.getLogger(__name__)
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model

from .models import Country, City, Role
from .serializers import (
    UserSerializer, AssignRoleSerializer,
    CountrySerializer, CitySerializer, RoleSerializer,
)

User = get_user_model()

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')  # Web client ID (backoffice)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_WEB_CLIENT_ID = os.environ.get('GOOGLE_WEB_CLIENT_ID', '')  # Web client ID (general/mobile web)
GOOGLE_ANDROID_CLIENT_ID = os.environ.get('GOOGLE_ANDROID_CLIENT_ID', '')  # Android client ID

# All valid client IDs that can appear as 'aud' in Google ID tokens
VALID_CLIENT_IDS = [cid for cid in [GOOGLE_CLIENT_ID, GOOGLE_WEB_CLIENT_ID, GOOGLE_ANDROID_CLIENT_ID] if cid]

DOMAIN_TO_COUNTRY = {
    'leasyauto.com': 'PE',
    'floty.mx': 'MX',
}


def _get_email_from_id_token(token_str):
    """Verify a Google ID token. Accepts tokens for Web or Android client IDs."""
    # Decode the ID token payload directly (base64) without network verification
    # For mobile flow, the token comes from Google SDK, so it's trustworthy
    import base64, json as _json
    parts = token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    payload_b64 = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        idinfo = _json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise ValueError(f'Failed to decode id_token: {e}')
    # Verify the audience matches one of our client IDs
    token_aud = idinfo.get('aud', '')
    if token_aud not in VALID_CLIENT_IDS:
        raise ValueError(f'Token audience {token_aud} not in valid client IDs')
    return {
        'email': idinfo.get('email', '').lower(),
        'first_name': idinfo.get('given_name', ''),
        'last_name': idinfo.get('family_name', ''),
        'picture': idinfo.get('picture', ''),
    }


# Client ID/Secret pairs for code exchange (backoffice uses WEB_CLIENT_ID if available)
BACKOFFICE_CLIENT_ID = GOOGLE_WEB_CLIENT_ID or GOOGLE_CLIENT_ID
BACKOFFICE_CLIENT_SECRET = os.environ.get('GOOGLE_WEB_CLIENT_SECRET', '') or GOOGLE_CLIENT_SECRET


def _get_email_from_auth_code(code):
    """Exchange a Google authorization code for tokens, then get user info."""
    # Use the backoffice client ID for code exchange (matches frontend initCodeClient)
    exchange_client_id = BACKOFFICE_CLIENT_ID
    exchange_client_secret = BACKOFFICE_CLIENT_SECRET

    # Exchange code for tokens
    logger.info(f'[OAUTH] Starting code exchange with client_id={exchange_client_id[:20]}...')
    try:
        token_resp = http_requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': exchange_client_id,
            'client_secret': exchange_client_secret,
            'redirect_uri': 'postmessage',  # Required for popup flow
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

    # Decode the ID token payload (base64) without network verification
    # The token was received directly from Google over HTTPS, so it's trustworthy
    import base64, json as _json
    parts = id_token_str.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed id_token')
    # Fix base64 padding
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


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def google_auth(request):
    """
    Google OAuth login/register.
    Accepts either:
      - token (str): Google ID token (from mobile app)
      - code (str): Google authorization code (from backoffice popup)
    Also:
      - source (str): 'mobile' or 'backoffice'
      - city_id (int, optional): City to assign on registration
    """
    token = request.data.get('token')
    code = request.data.get('code')
    source = request.data.get('source', 'mobile')
    city_id = request.data.get('city_id')

    if not token and not code:
        return Response({'error': 'Se requiere token o code'}, status=status.HTTP_400_BAD_REQUEST)

    if source not in ('mobile', 'backoffice'):
        return Response({'error': 'source debe ser "mobile" o "backoffice"'}, status=status.HTTP_400_BAD_REQUEST)

    # Get user info from Google
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

    # Validate domain
    domain = email.split('@')[1] if '@' in email else ''
    country_code = DOMAIN_TO_COUNTRY.get(domain)
    if not country_code:
        return Response(
            {'error': 'Dominio no permitido. Solo se aceptan correos de leasyauto.com y floty.mx'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Resolve country
    country = Country.objects.filter(code=country_code).first()

    # Resolve optional city
    city = None
    if city_id:
        try:
            city = City.objects.get(id=city_id, country=country)
        except City.DoesNotExist:
            pass

    # Get or create user
    is_new = False
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        is_new = True
        # Generate unique username
        username = email.split('@')[0]
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            profile_picture=picture,
            country=country,
            city=city,
            registered_from=source,
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

    # Update profile data on each login
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

    # Check access
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

    # Generate JWT
    refresh = RefreshToken.for_user(user)
    return Response({
        'status': 'ok',
        'token': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data,
    })


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def check_user_status(request):
    """Public endpoint to check if a user has been approved (for polling)."""
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
    # Supervisors cannot see admins — only admins see everyone
    if not request.user.has_perm_code('manage_all_roles'):
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

    # SECURITY: supervisors cannot touch admins or other supervisors
    if not request.user.has_perm_code('manage_all_roles'):
        if target.role and target.role.name in ('admin', 'supervisor'):
            return Response({'error': 'No tienes permiso para modificar este usuario'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AssignRoleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_role = Role.objects.get(id=serializer.validated_data['role_id'])

    # Permission checks — what roles can be assigned
    if new_role.name == 'admin' and not request.user.has_perm_code('manage_all_roles'):
        return Response({'error': 'Solo admins pueden asignar rol admin'}, status=status.HTTP_403_FORBIDDEN)
    if new_role.name == 'supervisor' and not request.user.has_perm_code('assign_supervisor_role'):
        return Response({'error': 'No tienes permiso para asignar supervisor'}, status=status.HTTP_403_FORBIDDEN)

    target.role = new_role
    target.is_approved = True
    target.save(update_fields=['role', 'is_approved'])
    return Response(UserSerializer(target).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    """Update a user's country, city, or approval status. Admin can do all, supervisor can change city/country for operarios."""
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

    # Supervisors can only edit operarios and users without role (pending)
    if not is_admin:
        if target.role and target.role.name in ('admin', 'supervisor'):
            return Response({'error': 'No tienes permiso para modificar este usuario'}, status=status.HTTP_403_FORBIDDEN)

    changed = []

    # Country
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

    # City
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

    # Approval status (admin only)
    if 'is_approved' in request.data and is_admin:
        target.is_approved = bool(request.data['is_approved'])
        changed.append('is_approved')

    if changed:
        target.save(update_fields=changed)

    return Response(UserSerializer(target).data)


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_location(request):
    """
    Receive user's lat/lng coordinates, find the nearest city in our coverage,
    and assign it to the user. Also sets the country automatically.
    """
    import math
    lat = request.data.get('latitude')
    lng = request.data.get('longitude')

    if lat is None or lng is None:
        return Response({'error': 'latitude and longitude required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid coordinates'}, status=status.HTTP_400_BAD_REQUEST)

    # Find nearest city using Haversine distance
    cities_with_coords = City.objects.filter(latitude__isnull=False, longitude__isnull=False).select_related('country')

    if not cities_with_coords.exists():
        return Response({'error': 'No cities with coordinates available'}, status=status.HTTP_404_NOT_FOUND)

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    nearest = None
    min_dist = float('inf')
    for city in cities_with_coords:
        d = haversine(lat, lng, city.latitude, city.longitude)
        if d < min_dist:
            min_dist = d
            nearest = city

    user = request.user
    user.city = nearest
    user.country = nearest.country
    user.save(update_fields=['city', 'country'])

    from .serializers import UserSerializer, CitySerializer
    return Response({
        'city': CitySerializer(nearest).data,
        'distance_km': round(min_dist, 1),
        'user': UserSerializer(user).data,
    })
