import type { PendingAction } from "./types";

export const MAX_RETRIES = 3;

export function statusFromError(error: unknown): number | undefined {
  if (typeof error === "object" && error !== null && "status" in error) {
    const status = (error as any).status;
    return typeof status === "number" ? status : undefined;
  }
  return undefined;
}

export function isPermanentFailure(status: number | undefined): boolean {
  return Boolean(status && status >= 400 && status < 500);
}

export function incrementFailureCount(action: PendingAction): PendingAction {
  const failures = (action.failureCount ?? 0) + 1;
  return { ...action, failureCount: failures, timestamp: Date.now() };
}
