# Трапезная МДА — Backend, фаза 5: Reports — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать бухгалтерские отчёты: дневной (по залам и приёмам: порции по типам питания + резерв по типам, итоги за день) и за период (только агрегированные суммы, без персональных данных). Доступ — бухгалтер и оператор.

**Architecture:** Продолжение слоистого монолита. `services/reports.py` считает отчёты, переиспользуя `services/day_view.get_day_state` (эффективные значения дня) — то есть отчёт автоматически учитывает заявки, дефолты и снимок доступности приёмов. Pydantic-схемы — `schemas/report.py`. HTTP — тонкий роутер `/accountant`.

**Tech Stack:** те же (FastAPI, Pydantic v2, SQLAlchemy 2.0 async, asyncpg, pytest/httpx).

**Spec:** `docs/superpowers/specs/2026-10-03-trapeznaya-mda-backend-design.md` (§10.4, §11)
**Предыдущая фаза:** `docs/superpowers/plans/2026-10-03-backend-phase-4-requests-marking.md`

## Global Constraints

- Учитываются только приёмы с `is_served = true` (снимок `day_hall_meals`) и `is_going = true`.
- **Тип питания** берётся из эффективного состояния дня (`request.meal_type_id`), при `None` — **фолбэк на первый активный тип** (по `sort_order`, затем `name`).
- `by_type` содержит **все активные типы** (включая нулевые); `reserve_by_type` — то же.
- `total` = сумма `by_type` за приём (резерв **входит** в total); `reserve_total` = сумма `reserve_by_type` (подмножество).
- Учитываются только активные залы и активные питающиеся (`role=eater`, `is_active=true`).
- Доступ к отчётам: `require_roles(UserRole.accountant, UserRole.operator)`.
- Формат сериализации: FastAPI отдаёт по алиасам (по умолчанию), поэтому поля `date_from`/`date_to` выводятся как `from`/`to`.

## Дерево файлов фазы 5

```
server/app/
  schemas/report.py                 # NEW
  services/reports.py               # NEW
  api/v1/routers/accountant.py      # NEW
  api/v1/router.py                  # MODIFY (include accountant)
server/tests/
  test_reports_service.py           # NEW
  test_reports_api.py               # NEW
```

**Interfaces, которые фаза отдаёт дальше:**
- `services/reports.py`: `build_daily_report(db, *, on_date, hall_id=None) -> DailyReportOut`, `build_period_report(db, *, start, end, hall_id=None) -> PeriodReportOut`.

---

### Task 1: Сервис отчётов + схемы

**Files:**
- Create: `server/app/schemas/report.py`, `server/app/services/reports.py`, `server/tests/test_reports_service.py`

**Interfaces:**
- Consumes: `services.day_view.get_day_state`, модели `Hall`, `MealType`, `User`, `UserHall`, `MealKind`.
- Produces: `build_daily_report`, `build_period_report` и pydantic-схемы `DailyReportOut`, `PeriodReportOut`, `HallReportOut`, `HallPeriodReportOut`, `MealReportOut`, `TypeCountOut`.

- [ ] **Step 1: Написать `app/schemas/report.py`**

```python
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MealKind


class TypeCountOut(BaseModel):
    meal_type_id: uuid.UUID | None
    name: str
    count: int


class MealReportOut(BaseModel):
    meal_kind: MealKind
    by_type: list[TypeCountOut]
    reserve_by_type: list[TypeCountOut]
    total: int
    reserve_total: int


class HallReportOut(BaseModel):
    hall_id: uuid.UUID
    hall_name: str
    meals: list[MealReportOut]
    day_total: int
    day_reserve_total: int


class DailyReportOut(BaseModel):
    date: date
    halls: list[HallReportOut]
    grand_total: int
    grand_reserve_total: int


class HallPeriodReportOut(BaseModel):
    hall_id: uuid.UUID
    hall_name: str
    meals: list[MealReportOut]
    period_total: int
    period_reserve_total: int


class PeriodReportOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")
    halls: list[HallPeriodReportOut]
    grand_total: int
    grand_reserve_total: int
```

- [ ] **Step 2: Написать падающий тест `tests/test_reports_service.py`**

