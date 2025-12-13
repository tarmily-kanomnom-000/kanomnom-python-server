from __future__ import annotations

from dataclasses import dataclass

from core.grocy.client import GrocyClient
from core.grocy.models import QuantityUnitDefinition
from core.grocy.responses import GrocyQuantityUnit
from core.grocy.sync import CreatedEntity, EntitySyncResult, EntitySyncSpecification, EntitySyncer


@dataclass
class QuantityUnitSyncResult:
    """Result returned after reconciling quantity units."""

    identifier_by_normalized_name: dict[str, int]
    created: list[CreatedEntity[QuantityUnitDefinition]]


class QuantityUnitService:
    """Service encapsulating quantity unit reconciliation logic."""

    def __init__(self, client: GrocyClient, syncer: EntitySyncer[QuantityUnitDefinition]) -> None:
        self.client = client
        self.syncer = syncer

    def ensure_quantity_units(self, definitions: list[QuantityUnitDefinition]) -> QuantityUnitSyncResult:
        """Ensure the universal quantity units exist and return their Grocy ids keyed by name."""
        existing_units = self.client.list_quantity_units()
        specification = EntitySyncSpecification(
            manifest_items=definitions,
            existing_items=existing_units,
            manifest_key=lambda definition: definition.normalized_name(),
            existing_key=_existing_unit_key,
            payload_builder=lambda definition, new_id: definition.to_payload(new_id),
            creator=self.client.create_quantity_unit,
        )
        sync_result = self.syncer.synchronize(specification)
        lookup = self._validate_lookup(definitions, sync_result.identifier_by_key)
        return QuantityUnitSyncResult(
            identifier_by_normalized_name=lookup,
            created=sync_result.created,
        )

    @staticmethod
    def _validate_lookup(
        definitions: list[QuantityUnitDefinition],
        lookup: dict[str, int],
    ) -> dict[str, int]:
        normalized_lookup: dict[str, int] = {}
        for definition in definitions:
            key = definition.normalized_name()
            if key not in lookup:
                raise ValueError(f"Quantity unit '{definition.name}' is missing after synchronization")
            normalized_lookup[key] = lookup[key]
        return normalized_lookup


def _existing_unit_key(item: GrocyQuantityUnit) -> str:
    """Normalize quantity unit names returned by Grocy."""
    return item.name.strip().lower()
