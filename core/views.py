from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from core.database.connection import db_service
import logging

logger = logging.getLogger(__name__)

class HealthCheckView(APIView):
    """
    Production health check endpoint.
    Verifies database connectivity and basic app state.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        db_healthy = db_service.check_health()
        
        if not db_healthy:
            return Response(
                {"status": "unhealthy", "checks": {"database": "fail"}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        return Response({
            "status": "healthy",
            "checks": {
                "database": "pass",
                "app": "running"
            }
        })
