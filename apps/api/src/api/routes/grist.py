import logging
import os
from datetime import UTC, datetime

import requests
from fastapi import APIRouter, HTTPException, status

from api.routes.medusa.dependencies import governor as medusa_governor
from api.routes.nextcloud.dependencies import governor as nextcloud_governor
from bot import BOT_ENABLED, TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from core.medusa.exceptions import MedusaMetadataNotFoundError
from core.medusa.orders import fetch_orders
from core.nextcloud.events import NextcloudCalendarEvent, build_order_calendar_event
from models.customer_inquiry_model import Inquiries, format_phone_number
from models.medusa.order_response import MedusaOrderResponse

router = APIRouter(prefix="/grist", tags=["grist"])

MARKDOWN_V2_SPECIAL_CHARACTERS = set("\\_*[]()~`>#+-=|{}.!")  # Telegram Markdown V2 reserved characters.
PREFERRED_SUFFIX = " _\\(Preferred\\)_"  # Italicised "(Preferred)" with escaped parentheses.

logger = logging.getLogger(__name__)


def escape_markdown_v2(value: str) -> str:
    """Escape Telegram MarkdownV2-reserved characters within the provided text."""
    escaped_characters: list[str] = []

    for character in value:
        if character in MARKDOWN_V2_SPECIAL_CHARACTERS:
            escaped_characters.append(f"\\{character}")
        else:
            escaped_characters.append(character)

    return "".join(escaped_characters)


def _resolve_medusa_instance_key() -> str:
    value = os.getenv("MEDUSA_DEFAULT_INSTANCE_KEY")
    if value is None:
        return "000000"
    cleaned = value.strip()
    return cleaned or "000000"


def _resolve_nextcloud_instance_key() -> str:
    value = os.getenv("NEXTCLOUD_DEFAULT_INSTANCE_KEY")
    if value is None:
        return "000000"
    cleaned = value.strip()
    return cleaned or "000000"


def _format_medusa_order_summary(order_id: str, order_response: MedusaOrderResponse | None) -> str:
    safe_order_id = escape_markdown_v2(order_id)
    summary_lines = [f"🧾 *Medusa Order ID:* {safe_order_id}"]
    if not order_response:
        return "\n".join(summary_lines)

    order = order_response.order

    display_id = order.display_id
    status_value = order.status
    email_value = getattr(order, "email", None)
    total_value = order.total
    currency_value = getattr(order, "currency_code", None)

    if display_id is not None:
        summary_lines.append(f"🔢 *Order Number:* {escape_markdown_v2(str(display_id))}")
    if status_value:
        summary_lines.append(f"✅ *Order Status:* {escape_markdown_v2(str(status_value))}")
    if email_value:
        summary_lines.append(f"📧 *Order Email:* {escape_markdown_v2(str(email_value))}")
    if total_value is not None and currency_value:
        summary_lines.append(
            f"💵 *Order Total:* {escape_markdown_v2(str(total_value))} {escape_markdown_v2(str(currency_value).upper())}"
        )

    return "\n".join(summary_lines)


@router.post("/new_inquiry_webhook")
async def grist_status(inquiries: Inquiries) -> dict:
    """Handles new customer inquiries and sends a message to the Telegram group."""

    messages: list[str] = []
    calendar_events: list[NextcloudCalendarEvent] = []
    order_ids = [inquiry.medusa_order_id for inquiry in inquiries.root if inquiry.medusa_order_id]
    order_ids = list(dict.fromkeys(order_ids))
    order_payloads: dict[str, MedusaOrderResponse] = {}
    nextcloud_client = None
    nextcloud_instance_key: str | None = None
    now = datetime.now(UTC)

    if order_ids:
        instance_key = _resolve_medusa_instance_key()
        try:
            client = medusa_governor.client_for(instance_key)
            order_payloads = fetch_orders(client, order_ids)
        except (MedusaMetadataNotFoundError, requests.RequestException, ValueError) as exc:
            logger.exception("Failed to fetch Medusa orders for %s", instance_key)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch Medusa order information",
            ) from exc

    for inquiry in inquiries.root:
        email_value = escape_markdown_v2(inquiry.email.ascii_email) if getattr(inquiry, "email", None) else "N/A"
        formatted_phone = format_phone_number(inquiry.phone_number)
        phone_value = escape_markdown_v2(formatted_phone) if formatted_phone else "N/A"

        email_line = f"📧 *Email:* {email_value}"
        phone_line = f"📞 *Phone:* {phone_value}"

        if inquiry.preferred_contact_method:
            preferred_contact = inquiry.preferred_contact_method.value
            if preferred_contact == "email":
                contact_info = f"{email_line}{PREFERRED_SUFFIX}\n{phone_line}"
            else:
                contact_info = f"{phone_line}{PREFERRED_SUFFIX}\n{email_line}"
        else:
            contact_info = f"{phone_line}\n{email_line}"

        customer_names = [name for name in (inquiry.customer_first_name, inquiry.customer_last_name) if name]
        customer_name = escape_markdown_v2(" ".join(customer_names)) if customer_names else "N/A"
        inquiry_type = escape_markdown_v2(inquiry.inquiry_type.value) if inquiry.inquiry_type else "N/A"
        inquiry_message = escape_markdown_v2(inquiry.inquiry or "N/A")
        needed_by = escape_markdown_v2(inquiry.date_needed_by.strftime("%Y-%m-%d %H:%M:%S")) if inquiry.date_needed_by else "N/A"

        medusa_summary = ""
        if inquiry.medusa_order_id:
            order_response = order_payloads.get(inquiry.medusa_order_id)
            medusa_summary = f"{_format_medusa_order_summary(inquiry.medusa_order_id, order_response)}\n"
            if order_response is not None:
                if nextcloud_client is None:
                    nextcloud_instance_key = _resolve_nextcloud_instance_key()
                    try:
                        nextcloud_client = nextcloud_governor.client_for(nextcloud_instance_key)
                    except (FileNotFoundError, ValueError, RuntimeError) as exc:
                        logger.exception(
                            "Failed to initialize Nextcloud client for %s",
                            nextcloud_instance_key,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Failed to initialize Nextcloud calendar client",
                        ) from exc
                calendar_event = build_order_calendar_event(
                    inquiry,
                    order_response,
                    nextcloud_client.config,
                    now,
                )
                calendar_events.append(calendar_event)

        message_text = (
            "📩 *New Inquiry Received*\n"
            f"👤 *Customer:* {customer_name}\n"
            f"📦 *Inquiry Type:* {inquiry_type}\n"
            f"📝 *Message:* {inquiry_message}\n"
            f"📅 *Date Needed:* {needed_by}\n"
            f"{medusa_summary}"
            f"📌 *Contact Information:*\n{contact_info}"
        )
        messages.append(message_text)

    if BOT_ENABLED and telegram_app is not None:
        for message in messages:
            await telegram_app.bot.send_message(
                chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
                text=message,
                parse_mode="MarkdownV2",
            )
    else:
        logger.info("Telegram bot disabled; skipping %d inquiry notifications.", len(messages))

    if calendar_events and nextcloud_client is not None:
        try:
            nextcloud_client.create_events(calendar_events)
        except Exception as exc:
            logger.exception(
                "Failed to create Nextcloud events for %s",
                nextcloud_instance_key,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create Nextcloud calendar events",
            ) from exc

    return {"status": "messages sent", "count": len(messages)}
