# Medusa Integration

## Overview

The API runtime integrates with Medusa using admin authentication at:

`POST /auth/user/emailpass`

The response returns a JWT token that is cached and used for subsequent admin API requests.

## Instance Metadata

Medusa instances are defined under `apps/api/medusa_manifest/<instance_key>/metadata.yaml`.

Required fields:

```yaml
medusa_url: "https://medusa.example.com"
```

Credentials are stored alongside the instance metadata in `credentials.yaml`. The server uses the default entry and supports multiple credentials per instance:

```yaml
credentials:
  - name: primary
    default: true
    admin_email: "admin@example.com"
    admin_password: "your-password"
```

## Environment Variables

- `MEDUSA_DEFAULT_INSTANCE_KEY` (defaults to `000000` when unset)

## Runtime Routes (API)

- `GET /medusa/instances` - list configured Medusa instances
- `GET /medusa/instances/{instance_key}/auth/verify` - validate authentication and refresh token if needed
