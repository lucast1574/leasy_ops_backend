#!/bin/bash
set -e

echo "=== Leasy Ops Backend Startup ==="

echo "[1/7] Running migrations..."
python manage.py migrate --noinput

echo "[2/7] Seeding database..."
python manage.py seed_db

echo "[3/7] Seeding task types..."
python manage.py seed_task_types

echo "[4/7] Seeding geofences..."
python manage.py seed_geofences

echo "[5/7] Seeding districts..."
python manage.py seed_districts

echo "[6/7] Rebuilding supervisor assignments..."
python manage.py rebuild_assignments || echo "WARNING: rebuild_assignments failed (non-fatal)"

echo "[7/7] Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --log-level ${LOG_LEVEL:-info} \
    --access-logfile - \
    --error-logfile -
