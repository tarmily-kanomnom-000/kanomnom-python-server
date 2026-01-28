from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import requests
from core.cache.grist_inquiry_idempotency import (
    GristInquiryIdempotencyStore,
    build_inquiry_idempotency_key,
)
from core.grist.config import (
    resolve_medusa_instance_key,
    resolve_nextcloud_instance_key,
)
from core.grist.exceptions import MedusaOrderFetchError
from core.grist.telegram import build_inquiry_message
from core.medusa.exceptions import MedusaMetadataNotFoundError
from core.medusa.governor import MedusaGovernor
from core.medusa.orders import fetch_orders
from core.nextcloud.client import NextcloudCalendarClient
from core.nextcloud.events import NextcloudCalendarEvent, build_order_calendar_event
from core.nextcloud.governor import NextcloudGovernor
from models.customer_inquiry_model import Inquiries
from models.medusa.order_response import MedusaOrderResponse

logger = logging.getLogger(__name__)


class TelegramSender(Protocol):
    async def send_message(self, chat_id: int, text: str, parse_mode: str) -> Any: ...


async def handle_inquiries(
    inquiries: Inquiries,
    now: datetime,
    medusa_governor: MedusaGovernor,
    nextcloud_governor: NextcloudGovernor,
    idempotency_store: GristInquiryIdempotencyStore,
    telegram_sender: TelegramSender | None,
    telegram_chat_id: int,
    bot_enabled: bool,
) -> int:
    messages: list[tuple[str, int, datetime, str]] = []
    calendar_events: list[tuple[str, int, datetime, NextcloudCalendarEvent]] = []
    order_ids = [
        inquiry.medusa_order_id for inquiry in inquiries.root if inquiry.medusa_order_id
    ]
    order_ids = list(dict.fromkeys(order_ids))
    order_payloads: dict[str, MedusaOrderResponse] = {}
    nextcloud_client: NextcloudCalendarClient | None = None
    nextcloud_instance_key: str | None = None

    if order_ids:
        instance_key = resolve_medusa_instance_key()
        try:
            client = medusa_governor.client_for(instance_key)
            order_payloads = fetch_orders(client, order_ids)
        except (
            MedusaMetadataNotFoundError,
            requests.RequestException,
            ValueError,
        ) as exc:
            logger.exception("Failed to fetch Medusa orders for %s", instance_key)
            raise MedusaOrderFetchError(instance_key) from exc

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

        if telegram_pending:
            message_text = build_inquiry_message(inquiry, order_response)
            messages.append(
                (idempotency_key, inquiry.id, inquiry.last_updated, message_text)
            )

        if nextcloud_pending and order_response is not None:
            if nextcloud_client is None:
                nextcloud_instance_key = resolve_nextcloud_instance_key()
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

    if bot_enabled and telegram_sender is not None:
        for idempotency_key, inquiry_id, updated_at, message in messages:
            await telegram_sender.send_message(
                chat_id=telegram_chat_id,
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

    return len(messages)
