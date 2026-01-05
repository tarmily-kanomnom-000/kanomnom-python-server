"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  defaultPurchaseCurrency,
  purchaseCurrencyOptions,
} from "@/config/purchase";
import { useMeasuredElementHeight } from "@/hooks/use-measured-element-height";
import {
  fetchPurchaseEntryDefaults,
  submitPurchaseEntry,
} from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  PurchaseEntryDefaults,
  PurchaseEntryRequestPayload,
} from "@/lib/grocy/types";
import {
  buildSearchableOptions,
  computeDefaultBestBeforeDate,
  roundToSixDecimals,
} from "./form-utils";
import { resolveQuantityUnit } from "./helpers";
import { DateField } from "./shared/date-field";
import { DerivedTotalsPanel } from "./shared/derived-totals-panel";
import { NoteField } from "./shared/note-field";
import { PurchaseLocationSection } from "./shared/purchase-location-section";
import { PurchasePackageFields } from "./shared/purchase-package-fields";
import { StatusMessage } from "./shared/status-message";
import { usePurchaseDerivation } from "./shared/use-purchase-derivation";
import { usePurchaseMetadata } from "./shared/use-purchase-metadata";

type PurchaseEntryFormProps = {
  product: GrocyProductInventoryEntry;
  instanceIndex: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  prefetchedDefaults?: PurchaseEntryDefaults | null;
  defaultPurchasedDate?: string | null;
  onClose: () => void;
  onProductChange: (product: GrocyProductInventoryEntry) => void;
  onSuccess: (message: string) => void;
  formId?: string;
};

