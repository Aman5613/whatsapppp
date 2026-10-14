"""Settings and Database Connection API router."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.crypto import decrypt_value, encrypt_value, mask_secret
from app.core.database import (
    check_db_connection,
    get_session,
    test_connection,
    update_database_connection,
)
from app.models.business import Business
from app.models.whatsapp_number import WhatsAppNumber
from app.services.ai.registry import get_provider
from app.services.ai.types import Msg
from app.services.whatsapp.client import WhatsAppClient

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class WhatsAppSettingsOut(BaseModel):
    phone_number_id: str
    waba_id: str | None = None
    verify_token: str
    has_access_token: bool
    access_token_masked: str | None = None
    has_app_secret: bool
    app_secret_masked: str | None = None


class BusinessSettingsOut(BaseModel):
    business_id: uuid.UUID
    business_name: str
    system_prompt: str
    language_pref: str
    tone: str
    ai_provider: str
    ai_model: str
    has_ai_key: bool
    ai_key_masked: str | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    has_fallback_key: bool
    fallback_key_masked: str | None = None
    webhook_key: str
    webhook_url: str
    whatsapp: WhatsAppSettingsOut | None = None


class UpdateSettingsRequest(BaseModel):
    business_name: str | None = None
    system_prompt: str | None = None
    language_pref: str | None = None
    tone: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None  # Write-only plain text key
    fallback_provider: str | None = None
    fallback_model: str | None = None
    fallback_key: str | None = None  # Write-only plain text key
    whatsapp_phone_number_id: str | None = None
    whatsapp_waba_id: str | None = None
    whatsapp_access_token: str | None = None  # Write-only plain text token
    whatsapp_app_secret: str | None = None  # Write-only plain text secret
    whatsapp_verify_token: str | None = None


class TestAIRequest(BaseModel):
    provider: str = Field(..., description="openai, anthropic, or gemini")
    model: str
    api_key: str | None = None  # If None, uses saved business key


class TestAIResponse(BaseModel):
    success: bool
    message: str
    latency_ms: float = 0.0


class TestWhatsAppRequest(BaseModel):
    phone_number_id: str
    access_token: str | None = None  # If None, uses saved business token


class TestWhatsAppResponse(BaseModel):
    success: bool
    message: str
    phone_data: dict[str, Any] | None = None


class DatabaseTestRequest(BaseModel):
    database_url: str = Field(..., min_length=10)


class DatabaseApplyRequest(BaseModel):
    database_url: str = Field(..., min_length=10)
    direct_database_url: str | None = None


@router.get("", response_model=BusinessSettingsOut)
async def get_settings(
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full configuration settings with masked secrets."""
    biz = await session.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    num_query = select(WhatsAppNumber).where(WhatsAppNumber.business_id == business_id)
    num_result = await session.execute(num_query)
    number = num_result.scalar_one_or_none()

    ai_plain = decrypt_value(biz.ai_api_key_enc) if biz.ai_api_key_enc else None
    fallback_plain = decrypt_value(biz.fallback_key_enc) if biz.fallback_key_enc else None

    wa_access_plain = (
        decrypt_value(number.access_token_enc) if number and number.access_token_enc else None
    )
    wa_secret_plain = (
        decrypt_value(number.app_secret_enc) if number and number.app_secret_enc else None
    )

    webhook_url = f"{app_settings.PUBLIC_BASE_URL.rstrip('/')}/webhook/{biz.webhook_key}"

    wa_data = None
    if number:
        wa_data = {
            "phone_number_id": number.phone_number_id,
            "waba_id": number.waba_id,
            "verify_token": number.verify_token,
            "has_access_token": bool(wa_access_plain),
            "access_token_masked": mask_secret(wa_access_plain) if wa_access_plain else None,
            "has_app_secret": bool(wa_secret_plain),
            "app_secret_masked": mask_secret(wa_secret_plain) if wa_secret_plain else None,
        }

    return {
        "business_id": biz.id,
        "business_name": biz.name,
        "system_prompt": biz.system_prompt,
        "language_pref": biz.language_pref,
        "tone": biz.tone,
        "ai_provider": biz.ai_provider,
        "ai_model": biz.ai_model,
        "has_ai_key": bool(ai_plain),
        "ai_key_masked": mask_secret(ai_plain) if ai_plain else None,
        "fallback_provider": biz.fallback_provider,
        "fallback_model": biz.fallback_model,
        "has_fallback_key": bool(fallback_plain),
        "fallback_key_masked": mask_secret(fallback_plain) if fallback_plain else None,
        "webhook_key": biz.webhook_key,
        "webhook_url": webhook_url,
        "whatsapp": wa_data,
    }


