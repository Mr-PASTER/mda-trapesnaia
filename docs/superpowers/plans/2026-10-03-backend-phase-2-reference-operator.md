# Трапезная МДА — Backend, фаза 2: Reference & Operator Admin — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить справочники (залы, дефолты питания) и полную панель оператора: CRUD пользователей/залов/типов питания, назначение ролей и залов, сброс пароля, мягкое/жёсткое удаление, настройки системы, плюс аудит-логирование мутаций.

**Architecture:** Продолжение слоистого монолита фазы 1. Бизнес-логика — в `services` (транзакции + вызов аудита), доступ к БД — в `repositories`, HTTP — тонкие роутеры `api/v1/routers/operator/*`. Все мутации пишут запись в `audit_logs`.

**Tech Stack:** те же, что в фазе 1 (FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic, pytest/httpx).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md`
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-backend-phase-1-foundation-auth.md`

## Global Constraints

- Все PK — `UUID` (`uuid.uuid4`).
- `created_at`/`updated_at` — `DateTime(timezone=True)`, `server_default=func.now()`, `updated_at.onupdate=func.now()`.
- Все эндпоинты оператора защищены `Depends(require_roles(UserRole.operator))`.
- Все мутации (create/update/delete) вызывают `services.audit.record(...)` в той же транзакции.
- Наружу не отдаём `password_hash`, `token_hash`, `device_fingerprint_hash`.
- Уникальные нарушения (например, `login`, `hall.name`) → `409` с `detail="already_exists"`.
- Нарушение бизнес-инвариантов → `400` с понятным `detail`.
- Инварианты:
  - минимум **один активный** `meal_type`;
  - `eater` — ровно **1** зал; `admin` — **≥1** зал; `accountant`/`operator` — **0** залов;
  - `login` уникален (в нижнем регистре);
  - тип питания по умолчанию (`users.default_meal_type_id`) должен ссылаться на **активный** тип.
- Тесты: env `TEST_DATABASE_URL` (см. фазу 1), отдельные БД для параллельных агентов.

## Дерево файлов фазы 2

```
server/app/
  models/
    hall.py                     # NEW
    user_hall.py                # NEW
    user_meal_default.py        # NEW
    audit_log.py                # NEW
    __init__.py                 # MODIFY
  schemas/
    hall.py                     # NEW
    meal_type.py                # NEW
    settings.py                 # NEW
    operator_user.py            # NEW
  repositories/
    halls.py                    # NEW
    meal_types.py               # NEW
    users.py                    # MODIFY (добавить методы)
    settings.py                 # NEW
    audit.py                    # NEW
  services/
    audit.py                    # NEW
    halls.py                    # NEW
    meal_types.py               # NEW
    users.py                    # NEW
    settings.py                 # NEW
  api/v1/routers/operator/
    __init__.py                 # NEW (сборка)
    halls.py                    # NEW
    meal_types.py               # NEW
    users.py                    # NEW
    settings.py                 # NEW
  api/v1/router.py              # MODIFY (включить operator)
server/tests/
    test_audit_service.py       # NEW
    test_halls_service.py       # NEW
    test_meal_types_service.py  # NEW
    test_users_service.py       # NEW
    test_settings_service.py    # NEW
    test_operator_api.py        # NEW
```

**Interfaces, которые фаза отдаёт дальше:**
- `services/audit.py`: `record(db, *, actor_id, action, entity_type, entity_id=None, details=None) -> None`.
- `services/halls.py`: `create_hall`, `list_halls`, `update_hall`, `deactivate_hall`.
- `services/meal_types.py`: `create_meal_type`, `list_meal_types`, `update_meal_type`, `deactivate_meal_type`.
- `services/users.py`: `create_user`, `update_user`, `set_password`, `set_halls`, `set_default_meal_type`, `deactivate_user`, `hard_delete_user`, `list_users`.
- `services/settings.py`: `get_settings`, `update_settings`.

---

### Task 1: Модели фазы 2 + миграция + аудит-сервис

**Files:**
- Create: `server/app/models/hall.py`, `user_hall.py`, `user_meal_default.py`, `audit_log.py`
- Modify: `server/app/models/__init__.py`
- Create: `server/app/repositories/audit.py`, `server/app/services/audit.py`
- Create: `server/tests/test_audit_service.py`
- Create (generated): `server/alembic/versions/<rev>_phase2_reference.py`

**Interfaces:**
- Produces: модели `Hall`, `UserHall`, `UserMealDefault`, `AuditLog`; `services.audit.record(...)`.

- [ ] **Step 1: Написать `app/models/hall.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Hall(Base):
    __tablename__ = "halls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Написать `app/models/user_hall.py`**

```python
import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserHall(Base):
    __tablename__ = "user_halls"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 3: Написать `app/models/user_meal_default.py`**

```python
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class UserMealDefault(Base):
    __tablename__ = "user_meal_defaults"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )
    is_going: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Написать `app/models/audit_log.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

- [ ] **Step 5: Обновить `app/models/__init__.py`**

```python
from app.models.app_settings import AppSettings
from app.models.audit_log import AuditLog
from app.models.enums import MealKind, UserRole
from app.models.hall import Hall
from app.models.meal_type import MealType
from app.models.session import UserSession
from app.models.user import User
from app.models.user_hall import UserHall
from app.models.user_meal_default import UserMealDefault

__all__ = [
    "AppSettings",
    "AuditLog",
    "Hall",
    "MealKind",
    "MealType",
    "User",
    "UserHall",
    "UserMealDefault",
    "UserRole",
    "UserSession",
]
```

