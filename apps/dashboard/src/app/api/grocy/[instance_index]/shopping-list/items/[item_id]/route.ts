import { NextResponse } from "next/server";

import { proxyGrocyRequest, resolveInstanceAndRole } from "../../route-helpers";
import type { RouteContext } from "../../types";

type UpdateBody = Record<string, unknown>;

type BulkUpdatePayload = {
  updates: UpdateBody[];
};

// Preserve the single-item endpoint by forwarding to the bulk updater (Design-for-N).
function buildSingleUpdatePayload(
  itemId: string,
  body: UpdateBody,
): BulkUpdatePayload {
  return {
    updates: [
      {
        ...body,
        item_id: itemId,
      },
    ],
  };
}

function validateSingleUpdatePayload(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return "Invalid JSON payload";
  }

  const { updates } = payload as { updates?: unknown };
  if (!Array.isArray(updates) || updates.length !== 1) {
    return "Payload must include exactly one update";
  }

  const [update] = updates;
  if (!update || typeof update !== "object") {
    return "Update must be an object";
  }

  if (typeof (update as { item_id?: unknown }).item_id !== "string") {
    return "item_id is required";
  }

  return null;
}

export async function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const resolved = await resolveInstanceAndRole(context);
  if ("error" in resolved) {
    return resolved.error;
  }
  const { instanceIndex, roleHeaders } = resolved;

  const { item_id: itemId } = await context.params;
  if (!itemId) {
    return NextResponse.json({ error: "item_id is required" }, { status: 400 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON payload" },
      { status: 400 },
    );
  }

  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json(
      { error: "Payload must be an object" },
      { status: 400 },
    );
  }

  const payload = buildSingleUpdatePayload(itemId, body as UpdateBody);

  return proxyGrocyRequest({
    instanceIndex,
    roleHeaders,
    path: "/grocy/{instance}/shopping-list/items/bulk",
    method: "PATCH",
    payload,
    logName: "shopping_list_single_update",
    validate: validateSingleUpdatePayload,
  });
}