```python
import datetime as dt

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, Request, RequestItem, User, UserHall, UserRole,
)
from app.services import reports


async def _setup(db_session):
    hall = Hall(name="Зал №1")
    meat = MealType(name="Мясо", sort_order=1)
    fish = MealType(name="Рыба", sort_order=2)
    db_session.add_all([hall, meat, fish])
    await db_session.flush()

    def eater(login, mt_id):
        return User(login=login, password_hash="x", full_name=login,
                    role=UserRole.eater, default_meal_type_id=mt_id)

    e1 = eater("e1", meat.id)
    e2 = eater("e2", fish.id)
    db_session.add_all([e1, e2])
    await db_session.flush()
    db_session.add_all([UserHall(user_id=e1.id, hall_id=hall.id),
                        UserHall(user_id=e2.id, hall_id=hall.id)])
    day = Day(date=dt.date(2026, 6, 10))
    db_session.add(day)
    await db_session.flush()
    for mk in MealKind:
        db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk,
                                   is_served=(mk != MealKind.snack)))
    await db_session.flush()
    return hall, meat, fish, e1, e2


async def test_daily_report_defaults(db_session):
    hall, meat, fish, e1, e2 = await _setup(db_session)
    rep = await reports.build_daily_report(db_session, on_date=dt.date(2026, 6, 10))
    # по умолчанию никто не ходит -> нули
    assert rep.grand_total == 0
    hall_rep = rep.halls[0]
    assert len(hall_rep.meals) == 4
    assert all(m.total == 0 for m in hall_rep.meals)
    # все активные типы присутствуют
    assert {t.name for t in hall_rep.meals[0].by_type} == {"Мясо", "Рыба"}


async def test_daily_report_counts_going_and_reserve(db_session):
    hall, meat, fish, e1, e2 = await _setup(db_session)
    # заявка e1: идёт на завтрак (Мясо, обычная)
    req = Request(user_id=e1.id, date=dt.date(2026, 6, 10), meal_type_id=meat.id, version=1)
    db_session.add(req)
    await db_session.flush()
    db_session.add_all([
        RequestItem(request_id=req.id, meal_kind=MealKind.breakfast, is_going=True, is_reserve=False),
        RequestItem(request_id=req.id, meal_kind=MealKind.lunch, is_going=True, is_reserve=True),
    ])
    # заявка e2: идёт на завтрак (Рыба, резерв)
    req2 = Request(user_id=e2.id, date=dt.date(2026, 6, 10), meal_type_id=fish.id, version=1)
    db_session.add(req2)
    await db_session.flush()
    db_session.add(RequestItem(request_id=req2.id, meal_kind=MealKind.breakfast,
                               is_going=True, is_reserve=True))
    await db_session.flush()

    rep = await reports.build_daily_report(db_session, on_date=dt.date(2026, 6, 10))
    hall_rep = rep.halls[0]
    breakfast = next(m for m in hall_rep.meals if m.meal_kind == MealKind.breakfast)
    by_name = {t.name: t.count for t in breakfast.by_type}
    assert by_name["Мясо"] == 1 and by_name["Рыба"] == 1
    assert breakfast.total == 2
    reserve_by_name = {t.name: t.count for t in breakfast.reserve_by_type}
    assert reserve_by_name["Рыба"] == 1 and reserve_by_name["Мясо"] == 0
    assert breakfast.reserve_total == 1

    # полдник не подаётся -> не учитывается даже если бы шли
    snack = next(m for m in hall_rep.meals if m.meal_kind == MealKind.snack)
    assert snack.total == 0
```

- [ ] **Step 3: Запустить — FAIL.** Затем реализовать.
Run: `TEST_DATABASE_URL=".../mda_test_b1" uv run pytest tests/test_reports_service.py -v`

- [ ] **Step 4: Написать `app/services/reports.py`**

