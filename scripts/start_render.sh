#!/bin/sh
set -eu

# Render Free no ofrece pre-deploy: estas operaciones son idempotentes.
: "${PORT:?Render debe proporcionar PORT}"
: "${APP_ENV:?Configurar APP_ENV}"
if [ "$APP_ENV" != "production" ]; then
  echo "APP_ENV debe ser production." >&2
  exit 1
fi
python -c 'from app.config import get_settings; get_settings()'
python -m alembic upgrade head
python -m app.seed
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --no-access-log