- [ ] **Step 6: Миграция**

```bash
cd server
uv run alembic revision --autogenerate -m "phase2 reference tables"
uv run alembic upgrade head
docker exec mda_db psql -U mda -d mda -c "\dt"
```

Ожидаем новые таблицы: `halls`, `user_halls`, `user_meal_defaults`, `audit_logs`, и enum `meal_kind`.
> Если в `downgrade()` нет дропа enum `meal_kind`, добавить `sa.Enum(name='meal_kind').drop(op.get_bind(), checkfirst=True)`.

- [ ] **Step 7: Написать `app/repositories/audit.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def create(
    db: AsyncSession,
    *,
    user_id,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict | None,
) -> AuditLog:
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(log)
    await db.flush()
    return log
```

- [ ] **Step 8: Написать падающий тест `tests/test_audit_service.py`**

```python
from sqlalchemy import select

from app.models import AuditLog, User, UserRole
from app.services import audit


async def test_record_writes_audit_log(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(actor)
    await db_session.flush()

    await audit.record(
        db_session,
        actor_id=actor.id,
        action="create",
        entity_type="hall",
        entity_id="abc",
        details={"name": "Зал №1"},
    )
    await db_session.flush()

    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "create"
    assert rows[0].entity_type == "hall"
    assert rows[0].details == {"name": "Зал №1"}
```

- [ ] **Step 9: Написать `app/services/audit.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import audit as audit_repo


async def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> None:
    await audit_repo.create(
        db,
        user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
```

- [ ] **Step 10: Прогнать**

```bash
cd server
export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b1"
uv run pytest tests/test_audit_service.py -v   # FAIL -> PASS
uv run pytest -v                               # весь набор зелёный
```

- [ ] **Step 11: Commit**

```bash
git add server/app/models server/app/repositories/audit.py server/app/services/audit.py server/tests/test_audit_service.py server/alembic
git commit -m "feat: add phase2 reference models, audit service and migration"
```

---

### Task 2: Залы — сервис + схемы

**Files:**
- Create: `server/app/repositories/halls.py`, `server/app/services/halls.py`, `server/app/schemas/hall.py`, `server/tests/test_halls_service.py`

**Interfaces:**
- Consumes: `services.audit.record`, модель `Hall`.
- Produces:
  - `create_hall(db, *, actor_id, name) -> Hall`
  - `list_halls(db, *, only_active=False) -> list[Hall]`
  - `update_hall(db, *, actor_id, hall_id, name=None, is_active=None) -> Hall`
  - `deactivate_hall(db, *, actor_id, hall_id) -> None`

- [ ] **Step 1: Написать падающий тест `tests/test_halls_service.py`**

```python
import pytest

from app.services import halls


async def _mk_actor(db_session):
    from app.models import User, UserRole

    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_create_and_list_halls(db_session):
    actor = await _mk_actor(db_session)
    h = await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")
    assert h.name == "Зал №1"
    assert (await halls.list_halls(db_session))[0].id == h.id


async def test_duplicate_hall_name_raises(db_session):
    actor = await _mk_actor(db_session)
    await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")
    with pytest.raises(halls.HallAlreadyExists):
        await halls.create_hall(db_session, actor_id=actor.id, name="Зал №1")


async def test_deactivate_hall(db_session):
    actor = await _mk_actor(db_session)
    h = await halls.create_hall(db_session, actor_id=actor.id, name="Зал №2")
    await halls.deactivate_hall(db_session, actor_id=actor.id, hall_id=h.id)
    assert (await halls.list_halls(db_session)) == []
    assert len(await halls.list_halls(db_session, only_active=False)) == 1
```

- [ ] **Step 2: Запустить — FAIL**, затем реализовать.

Run: `cd server && export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b2" && uv run pytest tests/test_halls_service.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Написать `app/repositories/halls.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall


async def get(db: AsyncSession, hall_id: uuid.UUID) -> Hall | None:
    return await db.get(Hall, hall_id)


async def get_by_name(db: AsyncSession, name: str) -> Hall | None:
    result = await db.execute(select(Hall).where(Hall.name == name))
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, only_active: bool) -> list[Hall]:
    stmt = select(Hall).order_by(Hall.name)
    if only_active:
        stmt = stmt.where(Hall.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def add(db: AsyncSession, hall: Hall) -> Hall:
    db.add(hall)
    await db.flush()
    return hall
```

- [ ] **Step 4: Написать `app/services/halls.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall
from app.repositories import halls as halls_repo
from app.services import audit


class HallAlreadyExists(Exception):
    pass


async def create_hall(db: AsyncSession, *, actor_id: uuid.UUID, name: str) -> Hall:
    name = name.strip()
    if await halls_repo.get_by_name(db, name) is not None:
        raise HallAlreadyExists(name)
    hall = await halls_repo.add(db, Hall(name=name))
    await audit.record(
        db,
        actor_id=actor_id,
        action="create",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"name": name},
    )
    return hall


async def list_halls(db: AsyncSession, *, only_active: bool = True) -> list[Hall]:
    return await halls_repo.list_all(db, only_active=only_active)


