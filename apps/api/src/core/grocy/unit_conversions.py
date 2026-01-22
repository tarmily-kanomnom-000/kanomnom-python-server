from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class QuantityUnitConversionDefinition:
    from_qu_name: str
    to_qu_name: str
    factor: float
    product_id: int | None

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "QuantityUnitConversionDefinition":
        return QuantityUnitConversionDefinition(
            from_qu_name=_require_unit_name(raw.get("from_qu_name"), "from_qu_name"),
            to_qu_name=_require_unit_name(raw.get("to_qu_name"), "to_qu_name"),
            factor=_require_positive_float(raw.get("factor"), "factor"),
            product_id=_optional_int(raw.get("product_id"), "product_id"),
        )


def load_quantity_unit_conversions(path: Path) -> list[QuantityUnitConversionDefinition]:
    if not path.exists():
        raise FileNotFoundError(f"Missing quantity unit conversion manifest: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [QuantityUnitConversionDefinition.from_dict(dict(entry)) for entry in data]


def build_conversion_graph(
    conversions: Sequence[QuantityUnitConversionDefinition],
    unit_name_lookup: Mapping[str, str],
) -> dict[str, list[tuple[str, float]]]:
    graph: dict[str, list[tuple[str, float]]] = {}
    missing_units: set[str] = set()
    for conversion in conversions:
        if conversion.product_id is not None:
            continue
        from_key = _normalize_unit_name(conversion.from_qu_name)
        to_key = _normalize_unit_name(conversion.to_qu_name)
        if not from_key or not to_key:
            raise ValueError("Quantity unit conversions must include from_qu_name and to_qu_name.")
        if from_key not in unit_name_lookup:
            missing_units.add(conversion.from_qu_name)
            continue
        if to_key not in unit_name_lookup:
            missing_units.add(conversion.to_qu_name)
            continue
        if conversion.factor <= 0:
            continue
        graph.setdefault(from_key, []).append((to_key, conversion.factor))
        graph.setdefault(to_key, []).append((from_key, 1 / conversion.factor))
    if missing_units:
        missing_list = ", ".join(sorted(missing_units))
        raise ValueError(f"Unknown quantity unit names in conversions manifest: {missing_list}.")
    return graph


def build_full_conversion_map(
    graph: Mapping[str, Sequence[tuple[str, float]]],
) -> dict[tuple[str, str], float]:
    results: dict[tuple[str, str], float] = {}
    for source in graph.keys():
        if source not in graph:
            continue
        visited: set[str] = {source}
        queue: list[tuple[str, float]] = [(source, 1.0)]
        while queue:
            current, factor = queue.pop(0)
            for neighbor, edge_factor in graph.get(current, ()):
                if neighbor in visited:
                    continue
                next_factor = factor * edge_factor
                results[(source, neighbor)] = next_factor
                visited.add(neighbor)
                queue.append((neighbor, next_factor))
    return results


def _require_unit_name(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field} is required.")
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field} must be a non-empty string.")
    return cleaned


def _optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc


def _require_positive_float(value: Any, field: str) -> float:
    if value is None:
        raise ValueError(f"{field} is required.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive.")
    return number


def _normalize_unit_name(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()
