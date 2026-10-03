# Трапезная МДА — Backend, фаза 1: Foundation & Auth — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поднять backend-скелет FastAPI с PostgreSQL, миграциями, моделью пользователей/сессий и рабочей аутентификацией по токену, привязанному к отпечатку устройства.

**Architecture:** Слоистый монолит FastAPI: `api` (роутеры) → `services` (логика) → `repositories`/`models` (БД). Async SQLAlchemy 2.0 + asyncpg, Alembic для миграций. Аутентификация — серверные сессии со случайным токеном (в БД хранится SHA-256 хеш), скользящий TTL 7 дней, привязка к отпечатку устройства.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0 (async), asyncpg, Alembic, argon2-cffi, uv, pytest, pytest-asyncio, httpx.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md`

## Global Constraints

- Python: `>=3.12`.
- Пакетный менеджер: `uv` (не pip/poetry). Зависимости — в `pyproject.toml`.
- Все PK — `UUID` (`uuid.uuid4`), кроме `app_settings.id` (фиксированный `1`).
- Все `created_at`/`updated_at` — `DateTime(timezone=True)`, `server_default=func.now()`; `updated_at` дополнительно `onupdate=func.now()`.
- Часовой пояс по умолчанию: `Europe/Moscow`.
- TTL сессии: **7 дней**, скользящий (`expires_at = now + 7d` при каждом запросе).
- Логин уникален, хранится в нижнем регистре.
- Наружу (в API) **никогда** не отдаём `password_hash`, `token_hash`, `device_fingerprint_hash`.
- Формат ошибок FastAPI по умолчанию: `{"detail": ...}`. Конфликт версий — `409` с `detail="record_changed"`.
- Префикс API: `/api/v1`.

## Дерево файлов фазы 1

```
server/
  pyproject.toml
  .env.example
  alembic.ini
  alembic/
    env.py
    script.py.mako
    versions/
  app/
    __init__.py
    main.py
    core/
      __init__.py
      config.py
      security.py
    db/
      __init__.py
      base.py
      session.py
    models/
      __init__.py
      enums.py
      meal_type.py
      user.py
      session.py
      app_settings.py
    schemas/
      __init__.py
      auth.py
      user.py
    repositories/
      __init__.py
      users.py
      sessions.py
    services/
      __init__.py
      auth.py
    api/
      __init__.py
      deps.py
      v1/
        __init__.py
        router.py
        routers/
          __init__.py
          auth.py
    seed.py
  tests/
    __init__.py
    conftest.py
    test_health.py
    test_security.py
    test_auth.py
    test_seed.py
```

**Interfaces (что производит эта фаза для следующих):**
- `app.db.session.get_db()` → `AsyncIterator[AsyncSession]` (FastAPI-зависимость).
- `app.api.deps.get_current_user(...)` → `User`; `require_roles(*roles)` → dependency-фабрика.
- `app.core.security`: `hash_password`, `verify_password`, `new_token`, `hash_token`, `hash_fingerprint`.
- Модели `User`, `UserRole`, `MealType`, `UserSession`, `AppSettings`.
- `app.services.auth`: `authenticate`, `create_session`, `resolve_session`, `revoke_session`.

---

### Task 1: Скаффолд проекта и health-эндпоинт

**Files:**
- Create: `server/pyproject.toml`
- Create: `server/.env.example`
- Create: `server/app/__init__.py`
- Create: `server/app/core/__init__.py`
- Create: `server/app/core/config.py`
- Create: `server/app/main.py`
- Test: `server/tests/__init__.py`, `server/tests/test_health.py`

- [ ] **Step 1: Создать `pyproject.toml`**

```toml
[project]
name = "mda-trapeznaya-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.8",
    "pydantic-settings>=2.4",
    "sqlalchemy[asyncio]>=2.0.32",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
    "argon2-cffi>=23.1",
    "apscheduler>=3.10",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
package = false
```

- [ ] **Step 2: Создать `.env.example`**

```dotenv
DATABASE_URL=postgresql+asyncpg://mda:mda@localhost:5432/mda
TZ=Europe/Moscow
SESSION_TTL_DAYS=7
```

- [ ] **Step 3: Написать `app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+asyncpg://mda:mda@localhost:5432/mda"
    timezone: str = "Europe/Moscow"
    session_ttl_days: int = 7

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")


