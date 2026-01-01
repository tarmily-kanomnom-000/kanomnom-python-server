import { NextResponse } from "next/server";
import { proxyGrocyRequest, resolveInstanceAndRole } from "../route-helpers";
import type { RouteContext } from "../types";

export async function POST(
  request: Request,
  context: RouteContext,
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
    path: "/grocy/{instance}/shopping-list/active/items",
    method: "POST",
    payload,
    okStatuses: [201],
  });
}
