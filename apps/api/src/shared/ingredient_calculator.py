import logging
from operator import attrgetter

from cachetools import LRUCache, cachedmethod

from pages.calculate_ingredients.constants import EXCLUDED_RECIPE_KEYWORD
from shared.models import Recipe
from shared.unit_converter import convert_to_standard_unit

logger = logging.getLogger(__name__)


class IngredientCalculator:
    """Handles ingredient calculations for recipes with caching for performance."""

    def __init__(self, recipes: list[Recipe]):
        self.recipes = recipes
        self.recipe_lookup = {recipe.name.lower(): recipe for recipe in recipes}
        # Cache for expensive calculations - holds up to 500 calculation results
        self._calculation_cache = LRUCache(maxsize=500)
        # Cache for raw ingredient breakdowns per recipe
        self._ingredient_cache = LRUCache(maxsize=1000)

    @cachedmethod(
        attrgetter("_calculation_cache"), key=lambda self, product_quantities: tuple(sorted(product_quantities.items()))
    )
    def calculate_raw_ingredients(self, product_quantities: dict[str, float]) -> dict[str, tuple[float, str]]:
        """
        Calculate raw ingredients needed for given product quantities.

        Args:
            product_quantities: dict of {recipe_name: quantity}

        Returns:
            dict of {raw_ingredient_name: (total_quantity_needed, unit)}
        """
        raw_ingredients = {}

        def get_raw_ingredients_for_recipe(
            recipe_name: str, needed_quantity: float, visited: set[str] = None
        ) -> dict[str, tuple[float, str]]:
            if visited is None:
                visited = set()

            recipe_key = recipe_name.lower()
            if recipe_key in visited:
                logger.warning(f"Circular dependency detected for recipe: {recipe_name}")
                return {}

            if recipe_key not in self.recipe_lookup:
                return {recipe_name: (needed_quantity, "g")}

            recipe = self.recipe_lookup[recipe_key]
            if not recipe.produced_amount or recipe.produced_amount <= 0:
                logger.warning(f"Recipe {recipe_name} has no production amount, treating as raw ingredient")
                return {recipe_name: (needed_quantity, recipe.produced_unit.value if recipe.produced_unit else "g")}

            visited.add(recipe_key)
            ingredient_breakdown = {}

            # Calculate how many units of the recipe we need to make
            units_to_produce = needed_quantity / (recipe.produced_amount or 1)

            for ingredient in recipe.ingredients.values():
                ingredient_name_lower = ingredient.name.lower()
                ingredient_quantity_needed = ingredient.quantity * units_to_produce

                # Check if this ingredient is itself a recipe
                if ingredient_name_lower in self.recipe_lookup:
                    sub_ingredients = get_raw_ingredients_for_recipe(ingredient.name, ingredient_quantity_needed, visited.copy())
                    for sub_ingredient, (sub_quantity, sub_unit) in sub_ingredients.items():
                        if sub_ingredient in ingredient_breakdown:
                            existing_qty, existing_unit = ingredient_breakdown[sub_ingredient]
                            ingredient_breakdown[sub_ingredient] = (existing_qty + sub_quantity, existing_unit)
                        else:
                            ingredient_breakdown[sub_ingredient] = (sub_quantity, sub_unit)
                else:
                    # This is a raw ingredient
                    ingredient_key = ingredient.name
                    if ingredient_key in ingredient_breakdown:
                        existing_qty, existing_unit = ingredient_breakdown[ingredient_key]
                        ingredient_breakdown[ingredient_key] = (
                            existing_qty + ingredient_quantity_needed,
                            existing_unit,
                        )
                    else:
                        ingredient_breakdown[ingredient_key] = (ingredient_quantity_needed, ingredient.unit.value)

            visited.remove(recipe_key)
            return ingredient_breakdown

        def get_raw_ingredients_for_single_unit(product_name: str) -> dict[str, tuple[float, str]]:
            """Calculate raw ingredients needed to make exactly 1 unit of a product."""
            product_key = product_name.lower()
            if product_key not in self.recipe_lookup:
                logger.warning(f"Product '{product_name}' not found in recipes")
                return {}

            product_recipe = self.recipe_lookup[product_key]
            raw_ingredients_for_unit = {}

            for ingredient in product_recipe.ingredients.values():
                ingredient_name_lower = ingredient.name.lower()
                ingredient_quantity_needed = ingredient.quantity

                if ingredient_name_lower in self.recipe_lookup:
                    sub_ingredients = get_raw_ingredients_for_recipe(ingredient.name, ingredient_quantity_needed, set())
                    for sub_ingredient, (sub_quantity, sub_unit) in sub_ingredients.items():
                        if sub_ingredient in raw_ingredients_for_unit:
                            existing_qty, existing_unit = raw_ingredients_for_unit[sub_ingredient]
                            raw_ingredients_for_unit[sub_ingredient] = (existing_qty + sub_quantity, existing_unit)
                        else:
                            raw_ingredients_for_unit[sub_ingredient] = (sub_quantity, sub_unit)
                else:
                    ingredient_key = ingredient.name
                    if ingredient_key in raw_ingredients_for_unit:
                        existing_qty, existing_unit = raw_ingredients_for_unit[ingredient_key]
                        raw_ingredients_for_unit[ingredient_key] = (
                            existing_qty + ingredient_quantity_needed,
                            existing_unit,
                        )
                    else:
                        raw_ingredients_for_unit[ingredient_key] = (ingredient_quantity_needed, ingredient.unit.value)

            return raw_ingredients_for_unit

        for product_name, quantity in product_quantities.items():
            if quantity > 0:
                breakdown = get_raw_ingredients_for_single_unit(product_name)
                for ingredient, (amount_per_unit, unit) in breakdown.items():
                    total_amount = amount_per_unit * quantity

                    # Apply unit conversion to standardize measurements
                    converted_amount, converted_unit = convert_to_standard_unit(total_amount, unit)

                    if ingredient in raw_ingredients:
                        existing_amount, existing_unit = raw_ingredients[ingredient]
                        # If units match, add quantities; otherwise keep separate entries
                        if existing_unit == converted_unit:
                            raw_ingredients[ingredient] = (existing_amount + converted_amount, existing_unit)
                        else:
                            # Handle unit conflicts by creating a combined entry key
                            raw_ingredients[f"{ingredient} ({converted_unit})"] = (converted_amount, converted_unit)
                    else:
                        raw_ingredients[ingredient] = (converted_amount, converted_unit)

        return raw_ingredients

    def calculate_ingredients_and_servings(
        self, selected_quantities: dict[str, float]
    ) -> tuple[dict[str, float], dict[str, tuple[float, str]]]:
        """
        Calculate both intermediate servings and raw ingredients in one unified pass.

        Args:
            selected_quantities: dict of {recipe_name: quantity}

        Returns:
            tuple of (intermediate_servings, raw_ingredients)
            - intermediate_servings: dict of {recipe_name: servings_needed}
            - raw_ingredients: dict of {raw_ingredient_name: (total_quantity_needed, unit)}
        """
        intermediate_servings = {}
        raw_ingredients = {}

        def process_recipe(recipe_name: str, needed_quantity: float, is_root_product: bool = False, visited: set = None):
            if visited is None:
                visited = set()

            recipe_key = recipe_name.lower()

            # Avoid circular dependencies
            if recipe_key in visited:
                logger.warning(f"Circular dependency detected for recipe: {recipe_name}")
                return

            # If not a recipe, it's a raw ingredient - but this should not happen
            # since we handle raw ingredients directly in the ingredient processing loop
            if recipe_key not in self.recipe_lookup:
                logger.warning(f"Raw ingredient {recipe_name} reached process_recipe directly - this shouldn't happen")
                return

            recipe = self.recipe_lookup[recipe_key]
            visited.add(recipe_key)

            # Skip chiffon recipes entirely
            if EXCLUDED_RECIPE_KEYWORD in recipe.name.lower():
                logger.info(f"Skipping {EXCLUDED_RECIPE_KEYWORD} recipe: {recipe.name}")
                visited.remove(recipe_key)
                return

            # Add to intermediate servings (but not root products)
            if not is_root_product and recipe.produced_amount and recipe.produced_amount > 0:
                servings_needed = needed_quantity / recipe.produced_amount
                if recipe.name not in intermediate_servings:
                    intermediate_servings[recipe.name] = 0
                intermediate_servings[recipe.name] += servings_needed
                logger.debug(f"Added intermediate recipe: {recipe.name} ({servings_needed} servings)")

            # Calculate scaling factor for ingredients
            if recipe.produced_amount and recipe.produced_amount > 0:
                if is_root_product:
                    # For root products, needed_quantity is the number of products wanted
                    scale_factor = needed_quantity
                else:
                    # For intermediate recipes, calculate servings needed and scale accordingly
                    servings_needed = needed_quantity / recipe.produced_amount
                    scale_factor = servings_needed
            else:
                scale_factor = needed_quantity

            # Process each ingredient in this recipe
            for ingredient in recipe.ingredients.values():
                # Skip chiffon ingredients
                if EXCLUDED_RECIPE_KEYWORD in ingredient.name.lower():
                    logger.info(f"Skipping {EXCLUDED_RECIPE_KEYWORD} ingredient: {ingredient.name}")
                    continue

                if is_root_product:
                    # For root products, scale by quantity of products * ingredient quantity per product
                    ingredient_needed = ingredient.quantity * needed_quantity
                else:
                    # For intermediate recipes, scale by servings * ingredient quantity per serving
                    ingredient_needed = ingredient.quantity * scale_factor

                # Check if this ingredient is a recipe or raw ingredient
                ingredient_key = ingredient.name.lower()
                if ingredient_key in self.recipe_lookup:
                    logger.debug(f"Processing ingredient '{ingredient.name}' as recipe (from {recipe.name})")
                    process_recipe(ingredient.name, ingredient_needed, False, visited.copy())
                else:
                    unit_str = ingredient.unit.value
                    converted_qty, converted_unit = convert_to_standard_unit(ingredient_needed, unit_str)

                    if ingredient.name in raw_ingredients:
                        existing_qty, existing_unit = raw_ingredients[ingredient.name]
                        if existing_unit == converted_unit:
                            raw_ingredients[ingredient.name] = (existing_qty + converted_qty, existing_unit)
                        else:
                            # Handle unit conflicts
                            raw_ingredients[f"{ingredient.name} ({converted_unit})"] = (converted_qty, converted_unit)
                    else:
                        raw_ingredients[ingredient.name] = (converted_qty, converted_unit)

            visited.remove(recipe_key)

        # Start calculation for each selected product
        for product_name, quantity in selected_quantities.items():
            process_recipe(product_name, quantity, is_root_product=True)

        return intermediate_servings, raw_ingredients

    @cachedmethod(
        attrgetter("_calculation_cache"), key=lambda self, remaining_servings: tuple(sorted(remaining_servings.items()))
    )
    def calculate_raw_ingredients_from_remaining(self, remaining_servings: dict[str, float]) -> dict[str, tuple[float, str]]:
        """Calculate raw ingredients needed based on remaining intermediate servings."""
        raw_ingredients = {}

        for recipe_name, servings_needed in remaining_servings.items():
            if servings_needed <= 0 or self._should_skip_recipe(recipe_name):
                continue

            self._process_recipe_ingredients(recipe_name, servings_needed, raw_ingredients)

        return raw_ingredients

    def _should_skip_recipe(self, recipe_name):
        """Check if recipe should be skipped (e.g., chiffon recipes)."""
        return EXCLUDED_RECIPE_KEYWORD in recipe_name.lower()

    def _process_recipe_ingredients(self, recipe_name, servings_needed, raw_ingredients):
        """Process ingredients for a single recipe."""
        recipe_key = recipe_name.lower()
        if recipe_key not in self.recipe_lookup:
            return

        recipe = self.recipe_lookup[recipe_key]

        for ingredient in recipe.ingredients.values():
            if self._should_skip_recipe(ingredient.name):
                continue

            self._add_ingredient_to_totals(ingredient, servings_needed, raw_ingredients)

    def _add_ingredient_to_totals(self, ingredient, servings_needed, raw_ingredients):
        """Add ingredient to raw ingredients totals."""
        total_needed = ingredient.quantity * servings_needed
        ingredient_key = ingredient.name.lower()

        # Skip nested recipes for now (only want raw ingredients)
        if ingredient_key in self.recipe_lookup:
            return

        # Convert and add raw ingredient
        unit_str = ingredient.unit.value
        converted_qty, converted_unit = convert_to_standard_unit(total_needed, unit_str)

        self._merge_ingredient_quantities(ingredient.name, converted_qty, converted_unit, raw_ingredients)

    def _merge_ingredient_quantities(self, ingredient_name, quantity, unit, raw_ingredients):
        """Merge ingredient quantities, handling unit conflicts."""
        if ingredient_name in raw_ingredients:
            existing_qty, existing_unit = raw_ingredients[ingredient_name]
            if existing_unit == unit:
                raw_ingredients[ingredient_name] = (existing_qty + quantity, unit)
            else:
                # Handle unit conflicts by creating separate entries
                raw_ingredients[f"{ingredient_name} ({unit})"] = (quantity, unit)
        else:
            raw_ingredients[ingredient_name] = (quantity, unit)
