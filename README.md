# kanomnom-platform

This repository now hosts multiple runtimes under a single roof. Each runtime lives in `apps/<name>/` with its own toolchain, dependencies, and deployment manifests. Shared documentation remains in `docs/`, and orchestrating scripts live at the repository root so you can start everything from one place.

## Dev

docker compose -f docker-compose-dev.yaml down && docker compose -f docker-compose-dev.yaml build && docker compose -f docker-compose-dev.yaml up

## Prod
docker compose -f docker-compose-prod.yaml down && sudo chown -R $USER:$USER . && chmod +x scripts/run-stack-prod.sh scripts/run-stack.sh && docker compose -f docker-compose-prod.yaml build --no-cache && docker compose -f docker-compose-prod.yaml up -d

## Directory Layout

```
apps/
  api/            # FastAPI + Flet server (current runtime)
docs/             # Shared design docs, specs, and runbooks
AGENTS.md         # Coding standards for every runtime
```

Add future runtimes by creating a new folder under `apps/` (`apps/dashboard`, `apps/bot`, etc.), keeping their dependencies self-contained just like the API.

## Running All Runtimes

Use the root `Makefile` or docker compose files so a single command can start every runtime that has been wired in:

```bash
make dev                        # currently starts only the API stack
# or
docker compose -f docker-compose-dev.yaml up
```

`docker-compose-dev.yaml` and `docker-compose-prod.yaml` live at the repository root and will eventually orchestrate every runtime. As new apps come online, extend those files (and the Make targets) so a single `make dev` keeps bringing everything up together. Each runtime also gets its own target—see `Makefile` for the latest list.

### Running API + Dashboard Without Docker

Hot reload dev loop:

```bash
./scripts/run-stack-dev.sh
```

Production-style run (no reload; dashboard build + start):

```bash
./scripts/run-stack-prod.sh
```

Prerequisites:

- Python deps installed via `uv` inside `apps/api`
- Node deps installed via your preferred package manager inside `apps/dashboard`
- `uv` plus either `pnpm` (preferred) or `npm` on your `PATH`
- Dashboard listens on `http://localhost:3000` (override via `DASHBOARD_PORT`)

Both scripts stream logs from the FastAPI service and dashboard, wire Ctrl+C to stop everything, and exit early if either process fails. The dev helper calls `fastapi dev` for hot reloads, while the prod helper uses `fastapi run` plus `pnpm|npm run build && run start` so you mirror the container entrypoints locally. Set `DASHBOARD_PORT` before running if you need a non-default dashboard port; the scripts pass the value to Next via `PORT` so you always get an explicit bind.

## Working on the API Runtime

FastAPI + Flet sources now live in `apps/api/`. To develop or deploy that service directly:

1. `cd apps/api`
2. Manage virtualenv/dependencies via `uv`, `pip`, etc. using the `pyproject.toml` in that folder.
3. Start the stack from the repository root using the shared docker-compose files:  
   - Dev: `docker compose -f docker-compose-dev.yaml up`  
   - Prod preview: `docker compose -f docker-compose-prod.yaml up -d --build`

Environment files (`apps/api/.env`, `apps/api/.env.default`) live next to the runtime; when you run docker compose from the root these files are referenced via the compose configuration.

## Adding Another Runtime

1. Create `apps/<runtime>/` with its own README, dependency files, and dev/prod start scripts.
2. Update the root `Makefile` so `make dev` launches the new runtime (or introduces a dedicated `make <runtime>-dev` target).
3. Document any shared contracts in `docs/` so other runtimes understand how to integrate.

This keeps runtimes isolated yet easy to run together with one top-level command.
