import { useCallback, useMemo, useRef, useState } from "react";
import { useDirtyStringField } from "@/hooks/use-dirty-string-field";
import type {
  PurchaseEntryDefaults,
  PurchaseEntryRequestPayload,
} from "@/lib/grocy/types";

export type PurchaseMetadataPayload = NonNullable<
  PurchaseEntryRequestPayload["metadata"]
>;

type NormalizeCurrencyFn = (value: string | null) => string;

type UsePurchaseMetadataArgs = {
  defaultCurrency: string;
  normalizeCurrency: NormalizeCurrencyFn;
};

type UsePurchaseMetadataResult = {
  packageSize: string;
  setPackageSize: (value: string) => void;
  packageQuantity: string;
  setPackageQuantity: (value: string) => void;
  packagePrice: string;
  setPackagePrice: (value: string) => void;
  currencyValue: string;
  setCurrencyValue: (value: string) => void;
  conversionRate: string;
  setConversionRate: (value: string) => void;
  shippingCost: string;
  setShippingCost: (value: string) => void;
  taxRate: string;
  setTaxRate: (value: string) => void;
  brand: string;
  setBrand: (value: string) => void;
  onSale: boolean;
  setOnSale: (value: boolean) => void;
  resetAll: () => void;
  applyDefaults: (metadata: PurchaseEntryDefaults["metadata"] | null) => void;
  packageSizeHasValue: boolean;
  packageQuantityHasValue: boolean;
  packagePriceHasValue: boolean;
  conversionRateHasValue: boolean;
  shippingCostHasValue: boolean;
  taxRateHasValue: boolean;
  isPackageSizeValid: boolean;
  isPackageQuantityValid: boolean;
  isPackagePriceValid: boolean;
  isConversionRateValid: boolean;
  isShippingCostValid: boolean;
  isTaxRateValid: boolean;
  normalizedPurchaseMetadata: PurchaseMetadataPayload;
  metadataHasValues: boolean;
  canDeriveTotals: boolean;
};

export function usePurchaseMetadata({
  defaultCurrency,
  normalizeCurrency,
}: UsePurchaseMetadataArgs): UsePurchaseMetadataResult {
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
  } = useDirtyStringField(defaultCurrency);
  const {
    value: conversionRate,
    set: setConversionRate,
    hydrate: hydrateConversionRate,
    reset: resetConversionRate,
  } = useDirtyStringField("1");
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

  const metadataHasValues = useMemo(() => {
    const hasBrand = brand.trim().length > 0;
    const hasShipping = isShippingCostValid && shippingCostHasValue;
    const hasTax = isTaxRateValid && taxRateHasValue;
    const hasPackageSize = isPackageSizeValid && packageSizeHasValue;
    const hasPackageQuantity =
      isPackageQuantityValid && packageQuantityHasValue;
    const hasPackagePrice = isPackagePriceValid && packagePriceHasValue;
    const hasConversionOverride =
      isConversionRateValid &&
      conversionRateHasValue &&
      conversionRate.trim() !== "1";
    const hasCurrencyOverride =
      currencyValue.trim().toUpperCase() !== defaultCurrency;
    const hasOnSale = onSaleDirtyRef.current || onSale === true;
    return (
      hasBrand ||
      hasShipping ||
      hasTax ||
      hasPackageSize ||
      hasPackageQuantity ||
      hasPackagePrice ||
      hasConversionOverride ||
      hasCurrencyOverride ||
      hasOnSale
    );
  }, [
    brand,
    conversionRate,
    conversionRateHasValue,
    currencyValue,
    defaultCurrency,
    isConversionRateValid,
    isPackagePriceValid,
    isPackageQuantityValid,
    isPackageSizeValid,
    isShippingCostValid,
    isTaxRateValid,
    onSale,
    packagePriceHasValue,
    packageQuantityHasValue,
    packageSizeHasValue,
    shippingCostHasValue,
    taxRateHasValue,
  ]);

  const canDeriveTotals =
    normalizedPurchaseMetadata.packageSize !== null &&
    normalizedPurchaseMetadata.quantity !== null &&
    normalizedPurchaseMetadata.packagePrice !== null &&
    normalizedPurchaseMetadata.conversionRate !== null;

  const resetAll = useCallback(() => {
    resetPackageSize("");
    resetPackageQuantity("");
    resetPackagePrice("");
    resetCurrencyValue(defaultCurrency);
    resetConversionRate("1");
    resetShippingCost("");
    resetTaxRate("");
    resetBrand("");
    setOnSaleState(false);
    onSaleDirtyRef.current = false;
  }, [
    resetBrand,
    resetConversionRate,
    resetCurrencyValue,
    resetPackagePrice,
    resetPackageQuantity,
    resetPackageSize,
    resetShippingCost,
    resetTaxRate,
    defaultCurrency,
  ]);

  const applyDefaults = useCallback(
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
      setOnSaleState(metadata?.onSale ?? false);
      onSaleDirtyRef.current = false;
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
    ],
  );

  return {
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
    setOnSale: (next) => {
      onSaleDirtyRef.current = true;
      setOnSaleState(next);
    },
    resetAll,
    applyDefaults,
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
  };
}
