# Трапезная МДА — Backend, фаза 3: Schedule Rules & Calendar — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить правила расписания (повторяющиеся/одноразовые, привязанные к залам), каркас календаря (`days`) со снимком доступности приёмов (`day_hall_meals`), генерацию/перегенерацию горизонта и ежедневную фоновую задачу (APScheduler).

**Architecture:** Продолжение слоистого монолита. Правила — отдельные сущности, назначаемые на залы. Генерация **материализует** доступность приёмов на дату по текущим правилам (снимок). Делит ответственность: `services/schedule_rules.py` (CRUD правил) и `services/calendar.py` (генерация, читает модели правил напрямую — без импорта сервиса правил). Фон — APScheduler в `app/jobs/`.

**Tech Stack:** те же + `apscheduler`.

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md` (§4, §7, §12)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-backend-phase-2-reference-operator.md`

## Global Constraints

- Все PK — `UUID` (`uuid.uuid4`), кроме составных PK в связующих таблицах.
- `created_at`/`updated_at` — `DateTime(timezone=True)`, `server_default=func.now()`, `updated_at.onupdate=func.now()`.
- Enum `meal_kind` уже существует (фаза 2) — переиспользуем, не создаём заново.
- Мутации правил вызывают `services.audit.record(...)`.
- Все эндпоинты — под `require_roles(UserRole.operator)`.
- Правила только **выключают** приёмы; конфликтов «вкл/выкл» нет.
- База: все приёмы `is_served = true`, затем активные правила выключают указанные приёмы.
- Горизонт перегенерации: `[today .. today + N]`; прошедшие даты (`< today`) не трогаем.
- Инварианты правил: `recurring` — непустые `weekdays`, пустые `dates`; `one_off` — непустые `dates`, пустые `weekdays`; непустые `meal_kinds` и `hall_ids` (все активные залы).

## Дерево файлов фазы 3

```
server/app/
  models/
    schedule_rule.py        # NEW (RuleKind + 5 таблиц)
    day.py                  # NEW (Day, DayHallMeal)
    enums.py                # MODIFY (добавить RuleKind)
    __init__.py             # MODIFY
  schemas/
    schedule_rule.py        # NEW
    calendar.py             # NEW
  repositories/
    schedule_rules.py       # NEW
    calendar.py             # NEW
  services/
    schedule_rules.py       # NEW
    calendar.py             # NEW
  jobs/
    __init__.py             # NEW
    scheduler.py            # NEW
    maintenance.py          # NEW
  api/v1/routers/operator/
    schedule_rules.py       # NEW
    days.py                 # NEW
    __init__.py             # MODIFY
  main.py                   # MODIFY (lifespan: догон + запуск планировщика)
server/tests/
    test_schedule_rules_service.py  # NEW
    test_calendar_service.py        # NEW
    test_scheduler.py               # NEW
    test_schedule_api.py            # NEW
```

**Interfaces, которые фаза отдаёт дальше:**
- `services/schedule_rules.py`: `create_rule`, `list_rules`, `update_rule`, `deactivate_rule`; исключения `InvalidRule`, `RuleNotFound`.
- `services/calendar.py`: `regenerate_range(db, start, end)`, `regenerate_horizon(db)`, `materialize_day(db, date)`.
- `jobs/maintenance.py`: `run_daily_maintenance()`.
- `jobs/scheduler.py`: `create_scheduler()`, `start_scheduler()`, `shutdown_scheduler()`.

---

### Task 1: Модели правил и календаря + миграция

**Files:**
- Modify: `server/app/models/enums.py` (добавить `RuleKind`)
- Create: `server/app/models/schedule_rule.py`, `server/app/models/day.py`
- Modify: `server/app/models/__init__.py`
- Create: `server/tests/test_phase3_models.py`
- Create (generated): `server/alembic/versions/<rev>_phase3_schedule.py`

**Interfaces:**
- Produces: `RuleKind`, `ScheduleRule`, `ScheduleRuleWeekday`, `ScheduleRuleDate`, `ScheduleRuleMeal`, `ScheduleRuleHall`, `Day`, `DayHallMeal`.

- [ ] **Step 1: Добавить `RuleKind` в `app/models/enums.py`**

```python
class RuleKind(str, enum.Enum):
    recurring = "recurring"
    one_off = "one_off"
```

