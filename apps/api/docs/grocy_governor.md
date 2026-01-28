## Grocy Governance Architecture

This document explains how Grocy-related components are structured inside the Python server and what future responsibilities the **GrocyGovernor** is expected to assume.

### Current Structure

```
apps/api/grocy_manifest/       # Source of truth on disk
apps/api/src/core/grocy/
├── client.py                  # Low-level HTTP wrapper for Grocy
├── manager.py                 # Per-instance orchestration (inventory, purchases, manifests)
├── metadata.py                # Typed loader for metadata.yaml files
├── governor.py                # Governing entity that returns managers
├── models.py                  # Dataclasses for manifest payloads
├── services.py                # Domain services (manifest sync for quantity units/product groups)
└── sync.py                    # Generic reconciliation engine
```

- **GrocyClient** performs authenticated REST calls and knows nothing about manifests or reconciliation rules.
- **GrocyManager** encapsulates per-instance business logic (e.g., `ensure_product_groups` + `ensure_quantity_units`) and composes shared services/syncers.
- **GrocyGovernor** owns `InstanceMetadataRepository`, lazily builds `GrocyManager` objects, and serves as the gateway for any feature that spans instances.

### API Surface

The HTTP layer exposes Grocy routes that are fully implemented where noted in
`apps/api/docs/grocy_route_semantics.md`. Handlers stay thin and delegate to the
governor/manager/services for orchestration; routes that are not yet supported
remain future work.

| Route | Method | Purpose |
|-------|--------|---------|
| `/grocy/instances` | `GET` | List instances discovered from the manifest repository. |
| `/grocy/{instance_index}` | `GET` | Fetch metadata and health for a single instance. |
| `/grocy/{instance_index}/initialize` | `POST` | Seed product groups and quantity units from the universal manifest. |
| `/grocy/{instance_index}/sync` | `POST` | Run all available sync routines (future). |
| `/grocy/{instance_index}/metadata` | `PUT` | Update connection metadata through the governor. |
| `/grocy/{instance_index}/actions/move-product` | `POST` | Coordinate cross-instance product transfers. |
| `/grocy/{instance_index}/events` | `GET` | Retrieve recent governance/audit events. |
| `/grocy/{instance_index}/products` | `GET` | Return Grocy’s product catalog enriched with latest stock quantity, last stock update timestamps, and product group names. Append `?force_refresh=true` to invalidate the instance caches before responding. |
| `/grocy/{instance_index}/products/{product_id}` | `GET` | Fetch a single product with freshly pulled stock entries so dashboards can reconcile just the affected row after a mutation. |
| `/grocy/{instance_index}/products/{product_id}/inventory` | `POST` | Submit inventory corrections (new amount, defaulted best-before date, and location). |
| `/grocy/{instance_index}/products/{product_id}/purchase` | `POST` | Record purchase entries that sync new stock amounts, locations, shopping locations, and unit pricing into Grocy. |
| `/grocy/{instance_index}/inventory` | `GET` | Summarize inventory for the instance (future). |
| `/grocy/{instance_index}/inventory/{product_sku}` | `GET` | Show product-level inventory details (future). |

Implemented route behavior (including shopping list and purchase defaults endpoints)
lives in `apps/api/docs/grocy_route_semantics.md`.

`/grocy/instances` returns non-sensitive metadata for every instance, including their
declared postal addresses, the live Grocy location list (cabinet/freezer definitions),
and the shopping-location/vendor roster fetched through the manager layer.

Routes never touch manifest files or metadata directly; they simply forward the requested instance id (and optional payloads) and translate the resulting domain objects into HTTP responses.

The dashboard’s “Refresh data” control calls `/{instance_index}/products?force_refresh=true`, which clears caches (products, groups, quantity units, and stock artifacts) for **only** that instance before the response is generated. Other instances keep their own caches warm, so operators can safely refresh a single site without disrupting the rest of the fleet.

### Route Design Guidelines

