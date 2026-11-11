from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue import Queue


async def get_by_tenant_and_name(
    session: AsyncSession, tenant_id: UUID, name: str
) -> Queue | None:
    result = await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id, Queue.name == name)
    )
    return result.scalar_one_or_none()


async def get_by_id(
    session: AsyncSession, tenant_id: UUID, queue_id: UUID
) -> Queue | None:
    result = await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id, Queue.id == queue_id)
    )
    return result.scalar_one_or_none()


async def list_for_tenant(session: AsyncSession, tenant_id: UUID) -> list[Queue]:
    result = await session.execute(
        select(Queue).where(Queue.tenant_id == tenant_id).order_by(Queue.name)
    )
    return list(result.scalars().all())
