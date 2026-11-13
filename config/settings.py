"""
Project settings.

Anything secret or environment-specific is read from environment variables
with a safe development default, so the same file works on your laptop and
on a server.
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets the VERCEL environment variable on its servers, so this is True
# only when the code is running there.
ON_VERCEL = bool(os.environ.get("VERCEL"))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-key-change-before-deploying")
# DEBUG shows detailed error pages: on by default on your computer, off on Vercel.
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"

# Hosts allowed to serve the site. ".vercel.app" covers every Vercel address;
# add your own domain later through the DJANGO_ALLOWED_HOSTS variable.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".vercel.app"]
ALLOWED_HOSTS += [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

# Needed for login and admin forms to work over HTTPS behind Vercel's proxy.
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]
CSRF_TRUSTED_ORIGINS += [
    f"https://{h}" for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tree.apps.TreeConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

# --- Database -------------------------------------------------------------
# SQLite on your computer. When a DATABASE_URL environment variable exists
# (Vercel creates it when you add a Postgres database), PostgreSQL is used
# instead. No code changes are needed to switch.
if os.environ.get("DATABASE_URL"):
    _db = urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db.path.lstrip("/"),
            "USER": unquote(_db.username or ""),
            "PASSWORD": unquote(_db.password or ""),
            "HOST": _db.hostname,
            "PORT": _db.port or 5432,
            "OPTIONS": {"sslmode": parse_qs(_db.query).get("sslmode", ["require"])[0]},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# en-gb makes the admin show and accept dates as day/month/year.
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files = CSS/JS/images that ship with the code.
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files = files uploaded by users (member photos).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Photo storage --------------------------------------------------------
# On your computer, photos are saved in the media/ folder. Vercel has no
# permanent disk, so there photos must go to an S3-compatible bucket (AWS S3,
# Cloudflare R2, Supabase Storage, ...). Setting AWS_STORAGE_BUCKET_NAME
# switches uploads to the bucket; the other AWS_* variables say where it is.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or None
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME") or None
    AWS_S3_FILE_OVERWRITE = False  # never replace a photo that has the same name

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
