import { NextResponse } from "next/server";

import { requireUser } from "@/lib/auth/authorization";
import { fetchGrocyProductsForInstance } from "@/lib/grocy/server";

type RouteContext = {
  params: Promise<{
    instance_index: string;
  }>;
};

function shouldForceRefresh(request: Request): boolean {
  const url = new URL(request.url);
  const value = url.searchParams.get("forceRefresh");
  if (!value) {
    return false;
  }
  const normalized = value.trim().toLowerCase();
  return ["1", "true", "yes", "y", "on"].includes(normalized);
}

export async function GET(
  request: Request,
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
  const forceRefresh = shouldForceRefresh(request);

  try {
    const products = await fetchGrocyProductsForInstance(instance_index, {
      forceRefresh,
    });
    return NextResponse.json({ products });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to load products.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
