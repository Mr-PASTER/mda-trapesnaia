# Трапезная МДА — Backend, фаза 4: Requests & Marking — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать ядро отметок питания: заявки (`requests`/`request_items`), ленивое создание из дефолтов, дедлайн правок, пометку «Из резерва», оптимистичную блокировку (версия → `409`), а также эндпоинты `/me` (питающийся) и `/admin` (админ своих залов).

**Architecture:** Продолжение слоистого монолита. Разделяем: `services/deadline.py` (чистый расчёт дедлайна), `services/access.py` (права на правку чужого дня), `services/day_view.py` (чтение эффективного состояния дня), `services/requests.py` (запись/ленивое создание/резерв/версия), `services/defaults.py` (дефолты). Сервисы читают модели напрямую, чтобы волны шли параллельно без гонок импортов. HTTP — тонкие роутеры `/me` и `/admin`.

**Tech Stack:** те же (FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, Alembic, pytest/httpx).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md` (§6, §8, §9, §10.2, §10.3)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-backend-phase-3-schedule-calendar.md`

## Global Constraints

- Все PK — `UUID` (`uuid.uuid4`); `created_at`/`updated_at` — `DateTime(timezone=True)`.
- Enum `meal_kind` уже существует — при миграции переиспользовать через `postgresql.ENUM(..., name='meal_kind', create_type=False)` (иначе `DuplicateObjectError`).
- **Дедлайн** дня `D` = `(D − K)` в `H:00` (K, H из `app_settings`), часовой пояс `Europe/Moscow`. До дедлайна — правит питающийся и админ; после — только админ, и правка помечается `is_reserve = true`.
- **Резерв:** админская правка **после** дедлайна помечает затронутые «иду»-порции (`is_going` изменился с `false` на `true`). Смена **типа** дня админом после дедлайна помечает **все** «иду»-порции дня. Если админ выключает приём (`is_going=false`) → `is_reserve` сбрасывается.
- **Версия — на заявку** (`requests.version`). Обновление под `SELECT ... FOR UPDATE`; несовпадение присланной версии → `VersionConflict` → HTTP `409` c `detail="record_changed"` и телом `current`.
- **Заявки не удаляются.** Если заявки нет — действуют дефолты (`user_meal_defaults`, `users.default_meal_type_id`).
- Эффективные значения учитывают только приёмы, где `day_hall_meals.is_served = true` (для залов пользователя; «объединение по залам»: приём считается подаваемым, если подан хотя бы в одном зале пользователя).
- Наружу не отдаём `password_hash`/`token_hash`/`device_fingerprint_hash`.
- Права: `/me/*` — любой аутентифицированный; `/admin/*` — только `admin` (и `operator` для чтения); правка чужого дня — только админ общих залов.

## Дерево файлов фазы 4

```
server/app/
  models/
    request.py              # NEW (Request, RequestItem)
    __init__.py             # MODIFY
  services/
    deadline.py             # NEW
    access.py               # NEW
    day_view.py             # NEW (DayState, MealState, get_day_state)
    requests.py             # NEW (save_day)
    defaults.py             # NEW
  schemas/
    request.py              # NEW
  api/v1/routers/
    me.py                   # NEW
    admin.py                # NEW
  api/v1/router.py          # MODIFY (include me, admin)
server/tests/
    test_deadline_service.py    # NEW
    test_access_service.py      # NEW
    test_day_view_service.py    # NEW
    test_requests_service.py    # NEW
    test_defaults_service.py    # NEW
    test_me_api.py              # NEW
    test_admin_api.py           # NEW
```

**Interfaces, которые фаза отдаёт дальше:**
- `services/deadline.py`: `deadline_for(db, day_date) -> datetime`, `is_locked(db, day_date, now=None) -> bool`.
- `services/access.py`: `AccessDenied`, `hall_ids_of(db, user_id) -> set[UUID]`, `ensure_can_edit_user(db, *, actor, target) -> None`.
- `services/day_view.py`: `MealState`, `DayState`, `get_day_state(db, *, user, day_date, now=None) -> DayState`.
- `services/requests.py`: `DayLocked`, `VersionConflict`, `MealTypeInvalid`, `save_day(db, *, actor, target, day_date, meal_type_id, meals, version) -> Request`.
- `services/defaults.py`: `Defaults`, `get_defaults(db, user) -> Defaults`, `update_defaults(db, *, actor_id, user, meal_type_id, meals) -> None`.

---

### Task 1: Модели заявок + дедлайн + права

**Files:**
- Create: `server/app/models/request.py`
- Modify: `server/app/models/__init__.py`
- Create: `server/app/services/deadline.py`, `server/app/services/access.py`
- Create: `server/tests/test_deadline_service.py`, `server/tests/test_access_service.py`
- Create (generated): `server/alembic/versions/<rev>_phase4_requests.py`

**Interfaces:**
- Produces: `Request`, `RequestItem`, `deadline.deadline_for`, `deadline.is_locked`, `access.AccessDenied`, `access.hall_ids_of`, `access.ensure_can_edit_user`.

