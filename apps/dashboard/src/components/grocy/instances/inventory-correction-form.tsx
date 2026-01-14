"use client";

import { useEffect, useMemo, useState } from "react";
import { useMeasuredElementHeight } from "@/hooks/use-measured-element-height";
import {
  submitInventoryAdjustment,
  submitInventoryCorrection,
} from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
  InventoryAdjustmentRequestPayload,
  InventoryCorrectionRequestPayload,
} from "@/lib/grocy/types";
import {
  buildSearchableOptions,
  computeDefaultBestBeforeDate,
} from "./form-utils";
import { resolveQuantityUnit } from "./helpers";
import { SearchableOptionSelect } from "./searchable-option-select";
import { InventoryStageModal } from "./shared/inventory-stage-modal";
import {
  type LossEntry,
  type LossOption,
  LossTrackingSection,
} from "./shared/loss-tracking-section";
import { StagedEntriesList } from "./shared/staged-entries-list";
import { useInventoryStaging } from "./shared/use-inventory-staging";

type InventoryCorrectionFormProps = {
  product: GrocyProductInventoryEntry;
  instanceIndex: string | null;
  locationNamesById: Record<number, string>;
  lossReasonOptions: LossOption[];
  onClose: () => void;
  onProductChange: (product: GrocyProductInventoryEntry) => void;
  onSuccess: (message: string) => void;
  formId?: string;
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
}: InventoryCorrectionFormProps) {
  const quantityUnit = resolveQuantityUnit(product);
  const {
    stagedEntries,
    stagedInterpretation,
    deltaDirection,
    stagedTotal,
    stagedNetPreview,
    submissionBaseAmount,
    resolvedNewAmount,
    hasAmountValue,
    isAmountValid,
    setStagedInterpretation,
    setDeltaDirection,
    addTareEntry,
    addManualEntry,
    addPackageEntry,
    addConversionEntry,
    removeStagedEntry,
    clearStagedEntries,
    hasTareWeight,
    tareWeight,
  } = useInventoryStaging({ product, instanceIndex });

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
  const [losses, setLosses] = useState<LossEntry[]>([]);
  const [isStageModalOpen, setStageModalOpen] = useState(false);
  const [stageEntryType, setStageEntryType] = useState<
    "tare" | "package" | "manual" | "conversion" | null
  >(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [isSubmitting, setSubmitting] = useState(false);
  const [leftColumnRef, leftColumnHeight] =
    useMeasuredElementHeight<HTMLDivElement>();

  const todayFloor = useMemo(() => {
    const reference = new Date();
    reference.setHours(0, 0, 0, 0);
    return reference;
  }, []);

  const locationOptions = useMemo(
    () => buildSearchableOptions(locationNamesById),
    [locationNamesById],
  );

  const unitConversions = useMemo(
    () => product.description_metadata?.unit_conversions ?? [],
    [product.description_metadata],
  );

  useEffect(() => {
    const nextDefaultBestBefore = computeDefaultBestBeforeDate(
      product.default_best_before_days,
    );
    const nextDefaultLocationId = product.location_id ?? null;

    setDefaultBestBefore(nextDefaultBestBefore);
    setBestBeforeDate(nextDefaultBestBefore);
    setLocationId(nextDefaultLocationId);
    setDefaultLocationId(nextDefaultLocationId);
    setNote("");
    setLosses([]);
    setLocationError(false);
    setStatusMessage(null);
    setStageModalOpen(false);
    setStageEntryType(null);
  }, [product]);

  const resetBestBeforeToDefault = () => {
    setBestBeforeDate(defaultBestBefore);
  };

  const isBestBeforeValid =
    !bestBeforeDate || !Number.isNaN(Date.parse(bestBeforeDate));
  const bestBeforeIsPast =
    Boolean(bestBeforeDate) &&
    new Date(bestBeforeDate).getTime() < todayFloor.getTime();

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

  const submissionPreview =
    hasAmountValue && isAmountValid
      ? stagedInterpretation === "delta"
        ? `${deltaDirection === "add" ? "+" : "-"}${formatAmountWithUnit(Math.abs(submissionBaseAmount))}`
        : formatAmountWithUnit(submissionBaseAmount)
      : "—";

  const isFormValid =
    hasAmountValue &&
    isAmountValid &&
    isBestBeforeValid &&
    !bestBeforeIsPast &&
    !locationError &&
    Boolean(instanceIndex) &&
    !isSubmitting;

  const openStageModal = (): void => {
    const nextDefault =
      stagedInterpretation === "delta"
        ? "manual"
        : hasTareWeight
          ? "tare"
          : "manual";
    setStageEntryType(nextDefault);
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
      const newAmountPayload =
        hasTareWeight && stagedInterpretation === "absolute"
          ? resolvedNewAmount + tareWeight
          : resolvedNewAmount;
      const payload = {
        ...(stagedInterpretation === "absolute"
          ? { newAmount: newAmountPayload }
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
      clearStagedEntries();
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
            <StagedEntriesList
              entries={stagedEntries}
              hasTareWeight={hasTareWeight}
              quantityUnit={quantityUnit}
              stagedTotal={stagedTotal}
              stagedNetPreview={stagedNetPreview}
              onRemove={removeStagedEntry}
              onAddClick={openStageModal}
            />
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
          <LossTrackingSection
            options={lossReasonOptions}
            losses={losses}
            onChange={setLosses}
          />
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
      <InventoryStageModal
        isOpen={isStageModalOpen}
        onClose={() => setStageModalOpen(false)}
        stageEntryType={stageEntryType}
        onStageEntryTypeChange={setStageEntryType}
        hasTareWeight={hasTareWeight}
        tareWeight={tareWeight}
        quantityUnit={quantityUnit}
        stagedInterpretation={stagedInterpretation}
        onAddManual={addManualEntry}
        onAddTare={addTareEntry}
        onAddPackage={addPackageEntry}
        onAddConversion={addConversionEntry}
        unitConversions={unitConversions}
      />
    </form>
  );
}
