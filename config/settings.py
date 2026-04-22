"""
Django settings for config project.
"""

from pathlib import Path
import os
import logging
import dj_database_url
from dotenv import load_dotenv

# Carga variables de entorno local si existen
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

# SECURITY: SECRET_KEY must be set in environment variables for production.
# If not set, Django will refuse to start in production (DEBUG=False).
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('DEBUG') == 'True':
        SECRET_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
    else:
        raise ValueError('SECRET_KEY environment variable is required in production')

# DEBUG debe ser False en producción (AWS)
DEBUG = os.environ.get('DEBUG') == 'True'

# ALLOWED_HOSTS: dominios reales + health check interno del ALB
# Configurable via env var. Incluye ALB hostname para health checks.
ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'django-backend-alb-290863292.us-east-2.elb.amazonaws.com,api.opps-app.leasyauto.com,api.leasyauto.com,localhost,127.0.0.1'
).split(',')

# Security warning: ALLOWED_HOSTS = '*' is a security risk in production
if '*' in ALLOWED_HOSTS:
    logging.warning(
        'SECURITY WARNING: ALLOWED_HOSTS contains "*" which allows any host. '
        'This is a significant security risk in production. '
        'Set ALLOWED_HOSTS to specific domains in your environment.'
    )

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'users',
    'tasks',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database configuration
# Por defecto usa SQLite, pero si existe DATABASE_URL (RDS), usa esa.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.environ.get('DATABASE_URL'):
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=False)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/min',
        'user': '100/min',
    },
}

# Configuración de CORS para el Frontend
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://localhost:5173,https://opps-app.leasyauto.com'
).split(',')

# JWT token lifetime — long-lived for internal app (Google OAuth handles auth security)
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=365),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=365),
    'ROTATE_REFRESH_TOKENS': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CSRF Trusted Origins (required for Django 4+ with HTTPS cross-origin requests)
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'https://opps-app.leasyauto.com'
).split(',')

# Para que las cookies funcionen tras el Load Balancer
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# -----------------------------------------------------------------------
# Security headers
# -----------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True

if not DEBUG:
    # SSL redirect is handled by the ALB listener rules, not Django.
    # Django sits behind the ALB and only receives plain HTTP traffic
    # internally, so SECURE_SSL_REDIRECT must stay off — otherwise the
    # ELB health checker (which hits /health/ over HTTP without
    # X-Forwarded-Proto) gets a 301 and the task is marked unhealthy.
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
