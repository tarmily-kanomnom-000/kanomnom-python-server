import { NextResponse } from "next/server";

import { requireUser } from "@/lib/auth/authorization";
import { safeReadResponseText } from "@/lib/http";
import { environmentVariables } from "@/utils/environmentVariables";

type RouteContext = {
  params: Promise<{
    instance_index: string;
  }>;
};

function resolveApiBaseUrl(): string {
  const apiBaseUrl = environmentVariables.apiBaseUrl?.trim();
  if (!apiBaseUrl) {
    throw new Error(
      "KANOMNOM_API_BASE_URL is not configured. Set it in your dashboard env file.",
    );
  }
  return apiBaseUrl;
}

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const authResult = await requireUser();
  if ("response" in authResult) {
    return authResult.response;
  }

  const { instance_index } = await context.params;
  if (!instance_index) {
    return NextResponse.json(
      { error: "instance_index is required" },
      { status: 400 },
    );
  }

  const apiBaseUrl = resolveApiBaseUrl();
  const url = new URL(`/grocy/${instance_index}/quantity-units`, apiBaseUrl);
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await safeReadResponseText(response);
    return NextResponse.json(
      { error: detail || "Failed to load Grocy quantity units." },
      { status: response.status || 502 },
    );
  }

  return NextResponse.json(await response.json());
}
