import { NextResponse } from "next/server";

import { fetchGrocyInstances } from "@/lib/grocy/server";

export async function GET(): Promise<Response> {
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
