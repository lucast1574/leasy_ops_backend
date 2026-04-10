#!/bin/bash
set -e

echo "=== Leasy Ops Backend Startup ==="

echo "[1/4] Running migrations..."
python manage.py migrate --noinput

echo "[2/4] Seeding database..."
python manage.py seed_db

echo "[3/4] Rebuilding supervisor assignments..."
python manage.py rebuild_assignments || echo "WARNING: rebuild_assignments failed (non-fatal)"

echo "[4/4] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
