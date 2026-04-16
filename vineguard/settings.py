INFLUX_TOKEN = "s6ZDX_S1cCzDRoeVW4-k4eizpPRLX8CYpb3tUVUZY12F80YoEEAtA76I1VBJzkw9CcfAUgqN1OAvuFiI8KnNeQ=="
INFLUX_HOST = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_ORG = "VINEGUARD SSH"
INFLUX_BUCKET = "nodo_vineguard_1"
GRAFANA_TOKEN = "tSeq4bQ1bYoWrEd3XiBAqT6eSJ-yzFysiSBBQmQJ086NV2cdsYSvHoYEuInRQg1s0hGujWlAuFvrug4RSKNa-g=="
TELEGRAM_TOKEN ="8796899155:AAHoSo2T5Fb8knEPOl66T3i1NbJ3OGhbgew"
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-key"
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
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

ROOT_URLCONF = "vineguard.urls"

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

WSGI_APPLICATION = "vineguard.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "it-it"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"