from rest_framework import serializers
from .models import TaskType, Task, TaskPhoto, TaskResult
from users.serializers import UserSerializer


class TaskTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskType
        fields = ['id', 'slug', 'name', 'icon', 'description']


class TaskPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskPhoto
        fields = ['id', 'label', 's3_key', 'tag', 'uploaded_at']


class TaskResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskResult
        fields = ['id', 'result_data', 'checklist_data', 'submitted_at']


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for task lists."""
    type = TaskTypeSerializer(read_only=True)
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'type', 'status', 'scheduled_date', 'start_time', 'end_time',
            'address', 'client_name', 'placa', 'marca', 'modelo',
            'started_at', 'completed_at', 'photo_count',
        ]

    def get_photo_count(self, obj):
        return obj.photos.count()


class TaskDetailSerializer(serializers.ModelSerializer):
    """Full serializer with all fields, photos, and result."""
    type = TaskTypeSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    assigned_by = UserSerializer(read_only=True)
    photos = TaskPhotoSerializer(many=True, read_only=True)
    result = TaskResultSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'type', 'status',
            'assigned_to', 'assigned_by',
            'scheduled_date', 'start_time', 'end_time',
            'address', 'latitude', 'longitude',
            'client_name', 'client_dni',
            'placa', 'marca', 'modelo', 'color', 'vehicle_type',
            'metadata', 'observations',
            'started_at', 'completed_at',
            'photos', 'result',
            'created_at', 'updated_at',
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    """For backoffice task creation."""
    type_slug = serializers.SlugRelatedField(
        slug_field='slug', queryset=TaskType.objects.all(), source='type'
    )
    assigned_to_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Task
        fields = [
            'type_slug', 'assigned_to_id',
            'scheduled_date', 'start_time', 'end_time',
            'address', 'latitude', 'longitude',
            'client_name', 'client_dni',
            'placa', 'marca', 'modelo', 'color', 'vehicle_type',
            'metadata', 'observations',
        ]

    def validate_assigned_to_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        if not user.role or user.role.name != 'operario':
            raise serializers.ValidationError("User must have 'operario' role.")
        return value

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assigned_to_id = validated_data.pop('assigned_to_id')
        validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
        validated_data['assigned_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskSubmitSerializer(serializers.Serializer):
    """For operario submitting task results."""
    result_data = serializers.JSONField(required=False, default=dict)
    checklist_data = serializers.JSONField(required=False, default=dict)
    observations = serializers.CharField(required=False, default='', allow_blank=True)
