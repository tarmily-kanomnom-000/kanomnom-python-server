## Grocy Governance Architecture

This document explains how Grocy-related components are structured inside the Python server and what future responsibilities the **GrocyGovernor** is expected to assume.

### Current Structure

```
grocy_manifest/                # Source of truth on disk
src/core/grocy/
├── client.py                  # Low-level HTTP wrapper for Grocy
├── manager.py                 # Per-instance orchestration (quantity units today)
├── metadata.py                # Typed loader for metadata.yaml files
├── governor.py                # Governing entity that returns managers
├── models.py                  # Dataclasses for manifest payloads
├── services.py                # Domain services (quantity unit sync)
└── sync.py                    # Generic reconciliation engine
```

- **GrocyClient** performs authenticated REST calls and knows nothing about manifests or reconciliation rules.
- **GrocyManager** encapsulates per-instance business logic (e.g., `ensure_quantity_units`) and composes shared services/syncers.
- **GrocyGovernor** owns `InstanceMetadataRepository`, lazily builds `GrocyManager` objects, and serves as the gateway for any feature that spans instances.

### API Surface

The HTTP layer now exposes a scaffold of Grocy routes (see `src/api/routes/grocy/`). Each handler is intentionally thin and either delegates to the governor today (`/initialize`) or raises a `501` placeholder until the corresponding capability is built. Planned endpoints:

| Route | Method | Purpose |
|-------|--------|---------|
| `/grocy/instances` | `GET` | List instances discovered from the manifest repository. |
| `/grocy/{instance_index}` | `GET` | Fetch metadata and health for a single instance. |
| `/grocy/{instance_index}/initialize` | `POST` | Seed quantity units from the universal manifest. |
| `/grocy/{instance_index}/sync` | `POST` | Run all available sync routines (future). |
| `/grocy/{instance_index}/metadata` | `PUT` | Update connection metadata through the governor. |
| `/grocy/{instance_index}/actions/move-product` | `POST` | Coordinate cross-instance product transfers. |
| `/grocy/{instance_index}/events` | `GET` | Retrieve recent governance/audit events. |
| `/grocy/{instance_index}/products` | `GET` | Return Grocy’s product catalog enriched with latest stock quantity, last stock update timestamps, and product group names. |
| `/grocy/{instance_index}/inventory` | `GET` | Summarize inventory for the instance (future). |
| `/grocy/{instance_index}/inventory/{product_sku}` | `GET` | Show product-level inventory details (future). |

`/grocy/instances` now returns non-sensitive metadata for every instance, including their declared postal addresses and the live Grocy location list (cabinet/freezer definitions) fetched through the manager layer.

Routes never touch manifest files or metadata directly; they simply forward the requested instance id (and optional payloads) and translate the resulting domain objects into HTTP responses.

### Route Design Guidelines

1. **Depend on the Governor**: import the shared governor singleton and call purpose-built methods (`ensure_quantity_units`, future sync/move operations). If a capability is missing, add a method to the governor rather than re-implementing inside the route.
2. **Keep Routes Thin**: FastAPI handlers should only perform request validation, call `run_in_threadpool` for blocking work, and shape responses. All manifest lookups, metadata parsing, and Grocy-specific logic must live under `src/core/grocy/`. The `/products` handler, for example, calls `GrocyManager.list_product_inventory()` which handles caching, stock reconciliation, and product-group lookups.
3. **Surface Domain Results**: Convert the governor’s return types into clear response models (`pydantic.BaseModel`) so downstream services understand what changed (e.g., created unit ids, sync summaries, errors).
4. **Centralize Errors**: Translate `MetadataNotFoundError` into HTTP 404 and treat manifest/other internal errors as 500s. Avoid custom error handling per route—create reusable exception types when new scenarios appear.

Following these rules keeps API layers dumb pipes and ensures all Grocy behaviour flows through a single governing authority.

### Design Considerations

1. **Single Source of Truth**: All Grocy connectivity details flow from `grocy_manifest/<instance>/metadata.yaml`; the governor never caches credentials outside memory and can drop/reload managers when metadata changes.
2. **Separation of Concerns**: HTTP transport (client), domain orchestration (manager/services), and system-wide governance (governor) remain isolated so we can test and extend them independently.
3. **Extensibility Hooks**: The governor exposes `available_instances()` and `manager_for()` today, but its constructor already accepts repositories, making it trivial to inject future persistence layers or policy engines. Typed Grocy response models (`src/core/grocy/responses.py`) ensure future routes reuse strict, validated parsing logic for products, stock logs, locations, and product groups.

### Future Responsibilities

The governor will eventually evolve from a simple manager directory to a coordinating authority. Planned capabilities include:

- **Cross-Instance Workflows**: moving products or stock between sites, reconciling inventory, or orchestrating failover.
- **Global Sync Scheduling**: running background jobs that ensure manifests and live Grocy instances stay in agreement, emitting telemetry per instance.
- **Central State / Database**: maintaining authoritative metadata (beyond what fits in YAML) such as audit logs, product lineages, or orchestration queues.
- **Policy Enforcement**: deciding which instance is authoritative for a product group, mediating conflicts, or triggering approvals before destructive actions.

Until those features are implemented, the governor’s public contract stays narrow: *hand back the correct `GrocyManager` for a requested instance*. As new responsibilities arrive, they should be layered into the governor (or services it composes) so there remains a single place to reason about system-wide Grocy behavior.