1. **Depend on the Governor**: import the shared governor singleton and call purpose-built methods (`ensure_product_groups`, `ensure_quantity_units`, future sync/move operations). If a capability is missing, add a method to the governor rather than re-implementing inside the route.
2. **Keep Routes Thin**: FastAPI handlers should only perform request validation, call `run_in_threadpool` for blocking work, and shape responses. All manifest lookups, metadata parsing, and Grocy-specific logic must live under `apps/api/src/core/grocy/`. The `/products` handler, for example, calls `GrocyManager.list_product_inventory()` which handles caching, stock reconciliation, and product-group lookups.
3. **Surface Domain Results**: Convert the governor’s return types into clear response models (`pydantic.BaseModel`) so downstream services understand what changed (e.g., created unit ids, sync summaries, errors).
4. **Centralize Errors**: Translate `MetadataNotFoundError` into HTTP 404 and treat manifest/other internal errors as 500s. Avoid custom error handling per route—create reusable exception types when new scenarios appear.

Following these rules keeps API layers dumb pipes and ensures all Grocy behaviour flows through a single governing authority.

### Structured Note Encoding

Grocy’s native `note` columns are free-form strings. To attach typed metadata (shipping costs, tax rates, etc.) without polluting user-facing notes, every mutation that includes metadata wraps the note text in a small JSON envelope:

```
kanomnom::{"v":1,"note":"Operator-facing text","attrs":{"kind":"purchase_entry","shipping_cost":5.25}}
```

- `kanomnom::` marks encoded payloads so the dashboard can distinguish them from plain text.
- `note` stores the human-readable message exactly as entered in the dashboard UI.
- `attrs` contains typed metadata. Each payload includes a `kind` field so the decoder can instantiate the right dataclass.

The encoder lives in `core/grocy/note_metadata.py`, alongside typed metadata classes (e.g. `PurchaseEntryNoteMetadata`) that validate numbers, strings, and character sets. Decoding happens when FastAPI serializes inventory responses: the API returns the plain note plus a `note_metadata` object (when the metadata kind is recognized) so the dashboard never has to parse raw JSON.

Current metadata kinds:

- `purchase_entry` — captures `shipping_cost`, `tax_rate`, and `brand` details for that buy.
- `inventory_correction` — records a `losses` array so every adjustment can capture multiple structured reasons plus short optional notes. Valid reasons today are `spoilage`, `breakage`, `overportion`, `theft`, `quality_reject`, `process_error`, and `other`, and duplicates are ignored to keep the payload concise.
- `product_description` — stores product-level `unit_conversions` so dashboards can convert between quantity units while keeping the human-facing description intact.

These metadata payloads are defined twice on purpose: FastAPI models live in `apps/api/src/models/grocy.py`, while the dashboard consumes mirrored TypeScript shapes in `apps/dashboard/src/lib/grocy/types.ts`. Whenever you add a field (or a new metadata kind), update both layers in the same change and refresh this document so server and client stay aligned.

Each metadata dataclass returns an empty dict when none of its attributes are populated. Routes only encode the Grocy note when both the human-facing text and the metadata payload contain meaningful information; if neither is present, the note field stays `null`. This prevents storing useless envelopes and keeps Grocy’s native UI clean.

### Design Considerations

1. **Single Source of Truth**: Grocy connectivity details flow from `apps/api/grocy_manifest/<instance>/metadata.yaml` plus `credentials.yaml` (default entry); the governor never caches credentials outside memory and can drop/reload managers when manifests change.
2. **Separation of Concerns**: HTTP transport (client), domain orchestration (manager/services), and system-wide governance (governor) remain isolated so we can test and extend them independently.
3. **Extensibility Hooks**: The governor exposes `available_instances()` and `manager_for()` today, but its constructor already accepts repositories, making it trivial to inject future persistence layers or policy engines. Typed Grocy response models (`apps/api/src/core/grocy/responses.py`) ensure future routes reuse strict, validated parsing logic for products, stock logs, locations, and product groups.

### Future Responsibilities

The governor will eventually evolve from a simple manager directory to a coordinating authority. Planned capabilities include:

- **Cross-Instance Workflows**: moving products or stock between sites, reconciling inventory, or orchestrating failover.
- **Global Sync Scheduling**: running background jobs that ensure manifests and live Grocy instances stay in agreement, emitting telemetry per instance.
- **Central State / Database**: maintaining authoritative metadata (beyond what fits in YAML) such as audit logs, product lineages, or orchestration queues.
- **Policy Enforcement**: deciding which instance is authoritative for a product group, mediating conflicts, or triggering approvals before destructive actions.

Until those features are implemented, the governor’s public contract stays narrow: *hand back the correct `GrocyManager` for a requested instance*. As new responsibilities arrive, they should be layered into the governor (or services it composes) so there remains a single place to reason about system-wide Grocy behavior.
