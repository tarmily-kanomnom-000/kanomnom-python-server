# AGENTS.md — Coding Standards & Philosophy

This document defines how we write, refactor, and maintain code in agent-related repositories.  
It’s intentionally opinionated, designed for clarity, reliability, and maintainability.

---

## Project Snapshot

- `apps/` holds every runtime (FastAPI API, Next.js dashboard, background workers). Each runtime keeps its own toolchain and `src/` tree under `apps/<runtime>/`.
- `apps/api/` contains the FastAPI-based Python server. `src/api/` defines HTTP routes, `src/core/` houses Grocy-specific services/caches, and `src/models/` contains typed payloads exposed to clients.
- `apps/dashboard/` is the Next.js UI runtime. `src/app/` implements routes and API proxies, while `src/components/`, `src/hooks/`, `src/lib/`, `src/queries/`, and `src/utils/` organize reusable UI logic for Grocy features (inventory, purchases, etc.).
- `apps/api/grocy_manifest/` stores instance manifests plus shared universal definitions that seed Grocy instances.
- Shopping list docs: API contract at `apps/api/docs/shopping_list.md`; dashboard offline/queue notes in `apps/dashboard/README.md` under PWA section.
- Broader docs: see `SHOPPING_LIST_IMPLEMENTATION.md` for the implementation guide/plan; phase summaries under `SHOPPING_LIST_PHASE*`; API runtime README in `apps/api/README.md`; dashboard README in `apps/dashboard/README.md`.
- Core shopping list semantics (merge rules, locking, normalization): `apps/api/docs/shopping_list_core.md`.

Keep this mental map current whenever you add new modules or runtimes—future contributors rely on it to navigate quickly.

---

## 0) TL;DR Principles

- **DRY** first – centralize shared logic.
- **Use proven libraries** instead of re-inventing.
- **Type everything.**
- **Python only:** avoid default function args; use configuration instead.
- **Abstraction:** only if it reduces duplication, centralizes logic, or manages cohesive state.
- **Design for N:** accept iterables/collections even when N=1 initially.
- **Refactor aggressively** and remove dead code.
- **Keep modules small and scoped.**
- **Single source of truth for state.**
- **Comments should explain *why*, not *what*.**
- **Build for debuggability; fail fast and loudly.**
- **Preserve originals when modifying complex systems**.
- **Before merging:** re-check logic, semantics, and naming.

---

## 1) DRY & Use Battle-Tested Libraries

**Policy:** Don’t re-implement existing, well-tested functionality.

**Examples (Python):**
- Caching → `functools.lru_cache`, `cachetools`
- Retries → `tenacity`
- Timing → `time.perf_counter()` with a context manager
- Parsing → `pydantic` or `dataclasses`
- CLI → `typer` / `click`

```python
from functools import lru_cache

@lru_cache(maxsize=256)
def get_user(uid: str) -> dict: ...
```

Avoid hand-rolled caches, retry loops, or timers.

---

## 2) Types Are Mandatory

**All** public and internal functions, class attributes, and module interfaces require type hints.

```python
def score(text: str, weights: dict[str, float]) -> float: ...
```

**TypeScript:** `strict: true` and never `any`.

---

## 3) Python: No Default Function Arguments

**Policy:** Defaults belong in configuration, not signatures.

```python
from dataclasses import dataclass

@dataclass
class RankerConfig:
    top_k: int = 50
    threshold: float = 0.7

def rank(items: list[str], cfg: RankerConfig) -> list[str]:
    ...
```

---

## 4) Abstraction: Only When It Earns Its Keep

Add abstractions only if they:
1. Reduce duplication  
2. Centralize logic  
3. Manage cohesive state  

**Rule:** If removing an abstraction simplifies code without losing clarity, delete it.

---

## 5) Refactor Ruthlessly (and Preserve Originals)

### 5.1 Removing Redundancy & Legacy
- Identify duplicates and merge them.  
- Delete feature flags and code paths that are fully superseded.  
- API compatibility is nice, but not mandatory if legacy design is worse.

### 5.2 Preserving the Original File During Complex Changes
When modifying a **complex system or critical module**, **never overwrite the original file directly**.  
Instead:
1. **Rename the original** with a `_original` suffix (e.g., `agent_core_original.py`).  
2. **Create a new version** (`agent_core.py`) to apply your modifications.  
3. Use the `_original` file as a **functional reference** to validate that nothing breaks.  
4. Once verified, **the original will be removed by me** (the maintainer) after confirming all functionality is preserved or improved.

**Why:**  
During large-scale changes, regressions are easy to introduce. Keeping a working reference makes debugging faster and prevents permanent loss of stable logic.

---

## 6) Design for N: Build Scalable APIs from the Start

**Policy:** When designing functions or APIs, default to accepting collections (lists, iterables) even if the initial use case only needs one item.

