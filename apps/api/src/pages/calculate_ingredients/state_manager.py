"""State management utilities for the ingredients calculator."""

from __future__ import annotations

import logging

from shared.models import Recipe

logger = logging.getLogger(__name__)

RawIngredients = dict[str, tuple[float, str]]
IntermediateServings = dict[str, float]
ExistingIntermediateAmounts = dict[str, dict[str, float]]


class IngredientsState:
    """Manages state for the ingredients calculator."""

    def __init__(self) -> None:
        self.product_recipes: list[Recipe] = []
        self.quantities: dict[str, float] = {}
        self.raw_ingredients: RawIngredients = {}
        self.intermediate_servings: IntermediateServings = {}
        self.existing_intermediate_amounts: ExistingIntermediateAmounts = {}

    def clear_all_state(self) -> None:
        """Clear all calculation state."""

        self.quantities.clear()
        self.raw_ingredients.clear()
        self.intermediate_servings.clear()
        self.existing_intermediate_amounts.clear()
        logger.info("Cleared all calculation state")

    def update_quantity(self, recipe_name: str, quantity: float) -> None:
        """Update quantity for a recipe."""

        if quantity > 0:
            self.quantities[recipe_name] = quantity
        else:
            self.quantities.pop(recipe_name, None)

    def update_existing_weight(self, recipe_name: str, weight: float) -> None:
        """Update existing weight for a recipe and clear servings."""

        record = self.existing_intermediate_amounts.setdefault(
            recipe_name, {"weight": 0.0, "servings": 0.0}
        )

        if weight > 0:
            record["weight"] = weight
            record["servings"] = 0.0
        else:
            record["weight"] = 0.0

    def update_existing_servings(self, recipe_name: str, servings: float) -> None:
        """Update existing servings for a recipe and clear weight."""

        record = self.existing_intermediate_amounts.setdefault(
            recipe_name, {"weight": 0.0, "servings": 0.0}
        )

        if servings > 0:
            record["servings"] = servings
            record["weight"] = 0.0
        else:
            record["servings"] = 0.0

    def get_recipe_lookup(self) -> dict[str, Recipe]:
        """Get recipe lookup dictionary."""

        return {recipe.name.lower(): recipe for recipe in self.product_recipes}

    def has_quantities(self) -> bool:
        """Check if any quantities are set."""

        return bool(self.quantities)

    def has_results(self) -> bool:
        """Check if calculation results exist."""

        return bool(self.raw_ingredients or self.intermediate_servings)
