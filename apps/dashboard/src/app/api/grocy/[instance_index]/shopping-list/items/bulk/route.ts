import { NextResponse } from "next/server";
import { proxyGrocyRequest, resolveInstanceAndRole } from "../../route-helpers";
import type { RouteContext } from "../../types";

async function handleRequest(
  request: Request,
  context: RouteContext,
  method: "PATCH" | "POST",
): Promise<Response> {
  const resolved = await resolveInstanceAndRole(context);
  if ("error" in resolved) {
    return resolved.error;
  }
  const { instanceIndex, roleHeaders } = resolved;

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  return proxyGrocyRequest({
    instanceIndex,
    roleHeaders,
    path:
      method === "POST"
        ? "/grocy/{instance}/shopping-list/active/items/bulk"
        : "/grocy/{instance}/shopping-list/items/bulk",
    method,
    payload,
    okStatuses: method === "POST" ? [201] : undefined,
    logName:
      method === "POST"
        ? "shopping_list_bulk_add"
        : "shopping_list_bulk_update",
    validate: (body) => {
      if (typeof body !== "object" || body === null) {
        return "Invalid JSON payload";
      }
      if (method === "PATCH" && !Array.isArray((body as any).updates)) {
        return "updates must be an array";
      }
      if (method === "POST" && !Array.isArray(body as any)) {
        return "Payload must be an array of items for bulk add";
      }
      return null;
    },
  });
}

export async function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return handleRequest(request, context, "PATCH");
}

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  return handleRequest(request, context, "POST");
}