settings = Settings()
```

- [ ] **Step 4: Написать `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Трапезная МДА API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Написать падающий тест `tests/test_health.py`**

```python
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 6: Установить зависимости и запустить тест**

Run: `cd server && uv sync && uv run pytest tests/test_health.py -v`
Expected: PASS (1 passed).

- [ ] **Step 7: Commit**

```bash
git add server/pyproject.toml server/.env.example server/app server/tests
git commit -m "chore: scaffold FastAPI backend with health endpoint"
```

---

### Task 2: Тестовая инфраструктура (conftest)

**Files:**
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_health.py` (модификация — перевести на фикстуру `client`)

**Interfaces:**
- Produces: фикстуры `client` (httpx AsyncClient), `db_session` (AsyncSession), схема тестовой БД создаётся из метаданных.

- [ ] **Step 1: Написать `tests/conftest.py`**

```python
> **ВАЖНО (исправлено при выполнении):** тестовый engine обязан быть с `poolclass=NullPool`
> (иначе asyncpg переиспользует соединение между разными event loop'ами и тесты падают с
> `attached to a different loop`), а фикстура `client` обязана **переопределять зависимость
> `get_db`** на тестовую сессию (иначе приложение ходит в основную БД `mda`, а не в `mda_test`).
> Также нужна autouse-фикстура, очищающая таблицы между тестами.

```python
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://mda:mda@localhost:5432/mda_test",
)

engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
TestSession = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _reset_data():
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db_session():
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    async def _override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
```
```

> Примечание: `Base` появится в Task 3. Этот шаг специально опережает модель — тест Task 2 начнёт проходить после Task 3. Для проверки самого conftest временно оставьте `Base` импорт; если запускаете до Task 3 — шаг пропустите и вернитесь к нему в Task 3, Step 5.

- [ ] **Step 2: Переписать `tests/test_health.py` на фикстуру `client`**

```python
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Запустить тесты**

Run: `cd server && uv run pytest tests/test_health.py -v`
Expected: PASS (после Task 3; до него возможен ImportError — см. примечание).

- [ ] **Step 4: Commit**

```bash
git add server/tests
git commit -m "test: add pytest fixtures for DB and HTTP client"
```

---

### Task 3: Ядро БД и модели первой фазы

**Files:**
- Create: `server/app/db/__init__.py`, `server/app/db/base.py`, `server/app/db/session.py`
- Create: `server/app/models/__init__.py`, `enums.py`, `meal_type.py`, `user.py`, `session.py`, `app_settings.py`
- Test: `server/tests/test_models.py`

**Interfaces:**
- Produces: `Base`, `get_db`, модели `MealType`, `User`, `UserSession`, `AppSettings`, enum `UserRole`.

- [ ] **Step 1: Написать `db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Написать `db/session.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Написать `models/enums.py`**

```python
import enum


class UserRole(str, enum.Enum):
    eater = "eater"
    admin = "admin"
    accountant = "accountant"
    operator = "operator"