- [ ] **Step 1: Написать `app/models/request.py`**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_requests_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    meal_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meal_types.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RequestItem(Base):
    __tablename__ = "request_items"
    __table_args__ = (
        UniqueConstraint("request_id", "meal_kind", name="uq_request_items_request_meal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE")
    )
    meal_kind: Mapped[MealKind] = mapped_column(Enum(MealKind, name="meal_kind"))
    is_going: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reserve: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 2: Обновить `app/models/__init__.py`** — добавить `Request`, `RequestItem` в импорты и `__all__`.

- [ ] **Step 3: Написать `app/services/deadline.py`**

```python
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import settings as settings_service


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


async def deadline_for(db: AsyncSession, day_date: date) -> datetime:
    cfg = await settings_service.get_settings(db)
    moment = datetime.combine(
        day_date - timedelta(days=cfg.deadline_offset_days), cfg.deadline_time
    )
    return moment.replace(tzinfo=_tz())


async def is_locked(db: AsyncSession, day_date: date, now: datetime | None = None) -> bool:
    now = now or datetime.now(_tz())
    return now >= await deadline_for(db, day_date)
```

- [ ] **Step 4: Написать `app/services/access.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserHall, UserRole


class AccessDenied(Exception):
    pass


async def hall_ids_of(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(select(UserHall.hall_id).where(UserHall.user_id == user_id))
    return set(result.scalars().all())


async def ensure_can_edit_user(db: AsyncSession, *, actor: User, target: User) -> None:
    if actor.id == target.id:
        return
    if actor.role == UserRole.admin:
        if await hall_ids_of(db, actor.id) & await hall_ids_of(db, target.id):
            return
    raise AccessDenied()
```

- [ ] **Step 5: Написать `tests/test_deadline_service.py`**

```python
import datetime as dt
from datetime import time
from zoneinfo import ZoneInfo

from app.models import User, UserRole
from app.services import deadline, settings as settings_service


async def _actor(db_session):
    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def test_deadline_and_lock(db_session):
    actor = await _actor(db_session)
    await settings_service.update_settings(
        db_session, actor_id=actor.id, deadline_offset_days=3, deadline_time=time(13, 0)
    )
    day = dt.date(2026, 10, 10)
    tz = ZoneInfo("Europe/Moscow")

    assert await deadline.deadline_for(db_session, day) == dt.datetime(2026, 10, 7, 13, 0, tzinfo=tz)
    assert await deadline.is_locked(
        db_session, day, now=dt.datetime(2026, 10, 7, 12, 0, tzinfo=tz)
    ) is False
    assert await deadline.is_locked(
        db_session, day, now=dt.datetime(2026, 10, 7, 14, 0, tzinfo=tz)
    ) is True
```

- [ ] **Step 6: Написать `tests/test_access_service.py`**

```python
import pytest

from app.models import Hall, User, UserHall, UserRole
from app.services import access


async def _mk(db_session, login, role, halls):
    u = User(login=login, password_hash="x", full_name=login, role=role)
    db_session.add(u)
    await db_session.flush()
    for h in halls:
        db_session.add(UserHall(user_id=u.id, hall_id=h.id))
    await db_session.flush()
    return u


async def test_self_allowed(db_session):
    eater = await _mk(db_session, "e1", UserRole.eater, [])
    await access.ensure_can_edit_user(db_session, actor=eater, target=eater)


async def test_admin_of_shared_hall_allowed(db_session):
    h1 = Hall(name="Зал №1")
    db_session.add(h1)
    await db_session.flush()
    admin = await _mk(db_session, "a1", UserRole.admin, [h1])
    eater = await _mk(db_session, "e1", UserRole.eater, [h1])
    await access.ensure_can_edit_user(db_session, actor=admin, target=eater)


async def test_admin_other_hall_denied(db_session):
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([h1, h2])
    await db_session.flush()
    admin = await _mk(db_session, "a1", UserRole.admin, [h1])
    eater = await _mk(db_session, "e1", UserRole.eater, [h2])
    with pytest.raises(access.AccessDenied):
        await access.ensure_can_edit_user(db_session, actor=admin, target=eater)


async def test_operator_denied(db_session):
    op = await _mk(db_session, "op", UserRole.operator, [])
    eater = await _mk(db_session, "e1", UserRole.eater, [])
    with pytest.raises(access.AccessDenied):
        await access.ensure_can_edit_user(db_session, actor=op, target=eater)
```

- [ ] **Step 7: Миграция**

```bash
cd server
uv run alembic revision --autogenerate -m "phase4 requests"
```
Затем ОБЯЗАТЕЛЬНО открыть файл и заменить inline enum на `postgresql.ENUM('breakfast','lunch','snack','dinner', name='meal_kind', create_type=False)` для `request_items.meal_kind`.

```bash
uv run alembic upgrade head
docker exec mda_db psql -U mda -d mda -c "\dt"
```
Ожидаем `requests`, `request_items`.