```python
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall, MealKind, MealType, User, UserHall, UserRole
from app.schemas.report import (
    DailyReportOut, HallPeriodReportOut, HallReportOut, MealReportOut,
    PeriodReportOut, TypeCountOut,
)
from app.services import day_view


class _Accumulator:
    def __init__(self, type_ids: list[uuid.UUID]) -> None:
        self.type_ids = type_ids
        self.by_type = {mk: {tid: 0 for tid in type_ids} for mk in MealKind}
        self.reserve = {mk: {tid: 0 for tid in type_ids} for mk in MealKind}
        self.total = {mk: 0 for mk in MealKind}
        self.reserve_total = {mk: 0 for mk in MealKind}

    def add(self, meal_kind: MealKind, type_id: uuid.UUID | None, is_reserve: bool) -> None:
        if type_id is None or type_id not in self.by_type[meal_kind]:
            return
        self.by_type[meal_kind][type_id] += 1
        self.total[meal_kind] += 1
        if is_reserve:
            self.reserve[meal_kind][type_id] += 1
            self.reserve_total[meal_kind] += 1


async def _active_types(db: AsyncSession) -> list[MealType]:
    stmt = (
        select(MealType)
        .where(MealType.is_active.is_(True))
        .order_by(MealType.sort_order, MealType.name)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _halls(db: AsyncSession, hall_id: uuid.UUID | None) -> list[Hall]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    if hall_id is not None:
        stmt = stmt.where(Hall.id == hall_id)
    return list((await db.execute(stmt)).scalars().all())


async def _eaters(db: AsyncSession, hall_id: uuid.UUID) -> list[User]:
    stmt = (
        select(User)
        .join(UserHall, UserHall.user_id == User.id)
        .where(User.role == UserRole.eater, User.is_active.is_(True), UserHall.hall_id == hall_id)
        .order_by(User.login)
    )
    return list((await db.execute(stmt)).scalars().all())


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


async def _accumulate(
    db: AsyncSession, eaters: list[User], dates: list[date],
    types: list[MealType], fallback_id: uuid.UUID | None, acc: _Accumulator,
) -> None:
    for eater in eaters:
        for day_date in dates:
            state = await day_view.get_day_state(db, user=eater, day_date=day_date)
            type_id = state.meal_type_id or fallback_id
            for item in state.items:
                if not item.is_served or not item.is_going:
                    continue
                acc.add(item.meal_kind, type_id, item.is_reserve)


def _meal_reports(types: list[MealType], acc: _Accumulator) -> list[MealReportOut]:
    meals: list[MealReportOut] = []
    for mk in MealKind:
        by_type = [
            TypeCountOut(meal_type_id=t.id, name=t.name, count=acc.by_type[mk][t.id])
            for t in types
        ]
        reserve_by_type = [
            TypeCountOut(meal_type_id=t.id, name=t.name, count=acc.reserve[mk][t.id])
            for t in types
        ]
        meals.append(
            MealReportOut(
                meal_kind=mk, by_type=by_type, reserve_by_type=reserve_by_type,
                total=acc.total[mk], reserve_total=acc.reserve_total[mk],
            )
        )
    return meals


async def build_daily_report(
    db: AsyncSession, *, on_date: date, hall_id: uuid.UUID | None = None
) -> DailyReportOut:
    types = await _active_types(db)
    fallback_id = types[0].id if types else None
    type_ids = [t.id for t in types]

    halls_out: list[HallReportOut] = []
    grand_total = grand_reserve = 0

    for hall in await _halls(db, hall_id):
        acc = _Accumulator(type_ids)
        await _accumulate(db, await _eaters(db, hall.id), [on_date], types, fallback_id, acc)
        meals = _meal_reports(types, acc)
        day_total = sum(m.total for m in meals)
        day_reserve = sum(m.reserve_total for m in meals)
        grand_total += day_total
        grand_reserve += day_reserve
        halls_out.append(
            HallReportOut(hall_id=hall.id, hall_name=hall.name, meals=meals,
                          day_total=day_total, day_reserve_total=day_reserve)
        )

    return DailyReportOut(
        date=on_date, halls=halls_out,
        grand_total=grand_total, grand_reserve_total=grand_reserve,
    )


async def build_period_report(
    db: AsyncSession, *, start: date, end: date, hall_id: uuid.UUID | None = None
) -> PeriodReportOut:
    types = await _active_types(db)
    fallback_id = types[0].id if types else None
    type_ids = [t.id for t in types]
    dates = list(_iter_dates(start, end)) if end >= start else []

    halls_out: list[HallPeriodReportOut] = []
    grand_total = grand_reserve = 0

    for hall in await _halls(db, hall_id):
        acc = _Accumulator(type_ids)
        await _accumulate(db, await _eaters(db, hall.id), dates, types, fallback_id, acc)
        meals = _meal_reports(types, acc)
        period_total = sum(m.total for m in meals)
        period_reserve = sum(m.reserve_total for m in meals)
        grand_total += period_total
        grand_reserve += period_reserve
        halls_out.append(
            HallPeriodReportOut(hall_id=hall.id, hall_name=hall.name, meals=meals,
                                period_total=period_total, period_reserve_total=period_reserve)
        )

    return PeriodReportOut(
        date_from=start, date_to=end, halls=halls_out,
        grand_total=grand_total, grand_reserve_total=grand_reserve,
    )
```

- [ ] **Step 5: Прогнать — PASS.**

- [ ] **Step 6: Commit**

```bash
git add server/app/schemas/report.py server/app/services/reports.py server/tests/test_reports_service.py
git commit -m "feat: add daily and period report services"
```

---

### Task 2: HTTP — эндпоинты отчётов

**Files:**
- Create: `server/app/api/v1/routers/accountant.py`
- Modify: `server/app/api/v1/router.py`
- Create: `server/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `services.reports`, `deps.require_roles`.
- Produces: `/api/v1/accountant/report`, `/api/v1/accountant/report/period`.

- [ ] **Step 1: Написать `app/api/v1/routers/accountant.py`**

```python
import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.report import DailyReportOut, PeriodReportOut
from app.services import reports

