"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  defaultPurchaseCurrency,
  purchaseCurrencyOptions,
} from "@/config/purchase";
import { useDirtyStringField } from "@/hooks/use-dirty-string-field";
import { useMeasuredElementHeight } from "@/hooks/use-measured-element-height";
import {
  fetchPurchaseEntryCalculation,
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
import { SearchableOptionSelect } from "./searchable-option-select";

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
    value: packageSize,
    set: setPackageSize,
    hydrate: hydratePackageSize,
    reset: resetPackageSize,
  } = useDirtyStringField("");
  const {
    value: packageQuantity,
    set: setPackageQuantity,
    hydrate: hydratePackageQuantity,
    reset: resetPackageQuantity,
  } = useDirtyStringField("");
  const {
    value: packagePrice,
    set: setPackagePrice,
    hydrate: hydratePackagePrice,
    reset: resetPackagePrice,
  } = useDirtyStringField("");
  const {
    value: currencyValue,
    set: setCurrencyValue,
    hydrate: hydrateCurrencyValue,
    reset: resetCurrencyValue,
  } = useDirtyStringField(defaultPurchaseCurrency);
  const {
    value: conversionRate,
    set: setConversionRate,
    hydrate: hydrateConversionRate,
    reset: resetConversionRate,
  } = useDirtyStringField("1");
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
  const {
    value: shippingCost,
    set: setShippingCost,
    hydrate: hydrateShippingCost,
    reset: resetShippingCost,
  } = useDirtyStringField("");
  const {
    value: taxRate,
    set: setTaxRate,
    hydrate: hydrateTaxRate,
    reset: resetTaxRate,
  } = useDirtyStringField("");
  const {
    value: brand,
    set: setBrand,
    hydrate: hydrateBrand,
    reset: resetBrand,
  } = useDirtyStringField("");
  const [onSale, setOnSaleState] = useState(false);
  const onSaleDirtyRef = useRef(false);
  const setOnSale = useCallback((nextValue: boolean) => {
    onSaleDirtyRef.current = true;
    setOnSaleState(nextValue);
  }, []);
  const hydrateOnSale = useCallback((nextValue: boolean) => {
    if (onSaleDirtyRef.current) {
      return;
    }
    setOnSaleState(nextValue);
  }, []);
  const resetOnSale = useCallback((nextValue: boolean) => {
    onSaleDirtyRef.current = false;
    setOnSaleState(nextValue);
  }, []);
  const [derivedTotals, setDerivedTotals] = useState<{
    amount: number | null;
    unitPrice: number | null;
    totalUsd: number | null;
  }>({ amount: null, unitPrice: null, totalUsd: null });
  const [deriveError, setDeriveError] = useState<string | null>(null);
  const deriveRequestId = useRef(0);
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
    resetPackageSize("");
    resetPackageQuantity("");
    resetPackagePrice("");
    resetCurrencyValue(defaultPurchaseCurrency);
    resetConversionRate("1");
    resetShippingCost("");
    resetTaxRate("");
    resetBrand("");
    resetOnSale(false);
    setLocationId(defaultLocationId);
    setShoppingLocationId(defaultShoppingLocationId);
    setShoppingLocationName(defaultShoppingLocationName);
    packageSizeInputRef.current?.focus();
  }, [
    formResetTrigger,
    resetBrand,
    resetConversionRate,
    resetCurrencyValue,
    resetPackagePrice,
    resetPackageQuantity,
    resetPackageSize,
    resetShippingCost,
    resetTaxRate,
    resetOnSale,
    defaultLocationId,
    defaultShoppingLocationId,
    defaultShoppingLocationName,
  ]);

  useEffect(() => {
    void formResetTrigger;
    setPurchasedDate(resolvedDefaultPurchasedDate);
  }, [formResetTrigger, resolvedDefaultPurchasedDate]);

  const applyMetadataDefaults = useCallback(
    (metadata: PurchaseEntryDefaults["metadata"] | null): void => {
      const sizeValue =
        metadata && metadata.packageSize !== null
          ? metadata.packageSize.toString()
          : "";
      hydratePackageSize(sizeValue);

      const quantityValue =
        metadata && metadata.quantity !== null
          ? metadata.quantity.toString()
          : "";
      hydratePackageQuantity(quantityValue);

      const priceValue =
        metadata && metadata.packagePrice !== null
          ? metadata.packagePrice.toString()
          : "";
      hydratePackagePrice(priceValue);

      const currency = normalizeCurrency(metadata?.currency ?? null);
      hydrateCurrencyValue(currency);

      const rateValue =
        metadata && metadata.conversionRate !== null
          ? metadata.conversionRate.toString()
          : "1";
      hydrateConversionRate(rateValue);

      const shippingValue =
        metadata && metadata.shippingCost !== null
          ? metadata.shippingCost.toString()
          : "";
      hydrateShippingCost(shippingValue);

      const taxValue =
        metadata && metadata.taxRate !== null
          ? metadata.taxRate.toString()
          : "";
      hydrateTaxRate(taxValue);

      const trimmedBrand = metadata?.brand?.trim() ?? "";
      hydrateBrand(trimmedBrand);
      hydrateOnSale(metadata?.onSale ?? false);
    },
    [
      hydrateBrand,
      hydrateConversionRate,
      hydrateCurrencyValue,
      hydratePackagePrice,
      hydratePackageQuantity,
      hydratePackageSize,
      hydrateShippingCost,
      hydrateTaxRate,
      normalizeCurrency,
      hydrateOnSale,
    ],
  );

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

  const packageSizeHasValue = packageSize.trim().length > 0;
  const packageSizeNumber = Number(packageSize);
  const isPackageSizeValid =
    packageSizeHasValue &&
    Number.isFinite(packageSizeNumber) &&
    packageSizeNumber > 0;
  const packageQuantityHasValue = packageQuantity.trim().length > 0;
  const packageQuantityNumber = Number(packageQuantity);
  const isPackageQuantityValid =
    packageQuantityHasValue &&
    Number.isFinite(packageQuantityNumber) &&
    packageQuantityNumber > 0;
  const packagePriceHasValue = packagePrice.trim().length > 0;
  const packagePriceNumber = Number(packagePrice);
  const isPackagePriceValid =
    packagePriceHasValue &&
    Number.isFinite(packagePriceNumber) &&
    packagePriceNumber > 0;
  const conversionRateHasValue = conversionRate.trim().length > 0;
  const conversionRateNumber = Number(conversionRate);
  const isConversionRateValid =
    conversionRateHasValue &&
    Number.isFinite(conversionRateNumber) &&
    conversionRateNumber > 0;

  const shippingCostHasValue = shippingCost.trim().length > 0;
  const shippingCostNumber = Number(shippingCost);
  const isShippingCostValid =
    !shippingCostHasValue ||
    (Number.isFinite(shippingCostNumber) && shippingCostNumber >= 0);
  const taxRateHasValue = taxRate.trim().length > 0;
  const taxRateNumber = Number(taxRate);
  const isTaxRateValid =
    !taxRateHasValue || (Number.isFinite(taxRateNumber) && taxRateNumber >= 0);

  type PurchaseMetadataPayload = {
    shippingCost: number | null;
    taxRate: number | null;
    brand: string | null;
    packageSize: number | null;
    packagePrice: number | null;
    quantity: number | null;
    currency: string | null;
    conversionRate: number | null;
    onSale: boolean;
  };

  const normalizedPurchaseMetadata = useMemo<PurchaseMetadataPayload>(() => {
    const trimmedBrand = brand.trim();
    return {
      shippingCost:
        isShippingCostValid && shippingCostHasValue ? shippingCostNumber : null,
      taxRate: isTaxRateValid && taxRateHasValue ? taxRateNumber : null,
      brand: trimmedBrand.length ? trimmedBrand : null,
      packageSize: isPackageSizeValid ? packageSizeNumber : null,
      packagePrice: isPackagePriceValid ? packagePriceNumber : null,
      quantity: isPackageQuantityValid ? packageQuantityNumber : null,
      currency: normalizeCurrency(currencyValue),
      conversionRate: isConversionRateValid ? conversionRateNumber : null,
      onSale,
    };
  }, [
    brand,
    currencyValue,
    onSale,
    isConversionRateValid,
    conversionRateNumber,
    isPackagePriceValid,
    packagePriceNumber,
    isPackageQuantityValid,
    packageQuantityNumber,
    isPackageSizeValid,
    packageSizeNumber,
    isShippingCostValid,
    shippingCostHasValue,
    shippingCostNumber,
    isTaxRateValid,
    taxRateHasValue,
    taxRateNumber,
    normalizeCurrency,
  ]);

  const metadataHasValues = useMemo(
    () =>
      Object.values(normalizedPurchaseMetadata).some(
        (value) => value !== null && value !== "",
      ),
    [normalizedPurchaseMetadata],
  );

  const metadataForSubmit: PurchaseEntryRequestPayload["metadata"] =
    metadataHasValues ? normalizedPurchaseMetadata : null;
  const normalizedShoppingLocationName = useMemo(
    () => shoppingLocationName.trim(),
    [shoppingLocationName],
  );
  const hasShoppingLocationSelection =
    shoppingLocationId !== null || normalizedShoppingLocationName.length > 0;

  const canDeriveTotals =
    Boolean(instanceIndex) &&
    normalizedPurchaseMetadata.packageSize !== null &&
    normalizedPurchaseMetadata.quantity !== null &&
    normalizedPurchaseMetadata.packagePrice !== null &&
    normalizedPurchaseMetadata.conversionRate !== null;

  useEffect(() => {
    if (!canDeriveTotals || !instanceIndex) {
      setDerivedTotals({ amount: null, unitPrice: null, totalUsd: null });
      setDeriveError(null);
      return;
    }
    const requestId = deriveRequestId.current + 1;
    deriveRequestId.current = requestId;
    setDeriveError(null);
    const loadDerivation = async () => {
      try {
        const result = await fetchPurchaseEntryCalculation(
          instanceIndex,
          product.id,
          normalizedPurchaseMetadata,
        );
        if (deriveRequestId.current !== requestId) {
          return;
        }
        setDerivedTotals({
          amount: result.amount,
          unitPrice: result.unitPrice,
          totalUsd: result.totalUsd,
        });
      } catch (error) {
        if (deriveRequestId.current !== requestId) {
          return;
        }
        const message =
          error instanceof Error
            ? error.message
            : "Unable to compute purchase totals.";
        setDerivedTotals({ amount: null, unitPrice: null, totalUsd: null });
        setDeriveError(message);
      }
    };
    void loadDerivation();
  }, [canDeriveTotals, instanceIndex, normalizedPurchaseMetadata, product.id]);

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
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Package size
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    step="0.0001"
                    value={packageSize}
                    ref={packageSizeInputRef}
                    onChange={(event) => {
                      setPackageSize(event.target.value);
                      if (statusMessage?.type === "error") {
                        setStatusMessage(null);
                      }
                    }}
                    className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                      shouldShowPackageSizeError
                        ? "border-rose-400 focus:border-rose-500"
                        : "border-neutral-200"
                    }`}
                    placeholder="e.g. 2.5"
                  />
                  {purchaseUnit ? (
                    <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                      {purchaseUnit}
                    </span>
                  ) : null}
                </div>
                {shouldShowPackageSizeError ? (
                  <p className="text-xs text-rose-600">
                    Package size is required and must be greater than 0.
                  </p>
                ) : (
                  <p className="text-xs text-neutral-500">
                    Number of {purchaseUnit ?? "units"} contained in each
                    package.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Package quantity
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={packageQuantity}
                  onChange={(event) => {
                    setPackageQuantity(event.target.value);
                    if (statusMessage?.type === "error") {
                      setStatusMessage(null);
                    }
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    shouldShowPackageQuantityError
                      ? "border-rose-400 focus:border-rose-500"
                      : "border-neutral-200"
                  }`}
                  placeholder="e.g. 3"
                />
                {shouldShowPackageQuantityError ? (
                  <p className="text-xs text-rose-600">
                    Quantity is required and must be greater than 0.
                  </p>
                ) : (
                  <p className="text-xs text-neutral-500">
                    Number of packages purchased during this entry.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Package price (local currency)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={packagePrice}
                  onChange={(event) => {
                    setPackagePrice(event.target.value);
                    if (statusMessage?.type === "error") {
                      setStatusMessage(null);
                    }
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    shouldShowPackagePriceError
                      ? "border-rose-400 focus:border-rose-500"
                      : "border-neutral-200"
                  }`}
                  placeholder="e.g. 12.50"
                />
                {shouldShowPackagePriceError ? (
                  <p className="text-xs text-rose-600">
                    Package price is required and must be greater than 0.
                  </p>
                ) : (
                  <p className="text-xs text-neutral-500">
                    Cost of a single package before shipping or tax.
                  </p>
                )}
                <label className="mt-2 flex items-center gap-2 text-sm font-semibold text-neutral-900">
                  <input
                    type="checkbox"
                    checked={onSale}
                    onChange={(event) => setOnSale(event.target.checked)}
                    className="h-4 w-4 rounded border-neutral-300 text-neutral-900 focus:ring-neutral-900"
                  />
                  <span>On sale</span>
                </label>
              </div>
            </div>
            <div className="space-y-4 md:ml-auto md:w-full">
              <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Derived totals
                </p>
                <dl className="mt-2 space-y-1 text-sm text-neutral-700">
                  <div className="flex items-center justify-between">
                    <dt>Units purchased</dt>
                    <dd className="font-semibold">
                      {derivedAmount !== null
                        ? `${roundToSixDecimals(derivedAmount).toFixed(6)}${purchaseUnit ? ` ${purchaseUnit}` : ""}`
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt>Total cost (USD)</dt>
                    <dd className="font-semibold">
                      {formattedTotalUsd ?? "—"}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt>Unit price (USD)</dt>
                    <dd className="font-semibold">
                      {formattedUnitPrice ?? "—"}
                    </dd>
                  </div>
                </dl>
                {deriveError ? (
                  <p className="mt-2 text-xs text-rose-600">{deriveError}</p>
                ) : null}
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Purchased date
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setPurchasedDate(resolvedDefaultPurchasedDate);
                    }}
                    className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
                  >
                    Use selected default
                  </button>
                </div>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={purchasedDate}
                    onChange={(event) => setPurchasedDate(event.target.value)}
                    className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Best before date
                  </label>
                  <button
                    type="button"
                    onClick={() => setBestBeforeDate(defaultBestBefore)}
                    className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
                  >
                    Use default
                  </button>
                </div>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={bestBeforeDate}
                    onChange={(event) => setBestBeforeDate(event.target.value)}
                    className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <SearchableOptionSelect
              label="Shopping location"
              options={shoppingLocationOptions}
              selectedId={shoppingLocationId}
              onSelectedIdChange={setShoppingLocationId}
              defaultOptionId={defaultShoppingLocationId}
              defaultOptionLabel={defaultShoppingLocationName}
              placeholder="Search shopping locations…"
              resetLabel="Use default"
              inputValue={shoppingLocationName}
              onInputValueChange={setShoppingLocationName}
              allowCustomValue
              onValidationChange={setShoppingLocationError}
              errorMessage="Select or enter a shopping location to continue."
              helperText="Type a new name to create it when you record the purchase."
            />
            <SearchableOptionSelect
              label="Location"
              options={locationOptions}
              selectedId={locationId}
              onSelectedIdChange={setLocationId}
              defaultOptionId={defaultLocationId}
              defaultOptionLabel={defaultLocationName}
              placeholder="Search locations…"
              resetLabel="Use default"
              onValidationChange={setLocationError}
              errorMessage="Select a location from the list to continue."
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Note
            </label>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
              placeholder="Optional context for this purchase"
            />
          </div>
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
      {statusMessage ? (
        <p
          className={`rounded-2xl px-4 py-3 text-sm ${
            statusMessage.type === "success"
              ? "bg-emerald-50 text-emerald-800"
              : "bg-rose-50 text-rose-700"
          }`}
        >
          {statusMessage.text}
        </p>
      ) : null}
    </form>
  );
}
