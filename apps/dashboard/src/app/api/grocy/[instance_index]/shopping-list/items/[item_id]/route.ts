import { NextResponse } from "next/server";
import { proxyGrocyRequest, resolveInstanceAndRole } from "../../route-helpers";
import type { RouteContext } from "../../types";

export async function PATCH(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const resolved = await resolveInstanceAndRole(context);
  if ("error" in resolved) {
    return resolved.error;
  }
  const { instanceIndex, roleHeaders } = resolved;
  const { item_id } = await context.params;
  if (!item_id) {
    return NextResponse.json(
      { error: "instance_index and item_id are required" },
      { status: 400 },
    );
  }

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
    path: `/grocy/{instance}/shopping-list/active/items/${item_id}`,
    method: "PATCH",
    payload,
  });
}

export async function DELETE(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const resolved = await resolveInstanceAndRole(context);
  if ("error" in resolved) {
    return resolved.error;
  }
  const { instanceIndex, roleHeaders } = resolved;
  const { item_id } = await context.params;
  if (!item_id) {
    return NextResponse.json(
      { error: "instance_index and item_id are required" },
      { status: 400 },
    );
  }

  return proxyGrocyRequest({
    instanceIndex,
    roleHeaders,
    path: `/grocy/{instance}/shopping-list/active/items/${item_id}`,
    method: "DELETE",
    okStatuses: [204],
  });
}
