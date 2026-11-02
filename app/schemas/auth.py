from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    """Input required to create a company workspace and its owner."""

    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)


class AuthUserResponse(BaseModel):
    """Public user information returned after authentication."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    company_id: UUID


class CompanyResponse(BaseModel):
    """Public company information."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SignupResponse(BaseModel):
    """Response returned after successful signup."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: AuthUserResponse
    company: CompanyResponse


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Credentials submitted by a user during login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access token returned after successful login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"