**Why:**
Many features start with `N = 1` but inevitably grow to require batch operations. Retrofitting a single-item API to handle multiple items often requires breaking changes, duplicated endpoints, or awkward wrapper functions.

**When to apply:**
- Functions that operate on domain entities (products, users, transactions, etc.)
- Operations that could logically be batched (database queries, API calls, validations)
- Any function where you can imagine "do this for multiple items" being a future requirement

**When to skip:**
- Pure utility functions with no domain context
- Operations that are inherently singular (e.g., "get current user session")
- Cases where batching would complicate the logic without clear benefit

**Examples:**

```python
# ✅ Good: Designed for N from the start
def update_product_prices(
    products: list[ProductUpdate],
    cfg: UpdateConfig
) -> list[UpdateResult]:
    """Update prices for one or more products."""
    return [_update_single(p, cfg) for p in products]

# Can be called with one item initially
update_product_prices([single_product], cfg)

# Scales naturally when needed
update_product_prices(many_products, cfg)
```

```python
# 🚫 Avoid: Single-item API that will need retrofitting
def update_product_price(product: ProductUpdate) -> UpdateResult:
    """Update price for a single product."""
    ...

# Later requires either:
# - A new bulk endpoint: update_product_prices_bulk(...)
# - Awkward loops in calling code
# - Breaking changes to accept list[ProductUpdate]
```

**Key insight:** Starting with an iterable type costs almost nothing but saves significant refactoring later. When in doubt, design for N.

---

## 7) File & Module Scope

Files should represent one logical area. Split when:
- LOC > ~400–600 and multiple domains coexist.  
- Test names start to become ambiguous.  

---

## 8) Single Source of Truth for State

Centralize state management — no scattered globals or shadow copies.

```python
class SessionState:
    \"\"\"Only way to read/write session token.\"\"\"
    def set_token(self, token: str) -> None: ...
    def token(self) -> str | None: ...
```

---

## 9) Comments vs. Names

- Use names to describe *what* and *how*.  
- Use comments only for *why* or *data quirks*.

```python
# Vendor omits 'cost' for discontinued SKUs → treat as 0.
def normalize_cost(raw: dict[str, str]) -> float: ...
```

---

## 10) Debuggable by Design

Assume first runs are wrong. Add logging, timing, and observability hooks.

```python
log.info("loaded_index", extra={"path": path, "ms": elapsed_ms})
```

Artifacts (snapshots, dumps) may go to `/tmp` or `./.debug/` as appropriate.

---

## 11) Fail Fast (No Silent Graceful Fallbacks)

Raise early and clearly unless explicitly required.

```python
if not os.path.exists(cfg.model_path):
    raise FileNotFoundError(f"Missing model: {cfg.model_path}")
```

---

## 12) Keep Names, Docs, and Semantics in Sync

When refactoring:
- Update function/class/file names.  
- Refresh docstrings and comments.  
- Fix tests and usage examples.  
- Provide a short migration note if public APIs change.

---

## 13) Abstraction Level Checklist

Ask before introducing new layers:
- Does it reduce duplication?  
- Does it centralize logic or state?  
- Does it clarify intent?  
- Would removing it make code simpler without loss?  
- Is it sized right (not bloated or trivial)?  

---

## 14) Composite Example

**Before**
```python
def normalize_a(...): ...
def normalize_b(...): ...
```

**After**
```python
def normalize(doc: dict[str, str]) -> NormalizedDoc:
    ...
```

---

## 15) Pre-Merge Checklist (Super Triple-Check)

- [ ] Meets requested requirements  
- [ ] Logic verified against expected behavior  
- [ ] Full type coverage  
- [ ] No redundant or dead code  
- [ ] Abstractions justified  
- [ ] Single source of truth enforced  
- [ ] Names/docs accurate  
- [ ] Debug/trace hooks present where useful  
- [ ] Fails loudly and clearly  
- [ ] Complex changes follow `_original` preservation rule  
- [ ] Tests updated and pass  

---

## 16) Quick Do / Don't Table

| ✅ Do | 🚫 Don't |
|------|-----------|
| Centralize shared logic and state | Re-implement common utilities |
| Use libraries for standard tasks | Add pointless wrapper functions |
| Keep all code typed | Hide defaults in function args |
| Design APIs to accept N items from start | Build single-item APIs that need retrofitting |
| Refactor and delete legacy | Maintain parallel state copies |
| Add debugging/logging hooks | Comment the obvious |
| Preserve `_original` for complex edits | Overwrite critical systems blindly |
| Fail fast and clearly | Gracefully fail silently |

---

**In summary:**  
Write code that’s minimal, typed, central, observable, and easy to reason about.  
When in doubt, simplify — and when modifying complex systems, **clone before cutting**.
