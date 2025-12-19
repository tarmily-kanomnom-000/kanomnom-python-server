"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { submitInventoryCorrection } from "@/lib/grocy/client";
import type {
  GrocyProductInventoryEntry,
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
}: InventoryCorrectionFormProps) {
  const quantityUnit = resolveQuantityUnit(product);
  const [newAmount, setNewAmount] = useState("");
  const defaultBestBefore = useMemo(
    () => computeDefaultBestBeforeDate(product.default_best_before_days),
    [product.default_best_before_days],
  );
  const [bestBeforeDate, setBestBeforeDate] = useState(defaultBestBefore);
  const defaultLocationId = product.location_id ?? null;
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
  const leftColumnRef = useRef<HTMLDivElement | null>(null);
  const [leftColumnHeight, setLeftColumnHeight] = useState<number | null>(null);

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
      return () => {
        observer.disconnect();
      };
    }
    window.addEventListener("resize", updateHeight);
    return () => {
      window.removeEventListener("resize", updateHeight);
    };
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

  const resetBestBeforeToDefault = () => {
    setBestBeforeDate(defaultBestBefore);
  };

  const parsedAmount = Number(newAmount);
  const hasAmountValue = newAmount.trim().length > 0;
  const hasTareWeight =
    Number.isFinite(product.tare_weight) && product.tare_weight > 0;
  const tareWeight = hasTareWeight ? product.tare_weight : 0;
  const isAmountValid =
    hasAmountValue && Number.isFinite(parsedAmount) && parsedAmount >= 0;
  const isBelowTare =
    hasTareWeight && isAmountValid && parsedAmount < tareWeight;
  const netAmount =
    hasAmountValue && Number.isFinite(parsedAmount)
      ? Math.max(parsedAmount - tareWeight, 0)
      : null;
  const isBestBeforeValid =
    !bestBeforeDate || !Number.isNaN(Date.parse(bestBeforeDate));
  const bestBeforeIsPast =
    Boolean(bestBeforeDate) &&
    new Date(bestBeforeDate).getTime() < todayFloor.getTime();
  const isFormValid =
    hasAmountValue &&
    isAmountValid &&
    !isBelowTare &&
    isBestBeforeValid &&
    !bestBeforeIsPast &&
    !locationError &&
    Boolean(instanceIndex) &&
    !isSubmitting;

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
        newAmount: parsedAmount,
        bestBeforeDate: bestBeforeDate || null,
        locationId,
        note: note.trim().length ? note.trim() : null,
        metadata: normalizedLosses.length ? { losses: normalizedLosses } : null,
      };
      const updatedProduct = await submitInventoryCorrection(
        instanceIndex,
        product.id,
        payload,
      );
      onProductChange(updatedProduct);
      onSuccess("Inventory correction submitted.");
      onClose();
      setNewAmount("");
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
    <form className="mt-5 space-y-5 text-sm" onSubmit={handleSubmit}>
      {instanceIndex ? null : (
        <p className="rounded-2xl bg-amber-50 px-4 py-3 text-amber-800">
          Select an instance before submitting inventory corrections.
        </p>
      )}
      <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5" ref={leftColumnRef}>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              New total amount<span className="text-rose-600">*</span>
            </label>
            <div className="relative">
              <input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={newAmount}
                onChange={(event) => setNewAmount(event.target.value)}
                className={`w-full rounded-2xl border border-neutral-200 px-4 py-2 text-base text-neutral-900 focus:border-neutral-900 focus:outline-none ${
                  quantityUnit ? "pr-16" : ""
                }`}
                placeholder="Enter the corrected amount"
                required
              />
              {quantityUnit ? (
                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm font-semibold text-neutral-500">
                  {quantityUnit}
                </span>
              ) : null}
            </div>
            {!hasAmountValue ? (
              <p className="text-xs text-neutral-500">
                Provide the exact total that should be on hand for this product
                {quantityUnit ? ` (in ${quantityUnit})` : ""}.
              </p>
            ) : !isAmountValid ? (
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
                  Weigh the filled container and enter the total weight here.
                  The tare weight above is subtracted automatically, so no
                  manual math is required.
                </p>
              </div>
            ) : null}
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
                Loss tracking
              </p>
              <p className="mt-1 text-xs text-neutral-500">
                Select every reason that contributed to this adjustment. Add a
                short note per reason to capture context.
              </p>
            </div>
            <div className="mt-3 flex-1 space-y-3 overflow-y-auto pr-2">
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
          {isSubmitting ? "Submitting…" : "Submit correction"}
        </button>
      </div>
    </form>
  );
}