async def update_hall(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    hall_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
) -> Hall:
    hall = await halls_repo.get(db, hall_id)
    if hall is None:
        raise LookupError("hall_not_found")
    if name is not None:
        name = name.strip()
        existing = await halls_repo.get_by_name(db, name)
        if existing is not None and existing.id != hall.id:
            raise HallAlreadyExists(name)
        hall.name = name
    if is_active is not None:
        hall.is_active = is_active
    await db.flush()
    await audit.record(
        db,
        actor_id=actor_id,
        action="update",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"name": hall.name, "is_active": hall.is_active},
    )
    return hall


async def deactivate_hall(
    db: AsyncSession, *, actor_id: uuid.UUID, hall_id: uuid.UUID
) -> None:
    hall = await halls_repo.get(db, hall_id)
    if hall is None:
        raise LookupError("hall_not_found")
    hall.is_active = False
    await db.flush()
    await audit.record(
        db,
        actor_id=actor_id,
        action="delete",
        entity_type="hall",
        entity_id=str(hall.id),
        details={"soft": True},
    )
```

- [ ] **Step 5: Написать `app/schemas/hall.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, Field


class HallIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class HallUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class HallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
```

- [ ] **Step 6: Прогнать — PASS**

Run: `cd server && export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b2" && uv run pytest -v`
Expected: весь набор PASS.

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories/halls.py server/app/services/halls.py server/app/schemas/hall.py server/tests/test_halls_service.py
git commit -m "feat: add halls service and schemas"
```

---

### Task 3: Типы питания — сервис + схемы

**Files:**
- Create: `server/app/repositories/meal_types.py`, `server/app/services/meal_types.py`, `server/app/schemas/meal_type.py`, `server/tests/test_meal_types_service.py`

**Interfaces:**
- Produces:
  - `create_meal_type(db, *, actor_id, name, sort_order=0) -> MealType`
  - `list_meal_types(db, *, only_active=False) -> list[MealType]`
  - `update_meal_type(db, *, actor_id, meal_type_id, name=None, sort_order=None, is_active=None) -> MealType`
  - `deactivate_meal_type(db, *, actor_id, meal_type_id) -> None`
- Инвариант: нельзя деактивировать/удалить последний активный тип → `LastMealType`.

- [ ] **Step 1: Написать падающий тест `tests/test_meal_types_service.py`**

```python
import pytest

from app.models import MealType
from app.services import meal_types


async def _actor(db_session):
    from app.models import User, UserRole

    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_create_and_list(db_session):
    actor = await _actor(db_session)
    await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо", sort_order=1)
    names = [m.name for m in await meal_types.list_meal_types(db_session)]
    assert names == ["Мясо"]


async def test_cannot_deactivate_last_active(db_session):
    actor = await _actor(db_session)
    m = await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо")
    with pytest.raises(meal_types.LastMealType):
        await meal_types.deactivate_meal_type(db_session, actor_id=actor.id, meal_type_id=m.id)


async def test_deactivate_when_more_than_one(db_session):
    actor = await _actor(db_session)
    a = await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Мясо", sort_order=1)
    await meal_types.create_meal_type(db_session, actor_id=actor.id, name="Пост", sort_order=2)
    await meal_types.deactivate_meal_type(db_session, actor_id=actor.id, meal_type_id=a.id)
    assert [m.name for m in await meal_types.list_meal_types(db_session)] == ["Пост"]
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.

Run: `cd server && export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b3" && uv run pytest tests/test_meal_types_service.py -v`

- [ ] **Step 3: Написать `app/repositories/meal_types.py`**

```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealType


async def get(db: AsyncSession, meal_type_id: uuid.UUID) -> MealType | None:
    return await db.get(MealType, meal_type_id)


async def get_by_name(db: AsyncSession, name: str) -> MealType | None:
    result = await db.execute(select(MealType).where(MealType.name == name))
    return result.scalar_one_or_none()


async def list_all(db: AsyncSession, *, only_active: bool) -> list[MealType]:
    stmt = select(MealType).order_by(MealType.sort_order, MealType.name)
    if only_active:
        stmt = stmt.where(MealType.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def count_active(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(MealType).where(MealType.is_active.is_(True))
    )
    return int(result.scalar_one())


async def add(db: AsyncSession, meal_type: MealType) -> MealType:
    db.add(meal_type)
    await db.flush()
    return meal_type
```

- [ ] **Step 4: Написать `app/services/meal_types.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealType
from app.repositories import meal_types as repo
from app.services import audit


class MealTypeAlreadyExists(Exception):
    pass


class LastMealType(Exception):
    pass


async def create_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, name: str, sort_order: int = 0
) -> MealType:
    name = name.strip()
    if await repo.get_by_name(db, name) is not None:
        raise MealTypeAlreadyExists(name)
    mt = await repo.add(db, MealType(name=name, sort_order=sort_order))
    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="meal_type",
        entity_id=str(mt.id), details={"name": name},
    )
    return mt


async def list_meal_types(db: AsyncSession, *, only_active: bool = True) -> list[MealType]:
    return await repo.list_all(db, only_active=only_active)


async def update_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, meal_type_id: uuid.UUID,
    name: str | None = None, sort_order: int | None = None, is_active: bool | None = None,
) -> MealType:
    mt = await repo.get(db, meal_type_id)
    if mt is None:
        raise LookupError("meal_type_not_found")
    if name is not None:
        name = name.strip()
        existing = await repo.get_by_name(db, name)
        if existing is not None and existing.id != mt.id:
            raise MealTypeAlreadyExists(name)
        mt.name = name
    if sort_order is not None:
        mt.sort_order = sort_order
    if is_active is False and mt.is_active and await repo.count_active(db) <= 1:
        raise LastMealType()
    if is_active is not None:
        mt.is_active = is_active
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="meal_type",
        entity_id=str(mt.id), details={"name": mt.name, "is_active": mt.is_active},
    )
    return mt


async def deactivate_meal_type(
    db: AsyncSession, *, actor_id: uuid.UUID, meal_type_id: uuid.UUID
) -> None:
    mt = await repo.get(db, meal_type_id)
    if mt is None:
        raise LookupError("meal_type_not_found")
    if mt.is_active and await repo.count_active(db) <= 1:
        raise LastMealType()
    mt.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="meal_type",
        entity_id=str(mt.id), details={"soft": True},
    )
```

