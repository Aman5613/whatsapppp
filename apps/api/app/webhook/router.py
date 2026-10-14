"""Meta WhatsApp Cloud API Webhook Router."""

import json
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_value
from app.core.database import get_session
from app.models.business import Business
from app.models.whatsapp_number import WhatsAppNumber
from app.webhook.handlers import process_webhook_event
from app.webhook.signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])


@router.get("/{webhook_key}", response_class=PlainTextResponse)
async def verify_webhook(
    webhook_key: str,
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Meta WhatsApp Webhook verification handshake.

    Meta calls this endpoint with hub.mode, hub.verify_token, and hub.challenge
    when you configure or verify the webhook in Meta App Dashboard.
    """
    if hub_mode != "subscribe" or not hub_verify_token or not hub_challenge:
        logger.warning("Invalid verification params received on webhook_key=%s", webhook_key)
        raise HTTPException(status_code=400, detail="Missing verification parameters")

    # Look up business
    biz_stmt = select(Business).where(Business.webhook_key == webhook_key)
    biz_res = await session.execute(biz_stmt)
    business = biz_res.scalar_one_or_none()
    if not business:
        logger.warning("Webhook verification for unknown business key: %s", webhook_key)
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # Match verify_token on configured WhatsAppNumber for this business
    num_stmt = select(WhatsAppNumber).where(
        WhatsAppNumber.business_id == business.id,
        WhatsAppNumber.verify_token == hub_verify_token,
    )
    num_res = await session.execute(num_stmt)
    number = num_res.scalar_one_or_none()

    if not number:
        logger.warning(
            "Verify token mismatch for business=%s (token=%s)",
            business.id,
            hub_verify_token,
        )
        raise HTTPException(status_code=403, detail="Verification token mismatch")

    logger.info("WhatsApp webhook verified successfully for business=%s", business.id)
    return PlainTextResponse(content=hub_challenge, status_code=200)


@router.post("/{webhook_key}")
async def receive_webhook(
    webhook_key: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    session: AsyncSession = Depends(get_session),
):
    """Receive incoming WhatsApp events from Meta.

    Verifies X-Hub-Signature-256 using the specific business's app secret,
    returns 200 immediately, and queues processing in a background task.
    """
    # 1. Look up Business by webhook_key
    biz_stmt = select(Business).where(Business.webhook_key == webhook_key)
    biz_res = await session.execute(biz_stmt)
    business = biz_res.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    # 2. Read raw payload bytes for signature verification
    raw_body = await request.body()
    try:
        payload_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    # 3. Extract phone_number_id from payload metadata to fetch specific app secret
    phone_number_id = None
    try:
        entries = payload_data.get("entry", [])
        if entries and entries[0].get("changes"):
            value = entries[0]["changes"][0].get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id")
    except Exception as exc:
        logger.warning("Could not extract phone_number_id from payload: %s", exc)

    if not phone_number_id:
        # If payload is empty or unknown structure, reject or return 200
        logger.warning("No phone_number_id in payload, cannot authenticate event")
        return {"status": "ignored"}

    # 4. Look up WhatsAppNumber to retrieve decrypted app secret
    num_stmt = select(WhatsAppNumber).where(
        WhatsAppNumber.business_id == business.id,
        WhatsAppNumber.phone_number_id == phone_number_id,
    )
    num_res = await session.execute(num_stmt)
    number = num_res.scalar_one_or_none()
    if not number:
        logger.warning("No registered WhatsAppNumber for phone_number_id=%s", phone_number_id)
        raise HTTPException(status_code=403, detail="Unregistered phone number")

    app_secret = decrypt_value(number.app_secret_enc)
    if not app_secret:
        raise HTTPException(status_code=500, detail="App secret configuration error")

    # 5. Verify HMAC Signature
    if not verify_signature(raw_body, x_hub_signature_256, app_secret):
        logger.warning("Signature verification failed for business=%s", business.id)
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 6. Queue background processing and return 200 immediately
    background_tasks.add_task(process_webhook_event, business.id, payload_data)
    return {"status": "ok"}
