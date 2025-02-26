import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from api.routes import grist
from bot import telegram_app

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
