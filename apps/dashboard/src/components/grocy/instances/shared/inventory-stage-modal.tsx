import {
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ProductUnitConversionDefinition } from "@/lib/grocy/types";
import { resolveUnitConversionFactor } from "@/lib/grocy/unit-conversions";

type StageEntryType = "measurement" | "package" | null;

type Props = {
  isOpen: boolean;
  hasTareWeight: boolean;
  tareWeight: number;
  quantityUnit: string | null;
  unitConversions: ProductUnitConversionDefinition[];
  stageEntryType: StageEntryType;
  onStageEntryTypeChange: (next: StageEntryType) => void;
  onClose: () => void;
  onAddPackage: (quantity: number, packageSize: number) => void;
  onAddMeasurement: (entry: MeasurementEntryInput) => void;
};

type MeasurementEntryInput = {
  grossAmount: number;
  netAmount: number;
  submissionAmount: number;
  fromUnit: string;
  toUnit: string;
  factor: number;
  tareApplied: boolean;
  tareAmount: number | null;
};

export function InventoryStageModal({
  isOpen,
  hasTareWeight,
  tareWeight,
  quantityUnit,
  unitConversions,
  stageEntryType,
  onStageEntryTypeChange,
  onClose,
  onAddPackage,
  onAddMeasurement,
}: Props) {
  const measurementAmountInputRef = useRef<HTMLInputElement | null>(null);
  const measurementUnitInputRef = useRef<HTMLInputElement | null>(null);
  const packageCountInputRef = useRef<HTMLInputElement | null>(null);

  const [packageCount, setPackageCount] = useState("");
  const [packageSize, setPackageSize] = useState("");
  const [measurementAmount, setMeasurementAmount] = useState("");
  const [measurementUnit, setMeasurementUnit] = useState("");
  const [isUnitDropdownOpen, setUnitDropdownOpen] = useState(false);
  const [isUnitFiltering, setUnitFiltering] = useState(false);
  const [applyTareWeight, setApplyTareWeight] = useState(true);
  const [convertedAmount, setConvertedAmount] = useState("");
  const [isConvertedManual, setIsConvertedManual] = useState(false);
  const [tareAmount, setTareAmount] = useState("");
  const [isTareManual, setIsTareManual] = useState(false);
  const [isTareToggleManual, setIsTareToggleManual] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    if (stageEntryType === "measurement") {
      measurementAmountInputRef.current?.focus();
    } else if (stageEntryType === "package") {
      packageCountInputRef.current?.focus();
    }
  }, [isOpen, stageEntryType]);

  const parsedMeasurementAmount = Number(measurementAmount);
  const parsedPackageCount = Number(packageCount);
  const parsedPackageSize = Number(packageSize);

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

  const normalizedQuantityUnit = useMemo(
    () => (quantityUnit ? quantityUnit : null),
    [quantityUnit],
  );

  const selectableUnits = useMemo(() => {
    if (!normalizedQuantityUnit) {
      return [];
    }
    const normalizedDefault = normalizedQuantityUnit.trim().toLowerCase();
    const universalConversions = unitConversions.filter(
      (conversion) => conversion.source === "universal",
    );
    const productConversions = unitConversions.filter(
      (conversion) => conversion.source === "product",
    );
    const universalUnits = new Set<string>();
    universalConversions.forEach((conversion) => {
      if (conversion.from_unit) {
        universalUnits.add(conversion.from_unit);
      }
      if (conversion.to_unit) {
        universalUnits.add(conversion.to_unit);
      }
    });
    universalUnits.add(normalizedQuantityUnit);
    const connectedUniversalUnits = Array.from(universalUnits).filter(
      (unit) => {
        const normalized = unit.trim().toLowerCase();
        if (!normalized) {
          return false;
        }
        if (normalized === normalizedDefault) {
          return true;
        }
        return (
          resolveUnitConversionFactor(
            universalConversions,
            unit,
            normalizedQuantityUnit,
          ) !== null
        );
      },
    );
    const productUnits = new Set<string>();
    productConversions.forEach((conversion) => {
      const fromNormalized = conversion.from_unit.trim().toLowerCase();
      const toNormalized = conversion.to_unit.trim().toLowerCase();
      if (fromNormalized === normalizedDefault) {
        productUnits.add(conversion.to_unit);
      } else if (toNormalized === normalizedDefault) {
        productUnits.add(conversion.from_unit);
      }
    });
    const units = new Set<string>([
      normalizedQuantityUnit,
      ...connectedUniversalUnits,
      ...productUnits,
    ]);
    const ordered = Array.from(units);
    ordered.sort((a, b) => a.localeCompare(b));
    const defaultIndex = ordered.findIndex(
      (unit) => unit.trim().toLowerCase() === normalizedDefault,
    );
    if (defaultIndex > 0) {
      const [defaultUnit] = ordered.splice(defaultIndex, 1);
      ordered.unshift(defaultUnit);
    }
    return ordered;
  }, [normalizedQuantityUnit, unitConversions]);

  const measurementUnitSuggestions = useMemo(() => {
    if (!isUnitFiltering) {
      return selectableUnits;
    }
    const normalized = measurementUnit.trim().toLowerCase();
    if (!normalized) {
      return selectableUnits;
    }
    return selectableUnits.filter((unit) =>
      unit.toLowerCase().includes(normalized),
    );
  }, [isUnitFiltering, measurementUnit, selectableUnits]);

  useEffect(() => {
    if (stageEntryType !== "measurement") {
      return;
    }
    if (!normalizedQuantityUnit) {
      return;
    }
    if (!measurementUnit) {
      setMeasurementUnit(normalizedQuantityUnit);
      return;
    }
    const normalized = measurementUnit.trim().toLowerCase();
    const exactMatch = selectableUnits.find(
      (unit) => unit.trim().toLowerCase() === normalized,
    );
    if (exactMatch && exactMatch !== measurementUnit) {
      setMeasurementUnit(exactMatch);
    }
  }, [
    measurementUnit,
    normalizedQuantityUnit,
    selectableUnits,
    stageEntryType,
  ]);

  const conversionFactor = useMemo(() => {
    if (!normalizedQuantityUnit || !measurementUnit) {
      return null;
    }
    if (
      measurementUnit.trim().toLowerCase() ===
      normalizedQuantityUnit.trim().toLowerCase()
    ) {
      return 1;
    }
    return resolveUnitConversionFactor(
      unitConversions,
      measurementUnit,
      normalizedQuantityUnit,
    );
  }, [measurementUnit, normalizedQuantityUnit, unitConversions]);

  const conversionTareAmount = useMemo(() => {
    if (!measurementUnit || !normalizedQuantityUnit) {
      return null;
    }
    const normalizedFrom = measurementUnit.trim().toLowerCase();
    const normalizedDefault = normalizedQuantityUnit.trim().toLowerCase();
    const direct = unitConversions.find((entry) => {
      if (entry.source !== "product") {
        return false;
      }
      const from = entry.from_unit.trim().toLowerCase();
      const to = entry.to_unit.trim().toLowerCase();
      return (
        (from === normalizedDefault && to === normalizedFrom) ||
        (from === normalizedFrom && to === normalizedDefault)
      );
    });
    if (!direct || typeof direct.tare !== "number") {
      return null;
    }
    if (direct.to_unit.trim().toLowerCase() !== normalizedFrom) {
      return null;
    }
    return direct.tare;
  }, [measurementUnit, normalizedQuantityUnit, unitConversions]);

  const hasTareOption =
    hasTareWeight || typeof conversionTareAmount === "number";

  const defaultTareAmount = useMemo(() => {
    if (typeof conversionTareAmount === "number") {
      return conversionTareAmount;
    }
    if (hasTareWeight) {
      return tareWeight;
    }
    return null;
  }, [conversionTareAmount, hasTareWeight, tareWeight]);

  useEffect(() => {
    if (!isOpen || stageEntryType !== "measurement") {
      return;
    }
    setApplyTareWeight(hasTareOption);
    setConvertedAmount("");
    setIsConvertedManual(false);
    setTareAmount(defaultTareAmount !== null ? String(defaultTareAmount) : "");
    setIsTareManual(false);
    setIsTareToggleManual(false);
  }, [defaultTareAmount, hasTareOption, isOpen, stageEntryType]);

  const measurementValid =
    measurementAmount.trim().length > 0 &&
    Number.isFinite(parsedMeasurementAmount) &&
    parsedMeasurementAmount >= 0;

  useEffect(() => {
    if (stageEntryType !== "measurement") {
      return;
    }
    if (!hasTareOption) {
      return;
    }
    if (isTareToggleManual) {
      return;
    }
    setApplyTareWeight(true);
  }, [hasTareOption, isTareToggleManual, stageEntryType]);

  useEffect(() => {
    if (stageEntryType !== "measurement") {
      return;
    }
    if (!hasTareOption || !applyTareWeight) {
      return;
    }
    if (isTareManual) {
      return;
    }
    if (defaultTareAmount === null) {
      return;
    }
    setTareAmount(String(defaultTareAmount));
  }, [
    applyTareWeight,
    defaultTareAmount,
    hasTareOption,
    isTareManual,
    stageEntryType,
  ]);

  const parsedConvertedAmount = Number(convertedAmount);
  const convertedValid =
    convertedAmount.trim().length > 0 &&
    Number.isFinite(parsedConvertedAmount) &&
    parsedConvertedAmount >= 0;
  const tareApplied = hasTareOption && applyTareWeight;
  const parsedTareAmount = Number(tareAmount);
  const tareValid =
    !tareApplied ||
    (tareAmount.trim().length > 0 &&
      Number.isFinite(parsedTareAmount) &&
      parsedTareAmount >= 0);
  const tareTooLarge =
    tareApplied && tareValid && parsedTareAmount > parsedMeasurementAmount;
  const measuredNetAmount =
    measurementValid && tareValid
      ? Math.max(
          parsedMeasurementAmount - (tareApplied ? parsedTareAmount : 0),
          0,
        )
      : null;
  const calculatedConvertedAmount =
    measuredNetAmount !== null && conversionFactor !== null
      ? roundToSix(measuredNetAmount * conversionFactor)
      : null;
  const netAmount = convertedValid ? parsedConvertedAmount : null;

  useEffect(() => {
    if (stageEntryType !== "measurement") {
      return;
    }
    if (isConvertedManual) {
      return;
    }
    if (calculatedConvertedAmount === null) {
      setConvertedAmount("");
      return;
    }
    setConvertedAmount(String(calculatedConvertedAmount));
  }, [calculatedConvertedAmount, isConvertedManual, stageEntryType]);

  const canAddMeasurementEntry =
    measurementValid &&
    conversionFactor !== null &&
    measurementUnit.trim().length > 0 &&
    convertedValid &&
    tareValid &&
    !tareTooLarge;

  const addMeasurementEntry = () => {
    if (
      !canAddMeasurementEntry ||
      netAmount === null ||
      !normalizedQuantityUnit
    ) {
      return;
    }
    onAddMeasurement({
      grossAmount: parsedMeasurementAmount,
      netAmount: netAmount,
      submissionAmount: tareApplied ? netAmount : parsedConvertedAmount,
      fromUnit: measurementUnit,
      toUnit: normalizedQuantityUnit,
      factor: conversionFactor ?? 1,
      tareApplied: tareApplied,
      tareAmount: tareApplied ? parsedTareAmount : null,
    });
    closeAndReset();
  };

  const addPackageEntry = () => {
    if (!canAddPackageEntry) {
      return;
    }
    onAddPackage(parsedPackageCount, parsedPackageSize);
    setPackageCount("");
    setPackageSize("");
    closeAndReset();
  };

  const handleMeasurementEnter = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    addMeasurementEntry();
  };

  const handlePackageEnter = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    addPackageEntry();
  };

  const closeAndReset = () => {
    setMeasurementAmount("");
    setMeasurementUnit("");
    setPackageCount("");
    setPackageSize("");
    setApplyTareWeight(hasTareOption);
    setConvertedAmount("");
    setIsConvertedManual(false);
    setTareAmount(defaultTareAmount !== null ? String(defaultTareAmount) : "");
    setIsTareManual(false);
    setIsTareToggleManual(false);
    setUnitDropdownOpen(false);
    setUnitFiltering(false);
    onStageEntryTypeChange(null);
    onClose();
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
          <button
            type="button"
            onClick={() => onStageEntryTypeChange("measurement")}
            className={`flex-1 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
              stageEntryType === "measurement"
                ? "border-neutral-900 bg-neutral-50 text-neutral-900"
                : "border-neutral-200 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
            }`}
          >
            Measurement
          </button>
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
          {stageEntryType === "measurement" ? (
            <div className="space-y-2 rounded-xl border border-neutral-200 bg-neutral-50 p-4">
              <p className="text-sm font-semibold text-neutral-900">
                Measurement
              </p>
              <p className="text-xs text-neutral-600">
                Enter the measured amount and choose a unit. The total will be
                converted to {normalizedQuantityUnit ?? "the default unit"}.
              </p>
              <div className="grid grid-cols-[1fr_1fr] gap-2">
                <div className="relative">
                  <input
                    type="number"
                    inputMode="decimal"
                    step="0.001"
                    min="0"
                    value={measurementAmount}
                    ref={measurementAmountInputRef}
                    onChange={(event) =>
                      setMeasurementAmount(event.target.value)
                    }
                    onKeyDown={handleMeasurementEnter}
                    className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                    placeholder="Measured amount"
                  />
                </div>
                <div className="relative">
                  <input
                    ref={measurementUnitInputRef}
                    value={measurementUnit}
                    onChange={(event) => {
                      setMeasurementUnit(event.target.value);
                      setUnitFiltering(true);
                    }}
                    onFocus={(event) => {
                      setUnitDropdownOpen(true);
                      setUnitFiltering(false);
                      event.currentTarget.select();
                    }}
                    onBlur={() => {
                      setTimeout(() => {
                        setUnitDropdownOpen(false);
                        setUnitFiltering(false);
                        const normalized = measurementUnit.trim().toLowerCase();
                        if (!normalized) {
                          return;
                        }
                        const exactMatch = selectableUnits.find(
                          (unit) => unit.trim().toLowerCase() === normalized,
                        );
                        if (exactMatch) {
                          if (exactMatch !== measurementUnit) {
                            setMeasurementUnit(exactMatch);
                          }
                        } else {
                          setMeasurementUnit("");
                        }
                      }, 120);
                    }}
                    onKeyDown={handleMeasurementEnter}
                    className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
                    placeholder="Select unit"
                    aria-expanded={isUnitDropdownOpen}
                  />
                  {isUnitDropdownOpen && measurementUnitSuggestions.length ? (
                    <div className="absolute left-0 top-12 z-10 max-h-56 w-full overflow-y-auto rounded-2xl border border-neutral-200 bg-white shadow-lg">
                      {measurementUnitSuggestions.map((unit) => (
                        <button
                          key={unit}
                          type="button"
                          className="block w-full px-4 py-2 text-left text-sm text-neutral-800 hover:bg-neutral-100"
                          onMouseDown={(event) => {
                            event.preventDefault();
                            setMeasurementUnit(unit);
                            setUnitDropdownOpen(false);
                            setUnitFiltering(false);
                          }}
                        >
                          {unit}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="relative">
                <input
                  type="number"
                  inputMode="decimal"
                  step="0.000001"
                  min="0"
                  value={convertedAmount}
                  onChange={(event) => {
                    setConvertedAmount(event.target.value);
                    setIsConvertedManual(true);
                  }}
                  onKeyDown={handleMeasurementEnter}
                  className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                    normalizedQuantityUnit ? "pr-16" : ""
                  }`}
                  placeholder="Converted amount"
                />
                {normalizedQuantityUnit ? (
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                    {normalizedQuantityUnit}
                  </span>
                ) : null}
              </div>
              {hasTareOption ? (
                <label className="flex items-center gap-2 text-xs text-neutral-600">
                  <input
                    type="checkbox"
                    checked={applyTareWeight}
                    onChange={(event) => {
                      setApplyTareWeight(event.target.checked);
                      setIsTareToggleManual(true);
                    }}
                    className="h-4 w-4 rounded border-neutral-300 text-neutral-900"
                  />
                  Apply tare weight
                </label>
              ) : null}
              {tareApplied ? (
                <div className="relative">
                  <input
                    type="number"
                    inputMode="decimal"
                    step="0.0001"
                    min="0"
                    value={tareAmount}
                    onChange={(event) => {
                      setTareAmount(event.target.value);
                      setIsTareManual(true);
                    }}
                    onKeyDown={handleMeasurementEnter}
                    className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                      normalizedQuantityUnit ? "pr-16" : ""
                    }`}
                    placeholder="Tare weight"
                  />
                  {normalizedQuantityUnit ? (
                    <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                      {normalizedQuantityUnit}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {conversionFactor === null ? (
                <p className="text-xs text-rose-600">
                  Select a unit connected to{" "}
                  {normalizedQuantityUnit ?? "the default unit"}.
                </p>
              ) : !convertedValid && convertedAmount.trim().length > 0 ? (
                <p className="text-xs text-rose-600">
                  Enter a non-negative converted amount.
                </p>
              ) : !tareValid && tareApplied ? (
                <p className="text-xs text-rose-600">
                  Enter a non-negative tare amount.
                </p>
              ) : tareTooLarge ? (
                <p className="text-xs text-rose-600">
                  Converted amount must be greater than tare weight.
                </p>
              ) : measurementValid && convertedValid && tareApplied ? (
                <p className="text-xs text-neutral-500">
                  Net after tare:{" "}
                  {formatAmountWithUnit(netAmount ?? 0, normalizedQuantityUnit)}
                </p>
              ) : (
                <p className="text-xs text-neutral-500">
                  Enter a measurement to preview the conversion.
                </p>
              )}
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={addMeasurementEntry}
                  disabled={!canAddMeasurementEntry}
                  className={`rounded-full px-4 py-2 text-sm font-semibold text-white transition ${
                    canAddMeasurementEntry
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
                    onKeyDown={handlePackageEnter}
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
                    onKeyDown={handlePackageEnter}
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
                  This entry adds{" "}
                  {formatAmountWithUnit(
                    packageEntryTotal,
                    normalizedQuantityUnit,
                  )}{" "}
                  to the total.
                </p>
              )}
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={addPackageEntry}
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

function roundToSix(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}
