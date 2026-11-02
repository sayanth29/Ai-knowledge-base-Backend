from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.invitations.service import (
    accept_invitation,
    create_invitation,
    list_invitations,
    preview_invitation,
    revoke_invitation,
)
from app.models.invitation import Invitation
from app.models.user import User, UserRole
from app.schemas.auth import AuthUserResponse, CompanyResponse, SignupResponse
from app.schemas.invitation import (
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationPreviewResponse,
    InvitationResponse,
)

router = APIRouter(
    prefix="/api/v1/invitations",
    tags=["Invitations"],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
WorkspaceManager = Annotated[
    User,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


@router.post(
    "",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_invitation(
    data: InvitationCreateRequest,
    db: DbSession,
    current_user: WorkspaceManager,
) -> InvitationCreateResponse:
    """Invite a user to the authenticated user's workspace."""
    invitation, raw_token = await create_invitation(
        db, invited_by=current_user, data=data
    )
    return InvitationCreateResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        invitation_token=raw_token,
    )


@router.get("", response_model=list[InvitationResponse])
async def get_workspace_invitations(
    db: DbSession,
    current_user: WorkspaceManager,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Invitation]:
    """List invitations belonging to the authenticated user's workspace."""
    return await list_invitations(
        db, company_id=current_user.company_id, limit=limit, offset=offset
    )


# Public routes: the invited person has no account yet.
# Keep static paths (/preview, /accept) above any "/{invitation_id}" GET route.
@router.get("/preview", response_model=InvitationPreviewResponse)
async def get_invitation_preview(
    token: Annotated[str, Query(min_length=32, max_length=512)],
    db: DbSession,
) -> InvitationPreviewResponse:
    """Preview an invitation before the invitee accepts it."""
    return await preview_invitation(db, token=token)


@router.post(
    "/accept",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def accept_workspace_invitation(
    data: InvitationAcceptRequest,
    db: DbSession,
) -> SignupResponse:
    """Accept an invitation and return the new user's credentials."""
    company, user, access_token = await accept_invitation(db, data=data)
    return SignupResponse(
        access_token=access_token,
        user=AuthUserResponse.model_validate(user),
        company=CompanyResponse.model_validate(company),
    )


@router.delete("/{invitation_id}", response_model=InvitationResponse)
async def revoke_workspace_invitation(
    invitation_id: UUID,
    db: DbSession,
    current_user: WorkspaceManager,
) -> Invitation:
    """Revoke a pending invitation in the authenticated user's workspace."""
    return await revoke_invitation(
        db,
        company_id=current_user.company_id,
        invitation_id=invitation_id,
    )
