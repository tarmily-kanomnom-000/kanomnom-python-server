from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Sequence, TypeVar

DefinitionT = TypeVar("DefinitionT")
ExistingT = TypeVar("ExistingT")


@dataclass
class CreatedEntity(Generic[DefinitionT]):
    """Record of a manifest item created in Grocy."""

    definition: DefinitionT
    identifier: int
    payload: dict[str, Any]


@dataclass
class EntitySyncResult(Generic[DefinitionT]):
    """Output of synchronizing manifest entities with a Grocy instance."""

    identifier_by_key: dict[str, int]
    created: list[CreatedEntity[DefinitionT]]


@dataclass
class EntitySyncSpecification(Generic[DefinitionT, ExistingT]):
    """Configuration required to reconcile manifests with Grocy objects."""

    manifest_items: Sequence[DefinitionT]
    existing_items: Sequence[ExistingT]
    manifest_key: Callable[[DefinitionT], str]
    existing_key: Callable[[ExistingT], str]
    payload_builder: Callable[[DefinitionT, int], dict[str, Any]]
    creator: Callable[[dict[str, Any]], dict[str, Any] | list[dict[str, Any]] | None]


class EntitySyncer(Generic[DefinitionT]):
    """Generic sync loop: fetch existing data, create missing objects, and track ids."""

    def synchronize(
        self,
        specification: EntitySyncSpecification[DefinitionT, ExistingT],
    ) -> EntitySyncResult[DefinitionT]:
        lookup = {specification.existing_key(item): _get_identifier(item) for item in specification.existing_items}
        created: list[CreatedEntity[DefinitionT]] = []
        next_identifier = _max_identifier(specification.existing_items)
        for manifest_item in specification.manifest_items:
            key = specification.manifest_key(manifest_item)
            if key in lookup:
                continue
            next_identifier += 1
            payload = specification.payload_builder(manifest_item, next_identifier)
            response = specification.creator(payload)
            created_identifier = _extract_identifier(response) or next_identifier
            lookup[key] = created_identifier
            created.append(
                CreatedEntity(
                    definition=manifest_item,
                    identifier=created_identifier,
                    payload=payload,
                )
            )
            next_identifier = max(next_identifier, created_identifier)
        return EntitySyncResult(identifier_by_key=lookup, created=created)


def _max_identifier(items: Sequence[ExistingT]) -> int:
    """Return the maximum numeric id exposed by Grocy objects."""
    if not items:
        return 0
    identifiers = [_get_identifier(item) for item in items]
    return max(identifiers)


def _extract_identifier(payload: dict[str, Any] | list[dict[str, Any]] | None) -> int | None:
    """Extract an id from Grocy's response payload when it returns one."""
    if not payload:
        return None
    if isinstance(payload, dict) and "id" in payload:
        return int(payload["id"])
    if isinstance(payload, list):
        identifiers = [
            int(item["id"]) for item in payload if isinstance(item, dict) and "id" in item and str(item["id"]).isdigit()
        ]
        if identifiers:
            return identifiers[0]
    return None


def _get_identifier(item: ExistingT) -> int:
    if isinstance(item, dict):
        return int(item.get("id", 0))
    if hasattr(item, "id"):
        identifier = getattr(item, "id")
        try:
            return int(identifier)
        except (TypeError, ValueError):
            return 0
    return 0
