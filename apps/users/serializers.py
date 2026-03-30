import random
import string
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role

User = get_user_model()

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']

class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.ReadOnlyField(source='role.name')
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'role', 'role_name', 'plain_password', 'is_active',
            'has_backoffice_access', 'has_mobile_access'
        ]

class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating users with auto-generated credentials.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role']

    def create(self, validated_data):
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        
        # Generate Username: first letter of name + last name (lowercase)
        # e.g. Lucas Santillan -> lsantillan
        base_username = f"{first_name[0]}{last_name}".lower().replace(" ", "")
        username = base_username
        
        # Ensure uniqueness
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        # Generate simple random password
        # e.g. leasy1234
        random_suffix = ''.join(random.choices(string.digits, k=4))
        password = f"leasy{random_suffix}"
        
        user = User.objects.create_user(
            username=username,
            password=password,
            **validated_data
        )
        
        # Store plain password for backoffice visibility as requested
        user.plain_password = password
        user.save()
        
        return user
