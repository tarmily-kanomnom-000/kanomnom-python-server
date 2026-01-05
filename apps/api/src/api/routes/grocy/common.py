from __future__ import annotations

from typing import Callable, TypeVar

import requests
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from core.cache.grocy_shopping_locations_cache import get_grocy_shopping_locations_cache
from core.grocy.exceptions import MetadataNotFoundError
from core.grocy.price_analyzer import PriceAnalyzer

from .dependencies import governor

T = TypeVar("T")


def with_grocy_manager(instance_index: str, op: Callable[[object], T]) -> T:
    try:
        manager = governor.manager_for(instance_index)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        return op(manager)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except requests.HTTPError as error:  # pragma: no cover - passthrough to HTTP
        status_code = error.response.status_code if error.response else 502
        detail = error.response.text.strip() if error.response else str(error)
        raise HTTPException(status_code=status_code, detail=detail or str(error)) from error


def parse_force_refresh(request: Request) -> bool:
    value = request.query_params.get("force_refresh")
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "t", "yes", "y", "on"}


def build_price_analyzer(instance_index: str) -> PriceAnalyzer:
    try:
        manager = governor.manager_for(instance_index)
        return PriceAnalyzer(manager.client)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to initialize price analyzer: {exc!s}") from exc


async def load_shopping_locations(instance_index: str) -> list:
    try:
        shopping_locations_cache = get_grocy_shopping_locations_cache()
        return await run_in_threadpool(shopping_locations_cache.load_shopping_locations, instance_index)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load shopping locations: {exc!s}") from exc


async def get_manager(instance_index: str) -> object:
    try:
        return await run_in_threadpool(governor.manager_for, instance_index)
    except MetadataNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load manager: {exc!s}") from exc
