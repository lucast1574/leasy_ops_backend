from rest_framework import serializers
from .models import User, Role, Permission, Country, City


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
        fields = ['id', 'name', 'country']


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
