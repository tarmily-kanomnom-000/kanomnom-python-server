from datetime import UTC, datetime

from api.routes.medusa.dependencies import governor as medusa_governor
from api.routes.nextcloud.dependencies import governor as nextcloud_governor
from bot import BOT_ENABLED, TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from core.cache.grist_inquiry_idempotency import (
    GristInquiryIdempotencyStore,
    load_grist_inquiry_idempotency_config,
)
from core.grist.exceptions import MedusaOrderFetchError
from core.grist.inquiry_handler import handle_inquiries
from fastapi import APIRouter, HTTPException, status
from models.customer_inquiry_model import Inquiries

router = APIRouter(prefix="/grist", tags=["grist"])
idempotency_store = GristInquiryIdempotencyStore(
    load_grist_inquiry_idempotency_config()
)


@router.post("/new_inquiry_webhook")
async def grist_status(inquiries: Inquiries) -> dict:
    """Handles new customer inquiries and sends a message to the Telegram group."""
    now = datetime.now(UTC)
    telegram_sender = telegram_app.bot if telegram_app is not None else None
    try:
        message_count = await handle_inquiries(
            inquiries=inquiries,
            now=now,
            medusa_governor=medusa_governor,
            nextcloud_governor=nextcloud_governor,
            idempotency_store=idempotency_store,
            telegram_sender=telegram_sender,
            telegram_chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
            bot_enabled=BOT_ENABLED,
        )
    except MedusaOrderFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch Medusa order information",
        ) from exc

    return {"status": "messages sent", "count": message_count}
