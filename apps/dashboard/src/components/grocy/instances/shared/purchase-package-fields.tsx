type PurchasePackageFieldsProps = {
  purchaseUnit: string | null;
  packageSize: string;
  setPackageSize: (value: string) => void;
  packageQuantity: string;
  setPackageQuantity: (value: string) => void;
  packagePrice: string;
  setPackagePrice: (value: string) => void;
  onSale: boolean;
  setOnSale: (value: boolean) => void;
  shouldShowPackageSizeError: boolean;
  shouldShowPackageQuantityError: boolean;
  shouldShowPackagePriceError: boolean;
  statusMessageType: "success" | "error" | null;
  clearStatusMessage: () => void;
};

export function PurchasePackageFields({
  purchaseUnit,
  packageSize,
  setPackageSize,
  packageQuantity,
  setPackageQuantity,
  packagePrice,
  setPackagePrice,
  onSale,
  setOnSale,
  shouldShowPackageSizeError,
  shouldShowPackageQuantityError,
  shouldShowPackagePriceError,
  statusMessageType,
  clearStatusMessage,
}: PurchasePackageFieldsProps) {
  return (
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
              if (statusMessageType === "error") {
                clearStatusMessage();
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
            Number of {purchaseUnit ?? "units"} contained in each package.
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
            if (statusMessageType === "error") {
              clearStatusMessage();
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
            if (statusMessageType === "error") {
              clearStatusMessage();
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
  );
}
