from django.contrib.auth import get_user_model
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

from .models import Country, City, Role
from .serializers import (
    UserSerializer, AssignRoleSerializer,
    CountrySerializer, CitySerializer
)

User = get_user_model()

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')

DOMAIN_TO_COUNTRY_CODE = {
    'leasyauto.com': 'PE',
    'floty.mx': 'MX',
}


def _get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def _domain_from_email(email):
    """Extract domain from an email address."""
    parts = email.split('@')
    if len(parts) != 2:
        return None
    return parts[1].lower()


@api_view(['POST'])
@permission_classes([AllowAny])
def google_auth(request):
    """
    Google OAuth login / register.

    Body:
        token     (str)  - Google ID token
        source    (str)  - 'mobile' or 'backoffice'
        city_id   (int, optional) - City pk to assign on registration
    """
    token = request.data.get('token')
    source = request.data.get('source', 'mobile')
    city_id = request.data.get('city_id')

    if not token:
        return Response({'error': 'token is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if source not in ('mobile', 'backoffice'):
        return Response({'error': "source must be 'mobile' or 'backoffice'."}, status=status.HTTP_400_BAD_REQUEST)

    # Verify the Google ID token
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        return Response({'error': f'Invalid token: {str(e)}'}, status=status.HTTP_401_UNAUTHORIZED)

    email = idinfo.get('email', '').lower()
    first_name = idinfo.get('given_name', '')
    last_name = idinfo.get('family_name', '')

    # Domain validation
    domain = _domain_from_email(email)
    country_code = DOMAIN_TO_COUNTRY_CODE.get(domain)
    if not country_code:
        return Response(
            {'error': 'Email domain not authorized. Only leasyauto.com and floty.mx are allowed.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Resolve country
    try:
        country = Country.objects.get(code=country_code)
    except Country.DoesNotExist:
        return Response({'error': 'Country not configured in database.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Resolve optional city
    city = None
    if city_id:
        try:
            city = City.objects.get(id=city_id, country=country)
        except City.DoesNotExist:
            return Response({'error': 'City not found or does not belong to the user country.'}, status=status.HTTP_400_BAD_REQUEST)

    # Get or create user
    created = False
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        created = True
        username = email.split('@')[0]
        # Ensure username uniqueness
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            country=country,
            city=city,
            registered_from=source,
        )

        if source == 'mobile':
            try:
                operario_role = Role.objects.get(name='operario')
            except Role.DoesNotExist:
                return Response({'error': 'Operario role not configured in database.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            user.role = operario_role
            user.is_approved = True
        else:
            # backoffice - pending approval
            user.role = None
            user.is_approved = False

        user.set_unusable_password()
        user.save()

    tokens = _get_tokens_for_user(user)

    response_data = {
        'tokens': tokens,
        'user': UserSerializer(user).data,
    }

    if created and source == 'backoffice' and not user.is_approved:
        response_data['message'] = 'Your account is pending role assignment by an administrator.'
        response_data['status'] = 'pending_approval'

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Return current authenticated user's full profile."""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user_city(request):
    """Authenticated user updates their own city."""
    city_id = request.data.get('city_id')
    if not city_id:
        return Response({'error': 'city_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        city = City.objects.get(id=city_id)
    except City.DoesNotExist:
        return Response({'error': 'City not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Optionally: validate city belongs to user's country
    if request.user.country and city.country != request.user.country:
        return Response({'error': 'City does not belong to your country.'}, status=status.HTTP_400_BAD_REQUEST)

    request.user.city = city
    request.user.save(update_fields=['city'])
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    """List all users. Requires manage_users permission."""
    if not request.user.has_app_permission('manage_users'):
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    users = User.objects.select_related('role', 'country', 'city').prefetch_related('role__permissions').all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role(request, user_id):
    """
    POST /users/backoffice/<user_id>/assign-role/

    Admins can assign any role.
    Supervisors can only assign "operario".
    Cannot change own role.
    """
    requester = request.user

    # Cannot change own role
    if requester.id == user_id:
        return Response({'error': 'You cannot change your own role.'}, status=status.HTTP_400_BAD_REQUEST)

    # Must have at least assign_operario_role permission
    if not requester.has_app_permission('assign_operario_role'):
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = AssignRoleSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    role_id = serializer.validated_data['role_id']
    try:
        new_role = Role.objects.get(id=role_id)
    except Role.DoesNotExist:
        return Response({'error': 'Role not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Supervisors can only assign 'operario'
    if not requester.has_app_permission('assign_supervisor_role'):
        if new_role.name != 'operario':
            return Response(
                {'error': 'Supervisors can only assign the operario role.'},
                status=status.HTTP_403_FORBIDDEN
            )

    target_user.role = new_role
    target_user.is_approved = True
    target_user.save(update_fields=['role', 'is_approved'])

    return Response(UserSerializer(target_user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_countries(request):
    """Public endpoint - list all countries."""
    countries = Country.objects.all()
    serializer = CountrySerializer(countries, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_cities(request):
    """
    Public endpoint - list cities.
    Optional query param: ?country_id=<id> or ?country_code=<PE|MX>
    """
    cities = City.objects.select_related('country').all()
    country_id = request.query_params.get('country_id')
    country_code = request.query_params.get('country_code')

    if country_id:
        cities = cities.filter(country_id=country_id)
    elif country_code:
        cities = cities.filter(country__code=country_code.upper())

    serializer = CitySerializer(cities, many=True)
    return Response(serializer.data)
