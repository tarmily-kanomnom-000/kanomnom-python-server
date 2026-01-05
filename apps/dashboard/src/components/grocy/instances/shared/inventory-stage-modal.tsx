import { useEffect, useMemo, useRef, useState } from "react";
import type { StagedInterpretation } from "./use-inventory-staging";

type StageEntryType = "tare" | "package" | "manual" | null;

type Props = {
  isOpen: boolean;
  hasTareWeight: boolean;
  tareWeight: number;
  quantityUnit: string | null;
  stagedInterpretation: StagedInterpretation;
  stageEntryType: StageEntryType;
  onStageEntryTypeChange: (next: StageEntryType) => void;
  onClose: () => void;
  onAddTare: (grossAmount: number) => void;
  onAddManual: (amount: number) => void;
  onAddPackage: (quantity: number, packageSize: number) => void;
};

export function InventoryStageModal({
  isOpen,
  hasTareWeight,
  tareWeight,
  quantityUnit,
  stagedInterpretation,
  stageEntryType,
  onStageEntryTypeChange,
  onClose,
  onAddTare,
  onAddManual,
  onAddPackage,
}: Props) {
  const stagedWeighedInputRef = useRef<HTMLInputElement | null>(null);
  const packageCountInputRef = useRef<HTMLInputElement | null>(null);
  const manualAmountInputRef = useRef<HTMLInputElement | null>(null);

  const [weighedAmount, setWeighedAmount] = useState("");
  const [packageCount, setPackageCount] = useState("");
  const [packageSize, setPackageSize] = useState("");
  const [manualAmount, setManualAmount] = useState("");

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (stageEntryType === "tare") {
      stagedWeighedInputRef.current?.focus();
    } else if (stageEntryType === "package") {
      packageCountInputRef.current?.focus();
    } else if (stageEntryType === "manual") {
      manualAmountInputRef.current?.focus();
    }
  }, [isOpen, stageEntryType]);

  useEffect(() => {
    if (
      hasTareWeight &&
      stagedInterpretation === "absolute" &&
      stageEntryType === "manual"
    ) {
      onStageEntryTypeChange("tare");
    }
  }, [
    hasTareWeight,
    stagedInterpretation,
    stageEntryType,
    onStageEntryTypeChange,
  ]);

  const parsedWeighedAmount = Number(weighedAmount);
  const parsedPackageCount = Number(packageCount);
  const parsedPackageSize = Number(packageSize);
  const parsedManualAmount = Number(manualAmount);

  const isWeighedAmountValid =
    weighedAmount.trim().length > 0 &&
    Number.isFinite(parsedWeighedAmount) &&
    parsedWeighedAmount >= 0;
  const isWeighedBelowTare =
    hasTareWeight && isWeighedAmountValid && parsedWeighedAmount < tareWeight;
  const netWeighedAmount = Math.max(parsedWeighedAmount - tareWeight, 0);
  const canAddWeighedEntry =
    isWeighedAmountValid && !isWeighedBelowTare && isOpen;

  const packageEntryTotal =
    Number.isFinite(parsedPackageCount) && Number.isFinite(parsedPackageSize)
      ? parsedPackageCount * parsedPackageSize
      : 0;
  const canAddPackageEntry =
    packageCount.trim().length > 0 &&
    packageSize.trim().length > 0 &&
    Number.isFinite(parsedPackageCount) &&
    Number.isFinite(parsedPackageSize) &&
    parsedPackageCount > 0 &&
    parsedPackageSize > 0;

  const canAddManualEntry =
    manualAmount.trim().length > 0 &&
    Number.isFinite(parsedManualAmount) &&
    parsedManualAmount >= 0 &&
    (!hasTareWeight || stagedInterpretation === "delta");

  const normalizedQuantityUnit = useMemo(
    () => (quantityUnit ? quantityUnit : null),
    [quantityUnit],
  );

  const closeAndReset = () => {
    setWeighedAmount("");
    setPackageCount("");
    setPackageSize("");
    setManualAmount("");
    onStageEntryTypeChange(null);
    onClose();
  };

  const formatAmountWithUnit = (value: number): string => {
    if (!Number.isFinite(value)) {
      return "—";
    }
    const rounded = Math.round(value * 100) / 100;
    const amountLabel = rounded.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    });
    return normalizedQuantityUnit
      ? `${amountLabel} ${normalizedQuantityUnit}`
      : amountLabel;
  };

  return !isOpen ? null : (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-10">
      <div className="w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Add to stage
            </p>
            <p className="text-sm text-neutral-800">
              Choose what you are adding, then enter the details.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
          >
            ✕
          </button>
        </div>
        <div className="mt-4 flex gap-2">
          {!hasTareWeight || stagedInterpretation === "delta" ? (
            <button
              type="button"
              onClick={() => onStageEntryTypeChange("manual")}
              className={`flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                stageEntryType === "manual"
                  ? "border-neutral-900 bg-neutral-50 text-neutral-900"
                  : "border-neutral-200 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
              }`}
            >
              {hasTareWeight ? "Change amount" : "Measurement"}
            </button>
          ) : null}
          {hasTareWeight ? (
            <button
              type="button"
              onClick={() => onStageEntryTypeChange("tare")}
              className={`flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
                stageEntryType === "tare"
                  ? "border-neutral-900 bg-neutral-50 text-neutral-900"
                  : "border-neutral-200 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
              }`}
            >
              Weighed (tare)
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => onStageEntryTypeChange("package")}
            className={`flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
              stageEntryType === "package"
                ? "border-neutral-900 bg-neutral-50 text-neutral-900"
                : "border-neutral-200 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
            }`}
          >
            Packages
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {stageEntryType === "manual" ? (
            <div className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <p className="text-sm font-semibold text-neutral-900">
                {hasTareWeight ? "Change amount" : "Measurement"}
              </p>
              <p className="text-xs text-neutral-600">
                {hasTareWeight
                  ? "Enter the amount to add or remove. Tare weight isn't needed for adjustments."
                  : "Enter a measured amount (e.g., what is left in an opened item without tare handling)."}
              </p>
              <div className="relative">
                <input
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  value={manualAmount}
                  ref={manualAmountInputRef}
                  onChange={(event) => setManualAmount(event.target.value)}
                  className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    quantityUnit ? "pr-16" : ""
                  }`}
                  placeholder={
                    hasTareWeight
                      ? "Enter the change amount"
                      : "Enter measured amount"
                  }
                />
                {quantityUnit ? (
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                    {quantityUnit}
                  </span>
                ) : null}
              </div>
              {!canAddManualEntry && manualAmount.trim().length > 0 ? (
                <p className="text-xs text-rose-600">
                  Enter a non-negative number.
                </p>
              ) : null}
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => {
                    if (!canAddManualEntry) {
                      return;
                    }
                    onAddManual(parsedManualAmount);
                    setManualAmount("");
                    closeAndReset();
                  }}
                  disabled={!canAddManualEntry}
                  className={`rounded-full px-4 py-2 text-sm font-semibold text-white transition ${
                    canAddManualEntry
                      ? "bg-neutral-900 hover:bg-neutral-800"
                      : "bg-neutral-400"
                  }`}
                >
                  Add entry
                </button>
              </div>
            </div>
          ) : null}
          {stageEntryType === "tare" ? (
            <div className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <p className="text-sm font-semibold text-neutral-900">
                Weighed tare container
              </p>
              <p className="text-xs text-neutral-600">
                Weigh the container holding opened product and enter the gross
                weight (container + contents).
              </p>
              <div className="relative">
                <input
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  value={weighedAmount}
                  ref={stagedWeighedInputRef}
                  onChange={(event) => setWeighedAmount(event.target.value)}
                  className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    quantityUnit ? "pr-16" : ""
                  }`}
                  placeholder="Gross weight incl. tare"
                />
                {quantityUnit ? (
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                    {quantityUnit}
                  </span>
                ) : null}
              </div>
              {!isWeighedAmountValid && weighedAmount.trim().length > 0 ? (
                <p className="text-xs text-rose-600">
                  Enter a non-negative number.
                </p>
              ) : isWeighedBelowTare ? (
                <p className="text-xs text-rose-600">
                  Measurement must be at least the tare weight (
                  {formatAmountWithUnit(tareWeight)}).
                </p>
              ) : hasTareWeight ? (
                <p className="text-xs text-neutral-500">
                  Net after tare: {formatAmountWithUnit(netWeighedAmount)}.
                </p>
              ) : null}
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => {
                    if (!canAddWeighedEntry) {
                      return;
                    }
                    onAddTare(parsedWeighedAmount);
                    setWeighedAmount("");
                    closeAndReset();
                  }}
                  disabled={!canAddWeighedEntry}
                  className={`rounded-full px-4 py-2 text-sm font-semibold text-white transition ${
                    canAddWeighedEntry
                      ? "bg-neutral-900 hover:bg-neutral-800"
                      : "bg-neutral-400"
                  }`}
                >
                  Add entry
                </button>
              </div>
            </div>
          ) : null}
          {stageEntryType === "package" ? (
            <div className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <p className="text-sm font-semibold text-neutral-900">
                Unopened packages
              </p>
              <p className="text-xs text-neutral-600">
                Count unopened packages and specify the package size.
              </p>
              <div className="grid grid-cols-[1fr_1fr] gap-2">
                <div className="relative">
                  <input
                    type="number"
                    inputMode="numeric"
                    step="1"
                    min="0"
                    value={packageCount}
                    ref={packageCountInputRef}
                    onChange={(event) => setPackageCount(event.target.value)}
                    className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                    placeholder="Packages"
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                    ×
                  </span>
                </div>
                <div className="relative">
                  <input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min="0"
                    value={packageSize}
                    onChange={(event) => setPackageSize(event.target.value)}
                    className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                      quantityUnit ? "pr-16" : ""
                    }`}
                    placeholder="Package size"
                  />
                  {quantityUnit ? (
                    <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                      {quantityUnit}
                    </span>
                  ) : null}
                </div>
              </div>
              {packageCount.trim().length === 0 ||
              packageSize.trim().length === 0 ? (
                <p className="text-xs text-neutral-500">
                  Use this for sealed units (e.g., 3 × 500g bags).
                </p>
              ) : !canAddPackageEntry ? (
                <p className="text-xs text-rose-600">
                  Enter quantities greater than zero.
                </p>
              ) : (
                <p className="text-xs text-neutral-500">
                  This entry adds {formatAmountWithUnit(packageEntryTotal)} to
                  the total.
                </p>
              )}
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => {
                    if (!canAddPackageEntry) {
                      return;
                    }
                    onAddPackage(parsedPackageCount, parsedPackageSize);
                    setPackageCount("");
                    setPackageSize("");
                    closeAndReset();
                  }}
                  disabled={!canAddPackageEntry}
                  className={`rounded-full px-4 py-2 text-sm font-semibold text-white transition ${
                    canAddPackageEntry
                      ? "bg-neutral-900 hover:bg-neutral-800"
                      : "bg-neutral-400"
                  }`}
                >
                  Add entry
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
