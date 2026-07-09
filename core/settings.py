import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def read_secret(var_name, default=None):
    """Helper to read secret file path from env or fallback to string."""
    file_path = os.environ.get(var_name)
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return default


def load_env_file(env_path):
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


load_env_file(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-ztl0+prq)bdb6ey2j*w^i##hyoeqjx_x2whgv$@g4*h(aud(mb"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "backend", "backend:8000", "*"]


CORS_ALLOW_CREDENTIALS = True

# Parse CORS origins from environment or use defaults
_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS")
CORS_ALLOWED_ORIGINS = (
    [origin.strip() for origin in _cors_origins.split(",")] if _cors_origins else
    ["http://localhost:3000", "http://127.0.0.1:3000", "http://frontend:3000"]
)

# Parse CSRF origins from environment or use defaults
_csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS")
CSRF_TRUSTED_ORIGINS = (
    [origin.strip() for origin in _csrf_origins.split(",")] if _csrf_origins else
    ["http://localhost:3000", "http://127.0.0.1:3000", "http://frontend:3000"]
)

AUTH_COOKIE = "access"
AUTH_COOKIE_ACCESS_MAX_AGE = 60 * 10  # 10 minutes
AUTH_COOKIE_REFRESH_MAX_AGE = 60 * 60 * 24  # 24 hrs
AUTH_COOKIE_SECURE = True  # In development must be true
AUTH_COOKIE_HTTP_ONLY = True
AUTH_COOKIE_PATH = "/"
AUTH_COOKIE_SAMESITE = "None"

DOMAIN = os.getenv("DOMAIN")
SITE_NAME = os.getenv("SITE_NAME")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third parties
    "drf_spectacular",
    "djoser",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # local apps
    "api.accounts",
    "api.appointments",
    "api.notifications",
    "api.consultations",
    "api.medical_records",
    "api.prescriptions",
    "api.laboratory",
    "api.billing",
    "api.pharmacy",
    "api.health_education",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "api.accounts.middleware.ProfileCompletionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases


USE_SQLITE = env_bool("USE_SQLITE", default=not bool(os.getenv("DATABASE_URL")))

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "example"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": read_secret("DB_PASSWORD_FILE", "cylvenda"),
            "HOST": os.environ.get("DB_HOST", "db"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    # {
    #     'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    # },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.accounts.authentication.CustomJWTAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOW_CREDENTIALS = True


CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "x-csrftoken",
]


# ─── Authentication ───────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "api.accounts.backends.EmailBackend",
]

DJOSER = {
    "LOGIN_FIELD": "email",
    "SEND_ACTIVATION_EMAIL": True,
    "ACTIVATION_URL": "activate/{uid}/{token}",
    "PASSWORD_RESET_CONFIRM_URL": "reset/{uid}/{token}",
    "SERIALIZERS": {
        "activation": "djoser.serializers.ActivationSerializer",
        "user": "api.accounts.serializers.CustomUserSerializer",
        "current_user": "api.accounts.serializers.CustomUserSerializer",
    },
    "EMAIL": {
        "activation": "api.accounts.email.CustomActivationEmail",
        "confirmation": "api.accounts.email.CustomConfirmationEmail",
        "password_reset": "api.accounts.email.CustomPasswordResetEmail",
        "password_changed_confirmation": "api.accounts.email.CustomPasswordChangedConfirmationEmail",
    },
    "EMAIL_FRONTEND_DOMAIN": "localhost:3000",
    "EMAIL_FRONTEND_PROTOCOL": "http",
    "EMAIL_FRONTEND_SITE_NAME": "Digital Patient Pre-Registration and Appointment Management System",
}

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
if not EMAIL_BACKEND:
    if DEBUG and (not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD):
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    else:
        EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
DEFAULT_FROM_EMAIL = (
    os.getenv("DEFAULT_FROM_EMAIL", "").strip()
    or EMAIL_HOST_USER
    or "webmaster@localhost"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ─── DRF Spectacular ─────────────────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "Digital Patient Pre-Registration and Appointment Management System API",
    "DESCRIPTION": "API for managing patient appointments, scheduling, and healthcare services.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {
        "name": "Cylvenda Dev",
        "email": "brayanmlawa0917@gmail.com",
    },
    "SERVE_INCLUDE_SCHEMA": False,
}