- [ ] **Step 5: Написать `app/schemas/meal_type.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MealTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class MealTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class MealTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
```

- [ ] **Step 6: Прогнать — PASS** (та же команда, что в Step 2).

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories/meal_types.py server/app/services/meal_types.py server/app/schemas/meal_type.py server/tests/test_meal_types_service.py
git commit -m "feat: add meal types service and schemas"
```

---

### Task 4: Пользователи — сервис + схемы

**Files:**
- Modify: `server/app/repositories/users.py` (добавить методы)
- Create: `server/app/services/users.py`, `server/app/schemas/operator_user.py`, `server/tests/test_users_service.py`

**Interfaces:**
- Produces:
  - `create_user(db, *, actor_id, login, password, full_name, role, hall_ids, default_meal_type_id=None) -> User`
  - `list_users(db, *, role=None, hall_id=None, only_active=False) -> list[User]`
  - `update_user(db, *, actor_id, user_id, full_name=None, role=None, default_meal_type_id=...) -> User`
  - `set_password(db, *, actor_id, user_id, password) -> None`
  - `set_halls(db, *, actor_id, user_id, hall_ids) -> None`
  - `deactivate_user(db, *, actor_id, user_id) -> None`
  - `hard_delete_user(db, *, actor_id, user_id) -> None`
- Исключения: `LoginAlreadyExists`, `InvalidHalls`, `DefaultMealTypeInvalid`.

> **Уточнение при выполнении (гонка параллельных агентов):** в `services/users.py` валидация залов
> и типа по умолчанию делается **напрямую по моделям** (`await db.get(Hall, hid)`, `await db.get(MealType, mt_id)`),
> а не через `repositories.halls`/`meal_types` (те писались параллельно в других задачах).
> Поведение и имена исключений — как в плане.

- [ ] **Step 1: Добавить в `app/repositories/users.py` методы**

```python
from sqlalchemy import delete, select

from app.models import User, UserHall


async def list_all(
    db, *, role=None, hall_id=None, only_active: bool = False
) -> list[User]:
    stmt = select(User).order_by(User.login)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if only_active:
        stmt = stmt.where(User.is_active.is_(True))
    if hall_id is not None:
        stmt = stmt.join(UserHall, UserHall.user_id == User.id).where(
            UserHall.hall_id == hall_id
        )
    return list((await db.execute(stmt)).scalars().all())


async def hall_ids_of(db, user_id) -> set:
    result = await db.execute(select(UserHall.hall_id).where(UserHall.user_id == user_id))
    return set(result.scalars().all())


async def replace_halls(db, user_id, hall_ids) -> None:
    await db.execute(delete(UserHall).where(UserHall.user_id == user_id))
    for hid in hall_ids:
        db.add(UserHall(user_id=user_id, hall_id=hid))
    await db.flush()


async def add(db, user: User) -> User:
    db.add(user)
    await db.flush()
    return user


async def delete_user(db, user_id) -> None:
    from sqlalchemy import delete as _delete

    await db.execute(_delete(User).where(User.id == user_id))
    await db.flush()
```

- [ ] **Step 2: Написать падающий тест `tests/test_users_service.py`**

```python
import pytest

from app.models import Hall, MealType, User, UserRole
from app.services import users


async def _ctx(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    db_session.add_all([actor, hall, mt])
    await db_session.flush()
    return actor, hall, mt


async def test_create_eater_requires_exactly_one_hall(db_session):
    actor, hall, mt = await _ctx(db_session)
    with pytest.raises(users.InvalidHalls):
        await users.create_user(
            db_session, actor_id=actor.id, login="ivan", password="p",
            full_name="Иван", role=UserRole.eater, hall_ids=[],
        )
    u = await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
        default_meal_type_id=mt.id,
    )
    assert u.login == "ivan"
    assert await users.repo.hall_ids_of(db_session, u.id) == {hall.id}


async def test_duplicate_login(db_session):
    actor, hall, mt = await _ctx(db_session)
    await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
    )
    with pytest.raises(users.LoginAlreadyExists):
        await users.create_user(
            db_session, actor_id=actor.id, login="IVAN", password="p",
            full_name="Иван 2", role=UserRole.eater, hall_ids=[hall.id],
        )


