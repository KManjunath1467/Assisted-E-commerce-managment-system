#!/bin/sh
set -e

echo "Running Alembic migrations..."
alembic upgrade head

if [ "${SEED_DB}" = "true" ]; then
  echo "Seeding database..."
  python -m scripts.seed_data
else
  echo "Skipping seed (set SEED_DB=true to seed)."
fi

echo "Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
