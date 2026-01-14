"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchGrocyQuantityUnits,
  submitProductDescriptionMetadata,
} from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  GrocyStockEntry,
} from "@/lib/grocy/types";
import { DescriptionWithLinks } from "./description-with-links";
import {
  formatLastUpdated,
  formatQuantityWithUnit,
  resolveProductGroup,
  resolveQuantityUnit,
} from "./helpers";
import { LOSS_REASON_LABELS } from "./loss-reasons";
import {
  formatBestBeforeDays,
  formatMinimumStock,
  formatShoppingLocationName,
  formatStockEntryAmount,
  formatStockEntryDate,
  formatStockEntryLocation,
  formatStockEntryTotalPrice,
  formatStockEntryUnitPrice,
  formatTareWeight,
  resolveDaysSinceUpdate,
} from "./product-metrics";

type ProductDetailsDialogProps = {
  product: GrocyProductInventoryEntry;
  onClose: () => void;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  instanceIndex: string | null;
  isAdmin: boolean;
  onProductUpdate?: (product: GrocyProductInventoryEntry) => void;
};

export function ProductDetailsDialog({
  product,
  onClose,
  locationNamesById,
  shoppingLocationNamesById,
  instanceIndex,
  isAdmin,
  onProductUpdate,
}: ProductDetailsDialogProps) {
  const [currentProduct, setCurrentProduct] =
    useState<GrocyProductInventoryEntry>(product);
  const rowIdRef = useRef(0);
  const createRowId = useCallback(
    () => `conversion-${product.id}-${rowIdRef.current++}`,
    [product.id],
  );
  const [descriptionText, setDescriptionText] = useState(
    product.description ?? "",
  );
  const [conversionRows, setConversionRows] = useState<ConversionRow[]>(() =>
    buildConversionRows(product, createRowId),
  );
  const [unitOptions, setUnitOptions] = useState<string[]>([]);
  const [unitOptionsStatus, setUnitOptionsStatus] = useState<
    "idle" | "loading" | "error"
  >("idle");
  const [isSavingMetadata, setIsSavingMetadata] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataSuccess, setMetadataSuccess] = useState<string | null>(null);
  const lastProductIdRef = useRef(product.id);

  useEffect(() => {
    if (lastProductIdRef.current !== product.id) {
      lastProductIdRef.current = product.id;
      setMetadataError(null);
      setMetadataSuccess(null);
    }
    setCurrentProduct(product);
    setDescriptionText(product.description ?? "");
    rowIdRef.current = 0;
    setConversionRows(buildConversionRows(product, createRowId));
  }, [createRowId, product]);

  useEffect(() => {
    if (!instanceIndex || !isAdmin) {
      setUnitOptions([]);
      setUnitOptionsStatus("idle");
      return;
    }
    let isActive = true;
    setUnitOptionsStatus("loading");
    fetchGrocyQuantityUnits(instanceIndex)
      .then((units) => {
        if (!isActive) {
          return;
        }
        const uniqueUnits = Array.from(
          new Set(units.map((unit) => unit.name.trim()).filter(Boolean)),
        ).sort((a, b) => a.localeCompare(b));
        setUnitOptions(uniqueUnits);
        setUnitOptionsStatus("idle");
      })
      .catch(() => {
        if (!isActive) {
          return;
        }
        setUnitOptions([]);
        setUnitOptionsStatus("error");
      });
    return () => {
      isActive = false;
    };
  }, [instanceIndex, isAdmin]);

  const normalizedUnitOptions = useMemo(() => {
    return new Set(unitOptions.map((unit) => unit.trim().toLowerCase()));
  }, [unitOptions]);

  const formattedTareWeight = formatTareWeight(currentProduct);
  const daysSinceUpdate = resolveDaysSinceUpdate(currentProduct);
  const quantityUnit = resolveQuantityUnit(currentProduct);

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Product
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-neutral-900">
              {currentProduct.name}
            </h2>
            <p className="text-sm text-neutral-500">
              {resolveProductGroup(currentProduct)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
            aria-label="Close details"
          >
            ✕
          </button>
        </div>

        {currentProduct.description ? (
          <DescriptionWithLinks
            description={currentProduct.description}
            className="mt-4 whitespace-pre-line text-sm text-neutral-700"
          />
        ) : null}

        <dl className="mt-6 grid grid-cols-1 gap-4 text-sm text-neutral-700 sm:grid-cols-2">
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Quantity on hand
            </dt>
            <dd className="mt-2 text-lg font-semibold text-neutral-900">
              {formatQuantityWithUnit(currentProduct)}
            </dd>
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Minimum required
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {formatMinimumStock(currentProduct)}
            </dd>
          </div>
          {formattedTareWeight ? (
            <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
              <dt className="text-xs uppercase tracking-wide text-neutral-500">
                Tare weight
              </dt>
              <dd className="mt-2 text-base text-neutral-900">
                {formattedTareWeight}
              </dd>
            </div>
          ) : null}
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Best before window
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {formatBestBeforeDays(currentProduct.default_best_before_days)}
            </dd>
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Last updated
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {formatLastUpdated(currentProduct.last_stock_updated_at)}
            </dd>
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Days since update
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {daysSinceUpdate} day{daysSinceUpdate === 1 ? "" : "s"}
            </dd>
          </div>
          {currentProduct.location_name ? (
            <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-neutral-500">
                Location
              </dt>
              <dd className="mt-2 text-base text-neutral-900">
                {currentProduct.location_name}
              </dd>
            </div>
          ) : null}
        </dl>

        <StockEntriesList
          stocks={currentProduct.stocks}
          unit={quantityUnit}
          locationNamesById={locationNamesById}
          shoppingLocationNamesById={shoppingLocationNamesById}
        />

        {isAdmin && instanceIndex ? (
          <ProductDescriptionMetadataEditor
            descriptionText={descriptionText}
            conversionRows={conversionRows}
            unitOptions={unitOptions}
            unitOptionsStatus={unitOptionsStatus}
            isSaving={isSavingMetadata}
            errorMessage={metadataError}
            successMessage={metadataSuccess}
            onDescriptionChange={setDescriptionText}
            onConversionChange={setConversionRows}
            onAddConversionRow={() =>
              setConversionRows((current) => [
                ...current,
                {
                  id: createRowId(),
                  fromUnit: "",
                  toUnit: "",
                  factor: "",
                  tare: "",
                },
              ])
            }
            onSave={async () => {
              if (!instanceIndex) {
                return;
              }
              setMetadataError(null);
              setMetadataSuccess(null);
              const validationError = validateConversionRows(
                conversionRows,
                descriptionText,
                normalizedUnitOptions,
                unitOptionsStatus,
              );
              if (validationError) {
                setMetadataError(validationError);
                return;
              }
              const trimmedDescription = descriptionText.trim();
              setIsSavingMetadata(true);
              try {
                const updates = await submitProductDescriptionMetadata(
                  instanceIndex,
                  {
                    updates: [
                      {
                        product_id: currentProduct.id,
                        description: trimmedDescription || null,
                        description_metadata: {
                          unit_conversions: conversionRows.map((row) => ({
                            from_unit: row.fromUnit.trim(),
                            to_unit: row.toUnit.trim(),
                            factor: Number(row.factor),
                            tare: row.tare.trim().length
                              ? Number(row.tare)
                              : undefined,
                          })),
                        },
                      },
                    ],
                  },
                );
                const updated =
                  updates.find((entry) => entry.id === currentProduct.id) ??
                  updates[0];
                if (updated) {
                  setCurrentProduct(updated);
                  setDescriptionText(updated.description ?? "");
                  rowIdRef.current = 0;
                  setConversionRows(buildConversionRows(updated, createRowId));
                  onProductUpdate?.(updated);
                }
                setMetadataSuccess("Metadata saved.");
              } catch (error) {
                const message =
                  error instanceof Error
                    ? error.message
                    : "Failed to save metadata.";
                setMetadataError(message);
              } finally {
                setIsSavingMetadata(false);
              }
            }}
          />
        ) : null}

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-neutral-900 px-5 py-2 text-sm font-semibold text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

type ConversionRow = {
  id: string;
  fromUnit: string;
  toUnit: string;
  factor: string;
  tare: string;
};

function buildConversionRows(
  product: GrocyProductInventoryEntry,
  createRowId: () => string,
): ConversionRow[] {
  const conversions = product.description_metadata?.unit_conversions ?? [];
  return conversions.map((conversion, index) => ({
    id: createRowId(),
    fromUnit: conversion.from_unit,
    toUnit: conversion.to_unit,
    factor: String(conversion.factor),
    tare: typeof conversion.tare === "number" ? String(conversion.tare) : "",
  }));
}

function validateConversionRows(
  rows: ConversionRow[],
  descriptionText: string,
  allowedUnits: Set<string>,
  unitOptionsStatus: "idle" | "loading" | "error",
): string | null {
  if (rows.length === 0) {
    return descriptionText.trim()
      ? null
      : "Add at least one unit conversion or enter a description.";
  }
  if (unitOptionsStatus === "loading") {
    return "Unit options are still loading.";
  }
  if (unitOptionsStatus === "error") {
    return "Unable to load unit options. Refresh and try again.";
  }
  if (allowedUnits.size === 0) {
    return "No quantity units available for this instance.";
  }
  for (const [index, row] of rows.entries()) {
    if (!row.fromUnit.trim() || !row.toUnit.trim()) {
      return `Row ${index + 1} must include both units.`;
    }
    const fromUnit = row.fromUnit.trim().toLowerCase();
    const toUnit = row.toUnit.trim().toLowerCase();
    if (!allowedUnits.has(fromUnit)) {
      return `Row ${index + 1} uses an unknown from-unit.`;
    }
    if (!allowedUnits.has(toUnit)) {
      return `Row ${index + 1} uses an unknown to-unit.`;
    }
    const factor = Number(row.factor);
    if (!Number.isFinite(factor) || factor <= 0) {
      return `Row ${index + 1} must include a positive factor.`;
    }
    if (row.tare.trim().length > 0) {
      const tareValue = Number(row.tare);
      if (!Number.isFinite(tareValue) || tareValue < 0) {
        return `Row ${index + 1} tare must be a non-negative number.`;
      }
    }
  }
  return null;
}

function ProductDescriptionMetadataEditor({
  descriptionText,
  conversionRows,
  unitOptions,
  unitOptionsStatus,
  onAddConversionRow,
  isSaving,
  errorMessage,
  successMessage,
  onDescriptionChange,
  onConversionChange,
  onSave,
}: {
  descriptionText: string;
  conversionRows: ConversionRow[];
  unitOptions: string[];
  unitOptionsStatus: "idle" | "loading" | "error";
  onAddConversionRow: () => void;
  isSaving: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  onDescriptionChange: (value: string) => void;
  onConversionChange: (rows: ConversionRow[]) => void;
  onSave: () => void;
}) {
  return (
    <div className="mt-6 rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Unit conversions
          </p>
          <p className="text-xs text-neutral-500">
            Define how one unit converts to another for this product.
          </p>
        </div>
        <button
          type="button"
          onClick={onAddConversionRow}
          className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
        >
          Add conversion
        </button>
      </div>

      <div className="mt-4 space-y-3">
        <label className="block text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Description
        </label>
        <textarea
          value={descriptionText}
          onChange={(event) => onDescriptionChange(event.target.value)}
          placeholder="Optional human-readable description"
          className="min-h-[80px] w-full rounded-2xl border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-800 shadow-sm focus:border-neutral-400 focus:outline-none"
        />
      </div>

      <div className="mt-4 space-y-3">
        {conversionRows.map((row, index) => (
          <div
            key={row.id}
            className="rounded-2xl border border-neutral-200 bg-white p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                list="quantity-unit-options"
                value={row.fromUnit}
                onChange={(event) =>
                  onConversionChange(
                    conversionRows.map((entry) =>
                      entry.id === row.id
                        ? { ...entry, fromUnit: event.target.value }
                        : entry,
                    ),
                  )
                }
                placeholder="From unit"
                className="flex-1 rounded-full border border-neutral-200 px-3 py-1 text-sm"
              />
              <span className="text-xs text-neutral-500">=</span>
              <input
                type="number"
                value={row.factor}
                onChange={(event) =>
                  onConversionChange(
                    conversionRows.map((entry) =>
                      entry.id === row.id
                        ? { ...entry, factor: event.target.value }
                        : entry,
                    ),
                  )
                }
                placeholder="Factor"
                className="w-24 rounded-full border border-neutral-200 px-3 py-1 text-sm"
              />
              <input
                type="text"
                list="quantity-unit-options"
                value={row.toUnit}
                onChange={(event) =>
                  onConversionChange(
                    conversionRows.map((entry) =>
                      entry.id === row.id
                        ? { ...entry, toUnit: event.target.value }
                        : entry,
                    ),
                  )
                }
                placeholder="To unit"
                className="flex-1 rounded-full border border-neutral-200 px-3 py-1 text-sm"
              />
              <input
                type="number"
                value={row.tare}
                onChange={(event) =>
                  onConversionChange(
                    conversionRows.map((entry) =>
                      entry.id === row.id
                        ? { ...entry, tare: event.target.value }
                        : entry,
                    ),
                  )
                }
                placeholder="Tare (to unit)"
                className="w-24 rounded-full border border-neutral-200 px-3 py-1 text-sm"
              />
              <button
                type="button"
                onClick={() =>
                  onConversionChange(
                    conversionRows.filter((entry) => entry.id !== row.id),
                  )
                }
                className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
              >
                Remove
              </button>
            </div>
            <p className="mt-2 text-[11px] text-neutral-400">
              Example: 1 {row.fromUnit || "unit"} = {row.factor || "x"}{" "}
              {row.toUnit || "unit"}
              {row.tare.trim().length > 0 ? ` (tare ${row.tare})` : ""}
            </p>
            <p className="mt-1 text-[11px] text-neutral-400">Row {index + 1}</p>
          </div>
        ))}
        <datalist id="quantity-unit-options">
          {unitOptions.map((unit) => (
            <option key={unit} value={unit} />
          ))}
        </datalist>
        {conversionRows.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-neutral-300 bg-white px-4 py-3 text-xs text-neutral-500">
            No unit conversions yet. Add at least one conversion to save.
          </p>
        ) : null}
      </div>

      {unitOptionsStatus === "loading" ? (
        <p className="mt-3 text-xs text-neutral-500">Loading unit options…</p>
      ) : null}
      {unitOptionsStatus === "error" ? (
        <p className="mt-3 text-xs text-red-600">
          Unable to load unit options. Refresh the page and try again.
        </p>
      ) : null}
      {errorMessage ? (
        <p className="mt-3 text-xs text-red-600">{errorMessage}</p>
      ) : null}
      {successMessage ? (
        <p className="mt-3 text-xs text-emerald-600">{successMessage}</p>
      ) : null}

      <div className="mt-4 flex justify-end gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="rounded-full bg-neutral-900 px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:bg-neutral-400"
        >
          {isSaving ? "Saving..." : "Save metadata"}
        </button>
      </div>
    </div>
  );
}