router = APIRouter(prefix="/accountant", tags=["accountant"])
_guard = require_roles(UserRole.accountant, UserRole.operator)


@router.get("/report", response_model=DailyReportOut)
async def daily_report(date: date, hall_id: uuid.UUID | None = None,
                       db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    return await reports.build_daily_report(db, on_date=date, hall_id=hall_id)


@router.get("/report/period", response_model=PeriodReportOut)
async def period_report(from_: date = Query(alias="from"), to: date = Query(...),
                        hall_id: uuid.UUID | None = None,
                        db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    return await reports.build_period_report(db, start=from_, end=to, hall_id=hall_id)
```

> Добавь `from fastapi import Query`. Параметр `date` в `daily_report` затеняет тип `date` — приведи к виду `on_date: date = Query(alias="date")` и передавай `on_date=on_date`, чтобы не путаться.

- [ ] **Step 2: Включить роутер в `app/api/v1/router.py`**

```python
from fastapi import APIRouter

from app.api.v1.routers import accountant, admin, auth, me
from app.api.v1.routers.operator import operator_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
api_router.include_router(accountant.router)
api_router.include_router(operator_router)
```

- [ ] **Step 3: Написать `tests/test_reports_api.py`**

```python
import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import Hall, MealType, User, UserRole

FP = "dev-1"


@pytest.fixture
async def accountant_headers(client, db_session):
    u = User(login="buh", password_hash=hash_password("bpass"),
             full_name="Бух", role=UserRole.accountant)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "buh", "password": "bpass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


@pytest.fixture
async def eater_headers(client, db_session):
    u = User(login="ivan", password_hash=hash_password("ipass"),
             full_name="Иван", role=UserRole.eater)
    db_session.add(u)
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"login": "ivan", "password": "ipass"},
                          headers={"X-Device-Fingerprint": FP})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Device-Fingerprint": FP}


async def test_daily_report_shape(client, accountant_headers, db_session):
    db_session.add_all([Hall(name="Зал №1"), MealType(name="Мясо", sort_order=1)])
    await db_session.commit()

    r = await client.get("/api/v1/accountant/report?date=2026-06-10", headers=accountant_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-06-10"
    assert len(body["halls"]) >= 1
    meal = body["halls"][0]["meals"][0]
    assert {"meal_kind", "by_type", "reserve_by_type", "total", "reserve_total"} <= set(meal)


async def test_period_report_shape(client, accountant_headers, db_session):
    r = await client.get(
        "/api/v1/accountant/report/period?from=2026-06-01&to=2026-06-03",
        headers=accountant_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["from"] == "2026-06-01" and body["to"] == "2026-06-03"
    assert "grand_total" in body


async def test_eater_forbidden(client, eater_headers):
    r = await client.get("/api/v1/accountant/report?date=2026-06-10", headers=eater_headers)
    assert r.status_code == 403
```

- [ ] **Step 4: Прогнать**

```bash
cd server
TEST_DATABASE_URL="postgresql+asyncpg://mda:mda@localhost:5432/mda_test" uv run pytest -v
```
Expected: весь набор PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/api/v1/routers/accountant.py server/app/api/v1/router.py server/tests/test_reports_api.py
git commit -m "feat: add accountant report endpoints"
```

---

## Self-Review (автора плана)

- **Покрытие спеки:** §11 дневной отчёт (`by_type` + `reserve_by_type`, `total`, `reserve_total`, `day_total`, `grand_total`) — Task 1; §11 отчёт за период (только суммы) — Task 1; §10.4 эндпоинты и доступ бухгалтер/оператор — Task 2.
- **Плейсхолдеров нет:** код и команды приведены; в Task 2 есть две пометки про переименование затеняющих параметров (`on_date`, `Query`) — они содержат конкретные указания.
- **Согласованность:** имена схем (`DailyReportOut`, `PeriodReportOut`, `MealReportOut`, `TypeCountOut`, `HallReportOut`, `HallPeriodReportOut`) и функций (`build_daily_report`, `build_period_report`) одинаковы в сервисе, роутере и тестах.
- **Фолбэк типа:** при `meal_type_id is None` используется первый активный тип; если активных типов нет — позиции не учитываются (не падаем).
- **Резерв — подмножество total:** `reserve_total` не вычитается из `total` (соответствует примеру из спеки).

## Следующая фаза

- **Фаза 6 — Logs & Docker:** эндпоинт просмотра логов оператором, автоочистка логов в 23:59, Dockerfile + сервис `api` в compose.
