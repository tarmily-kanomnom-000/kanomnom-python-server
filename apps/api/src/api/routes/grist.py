import logging
import os
from datetime import UTC, datetime

import requests
from api.routes.medusa.dependencies import governor as medusa_governor
from api.routes.nextcloud.dependencies import governor as nextcloud_governor
from bot import BOT_ENABLED, TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from core.cache.grist_inquiry_idempotency import (
    GristInquiryIdempotencyStore,
    build_inquiry_idempotency_key,
    load_grist_inquiry_idempotency_config,
)
from core.medusa.exceptions import MedusaMetadataNotFoundError
from core.medusa.orders import fetch_orders
from core.nextcloud.events import NextcloudCalendarEvent, build_order_calendar_event
from fastapi import APIRouter, HTTPException, status
from models.customer_inquiry_model import Inquiries, format_phone_number
from models.medusa.order_response import MedusaOrderResponse

router = APIRouter(prefix="/grist", tags=["grist"])

MARKDOWN_V2_SPECIAL_CHARACTERS = set(
    "\\_*[]()~`>#+-=|{}.!"
)  # Telegram Markdown V2 reserved characters.
PREFERRED_SUFFIX = (
    " _\\(Preferred\\)_"  # Italicised "(Preferred)" with escaped parentheses.
)

logger = logging.getLogger(__name__)
idempotency_store = GristInquiryIdempotencyStore(
    load_grist_inquiry_idempotency_config()
)


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


def _format_medusa_order_summary(
    order_id: str, order_response: MedusaOrderResponse | None
) -> str:
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
        summary_lines.append(
            f"🔢 *Order Number:* {escape_markdown_v2(str(display_id))}"
        )
    if status_value:
        summary_lines.append(
            f"✅ *Order Status:* {escape_markdown_v2(str(status_value))}"
        )
    if email_value:
        summary_lines.append(
            f"📧 *Order Email:* {escape_markdown_v2(str(email_value))}"
        )
    if total_value is not None and currency_value:
        summary_lines.append(
            f"💵 *Order Total:* {escape_markdown_v2(str(total_value))} {escape_markdown_v2(str(currency_value).upper())}"
        )

    return "\n".join(summary_lines)


@router.post("/new_inquiry_webhook")
async def grist_status(inquiries: Inquiries) -> dict:
    """Handles new customer inquiries and sends a message to the Telegram group."""

    messages: list[tuple[str, int, datetime, str]] = []
    calendar_events: list[tuple[str, int, datetime, NextcloudCalendarEvent]] = []
    order_ids = [
        inquiry.medusa_order_id for inquiry in inquiries.root if inquiry.medusa_order_id
    ]
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
        except (
            MedusaMetadataNotFoundError,
            requests.RequestException,
            ValueError,
        ) as exc:
            logger.exception("Failed to fetch Medusa orders for %s", instance_key)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch Medusa order information",
            ) from exc

    for inquiry in inquiries.root:
        idempotency_key = build_inquiry_idempotency_key(inquiry)
        record = idempotency_store.get_or_create(
            idempotency_key, inquiry.id, inquiry.last_updated, now
        )
        telegram_pending = record.telegram_sent_at is None
        nextcloud_pending = record.nextcloud_event_uid is None
        if not telegram_pending and not nextcloud_pending:
            logger.info(
                "Skipping inquiry %s due to idempotency key %s",
                inquiry.id,
                idempotency_key,
            )
            continue

        order_response: MedusaOrderResponse | None = None
        if inquiry.medusa_order_id:
            order_response = order_payloads.get(inquiry.medusa_order_id)

        email_value = (
            escape_markdown_v2(inquiry.email.ascii_email)
            if getattr(inquiry, "email", None)
            else "N/A"
        )
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

        customer_names = [
            name
            for name in (inquiry.customer_first_name, inquiry.customer_last_name)
            if name
        ]
        customer_name = (
            escape_markdown_v2(" ".join(customer_names)) if customer_names else "N/A"
        )
        inquiry_type = (
            escape_markdown_v2(inquiry.inquiry_type.value)
            if inquiry.inquiry_type
            else "N/A"
        )
        inquiry_message = escape_markdown_v2(inquiry.inquiry or "N/A")
        needed_by = (
            escape_markdown_v2(inquiry.date_needed_by.strftime("%Y-%m-%d %H:%M:%S"))
            if inquiry.date_needed_by
            else "N/A"
        )

        if telegram_pending:
            medusa_summary = ""
            if inquiry.medusa_order_id:
                medusa_summary = f"{_format_medusa_order_summary(inquiry.medusa_order_id, order_response)}\n"
            message_text = (
                "📩 *New Inquiry Received*\n"
                f"👤 *Customer:* {customer_name}\n"
                f"📦 *Inquiry Type:* {inquiry_type}\n"
                f"📝 *Message:* {inquiry_message}\n"
                f"📅 *Date Needed:* {needed_by}\n"
                f"{medusa_summary}"
                f"📌 *Contact Information:*\n{contact_info}"
            )
            messages.append(
                (idempotency_key, inquiry.id, inquiry.last_updated, message_text)
            )

        if nextcloud_pending and order_response is not None:
            if nextcloud_client is None:
                nextcloud_instance_key = _resolve_nextcloud_instance_key()
                try:
                    nextcloud_client = nextcloud_governor.client_for(
                        nextcloud_instance_key
                    )
                except (FileNotFoundError, ValueError, RuntimeError):
                    logger.exception(
                        "Failed to initialize Nextcloud client for %s",
                        nextcloud_instance_key,
                    )
                    nextcloud_client = None
                    nextcloud_instance_key = None
                    logger.info(
                        "Skipping Nextcloud event creation for inquiry %s", inquiry.id
                    )
                    continue
            calendar_event = build_order_calendar_event(
                inquiry,
                order_response,
                nextcloud_client.config,
                now,
            )
            calendar_events.append(
                (idempotency_key, inquiry.id, inquiry.last_updated, calendar_event)
            )

    if BOT_ENABLED and telegram_app is not None:
        for idempotency_key, inquiry_id, updated_at, message in messages:
            await telegram_app.bot.send_message(
                chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
                text=message,
                parse_mode="MarkdownV2",
            )
            idempotency_store.mark_telegram_sent(
                idempotency_key, inquiry_id, updated_at, datetime.now(UTC)
            )
    else:
        logger.info(
            "Telegram bot disabled; skipping %d inquiry notifications.", len(messages)
        )

    if calendar_events and nextcloud_client is not None:
        try:
            for (
                idempotency_key,
                inquiry_id,
                updated_at,
                calendar_event,
            ) in calendar_events:
                nextcloud_client.create_events([calendar_event])
                idempotency_store.mark_nextcloud_created(
                    idempotency_key,
                    inquiry_id,
                    updated_at,
                    calendar_event.uid,
                    datetime.now(UTC),
                )
        except Exception:
            logger.exception(
                "Failed to create Nextcloud events for %s",
                nextcloud_instance_key,
            )
            logger.info(
                "Continuing after Nextcloud failure; Telegram notifications already sent."
            )

    return {"status": "messages sent", "count": len(messages)}
