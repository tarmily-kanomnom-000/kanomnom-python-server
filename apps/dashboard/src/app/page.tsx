import Link from "next/link";

export default function Page() {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-12">
      <section className="rounded-3xl border border-neutral-200 bg-white p-10 shadow-sm">
        <p className="text-sm uppercase tracking-wide text-neutral-500">
          Ka-Nom Nom Dashboard
        </p>
        <h1 className="mt-3 text-4xl font-semibold text-neutral-900">
          Operate and monitor your services in one place.
        </h1>
        <p className="mt-4 text-base text-neutral-600">
          We{"'"}re gradually replacing the storefront with a focused internal
          console. Start with the Inventory workspace to browse Grocy instances,
          then layer in workflows as the API surface grows.
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            href="/inventory"
            className="inline-flex items-center justify-center rounded-full bg-neutral-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-neutral-800"
          >
            Go to Inventory
          </Link>
        </div>
      </section>
    </main>
  );
}
