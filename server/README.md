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

## Первый оператор (главный администратор)

Отдельный безопасный скрипт: создаёт оператора, а существующему меняет пароль только
с явным флагом `--reset-password` (идемпотентно).

```bash
cd server

# интерактивно (пароль запросится без эха)
uv run python -m app.create_operator --login root --full-name "Главный оператор"

# или сразу с паролем
uv run python -m app.create_operator --login root --full-name "Главный оператор" --password 'S3cret!'

# сменить пароль/ФИО существующему оператору
uv run python -m app.create_operator --login root --reset-password
```

Внутри работающего контейнера:

```bash
cd server
docker compose exec api python -m app.create_operator --login root --full-name "Главный оператор"
```

> При запуске из Git Bash пути с ведущим `/` искажаются (MSYS) — команда выше этого избегает
> (`python` берётся из venv, добавленного в `PATH` образа).

Коды выхода: `0` — успех; `2` — некорректные данные; `3` — оператор уже есть (нужен `--reset-password`);
`4` — логин занят пользователем с другой ролью.

## Seed (базовые данные: типы питания и настройки)

```bash
cd server
uv run python -m app.seed
```

Идемпотентно создаёт строку настроек, типы питания («Мясо», «Пост», «Рыба») и — если
оператора ещё нет — оператора из `SEED_OPERATOR_LOGIN` / `SEED_OPERATOR_PASSWORD`.
Для выбора собственных учётных данных оператора используйте `app.create_operator` выше.

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
