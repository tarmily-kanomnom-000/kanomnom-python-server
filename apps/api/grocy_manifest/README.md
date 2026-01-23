## Overview

`apps/api/grocy_manifest/` is the central source of truth for bootstrapping and maintaining several Grocy instances. Each instance lives in its own subdirectory and a `universal/` folder provides shared configuration that should be present everywhere (currently quantity units and product groups).

```
apps/api/grocy_manifest/
├── 000000/                # instance-specific data + metadata
├── 000001/
└── universal/             # reusable configuration applied to all instances
```

## Instance Metadata

Each instance folder must contain a `metadata.yaml` file with connection details and a `credentials.yaml` file with the API key. The server uses the default entry and supports multiple credentials per instance.

```yaml
grocy_url: "http://grocy_home:80"
location_name: "Home"
location_types: ["Warehouse", "Factory"]
```

```yaml
credentials:
  - name: primary
    default: true
    api_key: "example-api-key"
```

Fields:
- `grocy_url`: full URL (including port) reachable from this tooling.
- `api_key` (credentials.yaml): API key created in Grocy (Settings → Users → API Keys).
- `location_name`: human readable label for dashboards.
- `location_types`: list of tags describing the physical site (warehouse/factory/retail, etc.).

## Universal Configuration

`apps/api/grocy_manifest/universal/` stores semantic definitions that are expected everywhere:

- `quantity_units.json`: unit definitions keyed by their names, no database ids.
- `product_groups.json`: product group definitions keyed by their names, no database ids.
- `quantity_unit_conversions.json`: universal unit conversion definitions (name-to-name) used to build the shared conversion graph.

The FastAPI Grocy route resolves each name to the actual ids returned by Grocy, ensuring inserts remain consistent even when Grocy assigns new identifiers.

## Automated Setup (API)

Hit the FastAPI route to apply the universal manifest to a specific instance:

```
POST /grocy/{instance_index}/initialize
```

The route:
1. Reads `metadata.yaml` for the target index via the `InstanceMetadataRepository`.
2. Loads the universal manifest definitions from disk.
3. Fetches existing product groups and quantity units from Grocy.
4. Creates only the missing ones, returning their identifiers.

Re-running it is safe—the route checks semantically (by entity name) before posting.

## Manual Prerequisites (per instance)

1. Create a new admin user and delete the default admin account.
2. Generate an API key named `kanomnom-python-server` (or match whatever you store in `credentials.yaml`).
3. Settings → Stock Settings → Common → *Decimal places allowed for amounts* → set to **6**.
4. Settings → Stock Settings → Purchase → enable *Show purchased date on purchase*.

After satisfying these requirements and filling `metadata.yaml` + `credentials.yaml`, call `POST /grocy/{instance_index}/initialize`.

## Future Work

- Metadata sync between instances (e.g., product energy values) with configurable authorities/oracles.
