## Grocy Planned Routes

This document captures future Grocy governance endpoints so the ideas stay visible
without polluting the FastAPI router or generated OpenAPI schema. Each entry can
be promoted to a real route once its design and dependencies stabilize.

### Actions

| Method | Path | Summary | Detail |
| --- | --- | --- | --- |
| POST | `/{instance_index}/actions/move-product` | Coordinate moving a product between Grocy instances. | Will orchestrate product lookups, quantity holds, and stock adjustments between the source and destination governors so an operator can move a product in a single request. |

### Events

| Method | Path | Summary | Detail |
| --- | --- | --- | --- |
| GET | `/{instance_index}/events` | Return recent governance events for an instance. | Exposes recent lifecycle, synchronization, and automation events so operators can audit what happened to a Grocy instance without inspecting the raw manifests. |

### Inventory

| Method | Path | Summary | Detail |
| --- | --- | --- | --- |
| GET | `/{instance_index}/inventory` | Return summarized inventory data for the instance. | Aggregates product groups, total stock, and freshness signals so the UI can provide a quick status view before drilling into a specific product. |
| GET | `/{instance_index}/inventory/{product_sku}` | Return detailed inventory information for a specific product. | Surfaces batch-level quantities, upcoming expirations, and movement history to power proactive restocking flows. |

### Lifecycle

| Method | Path | Summary | Detail |
| --- | --- | --- | --- |
| POST | `/{instance_index}/sync` | Run all configured sync routines for the instance. | Intended to trigger every registered synchronization routine for a Grocy instance so state can be refreshed in a single operation rather than invoking each sync individually. |
