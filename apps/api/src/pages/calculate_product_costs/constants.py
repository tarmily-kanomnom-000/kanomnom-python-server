"""Constants for the product costs calculator."""

from shared.ui.constants import COMMON_UI_LAYOUT

# UI Layout Constants (shared baseline values)
COLUMN_SPACING: int = COMMON_UI_LAYOUT.column_spacing
CONTAINER_PADDING: int = COMMON_UI_LAYOUT.container_padding
CONTAINER_BORDER_RADIUS: int = COMMON_UI_LAYOUT.container_border_radius
BUTTON_SPACING: int = COMMON_UI_LAYOUT.button_spacing
TEXT_FIELD_WIDTH: int = COMMON_UI_LAYOUT.text_field_width

# Button and Component Sizes
PRODUCT_BUTTON_WIDTH = 250
PRODUCT_BUTTON_HEIGHT = 50
DATE_FIELD_WIDTH = 150

# Chart and Display Constants
DEFAULT_TRAILING_MONTHS = 12
CHART_HEIGHT = 400
CHART_WIDTH = 800

# Semantic Matching Constants
SEMANTIC_MATCH_CACHE_SIZE = 1000

# Cost Calculation Constants
DEFAULT_COST_BASIS_WINDOW_MONTHS = 6
INGREDIENT_DISPLAY_PRECISION = 4  # Decimal places for ingredient amounts
COST_DISPLAY_PRECISION = 2  # Decimal places for cost amounts

# Date Range Defaults
DEFAULT_DATE_FORMAT = "%Y-%m-%d"

# Text Sizes
TITLE_TEXT_SIZE = 24
SUBTITLE_TEXT_SIZE = 18
BODY_TEXT_SIZE = 14
SMALL_TEXT_SIZE = 12
COST_TEXT_SIZE = 16

# Padding and Spacing
COST_TEXT_PADDING_LEFT = 20
INGREDIENT_ROW_PADDING = 5
COPY_SECTION_PADDING = 10

# Cache Configuration
COST_CALCULATOR_CACHE_SIZE = 128
