from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox_event import OutboxEvent


async def create(
    session: AsyncSession,
    *,
    event_id: UUID,
    tenant_id: UUID,
    event_type: str,
    payload: dict,
) -> OutboxEvent:
    event = OutboxEvent(
        id=event_id,
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    return event
