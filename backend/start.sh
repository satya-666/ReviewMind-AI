#!/bin/sh
set -eu
python scripts/fetch_serving_model.py
python -m alembic -c backend/alembic.ini upgrade head
exec python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --no-access-log --no-proxy-headers
