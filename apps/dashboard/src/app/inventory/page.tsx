import type { Metadata } from "next";

import { InstancesPicker } from "@/components/grocy/instances-picker";
import { fetchGrocyInstances } from "@/lib/grocy/server";

export const metadata: Metadata = {
  title: "Inventory | Ka-Nom Nom Dashboard",
};

export const revalidate = 0;

export default async function InventoryPage() {
  let instances: Awaited<ReturnType<typeof fetchGrocyInstances>> = [];
  let errorMessage: string | null = null;

  try {
    instances = await fetchGrocyInstances();
  } catch (error) {
    errorMessage =
      error instanceof Error
        ? error.message
        : "An unexpected error occurred while loading Grocy instances.";
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-10">
      {errorMessage ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-900">
          <p className="font-semibold">Unable to reach the Grocy API.</p>
          <p className="mt-2 text-red-800">
            {errorMessage}. Confirm the FastAPI server is running and that
            `KANOMNOM_API_BASE_URL` is set correctly in your dashboard env file.
          </p>
        </div>
      ) : (
        <InstancesPicker instances={instances} />
      )}
    </main>
  );
}
