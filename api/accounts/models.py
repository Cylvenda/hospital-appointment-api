import uuid
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.auth.hashers import identify_hasher, make_password


# Custom User Manager
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


# Custom User Model
class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DOCTOR = "doctor", "Doctor"
        RECEPTIONIST = "receptionist", "Receptionist"
        PATIENT = "patient", "Patient"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    first_name = models.CharField(max_length=60, blank=True, null=True)
    middle_name = models.CharField(max_length=60, blank=True, null=True)
    last_name = models.CharField(max_length=60, blank=True, null=True)
    email = models.EmailField(unique=True, max_length=255)
    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for admin
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone"]

    objects = UserManager()

    def save(self, *args, **kwargs):
        # Guardrail: if a raw password is assigned directly, hash it before saving.
        if self.password and not self.password.startswith("!"):
            try:
                identify_hasher(self.password)
            except ValueError:
                self.password = make_password(self.password)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.role})"


# Doctor Profile
class DoctorProfile(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    license_number = models.CharField(max_length=50, unique=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"Dr. {self.user.full_name}"


# Doctor Categories (Many-to-Many)
class DoctorCategory(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE)
    category = models.ForeignKey(
        "appointments.IllnessCategory", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("doctor", "category")
        indexes = [
            models.Index(fields=["doctor"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.category}"


# Doctor Availability


class DoctorAvailability(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    doctor = models.ForeignKey(
        DoctorProfile, on_delete=models.CASCADE, related_name="availabilities"
    )
    day_of_week = models.IntegerField()  # 0=Monday, 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.doctor} - Day {self.day_of_week}"


# Region and District Models
class Region(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class District(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="districts")

    class Meta:
        unique_together = ("name", "region")

    def __str__(self):
        return f"{self.name} ({self.region.name})"


# Patient Profile
class PatientProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"
        OTHER = "Other", "Other"
        PREFER_NOT_TO_SAY = "Prefer not to say", "Prefer not to say"

    class EducationLevel(models.TextChoices):
        PRIMARY = "Primary", "Primary"
        SECONDARY = "Secondary", "Secondary"
        CERTIFICATE = "Certificate", "Certificate"
        DIPLOMA = "Diploma", "Diploma"
        BACHELOR = "Bachelor Degree", "Bachelor Degree"
        MASTER = "Master Degree", "Master Degree"
        PHD = "PhD", "PhD"
        OTHER = "Other", "Other"

    class MaritalStatus(models.TextChoices):
        SINGLE = "Single", "Single"
        MARRIED = "Married", "Married"
        DIVORCED = "Divorced", "Divorced"
        WIDOWED = "Widowed", "Widowed"
        SEPARATED = "Separated", "Separated"

    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="patient_profile"
    )
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True) # Kept for migration backwards-compatibility

    # Background Information
    education = models.CharField(max_length=50, choices=EducationLevel.choices, null=True, blank=True)
    country = models.CharField(max_length=100, default="Tanzania")
    religion = models.CharField(max_length=100, null=True, blank=True)
    tribe = models.CharField(max_length=100, null=True, blank=True)
    marital_status = models.CharField(max_length=20, choices=MaritalStatus.choices, null=True, blank=True)
    occupation = models.CharField(max_length=100, null=True, blank=True)

    # Residence Information
    veo_name = models.CharField(max_length=100, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients")
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name="patients")
    residence = models.CharField(max_length=255, null=True, blank=True)

    # Additional Medical Information
    blood_group = models.CharField(max_length=5, choices=BloodGroup.choices, null=True, blank=True)
    insurance_provider = models.CharField(max_length=100, null=True, blank=True)
    insurance_number = models.CharField(max_length=100, null=True, blank=True)
    nida_number = models.CharField(max_length=100, null=True, blank=True)
    
    is_profile_complete = models.BooleanField(default=False)

    def __str__(self):
        return self.user.full_name


class NextOfKin(models.Model):
    class Relationship(models.TextChoices):
        PARENT = "Parent", "Parent"
        SPOUSE = "Spouse", "Spouse"
        SIBLING = "Sibling", "Sibling"
        CHILD = "Child", "Child"
        FRIEND = "Friend", "Friend"
        GUARDIAN = "Guardian", "Guardian"
        RELATIVE = "Relative", "Relative"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    patient_profile = models.OneToOneField(
        PatientProfile, on_delete=models.CASCADE, related_name="next_of_kin"
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    relationship = models.CharField(max_length=20, choices=Relationship.choices)

    def __str__(self):
        return f"{self.name} ({self.relationship} of {self.patient_profile.user.full_name})"


class SystemSettings(models.Model):
    appointment_fee = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def __str__(self):
        return "Clinic Settings"