- [ ] **Step 8: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b1" uv run pytest -v
```

- [ ] **Step 9: Commit**

```bash
git add server/app/models server/app/services/deadline.py server/app/services/access.py server/tests/test_deadline_service.py server/tests/test_access_service.py server/alembic
git commit -m "feat: add request models, deadline and access services"
```

---

### Task 2: Чтение эффективного состояния дня

**Files:**
- Create: `server/app/services/day_view.py`, `server/tests/test_day_view_service.py`

**Interfaces:**
- Consumes: модели `Request`, `RequestItem`, `Day`, `DayHallMeal`, `UserMealDefault`, `deadline`.
- Produces: `MealState`, `DayState`, `get_day_state(db, *, user, day_date, now=None) -> DayState`.

- [ ] **Step 1: Написать падающий тест `tests/test_day_view_service.py`**

```python
import datetime as dt

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, User, UserHall, UserMealDefault, UserRole,
)
from app.services import day_view


async def _setup(db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    day = Day(date=dt.date(2026, 10, 10))
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk,
                                   is_served=(mk != MealKind.snack)))
    db_session.add_all([
        UserMealDefault(user_id=user.id, meal_kind=MealKind.breakfast, is_going=True),
        UserMealDefault(user_id=user.id, meal_kind=MealKind.lunch, is_going=True),
    ])
    await db_session.flush()
    return hall, mt, user


async def test_defaults_when_no_request(db_session):
    hall, mt, user = await _setup(db_session)
    state = await day_view.get_day_state(db_session, user=user, day_date=dt.date(2026, 10, 10))
    assert state.has_request is False
    assert state.version is None
    assert state.meal_type_id == mt.id
    served = {i.meal_kind: i.is_served for i in state.items}
    assert served[MealKind.snack] is False
    going = {i.meal_kind: i.is_going for i in state.items}
    assert going[MealKind.breakfast] is True
    assert going[MealKind.dinner] is False
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test_b2" uv run pytest tests/test_day_view_service.py -v`

- [ ] **Step 3: Написать `app/services/day_view.py`**

```python
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Day, DayHallMeal, MealKind, Request, RequestItem, User, UserMealDefault,
)
from app.services import access, deadline


@dataclass
class MealState:
    meal_kind: MealKind
    is_served: bool
    is_going: bool
    is_reserve: bool


@dataclass
class DayState:
    date: date
    meal_type_id: uuid.UUID | None
    items: list[MealState]
    version: int | None
    has_request: bool
    deadline_at: datetime
    editable: bool


async def _served_map(db: AsyncSession, hall_ids: set[uuid.UUID], day_date: date) -> dict[MealKind, bool]:
    served = {mk: False for mk in MealKind}
    if not hall_ids:
        return served
    stmt = (
        select(DayHallMeal.meal_kind, DayHallMeal.is_served)
        .join(Day, Day.id == DayHallMeal.day_id)
        .where(Day.date == day_date, DayHallMeal.hall_id.in_(hall_ids))
    )
    for meal_kind, is_served in (await db.execute(stmt)).all():
        served[meal_kind] = served[meal_kind] or is_served
    return served


async def get_day_state(
    db: AsyncSession, *, user: User, day_date: date, now: datetime | None = None
) -> DayState:
    hall_ids = await access.hall_ids_of(db, user.id)
    served = await _served_map(db, hall_ids, day_date)

    req = (
        await db.execute(
            select(Request).where(Request.user_id == user.id, Request.date == day_date)
        )
    ).scalar_one_or_none()

    if req is not None:
        items = {
            i.meal_kind: i
            for i in (
                await db.execute(select(RequestItem).where(RequestItem.request_id == req.id))
            ).scalars().all()
        }
        meal_type_id = req.meal_type_id
        version = req.version
        has_request = True
        going = {mk: (items[mk].is_going if mk in items else False) for mk in MealKind}
        reserve = {mk: (items[mk].is_reserve if mk in items else False) for mk in MealKind}
    else:
        rows = (
            await db.execute(
                select(UserMealDefault).where(UserMealDefault.user_id == user.id)
            )
        ).scalars().all()
        defaults = {r.meal_kind: r.is_going for r in rows}
        meal_type_id = user.default_meal_type_id
        version = None
        has_request = False
        going = {mk: defaults.get(mk, False) for mk in MealKind}
        reserve = {mk: False for mk in MealKind}

    deadline_at = await deadline.deadline_for(db, day_date)
    locked = await deadline.is_locked(db, day_date, now=now)

    return DayState(
        date=day_date,
        meal_type_id=meal_type_id,
        items=[
            MealState(
                meal_kind=mk,
                is_served=served[mk],
                is_going=going[mk],
                is_reserve=reserve[mk],
            )
            for mk in MealKind
        ],
        version=version,
        has_request=has_request,
        deadline_at=deadline_at,
        editable=not locked,
    )
```

- [ ] **Step 4: Прогнать — PASS.**

- [ ] **Step 5: Commit**

```bash
git add server/app/services/day_view.py server/tests/test_day_view_service.py
git commit -m "feat: add effective day state read service"
```

---

### Task 3: Запись дня (заявка, дедлайн, резерв, версия)

**Files:**
- Create: `server/app/services/requests.py`, `server/tests/test_requests_service.py`

