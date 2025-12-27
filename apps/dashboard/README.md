# Getting Started

## Development Tools

### `fnm` (https://github.com/Schniz/fnm)

`fnm` (Fast Node Manager) is a Node.js version manager. After installing it, run `fnm install` in the project directory to install the version of Node.js specified in the `.nvmrc` file.

export PATH="/Users/tarmilywen/.local/share/fnm/node-versions/v18.19.1/installation/bin":$PATH

### `pnpm` (https://github.com/pnpm/pnpm)

`pnpm` (Performance Node Package Manager) is a package manager for Node.js projects. After installing it, run `pnpm install` in the project directory to install all packages specified in the `package.json` file.

## Third-Party Services

- Vercel (https://vercel.com/craigcarrs-projects/kanomnom)
- Microsoft Clarity (https://clarity.microsoft.com/projects/view/px1f9mvqdo/dashboard)
- Medusa (https://medusa.kanomnom.com/app/products)
- Nextcloud (https://nextcloud.tarmily.com/s/nArsHmAC5A26LMz)

## Environment

Copy `.env.example` to `.env.local` (or the environment-specific file you prefer) and fill in the values. At minimum set `KANOMNOM_API_BASE_URL` (or `NEXT_PUBLIC_API_BASE_URL` when the value must be exposed to the browser) to point at the FastAPI runtime that serves Grocy data, e.g. `http://localhost:8000`. The dashboard relies on this to load Grocy instances for the Inventory workspace.

Authentication is handled by NextAuth with a simple credentials provider so the dashboard is not publicly exposed. Add:

- `AUTH_SECRET`: Random string for NextAuth JWT/session signing.
- `NEXTAUTH_URL`: The dashboard origin (e.g. `http://localhost:3000`).
- `DASHBOARD_USERS_FILE` (preferred): Path to a JSON file containing an array of `{ "username": "...", "passwordHash": "...", "role": "admin|viewer" }`. Relative paths are resolved from `apps/dashboard`, e.g. `./temp_accounts_hash.json`.
- `DASHBOARD_USERS_JSON` (fallback): JSON array of `{ "username": "...", "passwordHash": "...", "role": "admin|viewer" }` entries.

Generate password hashes with `node -e "console.log(require('bcryptjs').hashSync('changeme', 10))"`. Admins can mutate inventory/purchase data; viewers can only browse inventory.

## Dashboard Overview

### Purpose

This Next.js dashboard is the internal control surface for Ka-Nom Nom. The initial focus is the **Grocy Inventory workspace**, which lets operators browse every Grocy instance, inspect addresses/metadata, and view the latest product inventory directly inside the dashboard. All data flows through the FastAPI backend (`apps/api`), so the dashboard never talks to Grocy directly.

### Structure

```
apps/dashboard
├─ src/app
│  ├─ layout.tsx             // Global shell + menu bar
│  ├─ page.tsx               // Overview/landing page
│  ├─ inventory/page.tsx     // Grocy workspace entry
│  └─ api/grocy/...          // Next.js route handlers that proxy FastAPI
├─ src/components/grocy      // Inventory UI (search + product list)
├─ src/lib/grocy             // Typed helpers for server/client fetching
├─ src/queries               // React-query style helpers mirroring example_queries
└─ src/utils                 // Cross-cutting utilities (env vars, etc.)
```

- `src/app/api/grocy/*` exposes lightweight API endpoints (`/api/grocy/instances`, `/api/grocy/[instance]/products`, and the product mutation routes) that forward requests to the FastAPI service using the shared server helpers. This keeps browser traffic on the dashboard origin, avoids CORS/ad-blocker issues, and invalidates caches whenever a mutation runs.
- `src/lib/grocy/server.ts` and `src/lib/grocy/client.ts` centralize data access. The server module wraps remote calls with caching via `React.cache` + `fetch` revalidation and bumps cache versions whenever an inventory mutation succeeds. The client module uses Axios with an in-memory promise cache, automatically clearing entries after `submitInventoryCorrection/submitPurchaseEntry` so fresh product data loads on the next fetch.
- `src/components/grocy/instances-picker.tsx` is a client component that renders the searchable dropdown, instance detail card, and product list. It consumes the server-provided instance list and calls the internal API to hydrate product data.
- `src/queries/getGrocy*.ts` (mirroring `src/example_queries/`) provide ready-to-use query configs once the dashboard adopts TanStack Query. Each query is keyed, typed, and configurable with `useForceCache`.

### Logic Flow (Inventory)

1. `/inventory` loads server-side and calls `fetchGrocyInstances()` (cached on the server) to render the page.
2. `InstancesPicker` receives the instances, renders the search/dropdown UX, and preselects the first instance.
3. When the user focuses or searches, the component filters instances client-side. Selecting an instance triggers `fetchGrocyProducts(instance)` which goes through `/api/grocy/{instance}/products` → FastAPI → Grocy. Client responses are cached per instance, while the server helper tracks a cache-version map that appends `cache_buster` query params so a full page reload always re-fetches the latest data. Operators can click “Refresh data” to send `forceRefresh=1`, which eventually calls FastAPI with `force_refresh=true` and flushes caches for only the active instance.
4. Inventory corrections and purchase entries submit through the Next API routes and immediately fetch `/api/grocy/{instance}/products/{product_id}` so only the affected product row is reconciled in state. Each mutation also invalidates the client cache and bumps the server cache version so the next list fetch (manual or automatic) reflects the new stock.
5. Products are displayed with basic metadata (group, stock count, last update). Errors bubble up as inline alerts that point to misconfigured env vars or offline API nodes.

### Server ↔ Dashboard Type Mapping

FastAPI response/request models live in `apps/api/src/models/grocy.py`. Their TypeScript counterparts inside the dashboard must stay in sync; use this table as the source-of-truth when updating either side:

| FastAPI model (`apps/api/src/models/grocy.py`) | Dashboard type/location |
| --- | --- |
| `GrocyProductInventoryEntry` | `GrocyProductInventoryEntry` (`src/lib/grocy/types.ts`) |
| `GrocyStockEntryPayload` | `GrocyStockEntry` (`src/lib/grocy/types.ts`) |
| `GrocyProductsResponse` | `GrocyProductsResponse` (`src/lib/grocy/types.ts`) |
| `InventoryCorrectionRequest` | `InventoryCorrectionRequestPayload` (`src/lib/grocy/types.ts`) |
| `PurchaseEntryRequest` | `PurchaseEntryRequestPayload` (`src/lib/grocy/types.ts`) |

Whenever you add or rename fields in the Python models, mirror the change in the listed TypeScript types and re-run the transformers in `src/lib/grocy/transformers.ts` so serialization stays correct.

### Best Practices

- **Single source of truth:** All Grocy calls go through `src/lib/grocy` (server or client). Never hit the FastAPI host directly from React components—always go through the `/api/grocy` routes or the shared helpers.
- **Type everything:** Reuse the models in `src/lib/grocy/types.ts` throughout components, queries, and API handlers to avoid drift with the FastAPI schema.
- **Cache intentionally:** Use the existing `React.cache` wrappers server-side and the in-memory cache or query helpers client-side. If a call needs fresh data, pass `forceRefresh` to the client helper or `useForceCache=false` to the query builder, and make sure any new mutation invalidates the Grocy product caches by calling the provided helpers.
- **Invalidate after mutations:** When adding new Grocy actions (consumption, transfers, etc.), always call both the server (`invalidateGrocyProductsCache`) and client (`invalidateGrocyProductsClientCache`) helpers after the mutation completes so instance/product caches stay coherent.
- **Fail loudly:** When a fetch fails, surface a clear message (see the inventory page for the pattern) and mention the env variable or backend dependency the operator should check.
- **Keep UI components dumb:** All routing/fetching logic belongs in the helpers/API routes. Components should only orchestrate UI state (search text, dropdown visibility) and render typed data.
- **Extend via queries:** New dashboard modules should follow the `src/queries` pattern—wrap remote calls in a query builder, then consume that via TanStack Query or simple hooks. This keeps data-access consistent with the Medusa examples.

Following this structure ensures Grocy integrations stay debuggable, typed, and aligned with the rest of the Ka-Nom Nom dashboard.

## PWA + Offline Grocy Data

- Service worker: built by Serwist from `src/sw.ts` to `public/sw.js`. Registered in `src/app/layout.tsx` via `ServiceWorkerRegistration`.
- Prefetcher: `GrocyOfflineBootstrap` runs once per tab session and calls `prefetchGrocyDataForOffline()` (`src/lib/offline/grocy-cache.ts`). If online, it fetches `/api/grocy/instances`, caches to `localStorage` key `kanomnom:pwa:grocy:instances`, then loops each instance and fetches `/api/grocy/<instance_index>/products?forceRefresh=1`, caching to `kanomnom:pwa:grocy:products:<instance_index>`.
- Read path: Instances/products queries use `fetchWithOfflineCache`, so they store successful responses to `localStorage` and, when offline or on network failure, fall back to the cached payload.
- Mutations: `submitInventoryCorrection` and `submitPurchaseEntry` deserialize the returned product and upsert it into the cached list for that instance, keeping offline data in sync with server state. Client and server caches are invalidated after each mutation.
- Refresh: “Refresh data” passes `forceRefresh` through to the API, which overwrites the cached list with fresh server data.
- Scope: Only instance lists and product inventories are cached today. No offline mutation queue—offline writes will fail fast. Add new data types by reusing the helpers in `src/lib/offline/grocy-cache.ts` and the `fetchWithOfflineCache` wrapper.
