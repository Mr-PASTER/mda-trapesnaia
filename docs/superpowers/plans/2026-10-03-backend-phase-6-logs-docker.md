# Трапезная МДА — Backend, фаза 6: Logs & Docker — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать оператору просмотр аудит-логов за последние ~2 суток и автоматическую их очистку в 23:59, а также упаковать backend в Docker (`Dockerfile` + сервис `api` в `docker-compose.yml` с прогоном миграций на старте).

**Architecture:** Логи читаются из существующей таблицы `audit_logs` (пишется с фазы 2). Очистка «точкой сброса» встраивается в уже существующую задачу `jobs/maintenance.run_daily_maintenance` (23:59). Docker — один образ приложения рядом с сервисом `db` в одном compose на одном сервере.

**Tech Stack:** те же + Docker (python:3.12-slim, uv, uvicorn).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md` (§4 audit_logs, §10.5 logs, §12 очистка, §16 деплой)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-backend-phase-5-reports.md`

## Global Constraints

- Очистка: удалить `audit_logs`, где `created_at < (сегодня 00:00)` в поясе `Europe/Moscow` (лог, созданный в день `D`, живёт весь `D` и `D+1`, удаляется в 23:59 `D+1`).
- Просмотр логов — только `require_roles(UserRole.operator)`; сортировка от новых к старым; разумный лимит.
- Наружу не отдаём секретов; логи содержат `details` (jsonb), `action`, `entity_type`, `entity_id`, `user_id`, `created_at`.
- В контейнере БД доступна по хосту `db` (внутри compose), а не `localhost`.
- Миграции применяются на старте контейнера до запуска uvicorn.

## Дерево файлов фазы 6

```
server/
  app/
    repositories/audit.py            # MODIFY (list_logs, delete_older_than)
    services/audit.py                # MODIFY (list_logs, cleanup_older_than, today_reset_point)
    schemas/audit_log.py             # NEW
    api/v1/routers/operator/logs.py  # NEW
    api/v1/routers/operator/__init__.py  # MODIFY
    jobs/maintenance.py              # MODIFY (очистка логов)
  tests/
    test_logs_service.py             # NEW
    test_logs_api.py                 # NEW
  Dockerfile                         # NEW
  .dockerignore                      # NEW
  docker/entrypoint.sh               # NEW
  docker-compose.yml                 # MODIFY (сервис api)
  README.md                          # MODIFY (инструкции по Docker)
```

**Interfaces, которые фаза отдаёт дальше (финал backend):**
- `services/audit.py`: `list_logs(db, *, since=None, until=None, user_id=None, limit=1000)`, `cleanup_older_than(db, cutoff) -> int`, `today_reset_point(now=None) -> datetime`.

---

### Task 1: Логи — чтение, очистка, эндпоинт

**Files:**
- Modify: `server/app/repositories/audit.py`, `server/app/services/audit.py`, `server/app/jobs/maintenance.py`, `server/app/api/v1/routers/operator/__init__.py`
- Create: `server/app/schemas/audit_log.py`, `server/app/api/v1/routers/operator/logs.py`
- Create: `server/tests/test_logs_service.py`, `server/tests/test_logs_api.py`

**Interfaces:**
- Consumes: модель `AuditLog`, `SessionLocal`, `calendar.regenerate_horizon`, `settings.timezone`.
- Produces: `audit.list_logs`, `audit.cleanup_older_than`, `audit.today_reset_point`, эндпоинт `GET /api/v1/operator/logs`.

- [ ] **Step 1: Добавить в `app/repositories/audit.py`**

```python
from datetime import datetime

from sqlalchemy import delete, select

from app.models import AuditLog


async def list_logs(
    db, *, since: datetime | None = None, until: datetime | None = None,
    user_id=None, limit: int = 1000,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if since is not None:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditLog.created_at <= until)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return list((await db.execute(stmt)).scalars().all())


async def delete_older_than(db, cutoff: datetime) -> int:
    result = await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.flush()
    return int(result.rowcount or 0)
```

(Сохрани существующую функцию `create` и импорты.)