**Interfaces:**
- Consumes: `access`, `deadline`, модели `Request`, `RequestItem`, `MealType`, `UserMealDefault`.
- Produces: `DayLocked`, `VersionConflict`, `MealTypeInvalid`, `save_day(db, *, actor, target, day_date, meal_type_id, meals, version) -> Request`.

- [ ] **Step 1: Написать падающий тест `tests/test_requests_service.py`**

```python
import datetime as dt
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, RequestItem, User, UserHall,
    UserMealDefault, UserRole,
)
from app.services import requests as svc
from app.services import settings as settings_service

TZ = ZoneInfo("Europe/Moscow")
DAY = dt.date(2026, 10, 10)


async def _setup(db_session, *, k=2, h=time(13, 0)):
    op = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    eater = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([op, hall, mt, eater])
    await db_session.flush()
    db_session.add(UserHall(user_id=eater.id, hall_id=hall.id))
    eater.default_meal_type_id = mt.id
    day = Day(date=DAY)
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True))
    db_session.add(UserMealDefault(user_id=eater.id, meal_kind=MealKind.breakfast, is_going=True))
    await settings_service.update_settings(
        db_session, actor_id=op.id, deadline_offset_days=k, deadline_time=h
    )
    await db_session.flush()
    return op, hall, mt, eater


async def _items(db_session, request_id):
    from sqlalchemy import select

    rows = (await db_session.execute(
        select(RequestItem).where(RequestItem.request_id == request_id)
    )).scalars().all()
    return {r.meal_kind: r for r in rows}


async def test_lazy_create_from_defaults(db_session):
    op, hall, mt, eater = await _setup(db_session)
    # до дедлайна
    now = dt.datetime(2026, 10, 8, 14, 0, tzinfo=TZ)
    req = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={MealKind.lunch: True}, version=None,
    )
    assert req.version == 1
    items = await _items(db_session, req.id)
    assert items[MealKind.breakfast].is_going is True   # из дефолтов
    assert items[MealKind.lunch].is_going is True
    assert items[MealKind.dinner].is_going is False
    assert all(i.is_reserve is False for i in items.values())


async def test_eater_locked_after_deadline(db_session):
    op, hall, mt, eater = await _setup(db_session, k=2, h=time(13, 0))
    # now после дедлайна (дедлайн 08.10 13:00) -> сымитируем через реальное "сейчас"
    # используем day в прошлом, чтобы дедлайн точно прошёл
    past_day = dt.date(2020, 1, 1)
    with pytest.raises(svc.DayLocked):
        await svc.save_day(
            db_session, actor=eater, target=eater, day_date=past_day,
            meal_type_id=mt.id, meals={MealKind.lunch: True}, version=None,
        )


async def test_version_conflict(db_session):
    op, hall, mt, eater = await _setup(db_session)
    req = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={}, version=None,
    )
    with pytest.raises(svc.VersionConflict):
        await svc.save_day(
            db_session, actor=eater, target=eater, day_date=DAY,
            meal_type_id=mt.id, meals={MealKind.dinner: True}, version=999,
        )
    # верная версия — ок, версия растёт
    req2 = await svc.save_day(
        db_session, actor=eater, target=eater, day_date=DAY,
        meal_type_id=mt.id, meals={MealKind.dinner: True}, version=req.version,
    )
    assert req2.version == req.version + 1


async def test_admin_edit_after_deadline_sets_reserve(db_session):
    op, hall, mt, eater = await _setup(db_session)
    admin = User(login="adm", password_hash="x", full_name="Админ", role=UserRole.admin)
    db_session.add(admin)
    await db_session.flush()
    db_session.add(UserHall(user_id=admin.id, hall_id=hall.id))
    await db_session.flush()

    # создаём заявку в прошлом через админа после дедлайна -> резерв
    past = dt.date(2020, 1, 1)
    day = Day(date=past)
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True))
    await db_session.flush()

    req = await svc.save_day(
        db_session, actor=admin, target=eater, day_date=past,
        meal_type_id=mt.id, meals={MealKind.dinner: True}, version=None,
    )
    items = await _items(db_session, req.id)
    assert items[MealKind.dinner].is_reserve is True
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test_b3" uv run pytest tests/test_requests_service.py -v`

- [ ] **Step 3: Написать `app/services/requests.py`**

