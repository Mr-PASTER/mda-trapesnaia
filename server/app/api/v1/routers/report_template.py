from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.report_template import (
    ReportTemplateIn,
    ReportTemplateOut,
    TemplateGroupOut,
    TemplateTotalOut,
)
from app.services import report_template as svc

router = APIRouter(prefix="/report-template", tags=["report-template"])
_guard = require_roles(UserRole.accountant, UserRole.operator)


def _out(template: svc.ReportTemplate) -> ReportTemplateOut:
    return ReportTemplateOut(
        groups=[
            TemplateGroupOut(
                id=g.id, name=g.name, show_subtotal=g.show_subtotal, hall_ids=g.hall_ids
            )
            for g in template.groups
        ],
        totals=[
            TemplateTotalOut(
                id=t.id, name=t.name, all_halls=t.all_halls, hall_ids=t.hall_ids
            )
            for t in template.totals
        ],
    )


@router.get("", response_model=ReportTemplateOut)
async def get_template(
    db: AsyncSession = Depends(get_db), _: User = Depends(_guard)
) -> ReportTemplateOut:
    return _out(await svc.get_template(db))


@router.put("", response_model=ReportTemplateOut)
async def replace_template(
    payload: ReportTemplateIn,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_guard),
) -> ReportTemplateOut:
    try:
        template = await svc.replace_template(
            db,
            actor_id=actor.id,
            groups=[
                svc.TemplateGroup(
                    id=None, name=g.name, show_subtotal=g.show_subtotal, hall_ids=g.hall_ids
                )
                for g in payload.groups
            ],
            totals=[
                svc.TemplateTotal(
                    id=None, name=t.name, all_halls=t.all_halls, hall_ids=t.hall_ids
                )
                for t in payload.totals
            ],
        )
    except svc.InvalidTemplate as error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"invalid_template: {error}"
        )
    await db.commit()
    return _out(template)
