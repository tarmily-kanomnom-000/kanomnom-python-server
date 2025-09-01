"""
Complete cost calculation system for product costs.
Handles material cost basis calculation, ingredient cost lookup, time series analysis, and caching.
"""

import logging
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional
from cachetools import cachedmethod, LRUCache
from operator import attrgetter
from shared.unit_converter import get_liquid_density, get_special_conversion_factor
from .semantic_ingredient_matcher import get_semantic_matcher
from .openai_client import create_openai_client, APIBackend
from core.cache.cache_dependency_manager import get_cache_dependency_manager

logger = logging.getLogger(__name__)


class MaterialCostCalculator:
    """Complete cost calculation system with cost basis, semantic matching, and time series analysis."""
    
    def __init__(self):
        self.material_cost_basis = {}
        self.data_manager = None  # Will be set externally for time series calculations
        self._cache = LRUCache(maxsize=128)  # Cache for expensive operations
        self._register_with_dependency_manager()
        
    def calculate_material_cost_basis(self, filtered_grist_dataframe: pd.DataFrame) -> dict[str, dict[str, float]]:
        """
        Calculate cost basis per unit for each material from filtered Grist data.
        Groups by material2 and unit, then calculates weighted average cost per unit.
        
        Returns:
            dict[str, dict[str, float]]: {material_name: {unit: cost_per_unit}}
        """
        cost_basis = self._calculate_cost_basis_from_dataframe(filtered_grist_dataframe)
        logger.info(f"Calculated cost basis for {len(cost_basis)} materials")
        self.material_cost_basis = cost_basis
        return cost_basis

    def _try_unit_conversion(self, material_name: str, target_unit: str, material_costs: dict[str, float]) -> float:
        """
        Try to convert between units using special conversions first, then density.
        
        Args:
            material_name: Name of the material
            target_unit: Target unit from recipe
            material_costs: Available costs {unit: cost}
            
        Returns:
            float: Converted cost, or None if conversion not possible
        """
        # First try special conversions for discrete items
        for available_unit, cost in material_costs.items():
            special_factor = get_special_conversion_factor(material_name, available_unit, target_unit)
            if special_factor:
                return cost / special_factor  # cost per source unit / target units per source unit = cost per target unit
        
        # If recipe uses 'g' but we have 'mL' data, try density conversion
        if target_unit.lower() == 'g' and any(u.lower() == 'ml' for u in material_costs.keys()):
            # Get cost per mL (find the mL unit case-insensitively)
            cost_per_ml = None
            for available_unit, cost in material_costs.items():
                if available_unit.lower() == 'ml':
                    cost_per_ml = cost
                    break
            
            if cost_per_ml is not None:
                # Use centralized density conversion: 1mL costs X, so 1g costs X/density
                density = get_liquid_density(material_name)
                if density is not None:
                    cost_per_g = cost_per_ml / density
                    return cost_per_g
        
        # If recipe uses 'mL' but we have 'g' data, try reverse conversion
        elif target_unit.lower() == 'ml' and any(u.lower() == 'g' for u in material_costs.keys()):
            # Get cost per g (find the g unit case-insensitively)
            cost_per_g = None
            for available_unit, cost in material_costs.items():
                if available_unit.lower() == 'g':
                    cost_per_g = cost
                    break
            
            if cost_per_g is not None:
                # Use centralized density conversion: 1g costs X, so 1mL costs X*density
                density = get_liquid_density(material_name)
                if density is not None:
                    cost_per_ml = cost_per_g * density
                    return cost_per_ml
        
        return None

    # ============ CONSOLIDATED COST CALCULATION UTILITIES ============
    
    def set_data_manager(self, data_manager):
        """Set data manager for time series calculations."""
        self.data_manager = data_manager
    
    @cachedmethod(attrgetter('_cache'), key=lambda self: 'api_client')
    def _get_api_client(self):
        """Get or create the OpenAI API client (cached)."""
        logger.info("Creating and caching OpenAI client")
        return create_openai_client(backend=APIBackend.OPENAI)
    
    @cachedmethod(attrgetter('_cache'), key=lambda self: 'semantic_matcher')
    def _get_semantic_matcher(self):
        """Get or create the semantic matcher (cached)."""
        logger.info("Creating and caching semantic matcher")
        api_client = self._get_api_client()
        return get_semantic_matcher(api_client)
    
    def find_cost_in_basis(self, material_name: str, unit: str, cost_basis: dict) -> Optional[float]:
        """Find cost for a material and unit in the cost basis, with unit conversion if needed."""
        material_costs = cost_basis.get(material_name, {})
        
        # Try exact unit match first
        if unit in material_costs:
            return material_costs[unit]
        
        # Try case-insensitive unit matching
        for available_unit, cost in material_costs.items():
            if unit.lower() == available_unit.lower():
                return cost
        
        # Try unit conversion (reuse existing logic)
        converted_cost = self._try_unit_conversion(material_name, unit, material_costs)
        if converted_cost is not None:
            return converted_cost
        
        return None
    
    def calculate_ingredient_costs(self, ingredients: dict, cost_basis: dict) -> tuple[list[tuple], float]:
        """
        Calculate ingredient costs with complete breakdown using semantic matching.
        
        Args:
            ingredients: dict of {ingredient: (amount, unit)}
            cost_basis: Cost basis data
            
        Returns:
            tuple of (sorted_ingredients_list, total_cost) where sorted_ingredients_list contains
            (ingredient, amount, unit, cost_per_unit, ingredient_cost, match_info) tuples
        """
        ingredient_costs = []
        total_product_cost = 0.0
        
        # Get semantic matches for all ingredients at once
        ingredient_list = list(ingredients.keys())
        available_materials = list(cost_basis.keys())
        
        # Use cached semantic matcher to get matches (it handles caching internally)
        semantic_matcher = self._get_semantic_matcher()
        match_results = semantic_matcher.find_best_matches(ingredient_list, available_materials)
        
        # Create lookup dict for matches
        match_lookup = {result.ingredient: result for result in match_results}
        
        for ingredient, (amount, unit) in ingredients.items():
            # Get match result from semantic matcher
            match_result = match_lookup.get(ingredient)
            if match_result and match_result.matched_material:
                matched_material = match_result.matched_material
                match_info = {'matched_material': matched_material, 'match_type': match_result.match_type}
            else:
                # Fallback to exact match
                matched_material = ingredient
                match_info = {'matched_material': ingredient, 'match_type': 'exact'}
            
            # Look up cost using the matched material
            cost_per_unit = self.find_cost_in_basis(matched_material, unit, cost_basis)
            
            if cost_per_unit is not None:
                ingredient_cost = amount * cost_per_unit
                total_product_cost += ingredient_cost
            else:
                ingredient_cost = 0.0
            
            ingredient_costs.append((ingredient, amount, unit, cost_per_unit, ingredient_cost, match_info))
        
        # Sort ingredients by cost (descending) - most expensive ingredients first
        sorted_ingredients = sorted(ingredient_costs, key=lambda x: x[4], reverse=True)
        
        return sorted_ingredients, total_product_cost

    # ============ TIME SERIES CALCULATION METHODS ============
    
    def calculate_cost_time_series(self, product_name: str, product_ingredients: dict, 
                                 trailing_months: int = 6) -> list[tuple[datetime, float]]:
        """
        Calculate cost time series for a product with monthly time steps.
        
        Args:
            product_name: Name of the product
            product_ingredients: dict of {ingredient: (amount, unit)}
            trailing_months: Number of months to look back for cost calculation
            
        Returns:
            list of (datetime, cost) tuples representing the time series
        """
        # Validate prerequisites
        validation_result = self._validate_time_series_prerequisites()
        if validation_result is not None:
            return validation_result
        
        # Get date range and time points
        time_points = self._get_time_series_points()
        logger.info(f"Calculating cost time series for {product_name} with {len(time_points)} time points")
        
        # Calculate costs for each time point
        cost_series = self._calculate_costs_for_time_points(
            time_points, product_ingredients, trailing_months
        )
        
        logger.info(f"Generated {len(cost_series)} cost data points for {product_name}")
        return cost_series
    
    def _validate_time_series_prerequisites(self) -> Optional[list]:
        """Validate that prerequisites for time series calculation are met."""
        if self.data_manager is None or self.data_manager.grist_dataframe is None or self.data_manager.grist_dataframe.empty:
            logger.warning("No Grist data available for time series calculation")
            return []
        return None
    
    def _get_time_series_points(self) -> list[datetime]:
        """Get the time points for the time series calculation."""
        df = self.data_manager.grist_dataframe
        min_date = df['Purchase_Date'].min()
        max_date = df['Purchase_Date'].max()
        
        logger.debug(f"Data date range: {min_date} to {max_date}")
        return self._generate_monthly_time_points(min_date, max_date)
    
    def _calculate_costs_for_time_points(self, time_points: list[datetime], 
                                       product_ingredients: dict, trailing_months: int) -> list[tuple[datetime, float]]:
        """Calculate product costs for each time point."""
        cost_series = []
        df = self.data_manager.grist_dataframe
        
        for time_point in time_points:
            cost = self._calculate_cost_at_time_point(
                time_point, df, product_ingredients, trailing_months
            )
            if cost is not None:
                cost_series.append((time_point, cost))
                logger.debug(f"Cost at {time_point}: ${cost:.4f}")
        
        return cost_series
    
    def _calculate_cost_at_time_point(self, time_point: datetime, df: pd.DataFrame,
                                    product_ingredients: dict, trailing_months: int) -> Optional[float]:
        """Calculate product cost at a specific time point."""
        # Calculate trailing window start date
        window_start = time_point - relativedelta(months=trailing_months)
        
        # Filter data to trailing window
        window_data = df[
            (df['Purchase_Date'] >= window_start) & 
            (df['Purchase_Date'] <= time_point)
        ]
        
        if window_data.empty:
            logger.debug(f"No data for window ending {time_point}")
            return None
            
        # Calculate cost basis for this window
        temp_cost_basis = self._calculate_cost_basis_from_dataframe(window_data)
        
        # Calculate product cost using the window-specific cost basis
        _, product_cost = self.calculate_ingredient_costs(product_ingredients, temp_cost_basis)
        
        return product_cost
    
    def _generate_monthly_time_points(self, start_date: datetime, end_date: datetime) -> list[datetime]:
        """Generate monthly time points between start and end dates."""
        time_points = []
        current = start_date.replace(day=1)  # Start at beginning of month
        
        while current <= end_date:
            time_points.append(current)
            current += relativedelta(months=1)
            
        return time_points
    
    def _calculate_cost_basis_from_dataframe(self, dataframe: pd.DataFrame) -> dict[str, dict[str, float]]:
        """Calculate cost basis from any pandas DataFrame with purchase data."""
        if dataframe is None or dataframe.empty:
            logger.warning("No data available for cost basis calculation")
            return {}
        
        try:
            df = dataframe.copy()
            
            # Check required columns exist
            required_cols = ['material2', 'package_size', 'quantity_purchased', 'total_cost', 'unit']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                return {}
            
            # Calculate total amount bought for each row
            df['total_amount_bought'] = df['package_size'] * df['quantity_purchased']
            
            # Group by material2 and unit
            grouped = df.groupby(['material2', 'unit']).agg({
                'total_amount_bought': 'sum',
                'total_cost': 'sum'
            }).reset_index()
            
            # Calculate cost per unit
            grouped['cost_per_unit'] = grouped['total_cost'] / grouped['total_amount_bought']
            
            # Convert to nested dictionary
            cost_basis = {}
            for _, row in grouped.iterrows():
                material = row['material2']
                unit = row['unit']
                cost_per_unit = row['cost_per_unit']
                
                if material not in cost_basis:
                    cost_basis[material] = {}
                
                cost_basis[material][unit] = cost_per_unit
            
            return cost_basis
            
        except Exception as e:
            logger.error(f"Error calculating cost basis: {e}")
            return {}

    def calculate_cost_basis_for_window_at_date(self, selected_date: datetime, trailing_months: int) -> dict[str, dict[str, float]]:
        """Calculate cost basis for a specific date using trailing window."""
        if self.data_manager is None:
            return {}
            
        # Calculate trailing window start date
        window_start = selected_date - relativedelta(months=trailing_months)
        
        # Filter data to trailing window
        df = self.data_manager.grist_dataframe
        window_data = df[
            (df['Purchase_Date'] >= window_start) & 
            (df['Purchase_Date'] <= selected_date)
        ]
        
        if window_data.empty:
            logger.warning(f"No data available for time point {selected_date}")
            return {}
            
        # Use the existing cost calculation method
        return self._calculate_cost_basis_from_dataframe(window_data)
    
    def _register_with_dependency_manager(self):
        """Register this calculator's cache with the dependency manager."""
        try:
            dependency_manager = get_cache_dependency_manager()
            # Register our cache with a unique name
            dependency_manager.register_cache("cost_calculation", self._cache)
            
            # Set up dependencies: recipe → cost_calculation, material_purchases → cost_calculation
            dependency_manager.add_dependency("recipe", "cost_calculation")
            dependency_manager.add_dependency("material_purchases", "cost_calculation")
            
            logger.info("Registered cost calculation cache with dependency manager")
        except Exception as e:
            logger.error(f"Failed to register with dependency manager: {e}")