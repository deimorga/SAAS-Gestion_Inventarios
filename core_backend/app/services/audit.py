from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogEntry, PerformerInfo
from app.schemas.common import PaginatedResponse, PaginationMeta


async def log_action(
    db: AsyncSession,
    tenant_id: str,
    entity: str,
    entity_id: str,
    action: str,
    new_values: dict,
    performed_by: dict,
    old_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    log = AuditLog(
        id=str(uuid4()),
        tenant_id=tenant_id,
        entity=entity,
        entity_id=entity_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        performed_by=performed_by,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.commit()


async def get_audit_logs(
    db: AsyncSession,
    tenant_id: str,
    page: int,
    page_size: int,
    entity: str | None,
    action: str | None,
    user_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> PaginatedResponse:
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if entity:
        query = query.where(AuditLog.entity == entity)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.performed_by["id"].astext == user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    rows = await db.execute(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = rows.scalars().all()

    entries = [
        AuditLogEntry(
            id=log.id,
            entity=log.entity,
            entity_id=log.entity_id,
            action=log.action,
            old_values=log.old_values,
            new_values=log.new_values,
            performed_by=PerformerInfo(**log.performed_by),
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return PaginatedResponse(
        data=entries,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=-(-total // page_size),
        ),
    )
