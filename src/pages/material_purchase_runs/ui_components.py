"""UI helpers for the material purchase runs page."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import flet as ft

from .analysis_service import MaterialPurchaseAnalyticsResult, MaterialPurchaseProjection, SupplyRunGroup


class MaterialPurchaseRunsUIBuilder:
    """Builds reusable UI sections for the material purchase runs page."""

    def __init__(self) -> None:
        self._max_table_rows = 300

    def create_summary_section(self, analytics: MaterialPurchaseAnalyticsResult) -> ft.Container:
        total_materials = len(analytics.projections)
        low_supply = len(analytics.low_supply)
        supply_groups = len(analytics.supply_run_groups)
        generated = analytics.generated_at.strftime("%Y-%m-%d %H:%M")

        cards = ft.Row(
            controls=[
                self._metric_card("Total Materials", f"{total_materials}", ft.Colors.PRIMARY),
                self._metric_card("Low Supply (≤7d)", f"{low_supply}", ft.Colors.AMBER),
                self._metric_card("Upcoming Supply Runs", f"{supply_groups}", ft.Colors.TEAL),
            ],
            spacing=16,
            run_spacing=16,
            wrap=True,
        )

        generated_label = ft.Text(f"Last refreshed: {generated}", size=12, color=ft.Colors.GREY)

        return ft.Container(
            content=ft.Column([cards, generated_label], spacing=8),
            padding=16,
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=8,
        )

    def create_low_supply_section(self, materials: Iterable[MaterialPurchaseProjection]) -> ft.Container:
        material_list = list(materials)
        if not material_list:
            return self._panel(
                title="Materials Running Low",
                controls=[ft.Text("All materials look healthy for the next week.", color=ft.Colors.GREEN)],
            )

        tiles: list[ft.Control] = []
        for projection in material_list:
            days_text = self._format_number(projection.days_until_runout, 1, " days")
            runout_date_text = self._format_date(projection.estimated_runout_date)
            source_text = self._format_source(projection)
            confidence_text = self._format_percentage(projection.usage_confidence)
            unit_value = self._format_unit(projection)
            unit_text = f"Unit: {unit_value}" if unit_value else ""
            subtitle_parts = [
                part for part in [unit_text, days_text, runout_date_text, source_text, confidence_text] if part
            ]
            subtitle = " • ".join(subtitle_parts)
            tiles.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER, size=28),
                    title=ft.Text(projection.material, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(subtitle),
                )
            )

        return self._panel(title="Materials Running Low", controls=tiles)

    def create_supply_run_groups_section(self, groups: Iterable[SupplyRunGroup]) -> ft.Container:
        group_list = list(groups)
        if not group_list:
            return self._panel(
                title="Suggested Supply Runs",
                controls=[ft.Text("No upcoming supply runs in the next horizon.", color=ft.Colors.BLUE_GREY)],
            )

        tiles: list[ft.Control] = []
        for group in group_list:
            header = ft.Text(group.label, weight=ft.FontWeight.BOLD, size=14)
            subtitle = ft.Text(f"{len(group.materials)} materials", size=12, color=ft.Colors.GREY)

            material_rows = []
            for projection in sorted(
                group.materials,
                key=lambda item: item.days_until_runout if item.days_until_runout is not None else 999.0,
            ):
                days_text = self._format_number(projection.days_until_runout, 1, "d")
                confidence_text = self._format_percentage(projection.usage_confidence)
                material_rows.append(
                    ft.Row(
                        controls=[
                            ft.Text(projection.material, expand=2),
                            ft.Text(self._format_unit(projection) or "-", width=80),
                            ft.Text(days_text or "?", width=60),
                            ft.Text(self._format_source(projection) or "", expand=2),
                            ft.Text(confidence_text, width=70, text_align=ft.TextAlign.RIGHT),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                )

            tiles.append(
                ft.ExpansionTile(
                    title=ft.Row([header, subtitle], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    controls=material_rows,
                    initially_expanded=False,
                )
            )

        return self._panel(title="Suggested Supply Runs", controls=tiles)

    def create_projection_table(self, projections: Iterable[MaterialPurchaseProjection]) -> ft.Container:
        projection_list = list(projections)
        if not projection_list:
            return self._panel(
                title="Material Projections",
                controls=[ft.Text("No data available for the selected time range.", color=ft.Colors.RED)],
            )

        table_rows: list[ft.DataRow] = []
        for projection in projection_list[: self._max_table_rows]:
            row_cells = [
                ft.DataCell(ft.Text(projection.material)),
                ft.DataCell(ft.Text(self._format_unit(projection) or "-")),
                ft.DataCell(ft.Text(self._format_source(projection) or "-")),
                ft.DataCell(ft.Text(self._format_currency(projection.best_unit_cost))),
                ft.DataCell(ft.Text(self._format_number(projection.usage_per_day, 2, None))),
                ft.DataCell(ft.Text(self._format_number(projection.purchase_frequency_days, 1, None))),
                ft.DataCell(ft.Text(self._format_number(projection.days_until_runout, 1, None))),
                ft.DataCell(ft.Text(self._format_date(projection.estimated_runout_date))),
                ft.DataCell(ft.Text(self._format_date(projection.last_purchase_date))),
                ft.DataCell(ft.Text(str(projection.total_purchases))),
                ft.DataCell(ft.Text(self._format_percentage(projection.usage_confidence))),
            ]
            table_rows.append(ft.DataRow(cells=row_cells))

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Material")),
                ft.DataColumn(ft.Text("Unit")),
                ft.DataColumn(ft.Text("Best Source")),
                ft.DataColumn(ft.Text("Unit Cost")),
                ft.DataColumn(ft.Text("Usage / Day")),
                ft.DataColumn(ft.Text("Freq. (days)")),
                ft.DataColumn(ft.Text("Days Left")),
                ft.DataColumn(ft.Text("Runout Date")),
                ft.DataColumn(ft.Text("Last Purchase")),
                ft.DataColumn(ft.Text("Purchases")),
                ft.DataColumn(ft.Text("Confidence")),
            ],
            rows=table_rows,
            column_spacing=18,
            heading_row_color=ft.Colors.BLUE_GREY_100,
            divider_thickness=0.0,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Material Projections", size=16, weight=ft.FontWeight.BOLD),
                    table,
                    ft.Text(
                        f"Showing {min(len(projection_list), self._max_table_rows)} of {len(projection_list)} materials",
                        size=12,
                        color=ft.Colors.GREY,
                    ),
                ],
                spacing=8,
            ),
            padding=16,
            bgcolor=ft.Colors.WHITE,
            border_radius=8,
            expand=True,
        )

    def _metric_card(self, label: str, value: str, color: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(label, size=12, color=ft.Colors.GREY),
                ],
                spacing=4,
            ),
            padding=16,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            width=200,
        )

    def _panel(self, title: str, controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [ft.Text(title, size=16, weight=ft.FontWeight.BOLD)] + controls,
                spacing=8,
            ),
            padding=16,
            bgcolor=ft.Colors.WHITE,
            border_radius=8,
        )

    def _format_number(self, value: float | None, precision: int, suffix: str | None) -> str:
        if value is None:
            return ""
        formatted = f"{value:.{precision}f}"
        return f"{formatted}{suffix}" if suffix else formatted

    def _format_currency(self, value: float | None) -> str:
        if value is None:
            return "-"
        return f"${value:.4f}"

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d")

    def _format_source(self, projection: MaterialPurchaseProjection) -> str | None:
        if projection.best_source and projection.best_unit_cost is not None:
            return f"{projection.best_source} (${projection.best_unit_cost:.4f}/unit)"
        if projection.best_source:
            return projection.best_source
        return None

    def _format_percentage(self, value: float) -> str:
        return f"{value * 100:.0f}%" if value > 0 else "<20%"

    def _format_unit(self, projection: MaterialPurchaseProjection) -> str | None:
        if projection.unit:
            return projection.unit
        return None
