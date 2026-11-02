from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.invitation import InvitationStatus
from app.models.user import UserRole


class InvitationCreateRequest(BaseModel):
    """Data required to invite a user to a workspace."""

    email: EmailStr
    role: Literal[UserRole.ADMIN, UserRole.MEMBER]

    @field_validator("email")       
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class InvitationAcceptRequest(BaseModel):
    """Data required to accept a workspace invitation."""

    token: str = Field(min_length=32, max_length=512)
    name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v


class InvitationResponse(BaseModel):
    """Invitation info for admins (list / create responses)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRole
    status: InvitationStatus
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationCreateResponse(InvitationResponse):
    """Response after creating an invitation — includes the raw token for dev/testing.

    WARNING: In production, remove this and send the token via email instead.
    """

    invitation_token: str


class InvitationPreviewResponse(BaseModel):
    """Shown on the accept page, before the invited person sets a password."""

    email: EmailStr
    role: UserRole
    company_name: str
    expires_at: datetime