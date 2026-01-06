# Documentation Standards

How we keep documentation accurate, scoped, and useful across runtimes.

## Goals
- Stay current with code and behavior; no stale guidance.
- Be concise and purposeful—enough to unblock users and reviewers, no filler.
- Keep a single source of truth in the owning runtime; link out instead of duplicating.
- Capture intent and reasoning, not just surface mechanics.

## Where to Document
- **API runtime (`apps/api/`)**: endpoint contracts, semantics, and flows in `apps/api/docs/`. Pair major behavior changes with examples and expected responses.
- **Dashboard (`apps/dashboard/`)**: UI workflows, offline/queue behavior, and API proxy expectations in the dashboard README or route-specific docs under `src/app/` when necessary.
- **Shared manifests (`apps/api/grocy_manifest/`)**: schema notes, seed data expectations, and migration implications.
- **Repository-wide standards**: this file and `AGENTS.md`.
- **Incidentals / debugging**: short-lived notes in `/tmp` or `./.debug/`; convert to durable docs if they become repeatable knowledge.

## What to Capture When Adding or Changing Features
- **Purpose**: the problem and target behavior.
- **Surface area**: endpoints, routes, commands, data shapes, and feature flags touched.
- **Expectations**: inputs/outputs, error cases, retries, and idempotency.
- **User flows**: happy path plus key edge cases; include minimal examples.
- **Rollout/migration**: data migrations, backfills, config toggles, and compatibility notes.
- **Ownership**: point to the owning team/runtime and the canonical doc location.

## Level of Detail
- Document decisions and invariants; avoid narrating obvious code.
- Prefer small, scoped sections over long narratives.
- Use examples only when they clarify contracts or tricky behavior.

## Style and Structure
- Write in present tense and active voice.
- Use concise headings and bullet lists; keep paragraphs short.
- Link to code paths (`apps/...`) instead of duplicating snippets when possible.
- Note quirks and “why” in comments or nearby docs; keep “what/how” in code.

## When to Update
- Any feature addition, API change, or behavior adjustment that affects users, operators, or integrators.
- When modifying contracts, data shapes, error semantics, or background jobs.
- After migrations or seed data changes that affect manifests or dashboards.
- When retiring features—mark deprecations and removal timelines.

## Quick Checklist Before Merge
- [ ] Canonical doc updated in the owning runtime (API docs, dashboard README, manifest notes).
- [ ] Examples reflect current inputs/outputs and error behaviors.
- [ ] Migration/rollout instructions included or confirmed unnecessary.
- [ ] Links to related docs/code added; no duplicated content.
- [ ] Terminology and naming match the code.

## Examples: Good vs. Bad
- **Good (contract-focused):**
  - *API doc* — “`POST /items` accepts `name` (string), `quantity` (int ≥ 1), returns `id` (UUID). On duplicate name, responds `409` with `code: duplicate_item`.”
  - *Flow note* — “Dashboard queue: offline mutations persist to IndexedDB, replay in order on reconnect, stop on first 4xx. Users see a banner with last error.”
- **Bad (noise or missing intent):**
  - *Vague* — “Creates item; might fail.” (doesn’t define shape or errors)
  - *Narrative* — “We loop through items and push them to a list.” (restates code, no contract or rationale)
  - *Out of place* — API retry behavior documented only in dashboard README instead of API docs.

## Style Notes and Plans
- Docstrings: add when they clarify intent, invariants, side effects, or edge cases; keep them concise. Use Google-style sections (`Args`, `Returns`, `Raises`) so future tooling (e.g., Sphinx napoleon or linters) can parse consistently.
- Future docs site: planned to adopt Docusaurus to surface `docs/` and runtime-specific docs with navigation and link checks. Keep Markdown first; reserve MDX only when needed. Add the build/CI steps and publishing target when the integration starts.
