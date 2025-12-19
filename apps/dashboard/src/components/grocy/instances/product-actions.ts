export type ProductActionType =
  | "inventoryCorrection"
  | "purchaseEntry"
  | "consumption"
  | "stockTransfer";

export const ACTION_LABELS: Record<ProductActionType, string> = {
  inventoryCorrection: "Inventory Correction",
  purchaseEntry: "Purchase Entry",
  consumption: "Consumption",
  stockTransfer: "Stock Transfered",
};

export const ACTION_MENU_OPTIONS: Array<{
  label: string;
  value: ProductActionType;
}> = [
  { label: ACTION_LABELS.inventoryCorrection, value: "inventoryCorrection" },
  { label: ACTION_LABELS.purchaseEntry, value: "purchaseEntry" },
  { label: ACTION_LABELS.consumption, value: "consumption" },
  { label: ACTION_LABELS.stockTransfer, value: "stockTransfer" },
];
