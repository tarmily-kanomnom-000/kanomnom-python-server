import type { InventoryStagedEntry } from "./use-inventory-staging";

type Props = {
  entries: InventoryStagedEntry[];
  hasTareWeight: boolean;
  quantityUnit: string | null;
  stagedTotal: number;
  stagedNetPreview: number | null;
  onRemove: (entryId: string) => void;
  onAddClick: () => void;
};

const formatAmountWithUnit = (value: number, unit: string | null): string => {
  if (!Number.isFinite(value)) {
    return "—";
  }
  const rounded = Math.round(value * 100) / 100;
  const amountLabel = rounded.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
  return unit ? `${amountLabel} ${unit}` : amountLabel;
};

export function StagedEntriesList({
  entries,
  hasTareWeight,
  quantityUnit,
  stagedTotal,
  stagedNetPreview,
  onRemove,
  onAddClick,
}: Props) {
  return (
    <div className="space-y-3">
      <div className="space-y-2 rounded-2xl border border-neutral-200 bg-white p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-neutral-900">
              Staged entries
            </p>
            <p className="text-[11px] text-neutral-500">
              Combine staged measurements and unopened packages before
              submitting to Grocy.
            </p>
          </div>
          <p className="text-sm font-semibold text-neutral-900">
            {formatAmountWithUnit(stagedTotal, quantityUnit)}
          </p>
        </div>
        {entries.length ? (
          <div className="space-y-2">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-neutral-100 bg-neutral-50 px-3 py-2"
              >
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-neutral-900">
                    {entry.kind === "tare"
                      ? "Weighed container"
                      : entry.kind === "package"
                        ? "Package entry"
                        : "Measured entry"}
                  </p>
                  <p className="text-xs text-neutral-600">
                    {entry.kind === "tare"
                      ? `Gross ${formatAmountWithUnit(entry.grossAmount, quantityUnit)}${
                          hasTareWeight
                            ? ` • Net ${formatAmountWithUnit(entry.netAmount, quantityUnit)}`
                            : ""
                        }`
                      : entry.kind === "package"
                        ? `${entry.quantity.toLocaleString()} × ${formatAmountWithUnit(entry.packageSize, quantityUnit)} = ${formatAmountWithUnit(entry.submissionAmount, quantityUnit)}`
                        : `Amount: ${formatAmountWithUnit(entry.submissionAmount, quantityUnit)}`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemove(entry.id)}
                  className="rounded-full border border-neutral-200 px-3 py-1 text-xs font-semibold text-neutral-600 transition hover:border-neutral-900 hover:text-neutral-900"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-neutral-500">
            Stage opened-item measurements
            {hasTareWeight ? " with tare weight" : ""} and unopened package
            counts. The total below is what will be sent to Grocy.
          </p>
        )}
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={onAddClick}
            className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            Add to stage
          </button>
        </div>
        {stagedNetPreview !== null ? (
          <p className="text-[11px] text-neutral-500">
            Net after tare for weighed entries:{" "}
            {formatAmountWithUnit(stagedNetPreview, quantityUnit)}.
          </p>
        ) : null}
      </div>
    </div>
  );
}
