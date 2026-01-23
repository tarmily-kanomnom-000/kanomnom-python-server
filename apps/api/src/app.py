import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from cachetools import TTLCache
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from flet.fastapi import app as flet_fastapi
from telegram.ext import Application

from api.routes import grist, grocy, medusa
from bot import BOT_ENABLED, TELEGRAM_INQURY_GROUP_CHAT_ID, telegram_app
from core.cache.cache_service import get_cache_service
from core.cache.grist_cache_refresher import (
    GristCacheRefresher,
    GristCacheRefresherConfig,
)
from core.cache.tandoor_cache_refresher import (
    TandoorCacheRefresher,
    TandoorCacheRefresherConfig,
    default_tandoor_service_factory,
)
from flet_app import main as flet_main
from services.weather.config import (
    DEFAULT_DATABASE_CONFIG,
    DEFAULT_LOCATIONS,
    WEATHER_FETCH_TIME,
    weather_scheduler_timezone,
)
from services.weather.job import WeatherIngestJob
from services.weather.utils import seconds_until_next_run
from setup import initialize_server

initialize_server()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DEV_MODE: bool = os.getenv("FASTAPI_ENV", "").lower() in {"dev", "development"}


def _require_telegram_app() -> Application:
    if telegram_app is None:
        raise RuntimeError("Telegram bot is enabled but failed to initialize.")
    return telegram_app


# Start and Stop the Telegram Bot
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Handles startup and shutdown tasks."""
    bot_started = False
    bot_task: asyncio.Task[None] | None = None

    if not BOT_ENABLED or DEV_MODE:
        logging.info("FASTAPI_ENV indicates dev; skipping Telegram bot startup.")
    else:
        logging.info("Starting Telegram bot inside FastAPI lifespan...")
        bot_app = _require_telegram_app()
        await bot_app.initialize()
        bot_task = asyncio.create_task(bot_app.updater.start_polling())
        await bot_app.start()
        bot_started = True

    cache_service = get_cache_service()
    grist_cache_refresher = GristCacheRefresher(
        cache_service=cache_service,
        config=GristCacheRefresherConfig.default(),
    )
    tandoor_cache_refresher = TandoorCacheRefresher(
        cache_service=cache_service,
        config=TandoorCacheRefresherConfig.default(),
        service_factory=default_tandoor_service_factory,
    )

    try:
        await grist_cache_refresher.start()
        await tandoor_cache_refresher.start()
    except Exception:
        await grist_cache_refresher.stop()
        raise

    # weather_stop_event: asyncio.Event | None = None
    # weather_task: asyncio.Task | None = None

    # weather_stop_event = asyncio.Event()
    # weather_task = asyncio.create_task(_weather_ingest_loop(weather_stop_event))

    try:
        yield  # Continue running FastAPI
    finally:
        # if weather_stop_event:
        #     weather_stop_event.set()
        # if weather_task:
        #     try:
        #         await weather_task
        #     except asyncio.CancelledError:
        #         logging.info("Weather ingest scheduler cancelled during shutdown.")
        await tandoor_cache_refresher.stop()
        await grist_cache_refresher.stop()
        if bot_started:
            bot_app = _require_telegram_app()
            await bot_app.updater.stop()
            await bot_app.stop()
            if bot_task:
                bot_task.cancel()
            logging.info("Telegram bot stopped.")


app = FastAPI(
    title="My FastAPI Service",
    description="Python server to watch over services running for ka-nom nom like grist and medusa",
    version="1.0.0",
    lifespan=lifespan,
)

validation_error_cache = TTLCache(maxsize=1000, ttl=600)


# Directory to store request dumps
DUMP_DIR = Path("request_dumps")
DUMP_DIR.mkdir(exist_ok=True)


async def _weather_ingest_loop(stop_event: asyncio.Event) -> None:
    tz = weather_scheduler_timezone()
    job = WeatherIngestJob(
        db_config=DEFAULT_DATABASE_CONFIG,
        locations=DEFAULT_LOCATIONS,
    )
    while not stop_event.is_set():
        wait_seconds = seconds_until_next_run(datetime.now(tz), WEATHER_FETCH_TIME, tz)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_seconds)
            break
        except asyncio.TimeoutError:
            pass

        previous_day_iso = (datetime.now(tz) - timedelta(days=1)).date().isoformat()
        logging.info(
            "Starting scheduled weather ingest for %s (timezone=%s)",
            previous_day_iso,
            getattr(tz, "key", str(tz)),
        )
        try:
            await asyncio.to_thread(
                job.run,
                start_date=previous_day_iso,
                end_date=previous_day_iso,
                dry_run=False,
            )
            logging.info("Finished scheduled weather ingest for %s", previous_day_iso)
        except Exception:
            logging.exception("Weather ingest job failed for %s", previous_day_iso)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles validation errors, ensures one Telegram alert per request, and dumps request info to file."""

    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"Validation error on {request.url}: {exc_str}")

    # Create a unique request identifier (IP + route)
    request_id = f"{request.url.path}-{request.client.host}"

    # Dump request details to file for later inspection
    try:
        body = await request.body()
        request_dump = {
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "client": request.client.host,
            "body": body.decode("utf-8", errors="replace"),
            "error": exc_str,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{request.client.host.replace('.', '_')}.json"
        with open(DUMP_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(request_dump, f, indent=2)
    except Exception:
        logging.exception("Failed to dump request data")

    # Send alert via Telegram if not already done
    if BOT_ENABLED and request.url.path.startswith("/grist") and request_id not in validation_error_cache:
        validation_error_cache[request_id] = True

        error_message = (
            f"🚨 *Validation Error in Webhook*\n"
            f"❌ *Error:* {exc_str}\n"
            f"📅 *Time:* {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
        )

        bot_app = _require_telegram_app()
        await bot_app.bot.send_message(
            chat_id=TELEGRAM_INQURY_GROUP_CHAT_ID,
            text=error_message,
            parse_mode="Markdown",
        )

    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


# Mount Flet app to FastAPI
flet_app = flet_fastapi(session_handler=flet_main)
app.mount("/flet", flet_app)


@app.get("/calculate_ingredients")
async def redirect_to_flet() -> RedirectResponse:
    """Redirect to Flet app"""
    return RedirectResponse(url="/calculate_raw_ingredients")


app.include_router(grist.router)
app.include_router(grocy.router)
app.include_router(medusa.router)


@app.get("/")
async def root() -> dict[str, str]:
    logging.info("Received request on /")
    return {"message": "Welcome to FastAPI service"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    logging.info("Health check request received")
    return {"status": "healthy"}


if __name__ == "__main__":
    logging.info("Starting FastAPI server...")
    logging.info("Flet app available at: http://localhost:6969/flet")
    uvicorn.run(app, host="0.0.0.0", port=6969)
