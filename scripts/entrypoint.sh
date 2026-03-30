#!/bin/bash
set -e

echo ">>> Applying database migrations..."
python manage.py migrate --noinput

echo ">>> Collecting static files..."
python manage.py collectstatic --noinput

echo ">>> Seeding initial data..."
# Use a custom management command or call the seed service if needed.
# Since the seeder is already hooked into post_migrate in users.apps, 
# 'migrate' will trigger 'run_seeder' if migrations are running for the first time.
# But for explicit seeding, we can call a script.

# Starting the main application
echo ">>> Starting Gunicorn server..."
exec "$@"
