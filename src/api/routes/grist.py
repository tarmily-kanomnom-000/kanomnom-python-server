from fastapi import APIRouter, Request

from bot import TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from models.customer_inquiry_model import Inquiries

router = APIRouter(prefix="/grist", tags=["grist"])


@router.post("/new_inquiry_webhook")
async def grist_status(inquiries: Inquiries) -> dict:
    """Handles new customer inquiries and sends a message to the Telegram group."""

    messages = []

    for inquiry in inquiries.root:
        email_info = (
            f"📧 *Email:* {inquiry.email.ascii_email}"
            if inquiry.email
            else "📧 *Email:* N/A"
        )
        phone_info = (
            f"📞 *Phone:* {inquiry.phone_number.national_number}"
            if inquiry.phone_number
            else "📞 *Phone:* N/A"
        )

        if inquiry.preferred_contact_method:
            preferred_contact = inquiry.preferred_contact_method.value
            if preferred_contact == "email":
                contact_info = f"{email_info} _(Preferred)_\n{phone_info}"
            else:
                contact_info = f"{phone_info} _(Preferred)_\n{email_info}"
        else:
            contact_info = f"{phone_info}\n{email_info}"

        message_text = (
            f"📩 *New Inquiry Received*\n"
            f"👤 *Customer:* {inquiry.customer_first_name} {inquiry.customer_last_name}\n"
            f"📦 *Inquiry Type:* {inquiry.inquiry_type.value if inquiry.inquiry_type else 'N/A'}\n"
            f"📝 *Message:* {inquiry.inquiry}\n"
            f"📅 *Date Needed:* {
                inquiry.date_needed_by.strftime('%Y-%m-%d %H:%M:%S')
                if inquiry.date_needed_by
                else 'N/A'
            }\n"
            f"📌 *Contact Information:*\n{contact_info}"
        )
        messages.append(message_text)

    for message in messages:
        await telegram_app.bot.send_message(
            chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID, text=message, parse_mode="Markdown"
        )

    return {"status": "messages sent", "count": len(messages)}
