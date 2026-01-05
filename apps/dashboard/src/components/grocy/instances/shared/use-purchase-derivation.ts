import { useEffect, useRef, useState } from "react";
import { fetchPurchaseEntryCalculation } from "@/lib/grocy/client";
import type { PurchaseEntryRequestPayload } from "@/lib/grocy/types";

export type PurchaseMetadataPayload = NonNullable<
  PurchaseEntryRequestPayload["metadata"]
>;

type PurchaseDerivationState = {
  amount: number | null;
  unitPrice: number | null;
  totalUsd: number | null;
};

type UsePurchaseDerivationArgs = {
  instanceIndex: string | null;
  productId: number;
  metadata: PurchaseMetadataPayload;
  canDeriveTotals: boolean;
};

type UsePurchaseDerivationResult = {
  derivedTotals: PurchaseDerivationState;
  deriveError: string | null;
};

export function usePurchaseDerivation({
  instanceIndex,
  productId,
  metadata,
  canDeriveTotals,
}: UsePurchaseDerivationArgs): UsePurchaseDerivationResult {
  const [derivedTotals, setDerivedTotals] = useState<PurchaseDerivationState>({
    amount: null,
    unitPrice: null,
    totalUsd: null,
  });
  const [deriveError, setDeriveError] = useState<string | null>(null);
  const deriveRequestId = useRef(0);

  useEffect(() => {
    if (!canDeriveTotals || !instanceIndex) {
      setDerivedTotals({ amount: null, unitPrice: null, totalUsd: null });
      setDeriveError(null);
      return;
    }
    const requestId = deriveRequestId.current + 1;
    deriveRequestId.current = requestId;
    setDeriveError(null);
    const loadDerivation = async () => {
      try {
        const result = await fetchPurchaseEntryCalculation(
          instanceIndex,
          productId,
          metadata,
        );
        if (deriveRequestId.current !== requestId) {
          return;
        }
        setDerivedTotals({
          amount: result.amount,
          unitPrice: result.unitPrice,
          totalUsd: result.totalUsd,
        });
      } catch (error) {
        if (deriveRequestId.current !== requestId) {
          return;
        }
        const message =
          error instanceof Error
            ? error.message
            : "Unable to compute purchase totals.";
        setDerivedTotals({ amount: null, unitPrice: null, totalUsd: null });
        setDeriveError(message);
      }
    };
    void loadDerivation();
  }, [canDeriveTotals, instanceIndex, metadata, productId]);

  return { derivedTotals, deriveError };
}
