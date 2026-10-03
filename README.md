# Трапезная МДА

Веб-приложение для управления трапезной: FastAPI-бэкенд, PostgreSQL и SPA-фронтенд,
упакованные в Docker Compose.

## Запуск

```bash
cd server
docker compose up -d --build
```

- приложение — http://localhost:8080
- API (Swagger) — http://localhost:8000/docs
- первого оператора создать скриптом: `docker compose exec api python -m app.create_operator --login <логин>`
