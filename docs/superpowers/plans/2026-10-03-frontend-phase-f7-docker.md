# Трапезная МДА — Frontend, фаза F7: Docker/nginx — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Упаковать SPA в контейнер: сборка статики и раздача через nginx с проксированием `/api` на бэкенд (same-origin, чтобы cookie работали), плюс сервис `frontend` в общем `docker-compose.yml`.

**Architecture:** Multi-stage образ (`node:24-alpine` → сборка; `nginx:alpine` → раздача). nginx отдаёт `index.html` для любых SPA-маршрутов и проксирует `/api/` на сервис `api`. Всё в одном compose на одном сервере.

**Tech Stack:** Docker, nginx, Node 24.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-frontend-design.md` (§15)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-frontend-phase-f6b-operator-service.md`

## Global Constraints

- Сайт и API — **same-origin** (nginx проксирует `/api`), иначе cookie `SameSite=Lax` не поедут и CORS не настроен.
- `proxy_pass` — **без** завершающего пути, чтобы `/api/v1/...` уходил на бэкенд без изменений.
- SPA-роутинг: `try_files $uri $uri/ /index.html`.
- Порт фронта на хосте — `8080` (API публикуется на `8000`, БД на `5432`).
- `.dockerignore` обязателен: не тащить `node_modules`/`dist` в контекст.

## Дерево файлов фазы F7

```
syte/
  Dockerfile            # NEW
  .dockerignore         # NEW
  nginx.conf            # NEW
server/
  docker-compose.yml    # MODIFY: сервис frontend
README.md               # MODIFY (корневой, если есть) или server/README.md
```

---

### Task 1: Образ фронтенда

**Files:**
- Create: `syte/Dockerfile`, `syte/.dockerignore`, `syte/nginx.conf`

- [ ] **Step 1: Написать `syte/Dockerfile`**

```dockerfile
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 2: Написать `syte/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Написать `syte/.dockerignore`**

```
node_modules
dist
.git
.gitignore
*.log
tests
scripts
```

- [ ] **Step 4: Проверить сборку образа (без запуска)**

```bash
cd syte
docker build -t mda_frontend:dev .
```
Expected: образ собирается, финальный слой — `nginx:alpine`.

- [ ] **Step 5: Commit**

```bash
git add syte/Dockerfile syte/.dockerignore syte/nginx.conf
git commit -m "feat(front): add nginx-based docker image"
```

---

### Task 2: Сервис `frontend` в compose + смоук

**Files:**
- Modify: `server/docker-compose.yml`
- Modify: `MDA_Base/README.md` (создать, если нет) или `server/README.md`

- [ ] **Step 1: Добавить сервис в `server/docker-compose.yml`**

```yaml
  frontend:
    build:
      context: ../syte
    container_name: mda_frontend
    restart: unless-stopped
    depends_on:
      - api
    ports:
      - "8080:80"
```

> Контекст сборки — `../syte` (compose лежит в `server/`). Сервисы `db` и `api` не менять.

- [ ] **Step 2: Собрать и поднять всё**

```bash
cd server
docker compose up -d --build
docker compose ps
```
Expected: три контейнера `mda_db`, `mda_api`, `mda_frontend` — Up.

- [ ] **Step 3: Смоук через nginx (same-origin)**

```bash
# 1) страница отдаётся
curl -s -o /dev/null -w "index HTTP %{http_code}\n" http://localhost:8080/
# 2) SPA-роут отдаёт index (не 404)
curl -s -o /dev/null -w "deep link HTTP %{http_code}\n" http://localhost:8080/operator/users
# 3) API проксируется
curl -s -o /dev/null -w "api HTTP %{http_code} (401 ожидаем без cookie)\n" http://localhost:8080/api/v1/auth/me
# 4) логин через прокси выставляет cookie
curl -s -c /tmp/fe.txt -o /dev/null -w "login HTTP %{http_code}\n" -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" -H "X-Device-Fingerprint: fe-smoke" \
  -d '{"login":"demo_op","password":"secret123"}'
# 5) с cookie — 200
curl -s -b /tmp/fe.txt -o /dev/null -w "me HTTP %{http_code}\n" \
  -H "X-Device-Fingerprint: fe-smoke" http://localhost:8080/api/v1/auth/me
```
Expected: `index 200`, `deep link 200`, `api 401`, `login 200`, `me 200`.

- [ ] **Step 4: Обновить документацию**

Добавить в `MDA_Base/README.md` раздел «Запуск всего стека»:

```markdown
## Запуск

```bash
cd server
docker compose up -d --build
```

- приложение — http://localhost:8080
- API (Swagger) — http://localhost:8000/docs
- первого оператора создать скриптом: `docker compose exec api python -m app.create_operator --login <логин>`
```

- [ ] **Step 5: Commit**

```bash
git add server/docker-compose.yml README.md
git commit -m "feat: add frontend service to docker compose"
```

---

## Self-Review (автора плана)

- **Покрытие спеки (F7):** §15 (multi-stage образ, nginx SPA-fallback, прокси `/api`, сервис в compose) — задачи 1–2.
- **Плейсхолдеров нет:** код и команды приведены.
- **Риск:** `proxy_pass http://api:8000;` без пути — иначе путь перезапишется; проверено смоуком (шаг 3).

## Итог по фронтенду

После F7 фронт закрывает все разделы спеки: вход и сессии, меню с модалкой дня, настройки и темы, админский список и «за человека», отчёты с Excel, разделы оператора, и полностью упакован в Docker вместе с бэкендом.
