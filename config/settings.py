"""
==========================================================================
 DJANGO SETTINGS - Konfigurasi Utama Project ERP
==========================================================================
 File pengaturan utama Django. Berisi semua konfigurasi:
 - SECRET_KEY, DEBUG, ALLOWED_HOSTS (keamanan)
 - INSTALLED_APPS (daftar modul yang aktif)
 - MIDDLEWARE (pipeline request/response)
 - DATABASES (koneksi database)
 - AUTH/STATIC/MEDIA settings
 - Template & layout configuration (dari config/template.py)

 Variabel environment dibaca dari file .env via python-dotenv.
 Dokumentasi lengkap: https://docs.djangoproject.com/en/5.0/ref/settings/
==========================================================================
"""
import os
import secrets
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from .template import TEMPLATE_CONFIG, THEME_LAYOUT_DIR, THEME_VARIABLES

load_dotenv()  # take environment variables from .env.

# Bangun path di dalam proyek seperti ini: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/


# SECURITY WARNING: keep the secret key used in production secret!
# Jika SECRET_KEY tidak diset di .env, generate random key (aman untuk development)
# Untuk PRODUKSI: WAJIB set SECRET_KEY di .env agar konsisten antar restart!
SECRET_KEY = os.environ.get("SECRET_KEY", default=secrets.token_urlsafe(50))


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", 'True').lower() in ['true', 'yes', '1']


# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("ALLOWED_HOSTS", "localhost,0.0.0.0,127.0.0.1").split(",")]

# CSRF Trusted Origins (Required for HTTPS/PythonAnywhere)
CSRF_TRUSTED_ORIGINS = [host.strip() for host in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1,http://localhost").split(",")]

# Current DJANGO_ENVIRONMENT
ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", default="local")

# Tandai apakah instalasi ini ADALAH Central License Server itu sendiri.
# Jika True, SaaSLicenseMiddleware akan di-bypass agar tidak loopback cek ke diri sendiri.
# Default True karena file settings.py ini HANYA ada di proyek CLS.
# Untuk SIMKOS/SERPTECH, mereka punya settings.py sendiri TANPA variabel ini.
IS_LICENSE_SERVER = os.environ.get("IS_LICENSE_SERVER", 'True').lower() in ['true', 'yes', '1']


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",    # Django REST Framework
    # Auth Module
    "auth.apps.AuthConfig",
    # Core (untuk custom template filters)
    "apps.core.apps.CoreConfig",
    # Dashboard & User Management
    "apps.dashboard",
    "apps.user_management",
    
    # License Apps
    "apps.licenses.apps.LicensesConfig",
    
    # Permission Management
    "apps.permission_management.apps.PermissionManagementConfig",
    
    # Modul Terintegrasi dari SIMKOS
    "apps.activity_log.apps.ActivityLogConfig",
    "apps.automation.apps.AutomationConfig",
    "apps.pengaturan.apps.PengaturanConfig",
    "apps.laporan.apps.LaporanConfig",
    "apps.ai_assistant.apps.AiAssistantConfig",
    "apps.pembelian.apps.PembelianConfig",
    
    # Original Apps
    "apps.pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.license_middleware.SaaSLicenseMiddleware",  # SaaS License Interceptor
    "django.middleware.gzip.GZipMiddleware",  # Compress responses for faster load
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "web_project.language_middleware.DefaultLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.double_submit_middleware.PreventDoubleSubmitMiddleware",
    "apps.activity_log.middleware.ActivityLogMiddleware",  # Audit trail
    "apps.core.cache_middleware.TenantCacheInvalidationMiddleware",
    "apps.core.maintenance_middleware.MaintenanceMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.language_code",
                "config.context_processors.my_setting",
                "config.context_processors.get_cookie",
                "config.context_processors.environment",
                "config.context_processors.export_templates",  # Export Excel/PDF templates
                "config.context_processors.pengaturan_perusahaan",  # Logo, favicon, system settings
                "apps.core.context_processors.user_permissions",  # RBAC permissions
            ],
            "libraries": {
                "theme": "web_project.template_tags.theme",
            },
            "builtins": [
                "django.templatetags.static",
                "web_project.template_tags.theme",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
# Set DATABASE_ENGINE=postgresql di .env untuk aktifkan PostgreSQL (production)
# Default: sqlite (development lokal — tidak perlu setup apapun)

_DB_ENGINE = os.environ.get("DATABASE_ENGINE", "sqlite").lower()

if _DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "cls_db"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "600")),
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# Enable i18n and set the list of supported languages
LANGUAGES = [
    ("en", _("English")),
    ("fr", _("French")),
    ("ar", _("Arabic")),
    ("de", _("German")),
    # Add more languages as needed
]

