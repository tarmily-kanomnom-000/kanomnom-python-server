import { NextResponse } from "next/server";

import { requireUser } from "@/lib/auth/authorization";
import { fetchGrocyInstancesForDashboard } from "@/lib/grocy/server";

function shouldForceRefresh(request: Request): boolean {
  const url = new URL(request.url);
  const value = url.searchParams.get("forceRefresh");
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  return ["1", "true", "yes", "y", "on"].includes(normalized);
}

export async function GET(request: Request): Promise<Response> {
  const authResult = await requireUser();
  if ("response" in authResult) {
    return authResult.response;
  }
  const forceRefresh = shouldForceRefresh(request);
  try {
    const instances = await fetchGrocyInstancesForDashboard({ forceRefresh });
    return NextResponse.json({ instances });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Failed to load Grocy instances.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
