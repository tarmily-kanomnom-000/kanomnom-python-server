from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict

from .base import MedusaBaseModel


class MedusaRawAmount(MedusaBaseModel):
    value: str
    precision: int


class MedusaOrderSummary(MedusaBaseModel):
    paid_total: float | None = None
    refunded_total: float | None = None
    accounting_total: float | None = None
    credit_line_total: float | None = None
    transaction_total: float | None = None
    pending_difference: float | None = None
    current_order_total: float | None = None
    original_order_total: float | None = None
    raw_paid_total: MedusaRawAmount | None = None
    raw_refunded_total: MedusaRawAmount | None = None
    raw_accounting_total: MedusaRawAmount | None = None
    raw_credit_line_total: MedusaRawAmount | None = None
    raw_transaction_total: MedusaRawAmount | None = None
    raw_pending_difference: MedusaRawAmount | None = None
    raw_current_order_total: MedusaRawAmount | None = None
    raw_original_order_total: MedusaRawAmount | None = None


class MedusaOrderItemTaxLine(MedusaBaseModel):
    id: str
    description: str | None = None
    tax_rate_id: str | None = None
    code: str | None = None
    provider_id: str | None = None
    item_id: str | None = None
    raw_rate: MedusaRawAmount | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    rate: float | None = None
    total: float | None = None
    subtotal: float | None = None
    raw_total: MedusaRawAmount | None = None
    raw_subtotal: MedusaRawAmount | None = None


class MedusaOrderItemDetail(MedusaBaseModel):
    id: str
    version: int | None = None
    metadata: dict[str, Any] | None = None
    order_id: str | None = None
    raw_unit_price: MedusaRawAmount | None = None
    raw_compare_at_unit_price: MedusaRawAmount | None = None
    raw_quantity: MedusaRawAmount | None = None
    raw_fulfilled_quantity: MedusaRawAmount | None = None
    raw_delivered_quantity: MedusaRawAmount | None = None
    raw_shipped_quantity: MedusaRawAmount | None = None
    raw_return_requested_quantity: MedusaRawAmount | None = None
    raw_return_received_quantity: MedusaRawAmount | None = None
    raw_return_dismissed_quantity: MedusaRawAmount | None = None
    raw_written_off_quantity: MedusaRawAmount | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    item_id: str | None = None
    unit_price: float | None = None
    compare_at_unit_price: float | None = None
    quantity: float | None = None
    fulfilled_quantity: float | None = None
    delivered_quantity: float | None = None
    shipped_quantity: float | None = None
    return_requested_quantity: float | None = None
    return_received_quantity: float | None = None
    return_dismissed_quantity: float | None = None
    written_off_quantity: float | None = None


class MedusaProduct(MedusaBaseModel):
    id: str
    title: str | None = None
    handle: str | None = None
    subtitle: str | None = None
    description: str | None = None
    is_giftcard: bool | None = None
    status: str | None = None
    thumbnail: str | None = None
    weight: float | None = None
    length: float | None = None
    height: float | None = None
    width: float | None = None
    origin_country: str | None = None
    hs_code: str | None = None
    mid_code: str | None = None
    material: str | None = None
    discountable: bool | None = None
    external_id: str | None = None
    metadata: dict[str, Any] | None = None
    type_id: str | None = None
    type: dict[str, Any] | None = None
    collection_id: str | None = None
    collection: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class MedusaVariant(MedusaBaseModel):
    id: str
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    ean: str | None = None
    upc: str | None = None
    allow_backorder: bool | None = None
    manage_inventory: bool | None = None
    hs_code: str | None = None
    origin_country: str | None = None
    mid_code: str | None = None
    material: str | None = None
    weight: float | None = None
    length: float | None = None
    height: float | None = None
    width: float | None = None
    metadata: dict[str, Any] | None = None
    variant_rank: int | None = None
    thumbnail: str | None = None
    product_id: str | None = None
    product: MedusaProduct | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class MedusaOrderItem(MedusaBaseModel):
    id: str
    title: str | None = None
    subtitle: str | None = None
    thumbnail: str | None = None
    variant_id: str | None = None
    product_id: str | None = None
    product_title: str | None = None
    product_description: str | None = None
    product_subtitle: str | None = None
    product_type: str | None = None
    product_type_id: str | None = None
    product_collection: dict[str, Any] | None = None
    product_handle: str | None = None
    variant_sku: str | None = None
    variant_barcode: str | None = None
    variant_title: str | None = None
    variant_option_values: list[dict[str, Any]] | None = None
    requires_shipping: bool | None = None
    is_giftcard: bool | None = None
    is_discountable: bool | None = None
    is_tax_inclusive: bool | None = None
    is_custom_price: bool | None = None
    metadata: dict[str, Any] | None = None
    raw_compare_at_unit_price: MedusaRawAmount | None = None
    raw_unit_price: MedusaRawAmount | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    tax_lines: list[MedusaOrderItemTaxLine] | None = None
    adjustments: list[dict[str, Any]] | None = None
    compare_at_unit_price: float | None = None
    unit_price: float | None = None
    quantity: float | None = None
    raw_quantity: MedusaRawAmount | None = None
    detail: MedusaOrderItemDetail | None = None
    subtotal: float | None = None
    total: float | None = None
    original_subtotal: float | None = None
    original_total: float | None = None
    discount_subtotal: float | None = None
    discount_tax_total: float | None = None
    discount_total: float | None = None
    tax_total: float | None = None
    original_tax_total: float | None = None
    refundable_total_per_unit: float | None = None
    refundable_total: float | None = None
    fulfilled_total: float | None = None
    shipped_total: float | None = None
    return_requested_total: float | None = None
    return_received_total: float | None = None
    return_dismissed_total: float | None = None
    write_off_total: float | None = None
    raw_subtotal: MedusaRawAmount | None = None
    raw_total: MedusaRawAmount | None = None
    raw_original_subtotal: MedusaRawAmount | None = None
    raw_original_total: MedusaRawAmount | None = None
    raw_discount_subtotal: MedusaRawAmount | None = None
    raw_discount_tax_total: MedusaRawAmount | None = None
    raw_discount_total: MedusaRawAmount | None = None
    raw_tax_total: MedusaRawAmount | None = None
    raw_original_tax_total: MedusaRawAmount | None = None
    raw_refundable_total_per_unit: MedusaRawAmount | None = None
    raw_refundable_total: MedusaRawAmount | None = None
    raw_fulfilled_total: MedusaRawAmount | None = None
    raw_shipped_total: MedusaRawAmount | None = None
    raw_return_requested_total: MedusaRawAmount | None = None
    raw_return_received_total: MedusaRawAmount | None = None
    raw_return_dismissed_total: MedusaRawAmount | None = None
    raw_write_off_total: MedusaRawAmount | None = None
    variant: MedusaVariant | None = None


