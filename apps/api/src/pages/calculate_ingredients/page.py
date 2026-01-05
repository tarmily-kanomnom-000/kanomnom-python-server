"""Ingredients calculator page orchestration."""

from __future__ import annotations

import logging

import flet as ft
from flet.core.control_event import ControlEvent

from shared.tandoor_service import get_tandoor_service

from .calculation_service import IngredientsCalculationService
from .constants import COLUMN_SPACING
from .state_manager import IngredientsState
from .ui_components import IngredientUIBuilder

# Configure logging for debugging
logger = logging.getLogger(__name__)


class IngredientsCalculatorContent(ft.Container):
    def __init__(self, page: ft.Page | None = None) -> None:
        super().__init__()
        logger.info("🚀 Initializing IngredientsCalculatorContent")
        self.page: ft.Page | None = page
        self.state = IngredientsState()
        self.calculation_service = IngredientsCalculationService(self.state)
        self.tandoor = get_tandoor_service()
        self.ui_builder = IngredientUIBuilder()
        self.loading_indicator: ft.ProgressRing | None = None
        self.products_column: ft.Column | None = None
        self.ingredients_column: ft.Column | None = None
        self.main_content: ft.Column | None = None

    def update(self) -> None:
        """Update the page if available."""

        if self.page:
            self.page.update()

    def build_content(self) -> "IngredientsCalculatorContent":
        logger.info("🔧 Setting up UI...")
        self.setup_ui()
        logger.info("📋 Loading recipes...")
        self.load_recipes()
        logger.info("✅ Build complete")
        self.content = self.main_content
        return self

    def setup_ui(self) -> None:
        """Setup the main UI components."""

        self.loading_indicator = ft.ProgressRing(visible=False)
        self.products_column = self._create_products_column()
        self.ingredients_column = self._create_ingredients_column()
        self.main_content = self._create_main_layout()

    def _create_products_column(self) -> ft.Column:
        """Create the products column with initial state."""

        return ft.Column(
            controls=[
                ft.Text("🍰 Products", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Loading recipes...", size=14, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_ingredients_column(self) -> ft.Column:
        """Create the ingredients column with initial state."""

        return ft.Column(
            controls=[
                ft.Text("📋 Raw Ingredients", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("👆 Enter quantities on the left to see raw ingredients", size=14, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_main_layout(self) -> ft.Column:
        """Create the main layout with compact products column and expanded ingredients section."""
        assert self.products_column is not None
        assert self.ingredients_column is not None

        products_container = self.ui_builder.create_styled_container(self.products_column)
        products_container.expand = 1  # Takes up 1/3 of space

        ingredients_container = self.ui_builder.create_styled_container(self.ingredients_column)
        ingredients_container.expand = 2  # Takes up 2/3 of space

        main_row = ft.Row(
            controls=[products_container, ingredients_container],
            expand=True,
            spacing=COLUMN_SPACING,
        )

        return ft.Column(
            controls=[ft.Row([self.loading_indicator], alignment=ft.MainAxisAlignment.CENTER), main_row],
            expand=True,
            spacing=COLUMN_SPACING,
        )

    def load_recipes(self) -> None:
        logger.info("🔄 Starting recipe loading...")
        if self.loading_indicator:
            self.loading_indicator.visible = True

        try:
            # Load recipes from Tandoor
            all_recipes = self.tandoor.get_recipes()
            if not all_recipes:
                self.show_error("Failed to load recipes from Tandoor")
                return

            # Get product recipes
            product_recipes = self.tandoor.get_product_recipes()
            if not product_recipes:
                self.show_error("No recipes found with 'product' keyword")
                return

            # Initialize calculator with all recipes and set product recipes in state
            self.calculation_service.set_recipes(all_recipes)
            self.state.product_recipes = product_recipes
            self.state.quantities = {recipe.name: 0.0 for recipe in product_recipes}

            # Update UI
            self.setup_products_ui()

        except Exception as error:  # noqa: BLE001 - reported via UI
            logger.exception("Error loading recipes")
            self.show_error(f"Error loading recipes: {error}")
        finally:
            if self.loading_indicator:
                self.loading_indicator.visible = False
            self.update()

    def setup_products_ui(self) -> None:
        """Setup the products UI with recipe input fields and action buttons."""
        assert self.products_column is not None

        product_controls: list[ft.Control] = [ft.Text("🍰 Products", size=24, weight=ft.FontWeight.BOLD)]

        # Add recipe input rows
        recipe_rows = self.ui_builder.create_recipe_input_rows(self.state.product_recipes, self.on_quantity_change)
        product_controls.extend(recipe_rows)

        # Add action buttons
        action_buttons = self.ui_builder.create_action_buttons(self.update_ingredients, self.clear_all)
        product_controls.append(action_buttons)

        self.products_column.controls = product_controls
        self.update()

    def on_quantity_change(self, recipe_name: str, value: str) -> None:
        """Handle quantity change events."""
        try:
            quantity = float(value) if value else 0.0
            self.state.update_quantity(recipe_name, quantity)
        except (ValueError, KeyError):
            pass  # Invalid number or recipe name, ignore

    def update_ingredients(self, _event: ControlEvent) -> None:
        """Update ingredients based on current quantities."""
        try:
            # Get selected quantities > 0
            selected_quantities = {name: qty for name, qty in self.state.quantities.items() if qty > 0}

            if not selected_quantities:
                self.show_ingredients_info("👆 Enter quantities above to see raw ingredients")
                return

            # Use the calculation service with filtered quantities
            if not self.calculation_service.calculate_ingredients(selected_quantities):
                self.show_ingredients_info("❌ Calculation failed")
                return

            if not self.state.raw_ingredients:
                self.show_ingredients_info("👆 Enter quantities above to see raw ingredients")
                return

            self.show_ingredients_results()

        except Exception:  # noqa: BLE001 - surfaced via UI
            logger.exception("Error calculating raw ingredients")
            self.ingredients_column.controls = [
                ft.Text("📋 Raw Ingredients", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Error occurred during calculation", size=14, color=ft.Colors.RED),
            ]
            self.update()

    def show_ingredients_results(self) -> None:
        """Display the calculated ingredients results."""
        assert self.ingredients_column is not None

        ingredients_controls: list[ft.Control] = [ft.Text("📋 Raw Ingredients", size=24, weight=ft.FontWeight.BOLD)]

        # Add raw ingredients section
        ingredients_controls.extend(self._create_raw_ingredients_section())

        # Add intermediate servings section if available
        if self.state.intermediate_servings:
            intermediate_controls = self._create_intermediate_servings_section()
            if intermediate_controls:
                ingredients_controls.extend(intermediate_controls)

        self.ingredients_column.controls = ingredients_controls
        self.update()

    def _create_raw_ingredients_section(self) -> list[ft.Control]:
        """Create the raw ingredients display section."""
        ingredients_table = self.ui_builder.create_ingredients_table(self.state.raw_ingredients)
        copy_section = self.ui_builder.create_ingredients_copy_section(self.state.raw_ingredients)

        return [
            ft.Text("📋 Required Raw Ingredients:", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            ft.Container(content=ingredients_table, border=ft.border.all(1, ft.Colors.GREY), border_radius=5, padding=10),
            copy_section,
        ]

    def _create_intermediate_servings_section(self) -> list[ft.Control]:
        """Create the intermediate servings section if available."""
        # Initialize existing amounts for intermediate recipes
        for recipe_name in self.state.intermediate_servings.keys():
            if recipe_name not in self.state.existing_intermediate_amounts:
                self.state.existing_intermediate_amounts[recipe_name] = {"weight": 0.0, "servings": 0.0}

        remaining_servings = self.calculation_service._calculate_remaining_servings()

        intermediate_recipe_controls = self.ui_builder.create_intermediate_recipe_controls(
            self.state.intermediate_servings,
            self.state.existing_intermediate_amounts,
            remaining_servings,
            self.on_existing_weight_change,
            self.on_existing_servings_change,
        )

        if not intermediate_recipe_controls:
            return []

        # Add action button and copy section
        intermediate_recipe_controls.append(self.ui_builder.create_recalculate_button(self.recalculate_with_existing))
        servings_copy_section = self.ui_builder.create_servings_copy_section(self.state.intermediate_servings, remaining_servings)

        return [
            ft.Text("🔧 Intermediate Recipe Servings:", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            ft.Container(
                content=ft.Column(intermediate_recipe_controls),
                border=ft.border.all(1, ft.Colors.GREY),
                border_radius=5,
                padding=10,
            ),
            servings_copy_section,
        ]

    def on_existing_weight_change(self, recipe_name: str, value: str) -> None:
        """Handle changes to existing weight input."""
        try:
            weight = float(value) if value else 0.0
            self.state.update_existing_weight(recipe_name, weight)
        except ValueError as e:
            logger.warning(f"Invalid weight value for {recipe_name}: {value} - {e}")
            # Reset to 0 on invalid input
            self.state.update_existing_weight(recipe_name, 0.0)

    def on_existing_servings_change(self, recipe_name: str, value: str) -> None:
        """Handle changes to existing servings input."""
        try:
            servings = float(value) if value else 0.0
            self.state.update_existing_servings(recipe_name, servings)
        except ValueError as e:
            logger.warning(f"Invalid servings value for {recipe_name}: {value} - {e}")
            # Reset to 0 on invalid input
            self.state.update_existing_servings(recipe_name, 0.0)

    def recalculate_with_existing(self, _event: ControlEvent) -> None:
        """Recalculate raw ingredients accounting for existing intermediate amounts."""
        if not self.calculation_service.recalculate_with_existing():
            self.show_error("❌ Recalculation failed")
            return

        self.show_ingredients_results()

    def clear_all(self, _event: ControlEvent | None) -> None:
        """Clear all quantities and reset UI."""
        assert self.products_column is not None
        # Clear all state
        self.state.clear_all_state()

        # Update all text fields
        for control in self.products_column.controls:
            if isinstance(control, ft.Row):
                for item in control.controls:
                    if isinstance(item, ft.TextField):
                        item.value = "0"

        self.show_ingredients_info("👆 Enter quantities above to see raw ingredients")
        self.update()

    def show_ingredients_info(self, message: str) -> None:
        """Display an informational message in the ingredients column."""
        assert self.ingredients_column is not None
        self.ingredients_column.controls = [
            ft.Text("📋 Raw Ingredients", size=24, weight=ft.FontWeight.BOLD),
            ft.Text(message, size=14, color=ft.Colors.GREY),
        ]
        self.update()

    def show_error(self, error_message: str) -> None:
        """Log error message."""
        logger.error(f"Error: {error_message}")
