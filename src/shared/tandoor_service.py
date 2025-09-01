"""
Unified Tandoor service - single interface for all Tandoor operations.
Handles API communication, caching, recipe parsing, and model creation.
"""

import logging
import os
from typing import Optional

import requests

from core.cache.cache_service import get_cache_service
from shared.models import Ingredient, Recipe, Unit

logger = logging.getLogger(__name__)

# Configuration
TANDOOR_URL = os.getenv("TANDOOR_URL")


class TandoorService:
    """
    Unified service for all Tandoor operations.
    Provides a single interface that handles API requests, caching, and data parsing.
    """

    def __init__(self):
        self.base_url = TANDOOR_URL
        self.token = None
        self.cache_service = get_cache_service()
        self._recipes = None
        self._product_recipes = None

    def get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.token:
            logger.info("No token cached, fetching new token...")
            self.token = self._get_tandoor_token()
        
        if self.token:
            return {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            logger.error("No token available for authentication")
            return {
                "Content-Type": "application/json"
            }
    
    def get_token(self) -> Optional[str]:
        """Get the Tandoor authentication token."""
        return self._get_tandoor_token()
    
    def _get_tandoor_token(self) -> Optional[str]:
        """Fetch the Tandoor authentication token, refreshing if expired or near expiration."""
        # Try to get valid token from cache first
        logger.info("Checking token cache...")
        token = self.cache_service.token_cache.get_token()
        if token:
            logger.info("Found valid token in cache")
            return token
        
        logger.info("No valid token in cache, fetching new token from Tandoor...")

        # Token not in cache or expired, fetch new one
        username = os.getenv("TANDOOR_USERNAME")
        password = os.getenv("TANDOOR_PASSWORD")
        
        if not username or not password:
            logger.error("TANDOOR_USERNAME or TANDOOR_PASSWORD environment variables not set")
            return None
        
        payload = {
            "username": username,
            "password": password,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        auth_url = f"{self.base_url}/api-token-auth/"
        
        logger.info(f"Attempting authentication to {auth_url} with username: {username}")
        
        try:
            auth_response = requests.post(url=auth_url, data=payload, headers=headers)
            if auth_response.status_code == 200:
                resp_json = auth_response.json()
                token = resp_json.get("token")
                expires_str = resp_json.get("expires")
                
                if token and expires_str:
                    from datetime import datetime
                    expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    
                    # Cache the new token
                    self.cache_service.token_cache.save_token(token, expires)
                    logger.info("Successfully obtained and cached Tandoor token")
                    return token
                else:
                    logger.error("Token or expires missing from Tandoor response")
            else:
                logger.error("Authentication failed with Tandoor.")
                logger.error(f"Status Code: {auth_response.status_code}")
                logger.error(f"Response: {auth_response.text}")
        except Exception as e:
            logger.error(f"Error during Tandoor authentication: {e}")
        
        return None

    def test_token_validity(self) -> bool:
        """Test if the current token is valid by making a simple API call."""
        if not self.token:
            self.token = self._get_tandoor_token()
        
        if not self.token:
            logger.error("No token available for testing")
            return False
        
        # Test with a simple endpoint that should always work
        test_url = f"{self.base_url}/api/user/"
        headers = self.get_auth_headers()
        
        try:
            logger.info(f"🧪 Testing token validity with: {test_url}")
            response = requests.get(test_url, headers=headers)
            logger.info(f"🧪 Token test response: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("✅ Token is valid")
                return True
            elif response.status_code == 401 or response.status_code == 403:
                logger.error(f"❌ Token is invalid: {response.status_code}")
                logger.error(f"Response: {response.text}")
                # Clear the invalid token
                self.token = None
                return False
            else:
                logger.warning(f"⚠️ Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error testing token validity: {e}")
            return False

    def get_recipes(self, force_refresh: bool = False) -> list[Recipe]:
        """
        Get all recipes from Tandoor.
        Uses cache when available, fetches from API when needed.
        
        Args:
            force_refresh: If True, bypass cache and fetch from API
            
        Returns:
            list of Recipe objects
        """
        if self._recipes is not None and not force_refresh:
            return self._recipes

        try:
            if not force_refresh:
                # Try cache first
                logger.info("Checking recipe cache...")
                cached_recipes_data = self.cache_service.recipe_cache.load_recipes()
                if cached_recipes_data:
                    self._recipes = [Recipe.from_cache_dict(recipe_data) for recipe_data in cached_recipes_data]

            if not self._recipes or force_refresh:
                # Test token validity before making API calls
                if not self.test_token_validity():
                    logger.error("Token validation failed, cannot fetch recipes")
                    return []
                
                # Fetch from API
                logger.info("Fetching recipes from Tandoor API...")
                self._recipes = self._fetch_all_recipes_from_api()
                
                if self._recipes:
                    # Save to cache (convert Recipe objects back to dict for caching)
                    recipes_data = [recipe.to_cache_dict() for recipe in self._recipes]
                    self.cache_service.recipe_cache.save_recipes(recipes_data)
                    logger.info(f"Saved {len(self._recipes)} recipes to cache")
                    
                    # Notify dependency manager that recipe cache has been updated
                    self.cache_service.invalidate_dependent_caches("recipe")
                else:
                    logger.error("Failed to fetch recipes from API")
                    return []
            else:
                logger.info(f"Loaded {len(self._recipes)} recipes from cache")

            return self._recipes

        except Exception as e:
            logger.error(f"Error getting recipes: {e}")
            return []

    def get_product_recipes(self, force_refresh: bool = False) -> list[Recipe]:
        """
        Get recipes marked as products.
        
        Args:
            force_refresh: If True, reload all recipes first
            
        Returns:
            list of Recipe objects with 'product' keyword
        """
        if self._product_recipes is not None and not force_refresh:
            return self._product_recipes

        all_recipes = self.get_recipes(force_refresh)
        self._product_recipes = [recipe for recipe in all_recipes if "product" in recipe.keywords]
        
        logger.info(f"Found {len(self._product_recipes)} product recipes out of {len(all_recipes)} total")
        return self._product_recipes

    def get_recipe_by_name(self, name: str) -> Optional[Recipe]:
        """
        Get a specific recipe by name.
        
        Args:
            name: Recipe name to search for
            
        Returns:
            Recipe object if found, None otherwise
        """
        recipes = self.get_recipes()
        for recipe in recipes:
            if recipe.name.lower() == name.lower():
                return recipe
        return None

    def search_recipes(self, keyword: str) -> list[Recipe]:
        """
        Search recipes by keyword in name or keywords.
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            list of matching Recipe objects
        """
        recipes = self.get_recipes()
        keyword_lower = keyword.lower()
        
        matching_recipes = []
        for recipe in recipes:
            if (keyword_lower in recipe.name.lower() or 
                any(keyword_lower in kw for kw in recipe.keywords)):
                matching_recipes.append(recipe)
        
        logger.info(f"Found {len(matching_recipes)} recipes matching '{keyword}'")
        return matching_recipes

    def _fetch_all_recipes_from_api(self) -> list[Recipe]:
        """Fetch all recipes from Tandoor API with pagination support."""
        recipes = []
        page_num = 1
        
        # Start with the first page
        url = f"{self.base_url}/api/recipe/?limit=100"
        
        # Step 1: Fetch all recipe stubs using Tandoor's pagination
        while url:
            logger.info(f"Fetching recipes page {page_num}...")
            
            try:
                headers = self.get_auth_headers()
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                # Debug pagination info
                total_count = data.get('count', 'unknown')
                next_url = data.get('next')
                results_count = len(data.get('results', []))
                
                logger.info(f"📊 API response: total={total_count}, results={results_count}, has_next={bool(next_url)}")
                
                # Parse basic recipes from this page
                page_recipes = [self._parse_recipe(recipe_data) for recipe_data in data.get('results', [])]
                recipes.extend(page_recipes)
                
                logger.info(f"Fetched {len(page_recipes)} recipe stubs from page {page_num} (total so far: {len(recipes)})")
                
                # Use the next URL provided by Tandoor
                url = next_url
                page_num += 1
                
            except requests.RequestException as e:
                logger.error(f"Error fetching recipes from page {page_num}: {e}")
                break
        
        logger.info(f"Total recipe stubs fetched: {len(recipes)}")
        
        # Step 2: Populate details for each recipe
        logger.info("Populating recipe details...")
        for i, recipe in enumerate(recipes):
            try:
                self._populate_recipe_details(recipe)
                if (i + 1) % 50 == 0:  # Log progress every 50 recipes
                    logger.info(f"Populated details for {i + 1}/{len(recipes)} recipes")
            except Exception as e:
                logger.error(f"Error populating details for recipe {recipe.id} ({recipe.name}): {e}")
        
        logger.info(f"Total recipes fully populated: {len(recipes)}")
        return recipes

    def _parse_recipe(self, recipe_data: dict) -> Recipe:
        """Parse basic recipe data from Tandoor API list response into Recipe model."""
        # Only parse basic data available from the list endpoint
        recipe_stub = {
            'id': recipe_data.get('id'),
            'name': recipe_data.get('name', ''),
            'description': recipe_data.get('description', '')
        }
        
        return Recipe(recipe_stub)

    def _populate_recipe_details(self, recipe: Recipe):
        """Fetch and populate detailed recipe information."""
        detail_url = f"{self.base_url}/api/recipe/{recipe.id}/"
        
        try:
            response = requests.get(detail_url, headers=self.get_auth_headers())
            response.raise_for_status()
            recipe_details = response.json()
            
            # Use the existing parse_recipe_details method from the Recipe class
            recipe.parse_recipe_details(recipe_details)
            
        except requests.RequestException as e:
            logger.error(f"Error fetching details for recipe {recipe.id}: {e}")
            raise

    def _parse_ingredient(self, ingredient_data: dict) -> Optional[Ingredient]:
        """Parse ingredient data from Tandoor API response into Ingredient model."""
        food_data = ingredient_data.get('food', {})
        unit_data = ingredient_data.get('unit', {})
        
        if not food_data:
            return None
        
        return Ingredient(
            name=food_data.get('name', ''),
            quantity=ingredient_data.get('amount', 0),
            unit=Unit(unit_data.get('name', 'g'))
        )

    def invalidate_cache(self):
        """Invalidate cached data to force refresh on next request."""
        self._recipes = None
        self._product_recipes = None
        logger.info("Tandoor service cache invalidated")


# Global service instance
_tandoor_service = None


def get_tandoor_service() -> TandoorService:
    """Get the global Tandoor service instance."""
    global _tandoor_service
    if _tandoor_service is None:
        _tandoor_service = TandoorService()
    return _tandoor_service