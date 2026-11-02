from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import (
    create_access_token,
    hash_password_async,
    needs_rehash,
    verify_password_async,
)
from app.models.user import User, UserRole

if TYPE_CHECKING:
    from app.models.company import Company
    from app.schemas.auth import SignupRequest

logger = logging.getLogger(__name__)


async def login(db: AsyncSession, email: str, password: str) -> str:
    """
    Authenticate a user by email + password and return a signed JWT.

    Raises:
        401 — invalid credentials or deactivated user
        403 — company is suspended
    """

    # Eager-load company to avoid async lazy-load crash
    result = await db.execute(
        select(User)
        .where(User.email == email)
        .options(joinedload(User.company))
    )
    user = result.scalar_one_or_none()

    # Constant-time-ish: always run verify even if user is None would be
    # ideal, but the hash is unknown. Keep the same generic error message
    # so attackers can't distinguish "no such email" from "wrong password".
    if (
        user is None
        or not user.is_active
        or not await verify_password_async(password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    # Company-level gate
    if not user.company.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Company account is suspended")

    # Best-effort rehash — don't let a transient DB error block a valid login
    try:
        if needs_rehash(user.password_hash):
            user.password_hash = await hash_password_async(password)
            await db.commit()
    except Exception:
        logger.warning("Failed to rehash password for user %s", user.id, exc_info=True)
        await db.rollback()

    return create_access_token(
        subject=str(user.id),
        extra_claims={"company_id": str(user.company_id)},
    )


async def signup(
    db: AsyncSession,
    data: "SignupRequest",
) -> tuple["Company", "User", str]:
    """
    Create a new company and its owner user, then return a signed JWT.

    Raises:
        409 — email already registered
    """
    from app.models.company import Company

    # Check for duplicate email
    existing = await db.execute(
        select(User).where(User.email == data.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A user with this email already exists",
        )

    # Create company
    company = Company(name=data.company_name)
    db.add(company)
    await db.flush()  # Populate company.id

    # Create owner user
    password_hash = await hash_password_async(data.password)
    owner = User(
        name=data.name,
        email=data.email.lower(),
        password_hash=password_hash,
        role=UserRole.OWNER,
        company_id=company.id,
    )
    db.add(owner)
    await db.commit()
    await db.refresh(company)
    await db.refresh(owner)

    access_token = create_access_token(
        subject=str(owner.id),
        extra_claims={"company_id": str(company.id)},
    )

    return company, owner, access_token