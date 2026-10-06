# Трапезная МДА

Веб-приложение для управления трапезной: FastAPI-бэкенд, PostgreSQL и SPA-фронтенд,
упакованные в Docker Compose.

Наружу публикуется только фронтенд. API и база данных доступны исключительно во
внутренней сети compose (`frontend` → `api` → `db`), поэтому отдельные порты им не нужны.

## Локальный запуск

```bash
cd server
cp .env.example .env
docker compose up -d --build
```

- приложение — http://localhost:8080
- Swagger — http://localhost:8080/docs
- первый оператор: `docker compose exec api python -m app.create_operator --login <логин>`

---

# Развёртывание на сервере

Все команды выполняются **из каталога `server/`** — это корень Docker Compose.

## Этап 1. Подготовка сервера

1. Установить Docker Engine и плагин Compose — проверить: `docker compose version`.
2. В файрволе открыть только **80** и **443** (и SSH). Порты `8080` и `5432` наружу
   открывать не нужно: `8080` будет слушать только reverse-proxy, `5432` доступен
   лишь с самого сервера.
3. Получить код:

   ```bash
   git clone https://github.com/Mr-PASTER/mda-trapesnaia.git
   cd mda-trapesnaia/server
   ```

## Этап 2. Создать `.env` — что поменять

```bash
cp .env.example .env
nano .env
```

| Переменная | Что сделать |
|---|---|
| `POSTGRES_PASSWORD` | **Обязательно сменить.** Только URL-безопасные символы — пароль подставляется в строку подключения |
| `POSTGRES_USER`, `POSTGRES_DB` | Можно оставить `mda` |
| `SEED_OPERATOR_LOGIN`, `SEED_OPERATOR_PASSWORD` | **Задать** для первого оператора (пароль ≥ 8 символов). Оставить пустыми → создадите вручную на этапе 5 |
| `FRONTEND_BIND` | `127.0.0.1` — если перед фронтом стоит reverse-proxy (этап 6) |
| `FRONTEND_PORT` | По умолчанию `8080`; менять не обязательно |
| `TZ`, `TIMEZONE` | Часовой пояс сервера — влияет на дедлайны и ночное обслуживание |
| `SESSION_TTL_DAYS` | Срок жизни сессии, по умолчанию `7` |
| `SESSION_COOKIE_SECURE` | `true` — **после** настройки HTTPS (этап 6) |
| `DOCS_ENABLED` | `false` — закрыть `/docs`, `/redoc`, `/openapi.json` в проде |

Файл `.env` в `.gitignore`, поэтому секреты в репозиторий не попадут. Меняя `.env`,
применяйте изменения командой `docker compose up -d`.

## Этап 3. Запустить

```bash
docker compose up -d --build
docker compose ps            # db, api, frontend — должны быть healthy
docker compose logs -f api   # миграции и seed справочных данных
```

При старте `api` сам применяет миграции и создаёт справочные данные — строку настроек
и типы питания («Мясо», «Пост», «Рыба»). Отдельные команды для этого не нужны.

## Этап 4. Проверить

```bash
curl -I http://127.0.0.1:8080/                                              # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/v1/catalog/meal-types
# 401 — прокси до API работает, авторизация требуется
```

## Этап 5. Первый оператор

Если на этапе 2 вы задали `SEED_OPERATOR_LOGIN` и `SEED_OPERATOR_PASSWORD` — оператор
уже создан, входите с этими данными. Иначе создайте вручную:

```bash
docker compose exec api python -m app.create_operator --login root --full-name "Главный оператор"
```

Пароль запросится без эха. Открыть приложение: `http://<адрес-сервера>:8080`.

## Этап 6. HTTPS

1. Направить DNS-запись домена на сервер.
2. Поставить reverse-proxy с сертификатом. Пример для Caddy (сертификат получит сам):

   ```
   трапезная.example.org {
       reverse_proxy 127.0.0.1:8080
   }
   ```

3. В `.env` поменять и применить:

   ```
   FRONTEND_BIND=127.0.0.1
   SESSION_COOKIE_SECURE=true
   DOCS_ENABLED=false
   ```

   ```bash
   docker compose up -d
   ```

После этого фронт доступен только через HTTPS, cookie сессии идёт только по защищённому
соединению, а схема API закрыта.

## Этап 7. Бэкапы

Данные лежат в томе `mda_pgdata`. Ночной дамп по cron:

```bash
docker compose exec -T db pg_dump -U mda mda | gzip > /backup/mda-$(date +%F).sql.gz
```

Восстановление:

```bash
gunzip -c /backup/mda-2026-10-06.sql.gz | docker compose exec -T db psql -U mda -d mda
```

Копии стоит уносить с сервера (внешний диск или объектное хранилище).

## Этап 8. Обновление

```bash
cd mda-trapesnaia && git pull
cd server && docker compose up -d --build
```

`.env` при обновлении не затрагивается. Миграции применятся автоматически при старте.

## Ограничения

- **Один экземпляр `api`.** Миграции и обслуживание календаря выполняются при старте
  каждого процесса, а планировщик живёт внутри процесса uvicorn: не запускайте несколько
  реплик и не используйте `uvicorn --workers`.
- Пароль БД задаётся при первой инициализации тома. Его смена в `.env` на уже созданном
  томе ни на что не повлияет — нужен новый том или `ALTER USER` внутри контейнера.

## Диагностика

- `api` не становится healthy → `docker compose logs api`. Чаще всего не поднялась `db`
  или неверный `DATABASE_URL`/`POSTGRES_PASSWORD`.
- Reverse-proxy отдаёт 502 → контейнер `api` не healthy (см. выше).
- После `docker compose down -v` данные БД теряются — `-v` удаляет том.
- Детали по локальной разработке, тестам и переменным — `server/README.md`.
