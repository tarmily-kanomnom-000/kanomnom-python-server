from __future__ import annotations

import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Mapping, Sequence

logger = logging.getLogger(__name__)

NOTE_PREFIX = "kanomnom::"
NOTE_VERSION = 1

_KIND_REGISTRY: dict[str, type["BaseNoteMetadata"]] = {}


def _register_metadata(kind: str, cls: type["BaseNoteMetadata"]) -> None:
    if kind in _KIND_REGISTRY:
        raise ValueError(
            f"Metadata kind '{kind}' is already registered by {_KIND_REGISTRY[kind].__name__}"
        )
    _KIND_REGISTRY[kind] = cls


def _is_valid_character(value: str) -> bool:
    if value == "\n":
        return True
    return value.isprintable()


def _normalize_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return None
    if not normalized.isascii():
        raise ValueError(f"{field_name} must contain ASCII characters only.")
    if not all(_is_valid_character(char) for char in normalized):
        raise ValueError(f"{field_name} contains unsupported control characters.")
    return normalized


def _normalize_required_text(value: Any, field_name: str) -> str:
    normalized = _normalize_optional_text(value, field_name)
    if normalized is None:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _normalize_optional_number(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        value = trimmed
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a numeric value.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be a finite value.")
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return number


def _normalize_optional_positive_number(value: Any, field_name: str) -> float | None:
    normalized = _normalize_optional_number(value, field_name)
    if normalized is None:
        return None
    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return normalized


def _normalize_required_positive_number(value: Any, field_name: str) -> float:
    normalized = _normalize_optional_positive_number(value, field_name)
    if normalized is None:
        raise ValueError(f"{field_name} must be greater than 0.")
    return normalized


def _normalize_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean value.")


def _normalize_optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    return _normalize_bool(value, field_name)


def _normalize_string_sequence(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        candidates: Sequence[Any] = [value]
    elif isinstance(value, Sequence):
        candidates = value
    else:
        raise ValueError(f"{field_name} must be a list of strings.")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(candidates):
        token = _normalize_required_text(entry, f"{field_name}[{index}]")
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(token)
    return tuple(normalized)


class InventoryLossReason(str, Enum):
    SPOILAGE = "spoilage"
    BREAKAGE = "breakage"
    OVERPORTION = "overportion"
    THEFT = "theft"
    QUALITY_REJECT = "quality_reject"
    PROCESS_ERROR = "process_error"
    OTHER = "other"


@dataclass(frozen=True)
class LossDetail:
    reason: InventoryLossReason
    note: str | None = None


def _normalize_loss_details(value: Any) -> tuple[LossDetail, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        candidates: Sequence[Any] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates = value
    else:
        raise ValueError("losses must be a list of objects with reason/note.")

    normalized: list[LossDetail] = []
    seen: set[InventoryLossReason] = set()
    for entry in candidates:
        if not isinstance(entry, Mapping):
            raise ValueError("Each loss entry must be an object with reason/note.")
        reason_raw = entry.get("reason")
        if isinstance(reason_raw, InventoryLossReason):
            reason = reason_raw
        elif isinstance(reason_raw, str):
            trimmed = reason_raw.strip().lower()
            if not trimmed:
                continue
            try:
                reason = InventoryLossReason(trimmed)
            except ValueError as exc:
                allowed = ", ".join(reason.value for reason in InventoryLossReason)
                raise ValueError(f"loss reason must be one of: {allowed}.") from exc
        else:
            raise ValueError("Loss reason must be a string or enum value.")
        note_value = entry.get("note")
        note = (
            note_value.strip()
            if isinstance(note_value, str) and note_value.strip()
            else None
        )
        if reason in seen:
            continue
        seen.add(reason)
        normalized.append(LossDetail(reason=reason, note=note))
    return tuple(normalized)


class BaseNoteMetadata(ABC):
    """Typed metadata embedded inside Grocy note payloads."""

    kind: ClassVar[str]

    @abstractmethod
    def to_attrs(self) -> dict[str, Any]:
        """Serialize the metadata into the structured attrs payload."""

    @classmethod
    @abstractmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "BaseNoteMetadata":
        """Hydrate the metadata from the attrs payload."""

    def to_api_payload(self) -> dict[str, Any]:
        """Return a JSON-serializable representation exposed via the public API."""
        return self.to_attrs().copy()


@dataclass(frozen=True)
class PurchaseEntryNoteMetadata(BaseNoteMetadata):
    """Structured metadata used for Grocy purchase entries."""

    kind: ClassVar[str] = "purchase_entry"

    shipping_cost: float | None = None
    tax_rate: float | None = None
    brand: str | None = None
    package_size: float | None = None
    package_price: float | None = None
    package_quantity: float | None = None
    currency: str | None = None
    conversion_rate: float | None = None
    on_sale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "shipping_cost",
            _normalize_optional_number(self.shipping_cost, "shipping_cost"),
        )
        object.__setattr__(
            self, "tax_rate", _normalize_optional_number(self.tax_rate, "tax_rate")
        )
        object.__setattr__(self, "brand", _normalize_optional_text(self.brand, "brand"))
        object.__setattr__(
            self,
            "package_size",
            _normalize_optional_positive_number(self.package_size, "package_size"),
        )
        object.__setattr__(
            self,
            "package_price",
            _normalize_optional_number(self.package_price, "package_price"),
        )
        object.__setattr__(
            self,
            "package_quantity",
            _normalize_optional_positive_number(
                self.package_quantity, "package_quantity"
            ),
        )
        object.__setattr__(
            self, "currency", _normalize_optional_text(self.currency, "currency")
        )
        object.__setattr__(
            self,
            "conversion_rate",
            _normalize_optional_positive_number(
                self.conversion_rate, "conversion_rate"
            ),
        )
        object.__setattr__(
            self,
            "on_sale",
            _normalize_optional_bool(self.on_sale, "on_sale") or False,
        )

    def to_attrs(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.shipping_cost is not None:
            attrs["shipping_cost"] = self.shipping_cost
        if self.tax_rate is not None:
            attrs["tax_rate"] = self.tax_rate
        if self.brand is not None:
            attrs["brand"] = self.brand
        if self.package_size is not None:
            attrs["package_size"] = self.package_size
        if self.package_price is not None:
            attrs["package_price"] = self.package_price
        if self.package_quantity is not None:
            attrs["package_quantity"] = self.package_quantity
        if self.currency is not None:
            attrs["currency"] = self.currency
        if self.conversion_rate is not None:
            attrs["conversion_rate"] = self.conversion_rate
        attrs["on_sale"] = self.on_sale
        if not attrs:
            return {}
        attrs["kind"] = self.kind
        return attrs

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "PurchaseEntryNoteMetadata":
        return cls(
            shipping_cost=_normalize_optional_number(
                attrs.get("shipping_cost"), "shipping_cost"
            ),
            tax_rate=_normalize_optional_number(attrs.get("tax_rate"), "tax_rate"),
            brand=_normalize_optional_text(attrs.get("brand"), "brand"),
            package_size=_normalize_optional_positive_number(
                attrs.get("package_size"), "package_size"
            ),
            package_price=_normalize_optional_number(
                attrs.get("package_price"), "package_price"
            ),
            package_quantity=_normalize_optional_positive_number(
                attrs.get("package_quantity"), "package_quantity"
            ),
            currency=_normalize_optional_text(attrs.get("currency"), "currency"),
            conversion_rate=_normalize_optional_positive_number(
                attrs.get("conversion_rate"), "conversion_rate"
            ),
            on_sale=_normalize_optional_bool(attrs.get("on_sale"), "on_sale") or False,
        )


_register_metadata(PurchaseEntryNoteMetadata.kind, PurchaseEntryNoteMetadata)


@dataclass(frozen=True)
class ProductUnitConversion:
    """Represents a custom unit conversion for a product."""

    from_unit: str
    to_unit: str
    factor: float
    tare: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "from_unit", _normalize_required_text(self.from_unit, "from_unit")
        )
        object.__setattr__(
            self, "to_unit", _normalize_required_text(self.to_unit, "to_unit")
        )
        object.__setattr__(
            self, "factor", _normalize_required_positive_number(self.factor, "factor")
        )
        object.__setattr__(self, "tare", _normalize_optional_number(self.tare, "tare"))

    def to_attrs(self) -> dict[str, Any]:
        payload = {
            "from_unit": self.from_unit,
            "to_unit": self.to_unit,
            "factor": self.factor,
        }
        if self.tare is not None:
            payload["tare"] = self.tare
        return payload

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "ProductUnitConversion":
        if not isinstance(attrs, Mapping):
            raise ValueError(
                "Unit conversions must be objects with from_unit, to_unit, and factor fields."
            )
        return cls(
            from_unit=_normalize_required_text(attrs.get("from_unit"), "from_unit"),
            to_unit=_normalize_required_text(attrs.get("to_unit"), "to_unit"),
            factor=_normalize_required_positive_number(attrs.get("factor"), "factor"),
            tare=_normalize_optional_number(attrs.get("tare"), "tare"),
        )


def _normalize_unit_conversions(value: Any) -> tuple[ProductUnitConversion, ...]:
    if value is None:
        return ()
    if isinstance(value, ProductUnitConversion):
        return (value,)
    if isinstance(value, Mapping):
        candidates: Sequence[Any] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        candidates = value
    else:
        raise ValueError("unit_conversions must be a list of conversion definitions.")
    normalized: list[ProductUnitConversion] = []
    for entry in candidates:
        if isinstance(entry, ProductUnitConversion):
            normalized.append(entry)
        elif isinstance(entry, Mapping):
            normalized.append(ProductUnitConversion.from_attrs(entry))
        else:
            raise ValueError(
                "Each conversion entry must be an object with from_unit, to_unit, and factor."
            )
    return tuple(normalized)


@dataclass(frozen=True)
class ProductDescriptionMetadata(BaseNoteMetadata):
    """Structured metadata stored inside Grocy product descriptions."""

    kind: ClassVar[str] = "product_description"

    unit_conversions: tuple[ProductUnitConversion, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "unit_conversions", _normalize_unit_conversions(self.unit_conversions)
        )

    def to_attrs(self) -> dict[str, Any]:
        if not self.unit_conversions:
            return {}
        return {
            "kind": self.kind,
            "unit_conversions": [
                conversion.to_attrs() for conversion in self.unit_conversions
            ],
        }

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "ProductDescriptionMetadata":
        return cls(
            unit_conversions=_normalize_unit_conversions(attrs.get("unit_conversions"))
        )


_register_metadata(ProductDescriptionMetadata.kind, ProductDescriptionMetadata)


def normalize_product_description_metadata(
    metadata: ProductDescriptionMetadata,
    unit_name_lookup: Mapping[str, str],
) -> ProductDescriptionMetadata:
    if not metadata.unit_conversions:
        return metadata
    if not unit_name_lookup:
        raise ValueError(
            "Unable to validate unit conversions because Grocy quantity units are unavailable."
        )
    seen_pairs: set[tuple[str, str]] = set()
    sanitized: list[ProductUnitConversion] = []
    for conversion in metadata.unit_conversions:
        from_key = _normalize_unit_name(conversion.from_unit)
        to_key = _normalize_unit_name(conversion.to_unit)
        if not from_key or not to_key:
            raise ValueError(
                "Unit conversions must include from_unit and to_unit names."
            )
        if from_key not in unit_name_lookup:
            raise ValueError(f"Unknown Grocy quantity unit '{conversion.from_unit}'.")
        if to_key not in unit_name_lookup:
            raise ValueError(f"Unknown Grocy quantity unit '{conversion.to_unit}'.")
        pair_key = tuple(sorted((from_key, to_key)))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        sanitized.append(
            ProductUnitConversion(
                from_unit=unit_name_lookup[from_key],
                to_unit=unit_name_lookup[to_key],
                factor=conversion.factor,
                tare=conversion.tare,
            )
        )
    return ProductDescriptionMetadata(unit_conversions=tuple(sanitized))


def resolve_unit_conversion_factors(
    conversions: Sequence[ProductUnitConversion],
    requests: Sequence[tuple[str, str]],
) -> dict[tuple[str, str], float | None]:
    normalized_requests = [
        (_normalize_unit_name(req[0]), _normalize_unit_name(req[1])) for req in requests
    ]
    if not normalized_requests:
        return {}
    graph: dict[str, list[tuple[str, float]]] = {}
    for conversion in conversions:
        from_key = _normalize_unit_name(conversion.from_unit)
        to_key = _normalize_unit_name(conversion.to_unit)
        if not from_key or not to_key:
            continue
        if conversion.factor <= 0:
            continue
        graph.setdefault(from_key, []).append((to_key, conversion.factor))
        graph.setdefault(to_key, []).append((from_key, 1 / conversion.factor))
    results: dict[tuple[str, str], float | None] = {}
    for raw_request, (from_key, to_key) in zip(
        requests, normalized_requests, strict=True
    ):
        if not from_key or not to_key:
            results[raw_request] = None
            continue
        if from_key == to_key:
            results[raw_request] = 1.0
            continue
        results[raw_request] = _resolve_conversion_factor(graph, from_key, to_key)
    return results


def _normalize_unit_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def _resolve_conversion_factor(
    graph: Mapping[str, Sequence[tuple[str, float]]],
    source: str,
    target: str,
) -> float | None:
    queue: list[tuple[str, float]] = [(source, 1.0)]
    visited: set[str] = {source}
    while queue:
        current, factor = queue.pop(0)
        for neighbor, edge_factor in graph.get(current, ()):
            if neighbor in visited:
                continue
            next_factor = factor * edge_factor
            if neighbor == target:
                return next_factor
            visited.add(neighbor)
            queue.append((neighbor, next_factor))
    return None


@dataclass(frozen=True)
class QuantityUnitDescriptionMetadata(BaseNoteMetadata):
    """Structured metadata stored inside Grocy quantity unit descriptions."""

    kind: ClassVar[str] = "quantity_unit"

    is_discrete: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "is_discrete",
            _normalize_optional_bool(self.is_discrete, "is_discrete"),
        )

    def to_attrs(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.is_discrete is not None:
            attrs["is_discrete"] = self.is_discrete
        if not attrs:
            return {}
        attrs["kind"] = self.kind
        return attrs

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "QuantityUnitDescriptionMetadata":
        return cls(
            is_discrete=_normalize_optional_bool(
                attrs.get("is_discrete"), "is_discrete"
            )
        )


_register_metadata(
    QuantityUnitDescriptionMetadata.kind, QuantityUnitDescriptionMetadata
)


@dataclass(frozen=True)
class ProductGroupDescriptionMetadata(BaseNoteMetadata):
    """Structured metadata stored inside Grocy product group descriptions."""

    kind: ClassVar[str] = "product_group"

    allergens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "allergens", _normalize_string_sequence(self.allergens, "allergens")
        )

    def to_attrs(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.allergens:
            attrs["allergens"] = list(self.allergens)
        if not attrs:
            return {}
        attrs["kind"] = self.kind
        return attrs

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "ProductGroupDescriptionMetadata":
        return cls(
            allergens=_normalize_string_sequence(attrs.get("allergens"), "allergens")
        )


_register_metadata(
    ProductGroupDescriptionMetadata.kind, ProductGroupDescriptionMetadata
)


@dataclass(frozen=True)
class InventoryCorrectionNoteMetadata(BaseNoteMetadata):
    """Metadata describing any inventory loss captured during a correction."""

    kind: ClassVar[str] = "inventory_correction"

    losses: tuple[LossDetail, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "losses", _normalize_loss_details(self.losses))

    def to_attrs(self) -> dict[str, Any]:
        if not self.losses:
            return {}
        return {
            "kind": self.kind,
            "losses": [
                {"reason": loss.reason.value, "note": loss.note} for loss in self.losses
            ],
        }

    @classmethod
    def from_attrs(cls, attrs: Mapping[str, Any]) -> "InventoryCorrectionNoteMetadata":
        return cls(
            losses=_normalize_loss_details(attrs.get("losses")),
        )


_register_metadata(
    InventoryCorrectionNoteMetadata.kind, InventoryCorrectionNoteMetadata
)


@dataclass(frozen=True)
class DecodedGrocyNote:
    """Represents a Grocy note split into human text and structured metadata."""

    note: str
    metadata: BaseNoteMetadata | None


def encode_structured_note(
    note: str | None,
    metadata: BaseNoteMetadata | None = None,
) -> str | None:
    """Encode a Grocy note with optional metadata, returning None if empty."""
    plain_text = note or ""
    if not plain_text.strip():
        plain_text = ""
    else:
        normalized = _normalize_optional_text(plain_text, "note")
        plain_text = normalized or ""
    attrs = metadata.to_attrs() if metadata else {}
    if not plain_text and not attrs:
        return None
    payload = {"v": NOTE_VERSION, "note": plain_text, "attrs": attrs}
    return f"{NOTE_PREFIX}{json.dumps(payload, separators=(',', ':'))}"


def validate_note_text(note: str | None) -> None:
    """Ensure the provided note text adheres to the supported character set."""
    if note is None:
        return
    _normalize_optional_text(note, "note")


def decode_structured_note(raw: str | None) -> DecodedGrocyNote:
    """Decode a Grocy note string into human text and typed metadata."""
    if raw is None:
        return DecodedGrocyNote(note="", metadata=None)
    if not raw.startswith(NOTE_PREFIX):
        cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
        return DecodedGrocyNote(note=cleaned, metadata=None)
    payload_raw = raw[len(NOTE_PREFIX) :]
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        logger.warning("Failed to decode structured Grocy note; returning raw text.")
        return DecodedGrocyNote(note=raw, metadata=None)

    version = payload.get("v")
    if version != NOTE_VERSION:
        logger.warning(
            "Encountered unsupported note version %s; returning plain text.", version
        )

    note_text = payload.get("note")
    if not isinstance(note_text, str):
        note_text = ""
    attrs_raw = payload.get("attrs")
    attrs: dict[str, Any] = attrs_raw if isinstance(attrs_raw, dict) else {}
    metadata = _instantiate_metadata(attrs)
    cleaned_note = note_text.replace("\r\n", "\n").replace("\r", "\n")
    return DecodedGrocyNote(note=cleaned_note, metadata=metadata)


def _instantiate_metadata(attrs: Mapping[str, Any]) -> BaseNoteMetadata | None:
    kind = attrs.get("kind")
    if not isinstance(kind, str):
        return None
    metadata_cls = _KIND_REGISTRY.get(kind)
    if metadata_cls is None:
        logger.warning("No metadata handler registered for kind '%s'.", kind)
        return None
    try:
        return metadata_cls.from_attrs(attrs)
    except ValueError as exc:
        logger.warning("Failed to parse metadata for kind '%s': %s", kind, exc)
        return None
