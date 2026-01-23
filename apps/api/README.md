# kanomnom API Runtime

This folder contains the FastAPI + Flet server as well as all Grocy governance tooling. It was previously the entire repository root; everything now lives under `apps/api/` so the monorepo can host additional runtimes without entangling toolchains.

## Layout

```
apps/api/
├── Dockerfile.*              # Service-specific container builds
├── grocy_manifest/           # Declarative Grocy instance metadata + universal config
├── medusa_manifest/          # Declarative Medusa instance metadata
├── nextcloud_manifest/       # Declarative Nextcloud CalDAV instance metadata
├── pyproject.toml            # Python dependencies for this runtime
├── src/                      # FastAPI app, pages, and shared libraries
├── tests/                    # Pytest suites
└── request_dumps/, scripts/  # Utility assets for debugging/integration
```

## Environment

Copy `.env.default` to `.env` inside this directory, then adjust variables for your Grocy instances and any other service dependencies. The root docker-compose files reference `apps/api/.env`, so running compose from the repository root will still apply the values.

Nextcloud CalDAV credentials and calendar metadata are documented in `apps/api/docs/nextcloud_integration.md`.

```
cp .env.default .env
```

## Development

Run the dev stack locally (PostgreSQL, FastAPI, etc.) via the root-level docker compose file (from repo root):

```bash
docker compose -f docker-compose-dev.yaml up
```

While the containers are running, the FastAPI server reloads on changes under `src/`. You can still run `uv run pytest` or `uv run fastapi dev src/app.py` directly if you prefer bare-metal development.

## Production Preview

Build and run the production stack locally (again from the repository root):

```bash
docker compose -f docker-compose-prod.yaml up -d --build
```

Shut everything down with the matching `docker compose ... down` command.

## Testing

```bash
uv run pytest
```

Add new tests under `tests/` alongside the modules they cover; favor integration tests when touching Grocy workflows to ensure the typed response models keep matching live payloads.