@router.patch("", response_model=BusinessSettingsOut)
async def update_settings(
    payload: UpdateSettingsRequest,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update business settings and credentials securely."""
    biz = await session.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    num_query = select(WhatsAppNumber).where(WhatsAppNumber.business_id == business_id)
    num_result = await session.execute(num_query)
    number = num_result.scalar_one_or_none()
    if not number:
        number = WhatsAppNumber(
            business_id=biz.id,
            phone_number_id="pending",
            access_token_enc=encrypt_value(""),
            app_secret_enc=encrypt_value(""),
            verify_token=uuid.uuid4().hex,
        )
        session.add(number)

    # Business attributes
    if payload.business_name is not None:
        biz.name = payload.business_name
    if payload.system_prompt is not None:
        biz.system_prompt = payload.system_prompt
    if payload.language_pref is not None:
        biz.language_pref = payload.language_pref
    if payload.tone is not None:
        biz.tone = payload.tone
    if payload.ai_provider is not None:
        biz.ai_provider = payload.ai_provider
    if payload.ai_model is not None:
        biz.ai_model = payload.ai_model
    if payload.ai_api_key is not None and payload.ai_api_key.strip():
        biz.ai_api_key_enc = encrypt_value(payload.ai_api_key.strip())
    if payload.fallback_provider is not None:
        biz.fallback_provider = payload.fallback_provider or None
    if payload.fallback_model is not None:
        biz.fallback_model = payload.fallback_model or None
    if payload.fallback_key is not None and payload.fallback_key.strip():
        biz.fallback_key_enc = encrypt_value(payload.fallback_key.strip())

    # WhatsApp attributes
    if payload.whatsapp_phone_number_id is not None:
        number.phone_number_id = payload.whatsapp_phone_number_id
    if payload.whatsapp_waba_id is not None:
        number.waba_id = payload.whatsapp_waba_id
    if payload.whatsapp_verify_token is not None:
        number.verify_token = payload.whatsapp_verify_token
    if payload.whatsapp_access_token is not None and payload.whatsapp_access_token.strip():
        number.access_token_enc = encrypt_value(payload.whatsapp_access_token.strip())
    if payload.whatsapp_app_secret is not None and payload.whatsapp_app_secret.strip():
        number.app_secret_enc = encrypt_value(payload.whatsapp_app_secret.strip())

    await session.commit()
    return await get_settings(business_id=business_id, session=session)


@router.post("/test-ai", response_model=TestAIResponse)
async def test_ai_connection(
    payload: TestAIRequest,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> TestAIResponse:
    """Test AI model API key by sending a short ping prompt."""
    import time

    key_to_use = payload.api_key
    if not key_to_use:
        biz = await session.get(Business, business_id)
        if not biz or not biz.ai_api_key_enc:
            raise HTTPException(status_code=400, detail="No API key provided or configured.")
        key_to_use = decrypt_value(biz.ai_api_key_enc)

    try:
        provider = get_provider(
            provider_name=payload.provider,
            api_key=key_to_use,
            model=payload.model,
        )
        start_time = time.perf_counter()
        res = await provider.generate_reply(
            messages=[Msg(role="user", content="Ping. Reply with 'OK'.")],
            system_prompt="You are a ping test.",
        )
        latency = (time.perf_counter() - start_time) * 1000
        return TestAIResponse(
            success=True,
            message=f"Received: {res.content.strip()}",
            latency_ms=round(latency, 2),
        )
    except Exception as exc:
        return TestAIResponse(
            success=False,
            message=f"Connection failed: {exc}",
            latency_ms=0.0,
        )


@router.post("/test-whatsapp", response_model=TestWhatsAppResponse)
async def test_whatsapp_connection(
    payload: TestWhatsAppRequest,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> TestWhatsAppResponse:
    """Test WhatsApp Meta Graph API credentials."""
    token_to_use = payload.access_token
    if not token_to_use:
        num_query = select(WhatsAppNumber).where(WhatsAppNumber.business_id == business_id)
        result = await session.execute(num_query)
        number = result.scalar_one_or_none()
        if not number or not number.access_token_enc:
            raise HTTPException(status_code=400, detail="No WhatsApp access token configured.")
        token_to_use = decrypt_value(number.access_token_enc)

    try:
        client = WhatsAppClient()
        data = await client.get_phone_number_info(
            phone_number_id=payload.phone_number_id,
            access_token=token_to_use,
        )
        return TestWhatsAppResponse(
            success=True,
            message="WhatsApp Graph API connection successful.",
            phone_data=data,
        )
    except Exception as exc:
        return TestWhatsAppResponse(
            success=False,
            message=f"WhatsApp connection failed: {exc}",
        )


@router.get("/database/status")
async def database_status() -> dict[str, Any]:
    """Check connectivity to active runtime database."""
    connected = await check_db_connection()
    is_sqlite = app_settings.DATABASE_URL.startswith("sqlite")
    return {
        "connected": connected,
        "is_sqlite": is_sqlite,
        "pool_size": app_settings.DB_POOL_SIZE if not is_sqlite else 1,
    }


@router.post("/database/test")
async def database_test(payload: DatabaseTestRequest) -> dict[str, Any]:
    """Test a proposed PostgreSQL / Neon connection string."""
    ok, msg = await test_connection(payload.database_url)
    return {"success": ok, "message": msg}


@router.post("/database/apply")
async def database_apply(payload: DatabaseApplyRequest) -> dict[str, Any]:
    """Apply new connection string, run migrations, and rebind runtime engine."""
    try:
        await update_database_connection(
            new_url=payload.database_url,
            new_direct_url=payload.direct_database_url,
        )
        return {
            "success": True,
            "message": "Database updated and migrations applied successfully.",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
