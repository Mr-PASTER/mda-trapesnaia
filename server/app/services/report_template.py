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
            TemplateGroup(
                id=g.id, name=g.name, show_subtotal=g.show_subtotal,
                hall_ids=by_group.get(g.id, []),
            )
            for g in groups
        ],
        totals=[
            TemplateTotal(
                id=t.id, name=t.name, all_halls=t.all_halls,
                hall_ids=by_total.get(t.id, []),
            )
            for t in totals
        ],
    )


async def _validate_halls(db: AsyncSession, hall_ids: list[uuid.UUID], where: str) -> None:
    if len(set(hall_ids)) != len(hall_ids):
        raise InvalidTemplate(f"duplicate hall in {where}")
    for hall_id in hall_ids:
        hall = await db.get(Hall, hall_id)
        if hall is None or not hall.is_active:
            raise InvalidTemplate(f"hall {hall_id} not found or inactive in {where}")


async def _validate(
    db: AsyncSession,
    groups: list[TemplateGroup],
    totals: list[TemplateTotal],
) -> None:
    for group in groups:
        name = (group.name or "").strip()
        if not name:
            raise InvalidTemplate("group name is empty")
        if len(name) > 100:
            raise InvalidTemplate("group name is too long")
        await _validate_halls(db, group.hall_ids, f"group {name}")

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
        await _validate_halls(db, total.hall_ids, f"total {name}")


async def replace_template(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    groups: list[TemplateGroup],
    totals: list[TemplateTotal],
) -> ReportTemplate:
    await _validate(db, groups, totals)
    await repo.clear(db)

    for index, group in enumerate(groups):
        row = await repo.add_group(db, group.name.strip(), index, group.show_subtotal)
        for position, hall_id in enumerate(group.hall_ids):
            await repo.add_group_hall(db, row.id, hall_id, position)

    for index, total in enumerate(totals):
        row = await repo.add_total(db, total.name.strip(), index, total.all_halls)
        for position, hall_id in enumerate(total.hall_ids):
            await repo.add_total_hall(db, row.id, hall_id, position)

    await audit.record(
        db,
        actor_id=actor_id,
        action="update",
        entity_type="report_template",
        entity_id="1",
        details={"groups": len(groups), "totals": len(totals)},
    )
    await db.flush()
    return await get_template(db)