export function PurchaseEntryForm({
  product,
  instanceIndex,
  locationNamesById,
  shoppingLocationNamesById,
  prefetchedDefaults = null,
  defaultPurchasedDate: defaultPurchasedDateOverride = null,
  onClose,
  onProductChange,
  onSuccess,
  formId = "purchase-entry-form",
}: PurchaseEntryFormProps) {
  const normalizeCurrency = useCallback((value: string | null): string => {
    if (!value) {
      return defaultPurchaseCurrency;
    }
    const normalized = value.trim().toUpperCase();
    return purchaseCurrencyOptions.some((entry) => entry.value === normalized)
      ? normalized
      : defaultPurchaseCurrency;
  }, []);

  const purchaseUnit = resolveQuantityUnit(product);
  const packageSizeInputRef = useRef<HTMLInputElement | null>(null);
  const {
    packageSize,
    setPackageSize,
    packageQuantity,
    setPackageQuantity,
    packagePrice,
    setPackagePrice,
    currencyValue,
    setCurrencyValue,
    conversionRate,
    setConversionRate,
    shippingCost,
    setShippingCost,
    taxRate,
    setTaxRate,
    brand,
    setBrand,
    onSale,
    setOnSale,
    resetAll: resetPurchaseMetadata,
    applyDefaults: applyMetadataDefaults,
    packageSizeHasValue,
    packageQuantityHasValue,
    packagePriceHasValue,
    conversionRateHasValue,
    shippingCostHasValue,
    taxRateHasValue,
    isPackageSizeValid,
    isPackageQuantityValid,
    isPackagePriceValid,
    isConversionRateValid,
    isShippingCostValid,
    isTaxRateValid,
    normalizedPurchaseMetadata,
    metadataHasValues,
    canDeriveTotals,
  } = usePurchaseMetadata({
    defaultCurrency: defaultPurchaseCurrency,
    normalizeCurrency,
  });
  const defaultBestBefore = useMemo(
    () => computeDefaultBestBeforeDate(product.default_best_before_days),
    [product.default_best_before_days],
  );
  const [bestBeforeDate, setBestBeforeDate] = useState(defaultBestBefore);
  const todayPurchaseDate = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today.toISOString().slice(0, 10);
  }, []);
  const resolvedDefaultPurchasedDate = useMemo(() => {
    if (!defaultPurchasedDateOverride || !defaultPurchasedDateOverride.trim()) {
      return todayPurchaseDate;
    }
    return defaultPurchasedDateOverride;
  }, [defaultPurchasedDateOverride, todayPurchaseDate]);
  const [purchasedDate, setPurchasedDate] = useState(
    resolvedDefaultPurchasedDate,
  );
  const defaultLocationId = product.location_id ?? null;
  const defaultLocationName =
    (defaultLocationId && locationNamesById[defaultLocationId]) || "";
  const defaultShoppingLocationId = product.shopping_location_id ?? null;
  const defaultShoppingLocationName =
    (defaultShoppingLocationId &&
      shoppingLocationNamesById[defaultShoppingLocationId]) ||
    "";
  const [locationId, setLocationId] = useState<number | null>(
    defaultLocationId,
  );
  const [shoppingLocationId, setShoppingLocationId] = useState<number | null>(
    defaultShoppingLocationId,
  );
  const [shoppingLocationName, setShoppingLocationName] = useState(
    defaultShoppingLocationName,
  );
  const [locationError, setLocationError] = useState(false);
  const [shoppingLocationError, setShoppingLocationError] = useState(false);
  const [note, setNote] = useState("");
  const [leftColumnRef, leftColumnHeight] =
    useMeasuredElementHeight<HTMLDivElement>();
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const metadataRequestId = useRef(0);

  const locationOptions = useMemo(
    () => buildSearchableOptions(locationNamesById),
    [locationNamesById],
  );
  const shoppingLocationOptions = useMemo(
    () => buildSearchableOptions(shoppingLocationNamesById),
    [shoppingLocationNamesById],
  );

  const formResetTrigger = useMemo(
    () => `${instanceIndex ?? "none"}:${product.id}`,
    [instanceIndex, product.id],
  );

  useEffect(() => {
    void formResetTrigger;
    setShowValidationErrors(false);
    resetPurchaseMetadata();
    setLocationId(defaultLocationId);
    setShoppingLocationId(defaultShoppingLocationId);
    setShoppingLocationName(defaultShoppingLocationName);
    packageSizeInputRef.current?.focus();
  }, [
    formResetTrigger,
    resetPurchaseMetadata,
    defaultLocationId,
    defaultShoppingLocationId,
    defaultShoppingLocationName,
  ]);

  useEffect(() => {
    void formResetTrigger;
    setPurchasedDate(resolvedDefaultPurchasedDate);
  }, [formResetTrigger, resolvedDefaultPurchasedDate]);

  useEffect(() => {
    const targetShoppingLocationId = shoppingLocationId ?? null;
    if (!instanceIndex) {
      applyMetadataDefaults(null);
      return;
    }
    if (
      prefetchedDefaults &&
      prefetchedDefaults.productId === product.id &&
      (prefetchedDefaults.shoppingLocationId ?? null) ===
        targetShoppingLocationId
    ) {
      applyMetadataDefaults(prefetchedDefaults.metadata ?? null);
      return;
    }

    let isCancelled = false;
    const requestId = metadataRequestId.current + 1;
    metadataRequestId.current = requestId;

    const loadDefaults = async () => {
      try {
        // Future enhancement: include extra context (recent brand choice, tax overrides, etc.)
        // so the API can return smarter recommendations without additional round trips.
        const defaults = await fetchPurchaseEntryDefaults(
          instanceIndex,
          product.id,
          shoppingLocationId,
        );
        if (isCancelled || metadataRequestId.current !== requestId) {
          return;
        }
        applyMetadataDefaults(defaults?.metadata ?? null);
      } catch {
        if (isCancelled || metadataRequestId.current !== requestId) {
          return;
        }
        applyMetadataDefaults(null);
      }
    };

    void loadDefaults();

    return () => {
      isCancelled = true;
    };
  }, [
    instanceIndex,
    product.id,
    shoppingLocationId,
    prefetchedDefaults,
    applyMetadataDefaults,
  ]);

  const metadataForSubmit: PurchaseEntryRequestPayload["metadata"] =
    metadataHasValues ? normalizedPurchaseMetadata : null;
  const normalizedShoppingLocationName = useMemo(
    () => shoppingLocationName.trim(),
    [shoppingLocationName],
  );
  const hasShoppingLocationSelection =
    shoppingLocationId !== null || normalizedShoppingLocationName.length > 0;

  const { derivedTotals, deriveError } = usePurchaseDerivation({
    instanceIndex,
    productId: product.id,
    metadata: normalizedPurchaseMetadata,
    canDeriveTotals,
  });

  const derivedAmount = derivedTotals.amount;
  const derivedUnitPrice = derivedTotals.unitPrice;
  const derivedTotalUsd = derivedTotals.totalUsd;
  const formattedUnitPrice =
    derivedUnitPrice !== null
      ? roundToSixDecimals(derivedUnitPrice).toFixed(6)
      : null;
  const formattedTotalUsd =
    derivedTotalUsd !== null
      ? roundToSixDecimals(derivedTotalUsd).toFixed(2)
      : null;

  const isFormValid =
    canDeriveTotals &&
    isShippingCostValid &&
    isTaxRateValid &&
    derivedAmount !== null &&
    derivedUnitPrice !== null &&
    Boolean(instanceIndex) &&
    !locationError &&
    !shoppingLocationError &&
    hasShoppingLocationSelection &&
    !isSubmitting;

  const shouldShowPackageSizeError =
    !isPackageSizeValid && (packageSizeHasValue || showValidationErrors);
  const shouldShowPackageQuantityError =
    !isPackageQuantityValid &&
    (packageQuantityHasValue || showValidationErrors);
  const shouldShowPackagePriceError =
    !isPackagePriceValid && (packagePriceHasValue || showValidationErrors);
  const shouldShowConversionRateError =
    !isConversionRateValid && (conversionRateHasValue || showValidationErrors);

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    setShowValidationErrors(true);
    if (
      !instanceIndex ||
      !isFormValid ||
      derivedAmount === null ||
      derivedUnitPrice === null
    ) {
      setStatusMessage({
        type: "error",
        text: "Complete the highlighted fields to record a purchase.",
      });
      return;
    }
    setSubmitting(true);
    setStatusMessage(null);
    try {
      const payload = {
        amount: derivedAmount,
        bestBeforeDate: bestBeforeDate || null,
        purchasedDate: purchasedDate || null,
        pricePerUnit: roundToSixDecimals(derivedUnitPrice),
        locationId,
        shoppingLocationId,
        shoppingLocationName:
          shoppingLocationId === null && normalizedShoppingLocationName.length
            ? normalizedShoppingLocationName
            : null,
        note: note.trim().length ? note.trim() : null,
        metadata: metadataForSubmit,
      };
      const { product: updatedProduct } = await submitPurchaseEntry(
        instanceIndex,
        product.id,
        payload,
      );
      onProductChange(updatedProduct);
      onSuccess("Purchase entry recorded.");
      onClose();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to record purchase.";
      setStatusMessage({ type: "error", text: message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      id={formId}
      onSubmit={handleSubmit}
      className="mt-6 space-y-5 text-sm text-neutral-900"
    >
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5" ref={leftColumnRef}>
          <div className="grid items-start gap-4 md:grid-cols-[minmax(0,1fr)_240px]">
            <PurchasePackageFields
              purchaseUnit={purchaseUnit}
              packageSize={packageSize}
              setPackageSize={setPackageSize}
              packageQuantity={packageQuantity}
              setPackageQuantity={setPackageQuantity}
              packagePrice={packagePrice}
              setPackagePrice={setPackagePrice}
              onSale={onSale}
              setOnSale={setOnSale}
              shouldShowPackageSizeError={shouldShowPackageSizeError}
              shouldShowPackageQuantityError={shouldShowPackageQuantityError}
              shouldShowPackagePriceError={shouldShowPackagePriceError}
              statusMessageType={statusMessage?.type ?? null}
              clearStatusMessage={() => setStatusMessage(null)}
            />
            <div className="space-y-4 md:ml-auto md:w-full">
              <DerivedTotalsPanel
                derivedAmount={
                  derivedAmount !== null
                    ? Number(roundToSixDecimals(derivedAmount).toFixed(6))
                    : null
                }
                derivedUnitPrice={
                  derivedUnitPrice !== null
                    ? Number(roundToSixDecimals(derivedUnitPrice).toFixed(6))
                    : null
                }
                derivedTotalUsd={
                  derivedTotalUsd !== null
                    ? Number(roundToSixDecimals(derivedTotalUsd).toFixed(2))
                    : null
                }
                unitLabel={purchaseUnit}
                unitPriceFormatter={(value) =>
                  roundToSixDecimals(value).toFixed(6)
                }
                totalFormatter={(value) => roundToSixDecimals(value).toFixed(2)}
                error={deriveError}
              />
              <DateField
                label="Purchased date"
                value={purchasedDate}
                onChange={setPurchasedDate}
                onUseDefault={() =>
                  setPurchasedDate(resolvedDefaultPurchasedDate)
                }
              />
              <DateField
                label="Best before date"
                value={bestBeforeDate}
                onChange={setBestBeforeDate}
                onUseDefault={() => setBestBeforeDate(defaultBestBefore)}
              />
            </div>
          </div>
          <PurchaseLocationSection
            shoppingLocationOptions={shoppingLocationOptions}
            shoppingLocationId={shoppingLocationId}
            shoppingLocationName={shoppingLocationName}
            defaultShoppingLocationId={defaultShoppingLocationId}
            defaultShoppingLocationName={defaultShoppingLocationName}
            onShoppingLocationIdChange={setShoppingLocationId}
            onShoppingLocationNameChange={setShoppingLocationName}
            setShoppingLocationError={setShoppingLocationError}
            locationOptions={locationOptions}
            locationId={locationId}
            defaultLocationId={defaultLocationId}
            defaultLocationName={defaultLocationName}
            onLocationIdChange={setLocationId}
            setLocationError={setLocationError}
          />
          <NoteField
            value={note}
            onChange={setNote}
            placeholder="Optional context for this purchase"
          />
        </div>
        <div
          className="md:h-full"
          style={
            leftColumnHeight
              ? { maxHeight: leftColumnHeight, height: leftColumnHeight }
              : undefined
          }
        >
          <div className="flex h-full flex-col rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Additional costs & metadata
              </p>
            </div>
            <div className="mt-3 flex-1 space-y-4 overflow-y-auto pr-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Brand
                </label>
                <input
                  type="text"
                  value={brand}
                  onChange={(event) => {
                    setBrand(event.target.value);
                  }}
                  className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                  placeholder="e.g. Restaurant Depot"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Shipping cost
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={shippingCost}
                  onChange={(event) => {
                    setShippingCost(event.target.value);
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:outline-none ${
                    isShippingCostValid
                      ? "border-neutral-200 focus:border-neutral-900"
                      : "border-rose-400 focus:border-rose-500"
                  }`}
                  placeholder="e.g. 4.99"
                />
                <p className="text-xs text-neutral-500">
                  Optional shipping cost in {currencyValue || "local currency"}.
                </p>
                {!isShippingCostValid ? (
                  <p className="text-xs text-rose-600">
                    Shipping cost must be a non-negative number.
                  </p>
                ) : null}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Tax rate
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={taxRate}
                  onChange={(event) => {
                    setTaxRate(event.target.value);
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:outline-none ${
                    isTaxRateValid
                      ? "border-neutral-200 focus:border-neutral-900"
                      : "border-rose-400 focus:border-rose-500"
                  }`}
                  placeholder="e.g. 0.0825"
                />
                <p className="text-xs text-neutral-500">
                  Optional fractional rate (0.0825 represents 8.25%).
                </p>
                {!isTaxRateValid ? (
                  <p className="text-xs text-rose-600">
                    Tax rate must be a non-negative number.
                  </p>
                ) : null}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Currency
                </label>
                <select
                  value={currencyValue}
                  onChange={(event) => {
                    setCurrencyValue(normalizeCurrency(event.target.value));
                  }}
                  className="w-full rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                >
                  {purchaseCurrencyOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-neutral-500">
                  Applies to package price, shipping, and tax inputs.
                </p>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Conversion rate to USD
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={conversionRate}
                  onChange={(event) => {
                    setConversionRate(event.target.value);
                    if (statusMessage?.type === "error") {
                      setStatusMessage(null);
                    }
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:outline-none ${
                    shouldShowConversionRateError
                      ? "border-rose-400 focus:border-rose-500"
                      : "border-neutral-200 focus:border-neutral-900"
                  }`}
                  placeholder="e.g. 1.00"
                />
                <p className="text-xs text-neutral-500">
                  Multiply local currency amounts by this rate to convert to
                  USD.
                </p>
                {shouldShowConversionRateError ? (
                  <p className="text-xs text-rose-600">
                    Conversion rate must be greater than 0.
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
      <StatusMessage status={statusMessage} />
    </form>
  );
}
