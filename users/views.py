import os
import requests as http_requests
from rest_framework import status
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
    last_error = None
    for client_id in VALID_CLIENT_IDS:
        try:
            idinfo = id_token.verify_oauth2_token(
                token_str, google_requests.Request(), client_id
            )
            return {
                'email': idinfo.get('email', '').lower(),
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'picture': idinfo.get('picture', ''),
            }
        except ValueError as e:
            last_error = e
            continue
    raise ValueError(f'Token verification failed: {last_error}')


# Client ID/Secret pairs for code exchange (backoffice uses WEB_CLIENT_ID if available)
BACKOFFICE_CLIENT_ID = GOOGLE_WEB_CLIENT_ID or GOOGLE_CLIENT_ID
BACKOFFICE_CLIENT_SECRET = os.environ.get('GOOGLE_WEB_CLIENT_SECRET', '') or GOOGLE_CLIENT_SECRET


def _get_email_from_auth_code(code):
    """Exchange a Google authorization code for tokens, then get user info."""
    # Use the backoffice client ID for code exchange (matches frontend initCodeClient)
    exchange_client_id = BACKOFFICE_CLIENT_ID
    exchange_client_secret = BACKOFFICE_CLIENT_SECRET

    # Exchange code for tokens
    token_resp = http_requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': exchange_client_id,
        'client_secret': exchange_client_secret,
        'redirect_uri': 'postmessage',  # Required for popup flow
        'grant_type': 'authorization_code',
    })
    if token_resp.status_code != 200:
        raise ValueError(f'Failed to exchange code: {token_resp.text}')

    token_data = token_resp.json()
    id_token_str = token_data.get('id_token')
    if not id_token_str:
        raise ValueError('No id_token in response')

    # Verify the ID token we got from the exchange
    idinfo = id_token.verify_oauth2_token(
        id_token_str, google_requests.Request(), exchange_client_id
    )
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

    serializer = AssignRoleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_role = Role.objects.get(id=serializer.validated_data['role_id'])

    # Permission checks
    if new_role.name == 'admin' and not request.user.has_perm_code('manage_all_roles'):
        return Response({'error': 'Solo admins pueden asignar rol admin'}, status=status.HTTP_403_FORBIDDEN)
    if new_role.name == 'supervisor' and not request.user.has_perm_code('assign_supervisor_role'):
        return Response({'error': 'No tienes permiso para asignar supervisor'}, status=status.HTTP_403_FORBIDDEN)

    target.role = new_role
    target.is_approved = True
    target.save(update_fields=['role', 'is_approved'])
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
