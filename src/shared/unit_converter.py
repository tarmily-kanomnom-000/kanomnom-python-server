# Unit conversion utilities for both volume and density-based conversions

# Unit conversion map - converts to ml as base liquid unit
UNIT_CONVERSIONS = {
    "tsp": 4.92892,  # 1 tsp = 4.92892 ml (US teaspoon)
    "tbsp": 14.7868,  # 1 tbsp = 14.7868 ml (US tablespoon)
    "ml": 1.0,  # ml to ml (no conversion)
    "g": None,  # weight units don't convert to volume
    "count": None,  # discrete units don't convert
    "drop": 0.05,  # 1 drop ≈ 0.05 ml (approximate)
}

# Liquid density conversion table
# Densities are in g/mL at room temperature
# Sources: aqua-calc.com, FAO/INFOODS Density Database, USDA Food Database
LIQUID_DENSITIES = {
    # dairy
    "heavy cream": 1.01,
    "whole milk": 1.03,
    "evaporated milk": 1.08,
    # plant-based milks
    "coconut milk": 1.03,
    # oils and fats
    "canola oil": 0.91,
    # sweeteners
    "wildflower honey": 1.42,
    # Extracts and flavorings
    "vanilla extract": 0.88,
    # Other liquids
    "water": 1.00,
    "orange juice": 1.05,
    "coconut water": 1.01,
    "passion fruit pulp": 0.99,
    "frozen orange concentrate": 1.11,
}

# Special unit conversions for specific material-ingredient pairs
# Maps material name to conversion factors between units
SPECIAL_UNIT_CONVERSIONS = {
    "fresh mango": {
        "count_to_g": 181.8  # 1 fresh mango yields 181.8g chunks
    }
}


def get_special_conversion_factor(material_name: str, from_unit: str, to_unit: str) -> float:
    """Get special conversion factor for materials that don't follow standard density rules."""
    material_conversions = SPECIAL_UNIT_CONVERSIONS.get(material_name.lower())
    if not material_conversions:
        return None

    conversion_key = f"{from_unit}_to_{to_unit}"
    return material_conversions.get(conversion_key)


def convert_to_standard_unit(quantity: float, unit: str) -> tuple[float, str]:
    """
    Convert quantity to a standard unit where possible.

    Args:
        quantity: The amount
        unit: The original unit

    Returns:
        Tuple of (converted_quantity, standard_unit)
    """
    unit_lower = unit.lower()

    # Convert liquid measurements to ml
    if unit_lower in UNIT_CONVERSIONS and UNIT_CONVERSIONS[unit_lower] is not None:
        if unit_lower in ["tsp", "tbsp", "drop"]:
            converted_quantity = quantity * UNIT_CONVERSIONS[unit_lower]
            return (converted_quantity, "ml")

    # Return original if no conversion available
    return (quantity, unit)


def get_liquid_density(ingredient_name: str) -> float:
    """
    Get the density of a liquid ingredient in g/mL.

    Args:
        ingredient_name: Name of the ingredient

    Returns:
        float: Density in g/mL, or None if not found
    """
    # Normalize the ingredient name for lookup
    normalized_name = ingredient_name.lower().strip()

    # Direct lookup
    if normalized_name in LIQUID_DENSITIES:
        return LIQUID_DENSITIES[normalized_name]

    # Fuzzy matching for common variations
    for liquid_name, density in LIQUID_DENSITIES.items():
        if liquid_name in normalized_name or normalized_name in liquid_name:
            return density

    return None


def convert_ml_to_g(volume_ml: float, ingredient_name: str) -> float:
    """
    Convert volume in mL to mass in grams using ingredient density.

    Args:
        volume_ml: Volume in milliliters
        ingredient_name: Name of the ingredient

    Returns:
        float: Mass in grams, or None if density not found
    """
    density = get_liquid_density(ingredient_name)
    if density is not None:
        return volume_ml * density
    return None


def convert_g_to_ml(mass_g: float, ingredient_name: str) -> float:
    """
    Convert mass in grams to volume in mL using ingredient density.

    Args:
        mass_g: Mass in grams
        ingredient_name: Name of the ingredient

    Returns:
        float: Volume in milliliters, or None if density not found
    """
    density = get_liquid_density(ingredient_name)
    if density is not None:
        return mass_g / density
    return None
