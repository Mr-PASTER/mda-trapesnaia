# Трапезная МДА

Веб-приложение для управления трапезной: FastAPI-бэкенд, PostgreSQL и SPA-фронтенд,
упакованные в Docker Compose.

## Запуск

```bash
cd server
cp .env.example .env        # при необходимости поправьте значения
docker compose up -d --build
```

- приложение — http://localhost:8080
- схема API (Swagger) — http://localhost:8080/docs (в проде закрывается `DOCS_ENABLED=false`)
- первый оператор: задайте `SEED_OPERATOR_LOGIN` и `SEED_OPERATOR_PASSWORD` в `.env`
  до первого старта либо создайте вручную:
  `docker compose exec api python -m app.create_operator --login <логин>`

Наружу публикуется только фронтенд. API и база данных доступны исключительно
во внутренней сети compose: `frontend` → `api` → `db`.

Развёртывание на сервере (HTTPS, бэкапы, настройки) — `server/README.md`.
