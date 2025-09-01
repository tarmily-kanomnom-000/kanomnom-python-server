"""
Product costs calculator page - reorganized for better maintainability.
Main orchestration logic for the product costs calculation interface.
"""

import logging
from datetime import datetime
from typing import Optional

import flet as ft
from shared.tandoor_service import get_tandoor_service
from shared.ingredient_calculator import IngredientCalculator

from shared.grist_service import DataFilterManager
from .cost_calculator import MaterialCostCalculator
from .ui_components import UIComponentBuilder
from .chart_component import CostChartComponent
from .state_manager import ProductCostsState
from .constants import (
    COLUMN_SPACING, PRODUCT_BUTTON_WIDTH, PRODUCT_BUTTON_HEIGHT,
    COST_TEXT_PADDING_LEFT, COST_TEXT_SIZE, TITLE_TEXT_SIZE,
    SUBTITLE_TEXT_SIZE, BODY_TEXT_SIZE, DEFAULT_TRAILING_MONTHS,
    INGREDIENT_DISPLAY_PRECISION, COST_DISPLAY_PRECISION,
    CONTAINER_PADDING, CONTAINER_BORDER_RADIUS
)

# Configure logging for debugging
logger = logging.getLogger(__name__)


class ProductCostsCalculatorContent(ft.Container):
    def __init__(self, page=None):
        super().__init__()
        logger.info("🚀 Initializing ProductCostsCalculatorContent")
        self.page = page
        self._initialize_state()
        self._initialize_components()
        self._initialize_ui_components()

    def _initialize_state(self):
        """Initialize application state."""
        self.state = ProductCostsState()
        self.chart_component = CostChartComponent()

    def _initialize_components(self):
        """Initialize core components."""
        self.data_manager = DataFilterManager()
        self.cost_calculator = MaterialCostCalculator()
        self.tandoor = get_tandoor_service()
        self.ui_builder = None  # Will be initialized after loading data

    def _initialize_ui_components(self):
        """Initialize UI component references."""
        self.loading_indicator = None
        self.products_column = None
        self.chart_column = None

    def update(self):
        """Update the page if available."""
        if self.page:
            self.page.update()

    def build_content(self):
        logger.info("🔧 Setting up UI...")
        self.setup_ui()
        logger.info("📋 Loading recipes...")
        self.load_recipes()
        logger.info("📊 Loading Grist data...")
        self.load_grist_data()
        logger.info("✅ Build complete")
        # Set the container's content to our main content
        self.content = self.main_content
        return self

    def setup_ui(self):
        """Setup the main UI components."""
        self.loading_indicator = ft.ProgressRing(visible=False)
        self.products_column = self._create_products_column()
        self.chart_column = self._create_chart_column()
        self.main_content = self._create_main_layout()

    def _create_products_column(self):
        """Create the products column with initial state."""
        return ft.Column(
            controls=[
                ft.Text("🍰 Products", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
                self._create_date_range_section(),
                ft.Text("Loading recipes...", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_chart_column(self):
        """Create the chart column with initial state."""
        return ft.Column(
            controls=[
                ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
                ft.Text("👆 Click on a product to see its cost graph", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
            ],
            expand=1,
            scroll=ft.ScrollMode.AUTO,
        )

    def _create_main_layout(self):
        """Create the main layout with compact products column and expanded chart section."""
        # Create containers with specific flex values for sizing
        products_container = self._create_styled_container(self.products_column)
        products_container.expand = 1  # Takes up 1/3 of space
        
        chart_container = self._create_styled_container(self.chart_column)
        chart_container.expand = 2  # Takes up 2/3 of space
        
        main_row = ft.Row(
            controls=[products_container, chart_container],
            expand=True,
            spacing=COLUMN_SPACING,
        )

        return ft.Column(
            controls=[ft.Row([self.loading_indicator], alignment=ft.MainAxisAlignment.CENTER), main_row],
            expand=True,
            spacing=COLUMN_SPACING,
        )
    
    def _create_styled_container(self, content):
        """Create a styled container for content."""
        if self.ui_builder:
            return self.ui_builder.create_styled_container(content)
        else:
            # Fallback for initialization
            return ft.Container(
                content=content,
                bgcolor=ft.Colors.BLUE_GREY_100,
                padding=CONTAINER_PADDING,
                border_radius=CONTAINER_BORDER_RADIUS,
                expand=1,
            )

    def _create_date_range_section(self):
        """Create the date range input section."""
        if self.ui_builder:
            return self.ui_builder.create_date_range_section(
                self.data_manager.start_date,
                self.data_manager.end_date,
                self.on_start_date_change,
                self.on_end_date_change,
                self.apply_date_filter
            )
        else:
            # Fallback for initialization
            return ft.Text("Date range controls loading...", size=12, color=ft.Colors.GREY)

    def load_recipes(self):
        logger.info("🔄 Starting recipe loading...")
        self.loading_indicator.visible = True

        try:
            # Load recipes from Tandoor
            all_recipes = self.tandoor.get_recipes()
            if not all_recipes:
                self.show_error("Failed to load recipes from Tandoor")
                return

            # Get product recipes
            product_recipes = self.tandoor.get_product_recipes()
            
            # Store recipes using state manager
            self.state.set_recipes(all_recipes)
            
            logger.info(f"📋 Loaded {len(all_recipes)} total recipes, {len(product_recipes)} product recipes")

            if not self.state.has_product_recipes():
                self.show_error("No recipes found with 'product' keyword")
                return

            # Calculate raw ingredients for each product (for single quantity)
            self.calculate_product_ingredients()

            # Update UI
            self.setup_products_ui()

        except Exception as e:
            self.show_error(f"Error loading recipes: {e}")
        finally:
            self.loading_indicator.visible = False
            self.update()

    def setup_products_ui(self):
        """Setup the products UI with clickable recipe buttons."""
        # Initialize UI builder now that we have data
        if not self.ui_builder:
            self.ui_builder = UIComponentBuilder(self.cost_calculator, self.cost_calculator.material_cost_basis)

        product_controls = [
            ft.Text("🍰 Products", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            self._create_date_range_section(),
            ft.Text("Click on a product to see its raw ingredients:", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
        ]
        product_controls.extend(self._create_clickable_recipe_buttons())

        self.products_column.controls = product_controls
        self.update()

    def _create_clickable_recipe_buttons(self):
        """Create clickable buttons for each product recipe with current cost display."""
        recipe_buttons = []
        for recipe in self.state.product_recipes:
            # Check if this recipe is currently selected
            is_selected = self.state.selected_product == recipe.name
            
            # Calculate current cost with 1-year trailing window
            current_cost = self._calculate_current_product_cost(recipe.name)
            cost_text = f"${current_cost:.2f}" if current_cost is not None else "Cost N/A"
            
            # Create a row with the button and cost display
            recipe_row = ft.Row(
                controls=[
                    ft.ElevatedButton(
                        text=recipe.name,
                        width=PRODUCT_BUTTON_WIDTH,
                        height=PRODUCT_BUTTON_HEIGHT,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY if is_selected else ft.Colors.BLUE_GREY_100,
                            color=ft.Colors.WHITE if is_selected else ft.Colors.BLACK,
                        ),
                        on_click=lambda e, name=recipe.name: self.on_product_click(name),
                    ),
                    ft.Container(
                        content=ft.Text(
                            cost_text,
                            size=COST_TEXT_SIZE,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREEN if current_cost is not None else ft.Colors.RED,
                        ),
                        padding=ft.padding.only(left=COST_TEXT_PADDING_LEFT),
                        alignment=ft.alignment.center_left,
                    )
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            recipe_buttons.append(recipe_row)
        return recipe_buttons

    def _calculate_current_product_cost(self, recipe_name: str) -> Optional[float]:
        """Calculate current cost for a product using 1-year trailing window."""
        try:
            # Get ingredients for this product
            ingredients = self.state.get_product_ingredients(recipe_name)
            if not ingredients:
                logger.warning(f"No ingredients found for {recipe_name}")
                return None
            
            # Calculate cost using current cost basis (1-year trailing window by default)
            sorted_ingredients, total_cost = self.cost_calculator.calculate_ingredient_costs(
                ingredients, 
                self.cost_calculator.material_cost_basis
            )
            
            return total_cost
            
        except Exception as e:
            logger.error(f"Error calculating current cost for {recipe_name}: {e}")
            return None

    def on_product_click(self, recipe_name: str):
        """Handle product button clicks."""
        self.state.set_selected_product(recipe_name)
        logger.info(f"Selected product: {recipe_name}")
        
        # Update product buttons to show selection
        self.setup_products_ui()
        
        # Show cost chart for this product
        self.show_product_cost_chart(recipe_name)

    def on_start_date_change(self, e):
        """Handle start date field changes."""
        try:
            if e.control.value:
                self.data_manager.start_date = datetime.strptime(e.control.value, "%Y-%m-%d")
            else:
                self.data_manager.start_date = None
            logger.debug(f"Start date changed to: {self.data_manager.start_date}")
        except ValueError:
            logger.warning(f"Invalid start date format: {e.control.value}")
            self.data_manager.start_date = None

    def on_end_date_change(self, e):
        """Handle end date field changes."""
        try:
            if e.control.value:
                self.data_manager.end_date = datetime.strptime(e.control.value, "%Y-%m-%d")
            else:
                self.data_manager.end_date = None
            logger.debug(f"End date changed to: {self.data_manager.end_date}")
        except ValueError:
            logger.warning(f"Invalid end date format: {e.control.value}")
            self.data_manager.end_date = None

    def apply_date_filter(self, _e):
        """Apply date filter to Grist data."""
        logger.info("Applying date filter to Grist data...")
        
        # Apply the time filter to the dataframe
        self.data_manager.apply_time_filter()
        
        # Recalculate cost basis with filtered data
        self.cost_calculator.calculate_material_cost_basis(
            self.data_manager.get_filtered_data()
        )
        
        # Update UI builder with new cost basis
        if self.ui_builder:
            self.ui_builder.material_cost_basis = self.cost_calculator.material_cost_basis
        
        # Show feedback to user about the filtering results
        filtered_df = self.data_manager.get_filtered_data()
        if filtered_df is not None and not filtered_df.empty:
            total_records = len(self.data_manager.grist_dataframe) if self.data_manager.grist_dataframe is not None else 0
            filtered_records = len(filtered_df)
            
            # Log filter results
            if self.data_manager.start_date and self.data_manager.end_date:
                logger.info(f"Filter applied: {self.data_manager.start_date.strftime('%Y-%m-%d')} to {self.data_manager.end_date.strftime('%Y-%m-%d')}")
                logger.info(f"Showing {filtered_records} of {total_records} records")
            elif self.data_manager.start_date:
                logger.info(f"Filter applied: from {self.data_manager.start_date.strftime('%Y-%m-%d')}")
                logger.info(f"Showing {filtered_records} of {total_records} records")
            elif self.data_manager.end_date:
                logger.info(f"Filter applied: until {self.data_manager.end_date.strftime('%Y-%m-%d')}")
                logger.info(f"Showing {filtered_records} of {total_records} records")
            else:
                logger.info("No date filter applied - showing all records")
                logger.info(f"Showing {filtered_records} records")
        else:
            logger.warning("No data available after filtering")

    def calculate_product_ingredients(self):
        """Calculate raw ingredients for each product (for single quantity)."""
        if not self.state.has_recipes():
            return
            
        calculator = IngredientCalculator(self.state.recipes)
        
        for recipe in self.state.product_recipes:
            logger.info(f"Calculating ingredients for {recipe.name}")
            # Calculate ingredients for exactly 1 unit of this product
            single_product_quantities = {recipe.name: 1.0}
            
            # Use the existing method but extract per-product breakdown
            raw_ingredients = calculator.calculate_raw_ingredients(single_product_quantities)
            
            # Store ingredients for this product
            self.state.set_product_ingredients(recipe.name, raw_ingredients)
            
            logger.info(f"Product {recipe.name} uses {len(raw_ingredients)} raw ingredients")
            for ingredient, (amount, unit) in raw_ingredients.items():
                logger.debug(f"  - {ingredient}: {amount:.4f} {unit}")
        
        logger.info(f"Calculated ingredients for {len(self.state.product_ingredients)} products")

    def load_grist_data(self):
        """Load Grist data and apply initial time filtering."""
        self.data_manager.load_grist_data()
        
        # Calculate initial cost basis
        self.cost_calculator.calculate_material_cost_basis(
            self.data_manager.get_filtered_data()
        )
        
        # Set data manager for time series calculations
        self.cost_calculator.set_data_manager(self.data_manager)
        
        # Initialize UI builder with cost data
        self.ui_builder = UIComponentBuilder(self.cost_calculator, self.cost_calculator.material_cost_basis)
        
        # Refresh products UI now that cost basis is available
        if self.state.has_product_recipes():  # Only refresh if we have products loaded
            self.setup_products_ui()

    def show_product_cost_chart(self, recipe_name: str):
        """Display the cost over time chart for a specific product."""
        # Validate prerequisites
        validation_error = self._validate_chart_prerequisites(recipe_name)
        if validation_error:
            self._show_chart_error(validation_error)
            return
        
        # Show loading state
        self._show_chart_loading(recipe_name)
        
        try:
            # Generate chart data and display
            self._generate_and_display_chart(recipe_name)
        except Exception as e:
            logger.error(f"Error creating cost chart for {recipe_name}: {e}")
            self._show_chart_error(f"Error creating chart: {str(e)}")
    
    def _validate_chart_prerequisites(self, recipe_name: str) -> Optional[str]:
        """Validate that prerequisites for chart creation are met."""
        ingredients = self.state.get_product_ingredients(recipe_name)
        if not ingredients:
            return f"No ingredients found for {recipe_name}"
        
        if not self.cost_calculator:
            return "Cost calculator not initialized"
        
        return None
    
    def _show_chart_error(self, error_message: str):
        """Display error message in chart column."""
        self.chart_column.controls = [
            ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            ft.Text(error_message, size=BODY_TEXT_SIZE, color=ft.Colors.RED),
        ]
        self.update()
    
    def _show_chart_loading(self, recipe_name: str):
        """Display loading state in chart column."""
        chart_controls = [
            ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            ft.Text(f"Analyzing cost trends for {recipe_name}...", size=BODY_TEXT_SIZE, color=ft.Colors.GREY),
            ft.ProgressRing(visible=True)
        ]
        self.chart_column.controls = chart_controls
        self.update()
    
    def _generate_and_display_chart(self, recipe_name: str):
        """Generate cost data and display the complete chart."""
        ingredients = self.state.get_product_ingredients(recipe_name)
        
        # Calculate cost time series
        logger.info(f"Calculating cost time series for {recipe_name}")
        cost_data = self.cost_calculator.calculate_cost_time_series(
            recipe_name, 
            ingredients, 
            self.chart_component.trailing_months
        )
        
        # Update state
        self.state.set_current_cost_data(cost_data)
        self.state.set_current_recipe_ingredients(ingredients)
        
        # Create chart components
        chart_controls = [
            ft.Text("📊 Cost Over Time", size=TITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            self.chart_component.create_trailing_window_input(self.on_trailing_window_change),
            self.chart_component.create_cost_chart(recipe_name, cost_data, self.on_chart_click),
            self.chart_component.create_cost_summary(cost_data),
            ft.Divider(),
            ft.Text("📋 Cost Breakdown", size=SUBTITLE_TEXT_SIZE, weight=ft.FontWeight.BOLD),
            ft.Text("Click on a point in the graph to see ingredient costs at that time", size=12, color=ft.Colors.GREY),
            self.ui_builder.create_ingredient_breakdown(recipe_name, ingredients, None, self.cost_calculator.material_cost_basis)
        ]
        
        self.chart_column.controls = chart_controls
        self.update()

    def on_trailing_window_change(self, e):
        """Handle trailing window dropdown changes."""
        try:
            new_months = int(e.control.value)
            self.chart_component.trailing_months = new_months
            logger.info(f"Trailing window changed to {new_months} months")
            
            # Refresh chart if a product is selected
            if self.state.selected_product:
                self.show_product_cost_chart(self.state.selected_product)
        except ValueError:
            logger.warning(f"Invalid trailing window value: {e.control.value}")

    def on_chart_click(self, selected_date: datetime, selected_cost: float, spot_index: int):
        """Handle chart click events to update ingredient breakdown for selected time point."""
        
        if not self.state.selected_product:
            logger.warning("No product selected for chart click")
            return
            
        if not self.state.current_recipe_ingredients:
            logger.warning("No current recipe ingredients available")
            return
            
        # Calculate cost basis for the selected time point using cost calculator
        selected_cost_basis = self.cost_calculator.calculate_cost_basis_for_window_at_date(
            selected_date, self.chart_component.trailing_months
        )
        
        if not selected_cost_basis:
            logger.warning(f"No cost basis data available for {selected_date}")
            return
        
        # Update the ingredient breakdown section
        self._update_ingredient_breakdown_display(
            self.state.selected_product, 
            self.state.current_recipe_ingredients, 
            selected_date, 
            selected_cost_basis
        )

    def _update_ingredient_breakdown_display(self, recipe_name: str, ingredients: dict, 
                                           selected_date: datetime, cost_basis: dict):
        """Update the ingredient breakdown display for a specific time point."""
        try:
            # Create breakdown using UI builder
            new_breakdown = self.ui_builder.create_ingredient_breakdown(
                recipe_name, ingredients, selected_date, cost_basis
            )
            
            # Find or create the ingredient breakdown section
            if len(self.chart_column.controls) >= 8:  # Should have the breakdown section
                # Update the existing breakdown
                self.chart_column.controls[-1] = new_breakdown
                self.update()
            else:
                logger.warning(f"Chart column has only {len(self.chart_column.controls)} controls, expected at least 8")
        except Exception as e:
            logger.error(f"Error updating ingredient breakdown display: {e}")

    def show_error(self, error_message: str):
        """Log error message."""
        logger.error(f"Error: {error_message}")