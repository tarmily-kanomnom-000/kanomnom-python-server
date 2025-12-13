"""UI helpers for the material purchase runs page."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import flet as ft

from .analysis_service import (
    MaterialPurchaseAnalyticsResult,
    MaterialPurchaseProjection,
    ScheduledSupplyRun,
    SupplyRunAssignment,
)


class MaterialPurchaseRunsUIBuilder:
    """Builds reusable UI sections for the material purchase runs page."""

    def __init__(self) -> None:
        self._max_table_rows = 300

    def create_summary_section(self, analytics: MaterialPurchaseAnalyticsResult) -> ft.Container:
        total_materials = len(analytics.projections)
        generated = analytics.generated_at.strftime("%Y-%m-%d %H:%M")
        next_run_text = "-"
        if analytics.cadence_schedule:
            next_run = analytics.cadence_schedule[0]
            next_run_text = self._format_purchase_summary(next_run.assignments)

        cards = ft.Row(
            controls=[
                self._metric_card("Total Materials", f"{total_materials}", ft.Colors.PRIMARY),
                self._metric_card("Cadence", f"Every {analytics.run_interval_days}d", ft.Colors.INDIGO),
                self._metric_card("Next Run Buy", next_run_text, ft.Colors.DEEP_ORANGE),
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
            days_remaining = self._format_days(projection.days_until_runout)
            days_text = f"Days left: {days_remaining}" if days_remaining else ""
            runout_date_text = self._format_date(projection.estimated_runout_date)
            source_value = self._format_source(projection)
            source_text = f"Source: {source_value}" if source_value else ""
            confidence_text = f"Confidence: {self._format_percentage(projection.usage_confidence)}"
            window_text = self._format_supply_window_long(projection)
            unit_value = self._format_unit(projection)
            unit_text = f"Unit: {unit_value}" if unit_value else ""
            runout_text = f"Runout: {runout_date_text}" if runout_date_text != "-" else ""
            subtitle_parts = [
                part for part in [unit_text, days_text, window_text, runout_text, source_text, confidence_text] if part
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

    def create_cadence_schedule_section(
        self,
        schedule: Iterable[ScheduledSupplyRun],
        *,
        interval_days: int,
        low_supply: set[str],
    ) -> ft.Container:
        schedule_list = list(schedule)
        if not schedule_list:
            return self._panel(
                title="Cadence Supply Schedule",
                controls=[
                    ft.Text("No materials require ordering within the configured horizon.", color=ft.Colors.GREEN)
                ],
            )

        tiles: list[ft.Control] = []
        for run in schedule_list:
            header = ft.Text(
                f"{run.label} • {run.scheduled_date.strftime('%Y-%m-%d')}",
                weight=ft.FontWeight.BOLD,
                size=14,
            )
            summary = self._format_purchase_summary(run.assignments, prefix=f"{len(run.assignments)} materials")
            subtitle = ft.Text(summary, size=12, color=ft.Colors.GREY)

            rows: list[ft.DataRow] = []

            def _assignment_sort_key(item: SupplyRunAssignment) -> tuple[int, float, str]:
                safe = item.lower_days_available
                safe_value = safe if safe is not None else float("inf")
                priority = 0
                if item.projection.material in low_supply:
                    priority = -2
                elif item.violates_cadence:
                    priority = -1
                elif item.is_unreliable:
                    priority = 0
                else:
                    priority = 1
                return priority, safe_value, item.projection.material.lower()

            for assignment in sorted(run.assignments, key=_assignment_sort_key):
                projection = assignment.projection
                on_hand_text = self._format_quantity(assignment.projected_units_on_run_date, projection.unit)
                purchase_text = self._format_quantity(assignment.recommended_purchase_units, projection.unit)
                cost_text = self._format_currency(assignment.recommended_purchase_cost)
                safe_text = self._format_days(assignment.lower_days_available) or "-"
                buffer_text = self._format_days(assignment.buffer_days) or "-"
                confidence_text = self._format_percentage(projection.usage_confidence)
                icon_name, color, status_text = self._assignment_status_details(assignment, interval_days)
                if projection.material in low_supply:
                    icon_name = ft.Icons.WARNING_AMBER_ROUNDED
                    color = ft.Colors.AMBER
                    status_text = f"Low supply ({status_text})"
                source_text = self._format_source(projection) or "-"

                status_cell = ft.Row(
                    controls=[ft.Icon(icon_name, color=color, size=18), ft.Text(status_text)],
                    spacing=6,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )

                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(projection.material)),
                            ft.DataCell(ft.Text(self._format_unit(projection) or "-")),
                            ft.DataCell(ft.Text(source_text)),
                            ft.DataCell(ft.Text(on_hand_text)),
                            ft.DataCell(ft.Text(purchase_text)),
                            ft.DataCell(ft.Text(cost_text)),
                            ft.DataCell(ft.Text(safe_text)),
                            ft.DataCell(ft.Text(buffer_text)),
                            ft.DataCell(ft.Text(confidence_text)),
                            ft.DataCell(status_cell),
                        ]
                    )
                )

            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Material")),
                    ft.DataColumn(ft.Text("Unit")),
                    ft.DataColumn(ft.Text("Best Source")),
                    ft.DataColumn(ft.Text("On Hand")),
                    ft.DataColumn(ft.Text("Buy")),
                    ft.DataColumn(ft.Text("Cost")),
                    ft.DataColumn(ft.Text("Safe Window")),
                    ft.DataColumn(ft.Text("Buffer")),
                    ft.DataColumn(ft.Text("Confidence")),
                    ft.DataColumn(ft.Text("Status")),
                ],
                rows=rows,
                column_spacing=12,
                heading_row_color=ft.Colors.BLUE_GREY_100,
                divider_thickness=0.0,
            )

            tiles.append(
                ft.ExpansionTile(
                    title=ft.Column([header, subtitle], spacing=2),
                    controls=[table],
                    initially_expanded=False,
                )
            )

        return self._panel(title="Cadence Supply Schedule", controls=tiles)

    def create_cadence_warning_section(
        self,
        warnings: Iterable[SupplyRunAssignment],
        *,
        interval_days: int,
        schedule: Iterable[ScheduledSupplyRun] | None = None,
    ) -> ft.Container:
        warning_list = list(warnings)
        if not warning_list:
            return self._panel(
                title="Cadence Exceptions",
                controls=[ft.Text(f"All materials fit the {interval_days} day cadence.", color=ft.Colors.GREEN)],
            )

        schedule_lookup: dict[int, tuple[str, str | None]] = {}
        if schedule is not None:
            for run, assignment in self._flatten_schedule(schedule):
                key = id(assignment)
                schedule_lookup[key] = (run.label, run.scheduled_date.strftime("%Y-%m-%d"))

        columns = [
            ft.DataColumn(ft.Text("Run")),
            ft.DataColumn(ft.Text("Date")),
            ft.DataColumn(ft.Text("Material")),
            ft.DataColumn(ft.Text("Unit")),
            ft.DataColumn(ft.Text("Issue")),
            ft.DataColumn(ft.Text("Buy")),
            ft.DataColumn(ft.Text("Cost")),
            ft.DataColumn(ft.Text("Confidence")),
        ]

        rows: list[ft.DataRow] = []
        for assignment in sorted(warning_list, key=lambda item: item.projection.material.lower()):
            projection = assignment.projection
            run_label, run_date = schedule_lookup.get(
                id(assignment), (f"Run @ {assignment.run_offset_days:.0f}d", None)
            )
            reason = self._format_assignment_warning(assignment, interval_days)
            purchase_text = self._format_quantity(assignment.recommended_purchase_units, projection.unit)
            cost_text = self._format_currency(assignment.recommended_purchase_cost)
            confidence_text = self._format_percentage(projection.usage_confidence)

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(run_label)),
                        ft.DataCell(ft.Text(run_date if run_date else "-")),
                        ft.DataCell(ft.Text(projection.material)),
                        ft.DataCell(ft.Text(self._format_unit(projection) or "-")),
                        ft.DataCell(ft.Text(reason)),
                        ft.DataCell(ft.Text(purchase_text)),
                        ft.DataCell(ft.Text(cost_text)),
                        ft.DataCell(ft.Text(confidence_text)),
                    ]
                )
            )

        table = ft.DataTable(
            columns=columns,
            rows=rows,
            column_spacing=12,
            heading_row_color=ft.Colors.BLUE_GREY_100,
            divider_thickness=0.0,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Cadence Exceptions", size=16, weight=ft.FontWeight.BOLD),
                    table,
                ],
                spacing=8,
            ),
            padding=16,
            bgcolor=ft.Colors.WHITE,
            border_radius=8,
        )

    def create_projection_table(self, projections: Iterable[MaterialPurchaseProjection]) -> ft.Container:
        projection_list = list(projections)
        if not projection_list:
            return self._panel(
                title="Material Projections",
                controls=[ft.Text("No data available for the selected time range.", color=ft.Colors.RED)],
            )

        table_rows: list[ft.DataRow] = []
        for projection in projection_list[: self._max_table_rows]:
            unit_label = self._format_unit(projection) or "-"
            row_cells = [
                ft.DataCell(ft.Text(projection.material)),
                ft.DataCell(ft.Text(unit_label)),
                ft.DataCell(ft.Text(self._format_source(projection) or "-")),
                ft.DataCell(ft.Text(self._format_unit_cost(projection.best_unit_cost))),
                ft.DataCell(ft.Text(self._format_usage_per_day(projection, projection.unit))),
                ft.DataCell(ft.Text(self._format_days(projection.purchase_frequency_days) or "-")),
                ft.DataCell(ft.Text(self._format_days(projection.days_until_runout) or "-")),
                ft.DataCell(ft.Text(self._format_supply_window_short(projection) or "-")),
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
                ft.DataColumn(ft.Text("Remaining Range")),
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
        formatted = f"{value:,.{precision}f}"
        if precision > 0:
            formatted = formatted.rstrip("0").rstrip(".")
        return f"{formatted}{suffix}" if suffix else formatted

    def _format_currency(self, value: float | None) -> str:
        if value is None:
            return "-"
        magnitude = abs(value)
        precision = 4 if magnitude < 1 else 2
        formatted = f"${value:,.{precision}f}"
        formatted = formatted.rstrip("0").rstrip(".")
        return formatted

    def _format_unit_cost(self, value: float | None) -> str:
        if value is None:
            return "-"
        formatted = f"${value:,.4f}"
        formatted = formatted.rstrip("0").rstrip(".")
        return formatted

    def _format_usage_per_day(self, projection: MaterialPurchaseProjection, unit_label: str) -> str:
        usage = projection.usage_per_day
        if usage is None:
            return "-"
        quantity = self._format_quantity(usage, unit_label, precision=2)
        return f"{quantity}/d" if quantity else "-"

    def _format_days(self, value: float | None) -> str | None:
        if value is None:
            return None
        return self._format_number(value, 1, "d")

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d")

    def _format_source(self, projection: MaterialPurchaseProjection) -> str | None:
        if projection.best_source and projection.best_unit_cost is not None:
            return f"{projection.best_source} ({self._format_unit_cost(projection.best_unit_cost)}/unit)"
        if projection.best_source:
            return projection.best_source
        return None

    def _format_percentage(self, value: float) -> str:
        return f"{value * 100:.0f}%" if value > 0 else "<20%"

    def _format_unit(self, projection: MaterialPurchaseProjection) -> str | None:
        if projection.unit:
            return projection.unit
        return None

    def _assignment_status_details(
        self,
        assignment: SupplyRunAssignment,
        interval_days: int,
    ) -> tuple[str, str, str]:
        if assignment.violates_cadence:
            return (
                ft.Icons.ERROR_OUTLINE,
                ft.Colors.RED,
                f"Needs <{interval_days}d cadence",
            )
        if assignment.is_unreliable:
            return (
                ft.Icons.HELP_OUTLINE,
                ft.Colors.AMBER,
                "Usage uncertain",
            )
        return (
            ft.Icons.CHECK_CIRCLE_OUTLINE,
            ft.Colors.GREEN,
            "On cadence",
        )

    def _format_assignment_warning(self, assignment: SupplyRunAssignment, interval_days: int) -> str:
        parts: list[str] = []
        if assignment.violates_cadence:
            safe_text = self._format_days(assignment.lower_days_available) or "?"
            parts.append(f"Safe window {safe_text} < {interval_days}d cadence")
        if assignment.is_unreliable:
            confidence = assignment.projection.usage_confidence
            parts.append(f"Confidence {confidence * 100:.0f}%")
        if not parts:
            return "Included for tracking"
        return " • ".join(parts)

    def _supply_window_bounds(self, projection: MaterialPurchaseProjection) -> tuple[float, float, int] | None:
        window = projection.remaining_supply_window
        if window is None:
            return None
        if window.lower_days is None or window.upper_days is None:
            return None
        confidence = int(round(window.confidence * 100))
        return window.lower_days, window.upper_days, confidence

    def _format_supply_window_long(self, projection: MaterialPurchaseProjection) -> str | None:
        bounds = self._supply_window_bounds(projection)
        if bounds is None:
            return None
        lower, upper, confidence = bounds
        lower_text = self._format_number(lower, 1, None)
        upper_text = self._format_number(upper, 1, None)
        return f"{confidence}% range: {lower_text}–{upper_text} d"

    def _format_supply_window_short(self, projection: MaterialPurchaseProjection) -> str | None:
        bounds = self._supply_window_bounds(projection)
        if bounds is None:
            return None
        lower, upper, confidence = bounds
        lower_text = self._format_number(lower, 1, None)
        upper_text = self._format_number(upper, 1, None)
        return f"{lower_text}–{upper_text}d ({confidence}%)"

    def _format_quantity(
        self,
        value: float | None,
        unit_label: str | None,
        *,
        precision: int = 1,
    ) -> str:
        if value is None:
            return "-"
        number = self._format_number(value, precision, None)
        unit = unit_label or "units"
        return f"{number} {unit}"

    def _format_purchase_summary(
        self,
        assignments: Iterable[SupplyRunAssignment],
        *,
        prefix: str | None = None,
    ) -> str:
        count = 0
        total_cost = 0.0
        cost_found = False
        for assignment in assignments:
            units = assignment.recommended_purchase_units
            if units is not None and units > 0:
                count += 1
            cost = assignment.recommended_purchase_cost
            if cost is not None:
                total_cost += cost
                cost_found = True

        parts: list[str] = []
        if prefix:
            parts.append(prefix)
        if count > 0:
            parts.append(f"{count} purchase{'s' if count != 1 else ''}")
        if cost_found:
            parts.append(self._format_currency(total_cost))
        return " • ".join(parts) if parts else "-"

    def _flatten_schedule(
        self,
        schedule: Iterable[ScheduledSupplyRun],
    ) -> list[tuple[ScheduledSupplyRun, SupplyRunAssignment]]:
        flattened: list[tuple[ScheduledSupplyRun, SupplyRunAssignment]] = []
        for run in schedule:
            for assignment in run.assignments:
                flattened.append((run, assignment))
        return flattened
