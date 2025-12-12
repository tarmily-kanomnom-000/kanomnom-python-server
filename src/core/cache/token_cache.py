import logging
from datetime import datetime
from typing import Any, Dict, Optional

import diskcache as dc

from core.cache.cache_paths import resolve_cache_path

logger = logging.getLogger(__name__)


class TokenCacheManager:
    """Manages caching of authentication tokens using DiskCache."""

    def __init__(self):
        cache_dir = resolve_cache_path("tokens")
        self.cache = dc.Cache(str(cache_dir))
        logger.info(f"Initialized TokenCacheManager at {cache_dir}")

    def save_token(self, token: str, expires: datetime):
        """Save token to cache using the provided expiration time."""
        if not token:
            logger.warning("Attempting to cache empty token")
            return
            
        # Create token data structure
        token_data = {
            'access_token': token,
            'token': token,
            'expires_at': expires.isoformat()
        }
        
        # Calculate expiration seconds from provided datetime
        now = datetime.now(expires.tzinfo) if expires.tzinfo else datetime.now()
        time_until_expiry = expires - now
        expire_seconds = max(0, int(time_until_expiry.total_seconds()))
        logger.info(f"Token expires in {expire_seconds/3600:.1f} hours")
            
        # DiskCache handles serialization automatically
        self.cache.set("tandoor_token", token_data, expire=expire_seconds)
        logger.info("Saved token data to DiskCache")

    def get_token(self) -> Optional[str]:
        """Get the authentication token string from cache."""
        try:
            token_data = self.cache.get("tandoor_token")
            if token_data and self.is_token_valid():
                return token_data.get('access_token') or token_data.get('token')
        except Exception as e:
            logger.error(f"Error loading token from DiskCache: {e}")
        return None

    def is_token_valid(self) -> bool:
        """Check if cached token exists and is valid."""
        try:
            token_data = self.cache.get("tandoor_token")
            if not token_data:
                return False
                
            # Check if token has expiry information
            expires_at = token_data.get('expires_at')
            if expires_at:
                try:
                    # Parse expiry time and check if still valid
                    expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    now = datetime.now(expiry_time.tzinfo) if expiry_time.tzinfo else datetime.now()
                    return now < expiry_time
                except Exception as e:
                    logger.warning(f"Error parsing token expiry: {e}")
                    
            # If no expiry info, assume valid (DiskCache TTL will handle expiration)
            return True
        except Exception as e:
            logger.error(f"Error checking token validity: {e}")
            return False

    def clear_cache(self):
        """Clear the token cache."""
        if "tandoor_token" in self.cache:
            del self.cache["tandoor_token"]
            logger.info("Cleared token cache")

    def cache_info(self):
        """Get cache information for debugging."""
        size = len(self.cache)
        volume_path = self.cache.directory
        return f"Token cache size: {size} entries at {volume_path}"
