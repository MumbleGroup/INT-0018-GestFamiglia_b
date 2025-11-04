import os
import sys
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
SETTINGS_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = Path(__file__).resolve().parent.parent
print("BASE_DIR:", BASE_DIR)

# Aggiunge la cartella apps al path
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-i$i!h!827s^*idfbaypy+f4pg!c=!=10)z^+&ib_#=z7g-fs48'

# SECURITY WARNING: don't run with debug turned on in production!
#DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
DEBUG = True

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '192.168.1.125',
    'mycrisisfamily.com',
    'www.mycrisisfamily.com'
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'django_extensions',
    
    # Local apps
    'apps.users',
    'apps.expenses',
    'apps.categories',
    'apps.reports',
    'apps.updates',
    'apps.contributions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',  # Compressione per performance
    'corsheaders.middleware.CorsMiddleware',
    'config.middleware.LogIPMiddleware',  # Log IP addresses
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Database configuration moved to environment-specific files
# (local.py, production.py, etc.)
DATABASES = {
    'updates_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'updates.sqlite3',
    }
}

DATABASE_ROUTERS = ['config.db_router.UpdatesDBRouter']


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'it-it'

TIME_ZONE = 'Europe/Rome'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# APK storage configuration
APK_ROOT = BASE_DIR / 'media' / 'apk_releases'


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 10,
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React
    "http://127.0.0.1:3000",  # React
    "http://localhost:9000",  # Quasar
    "http://127.0.0.1:9000",  # Quasar
    "http://localhost:9001",  # Quasar dev
    "http://127.0.0.1:9001",  # Quasar dev
    "http://192.168.1.125:9000",  # Quasar da rete locale
    "http://192.168.1.125:8000",  # Django API da rete locale
    "https://mycrisisfamily.com",  # Produzione
    "https://www.mycrisisfamily.com",  # Produzione con www
    "capacitor://localhost",  # Capacitor Android
    "https://localhost",  # Capacitor iOS
]

# Per debug temporaneo, permetti tutti gli origins
CORS_ALLOW_ALL_ORIGINS = True

# Permetti credenziali nelle richieste CORS
CORS_ALLOW_CREDENTIALS = True

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Cache settings - Disabilita completamente la cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disabilita la cache delle sessioni
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_SAVE_EVERY_REQUEST = False

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'SIGNING_KEY': SECRET_KEY,
    'ALGORITHM': 'HS256',
}

# Email configuration
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # For development
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # For production

# SMTP settings for Zoho Mail
EMAIL_HOST = 'smtp.zoho.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'no-reply@mycrisisfamily.com'  # Account no-reply dedicato
EMAIL_HOST_PASSWORD = 'Mumble100%'  # Password account no-reply

# Default email settings
DEFAULT_FROM_EMAIL = 'MyCrisisFamily <no-reply@mycrisisfamily.com>'
SERVER_EMAIL = 'no-reply@mycrisisfamily.com'  # For error notifications
EMAIL_SUBJECT_PREFIX = '[MyCrisisFamily] '

# Email timeout settings
EMAIL_TIMEOUT = 10  # Timeout in secondi per connessione SMTP

# Frontend URL settings
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://mycrisisfamily.com/app')