```python
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MealKind, MealType, Request, RequestItem, User, UserMealDefault, UserRole,
)
from app.services import access, audit, deadline


class DayLocked(Exception):
    pass


class VersionConflict(Exception):
    pass


class MealTypeInvalid(Exception):
    pass


def _apply_meals(
    items: dict[MealKind, RequestItem], meals: dict[MealKind, bool], *, reserve_changes: bool
) -> None:
    for meal_kind, going in meals.items():
        item = items.get(meal_kind)
        if item is None:
            continue
        if not going:
            item.is_going = False
            item.is_reserve = False
        else:
            if reserve_changes and item.is_going is False:
                item.is_reserve = True
            item.is_going = True


def _mark_all_going_reserve(items: dict[MealKind, RequestItem]) -> None:
    for item in items.values():
        if item.is_going:
            item.is_reserve = True


async def _load_items(db: AsyncSession, request_id: uuid.UUID) -> dict[MealKind, RequestItem]:
    rows = (
        await db.execute(select(RequestItem).where(RequestItem.request_id == request_id))
    ).scalars().all()
    return {r.meal_kind: r for r in rows}


async def save_day(
    db: AsyncSession, *, actor: User, target: User, day_date: date,
    meal_type_id: uuid.UUID | None, meals: dict[MealKind, bool], version: int | None,
) -> Request:
    await access.ensure_can_edit_user(db, actor=actor, target=target)

    locked = await deadline.is_locked(db, day_date)
    is_admin_edit = actor.id != target.id and actor.role == UserRole.admin
    if locked and not is_admin_edit:
        raise DayLocked()
    reserve_changes = is_admin_edit and locked

    if meal_type_id is not None:
        mt = await db.get(MealType, meal_type_id)
        if mt is None or not mt.is_active:
            raise MealTypeInvalid(str(meal_type_id))

    req = (
        await db.execute(
            select(Request)
            .where(Request.user_id == target.id, Request.date == day_date)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if req is None:
        type_for_day = meal_type_id if meal_type_id is not None else target.default_meal_type_id
        req = Request(user_id=target.id, date=day_date, meal_type_id=type_for_day, version=1)
        db.add(req)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise VersionConflict()

        defaults_rows = (
            await db.execute(
                select(UserMealDefault).where(UserMealDefault.user_id == target.id)
            )
        ).scalars().all()
        defaults = {r.meal_kind: r.is_going for r in defaults_rows}
        items = {}
        for meal_kind in MealKind:
            item = RequestItem(
                request_id=req.id,
                meal_kind=meal_kind,
                is_going=defaults.get(meal_kind, False),
                is_reserve=False,
            )
            db.add(item)
            items[meal_kind] = item
        await db.flush()

        if reserve_changes and meal_type_id is not None and meal_type_id != target.default_meal_type_id:
            _mark_all_going_reserve(items)
        _apply_meals(items, meals, reserve_changes=reserve_changes)
        await db.flush()
    else:
        if version is None or version != req.version:
            raise VersionConflict()
        items = await _load_items(db, req.id)

        if meal_type_id is not None and meal_type_id != req.meal_type_id:
            if reserve_changes:
                _mark_all_going_reserve(items)
            req.meal_type_id = meal_type_id
        _apply_meals(items, meals, reserve_changes=reserve_changes)
        req.version = req.version + 1
        await db.flush()

    await audit.record(
        db, actor_id=actor.id, action="save_day", entity_type="request",
        entity_id=str(req.id),
        details={"user_id": str(target.id), "date": day_date.isoformat(),
                 "reserve": reserve_changes, "by_admin": is_admin_edit},
    )
    return req
```

- [ ] **Step 4: Прогнать — PASS.**

- [ ] **Step 5: Commit**

```bash
git add server/app/services/requests.py server/tests/test_requests_service.py
git commit -m "feat: add day save service with deadline, reserve and versioning"
```

---

### Task 4: Дефолты — сервис

**Files:**
- Create: `server/app/services/defaults.py`, `server/tests/test_defaults_service.py`

**Interfaces:**
- Produces: `Defaults` (dataclass), `get_defaults(db, user) -> Defaults`, `update_defaults(db, *, actor_id, user, meal_type_id, meals) -> None`.

- [ ] **Step 1: Написать падающий тест `tests/test_defaults_service.py`**

```python
import pytest
from sqlalchemy import select

from app.models import MealKind, MealType, UserMealDefault, User, UserRole
from app.services import defaults as svc


async def test_get_and_update_defaults(db_session):
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([mt, user])
    await db_session.flush()

    d = await svc.get_defaults(db_session, user)
    assert d.meal_type_id is None
    assert d.meals[MealKind.dinner] is False

    await svc.update_defaults(
        db_session, actor_id=user.id, user=user, meal_type_id=mt.id,
        meals={MealKind.breakfast: True, MealKind.lunch: True},
    )
    d2 = await svc.get_defaults(db_session, user)
    assert d2.meal_type_id == mt.id
    assert d2.meals[MealKind.breakfast] is True
    assert d2.meals[MealKind.breakfast] and d2.meals[MealKind.dinner] is False

    rows = (await db_session.execute(
        select(UserMealDefault).where(UserMealDefault.user_id == user.id)
    )).scalars().all()
    assert len(rows) == 4


async def test_invalid_meal_type(db_session):
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add(user)
    await db_session.flush()
    import uuid

    with pytest.raises(svc.MealTypeInvalid):
        await svc.update_defaults(
            db_session, actor_id=user.id, user=user, meal_type_id=uuid.uuid4(),
            meals={MealKind.breakfast: True},
        )
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test" uv run pytest tests/test_defaults_service.py -v`

- [ ] **Step 3: Написать `app/services/defaults.py`**

