"""Product costs calculator page orchestration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import flet as ft
from flet.core.control_event import ControlEvent

from shared.grist_service import DataFilterManager
from shared.ingredient_calculator import IngredientCalculator
from shared.tandoor_service import get_tandoor_service
from shared.ui.layout import LayoutConfig, default_layout_config, styled_container

from .chart_component import CostChartComponent
from .constants import (
    BODY_TEXT_SIZE,
    COLUMN_SPACING,
    COST_DISPLAY_PRECISION,
    COST_TEXT_PADDING_LEFT,
    COST_TEXT_SIZE,
    PRODUCT_BUTTON_HEIGHT,
    PRODUCT_BUTTON_WIDTH,
    SUBTITLE_TEXT_SIZE,
    TITLE_TEXT_SIZE,
)
from .cost_calculator import MaterialCostCalculator
from .state_manager import ProductCostsState
from .ui_components import UIComponentBuilder

logger = logging.getLogger(__name__)


class ProductCostsCalculatorContent(ft.Container):
    """Container that orchestrates the product cost calculation workflow."""

    def __init__(self, page: ft.Page | None = None) -> None:
        super().__init__()
        logger.info("🚀 Initializing ProductCostsCalculatorContent")

        self.page: ft.Page | None = page

        self.state = ProductCostsState()
        self.chart_component = CostChartComponent()

        self.data_manager = DataFilterManager()
        self.cost_calculator = MaterialCostCalculator()
        self.tandoor = get_tandoor_service()

        self.ui_builder: UIComponentBuilder | None = None
        self._layout_config: LayoutConfig = default_layout_config()

        self.loading_indicator: ft.ProgressRing | None = None
        self.products_column: ft.Column | None = None
        self.chart_column: ft.Column | None = None
        self.main_content: ft.Column | None = None

    def update(self) -> None:
        """Update the underlying Flet page if present."""

        if self.page:
            self.page.update()

    def build_content(self) -> "ProductCostsCalculatorContent":
        """Construct the full layout, load data, and return the container."""

        logger.info("🔧 Setting up UI...")
        self.setup_ui()
        logger.info("📋 Loading recipes...")
        self.load_recipes()
        logger.info("📊 Loading Grist data...")
        self.load_grist_data()
        logger.info("✅ Build complete")

        if self.main_content is not None:
            self.content = self.main_content
        return self

    def setup_ui(self) -> None:
        """Initialize UI scaffolding."""

        self.loading_indicator = ft.ProgressRing(visible=False)
        self.products_column = self._create_products_column()
        self.chart_column = self._create_chart_column()
        self.main_content = self._create_main_layout()

    def _create_products_column(self) -> ft.Column:
        """Create the left-hand product selection column."""

        return ft.Column(
            controls=[
                ft.Text("🍰 Products", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
                self._create_date_range_section(),
                ft.Text("Loading recipes...", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_chart_column(self) -> ft.Column:
        """Create the right-hand chart column placeholder."""

        return ft.Column(
            controls=[
                ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
                ft.Text("👆 Click on a product to see its cost graph", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_main_layout(self) -> ft.Column:
        """Compose the full page layout."""

        assert self.products_column is not None
        assert self.chart_column is not None

        products_container = self._create_styled_container(self.products_column)
        products_container.expand = 1

        chart_container = self._create_styled_container(self.chart_column)
        chart_container.expand = 2

        loading_indicator = self.loading_indicator or ft.ProgressRing(visible=False)

        main_row = ft.Row(
            controls=[products_container, chart_container],
            expand=True,
            spacing=COLUMN_SPACING,
        )

        return ft.Column(
            controls=[ft.Row([loading_indicator], alignment=ft.MainAxisAlignment.CENTER), main_row],
            expand=True,
            spacing=COLUMN_SPACING,
        )

    def _create_styled_container(self, content: ft.Control) -> ft.Container:
        """Return a styled container using shared layout defaults."""

        if self.ui_builder:
            return self.ui_builder.create_styled_container(content)
        return styled_container(content, self._layout_config)

    def _create_date_range_section(self) -> ft.Control:
        """Create the date range controls or a loading placeholder."""

        if self.ui_builder:
            return self.ui_builder.create_date_range_section(
                self.data_manager.start_date,
                self.data_manager.end_date,
                self.on_start_date_change,
                self.on_end_date_change,
                self.apply_date_filter,
            )

        return ft.Text("Date range controls loading...", size=BODY_TEXT_SIZE, color=ft.Colors.GREY)

    def load_recipes(self) -> None:
        """Load product recipes and initialise ingredient calculations."""

        logger.info("🔄 Starting recipe loading...")
        if self.loading_indicator:
            self.loading_indicator.visible = True

        try:
            all_recipes = self.tandoor.get_recipes()
            if not all_recipes:
                self.show_error("Failed to load recipes from Tandoor")
                return

            self.state.set_recipes(all_recipes)
            logger.info("📋 Loaded %d total recipes", len(all_recipes))

            if not self.state.has_product_recipes():
                self.show_error("No recipes found with 'product' keyword")
                return

            self.calculate_product_ingredients()
            self.setup_products_ui()

        except Exception:  # noqa: BLE001 - error surfaced via UI
            logger.exception("Error loading recipes")
            self.show_error("Error loading recipes. Check logs for details.")
        finally:
            if self.loading_indicator:
                self.loading_indicator.visible = False
            self.update()

    def setup_products_ui(self) -> None:
        """Render product buttons and cost summaries."""

        if self.products_column is None:
            return

        if self.ui_builder is None:
            self.ui_builder = UIComponentBuilder(self.cost_calculator, self.cost_calculator.material_cost_basis)

        product_controls: list[ft.Control] = [
            ft.Text("🍰 Products", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            self._create_date_range_section(),
            ft.Text("Click on a product to see its raw ingredients:", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
        ]
        product_controls.extend(self._create_clickable_recipe_buttons())

        self.products_column.controls = product_controls
        self.update()

    def _create_clickable_recipe_buttons(self) -> list[ft.Row]:
        """Build buttons for each product with current cost snapshot."""

        buttons: list[ft.Row] = []
        for recipe in self.state.product_recipes:
            is_selected = self.state.selected_product == recipe.name
            current_cost = self._calculate_current_product_cost(recipe.name)
            cost_text = f"${current_cost:.{COST_DISPLAY_PRECISION}f}" if current_cost is not None else "Cost N/A"

            button = ft.ElevatedButton(
                text=recipe.name,
                width=PRODUCT_BUTTON_WIDTH,
                height=PRODUCT_BUTTON_HEIGHT,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY if is_selected else ft.Colors.BLUE_GREY_100,
                    color=ft.Colors.WHITE if is_selected else ft.Colors.BLACK,
                ),
                on_click=lambda event, name=recipe.name: self.on_product_click(name),
            )

            cost_label = ft.Container(
                content=ft.Text(
                    cost_text,
                    size=COST_TEXT_SIZE,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREEN if current_cost is not None else ft.Colors.RED,
                ),
                padding=ft.padding.only(left=COST_TEXT_PADDING_LEFT),
                alignment=ft.alignment.center_left,
            )

            buttons.append(
                ft.Row(
                    controls=[button, cost_label],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        return buttons

    def _calculate_current_product_cost(self, recipe_name: str) -> Optional[float]:
        """Compute the current cost for a single unit of the product."""

        try:
            ingredients = self.state.get_product_ingredients(recipe_name)
            if not ingredients:
                logger.warning("No ingredients found for %s", recipe_name)
                return None

            _, total_cost = self.cost_calculator.calculate_ingredient_costs(
                ingredients, self.cost_calculator.material_cost_basis
            )
            return total_cost
        except Exception:  # noqa: BLE001 - surfaced via log
            logger.exception("Error calculating current cost for %s", recipe_name)
            return None

    def on_product_click(self, recipe_name: str) -> None:
        """Handle product selection."""

        self.state.set_selected_product(recipe_name)
        logger.info("Selected product: %s", recipe_name)
        self.setup_products_ui()
        self.show_product_cost_chart(recipe_name)

    def on_start_date_change(self, event: ControlEvent) -> None:
        """Parse and store the start date filter value."""

        value = event.control.value or ""
        try:
            self.data_manager.start_date = datetime.strptime(value, "%Y-%m-%d") if value else None
            logger.debug("Start date changed to: %s", self.data_manager.start_date)
        except ValueError:
            logger.warning("Invalid start date format: %s", value)
            self.data_manager.start_date = None

    def on_end_date_change(self, event: ControlEvent) -> None:
        """Parse and store the end date filter value."""

        value = event.control.value or ""
        try:
            self.data_manager.end_date = datetime.strptime(value, "%Y-%m-%d") if value else None
            logger.debug("End date changed to: %s", self.data_manager.end_date)
        except ValueError:
            logger.warning("Invalid end date format: %s", value)
            self.data_manager.end_date = None

    def apply_date_filter(self, _event: ControlEvent) -> None:
        """Apply the configured date range to the Grist dataset."""

        logger.info("Applying date filter to Grist data...")
        self.data_manager.apply_time_filter()
        filtered_data = self.data_manager.get_filtered_data()

        self.cost_calculator.calculate_material_cost_basis(filtered_data)

        if self.ui_builder:
            self.ui_builder.material_cost_basis = self.cost_calculator.material_cost_basis

        if filtered_data is None or filtered_data.is_empty():
            logger.warning("No data available after filtering")
            return

        total_records = self.data_manager.grist_dataframe.height if self.data_manager.grist_dataframe is not None else 0
        filtered_records = filtered_data.height

        if self.data_manager.start_date and self.data_manager.end_date:
            logger.info(
                "Filter applied: %s to %s",
                self.data_manager.start_date.strftime("%Y-%m-%d"),
                self.data_manager.end_date.strftime("%Y-%m-%d"),
            )
        elif self.data_manager.start_date:
            logger.info("Filter applied from %s", self.data_manager.start_date.strftime("%Y-%m-%d"))
        elif self.data_manager.end_date:
            logger.info("Filter applied until %s", self.data_manager.end_date.strftime("%Y-%m-%d"))
        else:
            logger.info("No date filter applied - showing all records")

        logger.info("Showing %d of %d records", filtered_records, total_records)

    def calculate_product_ingredients(self) -> None:
        """Pre-compute ingredient breakdown for each product recipe."""

        if not self.state.has_recipes():
            return

        calculator = IngredientCalculator(self.state.recipes)

        for recipe in self.state.product_recipes:
            raw_ingredients = calculator.calculate_raw_ingredients({recipe.name: 1.0})
            self.state.set_product_ingredients(recipe.name, raw_ingredients)

    def load_grist_data(self) -> None:
        """Load Grist exports and compute initial cost basis."""

        try:
            self.data_manager.load_grist_data()
            filtered_data = self.data_manager.get_filtered_data()
            self.cost_calculator.calculate_material_cost_basis(filtered_data)
            self.cost_calculator.set_data_manager(self.data_manager)

            if self.ui_builder is None:
                self.ui_builder = UIComponentBuilder(self.cost_calculator, self.cost_calculator.material_cost_basis)
            else:
                self.ui_builder.material_cost_basis = self.cost_calculator.material_cost_basis

            if self.state.has_product_recipes():
                self.setup_products_ui()
        except Exception:  # noqa: BLE001 - surfaced via log
            logger.exception("Failed to load Grist data")
            self.show_error("Failed to load cost data from Grist")

    def show_product_cost_chart(self, recipe_name: str) -> None:
        """Render the cost chart for the selected product."""

        if self.chart_column is None:
            return

        validation_error = self._validate_chart_prerequisites(recipe_name)
        if validation_error:
            self._show_chart_error(validation_error)
            return

        self._show_chart_loading(recipe_name)

        try:
            self._generate_and_display_chart(recipe_name)
        except Exception:  # noqa: BLE001 - surfaced via log and UI
            logger.exception("Error creating cost chart for %s", recipe_name)
            self._show_chart_error("Error creating chart. Check logs for details.")

    def _validate_chart_prerequisites(self, recipe_name: str) -> Optional[str]:
        """Ensure ingredients and calculators are ready for charting."""

        ingredients = self.state.get_product_ingredients(recipe_name)
        if not ingredients:
            return f"No ingredients found for {recipe_name}"

        if self.chart_column is None:
            return "Chart column not initialized"

        return None

    def _show_chart_error(self, error_message: str) -> None:
        """Display an error message in the chart column."""

        if self.chart_column is None:
            return

        header = ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD)
        body = ft.Text(error_message, size=BODY_TEXT_SIZE, color=ft.Colors.RED)

        if self.chart_column.controls:
            self.chart_column.controls.clear()
        self.chart_column.controls.extend([header, body])
        if self.page:
            self.page.update()

    def _show_chart_loading(self, recipe_name: str) -> None:
        """Show a loading indicator while cost data is calculated."""

        if self.chart_column is None:
            return

        header = ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD)
        message = ft.Text(
            f"Analyzing cost trends for {recipe_name}...",
            size=BODY_TEXT_SIZE,
            color=ft.Colors.GREY,
        )
        indicator = ft.ProgressRing(visible=True)

        if self.chart_column.controls:
            self.chart_column.controls.clear()
        self.chart_column.controls.extend([header, message, indicator])
        if self.page:
            self.page.update()

    def _generate_and_display_chart(self, recipe_name: str) -> None:
        """Calculate chart data and render the visualization."""

        assert self.chart_column is not None
        assert self.ui_builder is not None

        ingredients = self.state.get_product_ingredients(recipe_name)

        cost_data = self.cost_calculator.calculate_cost_time_series(
            recipe_name, ingredients, self.chart_component.trailing_months
        )

        self.state.set_current_cost_data(cost_data)
        self.state.set_current_recipe_ingredients(ingredients)

        breakdown = self.ui_builder.create_ingredient_breakdown(
            recipe_name,
            ingredients,
            None,
            self.cost_calculator.material_cost_basis,
        )
        self._render_chart_column(recipe_name, cost_data, breakdown)

    def _render_chart_column(
        self,
        recipe_name: str,
        cost_data: list[tuple[datetime, float]],
        breakdown: ft.Control,
    ) -> None:
        """Render the chart column with the provided controls."""

        if self.chart_column is None:
            return

        chart_controls: list[ft.Control] = [
            ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            self.chart_component.create_trailing_window_input(self.on_trailing_window_change),
            self.chart_component.create_cost_chart(recipe_name, cost_data, self.on_chart_click),
            self.chart_component.create_cost_summary(cost_data),
            ft.Divider(),
            ft.Text("📋 Cost Breakdown", size=SUBTITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Click on a point in the graph to see ingredient costs at that time",
                size=12,
                color=ft.Colors.GREY,
            ),
            breakdown,
        ]

        self.chart_column.controls.clear()
        self.chart_column.controls.extend(chart_controls)
        if self.page:
            self.page.update()

    def on_trailing_window_change(self, event: ControlEvent) -> None:
        """Update trailing months for the chart."""

        value = event.control.value or "0"
        try:
            self.chart_component.trailing_months = int(value)
            if self.state.selected_product:
                self.show_product_cost_chart(self.state.selected_product)
        except ValueError:
            logger.warning("Invalid trailing window value: %s", value)

    def on_chart_click(self, selected_date: datetime, _selected_cost: float, _spot_index: int) -> None:
        """Display ingredient breakdown for the clicked time point."""

        if not self.state.selected_product:
            logger.warning("No product selected for chart click")
            return

        if not self.state.current_recipe_ingredients:
            logger.warning("No current recipe ingredients available")
            return

        selected_cost_basis = self.cost_calculator.calculate_cost_basis_for_window_at_date(
            selected_date, self.chart_component.trailing_months
        )

        if not selected_cost_basis:
            logger.warning("No cost basis data available for %s", selected_date)
            return

        self._update_ingredient_breakdown_display(
            self.state.selected_product,
            self.state.current_recipe_ingredients,
            selected_date,
            selected_cost_basis,
        )

    def _update_ingredient_breakdown_display(
        self,
        recipe_name: str,
        ingredients: dict,
        selected_date: datetime,
        cost_basis: dict,
    ) -> None:
        """Refresh the ingredient breakdown section with historical pricing."""

        if self.chart_column is None or self.ui_builder is None:
            return

        try:
            new_breakdown = self.ui_builder.create_ingredient_breakdown(
                recipe_name, ingredients, selected_date, cost_basis
            )

            if not self.state.current_cost_data:
                logger.warning("No cached cost data available for chart refresh")
                return

            self._render_chart_column(recipe_name, self.state.current_cost_data, new_breakdown)
        except Exception:  # noqa: BLE001 - surfaced via log
            logger.exception("Error updating ingredient breakdown display")

    def show_error(self, error_message: str) -> None:
        """Log and surface errors in the products column."""

        logger.error("Error: %s", error_message)

        if self.products_column is not None:
            header = ft.Text("🍰 Products", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD)
            message = ft.Text(error_message, size=BODY_TEXT_SIZE, color=ft.Colors.RED)
            if self.products_column.controls:
                self.products_column.controls.clear()
            self.products_column.controls.extend([header, message])
            if self.page:
                self.page.update()
