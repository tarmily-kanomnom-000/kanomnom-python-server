import logging
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TANDOOR_URL = os.getenv("TANDOOR_URL")


def get_tandoor_token():
    """Get Tandoor authentication token using TandoorService."""
    try:
        from shared.tandoor_service import get_tandoor_service

        tandoor_service = get_tandoor_service()
        return tandoor_service.get_token()
    except Exception as e:
        logger.error(f"Failed to get Tandoor token: {e}")
        return None


def initialize_server():
    """Initialize server with unified cache warming."""
    service_root = Path(__file__).resolve().parents[1]
    env_path = service_root / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    env_values = dotenv_values(env_path)
    logger.info("Loaded .env file from %s", env_path)
    logger.info(
        "Medusa keys found in .env: base_email=%s base_password=%s instance_email=%s instance_password=%s",
        "MEDUSA_ADMIN_EMAIL" in env_values,
        "MEDUSA_ADMIN_PASSWORD" in env_values,
        "MEDUSA_ADMIN_EMAIL__000000" in env_values,
        "MEDUSA_ADMIN_PASSWORD__000000" in env_values,
    )
    logger.info(
        "Medusa env vars present: email=%s password=%s",
        bool(os.getenv("MEDUSA_ADMIN_EMAIL")),
        bool(os.getenv("MEDUSA_ADMIN_PASSWORD")),
    )
    logger.info(
        "Medusa instance env vars present (000000): email=%s password=%s",
        bool(os.getenv("MEDUSA_ADMIN_EMAIL__000000")),
        bool(os.getenv("MEDUSA_ADMIN_PASSWORD__000000")),
    )

    from core.cache.cache_service import get_cache_service

    # Initialize cache service and warm caches
    cache_service = get_cache_service()
    cache_service.warm_caches()

    # Verify token is available
    token = get_tandoor_token()
    if token:
        logger.info("✅ Tandoor authentication successful")
    else:
        logger.warning("⚠️ Tandoor authentication failed - some features may not work")

    logger.info("Server initialized successfully.")
