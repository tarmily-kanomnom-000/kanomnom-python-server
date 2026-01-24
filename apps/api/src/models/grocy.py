from __future__ import annotations

from datetime import date, datetime
from typing import Any

from core.grocy.note_metadata import InventoryLossReason
from pydantic import BaseModel, Field


class CreatedQuantityUnit(BaseModel):
    name: str
    identifier: int


class CreatedProductGroup(BaseModel):
    name: str
    identifier: int


class CreatedShoppingLocation(BaseModel):
    name: str
    identifier: int


class InitializeInstanceResponse(BaseModel):
    instance_index: str
    quantity_unit_identifiers: dict[str, int]
    created_units: list[CreatedQuantityUnit]
    product_group_identifiers: dict[str, int]
    created_product_groups: list[CreatedProductGroup]
    shopping_location_identifiers: dict[str, int]
    created_shopping_locations: list[CreatedShoppingLocation]


class GrocyLocationPayload(BaseModel):
    id: int
    name: str
    description: str | None = None
    row_created_timestamp: datetime
    is_freezer: bool
    active: bool


class GrocyShoppingLocationPayload(BaseModel):
    id: int
    name: str
    description: str | None = None
    row_created_timestamp: datetime
    active: bool


class GrocyQuantityUnitPayload(BaseModel):
    id: int
    name: str
    description: str | None = None
    name_plural: str | None = None
    plural_forms: str | None = None
    active: bool
    is_discrete: bool | None = None


class GrocyQuantityUnitsResponse(BaseModel):
    instance_index: str
    quantity_units: list[GrocyQuantityUnitPayload]


class GrocyQuantityUnitConversionPayload(BaseModel):
    from_unit_name: str
    to_unit_name: str
    factor: float


class GrocyQuantityUnitConversionsResponse(BaseModel):
    conversions: list[GrocyQuantityUnitConversionPayload]


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
    shopping_locations: list[GrocyShoppingLocationPayload] = Field(default_factory=list)


class ListInstancesResponse(BaseModel):
    instances: list[InstanceSummary]


class InventoryLossDetailPayload(BaseModel):
    reason: InventoryLossReason
    note: str | None = None


class InventoryCorrectionMetadataPayload(BaseModel):
    losses: list[InventoryLossDetailPayload] | None = None


class InventoryCorrectionRequest(BaseModel):
    new_amount: float
    best_before_date: date | None = None
    location_id: int | None = None
    note: str | None = None
    metadata: InventoryCorrectionMetadataPayload | None = None


class InventoryAdjustmentRequest(BaseModel):
    delta_amount: float
    best_before_date: date | None = None
    location_id: int | None = None
    note: str | None = None
    metadata: InventoryCorrectionMetadataPayload | None = None


class PurchaseEntryMetadataPayload(BaseModel):
    shipping_cost: float | None = None
    tax_rate: float | None = None
    brand: str | None = None
    package_size: float | None = None
    package_price: float | None = None
    package_quantity: float | None = None
    currency: str | None = None
    conversion_rate: float | None = None
    on_sale: bool = False


class PurchaseEntryRequest(BaseModel):
    amount: float
    price: float
    best_before_date: date | None = None
    purchased_date: date | None = None
    location_id: int | None = None
    shopping_location_id: int | None = None
    shopping_location_name: str | None = None
    note: str | None = None
    metadata: PurchaseEntryMetadataPayload | None = None


class PurchaseEntryDefaultsResponse(BaseModel):
    product_id: int
    shopping_location_id: int | None = None
    metadata: PurchaseEntryMetadataPayload


class PurchaseEntryDefaultsBatchRequest(BaseModel):
    product_ids: list[int] = Field(min_length=1)
    shopping_location_id: int | None = None


class PurchaseEntryDefaultsBatchResponse(BaseModel):
    defaults: list[PurchaseEntryDefaultsResponse]


class PurchaseEntryCalculationRequest(BaseModel):
    metadata: PurchaseEntryMetadataPayload


class PurchaseEntryCalculationResponse(BaseModel):
    amount: float
    unit_price: float
    total_usd: float


class ProductUnitConversionPayload(BaseModel):
    from_unit: str
    to_unit: str
    factor: float
    tare: float | None = None


class ProductDescriptionMetadataPayload(BaseModel):
    unit_conversions: list[ProductUnitConversionPayload] = Field(default_factory=list)


class ProductDescriptionMetadataUpdatePayload(BaseModel):
    product_id: int
    description: str | None = None
    description_metadata: ProductDescriptionMetadataPayload


class ProductDescriptionMetadataBatchRequest(BaseModel):
    updates: list[ProductDescriptionMetadataUpdatePayload] = Field(min_length=1)


class GrocyStockEntryPayload(BaseModel):
    id: int
    amount: float
    best_before_date: datetime | None = None
    purchased_date: datetime | None = None
    stock_id: str | None = None
    price: float | None = None
    open: bool
    opened_date: datetime | None = None
    row_created_timestamp: datetime
    location_id: int | None = None
    shopping_location_id: int | None = None
    note: str | None = None
    note_metadata: dict[str, Any] | None = None


class GrocyProductInventoryEntry(BaseModel):
    id: int
    name: str
    description: str | None = None
    description_metadata: ProductDescriptionMetadataPayload | None = None
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
    last_stock_updated_at: datetime
    product_group_name: str | None = None
    purchase_quantity_unit_name: str | None = None
    stock_quantity_unit_name: str | None = None
    consume_quantity_unit_name: str | None = None
    price_quantity_unit_name: str | None = None
    stocks: list[GrocyStockEntryPayload] = Field(default_factory=list)


class GrocyProductsResponse(BaseModel):
    instance_index: str
    products: list[GrocyProductInventoryEntry]


__all__ = [
    "CreatedQuantityUnit",
    "CreatedProductGroup",
    "CreatedShoppingLocation",
    "InitializeInstanceResponse",
    "GrocyQuantityUnitPayload",
    "GrocyQuantityUnitsResponse",
    "PurchaseEntryDefaultsResponse",
    "PurchaseEntryDefaultsBatchRequest",
    "PurchaseEntryDefaultsBatchResponse",
    "PurchaseEntryCalculationRequest",
    "PurchaseEntryCalculationResponse",
    "ProductUnitConversionPayload",
    "ProductDescriptionMetadataPayload",
    "ProductDescriptionMetadataUpdatePayload",
    "ProductDescriptionMetadataBatchRequest",
    "InstanceAddressPayload",
    "GrocyLocationPayload",
    "GrocyShoppingLocationPayload",
    "InventoryLossDetailPayload",
    "InventoryCorrectionMetadataPayload",
    "InventoryCorrectionRequest",
    "PurchaseEntryRequest",
    "GrocyProductInventoryEntry",
    "GrocyStockEntryPayload",
    "GrocyProductsResponse",
    "InstanceSummary",
    "ListInstancesResponse",
]
