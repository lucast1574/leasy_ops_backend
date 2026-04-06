import os
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer

User = get_user_model()

class GoogleAuthView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'No token provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client_id = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id')
            idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
            email = idinfo['email']
            
            allowed_domains = os.environ.get('GOOGLE_AUTH_ALLOWED_DOMAINS', 'leasyauto.com,floty.mx').split(',')
            domain = email.split('@')[1] if '@' in email else ''
            if domain not in [d.strip() for d in allowed_domains]:
                return Response({'error': 'Dominio no permitido'}, status=status.HTTP_403_FORBIDDEN)

            user, created = User.objects.get_or_create(email=email, defaults={
                'username': email,
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'is_approved': False, # Require approval by default
                'has_backoffice_access': False
            })

            if not user.is_approved:
                return Response({'error': 'Pendiente de aprobación en el Backoffice'}, status=status.HTTP_403_FORBIDDEN)

            refresh = RefreshToken.for_user(user)
            return Response({
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            })
            
        except ValueError as e:
            return Response({'error': 'Token inválido', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    if not request.user.has_backoffice_access:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    users = User.objects.all().order_by('-date_joined')
    return Response(UserSerializer(users, many=True).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_approval(request, user_id):
    if not request.user.has_backoffice_access:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    try:
        user = User.objects.get(id=user_id)
        # Prevent self-deactivation if needed, but keeping it simple for now
        if user == request.user:
            return Response({'error': 'No puedes cambiar tu propio estado'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_approved = not user.is_approved
        user.save()
        return Response(UserSerializer(user).data)
    except User.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
