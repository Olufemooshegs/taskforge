from uuid import UUID

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import UnauthorizedError


async def require_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> UUID:
    settings = get_settings()
    if not x_api_key or not settings.api_key or x_api_key != settings.api_key:
        raise UnauthorizedError("Missing or invalid API key")
    return UUID(settings.tenant_id)
