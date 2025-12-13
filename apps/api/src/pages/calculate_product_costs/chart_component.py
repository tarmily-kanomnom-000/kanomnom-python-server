"""
Chart component for displaying cost over time graphs.
"""

from datetime import datetime
from typing import Optional

import flet as ft


class CostChartComponent:
    """Creates line charts for displaying cost over time."""

    def __init__(self):
        self.trailing_months = 6  # Default trailing window

    def create_trailing_window_input(self, on_change_callback) -> ft.Container:
        """Create spinner input for configurable trailing window."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("📊 Graph Settings", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            ft.Text("Trailing Window:", size=14),
                            ft.Dropdown(
                                value=str(self.trailing_months),
                                width=120,
                                options=[
                                    ft.dropdown.Option("1", "1 month"),
                                    ft.dropdown.Option("2", "2 months"),
                                    ft.dropdown.Option("3", "3 months"),
                                    ft.dropdown.Option("6", "6 months"),
                                    ft.dropdown.Option("12", "12 months"),
                                    ft.dropdown.Option("18", "18 months"),
                                    ft.dropdown.Option("24", "24 months"),
                                    ft.dropdown.Option("36", "36 months"),
                                ],
                                on_change=on_change_callback,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10,
                    ),
                ]
            ),
            padding=10,
            margin=ft.margin.only(bottom=20),
            bgcolor=ft.Colors.BLUE_GREY_100,
            border_radius=5,
        )

    def create_cost_chart(
        self, product_name: str, cost_data: list[tuple[datetime, float]], on_chart_click=None
    ) -> ft.Container:
        """
        Create a line chart showing cost over time.

        Args:
            product_name: Name of the product
            cost_data: list of (datetime, cost) tuples
            on_chart_click: Callback function for chart click events

        Returns:
            ft.Container containing the chart
        """
        if not cost_data:
            return ft.Container(
                content=ft.Text(
                    "No cost data available for the selected time period",
                    size=16,
                    color=ft.Colors.GREY,
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=40,
                alignment=ft.alignment.center,
            )

        # Convert data to chart format
        chart_data_points = []
        min_cost = float("inf")
        max_cost = float("-inf")

        for i, (date, cost) in enumerate(cost_data):
            # Create tooltip with formatted date and cost
            tooltip = f"{date.strftime('%B %Y')}\n${cost:.4f}"
            chart_data_points.append(
                ft.LineChartDataPoint(
                    x=i,
                    y=cost,
                    tooltip=tooltip,
                    tooltip_style=ft.TextStyle(color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                )
            )
            min_cost = min(min_cost, cost)
            max_cost = max(max_cost, cost)

        # Add some padding to y-axis range
        cost_range = max_cost - min_cost
        y_padding = cost_range * 0.1 if cost_range > 0 else 0.1
        y_min = max(0, min_cost - y_padding)  # Don't go below 0
        y_max = max_cost + y_padding

        # Calculate average cost for the horizontal line
        costs = [cost for _, cost in cost_data]
        avg_cost = sum(costs) / len(costs) if costs else 0

        # Create average cost line data points (straight horizontal line)
        avg_line_points = [
            ft.LineChartDataPoint(x=0, y=avg_cost),
            ft.LineChartDataPoint(x=len(cost_data) - 1, y=avg_cost),
        ]

        # Create chart data for main cost line
        chart_data = ft.LineChartData(
            data_points=chart_data_points,
            stroke_width=3,
            color=ft.Colors.BLUE,
            curved=False,
            stroke_cap_round=True,
        )

        # Create chart data for average cost line
        avg_line_data = ft.LineChartData(
            data_points=avg_line_points,
            stroke_width=2,
            color=ft.Colors.ORANGE,
            curved=False,
        )

        # Create chart
        chart = ft.LineChart(
            data_series=[chart_data, avg_line_data],
            border=ft.border.all(1, ft.Colors.GREY_400),
            horizontal_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_300, width=1, dash_pattern=[3, 3]),
            vertical_grid_lines=ft.ChartGridLines(color=ft.Colors.GREY_300, width=1, dash_pattern=[3, 3]),
            left_axis=ft.ChartAxis(
                title=ft.Text("Cost ($)", size=12, weight=ft.FontWeight.BOLD),
                title_size=40,
                labels_size=40,
            ),
            bottom_axis=ft.ChartAxis(
                title=ft.Text("Time", size=12, weight=ft.FontWeight.BOLD),
                title_size=40,
                labels_size=40,
                labels=[
                    ft.ChartAxisLabel(value=i, label=ft.Text(date.strftime("%Y-%m"), size=10))
                    for i, (date, _) in enumerate(cost_data[:: max(1, len(cost_data) // 6)])  # Show max 6 labels
                ],
            ),
            min_y=y_min,
            max_y=y_max,
            min_x=0,
            max_x=len(cost_data) - 1,
            expand=True,
            tooltip_bgcolor=ft.Colors.BLACK87,  # Dark background for better contrast
            interactive=True,  # Enable hover interactions
            on_chart_event=self._create_chart_event_handler(cost_data, on_chart_click) if on_chart_click else None,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        f"Cost Over Time: {product_name}",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"Trailing Window: {self.trailing_months} months | Data Points: {len(cost_data)} | Average: ${avg_cost:.4f}",
                        size=12,
                        color=ft.Colors.GREY_600,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Blue line: Cost over time | Orange line: Average cost",
                        size=10,
                        color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        content=chart,
                        height=400,
                        padding=10,
                    ),
                ]
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            padding=15,
        )

    def create_cost_summary(self, cost_data: list[tuple[datetime, float]]) -> ft.Container:
        """Create a summary of cost statistics."""
        if not cost_data:
            return ft.Container()

        costs = [cost for _, cost in cost_data]

        avg_cost = sum(costs) / len(costs)
        min_cost = min(costs)
        max_cost = max(costs)

        # Find dates for min and max costs
        min_date = next(date for date, cost in cost_data if cost == min_cost)
        max_date = next(date for date, cost in cost_data if cost == max_cost)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("📈 Cost Statistics", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Average Cost", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"${avg_cost:.4f}", size=14, color=ft.Colors.BLUE),
                                ],
                                expand=1,
                            ),
                            ft.Column(
                                [
                                    ft.Text("Minimum Cost", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"${min_cost:.4f}", size=14, color=ft.Colors.GREEN),
                                    ft.Text(min_date.strftime("%Y-%m"), size=10, color=ft.Colors.GREY),
                                ],
                                expand=1,
                            ),
                            ft.Column(
                                [
                                    ft.Text("Maximum Cost", size=12, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"${max_cost:.4f}", size=14, color=ft.Colors.RED),
                                    ft.Text(max_date.strftime("%Y-%m"), size=10, color=ft.Colors.GREY),
                                ],
                                expand=1,
                            ),
                        ]
                    ),
                ]
            ),
            padding=15,
            bgcolor=ft.Colors.BLUE_GREY_50,
            border_radius=8,
            margin=ft.margin.only(top=10),
        )

    def _create_chart_event_handler(self, cost_data: list[tuple[datetime, float]], on_chart_click):
        """Create a simplified chart event handler for click events."""

        def handle_chart_event(e):
            # Handle chart click events by extracting spot index
            if hasattr(e, "spots") and e.spots:
                for spot in e.spots:
                    spot_index = self._extract_spot_index(spot)
                    if spot_index is not None and 0 <= spot_index < len(cost_data):
                        selected_date, selected_cost = cost_data[spot_index]
                        on_chart_click(selected_date, selected_cost, spot_index)
                        return

        return handle_chart_event

    def _extract_spot_index(self, spot) -> Optional[int]:
        """Extract spot index from chart spot data."""
        if isinstance(spot, dict):
            return spot.get("spot_index")
        elif hasattr(spot, "spot_index"):
            return spot.spot_index
        return None