function StockEntriesList({
  stocks,
  unit,
  locationNamesById,
  shoppingLocationNamesById,
}: {
  stocks: GrocyStockEntry[];
  unit: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
}) {
  const [expandedEntryIds, setExpandedEntryIds] = useState<
    Record<number, boolean>
  >(() => ({}));
  if (!stocks.length) {
    return (
      <div className="mt-6 rounded-2xl border border-dashed border-neutral-200 bg-neutral-50 px-4 py-5 text-sm text-neutral-500">
        No individual stock entries recorded for this product yet.
      </div>
    );
  }

  return (
    <div className="mt-6">
      <p className="text-xs uppercase tracking-wide text-neutral-500">
        Stock entries
      </p>
      <div className="mt-3 max-h-64 space-y-3 overflow-y-auto pr-2">
        {stocks.map((entry) => (
          <StockEntryCard
            key={entry.id}
            entry={entry}
            unit={unit}
            locationNamesById={locationNamesById}
            shoppingLocationNamesById={shoppingLocationNamesById}
            isExpanded={!!expandedEntryIds[entry.id]}
            onToggle={() =>
              setExpandedEntryIds((current) => ({
                ...current,
                [entry.id]: !current[entry.id],
              }))
            }
          />
        ))}
      </div>
    </div>
  );
}

