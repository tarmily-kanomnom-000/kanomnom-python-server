import axios from "axios";

type ErrorPayload = { error?: string; detail?: string };

export function isNetworkFailure(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    return !error.response;
  }
  // Fetch network errors surface as TypeError in browsers.
  return error instanceof TypeError;
}

export function normalizeGrocyError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = (error.response?.data ?? {}) as ErrorPayload;
    const message =
      payload.error ??
      payload.detail ??
      error.response?.statusText ??
      error.message;
    return message?.toString() || "Request failed";
  }

  if (error instanceof Error) {
    return error.message || "Request failed";
  }

  if (typeof error === "string") {
    return error || "Request failed";
  }

  return "Request failed";
}
