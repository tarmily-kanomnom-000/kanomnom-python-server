"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMeasuredElementHeight } from "@/hooks/use-measured-element-height";
import {
  submitInventoryAdjustment,
  submitInventoryCorrection,
} from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  InventoryAdjustmentRequestPayload,
  InventoryCorrectionRequestPayload,
  InventoryLossReason,
} from "@/lib/grocy/types";
import {
  buildSearchableOptions,
  computeDefaultBestBeforeDate,
} from "./form-utils";
import { resolveQuantityUnit } from "./helpers";
import { SearchableOptionSelect } from "./searchable-option-select";

type LossOption = {
  value: InventoryLossReason;
  label: string;
};

type InventoryStagedEntry =
  | {
      id: string;
      kind: "tare";
      submissionAmount: number;
      grossAmount: number;
      netAmount: number;
    }
  | {
      id: string;
      kind: "package";
      submissionAmount: number;
      quantity: number;
      packageSize: number;
    }
  | {
      id: string;
      kind: "manual";
      submissionAmount: number;
    };

const STAGING_TTL_MS = 24 * 60 * 60 * 1000;

const sanitizeStagedEntries = (
  rawEntries: unknown,
  allowTare: boolean,
  allowManualForTare: boolean,
): InventoryStagedEntry[] => {
  if (!Array.isArray(rawEntries)) {
    return [];
  }
  const isFiniteNumber = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value);
  return rawEntries
    .map((entry) => {
      if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
        return null;
      }
      const record = entry as Record<string, unknown>;
      const idValue = record.id;
      if (typeof idValue !== "string" || !idValue.trim().length) {
        return null;
      }
      const kind = record.kind;
      if (kind === "tare") {
        if (!allowTare) {
          return null;
        }
        const grossAmount = record.grossAmount;
        const netAmount = record.netAmount;
        const submissionAmount = record.submissionAmount;
        if (
          isFiniteNumber(grossAmount) &&
          isFiniteNumber(netAmount) &&
          isFiniteNumber(submissionAmount)
        ) {
          return {
            id: idValue,
            kind: "tare",
            grossAmount,
            netAmount,
            submissionAmount,
          };
        }
        return null;
      }
      if (kind === "package") {
        const quantity = record.quantity;
        const packageSize = record.packageSize;
        if (isFiniteNumber(quantity) && isFiniteNumber(packageSize)) {
          const submissionAmount = quantity * packageSize;
          return {
            id: idValue,
            kind: "package",
            quantity,
            packageSize,
            submissionAmount,
          };
        }
        return null;
      }
      if (kind === "manual") {
        if (allowTare && !allowManualForTare) {
          return null;
        }
        const submissionAmount = record.submissionAmount;
        if (isFiniteNumber(submissionAmount) && submissionAmount >= 0) {
          return {
            id: idValue,
            kind: "manual",
            submissionAmount,
          };
        }
      }
      return null;
    })
    .filter((entry): entry is InventoryStagedEntry => entry !== null);
};

type InventoryCorrectionFormProps = {
  product: GrocyProductInventoryEntry;
  instanceIndex: string | null;
  locationNamesById: Record<number, string>;
  lossReasonOptions: LossOption[];
  onClose: () => void;
  onProductChange: (product: GrocyProductInventoryEntry) => void;
  onSuccess: (message: string) => void;
};