async def test_set_halls_and_soft_hard_delete(db_session):
    actor, hall, mt = await _ctx(db_session)
    u = await users.create_user(
        db_session, actor_id=actor.id, login="ivan", password="p",
        full_name="Иван", role=UserRole.eater, hall_ids=[hall.id],
    )
    await users.deactivate_user(db_session, actor_id=actor.id, user_id=u.id)
    assert u.is_active is False
    await users.hard_delete_user(db_session, actor_id=actor.id, user_id=u.id)
    assert await users.repo.get_by_id(db_session, u.id) is None
```

- [ ] **Step 3: Запустить — FAIL.** Затем реализовать.

Run: `cd server && export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test" && uv run pytest tests/test_users_service.py -v`

- [ ] **Step 4: Написать `app/services/users.py`**

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import MealKind, User, UserRole
from app.repositories import halls as halls_repo
from app.repositories import meal_types as mt_repo
from app.repositories import users as repo
from app.services import audit

_HALL_RULES = {
    UserRole.eater: (1, 1),
    UserRole.admin: (1, None),
    UserRole.accountant: (0, 0),
    UserRole.operator: (0, 0),
}


class LoginAlreadyExists(Exception):
    pass


class InvalidHalls(Exception):
    pass


class DefaultMealTypeInvalid(Exception):
    pass


def _validate_halls(role: UserRole, hall_ids: list[uuid.UUID]) -> None:
    lo, hi = _HALL_RULES[role]
    n = len(set(hall_ids))
    if n < lo or (hi is not None and n > hi):
        raise InvalidHalls(f"role {role.value} requires {lo}..{hi} halls, got {n}")


async def _validate_hall_ids(db: AsyncSession, hall_ids: list[uuid.UUID]) -> None:
    for hid in set(hall_ids):
        hall = await halls_repo.get(db, hid)
        if hall is None or not hall.is_active:
            raise InvalidHalls(f"hall {hid} not found or inactive")


async def _validate_default_type(db: AsyncSession, meal_type_id: uuid.UUID | None) -> None:
    if meal_type_id is None:
        return
    mt = await mt_repo.get(db, meal_type_id)
    if mt is None or not mt.is_active:
        raise DefaultMealTypeInvalid(str(meal_type_id))


async def create_user(
    db: AsyncSession, *, actor_id: uuid.UUID, login: str, password: str,
    full_name: str, role: UserRole, hall_ids: list[uuid.UUID],
    default_meal_type_id: uuid.UUID | None = None,
) -> User:
    login = login.lower().strip()
    if await repo.get_by_login(db, login) is not None:
        raise LoginAlreadyExists(login)
    _validate_halls(role, hall_ids)
    await _validate_hall_ids(db, hall_ids)
    await _validate_default_type(db, default_meal_type_id)

    user = await repo.add(
        db,
        User(
            login=login,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            default_meal_type_id=default_meal_type_id,
        ),
    )
    await repo.replace_halls(db, user.id, hall_ids)
    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="user",
        entity_id=str(user.id),
        details={"login": login, "role": role.value, "halls": [str(h) for h in hall_ids]},
    )
    return user


async def list_users(
    db: AsyncSession, *, role: UserRole | None = None,
    hall_id: uuid.UUID | None = None, only_active: bool = False,
) -> list[User]:
    return await repo.list_all(db, role=role, hall_id=hall_id, only_active=only_active)


async def update_user(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID,
    full_name: str | None = None, role: UserRole | None = None,
    default_meal_type_id: uuid.UUID | None = None,
) -> User:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    if full_name is not None:
        user.full_name = full_name
    if role is not None and role != user.role:
        current = await repo.hall_ids_of(db, user.id)
        _validate_halls(role, list(current))
        user.role = role
    if default_meal_type_id is not None:
        await _validate_default_type(db, default_meal_type_id)
        user.default_meal_type_id = default_meal_type_id
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="user",
        entity_id=str(user.id),
        details={"full_name": user.full_name, "role": user.role.value},
    )
    return user


async def set_password(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, password: str
) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    user.password_hash = hash_password(password)
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="set_password", entity_type="user",
        entity_id=str(user.id), details=None,
    )


async def set_halls(
    db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID,
    hall_ids: list[uuid.UUID],
) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    _validate_halls(user.role, hall_ids)
    await _validate_hall_ids(db, hall_ids)
    await repo.replace_halls(db, user.id, hall_ids)
    await audit.record(
        db, actor_id=actor_id, action="set_halls", entity_type="user",
        entity_id=str(user.id), details={"halls": [str(h) for h in hall_ids]},
    )


async def deactivate_user(db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    user.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="user",
        entity_id=str(user.id), details={"soft": True},
    )


async def hard_delete_user(db: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID) -> None:
    user = await repo.get_by_id(db, user_id)
    if user is None:
        raise LookupError("user_not_found")
    details = {"login": user.login, "soft": False}
    await audit.record(
        db, actor_id=actor_id, action="hard_delete", entity_type="user",
        entity_id=str(user_id), details=details,
    )
    await repo.delete_user(db, user_id)
```

- [ ] **Step 5: Написать `app/schemas/operator_user.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole
from app.schemas.user import UserOut


class OperatorUserCreate(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=4, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    hall_ids: list[uuid.UUID] = []
    default_meal_type_id: uuid.UUID | None = None


class OperatorUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    default_meal_type_id: uuid.UUID | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=4, max_length=128)


class HallsSet(BaseModel):
    hall_ids: list[uuid.UUID]