```python
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MealKind, MealType, User, UserMealDefault
from app.services import audit


@dataclass
class Defaults:
    meal_type_id: uuid.UUID | None
    meals: dict[MealKind, bool]


class MealTypeInvalid(Exception):
    pass


async def get_defaults(db: AsyncSession, user: User) -> Defaults:
    rows = (
        await db.execute(select(UserMealDefault).where(UserMealDefault.user_id == user.id))
    ).scalars().all()
    stored = {r.meal_kind: r.is_going for r in rows}
    return Defaults(
        meal_type_id=user.default_meal_type_id,
        meals={mk: stored.get(mk, False) for mk in MealKind},
    )


async def update_defaults(
    db: AsyncSession, *, actor_id: uuid.UUID, user: User,
    meal_type_id: uuid.UUID | None, meals: dict[MealKind, bool],
) -> None:
    if meal_type_id is not None:
        mt = await db.get(MealType, meal_type_id)
        if mt is None or not mt.is_active:
            raise MealTypeInvalid(str(meal_type_id))
        user.default_meal_type_id = meal_type_id

    rows = {
        r.meal_kind: r
        for r in (
            await db.execute(select(UserMealDefault).where(UserMealDefault.user_id == user.id))
        ).scalars().all()
    }
    # Пишем ровно по одной строке на каждый приём (не только переданные),
    # чтобы get_defaults был детерминированным.
    for meal_kind in MealKind:
        going = meals.get(meal_kind, False)
        row = rows.get(meal_kind)
        if row is None:
            db.add(UserMealDefault(user_id=user.id, meal_kind=meal_kind, is_going=going))
        else:
            row.is_going = going
    await db.flush()

    await audit.record(
        db, actor_id=actor_id, action="update_defaults", entity_type="user",
        entity_id=str(user.id),
        details={"meal_type_id": str(meal_type_id) if meal_type_id else None},
    )
```

- [ ] **Step 4: Прогнать — PASS.**

- [ ] **Step 5: Commit**

```bash
git add server/app/services/defaults.py server/tests/test_defaults_service.py
git commit -m "feat: add user defaults service"
```

---

### Task 5: HTTP — `/me` и `/admin`

**Files:**
- Create: `server/app/schemas/request.py`, `server/app/api/v1/routers/me.py`, `server/app/api/v1/routers/admin.py`
- Modify: `server/app/api/v1/router.py`
- Create: `server/tests/test_me_api.py`, `server/tests/test_admin_api.py`

**Interfaces:**
- Consumes: `services.day_view`, `services.requests`, `services.defaults`, `services.access`, `deps.get_current_user`, `deps.require_roles`.
- Produces: эндпоинты `/api/v1/me/*` и `/api/v1/admin/*`.

- [ ] **Step 1: Написать `app/schemas/request.py`**

```python
import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import MealKind
from app.schemas.user import UserOut


class MealStateOut(BaseModel):
    meal_kind: MealKind
    is_served: bool
    is_going: bool
    is_reserve: bool


class DayStateOut(BaseModel):
    date: date
    meal_type_id: uuid.UUID | None
    items: list[MealStateOut]
    version: int | None
    has_request: bool
    deadline_at: datetime
    editable: bool


class DayUpdateRequest(BaseModel):
    meal_type_id: uuid.UUID | None = None
    meals: dict[MealKind, bool] = {}
    version: int | None = None


class DefaultsOut(BaseModel):
    default_meal_type_id: uuid.UUID | None
    meals: dict[MealKind, bool]


class DefaultsUpdate(BaseModel):
    default_meal_type_id: uuid.UUID | None = None
    meals: dict[MealKind, bool]


class AdminUserOut(UserOut):
    hall_ids: list[uuid.UUID] = []


class AdminDayOut(BaseModel):
    user: UserOut
    day: DayStateOut
```

- [ ] **Step 2: Написать `app/api/v1/routers/me.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.request import (
    DayStateOut, DayUpdateRequest, DefaultsOut, DefaultsUpdate, MealStateOut,
)
from app.services import day_view, defaults, requests

router = APIRouter(prefix="/me", tags=["me"])


def _day_out(state: day_view.DayState) -> DayStateOut:
    return DayStateOut(
        date=state.date,
        meal_type_id=state.meal_type_id,
        items=[MealStateOut(**vars(i)) for i in state.items],
        version=state.version,
        has_request=state.has_request,
        deadline_at=state.deadline_at,
        editable=state.editable,
    )


async def _defaults_out(db: AsyncSession, user: User) -> DefaultsOut:
    d = await defaults.get_defaults(db, user)
    return DefaultsOut(default_meal_type_id=d.meal_type_id, meals=d.meals)


@router.get("/defaults", response_model=DefaultsOut)
async def get_defaults(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await _defaults_out(db, user)


@router.put("/defaults", response_model=DefaultsOut)
async def update_defaults(payload: DefaultsUpdate, db: AsyncSession = Depends(get_db),
                          user: User = Depends(get_current_user)):
    try:
        await defaults.update_defaults(
            db, actor_id=user.id, user=user,
            meal_type_id=payload.default_meal_type_id, meals=payload.meals,
        )
    except defaults.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    return await _defaults_out(db, user)


@router.get("/calendar", response_model=list[DayStateOut])
async def calendar(from_: date = Query(alias="from"), to: date = Query(...),
                   db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = []
    current = from_
    while current <= to:
        result.append(_day_out(await day_view.get_day_state(db, user=user, day_date=current)))
        current = current.fromordinal(current.toordinal() + 1)
    return result


@router.put("/days/{day_date}", response_model=DayStateOut)
async def save_day(day_date: date, payload: DayUpdateRequest,
                   db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        await requests.save_day(
            db, actor=user, target=user, day_date=day_date,
            meal_type_id=payload.meal_type_id, meals=payload.meals, version=payload.version,
        )
    except requests.DayLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="day_locked")
    except requests.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    except requests.VersionConflict:
        state = await day_view.get_day_state(db, user=user, day_date=day_date)
        return JSONResponse(status_code=409, content={"detail": "record_changed",
                                                      "current": _day_out(state).model_dump(mode="json")})
    await db.commit()
    state = await day_view.get_day_state(db, user=user, day_date=day_date)
    return _day_out(state)
```

