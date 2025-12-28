from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from core.grocy.client import GrocyClient
from core.grocy.models import ProductGroupDefinition, QuantityUnitDefinition
from core.grocy.note_metadata import (
    ProductGroupDescriptionMetadata,
    QuantityUnitDescriptionMetadata,
    decode_structured_note,
)
from core.grocy.responses import GrocyProductGroup, GrocyQuantityUnit
from core.grocy.sync import CreatedEntity, EntitySyncer, EntitySyncSpecification


class _NamedDefinition(Protocol):
    name: str

    def normalized_name(self) -> str: ...


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
        existing_lookup = {_existing_unit_key(unit): unit for unit in existing_units}
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
        for definition in definitions:
            existing = existing_lookup.get(definition.normalized_name())
            if existing is None:
                continue
            identifier = lookup.get(definition.normalized_name())
            if identifier is None:
                continue
            desired_note, desired_is_discrete = _extract_unit_metadata(definition.description)
            current_note = _normalized_description(existing.description)
            if desired_note == current_note and desired_is_discrete == existing.is_discrete:
                continue
            payload = definition.to_payload(identifier)
            payload["description"] = definition.description
            self.client.update_quantity_unit(identifier, payload)
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
        existing_lookup = {_existing_product_group_key(group): group for group in existing_groups}
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
        for definition in definitions:
            existing = existing_lookup.get(definition.normalized_name())
            if existing is None:
                continue
            identifier = lookup.get(definition.normalized_name())
            if identifier is None:
                continue
            desired_note, desired_allergens = _extract_group_metadata(definition.description)
            current_note = _normalized_description(existing.description)
            current_allergens = getattr(existing, "allergens", ())
            if desired_note == current_note and desired_allergens == tuple(current_allergens or ()):
                continue
            payload = definition.to_payload(identifier)
            payload["description"] = definition.description
            self.client.update_product_group(identifier, payload)
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


def _normalized_description(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _extract_unit_metadata(description: str | None) -> tuple[str | None, bool | None]:
    if description is None:
        return (None, None)
    decoded = decode_structured_note(description)
    note = _normalized_description(decoded.note)
    metadata = decoded.metadata
    if isinstance(metadata, QuantityUnitDescriptionMetadata):
        return (note, metadata.is_discrete)
    return (note, None)


def _extract_group_metadata(description: str | None) -> tuple[str | None, tuple[str, ...]]:
    if description is None:
        return (None, ())
    decoded = decode_structured_note(description)
    note = _normalized_description(decoded.note)
    metadata = decoded.metadata
    if isinstance(metadata, ProductGroupDescriptionMetadata):
        return (note, metadata.allergens)
    return (note, ())
