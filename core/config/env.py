import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, "sqlite:///db.sqlite3"),
    SECRET_KEY=(str, "django-insecure-default-key"),
    CORS_ALLOWED_ORIGINS=(list, []),
    GOOGLE_CLIENT_ID=(str, ""),
    GOOGLE_CLIENT_SECRET=(str, ""),
    GOOGLE_AUTH_ALLOWED_DOMAINS=(list, ["leasyauto.com", "floty.mx"]),
    DB_SSLMODE=(str, "disable"),
    DB_SSLROOTCERT=(str, ""),
)

# Read environment variables
environ.Env.read_env(BASE_DIR / '.env')
