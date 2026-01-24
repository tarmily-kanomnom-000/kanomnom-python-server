"""UI components for the product costs calculator."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Optional

import flet as ft
from flet.core.control_event import ControlEvent
from shared.ui.layout import default_layout_config, styled_container

from .constants import (
    BUTTON_SPACING,
    COST_DISPLAY_PRECISION,
    DATE_FIELD_WIDTH,
    INGREDIENT_DISPLAY_PRECISION,
)

SortedIngredient = tuple[str, float, str, Optional[float], Optional[float], dict]


class UIComponentBuilder:
    """Builds UI components for the product costs calculator."""

    def __init__(self, cost_calculator, material_cost_basis: dict) -> None:
        self.cost_calculator = cost_calculator
        self.material_cost_basis = material_cost_basis

    def create_styled_container(self, content: ft.Control) -> ft.Container:
        """Create a styled container for content."""

        return styled_container(content, default_layout_config())

    def create_date_range_section(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        on_start_change: Callable[[ControlEvent], None],
        on_end_change: Callable[[ControlEvent], None],
        on_apply_filter: Callable[[ControlEvent], None],
    ) -> ft.Container:
        """Create the date range input section."""

        start_default = start_date.strftime("%Y-%m-%d") if start_date else ""
        end_default = end_date.strftime("%Y-%m-%d") if end_date else ""

        start_date_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=start_default,
            width=DATE_FIELD_WIDTH,
            on_change=on_start_change,
        )

        end_date_field = ft.TextField(
            label="End Date (YYYY-MM-DD)",
            value=end_default,
            width=DATE_FIELD_WIDTH,
            on_change=on_end_change,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("📅 Time Range Filter", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            start_date_field,
                            end_date_field,
                            ft.ElevatedButton(
                                "Apply Filter",
                                on_click=on_apply_filter,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.SECONDARY, color=ft.Colors.WHITE
                                ),
                            ),
                        ],
                        spacing=BUTTON_SPACING,
                    ),
                ]
            ),
            padding=10,
            margin=ft.margin.only(bottom=20),
            bgcolor=ft.Colors.BLUE_GREY_100,
            border_radius=5,
        )

    def create_ingredient_breakdown(
        self,
        recipe_name: str,
        ingredients: dict,
        selected_date: Optional[datetime],
        cost_basis: dict,
    ) -> ft.Container:
        """Create ingredient breakdown efficiently by reusing cached semantic matches."""

        if not cost_basis:
            return ft.Container(
                content=ft.Text(
                    "No cost data available for selected time point",
                    color=ft.Colors.RED,
                ),
                padding=10,
            )

        sorted_ingredients, total_cost = (
            self.cost_calculator.calculate_ingredient_costs(ingredients, cost_basis)
        )
        ingredients_table = self._create_ingredients_table(sorted_ingredients)
        title_text = self._create_breakdown_title(recipe_name, selected_date)

        key_suffix = selected_date.strftime("%Y%m") if selected_date else "current"

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        title_text,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PRIMARY,
                    ),
                    ft.Container(height=5),
                    ft.Container(
                        content=ingredients_table,
                        border=ft.border.all(1, ft.Colors.GREY),
                        border_radius=5,
                        padding=10,
                        bgcolor=ft.Colors.WHITE,
                    ),
                    self.create_ingredient_copy_section(
                        recipe_name, sorted_ingredients, total_cost
                    ),
                ]
            ),
            margin=ft.margin.only(top=10),
            key=f"ingredient_breakdown_{recipe_name}_{key_suffix}",
        )

    def create_ingredient_copy_section(
        self,
        recipe_name: str,
        sorted_ingredients: list[SortedIngredient],
        total_cost: float,
    ) -> ft.ExpansionTile:
        """Create copy-friendly section without calling semantic matching again."""

        lines = [
            f"Ingredients for 1 × {recipe_name}:\n",
            "Ingredient\tAmount\tUnit\tCost Basis\tIngredient Cost",
        ]

        for (
            ingredient,
            amount,
            unit,
            cost_per_unit,
            ingredient_cost,
            _,
        ) in sorted_ingredients:
            cost_basis_text = self._format_cost_basis(cost_per_unit, unit)
            ingredient_cost_text = self._format_money(ingredient_cost)
            lines.append(
                f"{ingredient}\t{amount:.{INGREDIENT_DISPLAY_PRECISION}f}\t{unit}\t{cost_basis_text}\t{ingredient_cost_text}"
            )

        lines.append(f"\nTOTAL COST: ${total_cost:.{COST_DISPLAY_PRECISION}f}")

        return ft.ExpansionTile(
            title=ft.Text("📋 Copy Ingredient Breakdown"),
            controls=[self._create_copy_text_field(lines, min_lines=6, max_lines=18)],
            initially_expanded=False,
        )

    def _create_ingredients_table(
        self, sorted_ingredients: list[SortedIngredient]
    ) -> ft.Column:
        """Create the ingredients table with header and data rows."""

        ingredient_rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(
                        "Ingredient",
                        weight=ft.FontWeight.BOLD,
                        expand=True,
                        selectable=True,
                    ),
                    ft.Text(
                        "Amount",
                        weight=ft.FontWeight.BOLD,
                        width=80,
                        text_align=ft.TextAlign.RIGHT,
                        selectable=True,
                    ),
                    ft.Text(
                        "Unit", weight=ft.FontWeight.BOLD, width=60, selectable=True
                    ),
                    ft.Text(
                        "Cost Basis",
                        weight=ft.FontWeight.BOLD,
                        width=100,
                        text_align=ft.TextAlign.RIGHT,
                        selectable=True,
                    ),
                    ft.Text(
                        "Ingredient Cost",
                        weight=ft.FontWeight.BOLD,
                        width=120,
                        text_align=ft.TextAlign.RIGHT,
                        selectable=True,
                    ),
                ]
            ),
            ft.Divider(),
        ]

        total_cost = 0.0
        for (
            ingredient,
            amount,
            unit,
            cost_per_unit,
            ingredient_cost,
            _,
        ) in sorted_ingredients:
            (
                cost_basis_text,
                ingredient_cost_text,
                cost_basis_color,
                ingredient_cost_color,
            ) = self._format_cost_data(cost_per_unit, ingredient_cost, unit)

            ingredient_rows.append(
                ft.Row(
                    [
                        ft.Text(ingredient, expand=True, selectable=True),
                        ft.Text(
                            f"{amount:.{INGREDIENT_DISPLAY_PRECISION}f}",
                            width=80,
                            text_align=ft.TextAlign.RIGHT,
                            selectable=True,
                        ),
                        ft.Text(unit, width=60, selectable=True),
                        ft.Text(
                            cost_basis_text,
                            width=100,
                            text_align=ft.TextAlign.RIGHT,
                            selectable=True,
                            color=cost_basis_color,
                        ),
                        ft.Text(
                            ingredient_cost_text,
                            width=120,
                            text_align=ft.TextAlign.RIGHT,
                            selectable=True,
                            color=ingredient_cost_color,
                        ),
                    ]
                )
            )
            total_cost += ingredient_cost or 0.0

        ingredient_rows.extend(
            [
                ft.Divider(),
                ft.Row(
                    [
                        ft.Text(
                            "TOTAL COST",
                            weight=ft.FontWeight.BOLD,
                            expand=True,
                            selectable=True,
                        ),
                        ft.Text("", width=80),
                        ft.Text("", width=60),
                        ft.Text("", width=100),
                        ft.Text(
                            f"${total_cost:.{COST_DISPLAY_PRECISION}f}",
                            width=120,
                            text_align=ft.TextAlign.RIGHT,
                            selectable=True,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE,
                        ),
                    ]
                ),
            ]
        )

        return ft.Column(ingredient_rows)

    def _format_cost_data(
        self,
        cost_per_unit: Optional[float],
        ingredient_cost: Optional[float],
        unit: str,
    ) -> tuple[str, str, str, str]:
        """Format cost data for display with appropriate colors."""

        if cost_per_unit is not None:
            cost_basis_text = (
                f"${cost_per_unit:.{INGREDIENT_DISPLAY_PRECISION}f}/{unit}"
            )
            ingredient_cost_text = self._format_money(ingredient_cost)
            return (
                cost_basis_text,
                ingredient_cost_text,
                ft.Colors.BLACK,
                ft.Colors.GREEN,
            )

        return "not found", "not found", ft.Colors.RED, ft.Colors.RED

    def _format_cost_basis(self, cost_per_unit: Optional[float], unit: str) -> str:
        """Format cost basis for copy sections."""

        if cost_per_unit is None:
            return "not found"
        return f"${cost_per_unit:.{INGREDIENT_DISPLAY_PRECISION}f}/{unit}"

    def _format_money(self, amount: Optional[float]) -> str:
        """Format a monetary amount for display."""

        if amount is None:
            return "not found"
        return f"${amount:.{INGREDIENT_DISPLAY_PRECISION}f}"

    def _create_breakdown_title(
        self, recipe_name: str, selected_date: Optional[datetime]
    ) -> str:
        """Create title text for ingredient breakdown."""

        if selected_date:
            return f"Ingredients for 1 × {recipe_name} (at {selected_date.strftime('%B %Y')}):"
        return f"Ingredients for 1 × {recipe_name} (Current Prices):"

    def _create_copy_text_field(
        self, lines: Iterable[str], *, min_lines: int, max_lines: int
    ) -> ft.Container:
        """Shared helper for read-only copy text fields."""

        return ft.Container(
            content=ft.TextField(
                value="\n".join(lines),
                multiline=True,
                read_only=True,
                min_lines=min_lines,
                max_lines=max_lines,
                text_size=11,
                border_color=ft.Colors.GREY_400,
                bgcolor=ft.Colors.GREY_50,
            ),
            padding=5,
        )
