#!/bin/sh
set -eu

debug="$(printf '%s' "${DJANGO_DEBUG:-0}" | tr '[:upper:]' '[:lower:]')"
case "$debug" in
  1|true|yes|on)
    ;;
  *)
    if [ -z "${DJANGO_SECRET_KEY:-}" ] || [ "${DJANGO_SECRET_KEY}" = "replace-with-a-long-random-secret" ]; then
      echo "Set DJANGO_SECRET_KEY to a unique production secret before starting." >&2
      exit 1
    fi
    if [ -z "${DATABASE_URL:-}" ]; then
      echo "DATABASE_URL must be configured in production; refusing to start on SQLite." >&2
      exit 1
    fi
    ;;
esac

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[vault] running database migrations..."
  python manage.py migrate --noinput
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "[vault] starting Gunicorn on :8000"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
