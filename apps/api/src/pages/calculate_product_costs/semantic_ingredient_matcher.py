import logging
from typing import Callable, NamedTuple, Optional

import inflect
from cachetools import LRUCache
from rapidfuzz import fuzz, process


class MatchResult(NamedTuple):
    """Result of ingredient matching with metadata."""

    ingredient: str
    matched_material: Optional[str]
    match_type: str  # 'exact' or 'semantic'


logger = logging.getLogger(__name__)


class SemanticIngredientMatcher:
    def __init__(self, api_client: Callable = None, fuzzy_threshold: float = 40.0, max_candidates: int = 3):
        """
        Initialize semantic matcher with an API client function.

        Args:
            api_client: Function that takes (messages, max_tokens) and returns response string
            fuzzy_threshold: Minimum fuzzy score (0-100) for candidate materials
            max_candidates: Maximum number of candidate materials to send to LLM
        """
        self.api_client = api_client
        self.fuzzy_threshold = fuzzy_threshold
        self.max_candidates = max_candidates
        self.match_cache = LRUCache(maxsize=1000)  # LRU Cache for ingredient -> material matches

        logger.info(f"Initialized semantic matcher (fuzzy_threshold={fuzzy_threshold}, max_candidates={max_candidates})")

    def set_api_client(self, api_client: Callable):
        """Set or update the API client function."""
        self.api_client = api_client
        logger.info("Updated API client for semantic matcher")

    def _filter_materials_by_fuzzy_score(self, unmatched_ingredients: list[str], available_materials: list[str]) -> list[str]:
        """
        Filter available materials using fuzzy string matching to get best candidates.

        Args:
            unmatched_ingredients: list of ingredients that need matches
            available_materials: Full list of available materials

        Returns:
            list of candidate materials that have good fuzzy scores
        """
        if not unmatched_ingredients or not available_materials:
            return available_materials

        candidate_materials = set()

        for ingredient in unmatched_ingredients:
            # Get fuzzy matches for this ingredient
            matches = process.extract(
                ingredient,
                available_materials,
                scorer=fuzz.token_sort_ratio,
                limit=self.max_candidates,
                score_cutoff=self.fuzzy_threshold,
            )

            # Add the matched materials to candidates
            for match, _, _ in matches:
                candidate_materials.add(match)

            logger.debug(f"🔍 Fuzzy search for '{ingredient}': {len(matches)} candidates (scores >= {self.fuzzy_threshold})")

        candidates_list = list(candidate_materials)
        original_count = len(available_materials)
        filtered_count = len(candidates_list)

        logger.info(
            f"📊 Fuzzy filtering: {original_count} materials → {filtered_count} candidates ({filtered_count / original_count * 100:.1f}%)"
        )

        return candidates_list

    def _create_matching_prompt(self, unmatched_ingredients: list[str], available_materials: list[str]) -> list[dict[str, str]]:
        """Create the prompt messages for matching unmatched ingredients to available materials."""
        ingredients_list = "\n".join(f"{i + 1}. {ingredient}" for i, ingredient in enumerate(unmatched_ingredients))
        materials_list = "\n".join(f"{i + 1}. {material}" for i, material in enumerate(available_materials))

        return [
            {
                "role": "system",
                "content": "You are a food expert. Match recipe ingredients to available purchase materials that can be substituted for cooking/baking. Be very strict about what makes sense to substitute.",
            },
            {
                "role": "user",
                "content": f"""I have these unmatched recipe ingredients (list A):
{ingredients_list}

And I have these available purchase materials (list B):  
{materials_list}

For each ingredient in list A, find the BEST matching material from list B that can be substituted for cooking/baking.

MATCHING RULES:
- Only match ingredients that are TRUE SUBSTITUTES for each other
- Different salt types (kosher salt, sea salt, table salt) can substitute for "salt"
- Different sugar types (granulated, white, cane, brown sugar) can substitute for "sugar"
- Different flour types (all-purpose, unbleached, bleached) can substitute for "flour"  
- Different honey types (wildflower, clover, manuka) can substitute for "honey"
- Different butter types (salted, unsalted) can substitute for "butter"
- Different milk types (whole, 2%, skim) can substitute for "milk"
- Different vanilla types (extract, essence) can substitute for "vanilla"

NEVER MATCH THESE:
- Salt ≠ salted butter, salted nuts, etc. (these contain salt but ARE NOT salt)
- Water ≠ coconut water, flavored waters (these are different liquids)
- Sugar ≠ sweet products that contain sugar  
- Butter ≠ products that contain butter
- Fresh vs frozen are different (don't substitute)
- Different chocolate percentages are different (don't substitute)

OUTPUT FORMAT (exactly as shown):
MATCH: recipe_ingredient -> available_material
NO_MATCH: recipe_ingredient

EXAMPLE:
MATCH: salt -> kosher salt
MATCH: sugar -> granulated sugar  
NO_MATCH: vanilla extract

Now match the ingredients:""",
            },
        ]

    def find_ingredient_matches(self, unmatched_ingredients: list[str], available_materials: list[str]) -> dict[str, str]:
        """
        Find matches between unmatched recipe ingredients and available materials.
        Uses fuzzy string matching to pre-filter materials before LLM call for efficiency.

        Args:
            unmatched_ingredients: list of recipe ingredients that need matches
            available_materials: list of available material names from purchase data

        Returns:
            dict mapping recipe ingredient to matched material (or None if no match)
        """
        if not unmatched_ingredients or not available_materials:
            return {}

        # Pre-filter materials using fuzzy matching to reduce LLM workload
        candidate_materials = self._filter_materials_by_fuzzy_score(unmatched_ingredients, available_materials)

        # Log LLM call details
        logger.info("🤖 Calling LLM for semantic matching")
        logger.info(f"   📝 Unmatched ingredients: {unmatched_ingredients}")
        logger.info(f"   📦 Candidate materials: {candidate_materials} options (filtered from {len(available_materials)})")

        try:
            # Create the prompt messages with filtered candidates
            messages = self._create_matching_prompt(unmatched_ingredients, candidate_materials)

            # Call the API client
            response = self.api_client(messages, max_tokens=1024)

            if response:
                # Parse the response and build matches (use candidate_materials for validation)
                matches = self._parse_matching_response(response, unmatched_ingredients, candidate_materials)

                # Log results
                successful_matches = {k: v for k, v in matches.items() if v is not None}
                logger.info(
                    f"✅ LLM call completed: {len(successful_matches)} matches found out of {len(unmatched_ingredients)} ingredients"
                )
                if successful_matches:
                    logger.info(f"   🔗 Successful matches: {successful_matches}")

                return matches
            else:
                logger.error("❌ Empty response from API client")
                return {}

        except Exception as e:
            logger.error(f"Error finding ingredient matches: {e}")
            return {}

    def _parse_matching_response(
        self, response: str, unmatched_ingredients: list[str], available_materials: list[str]
    ) -> dict[str, str]:
        """Parse the LLM response to build ingredient matches."""
        matches = {}

        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue

            if line.startswith("MATCH:"):
                # Format: MATCH: recipe_ingredient -> available_material
                try:
                    match_part = line[6:].strip()  # Remove "MATCH:" prefix
                    if "->" in match_part:
                        parts = match_part.split("->", 1)
                        if len(parts) == 2:
                            recipe_ingredient = parts[0].strip()
                            material = parts[1].strip()

                            # Verify both ingredients exist in their respective lists (case-insensitive)
                            recipe_found = None
                            material_found = None

                            for orig_ingredient in unmatched_ingredients:
                                if recipe_ingredient.lower() == orig_ingredient.lower().strip():
                                    recipe_found = orig_ingredient
                                    break

                            for orig_material in available_materials:
                                if material.lower() == orig_material.lower().strip():
                                    material_found = orig_material
                                    break

                            if recipe_found and material_found:
                                matches[recipe_found] = material_found

                except Exception as e:
                    logger.warning(f"Failed to parse MATCH line: {line} - {e}")

            elif line.startswith("NO_MATCH:"):
                # Format: NO_MATCH: recipe_ingredient
                try:
                    ingredient = line[9:].strip()  # Remove "NO_MATCH:" prefix
                    # Verify ingredient exists in unmatched list
                    for orig_ingredient in unmatched_ingredients:
                        if ingredient.lower() == orig_ingredient.lower().strip():
                            matches[orig_ingredient] = None
                            break
                except Exception as e:
                    logger.warning(f"Failed to parse NO_MATCH line: {line} - {e}")

        return matches

    def find_best_matches(self, recipe_ingredients: list[str], available_materials: list[str]) -> list[MatchResult]:
        """
        Find the best matching purchase materials for multiple recipe ingredients using two-pass matching with caching.

        Args:
            recipe_ingredients: list of ingredient names from recipe
            available_materials: list of available material names from purchase data

        Returns:
            list[MatchResult]: list of match results with metadata about match type
        """
        if not recipe_ingredients or not available_materials:
            return [MatchResult(ingredient, None, "no_match") for ingredient in recipe_ingredients]

        results = []
        unmatched_ingredients = []

        # Pass 0: Check cache first
        for ingredient in recipe_ingredients:
            if ingredient in self.match_cache:
                cached_result = self.match_cache[ingredient]
                results.append(cached_result)
                logger.debug(f"🔄 Using cached match for '{ingredient}': {cached_result.matched_material}")
            else:
                # Pass 1: Plural/singular matching (case-insensitive)
                exact_match = self._find_plural_singular_match(ingredient, available_materials)

                if exact_match:
                    match_result = MatchResult(ingredient, exact_match, "exact")
                    results.append(match_result)
                    self.match_cache[ingredient] = match_result  # Cache exact matches too
                else:
                    unmatched_ingredients.append(ingredient)

        # Pass 2: Semantic matching for uncached, unmatched ingredients
        if unmatched_ingredients:
            logger.info(f"🔍 Semantic matching needed for {len(unmatched_ingredients)} uncached ingredients")
            semantic_matches = self.find_ingredient_matches(unmatched_ingredients, available_materials)
            for ingredient in unmatched_ingredients:
                match = semantic_matches.get(ingredient)
                if match:
                    match_result = MatchResult(ingredient, match, "semantic")
                    results.append(match_result)
                    self.match_cache[ingredient] = match_result  # Cache semantic matches
                else:
                    match_result = MatchResult(ingredient, None, "no_match")
                    results.append(match_result)
                    self.match_cache[ingredient] = match_result  # Cache no-matches too

        return results

    def _find_plural_singular_match(self, ingredient: str, available_materials: list[str]) -> Optional[str]:
        """
        Find match handling plural/singular variations using inflect.

        Args:
            ingredient: Ingredient name to match
            available_materials: list of available materials

        Returns:
            str: Matched material name or None if not found
        """
        ingredient_lower = ingredient.lower().strip()
        p = inflect.engine()

        # Create set of material names for faster lookup
        materials_lower = {material.lower().strip(): material for material in available_materials}

        # Try exact match first
        if ingredient_lower in materials_lower:
            return materials_lower[ingredient_lower]

        # Try plural of ingredient
        ingredient_plural = p.plural(ingredient_lower)
        if ingredient_plural in materials_lower:
            return materials_lower[ingredient_plural]

        # Try singular of ingredient
        ingredient_singular = p.singular_noun(ingredient_lower)
        if ingredient_singular and ingredient_singular in materials_lower:
            return materials_lower[ingredient_singular]

        return None


# Global instance for reuse
_semantic_matcher = None


def get_semantic_matcher(
    api_client: Callable = None, fuzzy_threshold: float = 40.0, max_candidates: int = 2
) -> SemanticIngredientMatcher:
    """Get the global semantic matcher instance."""
    global _semantic_matcher

    if _semantic_matcher is None:
        _semantic_matcher = SemanticIngredientMatcher(api_client, fuzzy_threshold, max_candidates)
    elif api_client:
        _semantic_matcher.set_api_client(api_client)
    return _semantic_matcher
