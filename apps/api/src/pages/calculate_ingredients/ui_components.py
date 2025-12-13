"""
UI component creation for the ingredients calculator page.
Handles ingredient tables, intermediate servings display, and copy sections.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Final

import flet as ft

from shared.models import Recipe
from shared.ui.layout import default_layout_config, styled_container

from .constants import BUTTON_SPACING, EXCLUDED_RECIPE_KEYWORD, TEXT_FIELD_WIDTH

RawIngredients = dict[str, tuple[float, str]]
IntermediateServings = dict[str, float]
ExistingAmounts = dict[str, dict[str, float]]
RemainingServings = dict[str, float]

_HEADER_TITLES: Final[tuple[str, ...]] = ("Ingredient", "Amount", "Unit")


class IngredientUIBuilder:
    """Builds UI components for the ingredients calculator."""

    def create_recipe_input_rows(
        self,
        product_recipes: Sequence[Recipe],
        on_quantity_change: Callable[[str, str], None],
    ) -> list[ft.Row]:
        """Create input rows for each product recipe."""

        return [
            ft.Row(
                controls=[
                    ft.Text(recipe.name, width=200, size=14),
                    ft.TextField(
                        value="0",
                        width=TEXT_FIELD_WIDTH,
                        text_align=ft.TextAlign.RIGHT,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        on_change=lambda event, name=recipe.name: on_quantity_change(name, event.control.value or "0"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            for recipe in product_recipes
        ]

    def create_action_buttons(
        self,
        on_update: Callable[[ft.ControlEvent], None],
        on_clear: Callable[[ft.ControlEvent], None],
    ) -> ft.Row:
        """Create the action buttons for updating and clearing."""

        return ft.Row(
            controls=[
                ft.ElevatedButton(
                    "🔄 Update Ingredients",
                    on_click=on_update,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.WHITE),
                ),
                ft.ElevatedButton(
                    "🗑️ Clear All",
                    on_click=on_clear,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.WHITE),
                ),
            ],
            spacing=BUTTON_SPACING,
        )

    def create_styled_container(self, content: ft.Control) -> ft.Container:
        """Create a styled container for content using shared layout config."""

        return styled_container(content, default_layout_config())

    def create_ingredients_table(self, raw_ingredients: RawIngredients) -> ft.Column:
        """Create the ingredients table with headers and data."""

        ingredient_rows: list[ft.Control] = [self._create_table_header()]
        ingredient_rows.append(ft.Divider())

        for ingredient, (amount, unit) in self._sort_ingredients(raw_ingredients):
            ingredient_rows.append(
                ft.Row(
                    [
                        ft.Text(ingredient, expand=True, selectable=True),
                        ft.Text(f"{amount:.2f}", width=80, text_align=ft.TextAlign.RIGHT, selectable=True),
                        ft.Text(unit, width=60, selectable=True),
                    ]
                )
            )

        return ft.Column(ingredient_rows)

    def create_ingredients_copy_section(self, raw_ingredients: RawIngredients) -> ft.ExpansionTile:
        """Create the copy-friendly ingredients section."""

        lines = ["Ingredient\tAmount\tUnit"]
        for ingredient, (amount, unit) in self._sort_ingredients(raw_ingredients):
            lines.append(f"{ingredient}\t{amount:.2f}\t{unit}")

        return ft.ExpansionTile(
            title=ft.Text("📋 Copy All Ingredients"),
            controls=[self._create_copy_text_field(lines, min_lines=5, max_lines=15)],
            initially_expanded=False,
        )

    def create_intermediate_recipe_controls(
        self,
        intermediate_servings: IntermediateServings,
        existing_amounts: ExistingAmounts,
        remaining_servings: RemainingServings,
        on_weight_change: Callable[[str, str], None],
        on_servings_change: Callable[[str, str], None],
    ) -> list[ft.Container]:
        """Create controls for each intermediate recipe."""

        controls: list[ft.Container] = []
        for recipe_name, total_servings in self._sort_by_servings(intermediate_servings):
            if self._should_skip_recipe(recipe_name):
                continue

            remaining = remaining_servings.get(recipe_name, total_servings)
            controls.append(
                self._create_single_intermediate_control(
                    recipe_name,
                    total_servings,
                    remaining,
                    existing_amounts,
                    on_weight_change,
                    on_servings_change,
                )
            )

        return controls

    def create_recalculate_button(self, on_recalculate: Callable[[ft.ControlEvent], None]) -> ft.ElevatedButton:
        """Create the recalculate button."""

        return ft.ElevatedButton(
            "🔄 Update Remaining Ingredients",
            on_click=on_recalculate,
            style=ft.ButtonStyle(bgcolor=ft.Colors.SECONDARY, color=ft.Colors.WHITE),
        )

    def create_servings_copy_section(
        self,
        intermediate_servings: IntermediateServings,
        remaining_servings: RemainingServings,
    ) -> ft.ExpansionTile:
        """Create copy-friendly section for intermediate recipes."""

        lines = ["Recipe\tTotal Needed\tRemaining Needed"]
        for recipe_name, servings in self._sort_by_servings(intermediate_servings):
            if self._should_skip_recipe(recipe_name):
                continue

            remaining = remaining_servings.get(recipe_name, servings)
            lines.append(f"{recipe_name}\t{servings:.4f}\t{max(0.0, remaining):.4f}")

        return ft.ExpansionTile(
            title=ft.Text("📋 Copy All Intermediate Recipes"),
            controls=[self._create_copy_text_field(lines, min_lines=3, max_lines=8)],
            initially_expanded=False,
        )

    def _create_table_header(self) -> ft.Row:
        """Create the table header row."""

        return ft.Row(
            [
                ft.Text(_HEADER_TITLES[0], weight=ft.FontWeight.BOLD, expand=True, selectable=True),
                ft.Text(
                    _HEADER_TITLES[1],
                    weight=ft.FontWeight.BOLD,
                    width=80,
                    text_align=ft.TextAlign.RIGHT,
                    selectable=True,
                ),
                ft.Text(_HEADER_TITLES[2], weight=ft.FontWeight.BOLD, width=60, selectable=True),
            ]
        )

    def _create_copy_text_field(self, lines: Iterable[str], *, min_lines: int, max_lines: int) -> ft.Container:
        """Return a styled, read-only text field for copyable content."""

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

    def _create_single_intermediate_control(
        self,
        recipe_name: str,
        total_servings: float,
        remaining: float,
        existing_amounts: ExistingAmounts,
        on_weight_change: Callable[[str, str], None],
        on_servings_change: Callable[[str, str], None],
    ) -> ft.Container:
        """Create control for a single intermediate recipe."""

        existing = existing_amounts.get(recipe_name, {"weight": 0.0, "servings": 0.0})

        return ft.Container(
            content=ft.Column(
                [
                    self._create_recipe_header(recipe_name, total_servings),
                    self._create_existing_amounts_row(
                        recipe_name,
                        remaining,
                        existing,
                        on_weight_change,
                        on_servings_change,
                    ),
                ]
            ),
            bgcolor=ft.Colors.GREY_100,
            padding=8,
            border_radius=8,
        )

    def _create_recipe_header(self, recipe_name: str, total_servings: float) -> ft.Row:
        """Create header row for recipe with name and total needed."""

        return ft.Row(
            [
                ft.Text(recipe_name, size=16, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(f"Total needed: {total_servings:.4f} servings", size=14),
            ]
        )

    def _create_existing_amounts_row(
        self,
        recipe_name: str,
        remaining: float,
        existing: dict[str, float],
        on_weight_change: Callable[[str, str], None],
        on_servings_change: Callable[[str, str], None],
    ) -> ft.Row:
        """Create row for existing amounts input."""

        return ft.Row(
            [
                ft.Text("I already have:", size=14, width=120),
                ft.TextField(
                    label="Weight (g)",
                    value=str(existing.get("weight", 0.0)),
                    width=TEXT_FIELD_WIDTH,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda event, name=recipe_name: on_weight_change(name, event.control.value or "0"),
                ),
                ft.Text("OR", size=12, width=30),
                ft.TextField(
                    label="Servings",
                    value=str(existing.get("servings", 0.0)),
                    width=TEXT_FIELD_WIDTH,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda event, name=recipe_name: on_servings_change(name, event.control.value or "0"),
                ),
                ft.Text(
                    f"→ Still need: {max(0.0, remaining):.4f} servings",
                    size=14,
                    color=ft.Colors.PRIMARY,
                    expand=True,
                ),
            ]
        )

    def _sort_ingredients(self, raw_ingredients: RawIngredients) -> list[tuple[str, tuple[float, str]]]:
        """Return ingredients sorted by amount descending."""

        return sorted(raw_ingredients.items(), key=lambda item: item[1][0], reverse=True)

    def _sort_by_servings(self, servings: IntermediateServings) -> list[tuple[str, float]]:
        """Return servings sorted by value descending."""

        return sorted(servings.items(), key=lambda item: item[1], reverse=True)

    def _should_skip_recipe(self, recipe_name: str) -> bool:
        """Check if recipe should be skipped (e.g., chiffon recipes)."""

        return EXCLUDED_RECIPE_KEYWORD in recipe_name.lower()
