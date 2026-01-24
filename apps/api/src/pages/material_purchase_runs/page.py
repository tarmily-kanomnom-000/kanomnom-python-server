"""Material purchase runs analysis page."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

import flet as ft
from flet.core.control_event import ControlEvent
from shared.grist_service import DataFilterManager

from .analysis_service import (
    AdaptiveUsageConfig,
    MaterialPurchaseAnalyticsService,
    SupplyRunConfig,
)
from .state_manager import MaterialPurchaseRunsState
from .ui_components import MaterialPurchaseRunsUIBuilder

logger = logging.getLogger(__name__)


class MaterialPurchaseRunsContent(ft.Container):
    """Container that renders the material purchase run analytics."""

    def __init__(self, page: ft.Page | None) -> None:
        super().__init__()
        self.page = page
        self.state = MaterialPurchaseRunsState()
        self.data_manager = DataFilterManager()
        usage_config = AdaptiveUsageConfig()
        self.run_config = SupplyRunConfig()
        self.analytics_service = MaterialPurchaseAnalyticsService(
            usage_config, self.run_config
        )
        self.ui_builder = MaterialPurchaseRunsUIBuilder()

        self.loading_indicator: ft.ProgressRing | None = None
        self.summary_section = ft.Column([])
        self.cadence_schedule_section = ft.Column([])
        self.table_section = ft.Column([])
        self.date_filter_container: ft.Container | None = None
        self.start_date_field: ft.TextField | None = None
        self.end_date_field: ft.TextField | None = None
        self.min_purchases_field: ft.TextField | None = None
        self.run_interval_field: ft.TextField | None = None
        self.min_purchase_threshold: int = 6
        self.run_interval_days: int = self.run_config.target_run_interval_days

    def build_content(self) -> "MaterialPurchaseRunsContent":
        logger.info("Initializing Material Purchase Runs page")
        self._setup_ui()
        self._refresh_analytics(reload_data=True)
        return self

    def update(self) -> None:
        if self.page:
            self.page.update()

    def _setup_ui(self) -> None:
        header = ft.Text("Material Purchase Runs", size=28, weight=ft.FontWeight.BOLD)
        self.loading_indicator = ft.ProgressRing(visible=True)
        header_row = ft.Row(
            controls=[header, ft.Container(expand=True), self.loading_indicator],
            alignment=ft.MainAxisAlignment.START,
        )

        self.date_filter_container = self._create_date_filter_section()

        self.summary_section.controls = [
            ft.Text("Loading analytics...", color=ft.Colors.GREY)
        ]
        self.cadence_schedule_section.controls = [
            ft.Text("Waiting for schedule...", color=ft.Colors.GREY)
        ]
        self.table_section.controls = []

        main_column = ft.Column(
            controls=[
                header_row,
                self.date_filter_container,
                self.summary_section,
                self.cadence_schedule_section,
                self.table_section,
            ],
            spacing=20,
            expand=True,
        )

        self.content = ft.Container(content=main_column, padding=20, expand=True)

    def _create_date_filter_section(self) -> ft.Container:
        start_value = self._format_date_input(self.data_manager.start_date)
        end_value = self._format_date_input(self.data_manager.end_date)

        self.start_date_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=start_value,
            width=200,
            on_change=self.on_start_date_change,
        )
        self.end_date_field = ft.TextField(
            label="End Date (YYYY-MM-DD)",
            value=end_value,
            width=200,
            on_change=self.on_end_date_change,
        )

        self.min_purchases_field = ft.TextField(
            label="Min Purchases",
            value=str(self.min_purchase_threshold),
            width=140,
            on_change=self.on_min_purchases_change,
        )

        self.run_interval_field = ft.TextField(
            label="Run Cadence (days)",
            value=str(self.run_interval_days),
            width=160,
            on_change=self.on_run_interval_change,
        )

        apply_button = ft.ElevatedButton(
            "Apply Filter", on_click=self.apply_date_filter
        )

        return ft.Container(
            content=ft.Row(
                controls=[
                    self.start_date_field,
                    self.end_date_field,
                    self.min_purchases_field,
                    self.run_interval_field,
                    apply_button,
                ],
                spacing=16,
            ),
            padding=16,
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=8,
        )

    def _with_loading(self, operation: Callable[[], None]) -> None:
        if self.loading_indicator:
            self.loading_indicator.visible = True
            self.update()

        try:
            operation()
        finally:
            if self.loading_indicator:
                self.loading_indicator.visible = False
            self.update()

    def _refresh_analytics(self, *, reload_data: bool) -> None:
        action_label = "load data" if reload_data else "apply filter"
        error_message = (
            "Failed to load data from Grist"
            if reload_data
            else "Failed to apply filter"
        )

        def _execute() -> None:
            try:
                if reload_data:
                    logger.info("Loading material purchases from Grist")
                    self.data_manager.load_grist_data()
                else:
                    logger.info("Re-applying data filter for material purchase runs")
                    self.data_manager.apply_time_filter()

                filtered = self.data_manager.get_filtered_data()
                analytics = self.analytics_service.analyze(
                    filtered, self.min_purchase_threshold
                )
                self.state.set_analytics(analytics)
                self._render_analytics()
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to %s for material purchase analytics", action_label
                )
                self.state.set_error(error_message)
                self._render_error()

        self._with_loading(_execute)

    def on_start_date_change(self, event: ControlEvent) -> None:
        value = event.control.value or ""
        try:
            self.data_manager.start_date = (
                datetime.strptime(value, "%Y-%m-%d") if value else None
            )
        except ValueError:
            logger.warning("Invalid start date: %s", value)
            self.data_manager.start_date = None

    def on_end_date_change(self, event: ControlEvent) -> None:
        value = event.control.value or ""
        try:
            self.data_manager.end_date = (
                datetime.strptime(value, "%Y-%m-%d") if value else None
            )
        except ValueError:
            logger.warning("Invalid end date: %s", value)
            self.data_manager.end_date = None

    def on_min_purchases_change(self, event: ControlEvent) -> None:
        value = event.control.value or ""
        try:
            parsed_value = int(value)
        except ValueError:
            logger.warning("Invalid minimum purchase count: %s", value)
            parsed_value = 1

        self.min_purchase_threshold = parsed_value if parsed_value >= 1 else 1

        if self.min_purchases_field and self.min_purchases_field.value != str(
            self.min_purchase_threshold
        ):
            self.min_purchases_field.value = str(self.min_purchase_threshold)
            self.update()

    def on_run_interval_change(self, event: ControlEvent) -> None:
        value = event.control.value or ""
        try:
            parsed_value = int(value)
        except ValueError:
            logger.warning("Invalid run cadence: %s", value)
            parsed_value = self.run_interval_days

        self.run_interval_days = parsed_value if parsed_value >= 1 else 1
        self.run_config.target_run_interval_days = self.run_interval_days

        if self.run_interval_field and self.run_interval_field.value != str(
            self.run_interval_days
        ):
            self.run_interval_field.value = str(self.run_interval_days)
            self.update()

    def apply_date_filter(self, _event: ControlEvent) -> None:
        logger.info("Applying date filter for material purchase runs")
        self._refresh_analytics(reload_data=False)

    def _render_analytics(self) -> None:
        analytics = self.state.analytics
        if analytics is None:
            self._render_error()
            return

        self.summary_section.controls = [
            self.ui_builder.create_summary_section(analytics)
        ]
        self.cadence_schedule_section.controls = [
            self.ui_builder.create_cadence_schedule_section(
                analytics.cadence_schedule,
                interval_days=analytics.run_interval_days,
                low_supply={projection.material for projection in analytics.low_supply},
            )
        ]
        self.table_section.controls = [
            self.ui_builder.create_projection_table(analytics.projections)
        ]

    def _render_error(self) -> None:
        if self.state.error_message:
            error_text = ft.Text(self.state.error_message, color=ft.Colors.RED)
            self.summary_section.controls = [error_text]
            self.cadence_schedule_section.controls = []
            self.table_section.controls = []

    def _format_date_input(self, value: datetime | None) -> str:
        if value is None:
            return ""
        return value.strftime("%Y-%m-%d")
