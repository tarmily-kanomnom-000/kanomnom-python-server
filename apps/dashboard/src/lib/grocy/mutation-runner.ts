import { isOffline } from "@/lib/offline/status";
import { isNetworkFailure, normalizeGrocyError } from "./errors";

type MutationOptions<T> = {
  request: () => Promise<T>;
  offlineFallback?: (() => T | Promise<T>) | null;
  onSuccess?: (() => void) | null;
};

export async function runGrocyMutation<T>({
  request,
  offlineFallback,
  onSuccess,
}: MutationOptions<T>): Promise<T> {
  try {
    const result = await request();
    onSuccess?.();
    return result;
  } catch (error) {
    if (offlineFallback && (isOffline() || isNetworkFailure(error))) {
      return await offlineFallback();
    }
    const message = normalizeGrocyError(error);
    if (error instanceof Error && error.message === message) {
      throw error;
    }
    throw new Error(message);
  }
}