# Atur bahasa default
# ! Make sure you have cleared the browser cache after changing the default language
LANGUAGE_CODE = "en"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


STATICFILES_DIRS = [
    BASE_DIR / "src" / "assets",
    BASE_DIR / "static",
]

# Default URL on which Django application runs for specific environment
BASE_URL = os.environ.get("BASE_URL", default="http://127.0.0.1:8000")


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Template Settings
# ------------------------------------------------------------------------------

THEME_LAYOUT_DIR = THEME_LAYOUT_DIR
TEMPLATE_CONFIG = TEMPLATE_CONFIG
THEME_VARIABLES = THEME_VARIABLES

# Media Files (Upload)
# ------------------------------------------------------------------------------

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Email Settings
# ------------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""

# Login & Logout
# ------------------------------------------------------------------------------

LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"
LOGIN_REDIRECT_URL = "/"

# Session
# ------------------------------------------------------------------------------

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session expiry setiap request (cegah logout mendadak)

# Cookie name unik per aplikasi — WAJIB agar session & CSRF tidak saling tabrakan
# saat multiple Django app berjalan di localhost (port berbeda)
SESSION_COOKIE_NAME = "cls_sessionid"
CSRF_COOKIE_NAME = "cls_csrftoken"

# CSRF Failure Handler — Redirect ramah saat token kedaluwarsa (bukan error 403)
CSRF_FAILURE_VIEW = "auth.csrf_failure.csrf_failure_view"

# ==========================================================================
#  SECURITY HARDENING — Perlindungan dari Serangan Cyber
# ==========================================================================
# Pengaturan ini melindungi dari serangan umum:
# - XSS (Cross-Site Scripting): penyerang menyisipkan kode JavaScript jahat
# - Clickjacking: halaman dibingkai dalam iframe penyerang
# - MIME Sniffing: browser salah menebak tipe file
# - Man-in-the-Middle: penyadapan data di jaringan
# - CSRF (Cross-Site Request Forgery): permintaan palsu dari situs lain

# --- Pengaturan yang SELALU aktif (development & production) ---

# Cegah clickjacking: halaman tidak bisa di-embed dalam iframe situs lain
X_FRAME_OPTIONS = "DENY"

# Cegah browser menebak tipe konten (MIME sniffing attack)
SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Pengaturan KHUSUS PRODUCTION (hanya aktif saat DEBUG=False) ---
if not DEBUG:
    # HTTPS wajib: semua HTTP request di-redirect ke HTTPS
    SECURE_SSL_REDIRECT = True

    # HSTS (HTTP Strict Transport Security):
    # Browser akan SELALU menggunakan HTTPS selama 1 tahun
    # Bahkan jika user mengetik http:// → otomatis jadi https://
    SECURE_HSTS_SECONDS = 31536000       # 1 tahun dalam detik
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # Berlaku juga untuk subdomain
    SECURE_HSTS_PRELOAD = True             # Daftarkan ke HSTS preload list browser

    # Cookie hanya dikirim via HTTPS (cegah penyadapan session)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Proxy header: PythonAnywhere menggunakan reverse proxy
    # Header ini memberitahu Django bahwa request aslinya HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Referrer Policy: jangan kirim URL lengkap ke situs eksternal
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
else:
    # Development: cookie bisa dikirim tanpa HTTPS
    SESSION_COOKIE_SECURE = False

# Your stuff...
# ------------------------------------------------------------------------------

# Caching Configuration
# ------------------------------------------------------------------------------
# Set CACHE_BACKEND=redis di .env production agar cache konsisten lintas worker.
_CACHE_BACKEND = os.environ.get("CACHE_BACKEND", "locmem").lower()
if _CACHE_BACKEND == "redis":
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'cls-cache',
            'OPTIONS': {
                'MAX_ENTRIES': 1000,
                'CULL_FREQUENCY': 3,
            }
        }
    }

# Template Caching - Speeds up template rendering significantly
# Templates are compiled once and cached in memory
if not DEBUG:
    # Only enable in production to avoid caching during development
    TEMPLATES[0]['APP_DIRS'] = False
    TEMPLATES[0]['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]
# force reload
# force reload 2
