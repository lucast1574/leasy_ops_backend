"""
Authentication views: Google OAuth login and account status check.

Both mobile (id_token flow) and backoffice (auth-code flow) go through
`google_auth`. The common post-auth logic lives in `_process_google_auth`.
"""
import logging
import traceback

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from ..models import Country, City, Role
from ..serializers import UserSerializer
from ._google_oauth import (
    DOMAIN_TO_COUNTRY,
    get_email_from_id_token,
    get_email_from_auth_code,
)
from ._assignments import _auto_assign_supervisors

logger = logging.getLogger(__name__)
User = get_user_model()


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
            google_user = get_email_from_id_token(token)
        else:
            google_user = get_email_from_auth_code(code)
    except ValueError as e:
        return Response({'error': 'Token invalido', 'details': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.error(f'[OAUTH] Unexpected error in auth: {traceback.format_exc()}')
        return Response({'error': 'Error interno', 'details': str(e), 'trace': traceback.format_exc()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        return _process_google_auth(google_user, source, city_id)
    except Exception as e:
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

    # Fallback: if no city was provided, assign the first city of the country
    # (capital / default). GPS-based assignment will refine it later.
    if not city and country:
        city = City.objects.filter(country=country).order_by('id').first()

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
        if not user.city:
            # Assign fallback city (first city of user's country)
            fallback_city = city  # from request or country default above
            if not fallback_city and user.country:
                fallback_city = City.objects.filter(country=user.country).order_by('id').first()
            if fallback_city:
                user.city = fallback_city
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
            # If city was just assigned and user is operario, rebuild assignments
            if user.city and user.role and user.role.name == 'operario':
                _auto_assign_supervisors(user)

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
