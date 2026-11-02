from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

async def list_company_users(
    db: AsyncSession,
    *,
    company_id: UUID,
) -> list[User]:
    """Return users belonging to a specific company."""

    result = await db.scalars(
        select(User)
         .where(User.company_id == company_id)
         .order_by(User.created_at.desc())
)   
    return list(result.all())