- [ ] **Step 2: Добавить в `app/services/audit.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


async def list_logs(
    db, *, since: datetime | None = None, until: datetime | None = None,
    user_id=None, limit: int = 1000,
) -> list:
    return await audit_repo.list_logs(
        db, since=since, until=until, user_id=user_id, limit=limit
    )


def today_reset_point(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(settings.timezone)
    now = now or datetime.now(tz)
    return datetime.combine(now.date(), datetime.min.time(), tzinfo=tz)


async def cleanup_older_than(db, cutoff: datetime) -> int:
    return await audit_repo.delete_older_than(db, cutoff)
```

> В `services/audit.py` уже есть импорт `audit_repo` (`from app.repositories import audit as audit_repo`) и функция `record`. Дополни их, не дублируй импорты.

- [ ] **Step 3: Обновить `app/jobs/maintenance.py`**

```python
from app.db.session import SessionLocal
from app.services import audit, calendar


async def run_daily_maintenance() -> None:
    async with SessionLocal() as db:
        await calendar.regenerate_horizon(db)
        await audit.cleanup_older_than(db, audit.today_reset_point())
        await db.commit()
```

- [ ] **Step 4: Написать `app/schemas/audit_log.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict | None
    created_at: datetime
```

- [ ] **Step 5: Написать `app/api/v1/routers/operator/logs.py`**

```python
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.audit_log import AuditLogOut
from app.services import audit

router = APIRouter(prefix="/logs", tags=["operator:logs"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[AuditLogOut])
async def list_logs(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_guard),
):
    return await audit.list_logs(db, since=from_, until=to, user_id=user_id, limit=limit)
```

- [ ] **Step 6: Обновить `app/api/v1/routers/operator/__init__.py`** — добавить `logs`:

```python
from app.api.v1.routers.operator import (
    days, halls, logs, meal_types, schedule_rules, settings, users,
)

operator_router = APIRouter(prefix="/operator")
operator_router.include_router(halls.router)
operator_router.include_router(meal_types.router)
operator_router.include_router(users.router)
operator_router.include_router(settings.router)
operator_router.include_router(schedule_rules.router)
operator_router.include_router(days.router)
operator_router.include_router(logs.router)
```

- [ ] **Step 7: Написать `tests/test_logs_service.py`**

```python
import datetime as dt
from zoneinfo import ZoneInfo

from app.services import audit

TZ = ZoneInfo("Europe/Moscow")


async def test_cleanup_removes_old_logs_only(db_session):
    old = dt.datetime(2020, 1, 1, 12, 0, tzinfo=TZ)
    recent = dt.datetime.now(TZ)
    await audit.record(db_session, actor_id=None, action="a", entity_type="hall")
    # создаём «старый» лог вручную
    from app.repositories import audit as repo

    await repo.create(db_session, user_id=None, action="old", entity_type="hall",
                      entity_id=None, details=None)
    await db_session.flush()

    # помечаем первый лог старым
    logs = await audit.list_logs(db_session)
    for log in logs:
        if log.action == "old":
            log.created_at = old
    await db_session.flush()

    cutoff = dt.datetime.combine(dt.date.today(), dt.time.min, tzinfo=TZ)
    deleted = await audit.cleanup_older_than(db_session, cutoff)
    assert deleted == 1
    remaining = await audit.list_logs(db_session)
    assert all(log.action != "old" for log in remaining)
    assert any(log.action == "a" for log in remaining)


async def test_today_reset_point_is_midnight(db_session):
    now = dt.datetime(2026, 10, 3, 17, 30, tzinfo=TZ)
    assert audit.today_reset_point(now) == dt.datetime(2026, 10, 3, 0, 0, tzinfo=TZ)
```

- [ ] **Step 8: Написать `tests/test_logs_api.py`**

```python
import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def operator_headers(client, db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "root", "password": "rootpass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_logs_capture_actions(client, operator_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=operator_headers)
    assert r.status_code == 201

    r = await client.get("/api/v1/operator/logs", headers=operator_headers)
    assert r.status_code == 200
    actions = [(log["action"], log["entity_type"]) for log in r.json()]
    assert ("create", "hall") in actions


async def test_logs_forbidden_for_eater(client, db_session):
    u = User(login="ivan", password_hash=hash_password("p"), full_name="И", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "ivan", "password": "p"},
                          headers={"X-Device-Fingerprint": FP})
    headers = {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}
    assert (await client.get("/api/v1/operator/logs", headers=headers)).status_code == 403
```

