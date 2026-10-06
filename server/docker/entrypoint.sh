#!/bin/sh
set -e
cd /app
# Зависимости уже установлены на этапе сборки образа (uv sync --no-dev) —
# запускаем бинарники напрямую, без повторной синхронизации и без сети.
/app/.venv/bin/alembic upgrade head
# Справочные данные (настройки + типы питания) — идемпотентно, на каждом старте.
/app/.venv/bin/python -m app.seed
exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
