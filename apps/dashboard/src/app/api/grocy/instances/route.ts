import { NextResponse } from "next/server";

import { requireUser } from "@/lib/auth/authorization";
import { fetchGrocyInstances } from "@/lib/grocy/server";

export async function GET(): Promise<Response> {
  const authResult = await requireUser();
  if ("response" in authResult) {
    return authResult.response;
  }
  try {
    const instances = await fetchGrocyInstances();
    return NextResponse.json({ instances });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Failed to load Grocy instances.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
