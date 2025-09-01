import logging
import os

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
