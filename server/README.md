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

`tests/conftest.py` использует `TEST_DATABASE_URL`; по умолчанию —
`postgresql+asyncpg://mda:mda@127.0.0.1:5432/mda_test`. Берите `127.0.0.1`, а не
`localhost`: порт БД опубликован только на IPv4-loopback, а `localhost` сначала идёт
в `::1` и теряет ~2 с на каждом подключении.

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

Запускается автоматически при старте контейнера `api` — см. `docker/entrypoint.sh`.
Идемпотентно создаёт строку настроек и типы питания («Мясо», «Пост», «Рыба»).

Вручную (например, локально без Docker):

```bash
cd server
uv run python -m app.seed
```

Оператор создаётся **только если заданы обе** переменные `SEED_OPERATOR_LOGIN` и
`SEED_OPERATOR_PASSWORD` (пароль не короче 8 символов) и оператора ещё нет. Пароля
по умолчанию нет. Гибче — `app.create_operator` выше.

## Проверка через `/docs` (Swagger UI)

Открывается по адресу <http://localhost:8080/docs> (фронтенд проксирует схему на API;
в проде закрывается переменной `DOCS_ENABLED=false`).

1. `POST /api/v1/auth/login` → укажи заголовок `X-Device-Fingerprint` (любая строка,
   но далее используй ту же) и тело `{"login": "...", "password": "..."}`.
   В ответе — данные пользователя; токен больше не возвращается, а кладётся
   в HttpOnly-cookie сессии.
2. Защищённые эндпоинты вызываются сразу: браузер автоматически прикладывает cookie
   (тот же origin). Отдельная кнопка **Authorize** не нужна.
3. Не забудь заполнить заголовок `x-device-fingerprint` тем же значением, что при входе.
   Если отпечаток не совпадёт — `401`, и сессия сразу аннулируется (нужен повторный вход).

Выход: `POST /api/v1/auth/logout` очищает cookie сессии.

## Переменные окружения

Скопировать `.env.example` → `.env` и при необходимости поправить. Compose читает этот
файл сам; внутри контейнера приложение получает значения через `environment`.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `mda` | доступ к БД (пароль — URL-безопасный) |
| `FRONTEND_BIND` | `0.0.0.0` | адрес прослушивания фронта (`127.0.0.1` за reverse-proxy) |
| `FRONTEND_PORT` | `8080` | порт фронтенда на хосте |
| `DB_PORT` | `5432` | порт БД на loopback (для локальных тестов и psql) |
| `TZ` / `TIMEZONE` | `Europe/Moscow` | пояс процессов и планировщика |
| `SESSION_TTL_DAYS` | `7` | срок жизни сессии |
| `SESSION_COOKIE_SECURE` | `false` | `true` — обязательно при HTTPS |
| `DOCS_ENABLED` | `true` | `false` — закрыть `/docs`, `/redoc`, `/openapi.json` |
| `SEED_OPERATOR_LOGIN` / `SEED_OPERATOR_PASSWORD` | пусто | первый оператор (оба значения, пароль ≥ 8) |

> Смена `POSTGRES_PASSWORD` на уже созданном томе не меняет пароль в БД — нужен новый
> том или `ALTER USER` внутри контейнера.

## Запуск приложения (локально, без Docker)

```bash
cd server
uv run uvicorn app.main:app --reload
```

## Запуск через Docker (прод)

```bash
cd server
cp .env.example .env                # заполните секреты
FRONTEND_PORT=8080 docker compose up -d --build
```

Наружу публикуется только фронтенд; `api` доступен лишь во внутренней сети
compose (`frontend` → `api:8000`), а `db` — во внутренней сети и на loopback хоста
(для локальных тестов и `psql`); снаружи порт БД закрыт.

```bash
docker compose ps                   # статус и health services
docker compose logs -f api          # логи приложения
```

Миграции и seed справочных данных применяются автоматически при старте контейнера `api`.

## Развёртывание на сервере

```bash
git clone <repo> && cd <repo>/server
cp .env.example .env                # заполните секреты
docker compose up -d --build
```

Перед публикацией в интернет:

- **HTTPS.** Контейнеры отдают HTTP на `:8080`. Поставьте перед ними reverse-proxy
  (Caddy/Traefik/nginx) с сертификатом и проксируйте на `127.0.0.1:8080`.
- **`SESSION_COOKIE_SECURE=true`** — иначе cookie сессии уйдёт по HTTP.
- **`DOCS_ENABLED=false`** — чтобы `/docs`, `/redoc` и `/openapi.json` были недоступны.
- **Секреты** — в `.env` на сервере (файл в `.gitignore`), а не в `docker-compose.yml`.
- **Привязка к loopback.** Если перед `frontend` стоит reverse-proxy, поставьте в `.env`
  `FRONTEND_BIND=127.0.0.1` — тогда порт будет доступен только с самого сервера.

⚠️ **Один экземпляр.** Миграции и обслуживание календаря выполняются при старте каждого
процесса, а планировщик живёт внутри процесса uvicorn — не запускайте несколько реплик
`api` и не используйте `--workers N` без доработки.

### Бэкапы

Данные лежат в томе `mda_pgdata`. Пример ночного дампа (cron на хосте):

```bash
docker compose exec -T db pg_dump -U mda mda | gzip > /backup/mda-$(date +%F).sql.gz
```

Восстановление:

```bash
gunzip -c /backup/mda-2026-10-06.sql.gz | docker compose exec -T db psql -U mda -d mda
```

### Обновление

```bash
git pull && docker compose up -d --build
```