class MedusaOrderAddress(MedusaBaseModel):
    id: str
    customer_id: str | None = None
    company: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    country_code: str | None = None
    province: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


class MedusaPaymentSession(MedusaBaseModel):
    id: str


class MedusaPayment(MedusaBaseModel):
    id: str
    currency_code: str | None = None
    provider_id: str | None = None
    data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    captured_at: datetime | None = None
    canceled_at: datetime | None = None
    payment_collection_id: str | None = None
    payment_session: MedusaPaymentSession | None = None
    raw_amount: MedusaRawAmount | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    payment_session_id: str | None = None
    refunds: list[dict[str, Any]] | None = None
    captures: list[dict[str, Any]] | None = None
    amount: float | None = None


class MedusaPaymentCollection(MedusaBaseModel):
    id: str
    currency_code: str | None = None
    completed_at: datetime | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None
    raw_amount: MedusaRawAmount | None = None
    raw_authorized_amount: MedusaRawAmount | None = None
    raw_captured_amount: MedusaRawAmount | None = None
    raw_refunded_amount: MedusaRawAmount | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    payments: list[MedusaPayment] | None = None
    amount: float | None = None
    authorized_amount: float | None = None
    captured_amount: float | None = None
    refunded_amount: float | None = None


class MedusaOrder(MedusaBaseModel):
    id: str
    display_id: int | None = None
    custom_display_id: str | None = None
    email: str | None = None
    status: str | None = None
    version: int | None = None
    summary: MedusaOrderSummary | None = None
    total: float | None = None
    metadata: dict[str, Any] | None = None
    locale: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    region_id: str | None = None
    currency_code: str | None = None
    subtotal: float | None = None
    tax_total: float | None = None
    discount_total: float | None = None
    discount_tax_total: float | None = None
    original_total: float | None = None
    original_subtotal: float | None = None
    original_tax_total: float | None = None
    item_total: float | None = None
    item_subtotal: float | None = None
    item_tax_total: float | None = None
    original_item_total: float | None = None
    original_item_subtotal: float | None = None
    original_item_tax_total: float | None = None
    shipping_total: float | None = None
    shipping_subtotal: float | None = None
    shipping_tax_total: float | None = None
    original_shipping_tax_total: float | None = None
    original_shipping_subtotal: float | None = None
    original_shipping_total: float | None = None
    credit_line_total: float | None = None
    credit_line_subtotal: float | None = None
    credit_line_tax_total: float | None = None
    items: list[MedusaOrderItem] | None = None
    credit_lines: list[dict[str, Any]] | None = None
    shipping_address: MedusaOrderAddress | None = None
    shipping_methods: list[dict[str, Any]] | None = None
    payment_collections: list[MedusaPaymentCollection] | None = None
    fulfillments: list[dict[str, Any]] | None = None
    payment_status: str | None = None
    fulfillment_status: str | None = None


class MedusaOrderResponse(MedusaBaseModel):
    model_config = ConfigDict(extra="allow")

    order: MedusaOrder
