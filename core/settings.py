"""
Django settings for core project.
"""

import os
import socket
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# Security and environment
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
DJANGO_SECRET_KEY = (os.getenv("DJANGO_SECRET_KEY") or "").strip()
if not DJANGO_SECRET_KEY:
    if DEBUG:
        DJANGO_SECRET_KEY = "django-insecure-dev-only-change-me"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG=False")
SECRET_KEY = DJANGO_SECRET_KEY

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "corsheaders",
    "products",
    "orders",
    "users",
    "cart",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.LoginRateLimitMiddleware",
    "core.middleware.SlowQueryLoggingMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
# Keep CONN_MAX_AGE modest with PgBouncer transaction pooling.
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "60"))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
DB_KEEPALIVES_IDLE = int(os.getenv("DB_KEEPALIVES_IDLE", "30"))
DB_KEEPALIVES_INTERVAL = int(os.getenv("DB_KEEPALIVES_INTERVAL", "10"))
DB_KEEPALIVES_COUNT = int(os.getenv("DB_KEEPALIVES_COUNT", "5"))
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")
DB_FORCE_IPV4 = os.getenv("DB_FORCE_IPV4", "false").lower() == "true"
DB_HOSTADDR = os.getenv("DB_HOSTADDR", "").strip()

DB_NAME = os.getenv("DB_NAME", "").strip()
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "").strip()
DB_HOST = os.getenv("DB_HOST", "").strip()
DB_PORT = os.getenv("DB_PORT", "5432").strip()

database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url and all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST]):
    database_url = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        f"?sslmode={DB_SSLMODE}"
    )

if database_url:
    default_db = dj_database_url.parse(
        database_url,
        conn_max_age=DB_CONN_MAX_AGE,
        ssl_require=DB_SSLMODE in {"require", "verify-ca", "verify-full"},
    )
else:
    default_db = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
    }

if default_db.get("ENGINE") == "django.db.backends.postgresql":
    db_options = default_db.setdefault("OPTIONS", {})
    db_options.setdefault("sslmode", DB_SSLMODE)
    db_options.setdefault("connect_timeout", DB_CONNECT_TIMEOUT)
    db_options.setdefault("keepalives", 1)
    db_options.setdefault("keepalives_idle", DB_KEEPALIVES_IDLE)
    db_options.setdefault("keepalives_interval", DB_KEEPALIVES_INTERVAL)
    db_options.setdefault("keepalives_count", DB_KEEPALIVES_COUNT)

    if DB_HOSTADDR:
        db_options["hostaddr"] = DB_HOSTADDR
    elif DB_FORCE_IPV4 and default_db.get("HOST"):
        try:
            ipv4_results = socket.getaddrinfo(
                default_db["HOST"],
                default_db.get("PORT") or 5432,
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
            if ipv4_results:
                db_options.setdefault("hostaddr", ipv4_results[0][4][0])
        except OSError:
            pass

    default_db["CONN_HEALTH_CHECKS"] = True

DATABASES = {"default": default_db}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static/media
STATIC_URL = os.getenv("STATIC_URL", "/static/")
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = os.getenv("MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / "media"


# Caching / sessions
CACHE_TIMEOUT = int(os.getenv("CACHE_TIMEOUT", "120"))
REDIS_URL = (os.getenv("REDIS_URL") or "").strip()

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
            },
            "TIMEOUT": CACHE_TIMEOUT,
            "KEY_PREFIX": "thathwamasi",
        }
    }
elif DEBUG:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "thathwamasi-cache-local",
            "TIMEOUT": CACHE_TIMEOUT,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(BASE_DIR / ".cache"),
            "TIMEOUT": CACHE_TIMEOUT,
        }
    }

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"


# DRF
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "cart_add": os.getenv("THROTTLE_CART_ADD", "60/minute"),
    },
}


# Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL or "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = int(os.getenv("CELERY_BROKER_CONNECTION_MAX_RETRIES", "100"))
CELERY_BROKER_POOL_LIMIT = int(os.getenv("CELERY_BROKER_POOL_LIMIT", "20"))
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_TASK_DEFAULT_RETRY_DELAY = int(os.getenv("CELERY_TASK_DEFAULT_RETRY_DELAY", "5"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "90"))
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "120"))
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"


# App flags / integrations
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

CART_DEBUG_TOKEN = os.getenv("CART_DEBUG_TOKEN", "")
USE_LAYERED_ARCHITECTURE = os.getenv("USE_LAYERED_ARCHITECTURE", "true").lower() == "true"


# Proxy + security hardening
USE_X_FORWARDED_HOST = os.getenv("USE_X_FORWARDED_HOST", "true").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "true").lower() == "true"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "true").lower() == "true"

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "true").lower() == "true"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"


# Rate-limit / profiling knobs
RATE_LIMIT_ADMIN_LOGIN_MAX_ATTEMPTS = int(os.getenv("RATE_LIMIT_ADMIN_LOGIN_MAX_ATTEMPTS", "10"))
RATE_LIMIT_ADMIN_LOGIN_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_ADMIN_LOGIN_WINDOW_SECONDS", "60"))
SLOW_QUERY_MS = int(os.getenv("SLOW_QUERY_MS", "500"))


# Logging
LOG_DIR = BASE_DIR / "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "level": "INFO",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "level": "ERROR",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "app_file"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "core.slow_query": {
            "handlers": ["console", "app_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "app_file"],
        "level": "INFO",
    },
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