> Добавить импорт: `from fastapi.responses import JSONResponse`.

- [ ] **Step 3: Написать `app/api/v1/routers/admin.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.repositories import users as users_repo
from app.schemas.request import AdminDayOut, AdminUserOut, DayStateOut, DayUpdateRequest, MealStateOut
from app.services import access, day_view, requests

router = APIRouter(prefix="/admin", tags=["admin"])
_guard = require_roles(UserRole.admin, UserRole.operator)


def _day_out(state: day_view.DayState) -> DayStateOut:
    return DayStateOut(
        date=state.date, meal_type_id=state.meal_type_id,
        items=[MealStateOut(**vars(i)) for i in state.items],
        version=state.version, has_request=state.has_request,
        deadline_at=state.deadline_at, editable=state.editable,
    )


async def _assert_hall_access(db: AsyncSession, actor: User, hall_id) -> None:
    if actor.role == UserRole.operator:
        return
    if hall_id not in await access.hall_ids_of(db, actor.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="hall_forbidden")


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(hall_id=None, db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    if hall_id is not None:
        await _assert_hall_access(db, actor, hall_id)
    users = await users_repo.list_all(
        db, role=UserRole.eater, hall_id=hall_id,
        only_active=True,
    )
    if hall_id is None and actor.role == UserRole.admin:
        allowed = await access.hall_ids_of(db, actor.id)
        users = [
            u for u in users
            if await users_repo.hall_ids_of(db, u.id) & allowed
        ]
    out = []
    for u in users:
        o = AdminUserOut.model_validate(u)
        o.hall_ids = sorted(await users_repo.hall_ids_of(db, u.id))
        out.append(o)
    return out


@router.get("/requests", response_model=list[AdminDayOut])
async def requests_for_day(day_date: date, hall_id, db: AsyncSession = Depends(get_db),
                           actor: User = Depends(_guard)):
    await _assert_hall_access(db, actor, hall_id)
    users = await users_repo.list_all(db, role=UserRole.eater, hall_id=hall_id, only_active=True)
    out = []
    for u in users:
        state = await day_view.get_day_state(db, user=u, day_date=day_date)
        out.append(AdminDayOut(user=u, day=_day_out(state)))
    return out


@router.put("/requests/{user_id}/{day_date}", response_model=DayStateOut)
async def save_for_user(user_id, day_date: date, payload: DayUpdateRequest,
                        db: AsyncSession = Depends(get_db), actor: User = Depends(_guard)):
    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    try:
        await requests.save_day(
            db, actor=actor, target=target, day_date=day_date,
            meal_type_id=payload.meal_type_id, meals=payload.meals, version=payload.version,
        )
    except access.AccessDenied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    except requests.DayLocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="day_locked")
    except requests.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    except requests.VersionConflict:
        state = await day_view.get_day_state(db, user=target, day_date=day_date)
        return JSONResponse(status_code=409, content={"detail": "record_changed",
                                                      "current": _day_out(state).model_dump(mode="json")})
    await db.commit()
    state = await day_view.get_day_state(db, user=target, day_date=day_date)
    return _day_out(state)


@router.put("/users/{user_id}/defaults")
async def update_user_defaults(user_id, payload, db: AsyncSession = Depends(get_db),
                               actor: User = Depends(_guard)):
    from app.services import defaults as defaults_svc

    target = await users_repo.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    await access.ensure_can_edit_user(db, actor=actor, target=target)
    try:
        await defaults_svc.update_defaults(
            db, actor_id=actor.id, user=target,
            meal_type_id=payload.default_meal_type_id, meals=payload.meals,
        )
    except access.AccessDenied:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    except defaults_svc.MealTypeInvalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid_meal_type")
    await db.commit()
    d = await defaults_svc.get_defaults(db, target)
    return {"default_meal_type_id": d.meal_type_id, "meals": {k.value: v for k, v in d.meals.items()}}
```

> Типизируй пути (`uuid.UUID`) и тело (`payload: DefaultsUpdate`) через импорты `uuid` и `app.schemas.request.DefaultsUpdate`; сигнатуры выше — для наглядности, приведи к аннотированному виду.

