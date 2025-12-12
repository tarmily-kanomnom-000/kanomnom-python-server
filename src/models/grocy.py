from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreatedQuantityUnit(BaseModel):
    name: str
    identifier: int


class InitializeInstanceResponse(BaseModel):
    instance_index: str
    quantity_unit_identifiers: dict[str, int]
    created_units: list[CreatedQuantityUnit]


class GrocyLocationPayload(BaseModel):
    id: int
    name: str
    description: str | None = None
    row_created_timestamp: datetime
    is_freezer: bool
    active: bool


class InstanceAddressPayload(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str


class InstanceSummary(BaseModel):
    instance_index: str
    location_name: str | None = None
    location_types: list[str] = Field(default_factory=list)
    address: InstanceAddressPayload | None = None
    locations: list[GrocyLocationPayload] = Field(default_factory=list)


class ListInstancesResponse(BaseModel):
    instances: list[InstanceSummary]


class GrocyProductInventoryEntry(BaseModel):
    id: int
    name: str
    description: str | None = None
    product_group_id: int | None = None
    active: bool
    location_id: int | None = None
    shopping_location_id: int | None = None
    qu_id_purchase: int | None = None
    qu_id_stock: int | None = None
    min_stock_amount: float
    default_best_before_days: int
    default_best_before_days_after_open: int
    default_best_before_days_after_freezing: int
    default_best_before_days_after_thawing: int
    picture_file_name: str | None = None
    enable_tare_weight_handling: bool
    tare_weight: float
    not_check_stock_fulfillment_for_recipes: bool
    parent_product_id: int | None = None
    calories: float
    cumulate_min_stock_amount_of_sub_products: bool
    due_type: int | None = None
    quick_consume_amount: float
    hide_on_stock_overview: bool
    default_stock_label_type: int | None = None
    should_not_be_frozen: bool
    treat_opened_as_out_of_stock: bool
    no_own_stock: bool
    default_consume_location_id: int | None = None
    move_on_open: bool
    row_created_timestamp: datetime
    qu_id_consume: int | None = None
    auto_reprint_stock_label: bool
    quick_open_amount: float
    qu_id_price: int | None = None
    disable_open: bool
    default_purchase_price_type: int | None = None
    quantity_on_hand: float
    last_stock_updated_at: datetime
    product_group_name: str | None = None


class GrocyProductsResponse(BaseModel):
    instance_index: str
    products: list[GrocyProductInventoryEntry]


__all__ = [
    "CreatedQuantityUnit",
    "InitializeInstanceResponse",
    "InstanceAddressPayload",
    "GrocyLocationPayload",
    "GrocyProductInventoryEntry",
    "GrocyProductsResponse",
    "InstanceSummary",
    "ListInstancesResponse",
]
