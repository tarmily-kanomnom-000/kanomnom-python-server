from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    api_key: str
    location_name: str
    location_types: list[str]
    address: InstanceAddress | None = None


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
class UniversalManifest:
    """Aggregated universal manifest content shared across Grocy instances."""

    quantity_units: list[QuantityUnitDefinition]

    @staticmethod
    def load(universal_dir: Path) -> "UniversalManifest":
        """Load the universal manifest JSON payloads from disk."""
        quantity_units = _load_json_array(universal_dir / "quantity_units.json")
        return UniversalManifest(
            quantity_units=[QuantityUnitDefinition.from_dict(item) for item in quantity_units]
        )


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    """Load a JSON array from disk and validate its shape."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [dict(item) for item in data]
