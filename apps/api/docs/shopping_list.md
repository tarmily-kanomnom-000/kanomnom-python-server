# Shopping List API (Current)

Source: `apps/api/src/api/routes/grocy/shopping_list.py`

## Endpoints

- `POST /grocy/{instance_index}/shopping-list/generate` — generate/merge active list (conflict if active exists unless `merge_with_existing=true`).
- **Request:** `{ "merge_with_existing": false }`
- **Responses:** `200` with list JSON; `409` with detail if active exists and merge is false; `400` invalid JSON.
- `GET /grocy/{instance_index}/shopping-list/active` — fetch active list.
- **Responses:** `200` with list JSON; `200` with `null` if no active list exists.
- `POST /grocy/{instance_index}/shopping-list/active/complete` — archive active list (queued offline; replays once online).
- **Responses:** `200` with archive info `{ "archived_to": "...", "message": "..." }`; `404` if no active list.
- `POST /grocy/{instance_index}/shopping-list/active/items` — add single item.
- **Request:** `{ "product_id": <int>, "quantity": <float> }`
- **Notes:** Enriches each item with location name, current stock, min stock, unit, and last purchase price pulled from Grocy. Rejects duplicate `product_id` already on the active list (any status).
- **Responses:** `201` with item JSON; `404` if no active list; `404` if product_id not found.
- `POST /grocy/{instance_index}/shopping-list/active/items/bulk` — bulk add items (Design-for-N).
- **Request:** array of `{ "product_id": <int>, "quantity": <float> }` (duplicates rejected).
- **Notes:** Uses the same enrichment pipeline as single add (location name, stock totals, min stock, unit, last purchase price); rejects duplicate `product_id` already on the list.
- **Responses:** `201` with array of items; `404` if no active list; `404` if any product_id not found.
- `PATCH /grocy/{instance_index}/shopping-list/items/bulk` — bulk update items (status/notes/quantity).
- **Request:** `{ "updates": [ { "item_id": "uuid", "status": "pending|purchased|unavailable", "quantity_purchased": <float|null>, "notes": <string|null>, "checked_at": <iso|null> } ] }`
- **Responses:** `200` with updated items; `404` if list missing or any item_id missing; `400` invalid payload.
- `DELETE /grocy/{instance_index}/shopping-list/active/items/{item_id}` — remove a single item (tracks deleted product to prevent re-adding on merge).
- **Responses:** `204`; `404` if list missing or item not found.
- `POST /grocy/{instance_index}/shopping-list/items/remove` — bulk remove items; tracks deleted product_ids to avoid re-adding on merge.
- **Request:** `{ "item_ids": ["uuid1","uuid2"] }` (non-empty).
- **Responses:** `200` with removed items; `404` if list missing or any item_id missing; `400` invalid payload.

See `shopping_list_core.md` for manager/generator semantics (locking, normalization backups, merge rules, deleted_product_ids).

## Offline/Queue Semantics (Dashboard client)

- Actions queued offline: `add_item`, `remove_item`, `update_item`, `replay_snapshot` (coalesced offline state), and `complete_list`.
- Only consecutive `update_item` actions are merged; add/remove/complete/replay act as barriers to preserve intent.
- `complete_list` is replayed once online and removed from the queue (no duplicate completes).
- `replay_snapshot` replaces granular actions for the same instance; non-mergeable actions (e.g., complete) remain separate.
- Replay order on reconnect: latest `replay_snapshot` per instance runs first; remaining actions (including complete) then run in queue order.

## Connectivity and Caching

- Connectivity state is centralized via dashboard `useConnectivityStatus`/`useSyncStatus`; offline/online decisions for queue replay use that shared status.
- Product cache busting (`cache_buster` query) is only appended when a product cache version bump occurs or `forceRefresh` is requested; shopping-list-only operations do not invalidate products.
