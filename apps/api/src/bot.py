import logging
import os

from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)

TELEGRAM_INQURY_GROUP_CHAT_ID = "-1002388242169"

# Load bot token securely
# This token should be the one associated with @kanomnom_internal_bot
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")

logging.info("Initializing Telegram bot...")

# Create bot application
telegram_app = Application.builder().token(TOKEN).build()


async def start(update: Update, context: CallbackContext):
    logging.info(f"Received /start command from {update.effective_user.id}")
    await update.message.reply_text("Hello! I am the Ka-Nom Nom internal bot.")


# Log ALL updates to check if bot is receiving messages
async def handle_updates(update: Update, context: CallbackContext):
    logging.info(f"Received an update: {update}")


telegram_app.add_handler(CommandHandler("start", start))


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! I am the Ka-Nom Nom internal bot.")


telegram_app.add_handler(CommandHandler("start", start))
