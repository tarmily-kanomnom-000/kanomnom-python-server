"""
UI component creation for the ingredients calculator page.
Handles ingredient tables, intermediate servings display, and copy sections.
"""

import flet as ft

# Import shared constants
from .constants import (
    CONTAINER_PADDING, 
    CONTAINER_BORDER_RADIUS,
    BUTTON_SPACING,
    TEXT_FIELD_WIDTH,
    EXCLUDED_RECIPE_KEYWORD
)


class IngredientUIBuilder:
    """Builds UI components for the ingredients calculator."""
    
    pass
    
    def create_recipe_input_rows(self, product_recipes, on_quantity_change):
        """Create input rows for each product recipe."""
        recipe_rows = []
        for recipe in product_recipes:
            recipe_row = ft.Row(
                controls=[
                    ft.Text(recipe.name, width=200, size=14),
                    ft.TextField(
                        value="0",
                        width=TEXT_FIELD_WIDTH,
                        text_align=ft.TextAlign.RIGHT,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        on_change=lambda e, name=recipe.name: on_quantity_change(name, e.control.value),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            recipe_rows.append(recipe_row)
        return recipe_rows
    
    def create_action_buttons(self, on_update, on_clear):
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
    
    def create_styled_container(self, content):
        """Create a styled container for content."""
        return ft.Container(
            content=content,
            bgcolor=ft.Colors.BLUE_GREY_100,
            padding=CONTAINER_PADDING,
            border_radius=CONTAINER_BORDER_RADIUS,
            expand=1,
        )
    
    def create_ingredients_table(self, raw_ingredients: dict):
        """Create the ingredients table with headers and data."""
        # Create ingredient rows sorted by amount (descending)
        ingredients_list = []
        for ingredient, (amount, unit) in sorted(raw_ingredients.items(), key=lambda x: x[1][0], reverse=True):
            ingredients_list.append(
                ft.Row(
                    [
                        ft.Text(ingredient, expand=True, selectable=True),
                        ft.Text(f"{amount:.2f}", width=80, text_align=ft.TextAlign.RIGHT, selectable=True),
                        ft.Text(unit, width=60, selectable=True),
                    ]
                )
            )
        
        # Create table with header
        return ft.Column(
            [
                self.create_table_header(),
                ft.Divider(),
                *ingredients_list,
            ]
        )
    
    def create_table_header(self):
        """Create the table header row."""
        return ft.Row(
            [
                ft.Text("Ingredient", weight=ft.FontWeight.BOLD, expand=True, selectable=True),
                ft.Text("Amount", weight=ft.FontWeight.BOLD, width=80, text_align=ft.TextAlign.RIGHT, selectable=True),
                ft.Text("Unit", weight=ft.FontWeight.BOLD, width=60, selectable=True),
            ]
        )
    
    def create_ingredients_copy_section(self, raw_ingredients: dict):
        """Create the copy-friendly ingredients section."""
        ingredients_text = "Ingredient\tAmount\tUnit\n" + "\n".join(
            [
                f"{ingredient}\t{amount:.2f}\t{unit}"
                for ingredient, (amount, unit) in sorted(
                    raw_ingredients.items(), key=lambda x: x[1][0], reverse=True
                )
            ]
        )
        
        return ft.ExpansionTile(
            title=ft.Text("📋 Copy All Ingredients"),
            controls=[
                ft.Container(
                    content=ft.TextField(
                        value=ingredients_text,
                        multiline=True,
                        read_only=True,
                        min_lines=5,
                        max_lines=15,
                        text_size=11,
                        border_color=ft.Colors.GREY_400,
                        bgcolor=ft.Colors.GREY_50,
                    ),
                    padding=5,
                )
            ],
            initially_expanded=False,
        )
    
    def create_intermediate_recipe_controls(self, intermediate_servings, existing_amounts, remaining_servings, 
                                          on_weight_change, on_servings_change):
        """Create controls for each intermediate recipe."""
        controls = []
        for recipe_name, total_servings in sorted(intermediate_servings.items(), key=lambda x: x[1], reverse=True):
            if self._should_skip_recipe(recipe_name):
                continue
            
            remaining = remaining_servings.get(recipe_name, total_servings)
            recipe_control = self._create_single_intermediate_control(
                recipe_name, total_servings, remaining, existing_amounts,
                on_weight_change, on_servings_change
            )
            controls.append(recipe_control)
        return controls
    
    def _create_single_intermediate_control(self, recipe_name, total_servings, remaining, existing_amounts,
                                          on_weight_change, on_servings_change):
        """Create control for a single intermediate recipe."""
        existing = existing_amounts.get(recipe_name, {"weight": 0.0, "servings": 0.0})
        
        return ft.Container(
            content=ft.Column(
                [
                    self._create_recipe_header(recipe_name, total_servings),
                    self._create_existing_amounts_row(recipe_name, remaining, existing, 
                                                    on_weight_change, on_servings_change),
                ]
            ),
            bgcolor=ft.Colors.GREY_100,
            padding=8,
            border_radius=8,
        )
    
    def _create_recipe_header(self, recipe_name, total_servings):
        """Create header row for recipe with name and total needed."""
        return ft.Row(
            [
                ft.Text(recipe_name, size=16, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(f"Total needed: {total_servings:.4f} servings", size=14),
            ]
        )
    
    def _create_existing_amounts_row(self, recipe_name, remaining, existing, on_weight_change, on_servings_change):
        """Create row for existing amounts input."""
        return ft.Row(
            [
                ft.Text("I already have:", size=14, width=120),
                ft.TextField(
                    label="Weight (g)",
                    value=str(existing.get("weight", 0.0)),
                    width=TEXT_FIELD_WIDTH,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda e, name=recipe_name: on_weight_change(name, e.control.value),
                ),
                ft.Text("OR", size=12, width=30),
                ft.TextField(
                    label="Servings",
                    value=str(existing.get("servings", 0.0)),
                    width=TEXT_FIELD_WIDTH,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda e, name=recipe_name: on_servings_change(name, e.control.value),
                ),
                ft.Text(
                    f"→ Still need: {max(0, remaining):.4f} servings",
                    size=14,
                    color=ft.Colors.PRIMARY,
                    expand=True,
                ),
            ]
        )
    
    def create_recalculate_button(self, on_recalculate):
        """Create the recalculate button."""
        return ft.ElevatedButton(
            "🔄 Update Remaining Ingredients",
            on_click=on_recalculate,
            style=ft.ButtonStyle(bgcolor=ft.Colors.SECONDARY, color=ft.Colors.WHITE),
        )
    
    def create_servings_copy_section(self, intermediate_servings, remaining_servings):
        """Create copy-friendly section for intermediate recipes."""
        remaining_text = "Recipe\tTotal Needed\tRemaining Needed\n" + "\n".join(
            [
                f"{recipe_name}\t{servings:.4f}\t{max(0, remaining_servings.get(recipe_name, servings)):.4f}"
                for recipe_name, servings in sorted(
                    intermediate_servings.items(), key=lambda x: x[1], reverse=True
                )
                if not self._should_skip_recipe(recipe_name)
            ]
        )
        
        return ft.ExpansionTile(
            title=ft.Text("📋 Copy All Intermediate Recipes"),
            controls=[
                ft.Container(
                    content=ft.TextField(
                        value=remaining_text,
                        multiline=True,
                        read_only=True,
                        min_lines=3,
                        max_lines=8,
                        text_size=11,
                        border_color=ft.Colors.GREY_400,
                        bgcolor=ft.Colors.GREY_50,
                    ),
                    padding=5,
                )
            ],
            initially_expanded=False,
        )
    
    def _should_skip_recipe(self, recipe_name):
        """Check if recipe should be skipped (e.g., chiffon recipes)."""
        return EXCLUDED_RECIPE_KEYWORD in recipe_name.lower()
