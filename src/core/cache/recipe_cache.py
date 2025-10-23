import logging
from typing import Optional, List, Dict, Any
import diskcache as dc

from core.cache.cache_paths import resolve_cache_path

logger = logging.getLogger(__name__)


class RecipeCacheManager:
    """Manages caching of recipe data using DiskCache."""

    def __init__(self, cache_duration_seconds: int = 3600):  # 1 hour default
        self.cache_duration_seconds = cache_duration_seconds
        cache_dir = resolve_cache_path("recipes")
        self.cache = dc.Cache(str(cache_dir))
        logger.info(f"Initialized RecipeCacheManager with {cache_duration_seconds/3600}h TTL at {cache_dir}")

    def save_recipes(self, recipes_data: List[Dict[str, Any]]):
        """Save recipe data to cache."""
        if not recipes_data:
            logger.warning("Attempting to cache empty recipe data")
            return
            
        # DiskCache handles serialization automatically
        self.cache.set("tandoor_recipes", recipes_data, expire=self.cache_duration_seconds)
        logger.info(f"Saved {len(recipes_data)} recipes to DiskCache")

    def load_recipes(self) -> Optional[List[Dict[str, Any]]]:
        """Load recipe data from cache."""
        try:
            recipes_data = self.cache.get("tandoor_recipes")
            if recipes_data:
                logger.info(f"Loaded {len(recipes_data)} recipes from DiskCache")
                return recipes_data
        except Exception as e:
            logger.error(f"Error loading recipes from DiskCache: {e}")
        return None

    def clear_cache(self):
        """Clear the recipe cache."""
        if "tandoor_recipes" in self.cache:
            del self.cache["tandoor_recipes"]
            logger.info("Cleared recipe cache")

    def has_valid_cache(self) -> bool:
        """Return True when cached recipe data exists and contains entries."""
        try:
            recipes_data = self.cache.get("tandoor_recipes")
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error inspecting recipe cache: {exc}")
            return False

        if not recipes_data:
            logger.debug("Recipe cache is empty or missing data")
            return False

        if not isinstance(recipes_data, list):
            logger.info("Recipe cache contains unexpected data type %s", type(recipes_data))
            return False

        return True

    def cache_info(self):
        """Get cache information for debugging."""
        size = len(self.cache)
        volume_path = self.cache.directory
        return f"Recipe cache size: {size} entries at {volume_path}"
