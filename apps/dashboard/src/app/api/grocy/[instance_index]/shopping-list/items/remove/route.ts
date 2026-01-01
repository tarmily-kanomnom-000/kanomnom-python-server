import { proxyGrocyRequest, resolveInstanceAndRole } from "../../route-helpers";
import type { RouteContext } from "../../types";

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
    return new Response(JSON.stringify({ error: "Invalid JSON payload" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  return proxyGrocyRequest({
    instanceIndex,
    roleHeaders,
    path: "/grocy/{instance}/shopping-list/items/remove",
    method: "POST",
    payload,
    logName: "shopping_list_bulk_remove",
    validate: (body) => {
      if (
        !body ||
        typeof body !== "object" ||
        !Array.isArray((body as any).item_ids) ||
        (body as any).item_ids.length === 0
      ) {
        return "item_ids must be a non-empty array";
      }
      return null;
    },
  });
}
