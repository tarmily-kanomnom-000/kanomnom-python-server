from __future__ import annotations

# Import route modules to register endpoints with the shared router.
from . import auth as _auth  # noqa: F401
from . import instances as _instances  # noqa: F401
from .dependencies import router

__all__ = ["router"]
