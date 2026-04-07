#!/bin/bash
set -e

echo "=== Leasy Ops Backend Startup ==="

echo "[1/3] Running migrations..."
python manage.py migrate --noinput

echo "[2/3] Seeding database..."
python manage.py seed_db

echo "[3/3] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
