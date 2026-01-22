# Grocy Route Semantics (FastAPI)

Concise reference for the Grocy API routes and key helpers. Use this to understand behavior, validation, and error mapping without digging through route code or the implementation guide.

## Instances (`apps/api/src/api/routes/grocy/instances.py`)
- `GET /grocy/instances` (`list_instances`) — Returns every discovered instance plus address/location/shopping-location rosters by pulling managers from the governor. Loads location lists synchronously inside a threadpool; no pagination or filtering today.

## Lifecycle (`.../lifecycle.py`)
- `POST /grocy/{instance_index}/initialize` (`initialize_instance`) — Seeds shopping locations, product groups, and quantity units from the universal manifest via the governor. 404 if metadata missing; 500 if manifest missing. Response includes identifiers and created shopping locations/groups/units.

## Products (`.../products.py` + `helpers.serialize_inventory_view`)
- `GET /grocy/{instance_index}/products` (`list_products`) — Returns inventory-enriched products. Honors `force_refresh` truthy values {1,true,t,yes,y,on} to invalidate caches for that instance before listing. 404 on missing metadata.
- `GET /grocy/{instance_index}/products/{product_id}` (`get_product`) — Fetches a single product with fresh stock rows; 404 on missing metadata or product_id.
- `POST /grocy/{instance_index}/products/description-metadata` (`update_product_description_metadata`) — Applies structured unit conversions to multiple products and sets the human-readable description inside the note envelope. 400 on invalid conversions; 404 on missing metadata.
- `serialize_inventory_view` — Normalizes structured notes on products/stocks (decodes envelopes, drops empty metadata), validates unit conversions, and maps Grocy unit names across purchase/stock/consume/price contexts for consistent API responses.

## Inventory Corrections (`.../inventory.py`)
- `POST /grocy/{instance_index}/products/{product_id}/inventory` (`correct_product_inventory`) — Validates note text and optional loss-metadata; applies `InventoryCorrection` via `execute_product_mutation`. Returns refreshed inventory view. 400 on validation errors; 404 on missing metadata/product.

## Quantity Units (`.../quantity_units.py`)
- `GET /grocy/{instance_index}/quantity-units` (`list_quantity_units`) — Returns cached Grocy quantity units for the instance. 404 on missing metadata.
- `GET /grocy/quantity-unit-conversions` (`list_quantity_unit_conversions`) — Expands universal quantity unit conversions into a fully connected conversion map keyed by unit names (skipping product-specific conversions). 500 if the conversion manifest or universal manifest is missing; 400 on invalid manifest entries.

## Purchases (`.../purchases.py`)
- `GET /grocy/{instance_index}/products/{product_id}/purchase/defaults` — Returns purchase metadata defaults for a product, optionally scoped to `shopping_location_id`. 404 on missing metadata/product.
- `POST /grocy/{instance_index}/purchases/defaults` — Batch defaults; requires non-empty `product_ids` and returns entries in the same order. 500 if count mismatches, 404 on missing metadata/product.
- `GET /grocy/purchases/schema` — Serves the shared JSON schema for purchase entry payloads; fails fast if the schema diverges from the Pydantic model.
- `POST /grocy/{instance_index}/products/{product_id}/purchase` (`record_purchase_entry`) — Normalizes/derives amount + unit price from metadata (package size/quantity/price + conversion_rate); validates note text; optionally creates shopping locations by name; expands package batches into multiple drafts; writes entries via manager; identifies newly created stock rows; posts summarized purchase data to Grist (best-effort). 400 on metadata/note validation; 404 on metadata/product errors; 500 if no entries persisted.
- `POST /grocy/{instance_index}/products/{product_id}/purchase/derive` — Returns derived amount/unit price/total_usd; 400 unless package_size, package_quantity, package_price, and conversion_rate are provided and positive.
- Helpers: `_ensure_shopping_location_id` resolves/creates shopping locations (400 on validation, 500 on create failure); `_resolve_shopping_location_name` best-effort lookup for Grist payloads; `_derive_purchase_amount_and_price` enforces positive amounts/totals and includes shipping/tax in unit price.

### Tare handling (inventory and purchases)
- Definitions:
  - **Gross** = tare_weight + net. Grocy requires gross when you write stock rows.
  - **Net** = what you actually have on hand. Grocy’s read endpoints (stock/product) return net; tare is already removed.
- What to send:
  - Purchases (tare-enabled): send `current_net + purchased_net + tare`. Grocy subtracts tare once and the net stock ends up correct, even with multiple package drafts.
  - Inventory absolute corrections (tare-enabled): must send `target_net + tare`. If you send net, Grocy subtracts tare and undercounts by `tare_weight`.
  - Inventory delta adjustments (tare-enabled): send `current_net + delta + tare` as the gross new total.
- How to compute net for staged measurements:
  - Any per-entry tare (product tare, custom tare, or unit-conversion tare) is used only to calculate each entry’s **net** amount.
  - The final payload must still add the **product tare** once to the summed net total before sending to Grocy.
- Why purchase drafts don’t snowball: each draft pulls `current_net` from Grocy, adds the new purchased amount plus tare, and Grocy subtracts tare once. Net stock advances by the purchased amount per draft (no double-adding prior purchases).
- Pitfalls to avoid:
  - Never submit a net absolute correction for a tare product; always add tare before calling Grocy.
  - Do not treat Grocy’s `current_stock` as gross—it is net. Adding tare to a gross baseline will inflate stock.
  - UI/UX should state whether the user is entering net or gross; the backend must convert to gross before submit.

### Code layout (core)
- Inventory logic lives in `apps/api/src/core/grocy/inventory.py` (inventory views, corrections/adjustments, cache loading).
- Purchase resolution/defaults live in `apps/api/src/core/grocy/purchases.py`.
- Shared stock helpers (unit mapping, last-update mapping, price rounding, default best-before) live in `apps/api/src/core/grocy/stock_helpers.py`.

## Shopping Lists (`.../shopping_list.py`)
- See `apps/api/docs/shopping_list.md` for endpoints and `apps/api/docs/shopping_list_core.md` for manager/generator semantics (locking, merge rules, enrichment, deleted_product_ids).

## Shared Mutation Helper (`.../helpers.py`)
- `execute_product_mutation` — Wrapper that runs manager mutations in a threadpool, translates `MetadataNotFoundError`/`ValueError` to 404, propagates Grocy HTTP errors with original status/text, and always returns a refreshed `ProductInventoryView`.
