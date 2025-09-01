"""
State management for the product costs calculator.
Handles all application state and data transformations.
"""

import logging
from datetime import datetime
from typing import Optional

from shared.models import Recipe

logger = logging.getLogger(__name__)


class ProductCostsState:
    """Manages state for the product costs calculator."""

    def __init__(self):
        # Recipe data
        self.recipes: list[Recipe] = []
        self.product_recipes: list[Recipe] = []
        self.product_ingredients: dict[str, dict] = {}  # Store ingredient breakdown for each product
        
        # UI state
        self.selected_product: Optional[str] = None  # Currently selected product to show ingredients
        self.current_cost_data: list = []  # Store current cost time series data
        self.current_recipe_ingredients: dict = {}  # Store current recipe ingredients
        
        # Date range state
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None

    def clear_all_state(self):
        """Clear all calculation state."""
        self.recipes.clear()
        self.product_recipes.clear()
        self.product_ingredients.clear()
        self.selected_product = None
        self.current_cost_data.clear()
        self.current_recipe_ingredients.clear()
        self.start_date = None
        self.end_date = None
        logger.info("Cleared all calculation state")

    def set_recipes(self, recipes: list[Recipe]):
        """Set the recipes and extract product recipes."""
        self.recipes = recipes
        self.product_recipes = [recipe for recipe in recipes if "product" in recipe.keywords]
        logger.info(f"Set {len(recipes)} recipes, {len(self.product_recipes)} are products")

    def set_selected_product(self, product_name: str):
        """Set the currently selected product."""
        self.selected_product = product_name
        logger.debug(f"Selected product: {product_name}")

    def set_product_ingredients(self, product_name: str, ingredients: dict):
        """Store ingredient breakdown for a product."""
        self.product_ingredients[product_name] = ingredients
        logger.debug(f"Stored ingredients for {product_name}: {len(ingredients)} ingredients")

    def get_product_ingredients(self, product_name: str) -> dict:
        """Get ingredient breakdown for a product."""
        return self.product_ingredients.get(product_name, {})

    def set_current_cost_data(self, cost_data: list):
        """Set the current cost time series data."""
        self.current_cost_data = cost_data
        logger.debug(f"Set cost data with {len(cost_data)} points")

    def set_current_recipe_ingredients(self, ingredients: dict):
        """Set the current recipe ingredients."""
        self.current_recipe_ingredients = ingredients
        logger.debug(f"Set current recipe ingredients: {len(ingredients)} ingredients")

    def set_date_range(self, start_date: datetime, end_date: datetime):
        """Set the date range for cost calculations."""
        self.start_date = start_date
        self.end_date = end_date
        logger.debug(f"Set date range: {start_date} to {end_date}")

    def get_recipe_by_name(self, name: str) -> Optional[Recipe]:
        """Get a recipe by name."""
        for recipe in self.recipes:
            if recipe.name.lower() == name.lower():
                return recipe
        return None

    def get_product_recipe_by_name(self, name: str) -> Optional[Recipe]:
        """Get a product recipe by name."""
        for recipe in self.product_recipes:
            if recipe.name.lower() == name.lower():
                return recipe
        return None

    def has_recipes(self) -> bool:
        """Check if recipes are loaded."""
        return bool(self.recipes)

    def has_product_recipes(self) -> bool:
        """Check if product recipes are loaded."""
        return bool(self.product_recipes)

    def has_cost_data(self) -> bool:
        """Check if cost data is available."""
        return bool(self.current_cost_data)

    def get_state_summary(self) -> dict:
        """Get a summary of current state for debugging."""
        return {
            "total_recipes": len(self.recipes),
            "product_recipes": len(self.product_recipes),
            "selected_product": self.selected_product,
            "cost_data_points": len(self.current_cost_data),
            "current_ingredients": len(self.current_recipe_ingredients),
            "cached_product_ingredients": len(self.product_ingredients),
            "date_range": f"{self.start_date} to {self.end_date}" if self.start_date and self.end_date else None
        }