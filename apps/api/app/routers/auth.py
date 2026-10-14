"""Authentication API router."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.crypto import encrypt_value
from app.core.database import get_session
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.business import Business
from app.models.user import User
from app.models.whatsapp_number import WhatsAppNumber

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class SetupRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    business_id: uuid.UUID
    business_name: str
    webhook_key: str


class AuthStatusOut(BaseModel):
    initialized: bool


@router.get("/status", response_model=AuthStatusOut)
async def check_auth_status(
    session: AsyncSession = Depends(get_session),
) -> AuthStatusOut:
    """Check if the system has been initialized with at least one user."""
    count_query = select(func.count(User.id))
    result = await session.execute(count_query)
    user_count = result.scalar() or 0
    return AuthStatusOut(initialized=user_count > 0)


@router.post("/setup", response_model=UserOut)
async def initial_setup(
    payload: SetupRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """First-run onboarding: create initial business, number, and admin user."""
    count_query = select(func.count(User.id))
    result = await session.execute(count_query)
    if (result.scalar() or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System already initialized. Please log in.",
        )

    # 1. Create Business
    biz = Business(name=payload.business_name)
    session.add(biz)
    await session.flush()

    # 2. Create Default WhatsApp Number
    default_number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="pending_config",
        access_token_enc=encrypt_value("pending"),
        app_secret_enc=encrypt_value("pending"),
        verify_token=uuid.uuid4().hex,
    )
    session.add(default_number)
    await session.flush()

    # 3. Create Admin User
    user = User(
        business_id=biz.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()

    # 4. Issue JWT and set cookie
    token = create_access_token(
        {
            "sub": str(user.id),
            "business_id": str(biz.id),
            "email": user.email,
        }
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.PUBLIC_BASE_URL.startswith("https"),
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "id": user.id,
        "email": user.email,
        "business_id": biz.id,
        "business_name": biz.name,
        "webhook_key": biz.webhook_key,
    }


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Authenticate with email and password, set secure httpOnly cookie."""
    query = select(User).where(User.email == payload.email).options(selectinload(User.business))
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "business_id": str(user.business_id),
            "email": user.email,
        }
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.PUBLIC_BASE_URL.startswith("https"),
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "id": user.id,
        "email": user.email,
        "business_id": user.business.id,
        "business_name": user.business.name,
        "webhook_key": user.business.webhook_key,
    }


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear authentication cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return currently authenticated user and business context."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "business_id": current_user.business.id,
        "business_name": current_user.business.name,
        "webhook_key": current_user.business.webhook_key,
    }
