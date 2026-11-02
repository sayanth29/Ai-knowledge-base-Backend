import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, hash_password_async
from app.models.company import Company
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User, UserRole
from app.schemas.invitation import (
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationPreviewResponse,
)

INVITATION_EXPIRY_DAYS = 7


def hash_invitation_token(token: str) -> str:
    """Hash an invitation token before storing it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_invitation(
    db: AsyncSession,
    *,
    invited_by: User,
    data: InvitationCreateRequest,
) -> tuple[Invitation, str]:
    """Create a workspace invitation and return it with its raw token."""

    # 1. Validate the inviter's role.
    if invited_by.role not in {UserRole.OWNER, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to invite users.",
        )

    # 2. Admins can invite members, but not other admins.
    if invited_by.role == UserRole.ADMIN and data.role != UserRole.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins can invite members only.",
        )

    email = str(data.email).strip().lower()

    # 3. Check whether this email already has an account.
    existing_user = await db.scalar(
        select(User).where(User.email == email)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # 4. Check for an existing pending invitation.
    existing_invitation = await db.scalar(
        select(Invitation).where(
            Invitation.company_id == invited_by.company_id,
            Invitation.email == email,
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    if existing_invitation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending invitation already exists for this email.",
        )

    # 5. Generate a secure invitation token.
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)

    # 6. Set the expiration time.
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=INVITATION_EXPIRY_DAYS
    )

    # 7. Create the invitation for the inviter's company.
    invitation = Invitation(
        company_id=invited_by.company_id,
        invited_by_user_id=invited_by.id,
        email=email,
        role=data.role,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
    )

    db.add(invitation)

    try:
        await db.commit()
        await db.refresh(invitation)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The invitation could not be created because a conflicting record exists.",
        ) from exc

    return invitation, raw_token


async def list_invitations(
    db: AsyncSession,
    *,
    company_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Invitation]:
    """List invitations belonging to a workspace, ordered newest first."""
    query = (
        select(Invitation)
        .where(Invitation.company_id == company_id)
        .order_by(Invitation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.scalars(query)
    return list(result.all())


async def preview_invitation(
    db: AsyncSession,
    *,
    token: str,
) -> InvitationPreviewResponse:
    """Preview an invitation before accepting, ensuring it is valid and unexpired."""
    token_hash = hash_invitation_token(token)
    query = (
        select(Invitation)
        .where(Invitation.token_hash == token_hash)
        .options(selectinload(Invitation.company))
    )
    invitation = await db.scalar(query)

    if not invitation or invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has already been used.",
        )

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation has expired.",
        )

    return InvitationPreviewResponse(
        email=invitation.email,
        role=invitation.role,
        company_name=invitation.company.name,
        expires_at=invitation.expires_at,
    )


async def accept_invitation(
    db: AsyncSession,
    *,
    data: InvitationAcceptRequest,
) -> tuple[Company, User, str]:
    """Accept an invitation, create the user, mark invite accepted, and return JWT."""
    token_hash = hash_invitation_token(data.token)
    query = (
        select(Invitation)
        .where(Invitation.token_hash == token_hash)
        .options(selectinload(Invitation.company))
    )
    invitation = await db.scalar(query)

    if not invitation or invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or has already been used.",
        )

    now = datetime.now(timezone.utc)
    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation has expired.",
        )

    if not invitation.company.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company account is suspended.",
        )

    # Check if an account with this email was created in the meantime
    existing_user = await db.scalar(
        select(User).where(User.email == invitation.email)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Hash the new user's password
    password_hash = await hash_password_async(data.password)

    # Create the new user in the invited company
    new_user = User(
        company_id=invitation.company_id,
        name=data.name,
        email=invitation.email,
        password_hash=password_hash,
        role=UserRole(invitation.role.value),
        is_active=True,
    )
    db.add(new_user)

    # Mark the invitation as accepted
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = now

    try:
        await db.commit()
        await db.refresh(new_user)
        await db.refresh(invitation.company)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A conflict occurred while creating the account.",
        ) from exc

    # Generate access token
    access_token = create_access_token(
        subject=str(new_user.id),
        extra_claims={"company_id": str(new_user.company_id)},
    )

    return invitation.company, new_user, access_token


async def revoke_invitation(
    db: AsyncSession,
    *,
    company_id: UUID,
    invitation_id: UUID,
) -> Invitation:
    """Revoke a pending invitation for a company."""
    query = select(Invitation).where(
        Invitation.id == invitation_id,
        Invitation.company_id == company_id,
    )
    invitation = await db.scalar(query)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found.",
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot revoke an invitation with status '{invitation.status.value}'.",
        )

    invitation.status = InvitationStatus.REVOKED
    await db.commit()
    await db.refresh(invitation)
    return invitation
