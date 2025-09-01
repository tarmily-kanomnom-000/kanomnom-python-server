"""
Grist service - interface for Grist table operations.
Handles API communication, caching, data processing, and filtering.
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from core.cache.cache_service import get_cache_service
import os
import requests

logger = logging.getLogger(__name__)

# Grist API configuration
GRIST_ENDPOINT = os.getenv("GRIST_ENDPOINT")
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_OPEX_DOCUMENT_ID = os.getenv("GRIST_OPEX_DOCUMENT_ID")
GRIST_MATERIAL_PURCHASES_TABLE_ID = os.getenv("GRIST_MATERIAL_PURCHASES_TABLE_ID")


def get_grist_table():
    """
    Fetch Grist table data and return as pandas DataFrame with proper data types.
    Uses caching to avoid repeated API calls.
    """
    # Initialize cache service
    cache_service = get_cache_service()
    
    # Try to get data from cache first
    cached_df = cache_service.material_purchases_cache.get_dataframe_from_cache()
    if cached_df is not None:
        logger.info(f"Using cached material purchases data: {len(cached_df)} records")
        return cached_df
    
    # Cache miss - fetch fresh data from API
    logger.info("Cache miss - fetching fresh data from Grist API")
    
    table_records_response = requests.get(
        url=f"{GRIST_ENDPOINT}/api/docs/{GRIST_OPEX_DOCUMENT_ID}/tables/{GRIST_MATERIAL_PURCHASES_TABLE_ID}/records",
        headers={"Authorization": f"Bearer {GRIST_API_KEY}"},
    )
    
    if table_records_response.status_code != 200:
        logger.error(f"Failed to fetch Grist table: {table_records_response.status_code} - {table_records_response.text}")
        return pd.DataFrame()
    
    try:
        data = table_records_response.json()
        records = data.get("records", [])
        
        if not records:
            logger.warning("No records found in response")
            return pd.DataFrame()
        
        # Extract fields from all records
        rows = []
        for record in records:
            row = record.get("fields", {})
            row['id'] = record.get("id")  # Add the record ID
            rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        if df.empty:
            return df
        
        # Convert data types
        logger.info("Converting data types...")
        
        # Convert Purchase_Date from Unix timestamp to datetime
        if 'Purchase_Date' in df.columns:
            df['Purchase_Date'] = pd.to_datetime(df['Purchase_Date'], unit='s')
            logger.info(f"Converted Purchase_Date to datetime. Range: {df['Purchase_Date'].min()} to {df['Purchase_Date'].max()}")
            
            # Debug: Show some sample dates
            logger.info(f"Sample dates from results: {df['Purchase_Date'].head(3).tolist()}")
        
        # Convert numeric columns
        numeric_columns = [
            'quantity_purchased', 'package_size', 'purchase_price_per_item', 
            'tax_rate', 'shipping_fee', 'purchase_unit_price', 'total_cost', 
            'total_unit_cost', 'normal_price_per_item2', 'purchase_price_per_item2'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert ID to integer
        if 'id' in df.columns:
            df['id'] = pd.to_numeric(df['id'], errors='coerce').astype(int)
        
        # Clean string columns (remove extra whitespace)
        string_columns = [
            'material2', 'category', 'brand', 'unit', 'purchase_source', 
            'rating', 'notes', 'material', 'notes2'
        ]
        
        for col in string_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' string with actual NaN
                df[col] = df[col].replace('nan', pd.NA)
        
        logger.info(f"DataFrame created with {len(df)} rows and {len(df.columns)} columns")
        logger.info(f"DataFrame dtypes: {df.dtypes.to_dict()}")
        
        # Save to cache for future use
        cache_service.material_purchases_cache.save_cache(df)
        
        # Notify dependency manager that material_purchases cache has been updated
        cache_service.invalidate_dependent_caches("material_purchases")
        
        return df
        
    except Exception as e:
        logger.error(f"Error processing Grist response: {e}")
        return pd.DataFrame()


class DataFilterManager:
    """Manages data filtering operations for Grist data."""
    
    def __init__(self):
        self.grist_dataframe = None
        self.filtered_grist_dataframe = None
        self.start_date = None
        self.end_date = None
        self._set_default_date_range()
    
    def _set_default_date_range(self):
        """Set default date range to 3 years ago until now."""
        now = datetime.now()
        three_years_ago = now - timedelta(days=1095)
        self.start_date = three_years_ago
        self.end_date = now
    
    def load_grist_data(self):
        """Load Grist data and apply initial time filtering."""
        try:
            logger.info("Loading Grist material purchases data...")
            self.grist_dataframe = get_grist_table()
            
            if self.grist_dataframe.empty:
                logger.warning("No Grist data loaded")
                return
            
            logger.info(f"Loaded {len(self.grist_dataframe)} records from Grist")
            
            # Apply initial time filter
            self.apply_time_filter()
            
        except Exception as e:
            logger.error(f"Error loading Grist data: {e}")
            self.grist_dataframe = pd.DataFrame()
            self.filtered_grist_dataframe = pd.DataFrame()
    
    def apply_time_filter(self):
        """Apply time range filter to the Grist dataframe."""
        if self.grist_dataframe is None or self.grist_dataframe.empty:
            logger.warning("No Grist data to filter")
            self.filtered_grist_dataframe = pd.DataFrame()
            return
        
        try:
            df = self.grist_dataframe.copy()
            
            # Check if Purchase_Date column exists
            if 'Purchase_Date' not in df.columns:
                logger.warning("Purchase_Date column not found in Grist data")
                self.filtered_grist_dataframe = df
                return
            
            # Convert start and end dates to pandas datetime for comparison
            start_filter = pd.to_datetime(self.start_date) if self.start_date else None
            end_filter = pd.to_datetime(self.end_date) if self.end_date else None
            
            # Apply filters
            if start_filter and end_filter:
                mask = (df['Purchase_Date'] >= start_filter) & (df['Purchase_Date'] <= end_filter)
                filtered_df = df[mask]
                logger.info(f"Applied date filter: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
            elif start_filter:
                mask = df['Purchase_Date'] >= start_filter
                filtered_df = df[mask]
                logger.info(f"Applied start date filter: from {self.start_date.strftime('%Y-%m-%d')}")
            elif end_filter:
                mask = df['Purchase_Date'] <= end_filter
                filtered_df = df[mask]
                logger.info(f"Applied end date filter: until {self.end_date.strftime('%Y-%m-%d')}")
            else:
                filtered_df = df
                logger.info("No date filter applied")
            
            self.filtered_grist_dataframe = filtered_df
            
            logger.info(f"Filtered from {len(df)} to {len(filtered_df)} records")
            if len(filtered_df) > 0:
                logger.info(f"Filtered date range: {filtered_df['Purchase_Date'].min()} to {filtered_df['Purchase_Date'].max()}")
                logger.info(f"Unique materials in filtered data: {filtered_df['material2'].nunique()}")
            
        except Exception as e:
            logger.error(f"Error applying time filter: {e}")
            self.filtered_grist_dataframe = self.grist_dataframe.copy() if self.grist_dataframe is not None else pd.DataFrame()
    
    def update_date_range(self, start_date: datetime, end_date: datetime):
        """Update the date range and reapply filter."""
        self.start_date = start_date
        self.end_date = end_date
        self.apply_time_filter()
    
    def get_filtered_data(self) -> pd.DataFrame:
        """Get the current filtered dataframe."""
        return self.filtered_grist_dataframe if self.filtered_grist_dataframe is not None else pd.DataFrame()