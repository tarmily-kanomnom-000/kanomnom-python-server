from __future__ import annotations

from models.customer_inquiry_model import Inquiry, format_phone_number
from models.medusa.order_response import MedusaOrderResponse

MARKDOWN_V2_SPECIAL_CHARACTERS = set(
    "\\_*[]()~`>#+-=|{}.!"
)  # Telegram Markdown V2 reserved characters.
PREFERRED_SUFFIX = (
    " _\\(Preferred\\)_"  # Italicised "(Preferred)" with escaped parentheses.
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


def format_medusa_order_summary(
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
            "💵 *Order Total:* "
            f"{escape_markdown_v2(str(total_value))} "
            f"{escape_markdown_v2(str(currency_value).upper())}"
        )

    return "\n".join(summary_lines)


def build_inquiry_message(
    inquiry: Inquiry, order_response: MedusaOrderResponse | None
) -> str:
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

    medusa_summary = ""
    if inquiry.medusa_order_id:
        medusa_summary = (
            f"{format_medusa_order_summary(inquiry.medusa_order_id, order_response)}\n"
        )

    return (
        "📩 *New Inquiry Received*\n"
        f"👤 *Customer:* {customer_name}\n"
        f"📦 *Inquiry Type:* {inquiry_type}\n"
        f"📝 *Message:* {inquiry_message}\n"
        f"📅 *Date Needed:* {needed_by}\n"
        f"{medusa_summary}"
        f"📌 *Contact Information:*\n{contact_info}"
    )
