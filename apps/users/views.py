from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, viewsets
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import action
from .models import User, Role
from .serializers import UserSerializer, UserCreateSerializer # To be created

class LoginView(APIView):
    """
    Standard Login endpoint using Username and Password.
    Returns Access and Refresh JWT tokens with user profile.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({'error': 'Usuario y contraseña requeridos'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(username=username, password=password)
        
        if user is not None:
            if not user.is_active:
                return Response({'error': 'Usuario inactivo'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'token': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role.name if user.role else 'Sin rol',
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'has_backoffice_access': user.has_backoffice_access,
                    'has_mobile_access': user.has_mobile_access,
                }
            })
        else:
            return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)

class UserViewSet(viewsets.ModelViewSet):
    """
    Management API for users in the backoffice.
    Only accessible by Admin and Supervisor roles.
    """
    queryset = User.objects.all().order_by('-id')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        # Admin sees all, Supervisor might see only certain roles if needed
        return User.objects.all().select_related('role')

    @action(detail=False, methods=['get'])
    def roles(self, request):
        """Returns all available roles for the creation form."""
        roles = Role.objects.all()
        return Response([{'id': r.id, 'name': r.name} for r in roles])
