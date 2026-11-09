# Конструктор отчёта и Excel — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать бухгалтеру и оператору собрать структуру отчёта (группы залов с подытогами и строки общих итогов) и строить по ней Excel «за день» и «за N дней» в формате образца.

**Architecture:** Шаблон хранится в четырёх плоских таблицах. Генератор получает нормализованные данные (`ReportData`: типы, даты, названия залов, счётчики) и рендерит два листа; суммы по группам считают свои залы, строки общих итогов — каждый зал один раз. Шаблон читается и пишется целиком одним `PUT`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, openpyxl, pytest; React 19, TypeScript, TanStack Query, Tailwind, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-12-report-constructor-design.md`

## Global Constraints

- Порог пароля и прочие бизнес-правила не меняем; работаем только с отчётом.
- Все суммы — по активным залам и активным типам питания; резервные отметки входят в обычные числа, «Рез.» — уточняющая колонка.
- Дубли зала: внутри группы и внутри итога запрещены (уникальный индекс), между группами — разрешены.
- Строка итога с `all_halls=true` не хранит список залов.
- Существующие экранные отчёты (`/accountant/report`, `/report/period`) не меняются.
- Миграция только добавляет таблицы; данные не трогаем.

---

## Структура файлов

**Backend**
- Create `server/app/models/report_template.py` — 4 модели шаблона.
- Modify `server/app/models/__init__.py` — экспорт моделей.
- Create `server/alembic/versions/b7f1c2d3e4a5_report_template.py` — миграция.
- Create `server/app/repositories/report_template.py` — чтение/замена строк.
- Create `server/app/services/report_template.py` — `ReportTemplate`, `get_template`, `replace_template`, валидация.
- Create `server/app/schemas/report_template.py` — вход/выход API.
- Create `server/app/api/v1/routers/report_template.py` — `GET/PUT /report-template`.
- Modify `server/app/api/v1/router.py` — подключить роутер.
- Modify `server/app/api/v1/routers/catalog.py` — `GET /catalog/halls`.
- Modify `server/app/services/reports.py` — `PeriodMatrix`, `build_period_matrix`.
- Create `server/app/services/report_data.py` — `ReportData` и построители.
- Rewrite `server/app/services/report_excel.py` — два листа по шаблону.
- Modify `server/app/api/v1/routers/accountant.py` — `reserve` в экспорте.

**Frontend**
- Create `syte/src/api/reportTemplate.ts` — типы и хуки.
- Create `syte/src/features/reportTemplate/ReportTemplatePage.tsx` — страница-конструктор.
- Modify `syte/src/app/router.tsx` — маршрут.
- Modify `syte/src/app/Sidebar.tsx` — пункты для бухгалтера и оператора.
- Modify `syte/src/api/reports.ts` — `reserve` в URL экспорта.
- Modify `syte/src/features/reports/DailyReportPage.tsx`, `PeriodReportPage.tsx` — галочка резерва.

**Docs**
- Modify `server/README.md` — раздел про конструктор отчёта.

---

### Task 1: Модели шаблона и миграция

**Files:**
- Create: `server/app/models/report_template.py`
- Modify: `server/app/models/__init__.py`
- Create: `server/alembic/versions/b7f1c2d3e4a5_report_template.py`
- Test: `server/tests/test_report_template_model.py`

**Interfaces:**
- Produces: `ReportGroup(id, name, sort_order, show_subtotal)`, `ReportGroupHall(group_id, hall_id, sort_order)`, `ReportTotal(id, name, sort_order, all_halls)`, `ReportTotalHall(total_id, hall_id, sort_order)`.

- [ ] **Step 1: Написать падающий тест**

```python
# server/tests/test_report_template_model.py
import uuid

from app.models import Hall, ReportGroup, ReportGroupHall, ReportTotal, ReportTotalHall


async def test_group_hall_link_is_unique(db_session):
    hall = Hall(name="Зал №1")
    group = ReportGroup(name="Студенты", sort_order=1, show_subtotal=True)
    db_session.add_all([hall, group])
    await db_session.flush()
    db_session.add(ReportGroupHall(group_id=group.id, hall_id=hall.id, sort_order=0))
    await db_session.flush()
    db_session.add(ReportGroupHall(group_id=group.id, hall_id=hall.id, sort_order=1))
    with pytest.raises(Exception):
        await db_session.flush()


async def test_total_all_halls_flag(db_session):
    total = ReportTotal(name="ИТОГО", sort_order=0, all_halls=True)
    db_session.add(total)
    await db_session.flush()
    assert total.id is not None
    assert await db_session.get(ReportTotal, total.id) is not None
```

Добавить `import pytest` в шапку файла.

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_model.py -q`
Expected: FAIL — `ImportError: cannot import name 'ReportGroup'`.

- [ ] **Step 3: Написать модели**

