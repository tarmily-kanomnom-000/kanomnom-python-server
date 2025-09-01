"""
State management for the ingredients calculator.
Handles all application state and data transformations.
"""

import logging

from shared.models import Recipe

logger = logging.getLogger(__name__)


class IngredientsState:
    """Manages state for the ingredients calculator."""

    def __init__(self):
        self.product_recipes: list[Recipe] = []
        self.quantities: dict[str, float] = {}
        self.raw_ingredients: dict[str, tuple] = {}
        self.intermediate_servings: dict[str, float] = {}
        self.existing_intermediate_amounts: dict[str, dict[str, float]] = {}

    def clear_all_state(self):
        """Clear all calculation state."""
        self.quantities.clear()
        self.raw_ingredients.clear()
        self.intermediate_servings.clear()
        self.existing_intermediate_amounts.clear()
        logger.info("Cleared all calculation state")

    def update_quantity(self, recipe_name: str, quantity: float):
        """Update quantity for a recipe."""
        if quantity > 0:
            self.quantities[recipe_name] = quantity
        elif recipe_name in self.quantities:
            del self.quantities[recipe_name]

    def update_existing_weight(self, recipe_name: str, weight: float):
        """Update existing weight for a recipe and clear servings."""
        if recipe_name not in self.existing_intermediate_amounts:
            self.existing_intermediate_amounts[recipe_name] = {}
        
        if weight > 0:
            self.existing_intermediate_amounts[recipe_name]["weight"] = weight
            # Clear servings when weight is entered (they're mutually exclusive)
            self.existing_intermediate_amounts[recipe_name]["servings"] = 0.0
        else:
            # Set to 0 instead of deleting to maintain consistent structure
            self.existing_intermediate_amounts[recipe_name]["weight"] = 0.0

    def update_existing_servings(self, recipe_name: str, servings: float):
        """Update existing servings for a recipe and clear weight."""
        if recipe_name not in self.existing_intermediate_amounts:
            self.existing_intermediate_amounts[recipe_name] = {}
        
        if servings > 0:
            self.existing_intermediate_amounts[recipe_name]["servings"] = servings
            # Clear weight when servings is entered (they're mutually exclusive)
            self.existing_intermediate_amounts[recipe_name]["weight"] = 0.0
        else:
            # Set to 0 instead of deleting to maintain consistent structure
            self.existing_intermediate_amounts[recipe_name]["servings"] = 0.0

    def get_recipe_lookup(self) -> dict[str, Recipe]:
        """Get recipe lookup dictionary."""
        return {recipe.name.lower(): recipe for recipe in self.product_recipes}

    def has_quantities(self) -> bool:
        """Check if any quantities are set."""
        return bool(self.quantities)

    def has_results(self) -> bool:
        """Check if calculation results exist."""
        return bool(self.raw_ingredients or self.intermediate_servings)