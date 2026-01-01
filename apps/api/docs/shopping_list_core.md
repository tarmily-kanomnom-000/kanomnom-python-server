# Shopping List Core Semantics

Source: `apps/api/src/core/grocy/shopping_list_manager.py` & `shopping_list_generator.py`

## Manager Guarantees

- **Locking:** Per-instance lock file is used around mutating operations (add/remove/bulk update/bulk remove/archive) to avoid concurrent writes to `active.json`.
- **Normalization:** Legacy lists are backfilled on load (version, timestamps, location_order, deleted_product_ids, missing item fields). A `.bak` of the original file is written before saving the normalized version.
- **Validation:** Loaded lists are validated against `ShoppingList` Pydantic model before being returned.
- **Deleted product tracking:** Removes/bulk removes append `product_id` to `deleted_product_ids` to prevent re-adding on merge.

## Item Enrichment (Add/Bulk Add)

- Every add call builds item payloads with current stock totals, min stock, unit, shopping location name/id, and last purchase price (via `PriceAnalyzer`), plus timestamps and generated UUIDs.
- Both single and bulk add reject duplicate `product_id` values already present on the active list (any status) before persisting.

## Merge Logic (generate with merge_with_existing)

`ShoppingListGenerator.merge_with_existing`:
- Preserves checked items (`purchased`/`unavailable`).
- Excludes items in `deleted_product_ids`.
- Updates pending items with latest `quantity_suggested`, `current_stock`, `min_stock`, `last_price`, `modified_at`.
- Adds new items that fell below threshold.
- Logs merge summary (preserved/merged/added/skipped) for observability.

## Bulk Operations

- **Bulk add:** Rejects duplicate `product_id` already in list; enriches items with location/price; uses same pipeline as single add.
- **Bulk remove:** Errors if any `item_id` missing; updates `deleted_product_ids`; returns removed items.
- **Bulk update:** Errors if any `item_id` missing; updates status/quantity/notes/checked_at; bumps version/last_modified_at.

## Completion

- `complete_list` removes active list, archives to timestamped file, and clears cache; if queued offline it replays once online and is removed from the queue.

## Offline Replay (Dashboard client summary)

See also `apps/api/docs/shopping_list.md`:
- Queued actions: `add_item`, `remove_item`, `update_item`, `replay_snapshot` (coalesced offline state), `complete_list`.
- Only consecutive `update_item` actions merge; add/remove/complete/replay are barriers.
- On reconnect: latest `replay_snapshot` per instance runs first; remaining actions (including complete) then run in queue order. `complete_list` is removed after execution (404s ignored).
