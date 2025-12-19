"use client";

import { useEffect, useState } from "react";

import type {
  GrocyProductInventoryEntry,
  PurchaseEntryDefaults,
} from "@/lib/grocy/types";

import { InventoryCorrectionForm } from "./inventory-correction-form";
import { LOSS_REASON_OPTIONS } from "./loss-reasons";
import { ACTION_LABELS, type ProductActionType } from "./product-actions";
import { PurchaseEntryForm } from "./purchase-entry-form";

type ProductActionDialogProps = {
  product: GrocyProductInventoryEntry;
  action: ProductActionType;
  onClose: () => void;
  instanceIndex: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  onProductUpdate?: (product: GrocyProductInventoryEntry) => void;
  onSuccess: (message: string) => void;
  prefetchedPurchaseDefaults?: Record<number, PurchaseEntryDefaults>;
};

export function ProductActionDialog({
  product,
  action,
  onClose,
  instanceIndex,
  locationNamesById,
  shoppingLocationNamesById,
  onProductUpdate,
  onSuccess,
  prefetchedPurchaseDefaults,
}: ProductActionDialogProps) {
  const [transferScope, setTransferScope] = useState<
    "internal" | "external" | null
  >(null);
  const [currentProduct, setCurrentProduct] =
    useState<GrocyProductInventoryEntry>(product);
  useEffect(() => {
    setCurrentProduct(product);
  }, [product]);
  const showInventoryForm = action === "inventoryCorrection";
  const showPurchaseForm = action === "purchaseEntry";
  const dialogWidthClass = showInventoryForm
    ? "max-w-4xl"
    : showPurchaseForm
      ? "max-w-5xl"
      : "max-w-md";
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
    >
      <div
        className={`w-full ${dialogWidthClass} rounded-3xl bg-white p-6 shadow-2xl`}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Grocy action
            </p>
            <h3 className="mt-1 text-xl font-semibold text-neutral-900">
              {ACTION_LABELS[action]}
            </h3>
            <p className="text-sm text-neutral-500">{currentProduct.name}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
            aria-label="Close action dialog"
          >
            ✕
          </button>
        </div>
        {showInventoryForm ? (
          <InventoryCorrectionForm
            product={currentProduct}
            instanceIndex={instanceIndex}
            locationNamesById={locationNamesById}
            lossReasonOptions={LOSS_REASON_OPTIONS}
            onClose={onClose}
            onProductChange={(updatedProduct) => {
              setCurrentProduct(updatedProduct);
              onProductUpdate?.(updatedProduct);
            }}
            onSuccess={onSuccess}
          />
        ) : showPurchaseForm ? (
          <PurchaseEntryForm
            product={currentProduct}
            instanceIndex={instanceIndex}
            locationNamesById={locationNamesById}
            shoppingLocationNamesById={shoppingLocationNamesById}
            prefetchedDefaults={
              prefetchedPurchaseDefaults?.[currentProduct.id] ?? null
            }
            onClose={onClose}
            onProductChange={(updatedProduct) => {
              setCurrentProduct(updatedProduct);
              onProductUpdate?.(updatedProduct);
            }}
            onSuccess={onSuccess}
          />
        ) : (
          <>
            <div className="mt-5 space-y-4 text-sm text-neutral-700">
              {action === "stockTransfer" ? (
                <>
                  <p>
                    Was this stock transferred within the instance or moved to
                    another instance?
                  </p>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 text-sm text-neutral-800">
                      <input
                        type="radio"
                        name="stock-transfer-scope"
                        value="internal"
                        checked={transferScope === "internal"}
                        onChange={() => setTransferScope("internal")}
                      />
                      Moved between locations in this instance
                    </label>
                    <label className="flex items-center gap-2 text-sm text-neutral-800">
                      <input
                        type="radio"
                        name="stock-transfer-scope"
                        value="external"
                        checked={transferScope === "external"}
                        onChange={() => setTransferScope("external")}
                      />
                      Sent to a different instance
                    </label>
                  </div>
                </>
              ) : (
                <p>
                  This is a placeholder dialog for {ACTION_LABELS[action]}. The
                  action is not implemented yet.
                </p>
              )}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-neutral-900 px-5 py-2 text-sm font-semibold text-white"
              >
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
