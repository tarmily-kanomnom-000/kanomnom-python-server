"use client";

import { useState } from "react";
import type {
  GrocyProductInventoryEntry,
  GrocyStockEntry,
} from "@/lib/grocy/types";

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
  normalizeDescription,
  resolveDaysSinceUpdate,
} from "./product-metrics";

type ProductDetailsDialogProps = {
  product: GrocyProductInventoryEntry;
  onClose: () => void;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
};

export function ProductDetailsDialog({
  product,
  onClose,
  locationNamesById,
  shoppingLocationNamesById,
}: ProductDetailsDialogProps) {
  const formattedTareWeight = formatTareWeight(product);
  const daysSinceUpdate = resolveDaysSinceUpdate(product);
  const quantityUnit = resolveQuantityUnit(product);

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Product
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-neutral-900">
              {product.name}
            </h2>
            <p className="text-sm text-neutral-500">
              {resolveProductGroup(product)}
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

        {product.description ? (
          <p className="mt-4 whitespace-pre-line text-sm text-neutral-700">
            {normalizeDescription(product.description)}
          </p>
        ) : null}

        <dl className="mt-6 grid grid-cols-1 gap-4 text-sm text-neutral-700 sm:grid-cols-2">
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Quantity on hand
            </dt>
            <dd className="mt-2 text-lg font-semibold text-neutral-900">
              {formatQuantityWithUnit(product)}
            </dd>
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Minimum required
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {formatMinimumStock(product)}
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
              {formatBestBeforeDays(product.default_best_before_days)}
            </dd>
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <dt className="text-xs uppercase tracking-wide text-neutral-500">
              Last updated
            </dt>
            <dd className="mt-2 text-base text-neutral-900">
              {formatLastUpdated(product.last_stock_updated_at)}
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
          {product.location_name ? (
            <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-4 sm:col-span-2">
              <dt className="text-xs uppercase tracking-wide text-neutral-500">
                Location
              </dt>
              <dd className="mt-2 text-base text-neutral-900">
                {product.location_name}
              </dd>
            </div>
          ) : null}
        </dl>

        <StockEntriesList
          stocks={product.stocks}
          unit={quantityUnit}
          locationNamesById={locationNamesById}
          shoppingLocationNamesById={shoppingLocationNamesById}
        />

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
    if (
      shippingCost === null &&
      taxRate === null &&
      !brand &&
      packageSize === null &&
      packageQuantity === null &&
      packagePrice === null &&
      !currency &&
      conversionRate === null
    ) {
      return null;
    }
    const currencyLabel = currency ?? "local currency";
    return (
      <div className="mt-2 space-y-1 text-xs text-neutral-500">
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
