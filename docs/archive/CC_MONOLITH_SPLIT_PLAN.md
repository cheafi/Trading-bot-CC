# CC · Clarity Console — Monolith Split Plan

**Scope:** `src/api/templates/index.html` (~13k lines, single Alpine `x-data` root)  
**Goal:** Reduce merge risk and review fatigue without breaking instant-degraded or authority wiring.

---

## Phase 1 — Extract shared helpers (low risk)

| Step | Deliverable                                               | Notes                                                                     |
| ---- | --------------------------------------------------------- | ------------------------------------------------------------------------- |
| 1.1  | `src/api/static/cc-helpers.js`                            | Pure functions: warmup status, upgrade queue preview (started 2026-06-02) |
| 1.2  | `<script src="/static/cc-helpers.js">` before Alpine boot | Delegate `warmupStatusLine()` / queue to `CCHelpers.*` when wired         |
| 1.3  | Mirror copy in `fetch_surface_state.py`                   | Pytest parity (`test_warmup_ux.py`, `test_ops_recovery_guide.py`)         |

**Do not extract** ops degraded tables until Phase 2 — duplicated with Python `ops_degraded_copy` by design.

---

## Phase 2 — Tab partials (server-side)

| Step | Deliverable                                        | Notes                                                  |
| ---- | -------------------------------------------------- | ------------------------------------------------------ |
| 2.1  | `src/api/templates/cc/partials/guide.html`         | Guide-only markup (no data contract)                   |
| 2.2  | `cc/partials/deploy_surfaces.html`                 | Dashboard + Playbook shared card chrome                |
| 2.3  | `cc/partials/ops.html`                             | Ops console + recovery runbook                         |
| 2.4  | Jinja `{% include %}` from slim `index.html` shell | Keep one Alpine root; partials are HTML fragments only |

**Gate:** Each partial must pass existing integrity tests (`test_*_surface_integrity.py`) unchanged.

---

## Phase 3 — Build step (optional)

| Step | Deliverable                                                   | Notes                                      |
| ---- | ------------------------------------------------------------- | ------------------------------------------ |
| 3.1  | `scripts/build-cc-template.mjs`                               | Concat partials + minify inline CSS blocks |
| 3.2  | CI check: built `index.html` matches committed or auto-commit | Prevents drift                             |
| 3.3  | Source maps for Ops/debug only                                | Not required for production                |

---

## Out of scope (this plan)

- Splitting FastAPI routers (already modular)
- Moving ranked authority off server (`finalize_ranked_payload_authority` stays backend)
- Full Vite/React rewrite

---

## Success criteria

- No regression in §3–§8 pytest bundle (139+ tests)
- Playwright Phase E matrix green when enabled
- `index.html` shell &lt; 3k lines; largest partial &lt; 4k lines