function StockEntryCard({
  entry,
  unit,
  locationNamesById,
  shoppingLocationNamesById,
  isExpanded,
  onToggle,
}: {
  entry: GrocyStockEntry;
  unit: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4 text-sm text-neutral-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-neutral-900">
            {formatStockEntryAmount(entry.amount, unit)}
          </p>
          <p className="text-xs text-neutral-500">
            Purchased {formatStockEntryDate(entry.purchased_date)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
              entry.open
                ? "bg-amber-100 text-amber-800"
                : "bg-emerald-100 text-emerald-800"
            }`}
          >
            {entry.open ? "Open" : "Sealed"}
          </span>
          <button
            type="button"
            onClick={onToggle}
            className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            {isExpanded ? "Hide details" : "Show details"}
          </button>
        </div>
      </div>
      {isExpanded ? (
        <>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-neutral-600">
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Best before
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryDate(entry.best_before_date)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Purchased
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryDate(entry.purchased_date)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Recorded
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryDate(entry.row_created_timestamp)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Stock ID
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {entry.stock_id ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Unit price (USD)
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryUnitPrice(entry.price, unit)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Total (USD)
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryTotalPrice(entry.price, entry.amount)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Location
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatStockEntryLocation(entry.location_id, locationNamesById)}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] uppercase tracking-wide text-neutral-400">
                Shopping location
              </dt>
              <dd className="mt-1 font-medium text-neutral-900">
                {formatShoppingLocationName(
                  entry.shopping_location_id,
                  shoppingLocationNamesById,
                )}
              </dd>
            </div>
          </dl>
          {entry.note ? (
            <p className="mt-3 text-xs text-neutral-500">Note: {entry.note}</p>
          ) : null}
          <StockEntryMetadata metadata={entry.note_metadata} unit={unit} />
        </>
      ) : null}
    </div>
  );
}

function StockEntryMetadata({
  metadata,
  unit,
}: {
  metadata: GrocyStockEntry["note_metadata"];
  unit: string | null;
}) {
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  const kind = typeof metadata.kind === "string" ? metadata.kind : undefined;
  if (kind === "purchase_entry") {
    const shippingCost =
      typeof metadata.shipping_cost === "number"
        ? metadata.shipping_cost
        : null;
    const taxRate =
      typeof metadata.tax_rate === "number" ? metadata.tax_rate : null;
    const brand =
      typeof metadata.brand === "string" && metadata.brand.trim().length
        ? metadata.brand.trim()
        : null;
    const packageSize =
      typeof metadata.package_size === "number" ? metadata.package_size : null;
    const packageQuantity =
      typeof metadata.package_quantity === "number"
        ? metadata.package_quantity
        : null;
    const packagePrice =
      typeof metadata.package_price === "number"
        ? metadata.package_price
        : null;
    const currency =
      typeof metadata.currency === "string" && metadata.currency.trim().length
        ? metadata.currency.trim().toUpperCase()
        : null;
    const conversionRate =
      typeof metadata.conversion_rate === "number"
        ? metadata.conversion_rate
        : null;
    const onSale = metadata.on_sale === true;
    if (
      shippingCost === null &&
      taxRate === null &&
      !brand &&
      packageSize === null &&
      packageQuantity === null &&
      packagePrice === null &&
      !currency &&
      conversionRate === null &&
      !onSale
    ) {
      return null;
    }
    const currencyLabel = currency ?? "local currency";
    return (
      <div className="mt-2 space-y-1 text-xs text-neutral-500">
        {onSale ? <p>On sale: Yes</p> : null}
        {shippingCost !== null ? (
          <p>
            Shipping cost: {currencyLabel} {shippingCost.toFixed(2)}
          </p>
        ) : null}
        {taxRate !== null ? (
          <p>Tax rate: {(taxRate * 100).toFixed(2)}%</p>
        ) : null}
        {brand ? <p>Brand: {brand}</p> : null}
        {packageSize !== null ? (
          <p>
            Package size: {packageSize}
            {unit ? ` ${unit}` : ""}
          </p>
        ) : null}
        {packageQuantity !== null ? (
          <p>Packages purchased: {packageQuantity}</p>
        ) : null}
        {packagePrice !== null ? (
          <p>
            Package price: {currencyLabel} {packagePrice.toFixed(2)}
          </p>
        ) : null}
        {currency ? <p>Currency: {currency}</p> : null}
        {conversionRate !== null ? (
          <p>Conversion rate to USD: {conversionRate.toFixed(4)}</p>
        ) : null}
      </div>
    );
  }
  if (kind === "inventory_correction") {
    const rawLosses = Array.isArray(metadata.losses) ? metadata.losses : [];
    const parsedLosses = rawLosses
      .map((entry) => {
        if (!entry || typeof entry !== "object") {
          return null;
        }
        const reasonRaw = (entry as Record<string, unknown>).reason;
        if (typeof reasonRaw !== "string" || !reasonRaw.trim().length) {
          return null;
        }
        const normalizedReason = reasonRaw.trim().toLowerCase();
        const noteValue = (entry as Record<string, unknown>).note;
        const note =
          typeof noteValue === "string" && noteValue.trim().length
            ? noteValue.trim()
            : null;
        return { reason: normalizedReason, note };
      })
      .filter(
        (entry): entry is { reason: string; note: string | null } =>
          entry !== null,
      );
    if (!parsedLosses.length) {
      return null;
    }
    return (
      <div className="mt-2 text-xs text-neutral-500">
        <p>Loss reasons:</p>
        <ul className="list-disc pl-4">
          {parsedLosses.map((entry, index) => (
            <li key={`${entry.reason}-${index}`}>
              {LOSS_REASON_LABELS[entry.reason] ?? entry.reason}
              {entry.note ? ` — ${entry.note}` : ""}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return null;
}
