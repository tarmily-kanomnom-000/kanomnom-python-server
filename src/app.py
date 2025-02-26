import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from cachetools import TTLCache
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import grist
from bot import TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ✅ Correctly Start and Stop the Telegram Bot
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown tasks."""
    logging.info("Starting Telegram bot inside FastAPI lifespan...")

    # Initialize bot
    await telegram_app.initialize()

    # ✅ Start fetching updates in a background task
    bot_task = asyncio.create_task(telegram_app.updater.start_polling())
    await telegram_app.start()

    yield  # Continue running FastAPI

    # Stop bot gracefully on shutdown
    await telegram_app.updater.stop()
    await telegram_app.stop()
    bot_task.cancel()
    logging.info("Telegram bot stopped.")


# Create FastAPI app with lifespan
app = FastAPI(
    title="My FastAPI Service",
    description="Python server to watch over services running for ka-nom nom like grist and medusa",
    version="1.0.0",
    lifespan=lifespan,
)


validation_error_cache = TTLCache(maxsize=1000, ttl=600)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles validation errors but ensures only one Telegram alert per request within a short period."""

    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"Validation error on {request.url}: {exc_str}")

    # Create a unique request identifier (IP + route)
    request_id = f"{request.url.path}-{request.client.host}"

    if (
        request.url.path.startswith("/grist")
        and request_id not in validation_error_cache
    ):
        validation_error_cache[request_id] = (
            True  # Store request to prevent duplicate alerts
        )

        error_message = (
            f"🚨 *Validation Error in Webhook*\n"
            f"❌ *Error:* {exc_str}\n"
            f"📅 *Time:* {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await telegram_app.bot.send_message(
            chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
            text=error_message,
            parse_mode="Markdown",
        )

    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


app.include_router(grist.router)


@app.get("/")
async def root():
    logging.info("Received request on /")
    return {"message": "Welcome to FastAPI service"}


@app.get("/health")
async def health_check():
    logging.info("Health check request received")
    return {"status": "healthy"}


if __name__ == "__main__":
    logging.info("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=6969)
