"""State management for the material purchase runs page."""

from __future__ import annotations

from dataclasses import dataclass

from .analysis_service import MaterialPurchaseAnalyticsResult


@dataclass(slots=True)
class MaterialPurchaseRunsState:
    """Stores analytics results and error state for the page."""

    analytics: MaterialPurchaseAnalyticsResult | None = None
    error_message: str | None = None

    def set_analytics(self, analytics: MaterialPurchaseAnalyticsResult) -> None:
        self.analytics = analytics
        self.error_message = None

    def set_error(self, message: str) -> None:
        self.error_message = message
        self.analytics = None
