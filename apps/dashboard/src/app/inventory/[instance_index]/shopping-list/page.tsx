"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { OfflineIndicator } from "@/components/grocy/shopping-list/offline-indicator";
import { ShoppingListSections } from "@/components/grocy/shopping-list/shopping-list-sections";
import { SyncStatusBanner } from "@/components/grocy/shopping-list/sync-status-banner";
import { useShoppingListController } from "@/hooks/useShoppingListController";
import type { ProductSearchResult } from "@/lib/grocy/shopping-list-types";

export default function ShoppingListPage() {
  const params = useParams();
  const instanceIndex = params.instance_index as string;

  const {
    isOnline,
    isLoading,
    error,
    status,
    list,
    products,
    sections,
    purchasedCount,
    totalCount,
    progress,
    clearError,
    generateList,
    completeList,
    updateItem,
    removeItems,
    bulkCheckSection,
    bulkUncheckSection,
    bulkRemoveChecked,
    bulkUncheckAll,
    addItem,
  } = useShoppingListController(instanceIndex);

  const [collapsedSections, setCollapsedSections] = useState<
    Record<string, boolean>
  >({});
  const [showAddItem, setShowAddItem] = useState(false);
  const [addItemProductId, setAddItemProductId] = useState("");
  const [addItemQuantity, setAddItemQuantity] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProduct, setSelectedProduct] =
    useState<ProductSearchResult | null>(null);
  const [showCompleteDialog, setShowCompleteDialog] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [completionMessage, setCompletionMessage] = useState("");
  const handleBulkUncheckAll = () => bulkUncheckAll();
  const handleBulkRemoveChecked = () => bulkRemoveChecked();
  const handleGenerate = async (merge: boolean) => {
    if (!isOnline) {
      alert("Generating a new list requires an internet connection");
      return;
    }

    try {
      await generateList(merge);
    } catch (err) {
      if (
        err instanceof Error &&
        err.message.toLowerCase().includes("active shopping list exists")
      ) {
        if (
          confirm(
            "Active list exists. Merge with new items? (This will preserve checked items)",
          )
        ) {
          await handleGenerate(true);
          return;
        }
      }
    }
  };

  const handleCompleteClick = () => {
    setShowCompleteDialog(true);
    clearError();
  };

  const handleConfirmComplete = async () => {
    setIsCompleting(true);
    clearError();

    try {
      const message = await completeList();
      setCompletionMessage(message);
    } catch (err) {
      console.error(err);
      setShowCompleteDialog(false);
    } finally {
      setIsCompleting(false);
    }
  };

  const handleCloseCompleteDialog = () => {
    setShowCompleteDialog(false);
    setCompletionMessage("");
  };

  const toggleSection = (locationKey: string) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [locationKey]: !prev[locationKey],
    }));
  };

  // Client-side product search - filter locally instead of hitting server
  const searchResults = useMemo(() => {
    if (searchQuery.trim().length < 2 || products.length === 0) {
      return [];
    }

    const queryLower = searchQuery.toLowerCase();
    return products
      .filter((p) => p.name.toLowerCase().includes(queryLower))
      .map((p) => ({
        id: p.id,
        name: p.name,
        current_stock: p.stocks.reduce(
          (total, entry) => total + entry.amount,
          0,
        ),
        min_stock: p.min_stock_amount,
        unit: p.stock_quantity_unit_name || "unit",
      }))
      .sort((a, b) => a.name.localeCompare(b.name))
      .slice(0, 50);
  }, [searchQuery, products]);

  const handleSearchProducts = (query: string) => {
    setSearchQuery(query);
  };

  const handleSelectProduct = (product: ProductSearchResult) => {
    setSelectedProduct(product);
    setAddItemProductId(product.id.toString());
    setSearchQuery(product.name);
  };

  const handleAddItem = async () => {
    const productId = parseInt(addItemProductId, 10);
    const quantity = parseFloat(addItemQuantity);

    if (Number.isNaN(productId) || productId <= 0) {
      alert("Please select a product");
      return;
    }

    if (Number.isNaN(quantity) || quantity <= 0) {
      alert("Please enter a valid quantity");
      return;
    }

    await addItem(productId, quantity);
    setShowAddItem(false);
    setAddItemProductId("");
    setAddItemQuantity("");
    setSearchQuery("");
    setSelectedProduct(null);
  };

  if (isLoading) {
    return <div className="p-6">Loading...</div>;
  }

  return (
    <div className="mx-auto w-full max-w-4xl p-6">
      {/* Header */}
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Shopping List</h1>
          <div className="flex gap-3">
            {list ? (
              <>
                <button
                  onClick={() => {
                    if (!isOnline) {
                      alert("Adding items requires an internet connection");
                      return;
                    }
                    setShowAddItem(true);
                  }}
                  className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100"
                >
                  + Add Item
                </button>
                <button
                  onClick={() => handleGenerate(true)}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
                >
                  Update from Inventory
                </button>
                <button
                  onClick={handleCompleteClick}
                  className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700"
                >
                  Complete Shopping
                </button>
              </>
            ) : (
              <button
                onClick={() => handleGenerate(false)}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Generate List
              </button>
            )}
          </div>
        </div>

        {list && (
          <>
            <div className="text-sm text-gray-600">
              {purchasedCount} of {totalCount} items purchased ({progress}%)
            </div>
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full bg-green-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>

            {/* Bulk Actions */}
            {list.items.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={handleBulkUncheckAll}
                  className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50"
                >
                  Uncheck All
                </button>
                <button
                  onClick={handleBulkRemoveChecked}
                  className="rounded border border-red-300 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-100"
                >
                  Remove Checked Items
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </div>
      )}
      {status && (
        <div
          className={`mb-4 rounded border px-4 py-3 ${
            status.level === "error"
              ? "border-red-200 bg-red-50 text-red-700"
              : "border-blue-200 bg-blue-50 text-blue-800"
          }`}
        >
          {status.message}
        </div>
      )}

      {/* Add Item Modal */}
      {showAddItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-xl font-bold text-gray-900">
              Add Item to List
            </h2>

            <div className="space-y-4">
              <div className="relative">
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Product
                </label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => handleSearchProducts(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2"
                  placeholder="Search for a product..."
                  autoComplete="off"
                />

                {/* Search results dropdown */}
                {searchResults.length > 0 && (
                  <div className="absolute z-10 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-gray-300 bg-white shadow-lg">
                    {searchResults.map((product) => (
                      <button
                        key={product.id}
                        type="button"
                        onClick={() => handleSelectProduct(product)}
                        className="w-full border-b border-gray-100 px-3 py-2 text-left transition-colors hover:bg-blue-50"
                      >
                        <div className="font-medium text-gray-900">
                          {product.name}
                        </div>
                        <div className="text-xs text-gray-500">
                          ID: {product.id} | Stock: {product.current_stock} /
                          Min: {product.min_stock} {product.unit}
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {selectedProduct && (
                  <div className="mt-2 rounded border border-green-200 bg-green-50 px-3 py-2">
                    <div className="text-sm font-medium text-green-900">
                      Selected: {selectedProduct.name}
                    </div>
                    <div className="text-xs text-green-700">
                      Current stock: {selectedProduct.current_stock}{" "}
                      {selectedProduct.unit}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Quantity
                </label>
                <input
                  type="number"
                  value={addItemQuantity}
                  onChange={(e) => setAddItemQuantity(e.target.value)}
                  className="w-full rounded border border-gray-300 px-3 py-2"
                  placeholder="Enter quantity"
                  step="0.1"
                  min="0"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowAddItem(false);
                  setAddItemProductId("");
                  setAddItemQuantity("");
                  setSearchQuery("");
                  setSelectedProduct(null);
                }}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddItem}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                Add Item
              </button>
            </div>
          </div>
        </div>
      )}

      {!list && !isLoading && (
        <div className="rounded-lg bg-gray-50 py-12 text-center">
          <p className="mb-4 text-gray-600">No active shopping list</p>
          <button
            onClick={() => handleGenerate(false)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            Generate Shopping List
          </button>
        </div>
      )}

      {list && list.items.length === 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 py-12 text-center">
          <p className="mb-4 text-green-700">
            Everything is well-stocked! No shopping needed.
          </p>
        </div>
      )}

      {/* Items grouped by location */}
      {list && list.items.length > 0 && (
        <ShoppingListSections
          sections={sections}
          collapsedSections={collapsedSections}
          onToggleSection={toggleSection}
          onCheckSection={bulkCheckSection}
          onUncheckSection={bulkUncheckSection}
          onUpdateItem={updateItem}
          onDeleteItem={(itemId) => removeItems([itemId])}
        />
      )}

      {/* Complete Shopping Confirmation Dialog - rendered as portal */}
      {showCompleteDialog &&
        typeof window !== "undefined" &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 px-4">
            <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
              {completionMessage ? (
                // Success state
                <>
                  <div className="mb-4 flex items-center justify-center">
                    <div className="rounded-full bg-green-100 p-3">
                      <svg
                        className="h-8 w-8 text-green-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    </div>
                  </div>
                  <h2 className="mb-4 text-center text-xl font-bold text-gray-900">
                    Shopping Complete!
                  </h2>
                  <p className="mb-6 text-center text-sm text-gray-600">
                    {completionMessage}
                  </p>
                  <div className="flex justify-center">
                    <button
                      onClick={handleCloseCompleteDialog}
                      className="rounded-lg bg-green-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700"
                    >
                      Close
                    </button>
                  </div>
                </>
              ) : (
                // Confirmation state
                <>
                  <h2 className="mb-4 text-xl font-bold text-gray-900">
                    Complete Shopping?
                  </h2>
                  <p className="mb-6 text-sm text-gray-600">
                    This will archive the shopping list. Are you sure you want
                    to complete it?
                  </p>
                  <div className="flex justify-end gap-3">
                    <button
                      onClick={handleCloseCompleteDialog}
                      disabled={isCompleting}
                      className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleConfirmComplete}
                      disabled={isCompleting}
                      className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isCompleting ? "Completing..." : "Complete Shopping"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>,
          document.body,
        )}

      <SyncStatusBanner />
      <OfflineIndicator isOnline={isOnline} />
    </div>
  );
}
