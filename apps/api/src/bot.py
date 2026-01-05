import logging
import os
from typing import Optional

from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


TELEGRAM_INQURY_GROUP_CHAT_ID = "-1002388242169"
DEV_MODE: bool = os.getenv("FASTAPI_ENV", "").lower() in {"dev", "development"}
BOT_ENABLED: bool = _is_truthy(os.getenv("TELEGRAM_BOT_ENABLED")) and not DEV_MODE

telegram_app: Optional[Application] = None

if BOT_ENABLED:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")

    logging.info("Initializing Telegram bot...")
    telegram_app = Application.builder().token(token).build()


async def start(update: Update, context: CallbackContext) -> None:
    logging.info("Received /start command from %s", update.effective_user.id)
    await update.message.reply_text("Hello! I am the Ka-Nom Nom internal bot.")


def register_handlers() -> None:
    if telegram_app is None:
        return
    telegram_app.add_handler(CommandHandler("start", start))


register_handlers()
