#!/bin/sh
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Seeding database..."
python -m scripts.seed_data

echo "Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
