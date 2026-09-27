"""
Shop manager application configuration.

Business logic lives in domain services, not in this module. Environment-specific
values stay here (or in environment variables) so a future PostgreSQL / cloud
deployment can replace SQLite without rewriting the domain apps.
"""

from __future__ import annotations

import os
from pathlib import Path

from config.runtime import RuntimeConfig

# backend/ is the Django project root (manage.py lives here).
BASE_DIR = Path(__file__).resolve().parent.parent

RUNTIME = RuntimeConfig(BASE_DIR)

# Semantic version exposed by GET /api/v1/version/ so the desktop shell and
# future installers can detect which API they are talking to.
APPLICATION_NAME = "Shop Manager"
APPLICATION_VERSION = "1.0.0"
API_VERSION = "v1"
# Aliases used by health/version views and packaged launchers.
APPLICATION_NAME = APPLICATION_NAME
APPLICATION_VERSION = APPLICATION_VERSION
API_VERSION = API_VERSION


# The installed app gets a random key stored in the shop data folder.
SECRET_KEY = RUNTIME.secret_key()

# On for local development, off in the installed app (MM_PACKAGED=1).
DEBUG = RUNTIME.debug

# Tauri and the Vite dev server talk to Django on loopback. Hosts stay explicit
# so a future LAN/cloud backend can widen this without guessing.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "apps.core",
    "apps.products",
    "apps.inventory",
    "apps.vendors",
    "apps.customers",
    "apps.purchases",
    "apps.sales",
    "apps.payments",
    "apps.expenses",
    "apps.analytics",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.LoopbackOnlyMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# Shop data root: LocalAppData when packaged (MM_DATA_DIR), else backend/data.
SHOP_DATA_ROOT = RUNTIME.data_root()
_DATA_ROOT = SHOP_DATA_ROOT

# Built React app served by Django in the installed app (same origin as /api).
FRONTEND_DIST = RUNTIME.frontend_dist()

# SQLite is the Phase 1 system of record. WAL, foreign keys, and busy timeout
# are applied in apps.core.sqlite so the file remains durable on a desktop PC.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DATA_ROOT / "mm_electricals.sqlite3",
        "OPTIONS": {
            "timeout": 30,
        },
        "ATOMIC_REQUESTS": False,
    }
}

# pytest-django should never write into the live shop database file.
if os.environ.get("PYTEST_VERSION"):
    DATABASES["default"]["NAME"] = BASE_DIR / "data" / "test.sqlite3"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Product photos live next to the shop database.
MEDIA_ROOT = _DATA_ROOT / "media"
MEDIA_URL = "/media/"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# No CORS: in development Vite proxies /api and /media; in the installed app
# Django serves the UI itself, so the browser only ever talks to one origin.

# Public endpoints override permission_classes locally (health, version, auth).
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.CsrfExemptSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.core.permissions.IsAuthenticatedShopUser",
    ],
}

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12

# Backup service writes SQLite copies and CSV exports under this directory.
BACKUP_ROOT = SHOP_DATA_ROOT / "backups"
BACKUP_RETENTION_COUNT = 14

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "mm-electricals-analytics",
        "TIMEOUT": 60,
    }
}

# Default shop identity stored in ApplicationSettings (not scattered constants).
DEFAULT_SHOP_SETTINGS = {
    "shop_name": "",
    "address": "",
    "gstin": "",
    "phone": "",
    "invoice_prefix": "SH",
    "currency": "INR",
    "default_tax_inclusive": False,
    "low_stock_threshold": 5,
}

# The packaged launcher redirects stderr into logs/api.log, so this handler
# doubles as the production log file.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "timestamped": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "timestamped"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

