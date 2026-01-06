# Grocy Dashboard Semantics (Next.js)

Concise reference for dashboard-side Grocy flows: API proxies, data helpers, offline caches, and shopping-list sync. Use this to understand behavior, validation, and cache invalidation without digging through the code.

## Next.js API Routes (`apps/dashboard/src/app/api/grocy/`)
- `GET /api/grocy/instances` — Auth required (any role). Proxies to FastAPI `GET /grocy/instances`; returns `{ instances }` or 502 with message on upstream failure.
- `GET /api/grocy/{instance_index}/products` — Auth required (any role). Supports `forceRefresh` truthy query values {1,true,yes,y,on}; proxies to FastAPI products with matching `force_refresh`; returns `{ products }` or 502 on upstream failure; 400 if `instance_index` missing.
- Shopping list proxies (admin-only via `resolveInstanceAndRole`):
  - `POST /api/grocy/{instance}/shopping-list/generate` — Forwards JSON body; 400 on invalid JSON.
  - `GET /api/grocy/{instance}/shopping-list/active` — Pass-through to FastAPI.
  - `POST /api/grocy/{instance}/shopping-list/active/complete` — Completes active list.
  - `POST /api/grocy/{instance}/shopping-list/active/items` — Single add; 400 on invalid JSON; expects 201 upstream.
  - `PATCH|POST /api/grocy/{instance}/shopping-list/items/bulk` — Bulk update/add; validates payload shape (array for POST, `.updates` array for PATCH); logs success/failure labels; allows 201 for bulk add.
  - `POST /api/grocy/{instance}/shopping-list/items/remove` — Validates non-empty `item_ids` array; logs `shopping_list_bulk_remove`.
  - `PATCH /api/grocy/{instance}/shopping-list/active/items/{item_id}` — Validates `item_id` for legacy single-item updates. All proxies use `proxyGrocyRequest`, preserving upstream status and detail text when available.
- Shared helpers: `resolveInstanceAndRole` enforces admin for shopping-list mutations and builds role headers; `resolveApiBaseUrl` requires `KANOMNOM_API_BASE_URL`; `proxyGrocyRequest` centralizes fetch, status allowlist, JSON validation, and error logging.

## Server Data Access (`src/lib/grocy/server.ts`)
- `fetchGrocyInstances` — Server-only cached (`React.cache`) fetch to FastAPI `/grocy/instances`; revalidates every 120s; throws with upstream status detail on failure.
- `fetchGrocyProductsForInstance` — Uses per-instance cache-version map to append `cache_buster` on version bumps; honors `forceRefresh` to bypass cache and disable revalidation; `invalidateGrocyProductsCache` increments version so the next fetch bypasses stale cache (used after mutations).
- All fetches require `KANOMNOM_API_BASE_URL`; `safeReadResponseText` surfaces upstream error text in thrown messages.

## Client Data Access (`src/lib/grocy/client.ts`)
- In-memory promise cache per instance for list fetches; `invalidateGrocyProductsClientCache` clears it after mutations.
- `fetchGrocyProducts` — Uses `/api/grocy/{instance}/products`, routes through `fetchWithOfflineCache` to persist results to `localStorage` and fall back when offline/network errors occur; supports `forceRefresh`.
- `fetchGrocyProduct` — Reads cached list first; fetches `/api/grocy/{instance}/products/{id}`; on offline/network failure with cached entry returns cached product; updates offline cache on success.
- `submitInventoryCorrection` and `submitPurchaseEntry` — POST to API routes; normalize error messages; invalidate client cache and update/offload product fetch to keep cache coherent; purchase submission also returns new stock entries parsed from upstream.
- Purchase helpers for defaults/batch defaults/derive call corresponding API routes with no-store fetch and typed payloads.

## Offline Caching (Instances/Products) (`src/lib/offline/grocy-cache.ts`)
- Stores instances and per-instance products in `localStorage` under `kanomnom:pwa:*`; uses `fetchWithOfflineCache` to fall back on offline/network failure.
- `prefetchGrocyDataForOffline` (run once per tab via sessionStorage guard) fetches instances, products with `forceRefresh=1`, and active shopping list per instance; writes caches; logs warnings on failures but doesn’t throw.
- Helper functions read/write/upsert cached products and instances; `isOffline`/network checks gate fallbacks.

## Offline Shopping List Cache & Sync (`src/lib/offline/shopping-list-cache.ts`)
- Manages cached active list per instance and a sync queue persisted to `localStorage` (`kanomnom:pwa:shopping-list:*`).
- Queued actions: `add_item`, `remove_item`, `update_item`, `replay_snapshot` (coalesces latest offline state), `complete_list`, and `generate_list`. Consecutive updates are merged; snapshots replace prior granular actions for the same instance.
- `applyOptimisticUpdate` updates local list/version timestamps for UI responsiveness.
- `syncPendingActions` runs when online: replays latest snapshot per instance first, batches consecutive updates, retries transient failures up to 3 times, drops permanent 4xx errors, tracks `hadSyncDrop`, and updates listeners.
- `setupOnlineEventListeners` emits connectivity and sync info; `subscribe*` helpers let UI reflect queue status or persistence failures.
- `refreshActiveListCache` retries fetch of active list after mutations to keep offline cache aligned.

## Shopping List Client Helper (`src/lib/grocy/shopping-list-client.ts`)
- `bulkAddShoppingListItems` — Calls dashboard API bulk-add endpoint; raises error with upstream detail when available; returns typed items for optimistic UI or cache updates.
