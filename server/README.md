# Трапезная МДА — Backend

FastAPI + PostgreSQL. См. спеку: `../docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md`.

## Требования
- Docker Desktop (запущенный демон)
- `uv` (уже установлен)
- Python 3.12 (управляется `uv`, файл `.python-version`)

## Поднять базу данных

```bash
cd server
docker compose up -d db
docker compose ps        # дождаться healthy
```

Создадутся БД `mda` и `mda_test` (вторая — из `docker/initdb/01-create-test-db.sql`).

## Установить зависимости

```bash
cd server
uv sync
```

## Миграции

```bash
cd server
uv run alembic upgrade head          # основная БД
```

## Тесты

```bash
cd server
uv run pytest -v
```

`tests/conftest.py` использует `TEST_DATABASE_URL` (по умолчанию `mda_test`).

## Seed (первичный оператор, типы питания, настройки)

```bash
cd server
uv run python -m app.seed
```

Логин/пароль оператора берутся из `SEED_OPERATOR_LOGIN` / `SEED_OPERATOR_PASSWORD`.

## Переменные окружения

Скопировать `.env.example` → `.env` и при необходимости поправить.

## Запуск приложения (локально, без Docker)

```bash
cd server
uv run uvicorn app.main:app --reload
```

## Запуск через Docker (прод)

```bash
cd server
docker compose up -d --build        # поднимет db + api
docker compose logs -f api          # логи приложения
curl http://localhost:8000/health   # {"status":"ok"}
```

Миграции применяются автоматически при старте контейнера `api`.
