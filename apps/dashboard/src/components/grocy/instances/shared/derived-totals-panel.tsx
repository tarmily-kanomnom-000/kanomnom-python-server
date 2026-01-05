type DerivedTotalsPanelProps = {
  derivedAmount: number | null;
  derivedUnitPrice: number | null;
  derivedTotalUsd: number | null;
  unitLabel: string | null;
  unitPriceFormatter: (value: number) => string;
  totalFormatter: (value: number) => string;
  error: string | null;
};

export function DerivedTotalsPanel({
  derivedAmount,
  derivedUnitPrice,
  derivedTotalUsd,
  unitLabel,
  unitPriceFormatter,
  totalFormatter,
  error,
}: DerivedTotalsPanelProps) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-neutral-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Derived totals
      </p>
      <dl className="mt-2 space-y-1 text-sm text-neutral-700">
        <div className="flex items-center justify-between">
          <dt>Units purchased</dt>
          <dd className="font-semibold">
            {derivedAmount !== null
              ? `${derivedAmount}${unitLabel ? ` ${unitLabel}` : ""}`
              : "—"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt>Total cost (USD)</dt>
          <dd className="font-semibold">
            {derivedTotalUsd !== null ? totalFormatter(derivedTotalUsd) : "—"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt>Unit price (USD)</dt>
          <dd className="font-semibold">
            {derivedUnitPrice !== null
              ? unitPriceFormatter(derivedUnitPrice)
              : "—"}
          </dd>
        </div>
      </dl>
      {error ? <p className="mt-2 text-xs text-rose-600">{error}</p> : null}
    </div>
  );
}
