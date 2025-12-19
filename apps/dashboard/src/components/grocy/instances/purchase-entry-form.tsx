"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchPurchaseEntryDefaults,
  submitPurchaseEntry,
} from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  PurchaseEntryDefaults,
} from "@/lib/grocy/types";

import {
  buildSearchableOptions,
  computeDefaultBestBeforeDate,
  roundToSixDecimals,
} from "./form-utils";
import { resolveQuantityUnit } from "./helpers";
import { SearchableOptionSelect } from "./searchable-option-select";

const SUPPORTED_CURRENCIES: Array<{ value: string; label: string }> = [
  { value: "USD", label: "USD (United States Dollar)" },
  { value: "THB", label: "THB (Thai Baht)" },
];
const DEFAULT_CURRENCY = SUPPORTED_CURRENCIES[0]?.value ?? "USD";

type PurchaseEntryFormProps = {
  product: GrocyProductInventoryEntry;
  instanceIndex: string | null;
  locationNamesById: Record<number, string>;
  shoppingLocationNamesById: Record<number, string>;
  prefetchedDefaults?: PurchaseEntryDefaults | null;
  onClose: () => void;
  onProductChange: (product: GrocyProductInventoryEntry) => void;
  onSuccess: (message: string) => void;
};

export function PurchaseEntryForm({
  product,
  instanceIndex,
  locationNamesById,
  shoppingLocationNamesById,
  prefetchedDefaults = null,
  onClose,
  onProductChange,
  onSuccess,
}: PurchaseEntryFormProps) {
  const normalizeCurrency = useCallback((value: string | null): string => {
    if (!value) {
      return DEFAULT_CURRENCY;
    }
    const normalized = value.trim().toUpperCase();
    return SUPPORTED_CURRENCIES.some((entry) => entry.value === normalized)
      ? normalized
      : DEFAULT_CURRENCY;
  }, []);

  const purchaseUnit = resolveQuantityUnit(product);
  const [packageSize, setPackageSize] = useState("");
  const [packageQuantity, setPackageQuantity] = useState("");
  const [packagePrice, setPackagePrice] = useState("");
  const [currencyValue, setCurrencyValue] = useState(DEFAULT_CURRENCY);
  const [conversionRate, setConversionRate] = useState("1");
  const defaultBestBefore = useMemo(
    () => computeDefaultBestBeforeDate(product.default_best_before_days),
    [product.default_best_before_days],
  );
  const [bestBeforeDate, setBestBeforeDate] = useState(defaultBestBefore);
  const defaultPurchasedDate = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today.toISOString().slice(0, 10);
  }, []);
  const [purchasedDate, setPurchasedDate] = useState(defaultPurchasedDate);
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
  const [locationError, setLocationError] = useState(false);
  const [shoppingLocationError, setShoppingLocationError] = useState(false);
  const [note, setNote] = useState("");
  const [shippingCost, setShippingCost] = useState("");
  const [taxRate, setTaxRate] = useState("");
  const [brand, setBrand] = useState("");
  const [packageSizeDirty, setPackageSizeDirty] = useState(false);
  const [packageQuantityDirty, setPackageQuantityDirty] = useState(false);
  const [packagePriceDirty, setPackagePriceDirty] = useState(false);
  const [currencyDirty, setCurrencyDirty] = useState(false);
  const [conversionRateDirty, setConversionRateDirty] = useState(false);
  const [shippingCostDirty, setShippingCostDirty] = useState(false);
  const [taxRateDirty, setTaxRateDirty] = useState(false);
  const [brandDirty, setBrandDirty] = useState(false);
  const leftColumnRef = useRef<HTMLDivElement | null>(null);
  const [leftColumnHeight, setLeftColumnHeight] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const metadataRequestId = useRef(0);
  const shippingCostDirtyRef = useRef(shippingCostDirty);
  const taxRateDirtyRef = useRef(taxRateDirty);
  const brandDirtyRef = useRef(brandDirty);
  const packageSizeDirtyRef = useRef(packageSizeDirty);
  const packageQuantityDirtyRef = useRef(packageQuantityDirty);
  const packagePriceDirtyRef = useRef(packagePriceDirty);
  const currencyDirtyRef = useRef(currencyDirty);
  const conversionRateDirtyRef = useRef(conversionRateDirty);

  const locationOptions = useMemo(
    () => buildSearchableOptions(locationNamesById),
    [locationNamesById],
  );
  const shoppingLocationOptions = useMemo(
    () => buildSearchableOptions(shoppingLocationNamesById),
    [shoppingLocationNamesById],
  );

  useEffect(() => {
    const node = leftColumnRef.current;
    if (!node) {
      return;
    }
    const updateHeight = () => {
      setLeftColumnHeight(node.getBoundingClientRect().height);
    };
    updateHeight();
    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver(() => updateHeight());
      observer.observe(node);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", updateHeight);
    return () => window.removeEventListener("resize", updateHeight);
  }, []);

  useEffect(() => {
    shippingCostDirtyRef.current = shippingCostDirty;
    taxRateDirtyRef.current = taxRateDirty;
    brandDirtyRef.current = brandDirty;
  }, [shippingCostDirty, taxRateDirty, brandDirty]);

  useEffect(() => {
    packageSizeDirtyRef.current = packageSizeDirty;
    packageQuantityDirtyRef.current = packageQuantityDirty;
    packagePriceDirtyRef.current = packagePriceDirty;
    currencyDirtyRef.current = currencyDirty;
    conversionRateDirtyRef.current = conversionRateDirty;
  }, [
    packageSizeDirty,
    packageQuantityDirty,
    packagePriceDirty,
    currencyDirty,
    conversionRateDirty,
  ]);

  const formResetTrigger = useMemo(
    () => `${instanceIndex ?? "none"}:${product.id}`,
    [instanceIndex, product.id],
  );

  useEffect(() => {
    void formResetTrigger;
    setPackageSize("");
    setPackageQuantity("");
    setPackagePrice("");
    setCurrencyValue(DEFAULT_CURRENCY);
    setConversionRate("1");
    setPackageSizeDirty(false);
    setPackageQuantityDirty(false);
    setPackagePriceDirty(false);
    setCurrencyDirty(false);
    setConversionRateDirty(false);
    setShippingCostDirty(false);
    setTaxRateDirty(false);
    setBrandDirty(false);
    setShippingCost("");
    setTaxRate("");
    setBrand("");
  }, [formResetTrigger]);

  const applyMetadataDefaults = useCallback(
    (metadata: PurchaseEntryDefaults["metadata"] | null): void => {
      if (!packageSizeDirtyRef.current) {
        const sizeValue =
          metadata && metadata.packageSize !== null
            ? metadata.packageSize.toString()
            : "";
        setPackageSize(sizeValue);
      }
      if (!packageQuantityDirtyRef.current) {
        const quantityValue =
          metadata && metadata.quantity !== null
            ? metadata.quantity.toString()
            : "";
        setPackageQuantity(quantityValue);
      }
      if (!packagePriceDirtyRef.current) {
        const priceValue =
          metadata && metadata.packagePrice !== null
            ? metadata.packagePrice.toString()
            : "";
        setPackagePrice(priceValue);
      }
      if (!currencyDirtyRef.current) {
        const currency = normalizeCurrency(metadata?.currency ?? null);
        setCurrencyValue(currency);
      }
      if (!conversionRateDirtyRef.current) {
        const rateValue =
          metadata && metadata.conversionRate !== null
            ? metadata.conversionRate.toString()
            : "1";
        setConversionRate(rateValue);
      }
      if (!shippingCostDirtyRef.current) {
        const shippingValue =
          metadata && metadata.shippingCost !== null
            ? metadata.shippingCost.toString()
            : "";
        setShippingCost(shippingValue);
      }
      if (!taxRateDirtyRef.current) {
        const taxValue =
          metadata && metadata.taxRate !== null
            ? metadata.taxRate.toString()
            : "";
        setTaxRate(taxValue);
      }
      if (!brandDirtyRef.current) {
        const trimmedBrand = metadata?.brand?.trim() ?? "";
        setBrand(trimmedBrand);
      }
    },
    [normalizeCurrency],
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
    packagePriceNumber >= 0;
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

  // total_usd = (package_price * quantity + shipping) * (1 + tax_rate) * conversion_rate
  const derivedAmount =
    isPackageSizeValid && isPackageQuantityValid
      ? packageSizeNumber * packageQuantityNumber
      : null;
  const normalizedShipping =
    isShippingCostValid && shippingCostHasValue ? shippingCostNumber : 0;
  const normalizedTax = isTaxRateValid && taxRateHasValue ? taxRateNumber : 0;
  const subtotalLocal =
    isPackagePriceValid && isPackageQuantityValid
      ? packagePriceNumber * packageQuantityNumber + normalizedShipping
      : null;
  const totalUsd =
    subtotalLocal !== null && isConversionRateValid
      ? subtotalLocal * (1 + normalizedTax) * conversionRateNumber
      : null;
  const derivedUnitPrice =
    derivedAmount && derivedAmount > 0 && totalUsd !== null
      ? totalUsd / derivedAmount
      : null;
  const formattedUnitPrice =
    derivedUnitPrice !== null
      ? roundToSixDecimals(derivedUnitPrice).toFixed(6)
      : null;
  const formattedTotalUsd =
    totalUsd !== null ? roundToSixDecimals(totalUsd).toFixed(2) : null;

  const isFormValid =
    isPackageSizeValid &&
    isPackageQuantityValid &&
    isPackagePriceValid &&
    isConversionRateValid &&
    isShippingCostValid &&
    isTaxRateValid &&
    derivedAmount !== null &&
    derivedUnitPrice !== null &&
    Boolean(instanceIndex) &&
    !locationError &&
    !shoppingLocationError &&
    shoppingLocationId !== null &&
    !isSubmitting;

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    if (
      !instanceIndex ||
      !isFormValid ||
      derivedAmount === null ||
      derivedUnitPrice === null
    ) {
      return;
    }
    setSubmitting(true);
    setStatusMessage(null);
    try {
      const trimmedBrand = brand.trim();
      const trimmedCurrency = normalizeCurrency(currencyValue);
      const metadataPayload = {
        shippingCost: shippingCostHasValue ? shippingCostNumber : null,
        taxRate: taxRateHasValue ? taxRateNumber : null,
        brand: trimmedBrand.length ? trimmedBrand : null,
        packageSize: isPackageSizeValid ? packageSizeNumber : null,
        packagePrice: isPackagePriceValid ? packagePriceNumber : null,
        quantity: isPackageQuantityValid ? packageQuantityNumber : null,
        currency: trimmedCurrency.length ? trimmedCurrency : null,
        conversionRate: isConversionRateValid ? conversionRateNumber : null,
      };
      const metadata = Object.values(metadataPayload).every(
        (value) => value === null || value === "",
      )
        ? null
        : metadataPayload;
      const payload = {
        amount: derivedAmount,
        bestBeforeDate: bestBeforeDate || null,
        purchasedDate: purchasedDate || null,
        pricePerUnit: roundToSixDecimals(derivedUnitPrice),
        locationId,
        shoppingLocationId,
        note: note.trim().length ? note.trim() : null,
        metadata,
      };
      const updatedProduct = await submitPurchaseEntry(
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
                    onChange={(event) => {
                      setPackageSize(event.target.value);
                      setPackageSizeDirty(true);
                    }}
                    className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                      !isPackageSizeValid && packageSizeHasValue
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
                {!isPackageSizeValid && packageSizeHasValue ? (
                  <p className="text-xs text-rose-600">
                    Package size must be greater than 0.
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
                    setPackageQuantityDirty(true);
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    !isPackageQuantityValid && packageQuantityHasValue
                      ? "border-rose-400 focus:border-rose-500"
                      : "border-neutral-200"
                  }`}
                  placeholder="e.g. 3"
                />
                {!isPackageQuantityValid && packageQuantityHasValue ? (
                  <p className="text-xs text-rose-600">
                    Quantity must be greater than 0.
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
                    setPackagePriceDirty(true);
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    !isPackagePriceValid && packagePriceHasValue
                      ? "border-rose-400 focus:border-rose-500"
                      : "border-neutral-200"
                  }`}
                  placeholder="e.g. 12.50"
                />
                {!isPackagePriceValid && packagePriceHasValue ? (
                  <p className="text-xs text-rose-600">
                    Enter a valid price per package.
                  </p>
                ) : (
                  <p className="text-xs text-neutral-500">
                    Cost of a single package before shipping or tax.
                  </p>
                )}
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
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Purchased date
                  </label>
                  <button
                    type="button"
                    onClick={() => setPurchasedDate(defaultPurchasedDate)}
                    className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
                  >
                    Use today
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
              onValidationChange={setShoppingLocationError}
              errorMessage="Select a shopping location from the list to continue."
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
                    setBrandDirty(true);
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
                    setShippingCostDirty(true);
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
                    setTaxRateDirty(true);
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
                    setCurrencyDirty(true);
                  }}
                  className="w-full rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                >
                  {SUPPORTED_CURRENCIES.map((option) => (
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
                    setConversionRateDirty(true);
                  }}
                  className={`w-full rounded-2xl border px-4 py-2 text-base text-neutral-900 focus:outline-none ${
                    isConversionRateValid
                      ? "border-neutral-200 focus:border-neutral-900"
                      : "border-rose-400 focus:border-rose-500"
                  }`}
                  placeholder="e.g. 1.00"
                />
                <p className="text-xs text-neutral-500">
                  Multiply local currency amounts by this rate to convert to
                  USD.
                </p>
                {!isConversionRateValid ? (
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
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-neutral-200 px-5 py-2 text-sm font-semibold text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!isFormValid}
          className={`rounded-full px-5 py-2 text-sm font-semibold text-white transition ${
            isFormValid
              ? "bg-neutral-900 hover:bg-neutral-800"
              : "bg-neutral-400"
          }`}
        >
          {isSubmitting ? "Submitting…" : "Record purchase"}
        </button>
      </div>
    </form>
  );
}