```python
# server/app/models/report_template.py
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportGroup(Base):
    __tablename__ = "report_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    show_subtotal: Mapped[bool] = mapped_column(Boolean, default=True)


class ReportGroupHall(Base):
    __tablename__ = "report_group_halls"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_groups.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ReportTotal(Base):
    __tablename__ = "report_totals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    all_halls: Mapped[bool] = mapped_column(Boolean, default=False)


class ReportTotalHall(Base):
    __tablename__ = "report_total_halls"

    total_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_totals.id", ondelete="CASCADE"), primary_key=True
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 4: Экспортировать модели**

В `server/app/models/__init__.py` добавить импорты и строки в `__all__`:

```python
from app.models.report_template import (
    ReportGroup,
    ReportGroupHall,
    ReportTotal,
    ReportTotalHall,
)
```

и `"ReportGroup"`, `"ReportGroupHall"`, `"ReportTotal"`, `"ReportTotalHall"` в `__all__` (по алфавиту).

- [ ] **Step 5: Миграция**

```python
# server/alembic/versions/b7f1c2d3e4a5_report_template.py
"""report template

Revision ID: b7f1c2d3e4a5
Revises: 01fe93c155e1
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f1c2d3e4a5"
down_revision: Union[str, Sequence[str], None] = "01fe93c155e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("show_subtotal", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "report_group_halls",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["group_id"], ["report_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "hall_id"),
    )
    op.create_table(
        "report_totals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("all_halls", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "report_total_halls",
        sa.Column("total_id", sa.Uuid(), nullable=False),
        sa.Column("hall_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["total_id"], ["report_totals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hall_id"], ["halls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("total_id", "hall_id"),
    )


def downgrade() -> None:
    op.drop_table("report_total_halls")
    op.drop_table("report_totals")
    op.drop_table("report_group_halls")
    op.drop_table("report_groups")
```

- [ ] **Step 6: Прогнать тесты**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_model.py -q`
Expected: PASS (2 passed).

- [ ] **Step 7: Коммит**

```bash
git add server/app/models/report_template.py server/app/models/__init__.py \
        server/alembic/versions/b7f1c2d3e4a5_report_template.py \
        server/tests/test_report_template_model.py
git commit -m "feat(server): add report template tables"
```

---

### Task 2: Репозиторий и сервис шаблона

**Files:**
- Create: `server/app/repositories/report_template.py`
- Create: `server/app/services/report_template.py`
- Test: `server/tests/test_report_template_service.py`

**Interfaces:**
- Consumes: модели из Task 1.
- Produces:
  - `ReportTemplate(groups: list[TemplateGroup], totals: list[TemplateTotal])`
  - `TemplateGroup(id: uuid.UUID, name: str, show_subtotal: bool, hall_ids: list[uuid.UUID])`
  - `TemplateTotal(id: uuid.UUID, name: str, all_halls: bool, hall_ids: list[uuid.UUID])`
  - `async def get_template(db) -> ReportTemplate`
  - `async def replace_template(db, *, actor_id, groups: list[TemplateGroup], totals: list[TemplateTotal]) -> ReportTemplate`
  - `class InvalidTemplate(Exception)`

- [ ] **Step 1: Написать падающие тесты**

```python
# server/tests/test_report_template_service.py
import pytest

from app.models import Hall, User, UserRole
from app.services import report_template as svc


async def _ctx(db_session):
    actor = User(login="op", password_hash="x", full_name="Op", role=UserRole.operator)
    h1, h2 = Hall(name="Зал №1"), Hall(name="Зал №2")
    db_session.add_all([actor, h1, h2])
    await db_session.flush()
    return actor, h1, h2


def _group(name, hall_ids):
    return svc.TemplateGroup(id=None, name=name, show_subtotal=True, hall_ids=list(hall_ids))


async def test_replace_and_read_back(db_session):
    actor, h1, h2 = await _ctx(db_session)
    await svc.replace_template(
        db_session, actor_id=actor.id,
        groups=[_group("Студенты", [h1.id, h2.id])],
        totals=[svc.TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    tpl = await svc.get_template(db_session)
    assert [g.name for g in tpl.groups] == ["Студенты"]
    assert tpl.groups[0].hall_ids == [h1.id, h2.id]
    assert tpl.groups[0].show_subtotal is True
    assert tpl.totals[0].all_halls is True
    assert tpl.totals[0].hall_ids == []


async def test_duplicate_hall_in_group_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id,
            groups=[_group("Студенты", [h1.id, h1.id])], totals=[],
        )


async def test_all_halls_with_list_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[],
            totals=[svc.TemplateTotal(
                id=None, name="ИТОГО", all_halls=True, hall_ids=[h1.id]
            )],
        )


async def test_total_without_halls_rejected(db_session):
    actor, _, _ = await _ctx(db_session)
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[],
            totals=[svc.TemplateTotal(id=None, name="ИТОГО", all_halls=False, hall_ids=[])],
        )


async def test_inactive_hall_rejected(db_session):
    actor, h1, _ = await _ctx(db_session)
    h1.is_active = False
    await db_session.flush()
    with pytest.raises(svc.InvalidTemplate):
        await svc.replace_template(
            db_session, actor_id=actor.id, groups=[_group("Студенты", [h1.id])], totals=[],
        )


async def test_replace_is_full(db_session):
    actor, h1, h2 = await _ctx(db_session)
    await svc.replace_template(
        db_session, actor_id=actor.id, groups=[_group("A", [h1.id])], totals=[],
    )
    await svc.replace_template(
        db_session, actor_id=actor.id, groups=[_group("B", [h2.id])], totals=[],
    )
    tpl = await svc.get_template(db_session)
    assert [g.name for g in tpl.groups] == ["B"]
```

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.report_template'`.

- [ ] **Step 3: Репозиторий**

```python
# server/app/repositories/report_template.py
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReportGroup, ReportGroupHall, ReportTotal, ReportTotalHall


async def list_groups(db: AsyncSession) -> list[ReportGroup]:
    stmt = select(ReportGroup).order_by(ReportGroup.sort_order, ReportGroup.name)
    return list((await db.execute(stmt)).scalars().all())


async def list_group_halls(db: AsyncSession) -> list[ReportGroupHall]:
    stmt = select(ReportGroupHall).order_by(ReportGroupHall.sort_order)
    return list((await db.execute(stmt)).scalars().all())


async def list_totals(db: AsyncSession) -> list[ReportTotal]:
    stmt = select(ReportTotal).order_by(ReportTotal.sort_order, ReportTotal.name)
    return list((await db.execute(stmt)).scalars().all())


async def list_total_halls(db: AsyncSession) -> list[ReportTotalHall]:
    stmt = select(ReportTotalHall).order_by(ReportTotalHall.sort_order)
    return list((await db.execute(stmt)).scalars().all())


async def clear(db: AsyncSession) -> None:
    await db.execute(delete(ReportTotalHall))
    await db.execute(delete(ReportTotal))
    await db.execute(delete(ReportGroupHall))
    await db.execute(delete(ReportGroup))
    await db.flush()


async def add_group(db: AsyncSession, name: str, sort_order: int, show_subtotal: bool) -> ReportGroup:
    group = ReportGroup(name=name, sort_order=sort_order, show_subtotal=show_subtotal)
    db.add(group)
    await db.flush()
    return group


async def add_group_hall(db: AsyncSession, group_id: uuid.UUID, hall_id: uuid.UUID, sort_order: int) -> None:
    db.add(ReportGroupHall(group_id=group_id, hall_id=hall_id, sort_order=sort_order))


async def add_total(db: AsyncSession, name: str, sort_order: int, all_halls: bool) -> ReportTotal:
    total = ReportTotal(name=name, sort_order=sort_order, all_halls=all_halls)
    db.add(total)
    await db.flush()
    return total


async def add_total_hall(db: AsyncSession, total_id: uuid.UUID, hall_id: uuid.UUID, sort_order: int) -> None:
    db.add(ReportTotalHall(total_id=total_id, hall_id=hall_id, sort_order=sort_order))
```

- [ ] **Step 4: Сервис**

```python
# server/app/services/report_template.py
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Hall
from app.repositories import report_template as repo
from app.services import audit


class InvalidTemplate(Exception):
    pass


@dataclass
class TemplateGroup:
    id: uuid.UUID | None
    name: str
    show_subtotal: bool
    hall_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class TemplateTotal:
    id: uuid.UUID | None
    name: str
    all_halls: bool
    hall_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class ReportTemplate:
    groups: list[TemplateGroup] = field(default_factory=list)
    totals: list[TemplateTotal] = field(default_factory=list)


async def get_template(db: AsyncSession) -> ReportTemplate:
    groups = await repo.list_groups(db)
    group_halls = await repo.list_group_halls(db)
    totals = await repo.list_totals(db)
    total_halls = await repo.list_total_halls(db)

    by_group: dict[uuid.UUID, list[uuid.UUID]] = {}
    for link in group_halls:
        by_group.setdefault(link.group_id, []).append(link.hall_id)
    by_total: dict[uuid.UUID, list[uuid.UUID]] = {}
    for link in total_halls:
        by_total.setdefault(link.total_id, []).append(link.hall_id)

    return ReportTemplate(
        groups=[
            TemplateGroup(id=g.id, name=g.name, show_subtotal=g.show_subtotal,
                          hall_ids=by_group.get(g.id, []))
            for g in groups
        ],
        totals=[
            TemplateTotal(id=t.id, name=t.name, all_halls=t.all_halls,
                          hall_ids=by_total.get(t.id, []))
            for t in totals
        ],
    )


async def _validate(db: AsyncSession, groups, totals) -> None:
    for group in groups:
        name = (group.name or "").strip()
        if not name:
            raise InvalidTemplate("group name is empty")
        if len(name) > 100:
            raise InvalidTemplate("group name is too long")
        if len(set(group.hall_ids)) != len(group.hall_ids):
            raise InvalidTemplate(f"duplicate hall in group {name}")
        for hall_id in group.hall_ids:
            hall = await db.get(Hall, hall_id)
            if hall is None or not hall.is_active:
                raise InvalidTemplate(f"hall {hall_id} not found or inactive")

    for total in totals:
        name = (total.name or "").strip()
        if not name:
            raise InvalidTemplate("total name is empty")
        if len(name) > 100:
            raise InvalidTemplate("total name is too long")
        if total.all_halls and total.hall_ids:
            raise InvalidTemplate(f"total {name}: all_halls forbids hall list")
        if not total.all_halls and not total.hall_ids:
            raise InvalidTemplate(f"total {name}: hall list is empty")
        if len(set(total.hall_ids)) != len(total.hall_ids):
            raise InvalidTemplate(f"duplicate hall in total {name}")
        for hall_id in total.hall_ids:
            hall = await db.get(Hall, hall_id)
            if hall is None or not hall.is_active:
                raise InvalidTemplate(f"hall {hall_id} not found or inactive")


async def replace_template(
    db: AsyncSession, *, actor_id: uuid.UUID,
    groups: list[TemplateGroup], totals: list[TemplateTotal],
) -> ReportTemplate:
    await _validate(db, groups, totals)
    await repo.clear(db)

    for index, group in enumerate(groups):
        row = await repo.add_group(
            db, group.name.strip(), index, group.show_subtotal
        )
        for position, hall_id in enumerate(group.hall_ids):
            await repo.add_group_hall(db, row.id, hall_id, position)

    for index, total in enumerate(totals):
        row = await repo.add_total(db, total.name.strip(), index, total.all_halls)
        for position, hall_id in enumerate(total.hall_ids):
            await repo.add_total_hall(db, row.id, hall_id, position)

    await audit.record(
        db, actor_id=actor_id, action="update", entity_type="report_template",
        entity_id="1",
        details={"groups": len(groups), "totals": len(totals)},
    )
    await db.flush()
    return await get_template(db)
```

- [ ] **Step 5: Прогнать тесты**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_service.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Коммит**

```bash
git add server/app/repositories/report_template.py server/app/services/report_template.py \
        server/tests/test_report_template_service.py
git commit -m "feat(server): add report template service"
```

---

### Task 3: API шаблона и каталог залов

**Files:**
- Create: `server/app/schemas/report_template.py`
- Create: `server/app/api/v1/routers/report_template.py`
- Modify: `server/app/api/v1/router.py`
- Modify: `server/app/api/v1/routers/catalog.py`
- Test: `server/tests/test_report_template_api.py`

**Interfaces:**
- Consumes: `report_template.get_template`, `replace_template`, `TemplateGroup`, `TemplateTotal`.
- Produces: `GET /api/v1/report-template`, `PUT /api/v1/report-template`, `GET /api/v1/catalog/halls`.

- [ ] **Step 1: Написать падающие тесты**

```python
# server/tests/test_report_template_api.py
from app.core.security import hash_password
from app.models import Hall, User, UserRole

FP = "dev-1"


async def _login(client, db_session, role):
    user = User(login=f"u_{role.value}", password_hash=hash_password("pass"),
                full_name="U", role=role)
    db_session.add(user)
    await db_session.commit()
    await client.post("/api/v1/auth/login", json={"login": user.login, "password": "pass"},
                      headers={"X-Device-Fingerprint": FP})
    return {"X-Device-Fingerprint": FP}


async def test_accountant_can_save_and_read(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.commit()

    body = {
        "groups": [{"name": "Студенты", "show_subtotal": True, "hall_ids": [str(hall.id)]}],
        "totals": [{"name": "ИТОГО", "all_halls": True, "hall_ids": []}],
    }
    r = await client.put("/api/v1/report-template", json=body, headers=headers)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["groups"][0]["name"] == "Студенты"
    assert saved["groups"][0]["hall_ids"] == [str(hall.id)]
    assert saved["totals"][0]["all_halls"] is True

    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 200
    assert r.json()["groups"][0]["name"] == "Студенты"


async def test_operator_can_read(client, db_session):
    headers = await _login(client, db_session, UserRole.operator)
    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"groups": [], "totals": []}


async def test_eater_cannot_read(client, db_session):
    headers = await _login(client, db_session, UserRole.eater)
    r = await client.get("/api/v1/report-template", headers=headers)
    assert r.status_code == 403


async def test_duplicate_hall_returns_400(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.commit()
    body = {"groups": [{"name": "A", "show_subtotal": True,
                        "hall_ids": [str(hall.id), str(hall.id)]}], "totals": []}
    r = await client.put("/api/v1/report-template", json=body, headers=headers)
    assert r.status_code == 400


async def test_catalog_halls_available_to_accountant(client, db_session):
    headers = await _login(client, db_session, UserRole.accountant)
    db_session.add_all([Hall(name="Зал №1"), Hall(name="Зал №2", is_active=False)])
    await db_session.commit()
    r = await client.get("/api/v1/catalog/halls", headers=headers)
    assert r.status_code == 200
    assert [h["name"] for h in r.json()] == ["Зал №1"]
```

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_api.py -q`
Expected: FAIL — 404 на `/api/v1/report-template`.

- [ ] **Step 3: Схемы**

```python
# server/app/schemas/report_template.py
import uuid

from pydantic import BaseModel, Field


class TemplateGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    show_subtotal: bool = True
    hall_ids: list[uuid.UUID] = []


class TemplateTotalIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    all_halls: bool = False
    hall_ids: list[uuid.UUID] = []


class ReportTemplateIn(BaseModel):
    groups: list[TemplateGroupIn] = []
    totals: list[TemplateTotalIn] = []


class TemplateGroupOut(TemplateGroupIn):
    id: uuid.UUID


class TemplateTotalOut(TemplateTotalIn):
    id: uuid.UUID


class ReportTemplateOut(BaseModel):
    groups: list[TemplateGroupOut] = []
    totals: list[TemplateTotalOut] = []
```

- [ ] **Step 4: Роутер**

```python
# server/app/api/v1/routers/report_template.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.report_template import (
    ReportTemplateIn, ReportTemplateOut, TemplateGroupOut, TemplateTotalOut,
)
from app.services import report_template as svc

router = APIRouter(prefix="/report-template", tags=["report-template"])
_guard = require_roles(UserRole.accountant, UserRole.operator)


def _out(template: svc.ReportTemplate) -> ReportTemplateOut:
    return ReportTemplateOut(
        groups=[
            TemplateGroupOut(id=g.id, name=g.name, show_subtotal=g.show_subtotal,
                             hall_ids=g.hall_ids)
            for g in template.groups
        ],
        totals=[
            TemplateTotalOut(id=t.id, name=t.name, all_halls=t.all_halls,
                             hall_ids=t.hall_ids)
            for t in template.totals
        ],
    )


@router.get("", response_model=ReportTemplateOut)
async def get_template(db: AsyncSession = Depends(get_db),
                       _: User = Depends(_guard)) -> ReportTemplateOut:
    return _out(await svc.get_template(db))


@router.put("", response_model=ReportTemplateOut)
async def replace_template(payload: ReportTemplateIn,
                           db: AsyncSession = Depends(get_db),
                           actor: User = Depends(_guard)) -> ReportTemplateOut:
    try:
        template = await svc.replace_template(
            db, actor_id=actor.id,
            groups=[
                svc.TemplateGroup(id=None, name=g.name, show_subtotal=g.show_subtotal,
                                  hall_ids=g.hall_ids)
                for g in payload.groups
            ],
            totals=[
                svc.TemplateTotal(id=None, name=t.name, all_halls=t.all_halls,
                                  hall_ids=t.hall_ids)
                for t in payload.totals
            ],
        )
    except svc.InvalidTemplate as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"invalid_template: {e}")
    await db.commit()
    return _out(template)
```

- [ ] **Step 5: Подключить роутер**

В `server/app/api/v1/router.py`:

```python
from app.api.v1.routers import accountant, admin, auth, catalog, me, report_template
...
api_router.include_router(report_template.router)
```

- [ ] **Step 6: Каталог залов**

В `server/app/api/v1/routers/catalog.py` добавить импорты `select`, `Hall`, `HallBrief` и:

```python
@router.get("/halls", response_model=list[HallBrief])
async def list_halls(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[HallBrief]:
    stmt = select(Hall).where(Hall.is_active.is_(True)).order_by(Hall.name)
    halls = (await db.execute(stmt)).scalars().all()
    return [HallBrief.model_validate(h) for h in halls]
```

- [ ] **Step 7: Прогнать тесты**

Run: `cd server && uv run --no-sync pytest tests/test_report_template_api.py -q`
Expected: PASS (5 passed).

- [ ] **Step 8: Коммит**

```bash
git add server/app/schemas/report_template.py \
        server/app/api/v1/routers/report_template.py \
        server/app/api/v1/router.py \
        server/app/api/v1/routers/catalog.py \
        server/tests/test_report_template_api.py
git commit -m "feat(server): expose report template API and halls catalog"
```

---

### Task 4: Матрица периодного отчёта

**Files:**
- Modify: `server/app/services/reports.py`
- Test: `server/tests/test_reports_matrix.py`

**Interfaces:**
- Produces: `PeriodMatrix(types: list[MealType], dates: list[date], halls: list[Hall], counts: dict[date, dict[uuid.UUID, _Accumulator]])`, `async def build_period_matrix(db, *, start, end, hall_id=None) -> PeriodMatrix`.

- [ ] **Step 1: Написать падающий тест**

```python
# server/tests/test_reports_matrix.py
import datetime as dt

from app.models import (
    Day, DayHallMeal, Hall, MealKind, MealType, User, UserHall, UserMealDefault, UserRole,
)
from app.services import reports


async def test_matrix_has_counts_per_date_and_hall(db_session):
    hall = Hall(name="Зал №1")
    mt = MealType(name="Мясо", sort_order=1)
    user = User(login="ivan", password_hash="x", full_name="Иван", role=UserRole.eater)
    db_session.add_all([hall, mt, user])
    await db_session.flush()
    db_session.add(UserHall(user_id=user.id, hall_id=hall.id))
    user.default_meal_type_id = mt.id
    for offset in (0, 1):
        day = Day(date=dt.date(2026, 6, 10) + dt.timedelta(days=offset))
        db_session.add(day)
        await db_session.flush()
        for mk in MealKind:
            db_session.add(DayHallMeal(day_id=day.id, hall_id=hall.id, meal_kind=mk, is_served=True))
    db_session.add(UserMealDefault(user_id=user.id, meal_kind=MealKind.breakfast, is_going=True))
    await db_session.flush()

    matrix = await reports.build_period_matrix(
        db_session, start=dt.date(2026, 6, 10), end=dt.date(2026, 6, 11)
    )

    assert matrix.dates == [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    assert [h.name for h in matrix.halls] == ["Зал №1"]
    for day_date in matrix.dates:
        acc = matrix.counts[day_date][hall.id]
        assert acc.by_type[MealKind.breakfast][mt.id] == 1
        assert acc.by_type[MealKind.lunch][mt.id] == 0
```

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_reports_matrix.py -q`
Expected: FAIL — `AttributeError: module 'app.services.reports' has no attribute 'build_period_matrix'`.

- [ ] **Step 3: Добавить матрицу**

В `server/app/services/reports.py` после `build_period_report`:

```python
import dataclasses  # в шапку файла


@dataclasses.dataclass
class PeriodMatrix:
    types: list[MealType]
    dates: list[date]
    halls: list[Hall]
    counts: dict[date, dict[uuid.UUID, _Accumulator]]


async def build_period_matrix(
    db: AsyncSession, *, start: date, end: date, hall_id: uuid.UUID | None = None
) -> PeriodMatrix:
    types = await _active_types(db)
    fallback_id = types[0].id if types else None
    type_ids = [t.id for t in types]
    dates = list(_iter_dates(start, end)) if end >= start else []
    halls = await _halls(db, hall_id)

    counts: dict[date, dict[uuid.UUID, _Accumulator]] = {}
    for hall in halls:
        eaters = await _eaters(db, hall.id)
        for day_date in dates:
            acc = _Accumulator(type_ids)
            await _accumulate(db, eaters, [day_date], types, fallback_id, acc)
            counts.setdefault(day_date, {})[hall.id] = acc

    return PeriodMatrix(types=types, dates=dates, halls=halls, counts=counts)
```

- [ ] **Step 4: Прогнать тесты**

Run: `cd server && uv run --no-sync pytest tests/test_reports_matrix.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Коммит**

```bash
git add server/app/services/reports.py server/tests/test_reports_matrix.py
git commit -m "feat(server): build per-date report matrix"
```

---

### Task 5: Нормализованные данные и новый генератор Excel

**Files:**
- Create: `server/app/services/report_data.py`
- Rewrite: `server/app/services/report_excel.py`
- Modify: `server/tests/test_reports_export.py` (заголовок изменился)
- Test: `server/tests/test_report_excel.py`

**Interfaces:**
- Consumes: `DailyReportOut`, `PeriodMatrix`, `ReportTemplate`.
- Produces:
  - `ReportData(types: list[tuple[uuid.UUID, str]], dates: list[date], hall_names: dict[uuid.UUID, str], counts: dict[date, dict[uuid.UUID, dict[MealKind, dict[uuid.UUID, tuple[int, int]]]]])`
  - `report_data_from_daily(report) -> ReportData`
  - `report_data_from_matrix(matrix) -> ReportData`
  - `daily_report_to_xlsx(data, template, *, show_reserve: bool) -> bytes`
  - `period_report_to_xlsx(data, template, *, show_reserve: bool) -> bytes`

- [ ] **Step 1: Написать падающий тест генератора**

```python
# server/tests/test_report_excel.py
import datetime as dt
import io
import uuid

import openpyxl

from app.models import MealKind
from app.services import report_excel
from app.services.report_data import ReportData
from app.services.report_template import ReportTemplate, TemplateGroup, TemplateTotal

T1, T2 = uuid.uuid4(), uuid.uuid4()
H1, H2 = uuid.uuid4(), uuid.uuid4()


def _data():
    zeros = {mk: {T1: (0, 0), T2: (0, 0)} for mk in MealKind}
    breakfast = dict(zeros)
    breakfast[MealKind.breakfast] = {T1: (5, 2), T2: (1, 0)}
    lunch = dict(zeros)
    lunch[MealKind.lunch] = {T1: (3, 0), T2: (0, 0)}
    return ReportData(
        types=[(T1, "Мясо"), (T2, "Рыба")],
        dates=[dt.date(2026, 6, 10)],
        hall_names={H1: "Зал №1", H2: "Зал №2"},
        counts={dt.date(2026, 6, 10): {H1: breakfast, H2: lunch}},
    )


def _sheet(content):
    return openpyxl.load_workbook(io.BytesIO(content)).active


def test_daily_layout_with_groups_and_total():
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True,
                              hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))

    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Зал №1" in labels
    assert "Зал №2" in labels
    assert "Итого Студенты" in labels
    assert "ИТОГО" in labels

    # строка зала: Завтрак: Итог | Мясо | Рыба
    row = labels.index("Зал №1") + 1
    assert ws.cell(row=row, column=2).value == 6      # 5 + 1
    assert ws.cell(row=row, column=3).value == 5      # Мясо
    assert ws.cell(row=row, column=4).value == 1      # Рыба

    # подытог группы = оба зала: завтрак 6, обед 3 (обед — 5-я колонка)
    sub = labels.index("Итого Студенты") + 1
    assert ws.cell(row=sub, column=2).value == 6
    assert ws.cell(row=sub, column=5).value == 3


def test_total_counts_hall_once_when_it_is_in_two_groups():
    template = ReportTemplate(
        groups=[
            TemplateGroup(id=None, name="A", show_subtotal=True, hall_ids=[H1]),
            TemplateGroup(id=None, name="B", show_subtotal=True, hall_ids=[H1]),
        ],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    total = labels.index("ИТОГО") + 1
    # завтрак только у H1 (6), обед только у H2 (3); H1 не удваивается
    assert ws.cell(row=total, column=2).value == 6
    assert ws.cell(row=total, column=5).value == 3


def test_reserve_column_toggle():
    template = ReportTemplate(totals=[TemplateTotal(id=None, name="ИТОГО",
                                                     all_halls=True, hall_ids=[])])
    plain = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))
    with_reserve = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=True))

    headers = [with_reserve.cell(row=4, column=c).value for c in range(1, 10)]
    assert "Рез." in headers
    plain_headers = [plain.cell(row=4, column=c).value for c in range(1, 10)]
    assert "Рез." not in plain_headers
    assert with_reserve.max_column == plain.max_column + 4


def test_empty_template_falls_back_to_flat_halls():
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), ReportTemplate(), show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Зал №1" in labels and "Зал №2" in labels
    assert "ИТОГО" in labels


def test_period_layout_has_day_blocks():
    data = _data()
    data.dates = [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    data.counts[dt.date(2026, 6, 11)] = data.counts[dt.date(2026, 6, 10)]
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True, hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.period_report_to_xlsx(data, template, show_reserve=True))

    assert ws.title == "Отчет 2д"
    headers = [ws.cell(row=4, column=c).value for c in range(1, 20)]
    assert headers.count("Звтр") == 2
    assert headers.count("Звтр рез.") == 2
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Студенты" in labels
    assert "Мясо" in labels
    assert "ИТОГО" in labels
```

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_report_excel.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.report_data'`.

- [ ] **Step 3: Слой данных**

```python
# server/app/services/report_data.py
import uuid
from dataclasses import dataclass, field
from datetime import date

from app.models import MealKind
from app.schemas.report import DailyReportOut
from app.services.reports import PeriodMatrix

TypePair = tuple[uuid.UUID, str]
MealCounts = dict[MealKind, dict[uuid.UUID, tuple[int, int]]]
DayCounts = dict[uuid.UUID, MealCounts]


@dataclass
class ReportData:
    types: list[TypePair] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)
    hall_names: dict[uuid.UUID, str] = field(default_factory=dict)
    counts: dict[date, DayCounts] = field(default_factory=dict)


def report_data_from_daily(report: DailyReportOut) -> ReportData:
    if not report.halls:
        return ReportData(dates=[report.date])
    types: list[TypePair] = [
        (t.meal_type_id, t.name) for t in report.halls[0].meals[0].by_type
        if t.meal_type_id is not None
    ]
    hall_names: dict[uuid.UUID, str] = {}
    counts: DayCounts = {}
    for hall in report.halls:
        hall_names[hall.hall_id] = hall.hall_name
        per_meal: MealCounts = {}
        for meal in hall.meals:
            totals = {t.meal_type_id: t.count for t in meal.by_type}
            reserves = {t.meal_type_id: t.count for t in meal.reserve_by_type}
            per_meal[meal.meal_kind] = {
                tid: (totals.get(tid, 0), reserves.get(tid, 0)) for tid, _ in types
            }
        counts[hall.hall_id] = per_meal
    return ReportData(types=types, dates=[report.date], hall_names=hall_names,
                      counts={report.date: counts})


def report_data_from_matrix(matrix: PeriodMatrix) -> ReportData:
    types: list[TypePair] = [(t.id, t.name) for t in matrix.types]
    hall_names = {h.id: h.name for h in matrix.halls}
    counts: dict[date, DayCounts] = {}
    for day_date in matrix.dates:
        per_day: DayCounts = {}
        for hall_id, acc in matrix.counts[day_date].items():
            per_day[hall_id] = {
                mk: {
                    tid: (acc.by_type[mk].get(tid, 0), acc.reserve[mk].get(tid, 0))
                    for tid, _ in types
                }
                for mk in MealKind
            }
        counts[day_date] = per_day
    return ReportData(types=types, dates=list(matrix.dates), hall_names=hall_names,
                      counts=counts)
```

- [ ] **Step 4: Генератор**

```python
# server/app/services/report_excel.py
import io
from datetime import date
from typing import cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.models import MealKind
from app.services.report_data import DayCounts, ReportData
from app.services.report_template import ReportTemplate

MEAL_LABELS = {
    MealKind.breakfast: "Завтрак",
    MealKind.lunch: "Обед",
    MealKind.snack: "Полдник",
    MealKind.dinner: "Ужин",
}
MEAL_SHORT = {
    MealKind.breakfast: "Звтр",
    MealKind.lunch: "Обд",
    MealKind.snack: "Плдн",
    MealKind.dinner: "Ужн",
}

_THIN = Side(style="thin")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_BOLD = Font(bold=True)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _fmt(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _weekday(value: date) -> str:
    return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][value.weekday()]


def _values(counts: DayCounts, hall_ids: list[UUID], meal: MealKind,
            type_ids: list[UUID], reserve: bool) -> tuple[list[int], int]:
    """Сумма по залам без повторов: зал, указанный дважды, считается один раз."""
    per_type = [0] * len(type_ids)
    total = 0
    for hall_id in dict.fromkeys(hall_ids):
        per_hall = counts.get(hall_id)
        if not per_hall:
            continue
        for index, type_id in enumerate(type_ids):
            normal, reserved = per_hall.get(meal, {}).get(type_id, (0, 0))
            value = reserved if reserve else normal
            per_type[index] += value
            total += value
    return per_type, total


def _put_total_row(ws: Worksheet, row: int, label: str, counts: DayCounts,
                   hall_ids: list[UUID], type_ids: list[UUID], show_reserve: bool) -> None:
    ws.cell(row=row, column=1, value=label).font = _BOLD
    col = 2
    for meal in MealKind:
        per_type, total = _values(counts, hall_ids, meal, type_ids, reserve=False)
        ws.cell(row=row, column=col, value=total); col += 1
        for value in per_type:
            ws.cell(row=row, column=col, value=value); col += 1
        if show_reserve:
            _, reserved = _values(counts, hall_ids, meal, type_ids, reserve=True)
            ws.cell(row=row, column=col, value=reserved); col += 1


def daily_report_to_xlsx(data: ReportData, template: ReportTemplate, *,
                         show_reserve: bool) -> bytes:
    wb = Workbook()
    ws = cast(Worksheet, wb.active)
    ws.title = "Отчет 1д"
    if not data.dates:
        buffer = io.BytesIO(); wb.save(buffer); return buffer.getvalue()

    day = data.dates[0]
    counts = data.counts.get(day, {})
    type_ids = [tid for tid, _ in data.types]
    block = 1 + len(type_ids) + (1 if show_reserve else 0)
    last_col = 1 + block * len(MealKind)

    ws.cell(row=1, column=1,
            value=f"Количество питающихся по залам за: {_fmt(day)}").font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)

    ws.cell(row=3, column=1, value="Зал")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    col = 2
    for meal in MealKind:
        start = col
        headers = ["Итог"] + [name for _, name in data.types]
        if show_reserve:
            headers.append("Рез.")
        for header in headers:
            ws.cell(row=4, column=col, value=header); col += 1
        ws.cell(row=3, column=start, value=MEAL_LABELS[meal])
        ws.merge_cells(start_row=3, start_column=start, end_row=3, end_column=col - 1)

    row = 5
    groups = template.groups or []
    totals = template.totals or []

    if not groups and not totals:
        all_halls = list(data.hall_names.keys())
        for hall_id in all_halls:
            ws.cell(row=row, column=1, value=data.hall_names[hall_id])
            col = 2
            for meal in MealKind:
                per_type, total = _values(counts, [hall_id], meal, type_ids, reserve=False)
                ws.cell(row=row, column=col, value=total); col += 1
                for value in per_type:
                    ws.cell(row=row, column=col, value=value); col += 1
                if show_reserve:
                    _, reserved = _values(counts, [hall_id], meal, type_ids, reserve=True)
                    ws.cell(row=row, column=col, value=reserved); col += 1
            row += 1
        _put_total_row(ws, row, "ИТОГО", counts, all_halls, type_ids, show_reserve)
        row += 1
    else:
        for group in groups:
            for hall_id in group.hall_ids:
                ws.cell(row=row, column=1, value=data.hall_names.get(hall_id, "Зал"))
                col = 2
                for meal in MealKind:
                    per_type, total = _values(counts, [hall_id], meal, type_ids, reserve=False)
                    ws.cell(row=row, column=col, value=total); col += 1
                    for value in per_type:
                        ws.cell(row=row, column=col, value=value); col += 1
                    if show_reserve:
                        _, reserved = _values(counts, [hall_id], meal, type_ids, reserve=True)
                        ws.cell(row=row, column=col, value=reserved); col += 1
                row += 1
            if group.show_subtotal:
                _put_total_row(ws, row, f"Итого {group.name}", counts,
                               group.hall_ids, type_ids, show_reserve)
                row += 1
        all_halls = list(data.hall_names.keys())
        for total in totals:
            hall_ids = all_halls if total.all_halls else total.hall_ids
            _put_total_row(ws, row, total.name, counts, hall_ids, type_ids, show_reserve)
            row += 1

    _finish(ws, row - 1, last_col, first_data_row=5)
    buffer = io.BytesIO(); wb.save(buffer); return buffer.getvalue()


def period_report_to_xlsx(data: ReportData, template: ReportTemplate, *,
                          show_reserve: bool) -> bytes:
    wb = Workbook()
    ws = cast(Worksheet, wb.active)
    days = data.dates
    ws.title = f"Отчет {len(days)}д"
    if not days:
        buffer = io.BytesIO(); wb.save(buffer); return buffer.getvalue()

    type_ids = [tid for tid, _ in data.types]
    per_meal = 4 * (2 if show_reserve else 1)
    last_col = 1 + per_meal * len(days)

    ws.cell(row=1, column=1,
            value=f"Количество питающихся за период: {_fmt(days[0])} – {_fmt(days[-1])}"
            ).font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)

    ws.cell(row=3, column=1, value="Группа")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    col = 2
    for day in days:
        start = col
        for meal in MealKind:
            ws.cell(row=4, column=col, value=MEAL_SHORT[meal]); col += 1
            if show_reserve:
                ws.cell(row=4, column=col, value=f"{MEAL_SHORT[meal]} рез."); col += 1
        ws.cell(row=3, column=start, value=f"{_weekday(day)} {_fmt(day)}")
        ws.merge_cells(start_row=3, start_column=start, end_row=3, end_column=col - 1)

    def write_values(row: int, hall_ids: list[UUID], type_subset: list[UUID]) -> None:
        col = 2
        for day in days:
            counts = data.counts.get(day, {})
            for meal in MealKind:
                _, total = _values(counts, hall_ids, meal, type_subset, reserve=False)
                ws.cell(row=row, column=col, value=total); col += 1
                if show_reserve:
                    _, reserved = _values(counts, hall_ids, meal, type_subset, reserve=True)
                    ws.cell(row=row, column=col, value=reserved); col += 1

    row = 5
    groups = template.groups or []
    totals = template.totals or []
    all_halls = list(data.hall_names.keys())

    if not groups and not totals:
        ws.cell(row=row, column=1, value="Все залы").font = _BOLD
        write_values(row, all_halls, type_ids); row += 1
        ws.cell(row=row, column=1, value="ИТОГО").font = _BOLD
        write_values(row, all_halls, type_ids); row += 1
    else:
        for group in groups:
            ws.cell(row=row, column=1, value=group.name).font = _BOLD
            write_values(row, group.hall_ids, type_ids); row += 1
            for type_id, name in data.types:
                ws.cell(row=row, column=1, value=name)
                write_values(row, group.hall_ids, [type_id]); row += 1
        for total in totals:
            hall_ids = all_halls if total.all_halls else total.hall_ids
            ws.cell(row=row, column=1, value=total.name).font = _BOLD
            write_values(row, hall_ids, type_ids); row += 1

    _finish(ws, row - 1, last_col, first_data_row=5)
    buffer = io.BytesIO(); wb.save(buffer); return buffer.getvalue()


def _finish(ws: Worksheet, last_row: int, last_col: int, *, first_data_row: int) -> None:
    for row in ws.iter_rows(min_row=3, max_row=last_row, min_col=1, max_col=last_col):
        for cell in row:
            cell.border = _BORDER
            if cell.row <= 4:
                cell.font = _BOLD
                cell.alignment = _CENTER
    for col in range(1, last_col + 1):
        widest = 0
        for row in range(3, last_row + 1):
            value = ws.cell(row=row, column=col).value
            if value is not None:
                widest = max(widest, len(str(value)))
        ws.column_dimensions[get_column_letter(col)].width = min(max(widest + 2, 7), 30)
    ws.freeze_panes = f"B{first_data_row}"
```

- [ ] **Step 5: Прогнать тесты генератора**

Run: `cd server && uv run --no-sync pytest tests/test_report_excel.py -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Обновить существующие тесты экспорта**

В `server/tests/test_reports_export.py` заменить проверки заголовка на:

```python
    assert str(ws.cell(row=1, column=1).value).startswith("Количество питающихся")
```

(в обоих тестах).

- [ ] **Step 7: Коммит**

```bash
git add server/app/services/report_data.py server/app/services/report_excel.py \
        server/tests/test_report_excel.py server/tests/test_reports_export.py
git commit -m "feat(server): build excel report from template"
```

---

### Task 6: Экспорт использует шаблон и флаг резерва

**Files:**
- Modify: `server/app/api/v1/routers/accountant.py`
- Test: `server/tests/test_reports_export.py`

**Interfaces:**
- Consumes: `report_data.report_data_from_daily`, `report_data_from_matrix`, `report_template.get_template`, `report_excel.*`.
- Produces: `GET /accountant/report/export?...&reserve=true|false`, `GET /accountant/report/period/export?...&reserve=...`.

- [ ] **Step 1: Дописать тест**

В `server/tests/test_reports_export.py` добавить:

```python
async def test_export_uses_template_and_reserve_flag(client, accountant_headers, db_session):
    hall = Hall(name="Зал №1")
    db_session.add(hall)
    await db_session.commit()

    r = await client.put(
        "/api/v1/report-template",
        json={"groups": [{"name": "Студенты", "show_subtotal": True,
                          "hall_ids": [str(hall.id)]}], "totals": []},
        headers=accountant_headers,
    )
    assert r.status_code == 200

    r = await client.get(
        "/api/v1/accountant/report/export?date=2026-06-10&reserve=true",
        headers=accountant_headers,
    )
    assert r.status_code == 200
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    labels = [ws.cell(row=row, column=1).value for row in range(1, ws.max_row + 1)]
    assert "Зал №1" in labels
    assert "Итого Студенты" in labels
```

- [ ] **Step 2: Убедиться, что падает**

Run: `cd server && uv run --no-sync pytest tests/test_reports_export.py -q`
Expected: FAIL — нет строки «Итого Студенты» (шаблон не читается).

- [ ] **Step 3: Обновить роутер**

В `server/app/api/v1/routers/accountant.py`:

```python
from app.services import report_data, report_excel, report_template, reports
```

Дневной экспорт:

```python
@router.get("/report/export")
async def daily_report_export(on_date: date = Query(alias="date"),
                              hall_id: uuid.UUID | None = None,
                              reserve: bool = False,
                              db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    report = await reports.build_daily_report(db, on_date=on_date, hall_id=hall_id)
    template = await report_template.get_template(db)
    content = report_excel.daily_report_to_xlsx(
        report_data.report_data_from_daily(report), template, show_reserve=reserve
    )
    filename = f"report-{on_date.isoformat()}.xlsx"
    return Response(
        content=content, media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Периодный экспорт:

```python
@router.get("/report/period/export")
async def period_report_export(from_: date = Query(alias="from"), to: date = Query(...),
                               hall_id: uuid.UUID | None = None,
                               reserve: bool = False,
                               db: AsyncSession = Depends(get_db), _: User = Depends(_guard)):
    matrix = await reports.build_period_matrix(db, start=from_, end=to, hall_id=hall_id)
    template = await report_template.get_template(db)
    content = report_excel.period_report_to_xlsx(
        report_data.report_data_from_matrix(matrix), template, show_reserve=reserve
    )
    filename = f"report-{from_.isoformat()}_{to.isoformat()}.xlsx"
    return Response(
        content=content, media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Прогнать тесты**

Run: `cd server && uv run --no-sync pytest tests/test_reports_export.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Полный прогон бэкенда**

Run: `cd server && uv run --no-sync pytest -q`
Expected: PASS (все тесты).

- [ ] **Step 6: Коммит**

```bash
git add server/app/api/v1/routers/accountant.py server/tests/test_reports_export.py
git commit -m "feat(server): render excel exports from the report template"
```

---

### Task 7: Страница-конструктор

**Files:**
- Create: `syte/src/api/reportTemplate.ts`
- Create: `syte/src/features/reportTemplate/ReportTemplatePage.tsx`
- Modify: `syte/src/app/router.tsx`
- Modify: `syte/src/app/Sidebar.tsx`

**Interfaces:**
- Consumes: `GET/PUT /api/v1/report-template`, `GET /api/v1/catalog/halls`.
- Produces: страница `/report-template` для бухгалтера и оператора.

- [ ] **Step 1: API-хуки**

```ts
// syte/src/api/reportTemplate.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export type HallBrief = { id: string; name: string };

export type TemplateGroup = { id?: string; name: string; show_subtotal: boolean; hall_ids: string[] };
export type TemplateTotal = { id?: string; name: string; all_halls: boolean; hall_ids: string[] };
export type ReportTemplate = { groups: TemplateGroup[]; totals: TemplateTotal[] };

export const useReportTemplate = () =>
  useQuery({
    queryKey: ["report-template"],
    queryFn: () => apiFetch<ReportTemplate>("/report-template"),
  });

export const useSaveReportTemplate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportTemplate) =>
      apiFetch<ReportTemplate>("/report-template", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report-template"] }),
  });
};

export const useCatalogHalls = () =>
  useQuery({
    queryKey: ["catalog", "halls"],
    queryFn: () => apiFetch<HallBrief[]>("/catalog/halls"),
  });
```

- [ ] **Step 2: Страница**

Создать `ReportTemplatePage` с двумя блоками. Ключевые части:

```tsx
function move(list: string[], index: number, delta: number): string[] {
  const next = [...list];
  const target = index + delta;
  if (target < 0 || target >= next.length) return next;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

function HallList({ halls, selected, onChange }: {
  halls: HallBrief[];
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const byId = new Map(halls.map((h) => [h.id, h.name]));
  const free = halls.filter((h) => !selected.includes(h.id));
  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-xl border border-border-strong bg-sunken p-2">
        {selected.length === 0 && <p className="p-2 text-sm text-muted">Залы не выбраны</p>}
        {selected.map((id, index) => (
          <div key={id} className="flex min-h-11 items-center gap-2 text-sm">
            <span className="flex-1">{byId.get(id) ?? "Зал"}</span>
            <button type="button" onClick={() => onChange(move(selected, index, -1))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Выше">↑</button>
            <button type="button" onClick={() => onChange(move(selected, index, 1))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Ниже">↓</button>
            <button type="button" onClick={() => onChange(selected.filter((x) => x !== id))}
                    className="min-h-9 rounded-lg border border-border px-2" aria-label="Убрать">×</button>
          </div>
        ))}
      </div>
      <Select value="" onChange={(e) => e.target.value && onChange([...selected, e.target.value])}>
        <option value="">— добавить зал —</option>
        {free.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
      </Select>
    </div>
  );
}
```

Компоненты карточек и страница (тот же файл, вместе с хелперами выше):

```tsx
function GroupCard({ group, halls, onChange, onRemove }: {
  group: TemplateGroup;
  halls: HallBrief[];
  onChange: (next: TemplateGroup) => void;
  onRemove: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input value={group.name} placeholder="Название группы"
               onChange={(e) => onChange({ ...group, name: e.target.value })} />
        <Button variant="ghost" onClick={onRemove}>Удалить</Button>
      </div>
      <label className="mb-3 flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={group.show_subtotal}
               onChange={(e) => onChange({ ...group, show_subtotal: e.target.checked })}
               className="h-4 w-4 accent-accent" />
        Показывать подытог
      </label>
      <HallList halls={halls} selected={group.hall_ids}
                onChange={(hall_ids) => onChange({ ...group, hall_ids })} />
    </section>
  );
}

function TotalCard({ total, halls, onChange, onRemove }: {
  total: TemplateTotal;
  halls: HallBrief[];
  onChange: (next: TemplateTotal) => void;
  onRemove: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input value={total.name} placeholder="Название итога"
               onChange={(e) => onChange({ ...total, name: e.target.value })} />
        <Button variant="ghost" onClick={onRemove}>Удалить</Button>
      </div>
      <label className="mb-3 flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={total.all_halls}
               onChange={(e) => onChange({ ...total, all_halls: e.target.checked, hall_ids: [] })}
               className="h-4 w-4 accent-accent" />
        Все залы
      </label>
      {!total.all_halls && (
        <HallList halls={halls} selected={total.hall_ids}
                  onChange={(hall_ids) => onChange({ ...total, hall_ids })} />
      )}
    </section>
  );
}

export function ReportTemplatePage() {
  const toast = useToast();
  const { data: template, isLoading } = useReportTemplate();
  const { data: halls } = useCatalogHalls();
  const save = useSaveReportTemplate();
  const [groups, setGroups] = useState<TemplateGroup[]>([]);
  const [totals, setTotals] = useState<TemplateTotal[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!template || loaded) return;
    setGroups(template.groups);
    setTotals(template.totals);
    setLoaded(true);
  }, [template, loaded]);

  async function onSave() {
    try {
      await save.mutateAsync({ groups, totals });
      toast("Шаблон сохранён");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        toast("Проверьте группы и итоги");
        return;
      }
      toast("Не удалось сохранить");
    }
  }

  if (isLoading) return <div className="p-4"><Spinner /></div>;

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Конструктор отчёта</h1>
        <Button onClick={onSave} disabled={save.isPending}>Сохранить</Button>
      </header>

      <h2 className="mb-2 text-base font-semibold">Группы залов</h2>
      <div className="mb-4 flex flex-col gap-3">
        {groups.map((group, index) => (
          <GroupCard key={index} group={group} halls={halls ?? []}
                     onChange={(next) => setGroups((prev) => prev.map((g, i) => (i === index ? next : g)))}
                     onRemove={() => setGroups((prev) => prev.filter((_, i) => i !== index))} />
        ))}
        <Button variant="ghost"
                onClick={() => setGroups((prev) => [...prev, { name: "", show_subtotal: true, hall_ids: [] }])}>
          Добавить группу
        </Button>
      </div>

      <h2 className="mb-2 text-base font-semibold">Общие итоги</h2>
      <div className="flex flex-col gap-3">
        {totals.map((total, index) => (
          <TotalCard key={index} total={total} halls={halls ?? []}
                     onChange={(next) => setTotals((prev) => prev.map((t, i) => (i === index ? next : t)))}
                     onRemove={() => setTotals((prev) => prev.filter((_, i) => i !== index))} />
        ))}
        <Button variant="ghost"
                onClick={() => setTotals((prev) => [...prev, { name: "", all_halls: false, hall_ids: [] }])}>
          Добавить итог
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Маршрут**

В `syte/src/app/router.tsx` добавить импорт и маршрут в блок `RequireRole roles={["accountant", "operator"]}`:

```tsx
{ path: "/report-template", element: <ReportTemplatePage /> },
```

- [ ] **Step 4: Сайдбар**

В `syte/src/app/Sidebar.tsx`:

```ts
operator: [ ..., { to: "/report-template", label: "Конструктор отчёта", icon: "chart" } ],
accountant: [ ..., { to: "/report-template", label: "Конструктор отчёта", icon: "chart" } ],
```

- [ ] **Step 5: Сборка и тесты**

Run: `cd syte && npm run test -- --run && npm run build`
Expected: PASS, сборка чистая.

- [ ] **Step 6: Коммит**

```bash
git add syte/src/api/reportTemplate.ts syte/src/features/reportTemplate/ReportTemplatePage.tsx \
        syte/src/app/router.tsx syte/src/app/Sidebar.tsx
git commit -m "feat(front): add report template constructor page"
```

---

### Task 8: Галочка резерва в отчётах

**Files:**
- Modify: `syte/src/api/reports.ts`
- Modify: `syte/src/features/reports/DailyReportPage.tsx`
- Modify: `syte/src/features/reports/PeriodReportPage.tsx`
- Create: `syte/src/lib/reportPrefs.ts`

**Interfaces:**
- Produces: `dailyExportUrl(date, hallId?, reserve?)`, `periodExportUrl(from, to, hallId?, reserve?)`, `readReservePref()`, `writeReservePref(bool)`.

- [ ] **Step 1: Хелпер настроек**

```ts
// syte/src/lib/reportPrefs.ts
import { readLocal, writeLocal } from "./storage";

const KEY = "mda.report.reserve";

export function readReservePref(): boolean {
  return readLocal(KEY) === "1";
}

export function writeReservePref(value: boolean): void {
  writeLocal(KEY, value ? "1" : "0");
}
```

- [ ] **Step 2: Параметр в URL**

```ts
export function dailyExportUrl(date: string, hallId?: string, reserve = false): string {
  return `/api/v1/accountant/report/export?date=${date}${hallQuery(hallId)}&reserve=${reserve}`;
}

export function periodExportUrl(from: string, to: string, hallId?: string, reserve = false): string {
  return `/api/v1/accountant/report/period/export?from=${from}&to=${to}${hallQuery(hallId)}&reserve=${reserve}`;
}
```

- [ ] **Step 3: Галочка на страницах**

В `DailyReportPage` и `PeriodReportPage`:

```tsx
const [reserve, setReserve] = useState(readReservePref);

function toggleReserve(next: boolean) {
  setReserve(next);
  writeReservePref(next);
}

// в разметке рядом с кнопкой:
<label className="flex min-h-11 items-center gap-2 text-sm">
  <input type="checkbox" checked={reserve} onChange={(e) => toggleReserve(e.target.checked)}
         className="h-4 w-4 accent-accent" />
  С резервом
</label>

// вызов экспорта:
downloadExport(dailyExportUrl(date, undefined, reserve)).catch(...)
// и
downloadExport(periodExportUrl(from, to, undefined, reserve)).catch(...)
```

- [ ] **Step 4: Сборка**

Run: `cd syte && npm run test -- --run && npm run build`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add syte/src/lib/reportPrefs.ts syte/src/api/reports.ts \
        syte/src/features/reports/DailyReportPage.tsx \
        syte/src/features/reports/PeriodReportPage.tsx
git commit -m "feat(front): add reserve toggle to report exports"
```

---

### Task 9: Документация и приёмка

**Files:**
- Modify: `server/README.md`

- [ ] **Step 1: Раздел в README**

Добавить после раздела про экспорт:

```markdown
## Конструктор отчёта

Страница `/report-template` доступна бухгалтеру и оператору. Шаблон задаёт
структуру Excel:

- **Группы** — название, залы и флаг «Показывать подытог». Подытог считает залы
  группы, каждый один раз; один зал может входить в несколько групп.
- **Общие итоги** — название и набор залов либо «Все залы». Строка считает
  каждый зал один раз, поэтому при пересечении групп итог меньше суммы
  подытогов.

Пустой шаблон → отчёт строится по-старому: плоский список залов и «ИТОГО».
Кнопка «Скачать Excel» учитывает галочку «С резервом».
```

- [ ] **Step 2: Приёмочная проверка**

```bash
cd server && uv run --no-sync pytest -q
cd ../syte && npm run test -- --run && npm run build
cd ../server && docker compose up -d --build
```

Expected: тесты зелёные, сборка чистая, стек healthy.

- [ ] **Step 3: Ручная проверка**

1. Войти оператором, открыть «Конструктор отчёта».
2. Создать группу «Студенты» с двумя залами, включить подытог; добавить итог «ИТОГО» = «Все залы»; сохранить.
3. Открыть «Отчёт за день», скачать Excel — проверить строки залов, «Итого Студенты», «ИТОГО».
4. Включить «С резервом» и скачать снова — появились колонки «Рез.».
5. Открыть «Отчёт за период» за 3 дня — лист «Отчет 3д», блоки по 8 колонок.

- [ ] **Step 4: Коммит**

```bash
git add server/README.md
git commit -m "docs: describe report constructor"
```