- [ ] **Step 2: Написать `app/models/schedule_rule.py`**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind, RuleKind


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[RuleKind] = mapped_column(Enum(RuleKind, name="rule_kind"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduleRuleWeekday(Base):
    __tablename__ = "schedule_rule_weekdays"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0=Mon .. 6=Sun


class ScheduleRuleDate(Base):
    __tablename__ = "schedule_rule_dates"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    specific_date: Mapped[date] = mapped_column(Date, primary_key=True)


class ScheduleRuleMeal(Base):
    __tablename__ = "schedule_rule_meals"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )


class ScheduleRuleHall(Base):
    __tablename__ = "schedule_rule_halls"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_rules.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 3: Написать `app/models/day.py`**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MealKind


class Day(Base):
    __tablename__ = "days"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DayHallMeal(Base):
    __tablename__ = "day_hall_meals"

    day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("days.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    meal_kind: Mapped[MealKind] = mapped_column(
        Enum(MealKind, name="meal_kind"), primary_key=True
    )
    is_served: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Обновить `app/models/__init__.py`** — добавить импорты `Day`, `DayHallMeal`, `RuleKind`, `ScheduleRule`, `ScheduleRuleDate`, `ScheduleRuleHall`, `ScheduleRuleMeal`, `ScheduleRuleWeekday` и их в `__all__`.

- [ ] **Step 5: Написать `tests/test_phase3_models.py`**

```python
import datetime as dt

from sqlalchemy import select

from app.models import (
    Day, DayHallMeal, Hall, MealKind, RuleKind, ScheduleRule,
    ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)


async def test_create_rule_with_children_and_day(db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    rule = ScheduleRule(kind=RuleKind.recurring)
    db_session.add(rule)
    await db_session.flush()
    db_session.add_all([
        ScheduleRuleWeekday(rule_id=rule.id, weekday=6),
        ScheduleRuleMeal(rule_id=rule.id, meal_kind=MealKind.breakfast),
        ScheduleRuleHall(rule_id=rule.id, hall_id=hall.id),
    ])
    await db_session.flush()

    day = Day(date=dt.date(2026, 10, 4))
    db_session.add(day)
    await db_session.flush()
    db_session.add(
        DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=MealKind.breakfast, is_served=False)
    )
    await db_session.flush()

    meals = (await db_session.execute(select(DayHallMeal))).scalars().all()
    assert len(meals) == 1 and meals[0].is_served is False
```

- [ ] **Step 6: Миграция**

```bash
cd server
uv run alembic revision --autogenerate -m "phase3 schedule and calendar"
uv run alembic upgrade head
docker exec mda_db psql -U mda -d mda -c "\dt"
```
Ожидаем: `schedule_rules`, `schedule_rule_weekdays`, `schedule_rule_dates`, `schedule_rule_meals`, `schedule_rule_halls`, `days`, `day_hall_meals`; enum `rule_kind`.
> Если в `downgrade()` нет дропа enum `rule_kind` — добавить `sa.Enum(name='rule_kind').drop(op.get_bind(), checkfirst=True)`.
> **При выполнении выяснилось:** при автогенерации колонки с уже существующим enum `meal_kind`
> генерируются как inline `sa.Enum(..., name='meal_kind')`, что падает на `upgrade()` с
> `DuplicateObjectError: type "meal_kind" already exists`. Заменять такие колонки на
> `postgresql.ENUM(..., name='meal_kind', create_type=False)`. Это же правило действует в фазе 4
> при переиспользовании `meal_kind` и `rule_kind`.

- [ ] **Step 7: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test_b1" uv run pytest -v
```

- [ ] **Step 8: Commit**

```bash
git add server/app/models server/tests/test_phase3_models.py server/alembic
git commit -m "feat: add phase3 schedule rule and calendar models"
```

---

### Task 2: Правила — сервис + схемы

**Files:**
- Create: `server/app/repositories/schedule_rules.py`, `server/app/services/schedule_rules.py`, `server/app/schemas/schedule_rule.py`, `server/tests/test_schedule_rules_service.py`

**Interfaces:**
- Produces:
  - `create_rule(db, *, actor_id, kind, meal_kinds, hall_ids, weekdays=None, dates=None) -> ScheduleRule`
  - `list_rules(db, *, only_active=False) -> list[ScheduleRule]`
  - `update_rule(db, *, actor_id, rule_id, is_active=None, meal_kinds=None, hall_ids=None, weekdays=None, dates=None) -> ScheduleRule`
  - `deactivate_rule(db, *, actor_id, rule_id) -> None`
- Исключения: `InvalidRule`, `RuleNotFound`.

- [ ] **Step 1: Написать падающий тест `tests/test_schedule_rules_service.py`**

```python
import datetime as dt

import pytest

from app.models import Hall, MealKind, RuleKind, ScheduleRuleHall, ScheduleRuleWeekday, User, UserRole
from app.services import schedule_rules


async def _actor_halls(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([actor, h1, h2])
    await db_session.flush()
    return actor, h1, h2


async def test_create_recurring_rule(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    rule = await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.recurring,
        meal_kinds=[MealKind.breakfast], hall_ids=[h1.id], weekdays=[6],
    )
    assert rule.kind == RuleKind.recurring
    wd = [w.weekday for w in await schedule_rules.get_weekdays(db_session, rule.id)]
    assert wd == [6]


async def test_recurring_requires_weekdays(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[MealKind.breakfast], hall_ids=[h1.id], weekdays=[], dates=[],
        )


async def test_one_off_requires_dates(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.one_off,
            meal_kinds=[MealKind.lunch], hall_ids=[h1.id], dates=[],
        )


async def test_requires_meals_and_halls(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[], hall_ids=[h1.id], weekdays=[6],
        )
    with pytest.raises(schedule_rules.InvalidRule):
        await schedule_rules.create_rule(
            db_session, actor_id=actor.id, kind=RuleKind.recurring,
            meal_kinds=[MealKind.breakfast], hall_ids=[], weekdays=[6],
        )


async def test_deactivate_rule(db_session):
    actor, h1, _ = await _actor_halls(db_session)
    rule = await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.one_off,
        meal_kinds=[MealKind.dinner], hall_ids=[h1.id], dates=[dt.date(2026, 1, 1)],
    )
    await schedule_rules.deactivate_rule(db_session, actor_id=actor.id, rule_id=rule.id)
    assert rule.is_active is False
    assert await schedule_rules.list_rules(db_session) == []
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test_b2" uv run pytest tests/test_schedule_rules_service.py -v`

- [ ] **Step 3: Написать `app/repositories/schedule_rules.py`**

```python
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ScheduleRule, ScheduleRuleDate, ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)


async def get(db: AsyncSession, rule_id: uuid.UUID) -> ScheduleRule | None:
    return await db.get(ScheduleRule, rule_id)


async def list_all(db: AsyncSession, *, only_active: bool) -> list[ScheduleRule]:
    stmt = select(ScheduleRule).order_by(ScheduleRule.created_at)
    if only_active:
        stmt = stmt.where(ScheduleRule.is_active.is_(True))
    return list((await db.execute(stmt)).scalars().all())


async def get_weekdays(db: AsyncSession, rule_id) -> list[ScheduleRuleWeekday]:
    stmt = select(ScheduleRuleWeekday).where(ScheduleRuleWeekday.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_dates(db: AsyncSession, rule_id) -> list[ScheduleRuleDate]:
    stmt = select(ScheduleRuleDate).where(ScheduleRuleDate.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_meals(db: AsyncSession, rule_id) -> list[ScheduleRuleMeal]:
    stmt = select(ScheduleRuleMeal).where(ScheduleRuleMeal.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_halls(db: AsyncSession, rule_id) -> list[ScheduleRuleHall]:
    stmt = select(ScheduleRuleHall).where(ScheduleRuleHall.rule_id == rule_id)
    return list((await db.execute(stmt)).scalars().all())


async def add(db: AsyncSession, rule: ScheduleRule) -> ScheduleRule:
    db.add(rule)
    await db.flush()
    return rule


async def clear_children(db: AsyncSession, rule_id) -> None:
    for model in (ScheduleRuleWeekday, ScheduleRuleDate, ScheduleRuleMeal, ScheduleRuleHall):
        await db.execute(delete(model).where(model.rule_id == rule_id))


async def add_weekdays(db, rule_id, weekdays):
    for wd in sorted(set(weekdays)):
        db.add(ScheduleRuleWeekday(rule_id=rule_id, weekday=wd))
    await db.flush()


async def add_dates(db, rule_id, dates):
    for d in sorted(set(dates)):
        db.add(ScheduleRuleDate(rule_id=rule_id, specific_date=d))
    await db.flush()


async def add_meals(db, rule_id, meal_kinds):
    for mk in sorted(set(meal_kinds), key=lambda m: m.value):
        db.add(ScheduleRuleMeal(rule_id=rule_id, meal_kind=mk))
    await db.flush()


async def add_halls(db, rule_id, hall_ids):
    for hid in sorted(set(hall_ids)):
        db.add(ScheduleRuleHall(rule_id=rule_id, hall_id=hid))
    await db.flush()
```

- [ ] **Step 4: Написать `app/services/schedule_rules.py`**

```python
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall, MealKind, RuleKind, ScheduleRule
from app.repositories import schedule_rules as repo
from app.services import audit


class InvalidRule(Exception):
    pass


class RuleNotFound(Exception):
    pass


async def get_weekdays(db, rule_id):
    return await repo.get_weekdays(db, rule_id)


async def get_dates(db, rule_id):
    return await repo.get_dates(db, rule_id)


async def get_meal_kinds(db, rule_id) -> list[MealKind]:
    return [m.meal_kind for m in await repo.get_meals(db, rule_id)]


async def get_hall_ids(db, rule_id) -> list[uuid.UUID]:
    return [h.hall_id for h in await repo.get_halls(db, rule_id)]


def _validate(
    kind: RuleKind,
    meal_kinds: list[MealKind],
    hall_ids: list[uuid.UUID],
    weekdays: list[int] | None,
    dates: list[date] | None,
) -> None:
    if not meal_kinds:
        raise InvalidRule("meal_kinds must be non-empty")
    if not hall_ids:
        raise InvalidRule("hall_ids must be non-empty")
    if kind == RuleKind.recurring:
        if not weekdays:
            raise InvalidRule("recurring rule requires weekdays")
        if dates:
            raise InvalidRule("recurring rule must not have dates")
        if any(not (0 <= w <= 6) for w in weekdays):
            raise InvalidRule("weekday must be 0..6")
    else:  # one_off
        if not dates:
            raise InvalidRule("one_off rule requires dates")
        if weekdays:
            raise InvalidRule("one_off rule must not have weekdays")


async def _validate_halls(db: AsyncSession, hall_ids: list[uuid.UUID]) -> None:
    for hid in set(hall_ids):
        hall = await db.get(Hall, hid)
        if hall is None or not hall.is_active:
            raise InvalidRule(f"hall {hid} not found or inactive")


async def create_rule(
    db: AsyncSession, *, actor_id: uuid.UUID, kind: RuleKind,
    meal_kinds: list[MealKind], hall_ids: list[uuid.UUID],
    weekdays: list[int] | None = None, dates: list[date] | None = None,
) -> ScheduleRule:
    _validate(kind, meal_kinds, hall_ids, weekdays, dates)
    await _validate_halls(db, hall_ids)

    rule = await repo.add(db, ScheduleRule(kind=kind))
    if kind == RuleKind.recurring:
        await repo.add_weekdays(db, rule.id, weekdays or [])
    else:
        await repo.add_dates(db, rule.id, dates or [])
    await repo.add_meals(db, rule.id, meal_kinds)
    await repo.add_halls(db, rule.id, hall_ids)

    await audit.record(
        db, actor_id=actor_id, action="create", entity_type="schedule_rule",
        entity_id=str(rule.id),
        details={"kind": kind.value, "meals": [m.value for m in meal_kinds],
                 "halls": [str(h) for h in hall_ids]},
    )
    return rule


async def list_rules(db: AsyncSession, *, only_active: bool = True) -> list[ScheduleRule]:
    return await repo.list_all(db, only_active=only_active)


async def update_rule(
    db: AsyncSession, *, actor_id: uuid.UUID, rule_id: uuid.UUID,
    is_active: bool | None = None, meal_kinds: list[MealKind] | None = None,
    hall_ids: list[uuid.UUID] | None = None, weekdays: list[int] | None = None,
    dates: list[date] | None = None,
) -> ScheduleRule:
    rule = await repo.get(db, rule_id)
    if rule is None:
        raise RuleNotFound(str(rule_id))

    cur_meals = meal_kinds if meal_kinds is not None else await get_meal_kinds(db, rule_id)
    cur_halls = hall_ids if hall_ids is not None else await get_hall_ids(db, rule_id)
    cur_weekdays = weekdays if weekdays is not None else [w.weekday for w in await repo.get_weekdays(db, rule_id)]
    cur_dates = dates if dates is not None else [d.specific_date for d in await repo.get_dates(db, rule_id)]
    _validate(rule.kind, cur_meals, cur_halls, cur_weekdays, cur_dates)
    await _validate_halls(db, cur_halls)

    if is_active is not None:
        rule.is_active = is_active
    if meal_kinds is not None or hall_ids is not None or weekdays is not None or dates is not None:
        await repo.clear_children(db, rule_id)
        if rule.kind == RuleKind.recurring:
            await repo.add_weekdays(db, rule_id, cur_weekdays)
        else:
            await repo.add_dates(db, rule_id, cur_dates)
        await repo.add_meals(db, rule_id, cur_meals)
        await repo.add_halls(db, rule_id, cur_halls)
    await db.flush()

    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="schedule_rule",
        entity_id=str(rule.id), details={"is_active": rule.is_active},
    )
    return rule


async def deactivate_rule(db: AsyncSession, *, actor_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await repo.get(db, rule_id)
    if rule is None:
        raise RuleNotFound(str(rule_id))
    rule.is_active = False
    await db.flush()
    await audit.record(
        db, actor_id=actor_id, action="delete", entity_type="schedule_rule",
        entity_id=str(rule.id), details={"soft": True},
    )
```

- [ ] **Step 5: Написать `app/schemas/schedule_rule.py`**

```python
import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import MealKind, RuleKind


class ScheduleRuleCreate(BaseModel):
    kind: RuleKind
    meal_kinds: list[MealKind] = Field(min_length=1)
    hall_ids: list[uuid.UUID] = Field(min_length=1)
    weekdays: list[int] = []
    dates: list[date] = []


class ScheduleRuleUpdate(BaseModel):
    is_active: bool | None = None
    meal_kinds: list[MealKind] | None = None
    hall_ids: list[uuid.UUID] | None = None
    weekdays: list[int] | None = None
    dates: list[date] | None = None


class ScheduleRuleOut(BaseModel):
    id: uuid.UUID
    kind: RuleKind
    is_active: bool
    meal_kinds: list[MealKind]
    hall_ids: list[uuid.UUID]
    weekdays: list[int]
    dates: list[date]
```

- [ ] **Step 6: Прогнать — PASS** (команда из Step 2).

- [ ] **Step 7: Commit**

```bash
git add server/app/repositories/schedule_rules.py server/app/services/schedule_rules.py server/app/schemas/schedule_rule.py server/tests/test_schedule_rules_service.py
git commit -m "feat: add schedule rules service and schemas"
```

---

### Task 3: Календарь — генерация и перегенерация

**Files:**
- Create: `server/app/repositories/calendar.py`, `server/app/services/calendar.py`, `server/tests/test_calendar_service.py`

**Interfaces:**
- Consumes: модели `Day`, `DayHallMeal`, `Hall`, `ScheduleRule*`, `services/settings.get_settings`.
- Produces:
  - `materialize_day(db, date) -> None`
  - `regenerate_range(db, start: date, end: date) -> None`
  - `regenerate_horizon(db) -> None`
- **Важно:** сервис календаря читает модели правил **напрямую** (не импортирует `services/schedule_rules`).

- [ ] **Step 1: Написать падающий тест `tests/test_calendar_service.py`**

```python
import datetime as dt

from sqlalchemy import select

from app.models import (
    DayHallMeal, Hall, MealKind, RuleKind, User, UserRole,
)
from app.services import calendar, schedule_rules


async def _actor(db_session):
    u = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    db_session.add(u)
    await db_session.flush()
    return u


async def _served(db_session, day_date, hall_id, meal_kind) -> bool:
    from app.models import Day

    day = (await db_session.execute(select(Day).where(Day.date == day_date))).scalar_one()
    row = (await db_session.execute(
        select(DayHallMeal).where(
            DayHallMeal.day_id == day.id,
            DayHallMeal.hall_id == hall_id,
            DayHallMeal.meal_kind == meal_kind,
        )
    )).scalar_one()
    return row.is_served


async def test_recurring_rule_disables_meal_on_weekday(db_session):
    actor = await _actor(db_session)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    sunday = dt.date(2026, 10, 4)  # воскресенье
    assert sunday.weekday() == 6
    await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.recurring,
        meal_kinds=[MealKind.breakfast], hall_ids=[hall.id], weekdays=[6],
    )

    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is False
    assert await _served(db_session, sunday, hall.id, MealKind.lunch) is True

    monday = dt.date(2026, 10, 5)
    await calendar.regenerate_range(db_session, monday, monday)
    assert await _served(db_session, monday, hall.id, MealKind.breakfast) is True


async def test_one_off_rule_disables_all_meals_on_date(db_session):
    actor = await _actor(db_session)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    holiday = dt.date(2026, 1, 1)
    await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.one_off,
        meal_kinds=list(MealKind), hall_ids=[hall.id], dates=[holiday],
    )
    await calendar.regenerate_range(db_session, holiday, holiday)
    for mk in MealKind:
        assert await _served(db_session, holiday, hall.id, mk) is False


async def test_regeneration_restores_meal_after_rule_removed(db_session):
    actor = await _actor(db_session)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.flush()

    sunday = dt.date(2026, 10, 4)
    rule = await schedule_rules.create_rule(
        db_session, actor_id=actor.id, kind=RuleKind.recurring,
        meal_kinds=[MealKind.breakfast], hall_ids=[hall.id], weekdays=[6],
    )
    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is False

    await schedule_rules.deactivate_rule(db_session, actor_id=actor.id, rule_id=rule.id)
    await calendar.regenerate_range(db_session, sunday, sunday)
    assert await _served(db_session, sunday, hall.id, MealKind.breakfast) is True


async def test_inactive_hall_gets_no_rows(db_session):
    hall = Hall(name="Зал X", is_active=False)
    db_session.add(hall)
    await db_session.flush()
    d = dt.date(2026, 10, 6)
    await calendar.regenerate_range(db_session, d, d)
    from app.models import Day

    day = (await db_session.execute(select(Day).where(Day.date == d))).scalar_one()
    rows = (await db_session.execute(
        select(DayHallMeal).where(DayHallMeal.day_id == day.id)
    )).scalars().all()
    assert rows == []
```

- [ ] **Step 2: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test_b3" uv run pytest tests/test_calendar_service.py -v`

- [ ] **Step 3: Написать `app/repositories/calendar.py`**

```python
import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Day, DayHallMeal, Hall


async def get_or_create_day(db: AsyncSession, day_date: dt.date) -> Day:
    day = (await db.execute(select(Day).where(Day.date == day_date))).scalar_one_or_none()
    if day is None:
        day = Day(date=day_date)
        db.add(day)
        await db.flush()
    return day


async def list_active_halls(db: AsyncSession) -> list[Hall]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    return list((await db.execute(stmt)).scalars().all())


async def clear_day_meals(db: AsyncSession, day_id) -> None:
    await db.execute(delete(DayHallMeal).where(DayHallMeal.day_id == day_id))


async def add_day_meals(db: AsyncSession, rows: list[DayHallMeal]) -> None:
    if rows:
        db.add_all(rows)
        await db.flush()
```

- [ ] **Step 4: Написать `app/services/calendar.py`**

```python
import datetime as dt
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DayHallMeal, MealKind, RuleKind, ScheduleRule, ScheduleRuleDate,
    ScheduleRuleHall, ScheduleRuleMeal, ScheduleRuleWeekday,
)
from app.repositories import calendar as cal_repo
from app.services import settings as settings_service


async def _rule_ids_for_hall(db: AsyncSession, hall_id) -> list:
    stmt = (
        select(ScheduleRuleHall.rule_id)
        .join(ScheduleRule, ScheduleRule.id == ScheduleRuleHall.rule_id)
        .where(ScheduleRuleHall.hall_id == hall_id, ScheduleRule.is_active.is_(True))
    )
    return list((await db.execute(stmt)).scalars().all())


async def _disabled_meals(db: AsyncSession, day_date: dt.date, hall_id) -> set[MealKind]:
    disabled: set[MealKind] = set()
    rule_ids = await _rule_ids_for_hall(db, hall_id)
    if not rule_ids:
        return disabled

    rules = {
        r.id: r
        for r in (await db.execute(
            select(ScheduleRule).where(ScheduleRule.id.in_(rule_ids))
        )).scalars().all()
    }

    for rule_id, rule in rules.items():
        matched = False
        if rule.kind == RuleKind.recurring:
            wds = set((await db.execute(
                select(ScheduleRuleWeekday.weekday).where(ScheduleRuleWeekday.rule_id == rule_id)
            )).scalars().all())
            matched = day_date.weekday() in wds
        else:
            dts = set((await db.execute(
                select(ScheduleRuleDate.specific_date).where(ScheduleRuleDate.rule_id == rule_id)
            )).scalars().all())
            matched = day_date in dts
        if matched:
            meals = (await db.execute(
                select(ScheduleRuleMeal.meal_kind).where(ScheduleRuleMeal.rule_id == rule_id)
            )).scalars().all()
            disabled |= set(meals)
    return disabled


async def materialize_day(db: AsyncSession, day_date: dt.date) -> None:
    day = await cal_repo.get_or_create_day(db, day_date)
    halls = await cal_repo.list_active_halls(db)
    await cal_repo.clear_day_meals(db, day.id)

    rows: list[DayHallMeal] = []
    for hall in halls:
        disabled = await _disabled_meals(db, day_date, hall.id)
        for meal_kind in MealKind:
            rows.append(
                DayHallMeal(
                    day_id=day.id,
                    hall_id=hall.id,
                    meal_kind=meal_kind,
                    is_served=meal_kind not in disabled,
                )
            )
    await cal_repo.add_day_meals(db, rows)


def _iter_dates(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


async def regenerate_range(db: AsyncSession, start: dt.date, end: dt.date) -> None:
    if end < start:
        return
    for day_date in _iter_dates(start, end):
        await materialize_day(db, day_date)


async def regenerate_horizon(db: AsyncSession) -> None:
    config = await settings_service.get_settings(db)
    today = dt.date.today()
    await regenerate_range(db, today, today + dt.timedelta(days=config.generation_days))
```

- [ ] **Step 5: Прогнать — PASS** (команда из Step 2).

- [ ] **Step 6: Commit**

```bash
git add server/app/repositories/calendar.py server/app/services/calendar.py server/tests/test_calendar_service.py
git commit -m "feat: add calendar generation and regeneration service"
```

---

### Task 4: Фоновые задачи (APScheduler)

**Files:**
- Create: `server/app/jobs/__init__.py` (empty), `server/app/jobs/maintenance.py`, `server/app/jobs/scheduler.py`
- Modify: `server/app/main.py` (lifespan)
- Create: `server/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `services.calendar.regenerate_horizon`, `SessionLocal`, `settings.timezone`.
- Produces: `run_daily_maintenance()`, `create_scheduler()`, `start_scheduler()`, `shutdown_scheduler()`.

- [ ] **Step 1: Написать `app/jobs/maintenance.py`**

```python
from app.db.session import SessionLocal
from app.services import calendar


async def run_daily_maintenance() -> None:
    async with SessionLocal() as db:
        await calendar.regenerate_horizon(db)
        await db.commit()
```

- [ ] **Step 2: Написать `app/jobs/scheduler.py`**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.jobs.maintenance import run_daily_maintenance

_scheduler: AsyncIOScheduler | None = None


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_daily_maintenance,
        CronTrigger(hour=23, minute=59),
        id="daily_maintenance",
        replace_existing=True,
    )
    return scheduler


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
        _scheduler.start()
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
```

- [ ] **Step 3: Обновить `app/main.py` (lifespan)**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.jobs.maintenance import run_daily_maintenance
from app.jobs.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_daily_maintenance()   # догон генерации при старте
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Трапезная МДА API", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Написать `tests/test_scheduler.py`**

```python
from app.jobs.scheduler import create_scheduler


def test_scheduler_has_daily_maintenance_job():
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    assert any(j.id == "daily_maintenance" for j in jobs)
```

> Тесты не запускают планировщик (httpx `ASGITransport` не исполняет lifespan), поэтому реальных фоновых задач в тестах нет.

- [ ] **Step 5: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test" uv run pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add server/app/jobs server/app/main.py server/tests/test_scheduler.py
git commit -m "feat: add APScheduler daily maintenance and lifespan catch-up"
```

---

### Task 5: HTTP — правила и перегенерация

**Files:**
- Create: `server/app/api/v1/routers/operator/schedule_rules.py`, `days.py`
- Modify: `server/app/api/v1/routers/operator/__init__.py`
- Create: `server/tests/test_schedule_api.py`

**Interfaces:**
- Consumes: `services.schedule_rules`, `services.calendar`.
- Produces: `/api/v1/operator/schedule-rules*`, `/api/v1/operator/days/regenerate`.

- [ ] **Step 1: Написать `app/api/v1/routers/operator/schedule_rules.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.schedule_rule import ScheduleRuleCreate, ScheduleRuleOut, ScheduleRuleUpdate
from app.services import schedule_rules as svc

router = APIRouter(prefix="/schedule-rules", tags=["operator:schedule-rules"])
_guard = require_roles(UserRole.operator)


async def _to_out(db, rule) -> ScheduleRuleOut:
    return ScheduleRuleOut(
        id=rule.id, kind=rule.kind, is_active=rule.is_active,
        meal_kinds=await svc.get_meal_kinds(db, rule.id),
        hall_ids=await svc.get_hall_ids(db, rule.id),
        weekdays=[w.weekday for w in await svc.get_weekdays(db, rule.id)],
        dates=[d.specific_date for d in await svc.get_dates(db, rule.id)],
    )


@router.get("", response_model=list[ScheduleRuleOut])
async def list_rules(only_active: bool = True, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    return [await _to_out(db, r) for r in await svc.list_rules(db, only_active=only_active)]


@router.post("", response_model=ScheduleRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: ScheduleRuleCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        rule = await svc.create_rule(
            db, actor_id=user.id, kind=payload.kind, meal_kinds=payload.meal_kinds,
            hall_ids=payload.hall_ids, weekdays=payload.weekdays, dates=payload.dates,
        )
    except svc.InvalidRule as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_rule: {e}")
    await db.commit()
    return await _to_out(db, rule)


@router.put("/{rule_id}", response_model=ScheduleRuleOut)
async def update_rule(rule_id: uuid.UUID, payload: ScheduleRuleUpdate,
                      db: AsyncSession = Depends(get_db), user: User = Depends(_guard)):
    try:
        rule = await svc.update_rule(
            db, actor_id=user.id, rule_id=rule_id, is_active=payload.is_active,
            meal_kinds=payload.meal_kinds, hall_ids=payload.hall_ids,
            weekdays=payload.weekdays, dates=payload.dates,
        )
    except svc.RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rule_not_found")
    except svc.InvalidRule as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_rule: {e}")
    await db.commit()
    return await _to_out(db, rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: User = Depends(_guard)):
    try:
        await svc.deactivate_rule(db, actor_id=user.id, rule_id=rule_id)
    except svc.RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rule_not_found")
    await db.commit()
```

- [ ] **Step 2: Написать `app/api/v1/routers/operator/days.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.calendar import RegenerateRequest
from app.services import calendar

router = APIRouter(prefix="/days", tags=["operator:days"])
_guard = require_roles(UserRole.operator)


@router.post("/regenerate", status_code=status.HTTP_204_NO_CONTENT)
async def regenerate(payload: RegenerateRequest, db: AsyncSession = Depends(get_db),
                     _: User = Depends(_guard)):
    start: date = payload.from_
    end: date = payload.to
    await calendar.regenerate_range(db, start, end)
    await db.commit()
```

- [ ] **Step 3: Написать `app/schemas/calendar.py`**

```python
from datetime import date

from pydantic import BaseModel, Field


class RegenerateRequest(BaseModel):
    from_: date = Field(alias="from")
    to: date
```

> Внимание: поле называется `from_.` c алиасом `"from"` (зарезервированное слово). Эндпоинт читает `payload.from_`.

- [ ] **Step 4: Обновить `app/api/v1/routers/operator/__init__.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers.operator import days, halls, meal_types, schedule_rules, settings, users

operator_router = APIRouter(prefix="/operator")
operator_router.include_router(halls.router)
operator_router.include_router(meal_types.router)
operator_router.include_router(users.router)
operator_router.include_router(settings.router)
operator_router.include_router(schedule_rules.router)
operator_router.include_router(days.router)
```

- [ ] **Step 5: Написать `tests/test_schedule_api.py`**

```python
import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import User, UserRole

FP = "dev-1"


@pytest.fixture
async def op_headers(client, db_session):
    u = User(login="root", password_hash=hash_password("rootpass"),
             full_name="Root", role=UserRole.operator)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "root", "password": "rootpass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_create_rule_and_regenerate(client, op_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=op_headers)
    hall_id = r.json()["id"]

    r = await client.post("/api/v1/operator/schedule-rules", headers=op_headers, json={
        "kind": "recurring",
        "meal_kinds": ["breakfast"],
        "hall_ids": [hall_id],
        "weekdays": [6],
    })
    assert r.status_code == 201
    assert r.json()["weekdays"] == [6]

    sunday = dt.date(2026, 10, 4)
    r = await client.post("/api/v1/operator/days/regenerate", headers=op_headers,
                          json={"from": sunday.isoformat(), "to": sunday.isoformat()})
    assert r.status_code == 204


async def test_invalid_rule_returns_400(client, op_headers):
    r = await client.post("/api/v1/operator/halls", json={"name": "Зал №1"}, headers=op_headers)
    hall_id = r.json()["id"]
    r = await client.post("/api/v1/operator/schedule-rules", headers=op_headers, json={
        "kind": "recurring", "meal_kinds": ["breakfast"], "hall_ids": [hall_id], "weekdays": [],
    })
    assert r.status_code == 400
```

- [ ] **Step 6: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test" uv run pytest -v
```
Expected: весь набор PASS.

- [ ] **Step 7: Commit**

```bash
git add server/app/api/v1/routers/operator server/app/schemas/calendar.py server/tests/test_schedule_api.py
git commit -m "feat: add operator schedule rules and days regenerate endpoints"
```

---

## Self-Review (автора плана)

- **Покрытие спеки:** §4 (`schedule_rules*`, `days`, `day_hall_meals`) — Task 1; §7 (генерация/перегенерация, снимок, возврат приёма) — Task 3 + Task 5; §12 (ежедневная задача) — Task 4; операторские эндпоинты правил — Task 5.
- **Изоляция:** сервис календаря читает модели правил напрямую, чтобы Tasks 2 и 3 можно было вести параллельно без гонки импортов.
- **Плейсхолдеров нет:** каждый шаг содержит код/команду.
- **Согласованность:** имена (`materialize_day`, `regenerate_range`, `regenerate_horizon`, `InvalidRule`, `RuleNotFound`, `run_daily_maintenance`) одинаковы в сервисах, роутерах и тестах.
- **Изоляция тестов:** новые модели импортируются в `app/models/__init__.py` (Task 1) — обязательно для `Base.metadata`.

## Следующие фазы

- **Фаза 4 — Requests & Marking:** заявки, дедлайн, резерв, оптимистичная блокировка, `/me` и админ-правки.
- **Фаза 5 — Reports:** дневной и за период.
- **Фаза 6 — Logs cleanup & Docker:** просмотр/очистка логов, Dockerfile/compose.
