export type GrocyLocation = {
  id: number;
  name: string;
  description: string | null;
  row_created_timestamp: Date;
  is_freezer: boolean;
  active: boolean;
};

export type GrocyShoppingLocation = {
  id: number;
  name: string;
  description: string | null;
  row_created_timestamp: Date;
  active: boolean;
};

export type GrocyInstanceAddress = {
  line1: string;
  line2: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
} | null;

export type GrocyInstanceSummary = {
  instance_index: string;
  location_name: string | null;
  location_types: string[];
  address: GrocyInstanceAddress;
  locations: GrocyLocation[];
  shopping_locations: GrocyShoppingLocation[];
};

export type ListInstancesResponse = {
  instances: GrocyInstanceSummary[];
};

export type GrocyStockEntry = {
  id: number;
  amount: number;
  best_before_date: Date | null;
  purchased_date: Date | null;
  stock_id: string | null;
  price: number | null;
  open: boolean;
  opened_date: Date | null;
  row_created_timestamp: Date;
  location_id: number | null;
  shopping_location_id: number | null;
  note: string | null;
  note_metadata?: {
    kind?: string;
    losses?: InventoryLossDetailPayload[];
    shipping_cost?: number;
    tax_rate?: number;
    brand?: string;
    package_size?: number;
    package_price?: number;
    package_quantity?: number;
    currency?: string;
    conversion_rate?: number;
    on_sale?: boolean;
    [key: string]: unknown;
  } | null;
};

export type GrocyQuantityUnit = {
  id: number;
  name: string;
  description: string | null;
  name_plural: string | null;
  plural_forms: string | null;
  active: boolean;
  is_discrete: boolean | null;
};

export type ProductUnitConversionDefinition = {
  from_unit: string;
  to_unit: string;
  factor: number;
  tare?: number;
};

export type ProductDescriptionMetadata = {
  kind?: string;
  unit_conversions?: ProductUnitConversionDefinition[];
  [key: string]: unknown;
} | null;

export type ProductDescriptionMetadataUpdatePayload = {
  product_id: number;
  description: string | null;
  description_metadata: {
    unit_conversions: ProductUnitConversionDefinition[];
  };
};

export type ProductDescriptionMetadataBatchRequestPayload = {
  updates: ProductDescriptionMetadataUpdatePayload[];
};

export type GrocyProductInventoryEntry = {
  id: number;
  name: string;
  description: string | null;
  description_metadata: ProductDescriptionMetadata;
  product_group_name: string | null;
  min_stock_amount: number;
  default_best_before_days: number;
  tare_weight: number;
  last_stock_updated_at: Date;
  location_id: number | null;
  shopping_location_id?: number | null;
  location_name?: string | null;
  purchase_quantity_unit_name: string | null;
  stock_quantity_unit_name: string | null;
  consume_quantity_unit_name: string | null;
  price_quantity_unit_name: string | null;
  stocks: GrocyStockEntry[];
};

export type GrocyProductsResponse = {
  instance_index: string;
  products: GrocyProductInventoryEntry[];
};

export type InventoryLossReason =
  | "spoilage"
  | "breakage"
  | "overportion"
  | "theft"
  | "quality_reject"
  | "process_error"
  | "other";

export type InventoryLossDetailPayload = {
  reason: InventoryLossReason;
  note: string | null;
};

export type InventoryCorrectionRequestPayload = {
  newAmount: number;
  bestBeforeDate: string | null;
  locationId: number | null;
  note: string | null;
  metadata?: {
    losses?: InventoryLossDetailPayload[] | null;
  } | null;
};

export type InventoryAdjustmentRequestPayload = {
  deltaAmount: number;
  bestBeforeDate: string | null;
  locationId: number | null;
  note: string | null;
  metadata?: {
    losses?: InventoryLossDetailPayload[] | null;
  } | null;
};

export type PurchaseEntryRequestPayload = {
  amount: number;
  bestBeforeDate: string | null;
  purchasedDate: string | null;
  pricePerUnit: number;
  locationId: number | null;
  shoppingLocationId: number | null;
  shoppingLocationName: string | null;
  note: string | null;
  metadata?: {
    shippingCost?: number | null;
    taxRate?: number | null;
    brand?: string | null;
    packageSize?: number | null;
    packagePrice?: number | null;
    quantity?: number | null;
    currency?: string | null;
    conversionRate?: number | null;
    onSale?: boolean | null;
  } | null;
};

export type PurchaseEntryDefaults = {
  productId: number;
  shoppingLocationId: number | null;
  metadata: {
    shippingCost: number | null;
    taxRate: number | null;
    brand: string | null;
    packageSize: number | null;
    packagePrice: number | null;
    quantity: number | null;
    currency: string | null;
    conversionRate: number | null;
    onSale: boolean;
  };
};

export type PurchaseEntryCalculation = {
  amount: number;
  unitPrice: number;
  totalUsd: number;
};
