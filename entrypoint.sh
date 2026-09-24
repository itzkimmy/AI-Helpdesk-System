#!/bin/sh
set -e

echo "Running database migrations..."
python -m flask db upgrade || {
    echo "Migration failed or database uninitialized. Running initial db setup..."
    python -m flask db init || true
    python -m flask db migrate -m "Initial schema" || true
    python -m flask db upgrade || true
}

echo "Seeding default data (if empty)..."
python -m flask seed || true

echo "Training ML models (if missing)..."
python -m flask train-models || true

echo "Starting application..."
exec "$@"
