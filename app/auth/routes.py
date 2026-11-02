# pyrefly: ignore [missing-import]
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import login, signup as register_owner
 
#demo
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import AuthUserResponse


from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup_route(
    data: SignupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SignupResponse:
    """Create a new company workspace and its owner account."""
    company, owner, access_token = await register_owner(
        db=db,
        data=data,
    )

    return SignupResponse(
        access_token=access_token,
        user=owner,
        company=company,
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login_route(
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate a user and return an access token."""
    access_token = await login(db=db, email=data.email, password=data.password)
    return TokenResponse(access_token=access_token)



# ---------------------------------------------------------------------------
# jwt testing with this endpoint just test
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=AuthUserResponse,
)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AuthUserResponse:
    """Return the authenticated user's profile."""

    return AuthUserResponse.model_validate(current_user)