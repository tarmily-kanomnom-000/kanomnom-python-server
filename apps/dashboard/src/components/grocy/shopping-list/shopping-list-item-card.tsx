"use client";

import type React from "react";
import { useState } from "react";
import { createPortal } from "react-dom";
import type {
  ItemUpdate,
  ShoppingListItem,
} from "@/lib/grocy/shopping-list-types";

interface ShoppingListItemCardProps {
  item: ShoppingListItem;
  onUpdate: (itemId: string, updates: ItemUpdate) => Promise<void>;
  onDelete: (itemId: string) => Promise<void>;
  locationOptions: Array<{
    value: string;
    label: string;
    name: string;
  }>;
}

type StockTone = "critical" | "warning" | "caution";

function getStockTone(currentStock: number, minStock: number): StockTone {
  if (currentStock <= 0) {
    return "critical";
  }
  if (currentStock < minStock) {
    return "warning";
  }
  if (currentStock <= minStock * 1.15) {
    return "caution";
  }
  return "caution";
}

export function ShoppingListItemCard({
  item,
  onUpdate,
  onDelete,
  locationOptions,
}: ShoppingListItemCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState(item.notes || "");
  const [customQuantity, setCustomQuantity] = useState(
    item.quantity_purchased?.toString() || "",
  );
  const [touchStart, setTouchStart] = useState(0);
  const [touchEnd, setTouchEnd] = useState(0);
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isPurchased = item.status === "purchased";
  const isUnavailable = item.status === "unavailable";
  const stockTone = getStockTone(item.current_stock, item.min_stock);

  const minSwipeDistance = 50;

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchEnd(0);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
    const distance = e.targetTouches[0].clientX - touchStart;
    if (Math.abs(distance) < 150) {
      setSwipeOffset(distance);
    }
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) {
      setSwipeOffset(0);
      return;
    }

    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > minSwipeDistance;
    const isRightSwipe = distance < -minSwipeDistance;

    if (isLeftSwipe) {
      handleDeleteClick();
    }

    if (isRightSwipe && !isPurchased && !isUnavailable) {
      handleCheckboxChange({ target: { checked: true } } as any);
    }

    setSwipeOffset(0);
    setTouchStart(0);
    setTouchEnd(0);
  };

  const handleCheckboxChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const checked = e.target.checked;
    const newStatus = checked ? "purchased" : "pending";
    const checked_at = checked ? new Date().toISOString() : null;

    await onUpdate(item.id, { status: newStatus, checked_at });
  };

  const handleSaveNotes = async () => {
    await onUpdate(item.id, { notes });
    setEditingNotes(false);
  };

  const handleSaveQuantity = async () => {
    const qty = parseFloat(customQuantity);
    if (Number.isNaN(qty) || qty <= 0) {
      alert("Please enter a valid quantity");
      return;
    }

    const checked_at = new Date().toISOString();

    await onUpdate(item.id, {
      quantity_purchased: qty,
      status: "purchased",
      checked_at,
    });
  };

  const handleMarkUnavailable = async () => {
    const newStatus = isUnavailable ? "pending" : "unavailable";
    await onUpdate(item.id, { status: newStatus });
  };

  const handleLocationChange = async (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    const selectedValue = event.target.value;
    const numericId = Number.parseInt(selectedValue, 10);
    const isNumeric = Number.isFinite(numericId);
    const selectedOption = locationOptions.find(
      (option) => option.value === selectedValue,
    );
    const nextName = selectedOption?.name ?? selectedValue ?? "UNKNOWN";
    const shopping_location_id =
      selectedValue === "UNKNOWN" ? null : isNumeric ? numericId : null;
    await onUpdate(item.id, {
      shopping_location_id,
      shopping_location_name: nextName,
    });
  };

  const handleDeleteClick = () => {
    setShowDeleteDialog(true);
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);

    try {
      await onDelete(item.id);
      setShowDeleteDialog(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const borderColor =
    isPurchased || isUnavailable
      ? "border-green-200"
      : stockTone === "critical"
        ? "border-red-400"
        : stockTone === "warning"
          ? "border-orange-400"
          : "border-yellow-500";

  const bgColor =
    isPurchased || isUnavailable
      ? "bg-green-50"
      : stockTone === "critical"
        ? "bg-red-100"
        : stockTone === "warning"
          ? "bg-orange-100"
          : "bg-yellow-100";

  const swipeBackgroundColor =
    swipeOffset > 0 ? "bg-green-100" : swipeOffset < 0 ? "bg-red-100" : "";

  return (
    <div
      className={`relative overflow-hidden rounded-lg border p-3 transition-all ${borderColor} ${bgColor} ${
        isPurchased || isUnavailable ? "opacity-60" : ""
      } ${swipeBackgroundColor}`}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{ transform: `translateX(${swipeOffset}px)` }}
    >
      {/* Swipe hint indicators */}
      {swipeOffset > 20 && (
        <div className="absolute left-2 top-1/2 -translate-y-1/2 text-lg text-green-600">
          ✓
        </div>
      )}
      {swipeOffset < -20 && (
        <div className="absolute right-2 top-1/2 -translate-y-1/2 text-lg text-red-600">
          🗑️
        </div>
      )}

      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={isPurchased || isUnavailable}
          onChange={handleCheckboxChange}
          disabled={isUnavailable}
          className="mt-0.5 h-6 w-6 shrink-0 cursor-pointer rounded border-gray-300 text-green-600 focus:ring-2 focus:ring-green-500 focus:ring-offset-0 disabled:cursor-not-allowed md:h-5 md:w-5"
        />

        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <div
              className={`text-base font-medium ${
                isPurchased || isUnavailable
                  ? "text-gray-600 line-through"
                  : "text-gray-900"
              }`}
            >
              {item.product_name}
            </div>

            <div className="text-sm text-gray-600">
              Need: {item.quantity_suggested} {item.quantity_unit}
              {item.quantity_purchased && (
                <span className="ml-1 text-green-600">
                  (Got: {item.quantity_purchased})
                </span>
              )}
            </div>

            <div className="text-xs text-gray-500">
              Current: {item.current_stock} / Min: {item.min_stock}
            </div>
          </div>

          {/* Phase 2: Price info */}
          {item.last_price && (
            <div className="text-xs text-gray-500">
              Last: ${item.last_price.unit_price.toFixed(2)} at{" "}
              {item.last_price.shopping_location_name}
            </div>
          )}

          {/* Phase 2: Notes display */}
          {item.notes && !editingNotes && (
            <div className="text-xs italic text-gray-600">
              Note: {item.notes}
            </div>
          )}

          {/* Phase 2: Unavailable status */}
          {isUnavailable && (
            <div className="text-xs font-medium text-red-600">Unavailable</div>
          )}

          {/* Expanded controls */}
          {isExpanded && (
            <div className="mt-2 space-y-2 border-t border-gray-300 pt-2">
              {/* Notes editing */}
              <div>
                <label className="text-xs font-medium text-gray-700">
                  Notes:
                </label>
                {editingNotes ? (
                  <div className="mt-1 flex gap-2">
                    <input
                      type="text"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                      placeholder="Add a note..."
                    />
                    <button
                      onClick={handleSaveNotes}
                      className="rounded bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 md:px-2 md:py-1 md:text-xs"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setNotes(item.notes || "");
                        setEditingNotes(false);
                      }}
                      className="rounded bg-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-400 md:px-2 md:py-1 md:text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setEditingNotes(true)}
                    className="mt-1 text-xs text-blue-600 hover:underline"
                  >
                    {item.notes ? "Edit note" : "Add note"}
                  </button>
                )}
              </div>

              {/* Custom quantity */}
              <div>
                <label className="text-xs font-medium text-gray-700">
                  Custom Quantity ({item.quantity_unit}):
                </label>
                <div className="mt-1 flex gap-2">
                  <input
                    type="number"
                    value={customQuantity}
                    onChange={(e) => setCustomQuantity(e.target.value)}
                    className="w-24 rounded border border-gray-300 px-2 py-1 text-sm"
                    placeholder={item.quantity_suggested.toString()}
                    step="0.1"
                    min="0"
                  />
                  <button
                    onClick={handleSaveQuantity}
                    className="rounded bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 md:px-2 md:py-1 md:text-xs"
                  >
                    Set
                  </button>
                </div>
              </div>

              {/* Actions - larger touch targets on mobile */}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleMarkUnavailable}
                  className={`rounded px-4 py-2 text-sm font-medium md:px-3 md:py-1 md:text-xs ${
                    isUnavailable
                      ? "bg-gray-300 text-gray-700 hover:bg-gray-400"
                      : "bg-orange-600 text-white hover:bg-orange-700"
                  }`}
                >
                  {isUnavailable ? "Mark Available" : "Mark Unavailable"}
                </button>
                <div className="flex items-center gap-2 rounded border border-gray-300 bg-white px-2 py-1">
                  <label
                    className="text-xs text-gray-600"
                    htmlFor={`location-${item.id}`}
                  >
                    Move to:
                  </label>
                  <select
                    id={`location-${item.id}`}
                    value={
                      item.shopping_location_id !== null &&
                      item.shopping_location_id !== undefined
                        ? item.shopping_location_id.toString()
                        : item.shopping_location_name || "UNKNOWN"
                    }
                    onChange={handleLocationChange}
                    className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-800"
                  >
                    {locationOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleDeleteClick}
                  className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 md:px-3 md:py-1 md:text-xs"
                >
                  Remove
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Expand/collapse button - larger touch target on mobile */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="shrink-0 p-2 text-lg text-gray-500 hover:text-gray-700 md:p-0 md:text-base"
        >
          {isExpanded ? "▲" : "▼"}
        </button>
      </div>

      {/* Delete Confirmation Dialog - rendered as portal */}
      {showDeleteDialog &&
        typeof window !== "undefined" &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 px-4">
            <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
              <h2 className="mb-4 text-xl font-bold text-gray-900">
                Remove Item
              </h2>
              <p className="mb-6 text-sm text-gray-600">
                Are you sure you want to remove{" "}
                <span className="font-medium text-gray-900">
                  {item.product_name}
                </span>{" "}
                from the shopping list?
              </p>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowDeleteDialog(false)}
                  disabled={isDeleting}
                  className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isDeleting ? "Removing..." : "Remove"}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