class OperatorUserOut(UserOut):
    model_config = ConfigDict(from_attributes=True)
    hall_ids: list[uuid.UUID] = []
```

- [ ] **Step 6: Прогнать — PASS** (команда из Step 3).

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories/users.py server/app/services/users.py server/app/schemas/operator_user.py server/tests/test_users_service.py
git commit -m "feat: add operator users service and schemas"
```

---

### Task 5: Настройки — сервис + схемы

**Files:**
- Create: `server/app/repositories/settings.py`, `server/app/services/settings.py`, `server/app/schemas/settings.py`, `server/tests/test_settings_service.py`

**Interfaces:**
- Produces:
  - `get_settings(db) -> AppSettings` (создаёт строку id=1, если нет)
  - `update_settings(db, *, actor_id, generation_days=None, deadline_offset_days=None, deadline_time=None) -> AppSettings`

- [ ] **Step 1: Написать падающий тест `tests/test_settings_service.py`**

```python
from datetime import time

import pytest

from app.models import AppSettings, User, UserRole
from app.services import settings as svc


async def _actor(db_session):
    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_get_creates_defaults(db_session):
    s = await svc.get_settings(db_session)
    assert s.generation_days == 14
    assert s.deadline_offset_days == 2


async def test_update_settings(db_session):
    actor = await _actor(db_session)
    s = await svc.update_settings(
        db_session, actor_id=actor.id, generation_days=30,
        deadline_offset_days=3, deadline_time=time(12, 30),
    )
    assert s.generation_days == 30
    assert s.deadline_offset_days == 3
    assert s.deadline_time == time(12, 30)


async def test_invalid_values_rejected(db_session):
    actor = await _actor(db_session)
    with pytest.raises(ValueError):
        await svc.update_settings(db_session, actor_id=actor.id, generation_days=0)
    with pytest.raises(ValueError):
        await svc.update_settings(db_session, actor_id=actor.id, deadline_offset_days=-1)
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.

Run: `cd server && export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b1" && uv run pytest tests/test_settings_service.py -v`

- [ ] **Step 3: Написать `app/repositories/settings.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings


async def get(db: AsyncSession) -> AppSettings | None:
    return await db.get(AppSettings, 1)


async def ensure(db: AsyncSession) -> AppSettings:
    row = await db.get(AppSettings, 1)
    if row is None:
        row = AppSettings(id=1)
        db.add(row)
        await db.flush()
    return row
```

- [ ] **Step 4: Написать `app/services/settings.py`**

```python
import uuid
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings
from app.repositories import settings as repo
from app.services import audit


async def get_settings(db: AsyncSession) -> AppSettings:
    return await repo.ensure(db)


async def update_settings(
    db: AsyncSession, *, actor_id: uuid.UUID,
    generation_days: int | None = None,
    deadline_offset_days: int | None = None,
    deadline_time: time | None = None,
) -> AppSettings:
    if generation_days is not None and generation_days < 1:
        raise ValueError("generation_days must be >= 1")
    if deadline_offset_days is not None and deadline_offset_days < 0:
        raise ValueError("deadline_offset_days must be >= 0")

    row = await repo.ensure(db)
    if generation_days is not None:
        row.generation_days = generation_days
    if deadline_offset_days is not None:
        row.deadline_offset_days = deadline_offset_days
    if deadline_time is not None:
        row.deadline_time = deadline_time
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="settings",
        entity_id="1",
        details={
            "generation_days": row.generation_days,
            "deadline_offset_days": row.deadline_offset_days,
            "deadline_time": row.deadline_time.isoformat(),
        },
    )
    return row
```

- [ ] **Step 5: Написать `app/schemas/settings.py`**

```python
from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    generation_days: int | None = Field(default=None, ge=1)
    deadline_offset_days: int | None = Field(default=None, ge=0)
    deadline_time: time | None = None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generation_days: int
    deadline_offset_days: int
    deadline_time: time
```

- [ ] **Step 6: Прогнать — PASS** (команда из Step 2).

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories/settings.py server/app/services/settings.py server/app/schemas/settings.py server/tests/test_settings_service.py
git commit -m "feat: add app settings service and schemas"
```

---

### Task 6: HTTP-роутеры оператора + интеграционные тесты

**Files:**
- Create: `server/app/api/v1/routers/operator/__init__.py`, `halls.py`, `meal_types.py`, `users.py`, `settings.py`
- Modify: `server/app/api/v1/router.py`
- Create: `server/tests/test_operator_api.py`

**Interfaces:**
- Consumes: все сервисы фаз 2 и `require_roles(UserRole.operator)`.
- Produces: `operator_router` (prefix `/operator`) со всеми эндпоинтами.

- [ ] **Step 1: Написать `app/api/v1/routers/operator/halls.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.hall import HallIn, HallOut, HallUpdate
from app.services import halls

router = APIRouter(prefix="/halls", tags=["operator:halls"])