- [ ] **Step 9: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b1" uv run pytest -v
```
Expected: весь набор PASS (61 + новые).

- [ ] **Step 10: Commit**

```bash
git add server/app server/tests/test_logs_service.py server/tests/test_logs_api.py
git commit -m "feat: add audit logs endpoint and cleanup"
```

---

### Task 2: Docker — образ и сервис `api`

**Files:**
- Create: `server/Dockerfile`, `server/.dockerignore`, `server/docker/entrypoint.sh`
- Modify: `server/docker-compose.yml`, `server/README.md`

**Interfaces:**
- Consumes: `pyproject.toml`, `uv.lock`, `alembic/`, `app/`.
- Produces: работающий сервис `api` в compose (миграции + uvicorn), доступный на `http://localhost:8000/health`.

- [ ] **Step 1: Написать `server/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.12.22

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
```

- [ ] **Step 2: Написать `server/docker/entrypoint.sh`**

```sh
#!/bin/sh
set -e
cd /app
uv run alembic upgrade head
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> Файл должен иметь LF-переносы строк (не CRLF), иначе `sh` в контейнере упадёт.

- [ ] **Step 3: Написать `server/.dockerignore`**

```
.venv
__pycache__
**/__pycache__
*.pyc
.pytest_cache
.ruff_cache
.env
.env.*
tests
docs
.git
.gitignore
```

- [ ] **Step 4: Добавить сервис `api` в `server/docker-compose.yml`**

```yaml
  api:
    build: .
    container_name: mda_api
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://mda:mda@db:5432/mda
      TZ: Europe/Moscow
      SESSION_TTL_DAYS: "7"
      SEED_OPERATOR_LOGIN: operator
      SEED_OPERATOR_PASSWORD: changeme
    ports:
      - "8000:8000"
```

> Оставь сервис `db` без изменений; добавь `api` в то же `services:`.

- [ ] **Step 5: Обновить `server/README.md`**

Добавить раздел «Запуск через Docker»:

```markdown
## Запуск через Docker (прод)

```bash
cd server
docker compose up -d --build        # поднимет db + api
docker compose logs -f api          # логи приложения
curl http://localhost:8000/health   # {"status":"ok"}
```

Миграции применяются автоматически при старте контейнера `api`.
```

- [ ] **Step 6: Проверить конфигурацию и собрать**

```bash
cd server
docker compose config
docker compose build api
```

- [ ] **Step 7: Дымовой тест**

```bash
cd server
docker compose up -d api
sleep 20
docker compose ps
curl http://localhost:8000/health
docker compose logs --tail=30 api
```
Ожидаем: `{"status":"ok"}`; `api` в статусе Up.

> Порт 8000 должен быть свободен. Если занят — сообщи и временно используй другой маппинг (`8001:8000`), затем верни. После проверки: `docker compose down` (сервис `db` можно оставить).

- [ ] **Step 8: Commit**

```bash
git add server/Dockerfile server/.dockerignore server/docker/entrypoint.sh server/docker-compose.yml server/README.md
git commit -m "feat: add Dockerfile and api service"
```

---

## Self-Review (автора плана)

- **Покрытие спеки:** §4 `audit_logs` (чтение) — Task 1; §10.5 `GET /operator/logs` — Task 1; §12 очистка «до сегодня 00:00» в 23:59 — Task 1; §16 Docker (образ + сервис `api`) — Task 2.
- **Изоляция волн:** Task 1 (код логики) и Task 2 (Docker/инфра) не пересекаются по файлам → запускаются параллельно.
- **Плейсхолдеров нет:** код и команды приведены.
- **Согласованность:** `list_logs`, `cleanup_older_than`, `today_reset_point`, `AuditLogOut` — одинаковы в репозитории, сервисе, роутере и тестах.
- **Риск:** CRLF в `entrypoint.sh` сломает запуск — в плане явное требование LF.

## Итог по backend

После фазы 6 бэкенд покрывает все разделы спеки: аутентификация, справочники и панель оператора, расписание и генерация календаря, заявки/дедлайн/резерв/конкурентность, отчёты бухгалтера, аудит-логи, Docker-упаковка.
