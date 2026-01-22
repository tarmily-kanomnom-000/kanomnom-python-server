import { useCallback, useEffect, useMemo, useState } from "react";
import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
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
    }
  | {
      id: string;
      kind: "measurement";
      submissionAmount: number;
      grossAmount: number;
      netAmount: number;
      fromUnit: string;
      toUnit: string;
      factor: number;
      tareApplied: boolean;
      tareAmount: number | null;
    }
  | {
      id: string;
      kind: "conversion";
      submissionAmount: number;
      grossAmount: number;
      netAmount: number;
      fromUnit: string;
      toUnit: string;
      factor: number;
      tareApplied: boolean;
      tareAmount: number | null;
    };

export type StagedInterpretation = "absolute" | "delta";
export type DeltaDirection = "add" | "subtract";

const STAGING_TTL_MS = 24 * 60 * 60 * 1000;

type StagingState = {
  stagedEntries: InventoryStagedEntry[];
  stagedInterpretation: StagedInterpretation;
  deltaDirection: DeltaDirection;
};

const normalizeNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed.length) {
      return null;
    }
    const parsed = Number(trimmed);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
};

const buildDefaultState = (): StagingState => ({
  stagedEntries: [],
  stagedInterpretation: "absolute",
  deltaDirection: "add",
});

const sanitizeStagedEntries = (
  rawEntries: unknown,
  allowTare: boolean,
  allowManualForTare: boolean,
): InventoryStagedEntry[] => {
  if (!Array.isArray(rawEntries)) {
    return [];
  }
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
        const grossAmount = normalizeNumber(record.grossAmount);
        const netAmount = normalizeNumber(record.netAmount);
        const submissionAmount = normalizeNumber(record.submissionAmount);
        if (
          grossAmount !== null &&
          netAmount !== null &&
          submissionAmount !== null
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
        const quantity = normalizeNumber(record.quantity);
        const packageSize = normalizeNumber(record.packageSize);
        if (quantity !== null && packageSize !== null) {
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
        const submissionAmount = normalizeNumber(record.submissionAmount);
        if (submissionAmount !== null && submissionAmount >= 0) {
          return {
            id: idValue,
            kind: "manual",
            submissionAmount,
          };
        }
      }
      if (kind === "conversion") {
        return normalizeConversionEntry(record, idValue, "conversion");
      }
      if (kind === "measurement") {
        return normalizeConversionEntry(record, idValue, "measurement");
      }
      return null;
    })
    .filter((entry): entry is InventoryStagedEntry => entry !== null);
};

const normalizeConversionEntry = (
  record: Record<string, unknown>,
  idValue: string,
  kind: "conversion" | "measurement",
): InventoryStagedEntry | null => {
  const grossAmount = normalizeNumber(record.grossAmount);
  const netAmount = normalizeNumber(record.netAmount);
  const submissionAmount = normalizeNumber(record.submissionAmount);
  const fromUnit = record.fromUnit;
  const toUnit = record.toUnit;
  const factor = normalizeNumber(record.factor);
  const tareApplied = record.tareApplied;
  const tareAmount = normalizeNumber(record.tareAmount);
  if (
    grossAmount !== null &&
    netAmount !== null &&
    submissionAmount !== null &&
    typeof fromUnit === "string" &&
    typeof toUnit === "string" &&
    factor !== null &&
    typeof tareApplied === "boolean"
  ) {
    return {
      id: idValue,
      kind,
      grossAmount,
      netAmount,
      submissionAmount,
      fromUnit,
      toUnit,
      factor,
      tareApplied,
      tareAmount,
    };
  }
  return null;
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
  addPackageEntry: (quantity: number, packageSize: number) => void;
  addMeasurementEntry: (entry: MeasurementEntryInput) => void;
  removeStagedEntry: (id: string) => void;
  clearStagedEntries: () => void;
  resetStaging: () => void;
  hasTareWeight: boolean;
  tareWeight: number;
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

  const [state, setState] = useState<StagingState>(buildDefaultState);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    if (!stagingKey) {
      setIsHydrated(true);
      setState(buildDefaultState());
      return;
    }
    setIsHydrated(false);
    const payload = readStoredPayload<{
      entries?: unknown;
      updatedAt?: number;
      interpretation?: StagedInterpretation;
      direction?: DeltaDirection;
    }>(stagingKey);
    if (!payload) {
      setState(buildDefaultState());
      setIsHydrated(true);
      return;
    }
    try {
      const updatedAt =
        typeof payload.updatedAt === "number" &&
        Number.isFinite(payload.updatedAt)
          ? payload.updatedAt
          : 0;
      if (!updatedAt || Date.now() - updatedAt > STAGING_TTL_MS) {
        clearStoredPayload(stagingKey);
        setState(buildDefaultState());
        setIsHydrated(true);
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
        setState(buildDefaultState());
        setIsHydrated(true);
        return;
      }
      setState({
        stagedEntries: hydrated,
        stagedInterpretation: interpretation,
        deltaDirection: direction,
      });
      setIsHydrated(true);
    } catch (error) {
      console.warn("Failed to hydrate inventory staging state; clearing", {
        stagingKey,
        error,
      });
      clearStoredPayload(stagingKey);
      setState(buildDefaultState());
      setIsHydrated(true);
    }
  }, [hasTareWeight, stagingKey]);

  useEffect(() => {
    if (!stagingKey || !isHydrated) {
      return;
    }
    try {
      if (state.stagedEntries.length === 0) {
        clearStoredPayload(stagingKey);
        return;
      }
      const ok = writeStoredPayload(stagingKey, {
        updatedAt: Date.now(),
        entries: state.stagedEntries,
        interpretation: state.stagedInterpretation,
        direction: state.deltaDirection,
      });
      if (!ok) {
        console.warn("Failed to persist inventory staging state", {
          stagingKey,
        });
      }
    } catch (error) {
      console.warn("Failed to persist inventory staging state", {
        stagingKey,
        error,
      });
    }
  }, [isHydrated, state, stagingKey]);

  const stagedTotal = useMemo(
    () =>
      state.stagedEntries.reduce(
        (total, entry) => total + entry.submissionAmount,
        0,
      ),
    [state.stagedEntries],
  );

  const stagedNetPreview = useMemo(() => {
    const hasTareEntries = state.stagedEntries.some(
      (entry) =>
        entry.kind === "tare" ||
        ((entry.kind === "conversion" || entry.kind === "measurement") &&
          entry.tareApplied),
    );
    if (!hasTareWeight && !hasTareEntries) {
      return null;
    }
    return Math.max(
      state.stagedEntries.reduce((total, entry) => {
        if (entry.kind === "tare") {
          return total + entry.netAmount;
        }
        if (
          (entry.kind === "conversion" || entry.kind === "measurement") &&
          entry.tareApplied
        ) {
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

  const addMeasurementEntry = useCallback((entry: MeasurementEntryInput) => {
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `measurement-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setState((current) => ({
      ...current,
      stagedEntries: [
        ...current.stagedEntries,
        {
          id,
          kind: "measurement",
          submissionAmount: entry.submissionAmount,
          grossAmount: entry.grossAmount,
          netAmount: entry.netAmount,
          fromUnit: entry.fromUnit,
          toUnit: entry.toUnit,
          factor: entry.factor,
          tareApplied: entry.tareApplied,
          tareAmount: entry.tareAmount,
        },
      ],
    }));
  }, []);

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
    setState(buildDefaultState());
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
    addPackageEntry,
    addMeasurementEntry,
    removeStagedEntry,
    clearStagedEntries,
    resetStaging,
    hasTareWeight,
    tareWeight,
  };
}
