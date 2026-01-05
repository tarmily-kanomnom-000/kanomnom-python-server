type PurchaseMetadataPanelProps = {
  brand: string;
  setBrand: (value: string) => void;
  shippingCost: string;
  setShippingCost: (value: string) => void;
  taxRate: string;
  setTaxRate: (value: string) => void;
  currencyValue: string;
  setCurrencyValue: (value: string) => void;
  conversionRate: string;
  setConversionRate: (value: string) => void;
  isShippingCostValid: boolean;
  isTaxRateValid: boolean;
  shouldShowConversionRateError: boolean;
  statusMessageType: "success" | "error" | null;
  clearStatusMessage: () => void;
  currencyOptions: { label: string; value: string }[];
};

export function PurchaseMetadataPanel({
  brand,
  setBrand,
  shippingCost,
  setShippingCost,
  taxRate,
  setTaxRate,
  currencyValue,
  setCurrencyValue,
  conversionRate,
  setConversionRate,
  isShippingCostValid,
  isTaxRateValid,
  shouldShowConversionRateError,
  statusMessageType,
  clearStatusMessage,
  currencyOptions,
}: PurchaseMetadataPanelProps) {
  return (
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
              setCurrencyValue(event.target.value);
            }}
            className="w-full rounded-2xl border border-neutral-200 bg-white px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
          >
            {currencyOptions.map((option) => (
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
              if (statusMessageType === "error") {
                clearStatusMessage();
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
            Multiply local currency amounts by this rate to convert to USD.
          </p>
          {shouldShowConversionRateError ? (
            <p className="text-xs text-rose-600">
              Conversion rate must be greater than 0.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
