from rest_framework import serializers
from .models import User, Role, Permission, Country, City, District, UserLocation, SupervisorAssignment


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'codename', 'description']


class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'permissions']


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'domain_suffix']


class CitySerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)

    class Meta:
        model = City
        fields = ['id', 'name', 'country', 'latitude', 'longitude']


class DistrictSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    country_code = serializers.CharField(source='city.country.code', read_only=True)

    class Meta:
        model = District
        fields = ['id', 'name', 'city_name', 'country_code', 'latitude', 'longitude']


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    country = CountrySerializer(read_only=True)
    city = CitySerializer(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'country', 'city', 'is_approved', 'registered_from',
            'profile_picture', 'is_staff', 'is_superuser', 'date_joined',
            'permissions',
        ]

    def get_permissions(self, obj):
        if obj.role and obj.role.permissions.exists():
            return list(obj.role.permissions.values_list('codename', flat=True))
        return []


class AssignRoleSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()

    def validate_role_id(self, value):
        if not Role.objects.filter(id=value).exists():
            raise serializers.ValidationError("Role not found.")
        return value


# ---------------------------------------------------------------------------
# Tracking / Monitoring
# ---------------------------------------------------------------------------

class UserLocationSerializer(serializers.ModelSerializer):
    """Compact location payload returned by the tracking endpoint."""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    profile_picture = serializers.CharField(source='user.profile_picture', read_only=True, allow_blank=True)
    role_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    country_code = serializers.SerializerMethodField()

    class Meta:
        model = UserLocation
        fields = [
            'user_id', 'first_name', 'last_name', 'email',
            'profile_picture', 'role_name', 'city_name', 'country_code',
            'latitude', 'longitude', 'updated_at',
        ]

    def get_role_name(self, obj):
        return obj.user.role.name if obj.user.role else None

    def get_city_name(self, obj):
        return obj.user.city.name if obj.user.city else None

    def get_country_code(self, obj):
        return obj.user.country.code if obj.user.country else None


class SupervisorAssignmentSerializer(serializers.ModelSerializer):
    operario = UserSerializer(read_only=True)

    class Meta:
        model = SupervisorAssignment
        fields = ['id', 'operario', 'is_adopted', 'created_at']
