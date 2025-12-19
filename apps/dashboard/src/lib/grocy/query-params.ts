export const GROCY_QUERY_PARAMS = {
  instance: "instance",
  inventorySearch: "inventory_search",
  inventoryGroups: "inventory_groups",
  inventoryStatuses: "inventory_status",
  inventoryQuantityRange: "inventory_qty",
  inventoryStalenessRange: "inventory_stale",
  inventoryUpdatedRange: "inventory_updated",
  inventorySort: "inventory_sort",
} as const;

export const INVENTORY_QUERY_PARAM_KEYS: string[] = [
  GROCY_QUERY_PARAMS.inventorySearch,
  GROCY_QUERY_PARAMS.inventoryGroups,
  GROCY_QUERY_PARAMS.inventoryStatuses,
  GROCY_QUERY_PARAMS.inventoryQuantityRange,
  GROCY_QUERY_PARAMS.inventoryStalenessRange,
  GROCY_QUERY_PARAMS.inventoryUpdatedRange,
  GROCY_QUERY_PARAMS.inventorySort,
];
