"""
Public catalog endpoints: countries, cities, districts, roles.

All are `AllowAny` — used by login screens and dropdowns before authentication.
"""
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..models import Country, City, District, Role
from ..serializers import CountrySerializer, CitySerializer, DistrictSerializer, RoleSerializer


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


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def list_districts(request):
    """
    List districts, optionally filtered by country_code, city_id, or search query.
    GET /api/v1/users/districts/?country_code=PE&q=san+borja
    """
    districts = District.objects.select_related('city', 'city__country').all()

    country_code = request.query_params.get('country_code')
    city_id = request.query_params.get('city_id')
    q = request.query_params.get('q', '').strip()

    if country_code:
        districts = districts.filter(city__country__code=country_code.upper())
    if city_id:
        districts = districts.filter(city_id=city_id)
    if q:
        districts = districts.filter(name__icontains=q)

    return Response(DistrictSerializer(districts, many=True).data)