_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[HallOut])
async def list_halls(only_active: bool = True, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    return await halls.list_halls(db, only_active=only_active)


@router.post("", response_model=HallOut, status_code=status.HTTP_201_CREATED)
async def create_hall(payload: HallIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        hall = await halls.create_hall(db, actor_id=user.id, name=payload.name)
    except halls.HallAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return hall


@router.put("/{hall_id}", response_model=HallOut)
async def update_hall(hall_id: uuid.UUID, payload: HallUpdate,
                      db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        hall = await halls.update_hall(
            db, actor_id=user.id, hall_id=hall_id,
            name=payload.name, is_active=payload.is_active,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="hall_not_found")
    except halls.HallAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return hall


@router.delete("/{hall_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hall(hall_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        await halls.deactivate_hall(db, actor_id=user.id, hall_id=hall_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="hall_not_found")
    await db.commit()
```

- [ ] **Step 2: Написать `app/api/v1/routers/operator/meal_types.py`**

По той же схеме, что `halls.py`, с сервисом `meal_types`:
- `GET /meal-types` (`only_active: bool = True`) → `list[MealTypeOut]`
- `POST /meal-types` → `201`, `MealTypeAlreadyExists → 409`
- `PUT /meal-types/{id}` → `LookupError → 404`, `MealTypeAlreadyExists → 409`, `LastMealType → 400 detail="last_meal_type"`
- `DELETE /meal-types/{id}` → `204`, `LastMealType → 400 detail="last_meal_type"`

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.meal_type import MealTypeIn, MealTypeOut, MealTypeUpdate
from app.services import meal_types

router = APIRouter(prefix="/meal-types", tags=["operator:meal-types"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=list[MealTypeOut])
async def list_meal_types(only_active: bool = True, db: AsyncSession = Depends(get_db),
                          _: User = Depends(_guard)):
    return await meal_types.list_meal_types(db, only_active=only_active)


@router.post("", response_model=MealTypeOut, status_code=status.HTTP_201_CREATED)
async def create_meal_type(payload: MealTypeIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(_guard)):
    try:
        mt = await meal_types.create_meal_type(
            db, actor_id=user.id, name=payload.name, sort_order=payload.sort_order
        )
    except meal_types.MealTypeAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    await db.commit()
    return mt


@router.put("/{meal_type_id}", response_model=MealTypeOut)
async def update_meal_type(meal_type_id: uuid.UUID, payload: MealTypeUpdate,
                           db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        mt = await meal_types.update_meal_type(
            db, actor_id=user.id, meal_type_id=meal_type_id, name=payload.name,
            sort_order=payload.sort_order, is_active=payload.is_active,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="meal_type_not_found")
    except meal_types.MealTypeAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="already_exists")
    except meal_types.LastMealType:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="last_meal_type")
    await db.commit()
    return mt


@router.delete("/{meal_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal_type(meal_type_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           user: User = Depends(_guard)):
    try:
        await meal_types.deactivate_meal_type(db, actor_id=user.id, meal_type_id=meal_type_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="meal_type_not_found")
    except meal_types.LastMealType:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="last_meal_type")
    await db.commit()
```

- [ ] **Step 3: Написать `app/api/v1/routers/operator/users.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.repositories import users as users_repo
from app.schemas.operator_user import (
    HallsSet, OperatorUserCreate, OperatorUserOut, OperatorUserUpdate, PasswordSet,
)
from app.services import users

router = APIRouter(prefix="/users", tags=["operator:users"])
_guard = require_roles(UserRole.operator)


async def _to_out(db: AsyncSession, user: User) -> OperatorUserOut:
    halls = await users_repo.hall_ids_of(db, user.id)
    out = OperatorUserOut.model_validate(user)
    out.hall_ids = sorted(halls)
    return out


@router.get("", response_model=list[OperatorUserOut])
async def list_users(role: UserRole | None = None, hall_id: uuid.UUID | None = None,
                     only_active: bool = False, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    result = []
    for u in await users.list_users(db, role=role, hall_id=hall_id, only_active=only_active):
        result.append(await _to_out(db, u))
    return result


@router.post("", response_model=OperatorUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: OperatorUserCreate, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_guard)):
    try:
        user = await users.create_user(
            db, actor_id=actor.id, login=payload.login, password=payload.password,
            full_name=payload.full_name, role=payload.role, hall_ids=payload.hall_ids,
            default_meal_type_id=payload.default_meal_type_id,
        )
    except users.LoginAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="login_exists")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    except users.DefaultMealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _to_out(db, user)


@router.put("/{user_id}", response_model=OperatorUserOut)
async def update_user(user_id: uuid.UUID, payload: OperatorUserUpdate,
                      db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        user = await users.update_user(
            db, actor_id=actor.id, user_id=user_id, full_name=payload.full_name,
            role=payload.role, default_meal_type_id=payload.default_meal_type_id,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    except users.DefaultMealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _to_out(db, user)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(user_id: uuid.UUID, payload: PasswordSet,
                       db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        await users.set_password(db, actor_id=actor.id, user_id=user_id, password=payload.password)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await db.commit()


@router.put("/{user_id}/halls", response_model=OperatorUserOut)
async def set_halls(user_id: uuid.UUID, payload: HallsSet,
                    db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        await users.set_halls(db, actor_id=actor.id, user_id=user_id, hall_ids=payload.hall_ids)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    except users.InvalidHalls as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_halls: {e}")
    user = await users_repo.get_by_id(db, user_id)
    await db.commit()
    return await _to_out(db, user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, hard: bool = False,
                      db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    try:
        if hard:
            await users.hard_delete_user(db, actor_id=actor.id, user_id=user_id)
        else:
            await users.deactivate_user(db, actor_id=actor.id, user_id=user_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await db.commit()
```

- [ ] **Step 4: Написать `app/api/v1/routers/operator/settings.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services import settings as svc

router = APIRouter(prefix="/settings", tags=["operator:settings"])
_guard = require_roles(UserRole.operator)


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    row = await svc.get_settings(db)
    await db.commit()
    return row


@router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db),
                          user: User = Depends(_guard)):
    row = await svc.update_settings(
        db, actor_id=user.id, generation_days=payload.generation_days,
        deadline_offset_days=payload.deadline_offset_days, deadline_time=payload.deadline_time,
    )
    await db.commit()
    return row
```

- [ ] **Step 5: Написать `app/api/v1/routers/operator/__init__.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers.operator import halls, meal_types, settings, users

operator_router = APIRouter(prefix="/operator")
operator_router.include_router(halls.router)
operator_router.include_router(meal_types.router)
operator_router.include_router(users.router)
operator_router.include_router(settings.router)
```

- [ ] **Step 6: Включить в `app/api/v1/router.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers import auth
from app.api.v1.routers.operator import operator_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(operator_router)
```

- [ ] **Step 7: Написать `tests/test_operator_api.py`**

```python
import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def operator_token(db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    return u


async def _login(client, login="root", password="rootpass"):
    r = await client.post("/api/v1/auth/login", json={"login": login, "password": password},
                          headers={"X-Device-Fingerprint": FP})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_operator_crud_flow(client, operator_token):
    h = await _login(client)

    # создать зал
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=h)
    assert r.status_code == 201
    hall_id = r.json()["id"]

    # дубль зала → 409
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=h)
    assert r.status_code == 409

    # типы питания
    r = await client.post("/api/v1/operator/meal-types",
                          json={"name": "Мясо", "sort_order": 1}, headers=h)
    assert r.status_code == 201
    mt_id = r.json()["id"]

    # нельзя удалить последний активный тип → 400
    r = await client.delete(f"/api/v1/operator/meal-types/{mt_id}", headers=h)
    assert r.status_code == 400
    assert r.json()["detail"] == "last_meal_type"

    # создать питающегося без зала → 400
    r = await client.post("/api/v1/operator/users", headers=h, json={
        "login": "ivan", "password": "pass", "full_name": "Иван",
        "role": "eater", "hall_ids": [],
    })
    assert r.status_code == 400

    # корректный питающийся
    r = await client.post("/api/v1/operator/users", headers=h, json={
        "login": "ivan", "password": "pass", "full_name": "Иван",
        "role": "eater", "hall_ids": [hall_id], "default_meal_type_id": mt_id,
    })
    assert r.status_code == 201
    user_id = r.json()["id"]
    assert r.json()["hall_ids"] == [hall_id]

    # настройки
    r = await client.get("/api/v1/operator/settings", headers=h)
    assert r.status_code == 200
    r = await client.put("/api/v1/operator/settings", json={"generation_days": 21}, headers=h)
    assert r.status_code == 200 and r.json()["generation_days"] == 21

    # мягкое удаление
    r = await client.delete(f"/api/v1/operator/users/{user_id}", headers=h)
    assert r.status_code == 204


async def test_non_operator_forbidden(client, db_session):
    # питающийся не должен иметь доступ к операторским эндпоинтам
    u = User(login="eater1", password_hash=hash_password("p"),
             full_name="Е", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    h = await _login(client, "eater1", "p")
    r = await client.get("/api/v1/operator/halls", headers=h)
    assert r.status_code == 403
```

- [ ] **Step 8: Прогнать**

```bash
cd server
export TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test"
uv run pytest -v
```
Expected: весь набор PASS.

- [ ] **Step 9: Commit**

```bash
git add server/app/api/v1/routers/operator server/app/api/v1/router.py server/tests/test_operator_api.py
git commit -m "feat: add operator HTTP routers and integration tests"
```

---

## Self-Review (автора плана)

- **Инварианты:** ≥1 активный тип питания (Task 3), правила залов по ролям (Task 4), уникальность логина/названий (Tasks 2–4), активный тип по умолчанию (Task 4).
- **Аудит:** каждая мутация вызывает `audit.record` (Tasks 2–5).
- **Права:** все операторские роутеры под `require_roles(UserRole.operator)` (Task 6).
- **Плейсхолдеров нет:** каждый шаг содержит код/команду.
- **Согласованность:** имена сервисов/исключений одинаковы в тестах, сервисах и роутерах (`HallAlreadyExists`, `MealTypeAlreadyExists`, `LastMealType`, `LoginAlreadyExists`, `InvalidHalls`, `DefaultMealTypeInvalid`).
- **Замечание по изоляции тестов:** фаза 2 использует фазы 1 `conftest.py` (create_all/drop_all + TRUNCATE между тестами). Новые модели должны быть импортированы в `app/models/__init__.py` (Task 1), иначе они не попадут в `Base.metadata`.

## Следующие фазы

- **Фаза 3 — Schedule Rules & Calendar:** правила, `days`, `day_hall_meals`, генерация/перегенерация, APScheduler.
- **Фаза 4 — Requests & Marking:** заявки, дедлайн, резерв, оптимистичная блокировка, `/me` и админ-правки.
- **Фаза 5 — Reports:** дневной и за период.
- **Фаза 6 — Logs cleanup & Docker:** просмотр/очистка логов, Dockerfile/compose.