- [ ] **Step 4: Включить роутеры в `app/api/v1/router.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers import admin, auth, me
from app.api.v1.routers.operator import operator_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
api_router.include_router(operator_router)
```

- [ ] **Step 5: Написать `tests/test_me_api.py`**

```python
import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, MealKind, MealType, User, UserHall, UserRole

FP = "dev-1"


@pytest.fixture
async def eater_headers(client, db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash=hash_password("pass"),
                full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "ivan", "password": "pass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_defaults_get_and_put(client, eater_headers):
    r = await client.get("/api/v1/me/defaults", headers=eater_headers)
    assert r.status_code == 200
    assert r.json()["default_meal_type_id"] is not None

    r = await client.put("/api/v1/me/defaults", headers=eater_headers, json={
        "meals": {"breakfast": True, "lunch": True, "snack": False, "dinner": False},
    })
    assert r.status_code == 200
    assert r.json()["meals"]["breakfast"] is True


async def test_save_day_lazy_request_and_lock(client, eater_headers):
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
    r = await client.put(f"/api/v1/me/days/{future}", headers=eater_headers, json={
        "meals": {"breakfast": True}, "version": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["has_request"] is True and body["version"] == 1

    # конфликт версий
    r = await client.put(f"/api/v1/me/days/{future}", headers=eater_headers, json={
        "meals": {"dinner": True}, "version": 999,
    })
    assert r.status_code == 409
    assert r.json()["detail"] == "record_changed"

    # прошлый день -> заблокировано
    past = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    r = await client.put(f"/api/v1/me/days/{past}", headers=eater_headers, json={"meals": {}})
    assert r.status_code == 403
```

- [ ] **Step 6: Написать `tests/test_admin_api.py`**

```python
import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, User, UserHall, UserRole

FP = "dev-1"


@pytest.fixture
async def admin_headers(client, db_session):
    hall = Hall(name="Зал №1")
    admin = User(login="adm", password_hash=hash_password("apass"),
                 full_name="Админ", role=UserRole.admin)
    eater = User(login="ivan", password_hash=hash_password("ipass"),
                 full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, admin, eater])
    await db_session.flush()
    db_session.add_all([
        UserHall(user_id=admin.id, hall_id=hall.id),
        UserHall(user_id=eater.id, hall_id=hall.id),
    ])
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "adm", "password": "apass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}, hall.id


async def test_admin_lists_eaters_of_hall(client, admin_headers):
    headers, hall_id = admin_headers
    r = await client.get(f"/api/v1/admin/users?hall_id={hall_id}", headers=headers)
    assert r.status_code == 200
    logins = [u["login"] for u in r.json()]
    assert "ivan" in logins


async def test_admin_edits_eater_future_day(client, admin_headers):
    headers, hall_id = admin_headers
    r = await client.get(f"/api/v1/admin/users?hall_id={hall_id}", headers=headers)
    user_id = r.json()[0]["id"]
    future = (dt.date.today() + dt.timedelta(days=30)).isoformat()

    r = await client.put(f"/api/v1/admin/requests/{user_id}/{future}", headers=headers,
                         json={"meals": {"breakfast": True}, "version": None})
    assert r.status_code == 200
    assert r.json()["has_request"] is True
```

- [ ] **Step 7: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test" uv run pytest -v
```
Expected: весь набор PASS.

- [ ] **Step 8: Commit**

```bash
git add server/app/schemas/request.py server/app/api/v1/routers/me.py server/app/api/v1/routers/admin.py server/app/api/v1/router.py server/tests/test_me_api.py server/tests/test_admin_api.py
git commit -m "feat: add me and admin marking endpoints"
```

---

## Self-Review (автора плана)

- **Покрытие спеки:** §4 (`requests`, `request_items`) — Task 1; §6 (дедлайн, резерв, эффективные значения) — Tasks 1–3; §8 (ленивое создание, заявки не удаляются) — Task 3; §9 (версия на заявку, `409` + `current`) — Task 3 + Task 5; §10.2/§10.3 (`/me`, `/admin`) — Task 5.
- **Изоляция волн:** T1 (модели+дедлайн+права) → затем T2/T3/T4 параллельно (читают модели напрямую, без взаимных импортов) → T5 (HTTP).
- **Плейсхолдеров нет:** код и команды приведены; в Task 5 есть примечания «приведи аннотации к видам», но конкретный код дан.
- **Согласованность имён:** `save_day`, `get_day_state`, `DayState`, `MealState`, `update_defaults`, `ensure_can_edit_user`, `deadline_for`, `is_locked` — одинаковы в сервисах, роутерах и тестах.
- **Риск:** тест `test_eater_locked_after_deadline` использует дату в прошлом (2020-01-01), т.к. дедлайн вычисляется от реального «сейчас»; это надёжно.

## Следующие фазы

- **Фаза 5 — Reports:** дневной и за период.
- **Фаза 6 — Logs cleanup & Docker:** просмотр/очистка логов, Dockerfile/compose.
