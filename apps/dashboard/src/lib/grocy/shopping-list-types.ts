export type ItemStatus = "pending" | "purchased" | "unavailable";

export interface PriceSnapshot {
  unit_price: number;
  purchase_date: string;
  shopping_location_name: string;
}

export interface ShoppingListItem {
  id: string;
  product_id: number;
  product_name: string;
  product_group_name?: string | null;
  shopping_location_id: number | null;
  shopping_location_name: string;
  status: ItemStatus;
  quantity_suggested: number;
  quantity_purchased: number | null;
  quantity_unit: string;
  current_stock: number;
  min_stock: number;
  last_price: PriceSnapshot | null;
  notes: string;
  checked_at: string | null;
  modified_at: string;
}

export interface ShoppingList {
  id: string;
  instance_index: string;
  version: number;
  created_at: string;
  last_modified_at: string;
  items: ShoppingListItem[];
  location_order: Array<string | number>;
}

export interface ItemsByLocation {
  [locationKey: string]: ShoppingListItem[];
}

export interface AddItemRequest {
  product_id: number;
  quantity: number;
}

export interface GenerateListRequest {
  merge_with_existing: boolean;
}

export interface BulkItemUpdate {
  item_id: string;
  status?: ItemStatus;
  quantity_purchased?: number;
  notes?: string;
  checked_at?: string | null;
  shopping_location_id?: number | null;
  shopping_location_name?: string;
  /**
   * Client-side timestamp used for ordering/coalescing; ignored by server.
   */
  last_modified_at?: string;
}

export interface BulkUpdateRequest {
  updates: BulkItemUpdate[];
}

export interface ItemUpdate {
  status?: ItemStatus;
  quantity_purchased?: number | null;
  notes?: string;
  checked_at?: string | null;
  shopping_location_id?: number | null;
  shopping_location_name?: string;
}

export interface ProductSearchResult {
  id: number;
  name: string;
  current_stock: number;
  min_stock: number;
  unit: string;
}
