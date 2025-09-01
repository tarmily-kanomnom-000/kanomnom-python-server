"""
UI component creation for the product costs calculator page.
Handles ingredient tables, semantic grouping display, and copy sections.
"""

import flet as ft
from datetime import datetime
from typing import Optional
from .constants import (
    COLUMN_SPACING, CONTAINER_PADDING, CONTAINER_BORDER_RADIUS,
    BUTTON_SPACING, TEXT_FIELD_WIDTH, DATE_FIELD_WIDTH,
    INGREDIENT_DISPLAY_PRECISION, COST_DISPLAY_PRECISION
)


class UIComponentBuilder:
    """Builds UI components for the product costs calculator."""
    
    def __init__(self, cost_calculator, material_cost_basis):
        self.cost_calculator = cost_calculator
        self.material_cost_basis = material_cost_basis
    
    def create_styled_container(self, content) -> ft.Container:
        """Create a styled container for content."""
        return ft.Container(
            content=content,
            bgcolor=ft.Colors.BLUE_GREY_100,
            padding=CONTAINER_PADDING,
            border_radius=CONTAINER_BORDER_RADIUS,
            expand=1,
        )

    def create_date_range_section(self, start_date, end_date, on_start_change, on_end_change, on_apply_filter) -> ft.Container:
        """Create the date range input section."""
        # Set default values to the current date range
        start_default = start_date.strftime("%Y-%m-%d") if start_date else ""
        end_default = end_date.strftime("%Y-%m-%d") if end_date else ""
        
        start_date_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=start_default,
            width=DATE_FIELD_WIDTH,
            on_change=on_start_change
        )
        
        end_date_field = ft.TextField(
            label="End Date (YYYY-MM-DD)", 
            value=end_default,
            width=DATE_FIELD_WIDTH,
            on_change=on_end_change
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("📅 Time Range Filter", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    start_date_field,
                    end_date_field,
                    ft.ElevatedButton(
                        "Apply Filter",
                        on_click=on_apply_filter,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.SECONDARY, color=ft.Colors.WHITE),
                    )
                ], spacing=10)
            ]),
            padding=10,
            margin=ft.margin.only(bottom=20),
            bgcolor=ft.Colors.BLUE_GREY_100,
            border_radius=5
        )
    
    def create_ingredient_breakdown(self, recipe_name: str, ingredients: dict, 
                                  selected_date: Optional[datetime], cost_basis: dict) -> ft.Container:
        """Create ingredient breakdown efficiently by reusing cached semantic matches."""
        if not cost_basis:
            return ft.Container(
                content=ft.Text("No cost data available for selected time point", color=ft.Colors.RED),
                padding=10
            )
        
        # Calculate costs efficiently
        sorted_ingredients, total_cost = self.cost_calculator.calculate_ingredient_costs(ingredients, cost_basis)
        
        # Create the ingredients table
        ingredients_table = self._create_ingredients_table(sorted_ingredients)
        
        # Create title with date info
        title_text = self._create_breakdown_title(recipe_name, selected_date)
        
        return ft.Container(
            content=ft.Column([
                ft.Text(
                    title_text,
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.PRIMARY
                ),
                ft.Container(height=5),  # Small spacer
                ft.Container(
                    content=ingredients_table,
                    border=ft.border.all(1, ft.Colors.GREY),
                    border_radius=5,
                    padding=10,
                    bgcolor=ft.Colors.WHITE
                ),
                # Add copy section
                self.create_ingredient_copy_section(recipe_name, sorted_ingredients, total_cost)
            ]),
            margin=ft.margin.only(top=10),
            key=f"ingredient_breakdown_{recipe_name}_{selected_date.strftime('%Y%m') if selected_date else 'current'}"
        )
    
    def _create_ingredients_table(self, sorted_ingredients) -> ft.Column:
        """Create the ingredients table with header and data rows."""
        ingredient_rows = []
        
        # Header
        ingredient_rows.append(
            ft.Row([
                ft.Text("Ingredient", weight=ft.FontWeight.BOLD, expand=True, selectable=True),
                ft.Text("Amount", weight=ft.FontWeight.BOLD, width=80, text_align=ft.TextAlign.RIGHT, selectable=True),
                ft.Text("Unit", weight=ft.FontWeight.BOLD, width=60, selectable=True),
                ft.Text("Cost Basis", weight=ft.FontWeight.BOLD, width=100, text_align=ft.TextAlign.RIGHT, selectable=True),
                ft.Text("Ingredient Cost", weight=ft.FontWeight.BOLD, width=100, text_align=ft.TextAlign.RIGHT, selectable=True),
            ])
        )
        ingredient_rows.append(ft.Divider())
        
        # Add ingredient rows
        total_cost = 0.0
        for ingredient, amount, unit, cost_per_unit, ingredient_cost, _ in sorted_ingredients:
            cost_basis_text, ingredient_cost_text, cost_basis_color, ingredient_cost_color = self._format_cost_data(
                cost_per_unit, ingredient_cost, unit
            )
            
            ingredient_rows.append(
                ft.Row([
                    ft.Text(ingredient, expand=True, selectable=True),
                    ft.Text(f"{amount:.{INGREDIENT_DISPLAY_PRECISION}f}", width=80, text_align=ft.TextAlign.RIGHT, selectable=True),
                    ft.Text(unit, width=60, selectable=True),
                    ft.Text(cost_basis_text, width=100, text_align=ft.TextAlign.RIGHT, selectable=True, color=cost_basis_color),
                    ft.Text(ingredient_cost_text, width=100, text_align=ft.TextAlign.RIGHT, selectable=True, color=ingredient_cost_color),
                ])
            )
            total_cost += ingredient_cost if ingredient_cost else 0.0
        
        # Add total cost row
        ingredient_rows.append(ft.Divider())
        ingredient_rows.append(
            ft.Row([
                ft.Text("TOTAL COST", weight=ft.FontWeight.BOLD, expand=True, selectable=True),
                ft.Text("", width=80),
                ft.Text("", width=60),
                ft.Text("", width=100),
                ft.Text(f"${total_cost:.{COST_DISPLAY_PRECISION}f}", width=100, text_align=ft.TextAlign.RIGHT, selectable=True, 
                       weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
            ])
        )
        
        return ft.Column(ingredient_rows)
    
    def _format_cost_data(self, cost_per_unit: Optional[float], ingredient_cost: Optional[float], unit: str):
        """Format cost data for display with appropriate colors."""
        if cost_per_unit is not None:
            cost_basis_text = f"${cost_per_unit:.{INGREDIENT_DISPLAY_PRECISION}f}/{unit}"
            ingredient_cost_text = f"${ingredient_cost:.{INGREDIENT_DISPLAY_PRECISION}f}"
            cost_basis_color = ft.Colors.BLACK
            ingredient_cost_color = ft.Colors.GREEN
        else:
            cost_basis_text = "not found"
            ingredient_cost_text = "not found"
            cost_basis_color = ft.Colors.RED
            ingredient_cost_color = ft.Colors.RED
        
        return cost_basis_text, ingredient_cost_text, cost_basis_color, ingredient_cost_color
    
    def _create_breakdown_title(self, recipe_name: str, selected_date: Optional[datetime]) -> str:
        """Create title text for ingredient breakdown."""
        if selected_date:
            date_text = f"at {selected_date.strftime('%B %Y')}"
            return f"Ingredients for 1 × {recipe_name} ({date_text}):"
        else:
            return f"Ingredients for 1 × {recipe_name} (Current Prices):"
    
    def create_ingredient_copy_section(self, recipe_name: str, sorted_ingredients, total_cost: float) -> ft.ExpansionTile:
        """Create copy-friendly section without calling semantic matching again."""
        ingredients_text = f"Ingredients for 1 × {recipe_name}:\n\n"
        ingredients_text += "Ingredient\tAmount\tUnit\tCost Basis\tIngredient Cost\n"
        
        for ingredient, amount, unit, cost_per_unit, ingredient_cost, _ in sorted_ingredients:
            cost_basis_text = f"${cost_per_unit:.{INGREDIENT_DISPLAY_PRECISION}f}/{unit}" if cost_per_unit is not None else "not found"
            ingredient_cost_text = f"${ingredient_cost:.{INGREDIENT_DISPLAY_PRECISION}f}" if ingredient_cost is not None else "not found"
            ingredients_text += f"{ingredient}\t{amount:.{INGREDIENT_DISPLAY_PRECISION}f}\t{unit}\t{cost_basis_text}\t{ingredient_cost_text}\n"
        
        ingredients_text += f"\nTOTAL COST: ${total_cost:.{COST_DISPLAY_PRECISION}f}"
        
        return ft.ExpansionTile(
            title=ft.Text("📋 Copy Ingredient Breakdown"),
            controls=[
                ft.Container(
                    content=ft.TextField(
                        value=ingredients_text,
                        multiline=True,
                        read_only=True,
                        min_lines=8,
                        max_lines=20,
                        text_size=11,
                        border_color=ft.Colors.GREY_400,
                        bgcolor=ft.Colors.GREY_50,
                    ),
                    padding=5,
                )
            ],
            initially_expanded=False,
        )