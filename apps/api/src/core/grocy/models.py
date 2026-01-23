from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass
class InstanceAddress:
    """Postal address for a Grocy instance."""

    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    country: str


@dataclass
class InstanceMetadata:
    """Connection metadata for a Grocy instance declared in metadata.yaml."""

    grocy_url: str
    location_name: str
    location_types: list[str]
    instance_timezone: str | None = None
    address: InstanceAddress | None = None


@dataclass(frozen=True)
class InstanceCredentials:
    """Credentials stored alongside Grocy instance metadata."""

    api_key: str


@dataclass
class QuantityUnitDefinition:
    """Semantic definition of a quantity unit shipped in the universal manifest."""

    name: str
    description: str | None
    name_plural: str
    plural_forms: str | None
    active: int

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "QuantityUnitDefinition":
        """Hydrate a manifest entry into a strongly typed definition."""
        return QuantityUnitDefinition(
            name=str(raw["name"]),
            description=str(raw["description"]) if raw.get("description") is not None else None,
            name_plural=str(raw["name_plural"]),
            plural_forms=str(raw["plural_forms"]) if raw.get("plural_forms") is not None else None,
            active=int(raw["active"]),
        )

    def normalized_name(self) -> str:
        """Return the canonical form of the unit name for dictionary keys."""
        return self.name.strip().lower()

    def to_payload(self, unit_id: int) -> dict[str, Any]:
        """Render the definition into the payload Grocy expects."""
        return {
            "id": unit_id,
            "name": self.name,
            "description": self.description,
            "name_plural": self.name_plural,
            "plural_forms": self.plural_forms,
            "active": self.active,
        }


@dataclass
class ProductGroupDefinition:
    """Semantic definition of a product group shipped in the universal manifest."""

    name: str
    description: str | None
    active: int

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "ProductGroupDefinition":
        """Hydrate a manifest entry into a strongly typed definition."""
        return ProductGroupDefinition(
            name=str(raw["name"]),
            description=str(raw["description"]) if raw.get("description") is not None else None,
            active=int(raw["active"]),
        )

    def normalized_name(self) -> str:
        """Return the canonical form of the product group name for dictionary keys."""
        return self.name.strip().lower()

    def to_payload(self, group_id: int) -> dict[str, Any]:
        """Render the definition into the payload Grocy expects."""
        return {
            "id": group_id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
        }


@dataclass
class ShoppingLocationDefinition:
    """Semantic definition of a shopping location shipped in the universal manifest."""

    name: str
    description: str | None
    active: int

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "ShoppingLocationDefinition":
        """Hydrate the manifest entry into a strongly typed definition."""
        return ShoppingLocationDefinition(
            name=str(raw["name"]),
            description=str(raw["description"]) if raw.get("description") is not None else None,
            active=int(raw["active"]),
        )

    def normalized_name(self) -> str:
        """Return the canonical form of the shopping location name for dictionary keys."""
        return self.name.strip().lower()

    def to_payload(self, location_id: int) -> dict[str, Any]:
        """Render the definition into the payload Grocy expects."""
        return {
            "id": location_id,
            "name": self.name,
            "description": self.description,
            "active": self.active,
        }


@dataclass
class UniversalManifest:
    """Aggregated universal manifest content shared across Grocy instances."""

    quantity_units: list[QuantityUnitDefinition]
    product_groups: list[ProductGroupDefinition]
    shopping_locations: list[ShoppingLocationDefinition]

    @staticmethod
    def load(universal_dir: Path) -> "UniversalManifest":
        """Load the universal manifest JSON payloads from disk."""
        quantity_units = _load_json_array(universal_dir / "quantity_units.json")
        product_groups = _load_json_array(universal_dir / "product_groups.json")
        shopping_locations = _load_json_array_candidates(
            [
                universal_dir / "shopping_locations.json",
                universal_dir / "shoppings_locations.json",
            ]
        )
        return UniversalManifest(
            quantity_units=[QuantityUnitDefinition.from_dict(item) for item in quantity_units],
            product_groups=[ProductGroupDefinition.from_dict(item) for item in product_groups],
            shopping_locations=[ShoppingLocationDefinition.from_dict(item) for item in shopping_locations],
        )


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array from disk and validate its shape."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [dict(item) for item in data]


def _load_json_array_candidates(paths: Sequence[Path]) -> list[dict[str, Any]]:
    """Load a JSON array from the first existing path, raising with context if missing."""
    for path in paths:
        if path.exists():
            return _load_json_array(path)
    attempted = ", ".join(str(path) for path in paths)
    raise FileNotFoundError(f"Expected one of the following manifest files to exist: {attempted}")
