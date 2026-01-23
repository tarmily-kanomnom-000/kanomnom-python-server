from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.nextcloud.config import NextcloudConfig
from core.nextcloud.models import NextcloudCalendarMetadata
from models.customer_inquiry_model import Inquiry, format_phone_number
from models.medusa.order_response import MedusaOrderItem, MedusaOrderResponse


@dataclass(frozen=True)
class NextcloudCalendarEvent:
    uid: str
    summary: str
    description: str
    start_at: datetime
    end_at: datetime
    dtstamp: datetime
    calendar_name: str
    location: str | None
    item_kind: str


def build_order_calendar_event(
    inquiry: Inquiry,
    order_response: MedusaOrderResponse,
    config: NextcloudConfig,
    now: datetime,
) -> NextcloudCalendarEvent:
    """Build a calendar event for a Medusa-backed inquiry."""
    calendar_metadata = _resolve_calendar_for_tag("orders", config)
    calendar_name = calendar_metadata.name
    order = order_response.order
    customer_name = _format_customer_name(inquiry)
    summary = customer_name if customer_name else "Order Request"
    description = _build_order_description(inquiry, order_response)
    start_at = _resolve_event_start(inquiry, order_response, now)
    end_at = start_at + timedelta(minutes=config.event_duration_minutes)
    uid = f"medusa-order-{order.id}"
    return NextcloudCalendarEvent(
        uid=uid,
        summary=summary,
        description=description,
        start_at=start_at,
        end_at=end_at,
        dtstamp=now,
        calendar_name=calendar_name,
        location=_format_location(inquiry.location),
        item_kind=_resolve_calendar_item_kind(calendar_metadata),
    )


def build_ical_event(event: NextcloudCalendarEvent) -> str:
    """Render a calendar event into an iCalendar payload."""
    if event.item_kind == "task":
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//kanomnom//nextcloud//EN",
            "BEGIN:VTODO",
            f"UID:{_escape_ical_text(event.uid)}",
            f"DTSTAMP:{_format_ical_datetime(event.dtstamp)}",
            f"DTSTART:{_format_ical_datetime(event.start_at)}",
            f"DUE:{_format_ical_datetime(event.end_at)}",
            f"SUMMARY:{_escape_ical_text(event.summary)}",
            f"DESCRIPTION:{_escape_ical_text(event.description)}",
            "STATUS:NEEDS-ACTION",
        ]
    else:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//kanomnom//nextcloud//EN",
            "BEGIN:VEVENT",
            f"UID:{_escape_ical_text(event.uid)}",
            f"DTSTAMP:{_format_ical_datetime(event.dtstamp)}",
            f"DTSTART:{_format_ical_datetime(event.start_at)}",
            f"DTEND:{_format_ical_datetime(event.end_at)}",
            f"SUMMARY:{_escape_ical_text(event.summary)}",
            f"DESCRIPTION:{_escape_ical_text(event.description)}",
        ]
    if event.location:
        lines.append(f"LOCATION:{_escape_ical_text(event.location)}")
    if event.item_kind == "task":
        lines.extend(
            [
                "BEGIN:VALARM",
                "TRIGGER:-P1D",
                "ACTION:DISPLAY",
                "DESCRIPTION:Task reminder",
                "END:VALARM",
            ]
        )
        lines.append("END:VTODO")
    else:
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def _resolve_event_start(
    inquiry: Inquiry,
    order_response: MedusaOrderResponse,
    fallback: datetime,
) -> datetime:
    if inquiry.date_needed_by is not None:
        return inquiry.date_needed_by
    if order_response.order.created_at is not None:
        return order_response.order.created_at
    return fallback


def _format_customer_name(inquiry: Inquiry) -> str:
    customer_names = [name for name in (inquiry.customer_first_name, inquiry.customer_last_name) if name]
    if not customer_names:
        return ""
    return " ".join(customer_names)


def _build_order_description(inquiry: Inquiry, order_response: MedusaOrderResponse) -> str:
    order = order_response.order
    lines: list[str] = []
    contact_lines: list[str] = []
    preferred_contact = inquiry.preferred_contact_method.value if inquiry.preferred_contact_method else None
    if inquiry.preferred_contact_method:
        preferred_contact = inquiry.preferred_contact_method.value
    if inquiry.email:
        email_value = _format_inquiry_email(inquiry)
        suffix = " (Preferred)" if preferred_contact == "email" else ""
        contact_lines.append(f"📧 Email: {email_value}{suffix}")
    if inquiry.phone_number:
        formatted_phone = format_phone_number(inquiry.phone_number)
        if formatted_phone:
            suffix = " (Preferred)" if preferred_contact == "text" else ""
            contact_lines.append(f"📞 Phone: {formatted_phone}{suffix}")
    lines.extend(contact_lines)
    if inquiry.inquiry:
        lines.append(f"📝 Notes: {inquiry.inquiry}")
    if order.items:
        lines.append("🧾 Items:")
        lines.extend(_format_order_items(order.items))
    return "\n".join(lines)


def _format_order_items(items: list[MedusaOrderItem]) -> list[str]:
    formatted: list[str] = []
    display_items: list[tuple[str, str]] = []
    for item in items:
        title = item.title or item.product_title or "Item"
        variant = _resolve_item_variant(item)
        if variant and variant.lower() not in title.lower():
            title = f"{title} ({variant})"
        quantity = item.quantity
        if quantity is None:
            display_items.append(("", title))
        else:
            display_items.append((f"x{_format_quantity(quantity)}", title))
    if not display_items:
        return formatted
    max_qty_width = max(len(qty) for qty, _ in display_items)
    for qty, title in display_items:
        if qty:
            formatted.append(f"- {qty.rjust(max_qty_width)} {title}")
        else:
            formatted.append(f"- {' ' * max_qty_width} {title}")
    return formatted


def _format_inquiry_email(inquiry: Inquiry) -> str:
    email_value = inquiry.email
    if email_value is None:
        return ""
    ascii_email = getattr(email_value, "ascii_email", None)
    if ascii_email:
        return str(ascii_email)
    return str(email_value)


def _format_location(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _format_ical_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _escape_ical_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")
    return escaped


def _resolve_calendar_for_tag(tag: str, config: NextcloudConfig) -> NextcloudCalendarMetadata:
    matches = [calendar for calendar in config.calendars if tag in calendar.tags]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        available = ", ".join(sorted(_collect_tags(config))) or "none"
        raise ValueError(f"Unknown Nextcloud calendar tag '{tag}'. Available: {available}")
    raise ValueError(f"Multiple Nextcloud calendars match tag '{tag}': {', '.join(calendar.name for calendar in matches)}")


def _resolve_calendar_item_kind(metadata: NextcloudCalendarMetadata) -> str:
    return "task" if "task" in metadata.tags else "event"


def _resolve_item_variant(item: MedusaOrderItem) -> str | None:
    variant_title = (item.variant_title or "").strip()
    if variant_title and variant_title.lower() not in {"default", "default variant"}:
        return variant_title
    option_values: list[str] = []
    if item.variant_option_values:
        for option in item.variant_option_values:
            value = option.get("value")
            if value:
                option_values.append(str(value))
    if option_values:
        option_value = " / ".join(option_values)
        if option_value.lower() not in {"default", "default variant"}:
            return option_value
    return None


def _format_quantity(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _collect_tags(config: NextcloudConfig) -> list[str]:
    tags: set[str] = set()
    for calendar in config.calendars:
        tags.update(calendar.tags)
    return sorted(tags)
