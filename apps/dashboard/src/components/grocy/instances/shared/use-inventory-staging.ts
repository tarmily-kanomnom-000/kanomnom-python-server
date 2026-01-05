import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  buildStorageKey,
  clearStoredPayload,
  readStoredPayload,
  writeStoredPayload,
} from "@/lib/offline/local-storage";

export type InventoryStagedEntry =
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

export type StagedInterpretation = "absolute" | "delta";
export type DeltaDirection = "add" | "subtract";

const STAGING_TTL_MS = 24 * 60 * 60 * 1000;

type StagingState = {
  stagedEntries: InventoryStagedEntry[];
  stagedInterpretation: StagedInterpretation;
  deltaDirection: DeltaDirection;
};

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

type UseInventoryStagingParams = {
  product: GrocyProductInventoryEntry;
  instanceIndex: string | null;
};

type UseInventoryStagingResult = {
  stagedEntries: InventoryStagedEntry[];
  stagedInterpretation: StagedInterpretation;
  deltaDirection: DeltaDirection;
  stagedTotal: number;
  stagedNetPreview: number | null;
  submissionBaseAmount: number;
  resolvedNewAmount: number;
  hasAmountValue: boolean;
  isAmountValid: boolean;
  setStagedInterpretation: (next: StagedInterpretation) => void;
  setDeltaDirection: (next: DeltaDirection) => void;
  addTareEntry: (grossAmount: number) => void;
  addManualEntry: (amount: number) => void;
  addPackageEntry: (quantity: number, packageSize: number) => void;
  removeStagedEntry: (id: string) => void;
  clearStagedEntries: () => void;
  resetStaging: () => void;
  hasTareWeight: boolean;
  tareWeight: number;
};

