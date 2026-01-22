import { NextResponse } from "next/server";

import { requireUser } from "@/lib/auth/authorization";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

function resolveApiBaseUrl(): string {
  const apiBaseUrl = environmentVariables.apiBaseUrl?.trim();
  if (!apiBaseUrl) {
    throw new Error(
      "KANOMNOM_API_BASE_URL is not configured. Set it in your dashboard env file.",
    );
  }
  return apiBaseUrl;
}

export async function GET(): Promise<Response> {
  const authResult = await requireUser();
  if ("response" in authResult) {
    return authResult.response;
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL("/grocy/quantity-unit-conversions", apiBaseUrl);
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await safeReadResponseText(response);
    return NextResponse.json(
      { error: detail || "Failed to load Grocy quantity unit conversions." },
      { status: response.status || 502 },
    );
  }

  return NextResponse.json(await response.json());
}
