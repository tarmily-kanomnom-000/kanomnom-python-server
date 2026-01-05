import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Unit(Enum):
    GRAM = "g"
    MILLILITER = "ml"
    COUNT = "count"
    TEASPOON = "tsp"
    TABlESPOON = "tbsp"
    DROP = "drop"


@dataclass
class Ingredient:
    id: int
    name: str
    quantity: float
    unit: Unit


class Recipe:
    def __init__(self, recipe_stub: dict):
        self.id: int = recipe_stub["id"]
        self.name: str = recipe_stub["name"]
        self.description: str = recipe_stub["description"]

        self.ingredients: dict[tuple[int, str], Ingredient] = {}
        self.keywords: list[str] = []

        self.produced_amount: float = None
        self.produced_unit: Unit = None
        self._parse_produced_amount()

    def parse_recipe_details(self, full_recipe_details: dict):
        self.keywords: list[str] = [keyword["label"] for keyword in full_recipe_details["keywords"]]
        ingredient_map = {}

        for step in full_recipe_details.get("steps", []):
            for ingredient in step.get("ingredients", []):
                if ingredient["food"] is None:
                    print(f"Skipping ingredient with no food data: {ingredient}")
                    continue
                try:
                    food_id = ingredient["food"]["id"]
                    food_name = ingredient["food"]["name"].strip().lower()
                    unit_name = ingredient["unit"]["name"].strip().lower()
                    amount = float(ingredient["amount"])

                    try:
                        unit_enum = Unit(unit_name)
                    except ValueError:
                        error_msg = f"Unknown unit '{unit_name}' encountered for ingredient '{food_name}' in recipe '{self.name}'. Available units: {[u.value for u in Unit]}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                    # Skip zero amounts
                    if amount == 0:
                        continue

                    key = (food_id, food_name)

                    if key in ingredient_map:
                        # Check if units match before aggregating
                        if ingredient_map[key].unit == unit_enum:
                            ingredient_map[key].quantity += amount
                        else:
                            # Different units for same ingredient - prefer the non-zero entry
                            # This handles cases where Tandoor has both 0.0g and 0.5 count entries
                            logger.debug(
                                f"Ingredient '{food_name}' has conflicting units in recipe '{self.name}': existing {ingredient_map[key].unit.value}, new {unit_enum.value}. Using the non-zero entry."
                            )
                            # Keep the new entry since we already filtered out zero amounts
                            ingredient_map[key] = Ingredient(id=food_id, name=food_name, quantity=amount, unit=unit_enum)
                    else:
                        ingredient_map[key] = Ingredient(id=food_id, name=food_name, quantity=amount, unit=unit_enum)
                except Exception as e:
                    print(f"Error processing ingredient: {e}, ingredient data: {ingredient}")
                    continue

        self.ingredients = ingredient_map

        if self.produced_amount is None:
            gram_total = sum(ingredient.quantity for ingredient in ingredient_map.values() if ingredient.unit == Unit.GRAM)
            if gram_total > 0:
                self.produced_amount = gram_total
                self.produced_unit = Unit.GRAM

    def _parse_produced_amount(self):
        if not self.description:
            return

        pattern = r"Produces\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+per\s+serving"
        match = re.search(pattern, self.description)

        if match:
            try:
                unit_enum = Unit(match.group(2))
                self.produced_amount = float(match.group(1))
                self.produced_unit = unit_enum
            except ValueError:
                error_msg = f"Unknown unit '{match.group(2)}' in produced amount description for recipe '{self.name}'. Available units: {[u.value for u in Unit]}"
                logger.error(error_msg)
                raise ValueError(error_msg)

    def to_cache_dict(self) -> dict:
        """Convert recipe to cache-compatible dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "ingredients": {
                f"{k[0]}_{k[1]}": {"id": v.id, "name": v.name, "quantity": v.quantity, "unit": v.unit.value}
                for k, v in self.ingredients.items()
            },
            "produced_amount": self.produced_amount,
            "produced_unit": self.produced_unit.value if self.produced_unit else None,
        }

    @classmethod
    def from_cache_dict(cls, cache_dict: dict):
        """Create recipe from cached dictionary."""
        recipe_stub = {"id": cache_dict["id"], "name": cache_dict["name"], "description": cache_dict["description"]}
        recipe = cls(recipe_stub)
        recipe.keywords = cache_dict["keywords"]

        for key, ing_data in cache_dict["ingredients"].items():
            food_id, food_name = key.split("_", 1)
            recipe.ingredients[(int(food_id), food_name)] = Ingredient(
                id=ing_data["id"], name=ing_data["name"], quantity=ing_data["quantity"], unit=Unit(ing_data["unit"])
            )

        recipe.produced_amount = cache_dict["produced_amount"]
        recipe.produced_unit = Unit(cache_dict["produced_unit"]) if cache_dict["produced_unit"] else None
        return recipe