export function useInventoryStaging({
  product,
  instanceIndex,
}: UseInventoryStagingParams): UseInventoryStagingResult {
  const hasTareWeight =
    Number.isFinite(product.tare_weight) && product.tare_weight > 0;
  const tareWeight = hasTareWeight ? product.tare_weight : 0;
  const stagingKey =
    instanceIndex !== null
      ? buildStorageKey(["inventory-staging", instanceIndex, `${product.id}`])
      : null;

  const [state, setState] = useState<StagingState>({
    stagedEntries: [],
    stagedInterpretation: "absolute",
    deltaDirection: "add",
  });

  useEffect(() => {
    if (!stagingKey) {
      return;
    }
    const payload = readStoredPayload<{
      entries?: unknown;
      updatedAt?: number;
      interpretation?: StagedInterpretation;
      direction?: DeltaDirection;
    }>(stagingKey);
    if (!payload) {
      return;
    }
    try {
      const updatedAt =
        typeof payload.updatedAt === "number" && Number.isFinite(payload.updatedAt)
          ? payload.updatedAt
          : 0;
      if (!updatedAt || Date.now() - updatedAt > STAGING_TTL_MS) {
        clearStoredPayload(stagingKey);
        return;
      }
      const interpretation: StagedInterpretation =
        payload.interpretation === "delta" ? "delta" : "absolute";
      const direction: DeltaDirection =
        payload.direction === "subtract" ? "subtract" : "add";
      const hydrated = sanitizeStagedEntries(
        payload.entries,
        hasTareWeight,
        interpretation === "delta",
      );
      if (!hydrated.length) {
        clearStoredPayload(stagingKey);
        return;
      }
      setState({
        stagedEntries: hydrated,
        stagedInterpretation: interpretation,
        deltaDirection: direction,
      });
    } catch (error) {
      console.warn("Failed to hydrate inventory staging state; clearing", {
        stagingKey,
        error,
      });
      clearStoredPayload(stagingKey);
    }
  }, [stagingKey, hasTareWeight]);

  useEffect(() => {
    if (!stagingKey) {
      return;
    }
    if (state.stagedEntries.length === 0) {
      clearStoredPayload(stagingKey);
      return;
    }
    try {
      writeStoredPayload(stagingKey, {
        updatedAt: Date.now(),
        entries: state.stagedEntries,
        interpretation: state.stagedInterpretation,
        direction: state.deltaDirection,
      });
    } catch (error) {
      console.warn("Failed to persist inventory staging state", {
        stagingKey,
        error,
      });
    }
  }, [state, stagingKey]);

  const stagedTotal = useMemo(
    () =>
      state.stagedEntries.reduce(
        (total, entry) => total + entry.submissionAmount,
        0,
      ),
    [state.stagedEntries],
  );

  const stagedNetPreview = useMemo(() => {
    if (
      !hasTareWeight ||
      !state.stagedEntries.some((entry) => entry.kind === "tare")
    ) {
      return null;
    }
    return Math.max(
      state.stagedEntries.reduce((total, entry) => {
        if (entry.kind === "tare") {
          return total + entry.netAmount;
        }
        return total + entry.submissionAmount;
      }, 0),
      0,
    );
  }, [state.stagedEntries, hasTareWeight]);

  const hasAmountValue = state.stagedEntries.length > 0;
  const isAmountValid = hasAmountValue && Number.isFinite(stagedTotal);
  const adjustmentSign = state.deltaDirection === "add" ? 1 : -1;
  const submissionBaseAmount = hasAmountValue ? stagedTotal : 0;
  const resolvedNewAmount =
    state.stagedInterpretation === "absolute"
      ? submissionBaseAmount
      : submissionBaseAmount * adjustmentSign;

  const addTareEntry = useCallback(
    (grossAmount: number) => {
      const netAmount = Math.max(grossAmount - tareWeight, 0);
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `tare-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setState((current) => ({
        ...current,
        stagedEntries: [
          ...current.stagedEntries,
          {
            id,
            kind: "tare",
            submissionAmount: netAmount,
            grossAmount,
            netAmount,
          },
        ],
      }));
    },
    [tareWeight],
  );

  const addManualEntry = useCallback((amount: number) => {
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setState((current) => ({
      ...current,
      stagedEntries: [
        ...current.stagedEntries,
        { id, kind: "manual", submissionAmount: amount },
      ],
    }));
  }, []);

  const addPackageEntry = useCallback(
    (quantity: number, packageSize: number) => {
      const submissionAmount = quantity * packageSize;
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `package-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      setState((current) => ({
        ...current,
        stagedEntries: [
          ...current.stagedEntries,
          {
            id,
            kind: "package",
            submissionAmount,
            quantity,
            packageSize,
          },
        ],
      }));
    },
    [],
  );

  const removeStagedEntry = useCallback((id: string) => {
    setState((current) => ({
      ...current,
      stagedEntries: current.stagedEntries.filter((entry) => entry.id !== id),
    }));
  }, []);

  const clearStagedEntries = useCallback(() => {
    setState((current) => ({
      ...current,
      stagedEntries: [],
    }));
  }, []);

  const resetStaging = useCallback(() => {
    setState({
      stagedEntries: [],
      stagedInterpretation: "absolute",
      deltaDirection: "add",
    });
  }, []);

  return {
    stagedEntries: state.stagedEntries,
    stagedInterpretation: state.stagedInterpretation,
    deltaDirection: state.deltaDirection,
    stagedTotal,
    stagedNetPreview,
    submissionBaseAmount,
    resolvedNewAmount,
    hasAmountValue,
    isAmountValid,
    setStagedInterpretation: (next) =>
      setState((current) => ({ ...current, stagedInterpretation: next })),
    setDeltaDirection: (next) =>
      setState((current) => ({ ...current, deltaDirection: next })),
    addTareEntry,
    addManualEntry,
    addPackageEntry,
    removeStagedEntry,
    clearStagedEntries,
    resetStaging,
    hasTareWeight,
    tareWeight,
  };
}
