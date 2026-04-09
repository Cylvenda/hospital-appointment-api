from djoser.serializers import UserSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers
from api.appointments.models import IllnessCategory
from .models import DoctorCategory, DoctorProfile


class CustomUserSerializer(UserSerializer):
    is_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = (
            "uuid",
            "first_name",
            "last_name",
            "role",
            "email",
            "phone",
            "is_active",
            "is_staff",
            "is_admin",
        )
        read_only_fields = ("uuid",)


class AdminUserSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source="is_superuser", read_only=True)
    username = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "uuid",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "username",
            "role",
            "is_active",
            "is_staff",
            "is_admin",
        )

    def get_username(self, obj):
        return obj.email.split("@")[0] if obj.email else ""


class DoctorDirectorySerializer(serializers.ModelSerializer):
    user_uuid = serializers.UUIDField(source="user.uuid", read_only=True)
    name = serializers.CharField(source="user.full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    categories = serializers.SerializerMethodField()

    class Meta:
        model = DoctorProfile
        fields = (
            "uuid",
            "user_uuid",
            "name",
            "email",
            "phone",
            "license_number",
            "is_available",
            "categories",
        )

    def get_categories(self, obj):
        return [item.category.name for item in obj.doctorcategory_set.all()]


class AdminOverviewSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    total_doctors = serializers.IntegerField()
    total_receptionists = serializers.IntegerField()
    active_users = serializers.IntegerField()
    today_appointments = serializers.IntegerField()
    pending_appointments = serializers.IntegerField()
    approved_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()


class AdminSettingsSerializer(serializers.Serializer):
    clinic_name = serializers.CharField()
    support_email = serializers.CharField()
    clinic_hours = serializers.CharField()
    default_time_slot = serializers.CharField()
    secure_sessions = serializers.BooleanField()
    patient_confirmation_emails = serializers.BooleanField()


class AdminUserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = get_user_model()
        fields = (
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "role",
            "is_active",
        )

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "This field is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return get_user_model().objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AdminDoctorWriteSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(min_length=8, style={"input_type": "password"})
    license_number = serializers.CharField(max_length=50)
    is_available = serializers.BooleanField(default=True)
    category_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )

    def create(self, validated_data):
        category_uuids = validated_data.pop("category_uuids", [])
        password = validated_data.pop("password")
        user = get_user_model().objects.create_user(
            email=validated_data["email"],
            phone=validated_data["phone"],
            password=password,
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            role="doctor",
            is_staff=True,
            is_active=True,
        )
        doctor = DoctorProfile.objects.create(
            user=user,
            license_number=validated_data["license_number"],
            is_available=validated_data["is_available"],
        )

        if category_uuids:
            categories = IllnessCategory.objects.filter(uuid__in=category_uuids)
            DoctorCategory.objects.bulk_create(
                [DoctorCategory(doctor=doctor, category=category) for category in categories]
            )

        return doctor
