#!/bin/bash
set -e

export FLASK_APP=run.py

echo ">>> Executando migrations..."
flask db upgrade

echo ">>> Populando dados iniciais (seed idempotente)..."
flask seed-db || echo "Seed já executado ou ignorado."

echo ">>> Iniciando gunicorn..."
exec gunicorn run:app \
  --workers=2 \
  --bind=0.0.0.0:${PORT:-8000} \
  --timeout=120 \
  --log-level=info \
  --access-logfile=- \
  --error-logfile=-
