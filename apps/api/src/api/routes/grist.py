from fastapi import APIRouter

from bot import TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from models.customer_inquiry_model import Inquiries

router = APIRouter(prefix="/grist", tags=["grist"])

MARKDOWN_V2_SPECIAL_CHARACTERS = set("\\_*[]()~`>#+-=|{}.!")  # Telegram Markdown V2 reserved characters.
PREFERRED_SUFFIX = " _\\(Preferred\\)_"  # Italicised "(Preferred)" with escaped parentheses.


def escape_markdown_v2(value: str) -> str:
    """Escape Telegram MarkdownV2-reserved characters within the provided text."""
    escaped_characters: list[str] = []

    for character in value:
        if character in MARKDOWN_V2_SPECIAL_CHARACTERS:
            escaped_characters.append(f"\\{character}")
        else:
            escaped_characters.append(character)

    return "".join(escaped_characters)


@router.post("/new_inquiry_webhook")
async def grist_status(inquiries: Inquiries) -> dict:
    """Handles new customer inquiries and sends a message to the Telegram group."""

    messages: list[str] = []

    for inquiry in inquiries.root:
        email_value = escape_markdown_v2(inquiry.email.ascii_email) if getattr(inquiry, "email", None) else "N/A"
        phone_value = (
            escape_markdown_v2(str(inquiry.phone_number.national_number)) if getattr(inquiry, "phone_number", None) else "N/A"
        )

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

        message_text = (
            "📩 *New Inquiry Received*\n"
            f"👤 *Customer:* {customer_name}\n"
            f"📦 *Inquiry Type:* {inquiry_type}\n"
            f"📝 *Message:* {inquiry_message}\n"
            f"📅 *Date Needed:* {needed_by}\n"
            f"📌 *Contact Information:*\n{contact_info}"
        )
        messages.append(message_text)

    for message in messages:
        await telegram_app.bot.send_message(
            chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
            text=message,
            parse_mode="MarkdownV2",
        )

    return {"status": "messages sent", "count": len(messages)}
