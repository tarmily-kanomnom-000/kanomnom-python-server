"""Business logic service for ingredients calculations."""

from __future__ import annotations

import logging

from shared.ingredient_calculator import IngredientCalculator
from shared.models import Recipe

from .state_manager import IngredientsState, IntermediateServings

logger = logging.getLogger(__name__)

SelectedQuantities = dict[str, float]


class IngredientsCalculationService:
    """Handles all ingredients calculation business logic."""

    def __init__(self, state: IngredientsState) -> None:
        self.state = state
        self._calculator: IngredientCalculator | None = None

    def set_recipes(self, recipes: list[Recipe]) -> None:
        """Set recipes and initialize calculator."""

        self.state.product_recipes = recipes
        self._calculator = IngredientCalculator(recipes)
        logger.info("Initialized calculator with %d recipes", len(recipes))

    def calculate_ingredients(self, selected_quantities: SelectedQuantities) -> bool:
        """Perform ingredient calculations."""

        if not self._calculator:
            logger.warning("Cannot calculate: missing calculator")
            return False

        if not selected_quantities:
            logger.warning("Cannot calculate: no quantities selected")
            return False

        try:
            intermediate_servings, raw_ingredients = self._calculator.calculate_ingredients_and_servings(selected_quantities)
            self.state.intermediate_servings = intermediate_servings
            self.state.raw_ingredients = raw_ingredients

            logger.info("Calculated %d raw ingredients", len(raw_ingredients))
            logger.info("Calculated %d intermediate servings", len(intermediate_servings))
            return True
        except Exception:  # noqa: BLE001 - surfaced via log, caller shows failure message
            logger.exception("Calculation failed")
            return False

    def recalculate_with_existing(self) -> bool:
        """Recalculate ingredients accounting for existing intermediate amounts."""

        if not self._calculator:
            logger.warning("Cannot recalculate: missing calculator")
            return False

        try:
            remaining_servings = self._calculate_remaining_servings()
            if remaining_servings:
                self.state.raw_ingredients = self._calculator.calculate_raw_ingredients_from_remaining(remaining_servings)
            else:
                self.state.raw_ingredients = {}

            logger.info("Recalculated with existing amounts: %d raw ingredients", len(self.state.raw_ingredients))
            return True
        except Exception:  # noqa: BLE001 - surfaced via log, caller shows failure message
            logger.exception("Recalculation failed")
            return False

    def _calculate_remaining_servings(self) -> IntermediateServings:
        """Calculate remaining servings needed after accounting for existing amounts."""

        if not self._calculator:
            return {}

        remaining_servings: IntermediateServings = {}
        recipe_lookup = {recipe.name.lower(): recipe for recipe in self._calculator.recipes}

        for recipe_name, needed_servings in self.state.intermediate_servings.items():
            existing_servings = self._calculate_existing_servings(recipe_name, recipe_lookup)
            remaining = max(0.0, needed_servings - existing_servings)

            if remaining > 0:
                remaining_servings[recipe_name] = remaining

            logger.debug(
                "%s: needed=%s, existing=%s, remaining=%s",
                recipe_name,
                needed_servings,
                existing_servings,
                remaining,
            )

        return remaining_servings

    def _calculate_existing_servings(self, recipe_name: str, recipe_lookup: dict[str, Recipe]) -> float:
        """Calculate existing servings for a recipe from weight and servings inputs."""

        existing_amounts = self.state.existing_intermediate_amounts.get(recipe_name)
        if not existing_amounts:
            return 0.0

        existing_servings = existing_amounts.get("servings", 0.0)
        existing_weight = existing_amounts.get("weight", 0.0)

        if existing_weight > 0:
            existing_servings += self._convert_weight_to_servings(recipe_name, existing_weight, recipe_lookup)

        return existing_servings

    def _convert_weight_to_servings(self, recipe_name: str, weight: float, recipe_lookup: dict[str, Recipe]) -> float:
        """Convert weight to servings for a recipe."""

        recipe_key = recipe_name.lower()
        recipe = recipe_lookup.get(recipe_key)
        if recipe is None:
            logger.warning("Recipe not found for weight conversion: %s", recipe_name)
            return 0.0

        if not recipe.produced_amount or recipe.produced_amount <= 0:
            logger.warning("Recipe %s has no production amount for weight conversion", recipe_name)
            return 0.0

        servings = weight / recipe.produced_amount
        logger.debug("Converted %sg to %s servings for %s", weight, servings, recipe_name)
        return servings

    def get_calculation_summary(self) -> dict[str, int]:
        """Get summary of current calculations."""

        return {
            "recipes": len(self.state.product_recipes),
            "quantities_set": len(self.state.quantities),
            "raw_ingredients": len(self.state.raw_ingredients),
            "intermediate_servings": len(self.state.intermediate_servings),
            "existing_amounts": len(self.state.existing_intermediate_amounts),
        }
