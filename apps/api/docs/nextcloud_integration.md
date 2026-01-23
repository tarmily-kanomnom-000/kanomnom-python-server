# Nextcloud CalDAV Integration

Documentation standards: see `../../docs/DOCUMENTATION_STANDARDS.md`.

## Overview

The API runtime can create Nextcloud calendar events for Medusa-backed inquiries received through the Grist webhook. The flow is:

1. Grist inquiry webhook arrives.
2. Medusa order details are fetched for the inquiry order ID.
3. A CalDAV item is created in Nextcloud for the order (event or task).

## Authentication

Nextcloud CalDAV uses HTTP Basic authentication. Recommended setup:

- Create an App Password in Nextcloud (Settings -> Security -> App passwords).
- Use your Nextcloud username plus the generated app password.

## Instance Metadata

Nextcloud instances are defined under `apps/api/nextcloud_manifest/<instance_key>/metadata.yaml`.

Required fields:

```yaml
dav_url: "https://nextcloud.tarmily.com/remote.php/dav"
calendars:
  - name: "Ka-Nom Nom – Orders"
    description: "Customer order follow-ups"
    tags: ["orders", "task"]
  - name: "Ka-Nom Nom – Shifts"
    description: "Staffing schedule"
    tags: ["shifts"]
  - name: "Ka-Nom Nom – Production"
    description: "Production planning"
    tags: ["production"]
  - name: "Ka-Nom Nom – Store Hours & Pop-ups"
    description: "Store hours and pop-up events"
    tags: ["store_hours", "popups"]
  - name: "Ka-Nom Nom – Daily Ops"
    description: "Daily operations"
    tags: ["daily_ops"]
```

Credentials are stored alongside the instance metadata in `credentials.yaml`. The server uses the default entry and supports multiple credentials per instance:

```yaml
credentials:
  - name: primary
    default: true
    username: "your-username"
    password: "app-password"
```

## Environment Variables

- `NEXTCLOUD_DEFAULT_INSTANCE_KEY` (defaults to `000000` when unset)

## Event Semantics

## Item Semantics

- Item type: `VTODO` when the calendar is tagged with `task`, otherwise `VEVENT`.
- Summary: customer name when available, otherwise `Order Request`.
- Start time: `inquiry.date_needed_by` if present, otherwise `order.created_at`.
- Due/end time: start time + 15 minutes.
- Status: `NEEDS-ACTION` for tasks.
- Reminder: 1 day before due date for tasks (`TRIGGER:-P1D`).
- Description includes inquiry notes, contact details, and item list.
- Calendar tag used for orders: `orders`.
