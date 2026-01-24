import logging

import flet as ft
from pages.calculate_ingredients.page import IngredientsCalculatorContent
from pages.calculate_product_costs.page import ProductCostsCalculatorContent
from pages.material_purchase_runs.page import MaterialPurchaseRunsContent

# Configure logging for debugging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def home_view():
    """Create the home page view with navigation"""
    return ft.View(
        route="/",
        controls=[
            ft.AppBar(
                title=ft.Text("🧁 Ka-nom Nom Server"), bgcolor=ft.Colors.SURFACE_VARIANT
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Welcome to Ka-nom Nom Server",
                            size=32,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Choose a tool to get started:",
                            size=18,
                            text_align=ft.TextAlign.CENTER,
                            color=ft.Colors.GREY,
                        ),
                        ft.Container(height=20),  # Spacer
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column(
                                    [
                                        ft.ListTile(
                                            leading=ft.Icon(
                                                ft.Icons.CALCULATE, size=40
                                            ),
                                            title=ft.Text(
                                                "Raw Ingredients Calculator",
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            subtitle=ft.Text(
                                                "Calculate raw ingredients from product recipes"
                                            ),
                                            on_click=lambda e: e.page.go(
                                                "/calculate_ingredients"
                                            ),
                                        ),
                                        ft.ListTile(
                                            leading=ft.Icon(
                                                ft.Icons.ATTACH_MONEY, size=40
                                            ),
                                            title=ft.Text(
                                                "Product Cost Calculator",
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            subtitle=ft.Text(
                                                "Review material costs by recipe"
                                            ),
                                            on_click=lambda e: e.page.go(
                                                "/calculate_product_costs"
                                            ),
                                        ),
                                        ft.ListTile(
                                            leading=ft.Icon(
                                                ft.Icons.INVENTORY, size=40
                                            ),
                                            title=ft.Text(
                                                "Material Purchase Runs",
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            subtitle=ft.Text(
                                                "Forecast upcoming supply runs"
                                            ),
                                            on_click=lambda e: e.page.go(
                                                "/material_purchase_runs"
                                            ),
                                        ),
                                    ]
                                ),
                                padding=20,
                            )
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=20,
                ),
                padding=40,
                expand=True,
            ),
        ],
    )


def main(page: ft.Page):
    page.title = "Ingredients Calculator"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    # Try to disable any debug/banner elements
    try:
        page.overlay.clear()
        page.banner = None
        page.snack_bar = None
        # Try to disable debug mode or dev tools
        page.debug = False
        page.rtl = False
        page.show_semantics_debugger = False

        # Try to add CSS to hide banner elements
        page.add_css = """
        .flet-banner, [data-testid="banner"], .banner, .debug-banner {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }
        """
    except Exception:
        logger.exception("Failed to disable Flet debug/banner UI elements")

    def route_change(route):
        page.views.clear()

        if page.route == "/calculate_ingredients":
            # Calculate ingredients page
            calculator = IngredientsCalculatorContent(page)
            calculator.build_content()
            page.views.append(
                ft.View(
                    "/calculate_ingredients", [calculator], scroll=ft.ScrollMode.AUTO
                )
            )
        elif page.route == "/calculate_product_costs":
            # Calculate product costs page
            calculator = ProductCostsCalculatorContent(page)
            calculator.build_content()
            page.views.append(
                ft.View(
                    "/calculate_product_costs", [calculator], scroll=ft.ScrollMode.AUTO
                )
            )
        elif page.route == "/material_purchase_runs":
            analysis = MaterialPurchaseRunsContent(page)
            analysis.build_content()
            page.views.append(
                ft.View(
                    "/material_purchase_runs", [analysis], scroll=ft.ScrollMode.AUTO
                )
            )
        elif page.route == "/" or page.route == "":
            # Home page with navigation
            home_content = ft.Column(
                controls=[
                    ft.Text(
                        "Welcome to Ka-Nom Nom Tools",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Select a tool to get started:", size=18),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "🧮 Calculate Ingredients",
                        on_click=lambda _: page.go("/calculate_ingredients"),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            padding=ft.Padding(20, 15, 20, 15),
                        ),
                        width=300,
                        height=60,
                    ),
                    ft.ElevatedButton(
                        "💰 Calculate Product Costs",
                        on_click=lambda _: page.go("/calculate_product_costs"),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.SECONDARY,
                            color=ft.Colors.ON_SECONDARY,
                            padding=ft.Padding(20, 15, 20, 15),
                        ),
                        width=300,
                        height=60,
                    ),
                    ft.ElevatedButton(
                        "📦 Material Purchase Runs",
                        on_click=lambda _: page.go("/material_purchase_runs"),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.TEAL,
                            color=ft.Colors.WHITE,
                            padding=ft.Padding(20, 15, 20, 15),
                        ),
                        width=300,
                        height=60,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
            page.views.append(ft.View("/", [home_content], scroll=ft.ScrollMode.AUTO))
        else:
            # Unknown route - redirect to home
            page.go("/")
            return

        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Start with the home route
    page.go("/")


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP)