class MealKind(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    snack = "snack"
    dinner = "dinner"
```

- [ ] **Step 4: Написать модели**

`models/meal_type.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MealType(Base):
    __tablename__ = "meal_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`models/user.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    default_meal_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meal_types.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`models/session.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_fingerprint_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`models/app_settings.py`:

```python
from datetime import datetime, time

from sqlalchemy import DateTime, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    generation_days: Mapped[int] = mapped_column(Integer, default=14)
    deadline_offset_days: Mapped[int] = mapped_column(Integer, default=2)
    deadline_time: Mapped[time] = mapped_column(Time, default=time(13, 0))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`models/__init__.py`:

```python
from app.models.app_settings import AppSettings
from app.models.enums import MealKind, UserRole
from app.models.meal_type import MealType
from app.models.session import UserSession
from app.models.user import User

__all__ = ["AppSettings", "MealKind", "MealType", "User", "UserRole", "UserSession"]
```

- [ ] **Step 5: Написать `tests/test_models.py`**

```python
import uuid

from app.models import MealType, User, UserRole


async def test_create_user_and_meal_type(db_session):
    mt = MealType(name="Мясо", sort_order=1)
    db_session.add(mt)
    await db_session.flush()

    user = User(
        login="ivan",
        password_hash="x",
        full_name="Иван",
        role=UserRole.eater,
        default_meal_type_id=mt.id,
    )
    db_session.add(user)
    await db_session.flush()

    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
```

- [ ] **Step 6: Запустить тесты**

Run: `cd server && uv run pytest -v`
Expected: PASS (health + models). Требуется запущенная тестовая БД `mda_test`.

- [ ] **Step 7: Commit**

```bash
git add server/app/db server/app/models server/tests/test_models.py
git commit -m "feat: add DB core and phase-1 models"
```

---

### Task 4: Alembic и первая миграция

**Files:**
- Create: `server/alembic.ini`, `server/alembic/env.py`, `server/alembic/script.py.mako`
- Create: `server/alembic/versions/<rev>_initial.py` (генерируется)

- [ ] **Step 1: Инициализировать Alembic**

Run: `cd server && uv run alembic init -t async alembic`
Expected: созданы `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, папка `versions/`.

- [ ] **Step 2: Правка `alembic/env.py` — подключить метаданные и URL**

В начале файла добавить:

```python
from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401  (регистрирует модели в метаданных)

config.set_main_option("sqlalchemy.url", settings.database_url)  # ИСПРАВЛЕНО: async-URL (asyncpg), НЕ sync_database_url
```

…и `target_metadata = Base.metadata`. Убедиться, что `run_migrations_online()` использует `config.get_main_option("sqlalchemy.url")` (async-шаблон это делает).

> **Исправлено при выполнении:** при async-шаблоне в `env.py` нужен **async-URL** (`settings.database_url`),
> иначе `async_engine_from_config` падает с "asyncio extension requires an async driver".
> В `downgrade()` миграции добавлена строка `sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)` —
> Postgres не удаляет enum вместе с таблицей, без этого цикл downgrade→upgrade падает.

- [ ] **Step 3: Сгенерировать миграцию**

Run: `cd server && uv run alembic revision --autogenerate -m "initial schema"`
Expected: новый файл в `alembic/versions/` с созданием `meal_types`, `users`, `sessions`, `app_settings`.

- [ ] **Step 4: Открыть файл миграции и проверить**

Проверь, что создаются все 4 таблицы, enum `user_role`, FK `users.default_meal_type_id → meal_types.id`, unique по `users.login`, `sessions.token_hash`. Если чего-то нет — поправить вручную.

- [ ] **Step 5: Применить и проверить**

Run: `cd server && uv run alembic upgrade head`
Expected: миграция применена без ошибок.

- [ ] **Step 6: Commit**

```bash
git add server/alembic.ini server/alembic
git commit -m "feat: add alembic with initial schema migration"
```

---

### Task 5: Утилиты безопасности

**Files:**
- Create: `server/app/core/security.py`
- Test: `server/tests/test_security.py`

**Interfaces:**
- Produces: `hash_password(str)->str`, `verify_password(hash,raw)->bool`, `new_token()->str`, `hash_token(str)->str`, `hash_fingerprint(str)->str`.

- [ ] **Step 1: Написать падающий тест `tests/test_security.py`**

```python
from app.core.security import (
    hash_fingerprint,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password(h, "secret123") is True
    assert verify_password(h, "wrong") is False


def test_token_is_random_and_hashed_deterministically():
    t1, t2 = new_token(), new_token()
    assert t1 != t2
    assert hash_token(t1) == hash_token(t1)
    assert len(hash_token(t1)) == 64


def test_fingerprint_hash_stable():
    assert hash_fingerprint("abc") == hash_fingerprint("abc")
    assert hash_fingerprint("abc") != hash_fingerprint("abd")
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd server && uv run pytest tests/test_security.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Написать `app/core/security.py`**

```python
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_fingerprint(fingerprint: str) -> str:
    return hashlib.sha256(fingerprint.encode()).hexdigest()
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd server && uv run pytest tests/test_security.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add server/app/core/security.py server/tests/test_security.py
git commit -m "feat: add security utilities (argon2, tokens, fingerprints)"
```

---

### Task 6: Репозитории и сервис аутентификации

**Files:**
- Create: `server/app/repositories/users.py`, `sessions.py`
- Create: `server/app/services/auth.py`
- Test: `server/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `security` из Task 5, модели из Task 3.
- Produces:
  - `repositories.users.get_by_login(db, login) -> User | None`
  - `repositories.users.get_by_id(db, user_id) -> User | None`
  - `repositories.sessions.create(db, ...) -> (UserSession, raw_token)`
  - `repositories.sessions.get_by_token_hash(db, hash) -> UserSession | None`
  - `services.auth.authenticate(db, login, password) -> User | None`
  - `services.auth.create_session(db, user, fingerprint) -> str`
  - `services.auth.resolve_session(db, raw_token, fingerprint) -> User | None` (с продлением и аннулированием при смене отпечатка)
  - `services.auth.revoke_session(db, raw_token) -> None`

- [ ] **Step 1: Написать `repositories/users.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_login(db: AsyncSession, login: str) -> User | None:
    result = await db.execute(select(User).where(User.login == login.lower().strip()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)
```

- [ ] **Step 2: Написать `repositories/sessions.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_fingerprint, hash_token, new_token
from app.models import UserSession


async def create(db: AsyncSession, user_id, fingerprint: str) -> tuple[UserSession, str]:
    raw = new_token()
    now = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user_id,
        token_hash=hash_token(raw),
        device_fingerprint_hash=hash_fingerprint(fingerprint),
        expires_at=now + timedelta(days=settings.session_ttl_days),
    )
    db.add(session)
    await db.flush()
    return session, raw


async def get_by_token_hash(db: AsyncSession, token_hash: str) -> UserSession | None:
    result = await db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 3: Написать падающий тест `tests/test_auth_service.py`**

```python
import pytest

from app.core.security import hash_password
from app.models import User, UserRole
from app.services import auth


@pytest.fixture
async def eater(db_session):
    user = User(
        login="ivan",
        password_hash=hash_password("secret123"),
        full_name="Иван",
        role=UserRole.eater,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_authenticate_ok_and_bad(db_session, eater):
    assert (await auth.authenticate(db_session, "IVAN", "secret123")).id == eater.id
    assert await auth.authenticate(db_session, "ivan", "wrong") is None
    assert await auth.authenticate(db_session, "nobody", "secret123") is None


async def test_session_roundtrip_and_fingerprint_mismatch(db_session, eater):
    token = await auth.create_session(db_session, eater, "dev-A")
    assert (await auth.resolve_session(db_session, token, "dev-A")).id == eater.id
    # другой отпечаток → сессия аннулируется, доступ закрыт
    assert await auth.resolve_session(db_session, token, "dev-B") is None
    # исходный отпечаток больше не работает (сессия отозвана)
    assert await auth.resolve_session(db_session, token, "dev-A") is None


async def test_revoke_session(db_session, eater):
    token = await auth.create_session(db_session, eater, "dev-A")
    await auth.revoke_session(db_session, token)
    assert await auth.resolve_session(db_session, token, "dev-A") is None
```

- [ ] **Step 4: Запустить — убедиться, что падает**

Run: `cd server && uv run pytest tests/test_auth_service.py -v`
Expected: FAIL (ImportError: services.auth).

- [ ] **Step 5: Написать `services/auth.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_fingerprint, hash_token, verify_password
from app.models import User, UserSession
from app.repositories import sessions as sessions_repo
from app.repositories import users as users_repo


async def authenticate(db: AsyncSession, login: str, password: str) -> User | None:
    user = await users_repo.get_by_login(db, login)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def create_session(db: AsyncSession, user: User, fingerprint: str) -> str:
    _, raw = await sessions_repo.create(db, user.id, fingerprint)
    return raw


async def resolve_session(
    db: AsyncSession, raw_token: str, fingerprint: str
) -> User | None:
    token_hash = hash_token(raw_token)
    session = await sessions_repo.get_by_token_hash(db, token_hash)
    if session is None:
        return None

    now = datetime.now(timezone.utc)

    if session.revoked_at is not None or session.expires_at <= now:
        return None

    if session.device_fingerprint_hash != hash_fingerprint(fingerprint):
        session.revoked_at = now
        await db.flush()
        return None

    user = await users_repo.get_by_id(db, session.user_id)
    if user is None or not user.is_active:
        return None

    # скользящее продление + отметка активности
    session.last_seen_at = now
    session.expires_at = now + timedelta(days=settings.session_ttl_days)
    await db.flush()
    return user


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    session = await sessions_repo.get_by_token_hash(db, hash_token(raw_token))
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        await db.flush()
```

- [ ] **Step 6: Запустить — убедиться, что проходит**

Run: `cd server && uv run pytest tests/test_auth_service.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories server/app/services server/tests/test_auth_service.py
git commit -m "feat: add auth repositories and session service"
```

---

### Task 7: HTTP-эндпоинты `/auth`

**Files:**
- Create: `server/app/schemas/auth.py`, `server/app/schemas/user.py`
- Create: `server/app/api/deps.py`
- Create: `server/app/api/v1/router.py`, `server/app/api/v1/routers/auth.py`
- Modify: `server/app/main.py` (подключить роутер)
- Test: `server/tests/test_auth.py`

**Interfaces:**
- Consumes: `services.auth`, `get_db`, модели, схемы.
- Produces: `get_current_user`, `require_roles(*roles)` для последующих фаз.

- [ ] **Step 1: Написать схемы**

`schemas/user.py`:

```python
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    login: str
    full_name: str
    role: UserRole
    is_active: bool
    default_meal_type_id: uuid.UUID | None
```

`schemas/auth.py`:

```python
from pydantic import BaseModel

from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    login: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut
```

- [ ] **Step 2: Написать `api/deps.py`**

```python
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import User, UserRole
from app.services import auth


async def get_current_user(
    authorization: str = Header(...),
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_auth_header")
    raw_token = authorization.removeprefix("Bearer ").strip()
    user = await auth.resolve_session(db, raw_token, x_device_fingerprint)
    # resolve_session мог отозвать сессию (несовпадение отпечатка) через flush;
    # коммитим и на пути отказа, иначе отзыв потеряется вместе с rollback.
    await db.commit()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    return user


def require_roles(*roles: UserRole) -> Callable:
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _dep
```

- [ ] **Step 3: Написать `api/v1/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserOut
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    x_device_fingerprint: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    user = await auth.authenticate(db, payload.login, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    token = await auth.create_session(db, user, x_device_fingerprint)
    await db.commit()
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> None:
    raw_token = authorization.removeprefix("Bearer ").strip()
    await auth.revoke_session(db, raw_token)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
```

- [ ] **Step 4: Написать `api/v1/router.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers import auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
```

- [ ] **Step 5: Подключить роутер в `app/main.py`**

```python
from fastapi import FastAPI

from app.api.v1.router import api_router

app = FastAPI(title="Трапезная МДА API", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Написать `tests/test_auth.py`**

```python
import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "device-1"


@pytest.fixture
async def operator(db_session):
    user = User(
        login="oper",
        password_hash=hash_password("secret123"),
        full_name="Оператор",
        role=UserRole.operator,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_login_me_logout_flow(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "secret123"},
        headers={"X-Device-Fingerprint": FP},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert resp.json()["user"]["role"] == "operator"
    assert "password_hash" not in resp.json()["user"]

    auth_headers = {"Authorization": f"Bearer {token}", "X-Device-Fingerprint": FP}

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["login"] == "oper"

    out = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert out.status_code == 204

    me_after = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_after.status_code == 401


async def test_login_bad_password(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "nope"},
        headers={"X-Device-Fingerprint": FP},
    )
    assert resp.status_code == 401


async def test_fingerprint_change_revokes_session(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"login": "oper", "password": "secret123"},
        headers={"X-Device-Fingerprint": FP},
    )
    token = resp.json()["token"]

    other = {"Authorization": f"Bearer {token}", "X-Device-Fingerprint": "device-2"}
    r1 = await client.get("/api/v1/auth/me", headers=other)
    assert r1.status_code == 401

    same = {"Authorization": f"Bearer {token}", "X-Device-Fingerprint": FP}
    r2 = await client.get("/api/v1/auth/me", headers=same)
    assert r2.status_code == 401  # сессия уже отозвана
```

> Примечание: тесты `client` и `db_session` используют разные соединения. Чтобы данные из фикстуры `db_session` были видны `client`, `operator` коммитится (`await db_session.commit()`), а приложение (через `get_db`) видит их в своей транзакции. Убедитесь, что тестовая БД одна и та же.

- [ ] **Step 7: Запустить тесты**

Run: `cd server && uv run pytest -v`
Expected: PASS (все тесты фазы).

- [ ] **Step 8: Commit**

```bash
git add server/app/schemas server/app/api server/app/main.py server/tests/test_auth.py
git commit -m "feat: add auth endpoints (login/logout/me)"
```

---

### Task 8: Seed первичных данных

**Files:**
- Create: `server/app/seed.py`
- Test: `server/tests/test_seed.py`

**Interfaces:**
- Consumes: модели, `security.hash_password`, `SessionLocal`.
- Produces: `seed(db, operator_login, operator_password) -> None` — идемпотентно создаёт: `app_settings` (id=1) и 3 типа питания («Мясо», «Пост», «Рыба»), и оператора, если его нет.

- [ ] **Step 1: Написать падающий тест `tests/test_seed.py`**

```python
from sqlalchemy import select

from app.models import AppSettings, MealType, User, UserRole
from app.seed import seed


async def test_seed_is_idempotent(db_session):
    await seed(db_session, operator_login="root", operator_password="rootpass")
    await seed(db_session, operator_login="root", operator_password="rootpass")

    settings = await db_session.get(AppSettings, 1)
    assert settings is not None

    names = (await db_session.execute(select(MealType.name))).scalars().all()
    assert sorted(names) == ["Мясо", "Пост", "Рыба"]

    operators = (
        await db_session.execute(select(User).where(User.role == UserRole.operator))
    ).scalars().all()
    assert len(operators) == 1
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd server && uv run pytest tests/test_seed.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Написать `app/seed.py`**

```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AppSettings, MealType, User, UserRole

DEFAULT_MEAL_TYPES = ["Мясо", "Пост", "Рыба"]


async def seed(db: AsyncSession, operator_login: str, operator_password: str) -> None:
    if await db.get(AppSettings, 1) is None:
        db.add(AppSettings(id=1))

    existing = set((await db.execute(select(MealType.name))).scalars().all())
    for i, name in enumerate(DEFAULT_MEAL_TYPES, start=1):
        if name not in existing:
            db.add(MealType(name=name, sort_order=i))

    has_operator = (
        await db.execute(select(User.id).where(User.role == UserRole.operator))
    ).first()
    if has_operator is None:
        db.add(
            User(
                login=operator_login.lower().strip(),
                password_hash=hash_password(operator_password),
                full_name="Оператор",
                role=UserRole.operator,
            )
        )

    await db.flush()


async def main() -> None:
    import os

    login = os.environ.get("SEED_OPERATOR_LOGIN", "operator")
    password = os.environ.get("SEED_OPERATOR_PASSWORD", "changeme")
    async with SessionLocal() as db:
        await seed(db, login, password)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `cd server && uv run pytest tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 5: Прогнать весь набор и проверить линтер**

Run: `cd server && uv run pytest -v`
Expected: все тесты PASS.

- [ ] **Step 6: Commit**

```bash
git add server/app/seed.py server/tests/test_seed.py
git commit -m "feat: add idempotent seed for operator, meal types and settings"
```

---

## Self-Review (выполнено автором плана)

**1. Покрытие спеки (фаза 1):**
- §2 роли — enum `UserRole` создан; `require_roles` готов к использованию.
- §3 стек (async SQLAlchemy, Alembic, uv, argon2) — Tasks 1, 3, 4, 5.
- §4 `app_settings`, `meal_types`, `users`, `sessions` — Task 3 + миграция Task 4.
- §5 аутентификация/сессии (токен+хеш, отпечаток, TTL 7д, мгновенный сброс) — Tasks 5, 6, 7.
- Seed (оператор, типы, настройки) — Task 8.
- Остальные сущности (halls, requests, days, rules, audit_logs) — фазы 2–6.

**2. Плейсхолдеры:** не осталось; везде конкретный код или команда.

**3. Согласованность имён:** `get_db`, `get_current_user`, `require_roles`, `resolve_session`, `hash_fingerprint`, `MealType`, `UserSession`, `UserRole` — используются одинаково во всех задачах.

**4. Известное ограничение:** команды `git ...` предполагают инициализированный репозиторий (в проекте его пока нет — инициализировать перед выполнением или пропускать коммит-шаги).

---

## Дальнейшие фазы (кратко, отдельные планы)

- **Фаза 2 — Reference & Operator Admin:** `halls`, `user_halls`, `user_meal_defaults`, CRUD оператора, роли, пароли, мягкое/жёсткое удаление, аудит-логирование.
- **Фаза 3 — Schedule Rules & Calendar:** `schedule_rules*`, `days`, `day_hall_meals`, генерация/перегенерация, APScheduler.
- **Фаза 4 — Requests & Marking:** `requests`/`request_items`, дедлайн, резерв, оптимистичная блокировка, `/me` и админ-правки.
- **Фаза 5 — Reports:** дневной и за период.
- **Фаза 6 — Logs cleanup & Docker:** просмотр/очистка логов, Dockerfile/compose.
