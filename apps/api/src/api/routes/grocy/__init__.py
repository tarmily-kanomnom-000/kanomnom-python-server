from __future__ import annotations

from .dependencies import router

# Import route modules to register endpoints with the shared router.
from . import instances as _instances  # noqa: F401
from . import inventory as _inventory  # noqa: F401
from . import lifecycle as _lifecycle  # noqa: F401
from . import products as _products  # noqa: F401
from . import purchases as _purchases  # noqa: F401

# Planned endpoints now live in docs/grocy/planned_routes.md.

__all__ = ["router"]
