from typing import Annotated
import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User,UserRole

bearer_scheme = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared error factories
# ---------------------------------------------------------------------------


_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_inactive_error = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Account is deactivated",
)

_company_suspended_error = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Company account is suspended",
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT, load the user, and enforce active status.

    Raises:
        401  — invalid / expired / malformed token, or user not found
        403  — user or company is deactivated
        500  — unexpected database error (logged, never leaked)
    """

    # --- Credentials check --------------------------------------------------
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # --- Token validation ---------------------------------------------------
    payload = decode_access_token(token)
    if payload is None:
        raise _credentials_error

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise _credentials_error

    # --- User lookup --------------------------------------------------------
    try:
        user = await db.get(
            User,
            user_id,
            options=[selectinload(User.company)],
        )
    except SQLAlchemyError:
        logger.exception("DB error while fetching user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    if user is None:
        raise _credentials_error

    # --- Active checks ------------------------------------------------------
    if not user.is_active:
        raise _inactive_error

    if not user.company.is_active:
        raise _company_suspended_error

    return user


async def get_current_company_id(
    user: User = Depends(get_current_user),
) -> UUID:
    """Use this in every route that touches company data (tenant isolation)."""
    return user.company_id


    
# ---  createing a dependency and checking check the user's role  -------------------------------------------------- 

def require_roles(*allowed_roles: UserRole):
    """Create a dependency that checks the user's role."""

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker