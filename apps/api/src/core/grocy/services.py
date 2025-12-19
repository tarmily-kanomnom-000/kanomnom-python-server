from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from core.grocy.client import GrocyClient
from core.grocy.models import ProductGroupDefinition, QuantityUnitDefinition
from core.grocy.responses import GrocyProductGroup, GrocyQuantityUnit
from core.grocy.sync import CreatedEntity, EntitySyncSpecification, EntitySyncer


class _NamedDefinition(Protocol):
    name: str

    def normalized_name(self) -> str:
        ...


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
        lookup = _normalize_lookup(definitions, sync_result.identifier_by_key, "Quantity unit")
        return QuantityUnitSyncResult(
            identifier_by_normalized_name=lookup,
            created=sync_result.created,
        )


@dataclass
class ProductGroupSyncResult:
    """Result returned after reconciling product groups."""

    identifier_by_normalized_name: dict[str, int]
    created: list[CreatedEntity[ProductGroupDefinition]]


class ProductGroupService:
    """Service encapsulating product group reconciliation logic."""

    def __init__(self, client: GrocyClient, syncer: EntitySyncer[ProductGroupDefinition]) -> None:
        self.client = client
        self.syncer = syncer

    def ensure_product_groups(self, definitions: list[ProductGroupDefinition]) -> ProductGroupSyncResult:
        """Ensure the universal product groups exist and return their Grocy ids keyed by name."""
        existing_groups = self.client.list_product_groups()
        specification = EntitySyncSpecification(
            manifest_items=definitions,
            existing_items=existing_groups,
            manifest_key=lambda definition: definition.normalized_name(),
            existing_key=_existing_product_group_key,
            payload_builder=lambda definition, new_id: definition.to_payload(new_id),
            creator=self.client.create_product_group,
        )
        sync_result = self.syncer.synchronize(specification)
        lookup = _normalize_lookup(definitions, sync_result.identifier_by_key, "Product group")
        return ProductGroupSyncResult(
            identifier_by_normalized_name=lookup,
            created=sync_result.created,
        )


def _existing_unit_key(item: GrocyQuantityUnit) -> str:
    """Normalize quantity unit names returned by Grocy."""
    return item.name.strip().lower()


def _existing_product_group_key(item: GrocyProductGroup) -> str:
    """Normalize product group names returned by Grocy."""
    return item.name.strip().lower()


def _normalize_lookup(
    definitions: Sequence[_NamedDefinition],
    lookup: dict[str, int],
    entity_label: str,
) -> dict[str, int]:
    normalized_lookup: dict[str, int] = {}
    for definition in definitions:
        key = definition.normalized_name()
        if key not in lookup:
            raise ValueError(f"{entity_label} '{definition.name}' is missing after synchronization")
        normalized_lookup[key] = lookup[key]
    return normalized_lookup
