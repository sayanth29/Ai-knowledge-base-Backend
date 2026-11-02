from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.schemas.user import UserResponse
from app.users.service import list_company_users


router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)


@router.get(
    "",
    response_model=list[UserResponse],
)
async def get_company_users(
    current_user: Annotated[
        User,
        Depends(
            require_roles(
                UserRole.OWNER,
                UserRole.ADMIN,
            )
        ),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserResponse]:
    """List users in the authenticated user's company."""

    users = await list_company_users(
        db,
        company_id=current_user.company_id,
    )

    return [
        UserResponse.model_validate(user)
        for user in users
    ]