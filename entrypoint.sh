#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."

while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME"; do
    sleep 2
done

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting Django..."

exec "$@"