export function InventoryCorrectionForm({
  product,
  instanceIndex,
  locationNamesById,
  lossReasonOptions,
  onClose,
  onProductChange,
  onSuccess,
  formId = "inventory-correction-form",
}: InventoryCorrectionFormProps & { formId?: string }) {
  const quantityUnit = resolveQuantityUnit(product);
  const amountInputRef = useRef<HTMLInputElement | null>(null);
  const [entryMode, setEntryMode] = useState<"direct" | "staged">("staged");
  const [newAmount, setNewAmount] = useState("");
  const stagedWeighedInputRef = useRef<HTMLInputElement | null>(null);
  const packageCountInputRef = useRef<HTMLInputElement | null>(null);
  const manualAmountInputRef = useRef<HTMLInputElement | null>(null);
  const [weighedAmount, setWeighedAmount] = useState("");
  const [packageCount, setPackageCount] = useState("");
  const [packageSize, setPackageSize] = useState("");
  const [manualAmount, setManualAmount] = useState("");
  const [stagedEntries, setStagedEntries] = useState<InventoryStagedEntry[]>(
    [],
  );
  const [defaultBestBefore, setDefaultBestBefore] = useState<string>(() =>
    computeDefaultBestBeforeDate(product.default_best_before_days),
  );
  const [bestBeforeDate, setBestBeforeDate] = useState(defaultBestBefore);
  const [defaultLocationId, setDefaultLocationId] = useState<number | null>(
    product.location_id ?? null,
  );
  const defaultLocationName =
    (defaultLocationId && locationNamesById[defaultLocationId]) || "";
  const [locationId, setLocationId] = useState<number | null>(
    defaultLocationId,
  );
  const [locationError, setLocationError] = useState(false);
  const [note, setNote] = useState("");
  const [losses, setLosses] = useState<
    { reason: InventoryLossReason; note: string }[]
  >([]);
  const [isStageModalOpen, setStageModalOpen] = useState(false);
  const [stageEntryType, setStageEntryType] = useState<
    "tare" | "package" | "manual" | null
  >(null);
  const [leftColumnRef, leftColumnHeight] =
    useMeasuredElementHeight<HTMLDivElement>();
  const hasTareWeight =
    Number.isFinite(product.tare_weight) && product.tare_weight > 0;
  const tareWeight = hasTareWeight ? product.tare_weight : 0;
  const stagingKey =
    instanceIndex !== null
      ? `inventory-staging:${instanceIndex}:${product.id}`
      : null;
  const [stagedInterpretation, setStagedInterpretation] = useState<
    "absolute" | "delta"
  >("absolute");
  const [deltaDirection, setDeltaDirection] = useState<"add" | "subtract">(
    "add",
  );

  useEffect(() => {
    amountInputRef.current?.focus();
  }, []);

  const isLossReasonSelected = (reason: InventoryLossReason): boolean =>
    losses.some((entry) => entry.reason === reason);

  const handleLossReasonToggle = (reason: InventoryLossReason): void => {
    setLosses((current) => {
      const exists = current.find((entry) => entry.reason === reason);
      if (exists) {
        return current.filter((entry) => entry.reason !== reason);
      }
      return [...current, { reason, note: "" }];
    });
  };

  const handleLossReasonNoteChange = (
    reason: InventoryLossReason,
    value: string,
  ): void => {
    setLosses((current) =>
      current.map((entry) =>
        entry.reason === reason ? { ...entry, note: value } : entry,
      ),
    );
  };

  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const todayFloor = useMemo(() => {
    const reference = new Date();
    reference.setHours(0, 0, 0, 0);
    return reference;
  }, []);

  const locationOptions = useMemo(
    () => buildSearchableOptions(locationNamesById),
    [locationNamesById],
  );

  useEffect(() => {
    const nextDefaultBestBefore = computeDefaultBestBeforeDate(
      product.default_best_before_days,
    );
    const nextDefaultLocationId = product.location_id ?? null;

    setDefaultBestBefore(nextDefaultBestBefore);
    setWeighedAmount("");
    setPackageCount("");
    setPackageSize("");
    setManualAmount("");
    setStagedEntries([]);
    setBestBeforeDate(nextDefaultBestBefore);
    setLocationId(nextDefaultLocationId);
    setDefaultLocationId(nextDefaultLocationId);
    setNote("");
    setLosses([]);
    setLocationError(false);
    setStatusMessage(null);
    setStageModalOpen(false);
    setStageEntryType(null);
    setStagedInterpretation("absolute");
    setDeltaDirection("add");
  }, [product]);

  const resetBestBeforeToDefault = () => {
    setBestBeforeDate(defaultBestBefore);
  };

  useEffect(() => {
    stagedWeighedInputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!isStageModalOpen) {
      return;
    }
    if (stageEntryType === "tare") {
      stagedWeighedInputRef.current?.focus();
    } else if (stageEntryType === "package") {
      packageCountInputRef.current?.focus();
    } else if (stageEntryType === "manual") {
      manualAmountInputRef.current?.focus();
    }
  }, [isStageModalOpen, stageEntryType]);

  useEffect(() => {
    if (
      hasTareWeight &&
      stagedInterpretation === "absolute" &&
      stageEntryType === "manual"
    ) {
      setStageEntryType("tare");
    }
  }, [hasTareWeight, stagedInterpretation, stageEntryType]);

  useEffect(() => {
    if (!stagingKey || typeof window === "undefined") {
      return;
    }
    const raw = window.localStorage.getItem(stagingKey);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as {
        entries?: unknown;
        updatedAt?: number;
        interpretation?: "absolute" | "delta";
        direction?: "add" | "subtract";
      };
      const updatedAt =
        typeof parsed.updatedAt === "number" &&
        Number.isFinite(parsed.updatedAt)
          ? parsed.updatedAt
          : 0;
      if (!updatedAt || Date.now() - updatedAt > STAGING_TTL_MS) {
        window.localStorage.removeItem(stagingKey);
        return;
      }
      const hydrated = sanitizeStagedEntries(
        parsed.entries,
        hasTareWeight,
        parsed.interpretation === "delta",
      );
      if (!hydrated.length) {
        window.localStorage.removeItem(stagingKey);
        return;
      }
      setStagedEntries(hydrated);
      setEntryMode("staged");
      if (
        parsed.interpretation === "delta" ||
        parsed.interpretation === "absolute"
      ) {
        setStagedInterpretation(parsed.interpretation);
      }
      if (parsed.direction === "add" || parsed.direction === "subtract") {
        setDeltaDirection(parsed.direction);
      }
    } catch {
      window.localStorage.removeItem(stagingKey);
    }
  }, [stagingKey, hasTareWeight]);

  useEffect(() => {
    if (!stagingKey || typeof window === "undefined") {
      return;
    }
    if (stagedEntries.length === 0) {
      window.localStorage.removeItem(stagingKey);
      return;
    }
    try {
      window.localStorage.setItem(
        stagingKey,
        JSON.stringify({
          updatedAt: Date.now(),
          entries: stagedEntries,
          interpretation: stagedInterpretation,
          direction: deltaDirection,
        }),
      );
    } catch {
      // Ignore write errors (e.g., storage quota).
    }
  }, [stagedEntries, stagingKey, stagedInterpretation, deltaDirection]);

  const formatAmountWithUnit = (value: number): string => {
    if (!Number.isFinite(value)) {
      return "—";
    }
    const rounded = Math.round(value * 100) / 100;
    const amountLabel = rounded.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    });
    return quantityUnit ? `${amountLabel} ${quantityUnit}` : amountLabel;
  };

  const parsedWeighedAmount = Number(weighedAmount);
  const parsedPackageCount = Number(packageCount);
  const parsedPackageSize = Number(packageSize);
  const parsedManualAmount = Number(manualAmount);
  const packageEntryTotal =
    Number.isFinite(parsedPackageCount) && Number.isFinite(parsedPackageSize)
      ? parsedPackageCount * parsedPackageSize
      : 0;
  const canAddManualEntry =
    manualAmount.trim().length > 0 &&
    Number.isFinite(parsedManualAmount) &&
    parsedManualAmount >= 0 &&
    !isSubmitting;
  const hasAmountValue = stagedEntries.length > 0;
  const hasDirectAmountValue = newAmount.trim().length > 0;
  const isDirectAmountValid = true;
  const isWeighedAmountValid =
    weighedAmount.trim().length > 0 &&
    Number.isFinite(parsedWeighedAmount) &&
    parsedWeighedAmount >= 0;
  const isWeighedBelowTare =
    hasTareWeight && isWeighedAmountValid && parsedWeighedAmount < tareWeight;
  const isBelowTare = false;
  const canAddWeighedEntry =
    isWeighedAmountValid && !isWeighedBelowTare && !isSubmitting;
  const canAddPackageEntry =
    packageCount.trim().length > 0 &&
    packageSize.trim().length > 0 &&
    Number.isFinite(parsedPackageCount) &&
    Number.isFinite(parsedPackageSize) &&
    parsedPackageCount > 0 &&
    parsedPackageSize > 0 &&
    !isSubmitting;
  const stagedTotal = stagedEntries.reduce(
    (total, entry) => total + entry.submissionAmount,
    0,
  );
  const adjustmentSign = deltaDirection === "add" ? 1 : -1;
  const submissionBaseAmount = stagedEntries.length > 0 ? stagedTotal : 0;
  const isAmountValid =
    stagedEntries.length > 0 && Number.isFinite(stagedTotal);
  const netAmount =
    stagedInterpretation === "absolute" && hasTareWeight
      ? Math.max(stagedTotal - tareWeight, 0)
      : null;
  const stagedNetPreview =
    hasTareWeight && stagedEntries.some((entry) => entry.kind === "tare")
      ? Math.max(
          stagedEntries.reduce((total, entry) => {
            if (entry.kind === "tare") {
              return total + entry.netAmount;
            }
            return total + entry.submissionAmount;
          }, 0),
          0,
        )
      : null;
  const isBestBeforeValid =
    !bestBeforeDate || !Number.isNaN(Date.parse(bestBeforeDate));
  const bestBeforeIsPast =
    Boolean(bestBeforeDate) &&
    new Date(bestBeforeDate).getTime() < todayFloor.getTime();
  const resolvedNewAmount =
    stagedInterpretation === "absolute"
      ? submissionBaseAmount
      : submissionBaseAmount * adjustmentSign;
  const submissionPreview =
    hasAmountValue && isAmountValid
      ? stagedInterpretation === "delta"
        ? `${deltaDirection === "add" ? "+" : "-"}${formatAmountWithUnit(Math.abs(submissionBaseAmount))}`
        : formatAmountWithUnit(submissionBaseAmount)
      : "—";
  const isFormValid =
    hasAmountValue &&
    isAmountValid &&
    !isBelowTare &&
    isBestBeforeValid &&
    !bestBeforeIsPast &&
    !locationError &&
    Boolean(instanceIndex) &&
    !isSubmitting;

  const handleAddWeighedEntry = (): void => {
    if (!canAddWeighedEntry) {
      return;
    }
    const netWeighedAmount = Math.max(parsedWeighedAmount - tareWeight, 0);
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `tare-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStagedEntries((current) => [
      ...current,
      {
        id,
        kind: "tare",
        submissionAmount: netWeighedAmount,
        grossAmount: parsedWeighedAmount,
        netAmount: netWeighedAmount,
      },
    ]);
    setWeighedAmount("");
    setStageModalOpen(false);
    setStageEntryType(null);
  };

  const handleAddManualEntry = (): void => {
    if (!canAddManualEntry) {
      return;
    }
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStagedEntries((current) => [
      ...current,
      {
        id,
        kind: "manual",
        submissionAmount: parsedManualAmount,
      },
    ]);
    setManualAmount("");
    setStageModalOpen(false);
    setStageEntryType(null);
  };

  const handleAddPackageEntry = (): void => {
    if (!canAddPackageEntry) {
      return;
    }
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `package-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setStagedEntries((current) => [
      ...current,
      {
        id,
        kind: "package",
        submissionAmount: packageEntryTotal,
        quantity: parsedPackageCount,
        packageSize: parsedPackageSize,
      },
    ]);
    setPackageCount("");
    setPackageSize("");
    setStageModalOpen(false);
    setStageEntryType(null);
  };

  const handleRemoveStagedEntry = (entryId: string): void => {
    setStagedEntries((current) =>
      current.filter((entry) => entry.id !== entryId),
    );
  };

  const openStageModal = (): void => {
    const nextDefault =
      stagedInterpretation === "delta"
        ? "manual"
        : hasTareWeight
          ? "tare"
          : "manual";
    setStageEntryType(nextDefault);
    setWeighedAmount("");
    setPackageCount("");
    setPackageSize("");
    setManualAmount("");
    setStageModalOpen(true);
  };

  const handleSubmit = async (
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    if (!instanceIndex || !isFormValid) {
      return;
    }
    setSubmitting(true);
    setStatusMessage(null);
    try {
      const normalizedLosses =
        losses.length > 0
          ? losses.map((entry) => ({
              reason: entry.reason,
              note: entry.note.trim().length ? entry.note.trim() : null,
            }))
          : [];
      const payload = {
        ...(stagedInterpretation === "absolute"
          ? { newAmount: resolvedNewAmount }
          : { deltaAmount: resolvedNewAmount }),
        bestBeforeDate: bestBeforeDate || null,
        locationId,
        note: note.trim().length ? note.trim() : null,
        metadata: normalizedLosses.length ? { losses: normalizedLosses } : null,
      };
      const updatedProduct =
        stagedInterpretation === "absolute"
          ? await submitInventoryCorrection(
              instanceIndex,
              product.id,
              payload as InventoryCorrectionRequestPayload,
            )
          : await submitInventoryAdjustment(
              instanceIndex,
              product.id,
              payload as unknown as InventoryAdjustmentRequestPayload,
            );
      onProductChange(updatedProduct);
      onSuccess("Inventory correction submitted.");
      onClose();
      setNewAmount("");
      setWeighedAmount("");
      setPackageCount("");
      setPackageSize("");
      setStagedEntries([]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Failed to submit inventory correction.";
      setStatusMessage({ type: "error", text: message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      id={formId}
      className="mt-5 space-y-5 text-sm"
      onSubmit={handleSubmit}
    >
      {instanceIndex ? null : (
        <p className="rounded-2xl bg-amber-50 px-4 py-3 text-amber-800">
          Select an instance before submitting inventory corrections.
        </p>
      )}
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5" ref={leftColumnRef}>
          <div className="space-y-3 rounded-2xl border border-neutral-100 bg-neutral-50 p-4">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Amount entry
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => setStagedInterpretation("absolute")}
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${
                    stagedInterpretation === "absolute"
                      ? "bg-neutral-900 text-white shadow"
                      : "border border-neutral-300 text-neutral-700 hover:border-neutral-900 hover:text-neutral-900"
                  }`}
                >
                  Set new total
                </button>
                <div className="flex items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-semibold text-neutral-700">
                  <button
                    type="button"
                    onClick={() => {
                      setStagedInterpretation("delta");
                      setDeltaDirection("add");
                    }}
                    className={`rounded-full px-2 py-1 ${
                      stagedInterpretation === "delta" &&
                      deltaDirection === "add"
                        ? "bg-neutral-900 text-white"
                        : "hover:text-neutral-900"
                    }`}
                  >
                    + Add
                  </button>
                  <span className="text-neutral-300">|</span>
                  <button
                    type="button"
                    onClick={() => {
                      setStagedInterpretation("delta");
                      setDeltaDirection("subtract");
                    }}
                    className={`rounded-full px-2 py-1 ${
                      stagedInterpretation === "delta" &&
                      deltaDirection === "subtract"
                        ? "bg-neutral-900 text-white"
                        : "hover:text-neutral-900"
                    }`}
                  >
                    - Remove
                  </button>
                </div>
              </div>
            </div>
            {entryMode === "direct" ? (
              <div className="space-y-2">
                <div className="relative">
                  <input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min="0"
                    value={newAmount}
                    ref={amountInputRef}
                    onChange={(event) => setNewAmount(event.target.value)}
                    className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                      quantityUnit ? "pr-16" : ""
                    }`}
                    placeholder="Enter the corrected amount"
                    required={entryMode === "direct"}
                  />
                  {quantityUnit ? (
                    <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                      {quantityUnit}
                    </span>
                  ) : null}
                </div>
                {!hasDirectAmountValue ? (
                  <p className="text-xs text-neutral-500">
                    Provide the exact total that should be on hand for this
                    product{quantityUnit ? ` (in ${quantityUnit})` : ""}.
                  </p>
                ) : !isDirectAmountValid ? (
                  <p className="text-xs text-rose-600">
                    Enter a non-negative number.
                  </p>
                ) : isBelowTare ? (
                  <p className="text-xs text-rose-600">
                    Amount must be at least the tare weight ({tareWeight}
                    {quantityUnit ? ` ${quantityUnit}` : ""}).
                  </p>
                ) : null}
                {hasTareWeight ? (
                  <div className="space-y-1 text-xs text-neutral-500">
                    <p>
                      Tare weight: {tareWeight}. Net stock recorded will be{" "}
                      {netAmount !== null ? netAmount.toFixed(2) : "—"}.
                    </p>
                    <p>
                      Weigh the filled container and enter the total weight
                      here. The tare weight above is subtracted automatically,
                      so no manual math is required.
                    </p>
                  </div>
                ) : null}
              </div>
            ) : (
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
                      {formatAmountWithUnit(stagedTotal)}
                    </p>
                  </div>
                  {stagedEntries.length ? (
                    <div className="space-y-2">
                      {stagedEntries.map((entry) => (
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
                                ? `Gross ${formatAmountWithUnit(entry.grossAmount)}${
                                    hasTareWeight
                                      ? ` • Net ${formatAmountWithUnit(entry.netAmount)}`
                                      : ""
                                  }`
                                : entry.kind === "package"
                                  ? `${entry.quantity.toLocaleString()} × ${formatAmountWithUnit(entry.packageSize)} = ${formatAmountWithUnit(entry.submissionAmount)}`
                                  : `Amount: ${formatAmountWithUnit(entry.submissionAmount)}`}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveStagedEntry(entry.id)}
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
                      {hasTareWeight ? " with tare weight" : ""} and unopened
                      package counts. The total below is what will be sent to
                      Grocy.
                    </p>
                  )}
                  <div className="mt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={openStageModal}
                      className="rounded-full border border-neutral-200 px-3 py-1 text-[11px] font-semibold text-neutral-700 transition hover:border-neutral-900 hover:text-neutral-900"
                    >
                      Add to stage
                    </button>
                  </div>
                  {stagedNetPreview !== null ? (
                    <p className="text-[11px] text-neutral-500">
                      Net after tare for weighed entries:{" "}
                      {formatAmountWithUnit(stagedNetPreview)}.
                    </p>
                  ) : null}
                </div>
              </div>
            )}
            <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 text-sm">
              <div>
                <p className="font-semibold text-neutral-900">
                  {stagedInterpretation === "delta"
                    ? "Adjustment to submit"
                    : "Final amount to submit"}
                </p>
                <p className="text-xs text-neutral-500">
                  {stagedInterpretation === "delta"
                    ? "Applies this change to the current stock on submit."
                    : "Sum of all staged entries."}
                </p>
              </div>
              <span className="text-base font-semibold text-neutral-900">
                {submissionPreview}
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Best before date
              </label>
              <button
                type="button"
                onClick={resetBestBeforeToDefault}
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
            {bestBeforeIsPast ? (
              <p className="text-xs text-rose-600">
                Best-before date cannot be in the past.
              </p>
            ) : null}
          </div>
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
        <div
          className="md:h-full space-y-3"
          style={
            leftColumnHeight
              ? { maxHeight: leftColumnHeight, height: leftColumnHeight }
              : undefined
          }
        >
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Note
            </label>
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              className="w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none"
              placeholder="Optional context for this correction"
            />
          </div>
          <div className="rounded-2xl border border-neutral-100 bg-neutral-50">
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between px-4 py-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Loss tracking
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Select reasons that contributed to this adjustment.
                  </p>
                </div>
                <span className="text-neutral-500 transition group-open:rotate-180">
                  ▼
                </span>
              </summary>
              <div className="space-y-3 px-4 pb-4">
                {lossReasonOptions.map((option) => {
                  const selected = isLossReasonSelected(option.value);
                  const currentEntry = losses.find(
                    (entry) => entry.reason === option.value,
                  );
                  return (
                    <div
                      key={option.value}
                      className="rounded-2xl border border-neutral-100 bg-white p-3"
                    >
                      <label className="flex items-center gap-2 text-sm text-neutral-800">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => handleLossReasonToggle(option.value)}
                        />
                        {option.label}
                      </label>
                      {selected ? (
                        <div className="mt-2">
                          <textarea
                            value={currentEntry?.note ?? ""}
                            onChange={(event) =>
                              handleLossReasonNoteChange(
                                option.value,
                                event.target.value,
                              )
                            }
                            rows={2}
                            className="w-full resize-none rounded-2xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 focus:border-neutral-900 focus:outline-none"
                            placeholder="Notes about this loss (optional)"
                          />
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </details>
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
      {isStageModalOpen ? (
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
                onClick={() => setStageModalOpen(false)}
                className="rounded-full border border-neutral-200 p-2 text-neutral-500 transition hover:border-neutral-900 hover:text-neutral-900"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 flex gap-2">
              {!hasTareWeight || stagedInterpretation === "delta" ? (
                <button
                  type="button"
                  onClick={() => setStageEntryType("manual")}
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
                  onClick={() => setStageEntryType("tare")}
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
                onClick={() => setStageEntryType("package")}
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
                      onClick={handleAddManualEntry}
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
                    Weigh the container holding opened product and enter the
                    gross weight (container + contents).
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
                      Net after tare:{" "}
                      {formatAmountWithUnit(
                        Math.max(parsedWeighedAmount - tareWeight, 0),
                      )}
                      .
                    </p>
                  ) : null}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleAddWeighedEntry}
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
                        onChange={(event) =>
                          setPackageCount(event.target.value)
                        }
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
                      This entry adds {formatAmountWithUnit(packageEntryTotal)}{" "}
                      to the total.
                    </p>
                  )}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={handleAddPackageEntry}
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
      ) : null}
    </form>
  );
}
