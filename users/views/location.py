"""
Live GPS location reporting for authenticated users.

Upserts `UserLocation`, snaps to the nearest `City` with coordinates, and
rebuilds supervisor assignments when an operario's city changes.
"""
import math
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import City, UserLocation
from ..serializers import UserSerializer, CitySerializer
from ._assignments import _rebuild_assignments_for_user

logger = logging.getLogger(__name__)


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
    try:
        UserLocation.objects.update_or_create(
            user=request.user,
            defaults={'latitude': lat, 'longitude': lng},
        )
    except Exception as e:
        logger.error(f'[SET_LOCATION] UserLocation upsert failed: {e}')
        return Response({'error': f'Failed to save location: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
