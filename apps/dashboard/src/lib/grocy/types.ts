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
    [key: string]: unknown;
  } | null;
};

export type GrocyProductInventoryEntry = {
  id: number;
  name: string;
  description: string | null;
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

export type PurchaseEntryRequestPayload = {
  amount: number;
  bestBeforeDate: string | null;
  purchasedDate: string | null;
  pricePerUnit: number;
  locationId: number | null;
  shoppingLocationId: number | null;
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
  };
};
