"""
Business logic service for ingredients calculations.
Handles all calculation operations and data processing.
"""

import logging
from typing import Optional

from shared.ingredient_calculator import IngredientCalculator
from shared.models import Recipe
from .state_manager import IngredientsState

logger = logging.getLogger(__name__)


class IngredientsCalculationService:
    """Handles all ingredients calculation business logic."""

    def __init__(self, state: IngredientsState):
        self.state = state
        self._calculator: Optional[IngredientCalculator] = None

    def set_recipes(self, recipes: list[Recipe]):
        """Set recipes and initialize calculator."""
        self.state.product_recipes = recipes
        self._calculator = IngredientCalculator(recipes)
        logger.info(f"Initialized calculator with {len(recipes)} recipes")

    def calculate_ingredients(self, selected_quantities: Optional[dict[str, float]] = None) -> bool:
        """
        Perform ingredient calculations.
        
        Args:
            selected_quantities: Optional dict of {recipe_name: quantity} to calculate.
                               If None, uses all non-zero quantities from state.
        
        Returns:
            bool: True if calculations succeeded, False otherwise
        """
        if not self._calculator:
            logger.warning("Cannot calculate: missing calculator")
            return False

        # Use provided quantities or filter non-zero quantities from state
        if selected_quantities is None:
            selected_quantities = {name: qty for name, qty in self.state.quantities.items() if qty > 0}
        
        if not selected_quantities:
            logger.warning("Cannot calculate: no quantities selected")
            return False

        try:
            # Calculate raw ingredients and intermediate servings
            self.state.intermediate_servings, self.state.raw_ingredients = (
                self._calculator.calculate_ingredients_and_servings(selected_quantities)
            )
            
            logger.info(f"Calculated {len(self.state.raw_ingredients)} raw ingredients")
            logger.info(f"Calculated {len(self.state.intermediate_servings)} intermediate servings")
            return True
            
        except Exception as e:
            logger.error(f"Calculation failed: {e}")
            return False

    def recalculate_with_existing(self) -> bool:
        """
        Recalculate ingredients accounting for existing intermediate amounts.
        
        Returns:
            bool: True if recalculation succeeded, False otherwise
        """
        if not self._calculator:
            logger.warning("Cannot recalculate: missing calculator")
            return False

        try:
            remaining_servings = self._calculate_remaining_servings()
            if remaining_servings:
                self.state.raw_ingredients = self._calculator.calculate_raw_ingredients_from_remaining(
                    remaining_servings
                )
            else:
                self.state.raw_ingredients = {}
            
            logger.info(f"Recalculated with existing amounts: {len(self.state.raw_ingredients)} raw ingredients")
            return True
            
        except Exception as e:
            logger.error(f"Recalculation failed: {e}")
            return False

    def _calculate_remaining_servings(self) -> dict[str, float]:
        """Calculate remaining servings needed after accounting for existing amounts."""
        remaining_servings = {}
        # Need all recipes for intermediate recipe lookup, not just product recipes
        recipe_lookup = {recipe.name.lower(): recipe for recipe in self._calculator.recipes}
        
        for recipe_name, needed_servings in self.state.intermediate_servings.items():
            existing_servings = self._calculate_existing_servings(recipe_name, recipe_lookup)
            remaining = max(0, needed_servings - existing_servings)
            
            if remaining > 0:
                remaining_servings[recipe_name] = remaining
            
            logger.debug(f"{recipe_name}: needed={needed_servings}, existing={existing_servings}, remaining={remaining}")
        
        return remaining_servings

    def _calculate_existing_servings(self, recipe_name: str, recipe_lookup: dict[str, Recipe]) -> float:
        """Calculate existing servings for a recipe from weight and servings inputs."""
        if recipe_name not in self.state.existing_intermediate_amounts:
            return 0.0
        
        existing_amounts = self.state.existing_intermediate_amounts[recipe_name]
        existing_servings = existing_amounts.get("servings", 0)
        existing_weight = existing_amounts.get("weight", 0)
        
        # Convert weight to servings if available
        if existing_weight > 0:
            weight_as_servings = self._convert_weight_to_servings(recipe_name, existing_weight, recipe_lookup)
            existing_servings += weight_as_servings
        
        return existing_servings

    def _convert_weight_to_servings(self, recipe_name: str, weight: float, recipe_lookup: dict[str, Recipe]) -> float:
        """Convert weight to servings for a recipe."""
        recipe_key = recipe_name.lower()
        if recipe_key not in recipe_lookup:
            logger.warning(f"Recipe not found for weight conversion: {recipe_name}")
            return 0.0
        
        recipe = recipe_lookup[recipe_key]
        if not recipe.produced_amount or recipe.produced_amount <= 0:
            logger.warning(f"Recipe {recipe_name} has no production amount for weight conversion")
            return 0.0
        
        # Convert weight to servings based on recipe production
        servings = weight / recipe.produced_amount
        logger.debug(f"Converted {weight}g to {servings} servings for {recipe_name}")
        return servings

    def get_calculation_summary(self) -> dict[str, int]:
        """Get summary of current calculations."""
        return {
            "recipes": len(self.state.product_recipes),
            "quantities_set": len(self.state.quantities),
            "raw_ingredients": len(self.state.raw_ingredients),
            "intermediate_servings": len(self.state.intermediate_servings),
            "existing_amounts": len(self.state.existing_intermediate_amounts)
        }