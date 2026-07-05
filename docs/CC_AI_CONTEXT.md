# CC · Clarity Console — Full AI Context

**Last updated:** 2026-06-04  
**Product score:** **9.9/10**  
**Repo:** `TradingAI_Bot-main`  
**Purpose:** Single copy-paste context for AI agents working on Clarity Console (CC). Latest truth only — no audit history.

---

## Executive summary

Clarity Console (CC) is an institutional PM decision console: regime-first layout, honest no-setup diagnosis, ranked playbook, single-stock dossier, IBKR execution readiness, and ops recovery — all governed by a strict **authority model** where **page gate beats card temptation**.

**What is shipped and stable:**

- **Authority model:** Deploy authority exists only on **Dashboard (Today)** and **Playbook**. All other surfaces are research, confirmation, ops-probe, or suspended (Guide). Intelligence signals (insider, 13F, events, strategy curves) are **research-only** and never authorize deploy alone.
- **Trust / recovery UX:** Copy-only recovery lines for loading, instant degraded, IBKR LOGIN→READY, engine OFF, stale market, route abort, WAIT-day mission panel. Python mirrors in `fetch_surface_state.py`; JS in `cc-helpers.js`.
- **Monolith partials:** `degraded_banners`, `ops_recovery_runbook`, `guide`, `deploy_surfaces` — injected via `scripts/build-cc-template.mjs` with CI drift gate.
- **E2E:** 21 Playwright specs in `tests/e2e/cc_operator_workflows.spec.ts`; CI job `cc-e2e`.
- **Pytest hang fix:** Ranked payload authority uses in-memory `ibkr_authority_gate_snapshot()` — no TCP probes during authority finalize.
- **Opportunity intelligence (foundation):** Four services + `/api/v7/intelligence/*` routes + dossier opp-intel strip — all research-only.
- **Instant server:** `_cc_instant.py` binds `:8000` instantly, spawns full API on `:8001`, serves degraded snapshots when backend not ready.

**Blockers to 10/10:**

1. `cc-e2e` green streak on **3+ consecutive main merges**
2. **Staging soak sign-off** ([CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md))
3. Optional: backend auto-heal beyond copy-only guidance; full monolith split (`ops.html`)

**Not present:** `docs/CC_QUANT_ALGO_UPGRADE_ROADMAP.md` does not exist. Quant/algo UI helpers exist in `cc-helpers.js` (`quantResearchBadge`, `costRankTag`, etc.) but no dedicated CC quant roadmap doc.

---

## Architecture & authority rules (non-negotiables)

### Five-level decision hierarchy

Defined in `src/services/decision_hierarchy.py`:

1. **Page / regime gate** — blocks or permits all deploy surfaces
2. **Board opportunity quality** — caps how many names earn sizing
3. **Setup evidence & thesis** — timing, R:R, thesis (not decorative)
4. **Execution & broker readiness** — IBKR + bracket + fill realism
5. **Portfolio fit & restraint** — book fit, turnover, crowding

**Rule:** Level 1 always wins. A green card on a research surface does not override a WAIT board.

### Authority constants

From `src/services/surface_authority.py`:

| Constant            | Meaning                                                   |
| ------------------- | --------------------------------------------------------- |
| `deploy_authority`  | Gated board may permit sizing                             |
| `pilot_only`        | Half size, stop required                                  |
| `research_only`     | Informs, does not authorize trades                        |
| `confirmation_only` | Must align with board + regime; downgrade-only for events |
| `ops_probe`         | Connectivity/runtime — not investable signal              |
| `blocked`           | Page gate or broker prevents deploy                       |
| `suspended`         | Guide mode — decision surfaces suspended                  |

### Deploy surfaces (only two)

- **Dashboard (`today`)** — board gate + today's decision
- **Playbook (`signals`)** — ranked opportunities when `board_mode` full

All other tabs: research, confirmation, ops, or suspended. **Never** add deploy chips (`show_decision_chips`) outside `dashboard_core` + `playbook_core`.

### Header / PM strip fix (2026-06)

**Root cause fixed:** Global `decisionHub.decision_strip` leaked deploy language onto every tab.

**Fix:** One surface owns header via `build_header_summary(surface_mode, context)` / Alpine `headerSummary()`. Deploy chips only on dashboard + playbook. See `docs/SURFACE_AUTHORITY_REFACTOR.md`.

### Fetch states

From `fetch_surface_state.py`: `loading`, `failed_fetch`, `stale`, `fallback`, `partial`, `probe_only`, `runtime_unknown`, `research_only`, `mock_only`, `no_data`, `not_authoritative`, `execution_blocked`.

Alpine uses `ccFetchJson()` + `ccFetch({normalize:true})` → `surfaceFetchHints[tab]`.

### Instant degraded path

`_cc_instant.py` serves shell on `:8000` immediately. When backend unavailable:

- Stamps `degraded`, `instant_degraded`, banner: _"INSTANT DEGRADED — snapshot only · not suitable for sizing or IBKR handoff"_
- Ranked/brief/dossier/intelligence paths return honest stubs — **no fake authority**
- `/health` exposes `mode`: `loading` → `full` (typically ≤ ~2 min)

### Opportunity intelligence ceilings

From `signal_provenance.py`: every intelligence envelope has `deploy_from_signal_alone: False`. News/events are **downgrade-only**. Strategy curves inform research sizing templates — never handoff permission alone.

---

## Surface map

### Primary nav (8 tabs + hidden)

| Tab id        | UI name              | Surface mode            | Default authority    | Deploy?                    |
| ------------- | -------------------- | ----------------------- | -------------------- | -------------------------- |
| `today`       | Overview / Dashboard | `dashboard_core`        | `deploy_authority`\* | **Yes** (when gates clear) |
| `signals`     | Playbook             | `playbook_core`         | `deploy_authority`\* | **Yes** (when gates clear) |
| `scanners`    | Discovery            | `discovery_research`    | `research_only`      | No                         |
| `stock-intel` | Dossier              | `dossier_research`      | `research_only`      | No                         |
| `portfolio`   | Portfolio            | `portfolio_manual`      | `deploy_authority`\* | Book construction only     |
| `funds`       | Funds                | `funds_research`        | `research_only`      | No                         |
| `flow`        | Flow                 | `flow_supporting`       | `confirmation_only`  | No                         |
| `ibkr`        | IBKR                 | `ibkr_execution`        | `ops_probe`          | Handoff when READY         |
| `ops`         | Ops                  | `ops_diagnostic`        | `ops_probe`          | No                         |
| `guide`       | Guide                | `guide_reference`       | `suspended`          | No                         |
| `rs`          | RS                   | `rs_supporting`         | `research_only`      | No                         |
| `notrade`     | Rejections           | `rejections_diagnostic` | `research_only`      | No                         |
| `btlab`       | Backtest Lab         | `backtest_research`     | `research_only`      | No                         |
| `command`     | Command              | (hidden nav)            | `research_only`      | No                         |

\*Effective authority downgrades to `blocked`, `research_only`, or `pilot_only` when tradeability is WAIT/NO_TRADE, IBKR blocked, zero deployable names, or compressed board mode.

### Tab id aliases

`signals` → playbook, `scanners` → discovery, `stock-intel` → dossier, `rejections` → notrade, `backtest` → btlab.

### Stable E2E / soak selectors (`data-cc`)

| Selector                            | Surface / purpose                  |
| ----------------------------------- | ---------------------------------- |
| `data-cc="data-contract-strip"`     | Authority contract strip           |
| `data-cc="instant-degraded-banner"` | Instant degraded banner            |
| `data-cc="warmup-context-strip"`    | Loading / WARMING strip            |
| `data-cc="deploy-status-strip"`     | IBKR + ENGINE pills (dashboard)    |
| `data-cc="today-mission-panel"`     | Mission focus, blockers, monitors  |
| `data-cc="playbook-surface"`        | Playbook body — no handoff on WAIT |
| `data-cc="dossier-surface"`         | Dossier research shell             |
| `data-cc="discovery-surface"`       | Discovery funnel                   |
| `data-cc="guide-surface"`           | Guide reference                    |
| `data-cc="ops-recovery-runbook"`    | Ops recovery card                  |
| `data-cc="market-strip-stale"`      | Stale market downgrade             |
| `data-cc="dossier-opp-intel"`       | Opportunity intelligence strip     |
| `data-cc="portfolio-stop-blockers"` | Portfolio stop blockers            |

Bottom nav: `data-cc-nav="today|signals|scanners|stock-intel|portfolio|funds|flow|guide"` (etc.).

---

## Key services & files

### Frontend shell

| File                                   | Role                                                                                   |
| -------------------------------------- | -------------------------------------------------------------------------------------- |
| `src/api/templates/index.html`         | ~13k-line Alpine monolith (single `x-data` root); partial markers `@cc-partial {name}` |
| `src/api/static/cc-helpers.js`         | Pure UI copy/helpers; loaded **before** Alpine; mirrors Python                         |
| `src/api/templates/cc/partials/*.html` | Extracted fragments (see Monolith split)                                               |
| `scripts/build-cc-template.mjs`        | Injects partials into committed `index.html`; `--check` in CI                          |

### Backend authority & state

| File                                   | Role                                                                       |
| -------------------------------------- | -------------------------------------------------------------------------- |
| `src/services/surface_authority.py`    | Tab→authority map, `resolve_authority()`, header summaries                 |
| `src/services/fetch_surface_state.py`  | Fetch states, recovery copy, `soak_confirmation_signals()`, monitor labels |
| `src/services/decision_truth_model.py` | `build_decision_authority()`, `finalize_ranked_payload_authority()`        |
| `src/services/decision_hierarchy.py`   | Five-level hierarchy evaluation                                            |
| `src/services/best_action.py`          | Best Action Now, `enrich_ranked_payload()`                                 |
| `src/services/today_insights.py`       | No-setup diagnosis, near-miss, monitor triggers                            |
| `src/services/signal_provenance.py`    | Intelligence authority ceilings                                            |
| `src/api/routers/cc_header.py`         | `?tab=` → `header_summary`                                                 |
| `src/api/routers/decision.py`          | `/api/v7/today` payload + surface_authority strip                          |

### IBKR & execution

| File                                  | Role                                                                      |
| ------------------------------------- | ------------------------------------------------------------------------- |
| `src/services/ibkr_service.py`        | Broker status; **`ibkr_authority_gate_snapshot()`** (memory-only, no TCP) |
| `src/services/ibkr_diagnosis.py`      | TCP probes — **must not** run during ranked authority finalize            |
| `src/services/execution_readiness.py` | Execution readiness on today payload                                      |

### Opportunity intelligence

| File                                          | Role                                                                      |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| `src/services/insider_tracker.py`             | Form 4 scoring (research_only)                                            |
| `src/services/institutional_13f.py`           | 13F change types (research_only)                                          |
| `src/services/event_noise_filter.py`          | Event clustering (confirmation_only / downgrade)                          |
| `src/services/strategy_curve_health.py`       | Walk-forward curve health (research_only)                                 |
| `src/api/routers/opportunity_intelligence.py` | `GET /api/v7/intelligence/{insider,institutional,events,strategy-health}` |

### Instant server

| File                                       | Role                                                                         |
| ------------------------------------------ | ---------------------------------------------------------------------------- |
| `_cc_instant.py`                           | Port 8000 instant shell; proxies to 8001; degraded stubs; stale lock reclaim |
| `data/market_overview_last_good.json`      | Last-good snapshot for instant degraded                                      |
| `data/cache/playbook_ranked_snapshot.json` | Ranked snapshot cache                                                        |

### Settings pattern (AGENTS.md)

When editing **SettingsView**: bind inputs to local `cachedState`, **not** live `useExtensionState()`. Save commits to `ContextProxy` source-of-truth.

---

## What's implemented (by area)

### Trust & authority

- Surface-specific header summaries — no cross-tab deploy chip leak
- Ranked payload authority on all row keys (`effective_action`, gates per opportunity/near_miss)
- Hang fix: authority finalize uses `ibkr_authority_gate_snapshot()` not `get_ibkr_service().status()`
- Evidence badges, score reconciliation, honest fallback/stale/mock labeling
- Five-level hierarchy wired into today payload
- Signal provenance envelopes on all intelligence routes

### Warmup & instant degraded

- `_cc_instant.py`: sub-second shell, background uvicorn on 8001, `/health` mode transitions
- Degraded banner precedence over warmup strip (no duplicate WARMING copy)
- `operatorLoadingSafeLine`, `loadingSessionRecoveryLine` — safe actions during loading
- Stale singleton lock reclaim on dead PID
- Instant degraded stubs for today, playbook, dossier, intelligence paths

### Recovery copy (JS ↔ Python parity)

| Signal             | JS helper                                                | Python mirror                        |
| ------------------ | -------------------------------------------------------- | ------------------------------------ |
| Long loading       | `loadingSessionRecoveryLine`, `operatorLoadingSafeLine`  | `operator_loading_safe_line`         |
| Route abort        | `routeAbortRecoveryHint`                                 | `route_abort_recovery_hint`          |
| Stale market       | `staleRefreshRecoveryLine`                               | `stale_refresh_recovery_line`        |
| Engine OFF         | `engineOffRecoveryLine`                                  | `engine_off_recovery_line`           |
| IBKR LOGIN         | `ibkrLoginToReadyHint`                                   | `ibkr_login_to_ready_hint`           |
| WAIT mission       | `todayMissionWaitSubtitle`, `todayMissionSafeUnlockHint` | same names snake_case                |
| Monitors vs deploy | `todayMissionMonitorsColumnHint`                         | `today_mission_monitors_column_hint` |
| Soak anchors       | `soakConfirmationSelectors()`                            | `soak_confirmation_signals()`        |

Playbook WAIT copy: _"gate context below (not deploy)"_ — unlock conditions are not deploy permission.

### E2E & CI

- **21 Playwright specs** — serial workers=1, 2 CI retries, 15s expect timeout
- Route-abort dossier + discovery in isolated describe block
- `data-cc-nav` tab clicks; shell attach wait; deploy-status-strip test
- CI `cc-e2e`: template `--check` then Playwright; junit + artifact upload on failure

### Monolith partials (Phase 2)

| Partial                     | Contents                            | Status   |
| --------------------------- | ----------------------------------- | -------- |
| `degraded_banners.html`     | Instant degraded + warmup strips    | Done     |
| `ops_recovery_runbook.html` | Ops recovery card                   | Done     |
| `guide.html`                | Guide tab body (~558 lines)         | Done     |
| `deploy_surfaces.html`      | Mission panel + deploy status strip | Done     |
| `ops.html`                  | Full ops console                    | **Next** |

Alpine root stays **single** `x-data` in shell. Jinja `{% include %}` deferred — instant serves built `index.html`.

### Dossier

- Core-only / CONFIRM ONLY on fetch failure
- Route-abort → research shell (E2E covered)
- `dosFetchErrorGrade()` → _"levels not live-confirmed"_
- Opportunity intel strip: `data-cc="dossier-opp-intel"`, RESEARCH ONLY badge, parallel fetch on load
- Peers table, options tab, narrative — see PM roadmap for depth gaps

### Playbook & Discovery

- Ranked board with authority gates; fallback rank / WATCH ONLY on WAIT
- No `Send to IBKR` on playbook surface when WAIT (E2E)
- Discovery funnel: research-only; route-abort → fallback funnel
- Near-miss monitors ≠ deploy; monitor trigger types include opportunity hints

### Dashboard / Today

- Best Action Now strip (capital stance, best trade/watch, next review)
- No-setup diagnosis breakdown (failed timing/R:R/execution/regime/score/data)
- Active sleeve / fund manager (gate_status, stance, mode, controls_capital)
- Equity curve spark + max drawdown on strip
- Mission panel: focus, monitors hint, safe/unlock, system blockers
- Deploy status strip: IBKR + ENGINE pills

### IBKR & Ops

- IBKR tab: LOGIN / OFFLINE / READY states; ops_probe authority
- Execution readiness panel on today payload
- Ops recovery runbook partial synced with Python `ops_recovery_guide()`
- Critical IBKR check failure → blocked authority on deploy surfaces

### Opportunity intelligence (shipped foundation)

- Four services + unit tests + router with API key dependency
- Dossier UI strip with mock/degraded badges via `CCHelpers.opportunityIntelligenceBadge`
- Monitor hooks: `OPPORTUNITY_MONITOR_TRIGGER_TYPES` in fetch_surface_state
- `_cc_instant.py` degraded handlers for intelligence paths

---

## Testing

### Playwright E2E (21 specs)

```bash
npm install --no-save @playwright/test@1.49.1
npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

**Config:** `playwright.config.ts` — webServer runs `_cc_instant.py`, 120s boot, `/health`, workers=1.

**Coverage highlights:** cc-helpers load, health mode, contract strip, banner precedence, warmup recovery, WAIT no green TRADE pills, playbook fallback/handoff, IBKR states, guide surface, mission panel, rejections shell, dossier core/abort, discovery funnel/abort, portfolio blockers, ops runbook/loading, market stale, deploy-status-strip.

### CI (`cc-e2e` job in `.github/workflows/ci.yml`)

1. `node scripts/build-cc-template.mjs --check`
2. `npx playwright test tests/e2e/cc_operator_workflows.spec.ts`
3. On failure: upload playwright report, junit, test-results

### Pytest canonical CC bundle (~194–199 tests)

Run after any CC authority, template, or recovery copy change:

```bash
pytest \
  tests/test_surface_authority_header.py \
  tests/test_fetch_surface_state.py \
  tests/test_ui_render_integrity.py \
  tests/test_ui_render_safety.py \
  tests/test_decision_authority.py \
  tests/test_decision_truth_model.py \
  tests/test_fourth_pass_polish.py \
  tests/test_final_hardening.py \
  tests/test_stabilization_pass.py \
  tests/test_final_verification.py \
  tests/test_warmup_ux.py \
  tests/test_ops_recovery_guide.py \
  tests/test_dashboard_decision_integrity.py \
  tests/test_playbook_render_integrity.py \
  tests/test_playbook_funnel.py \
  tests/test_playbook_board_fallback.py \
  tests/test_dossier_instant_core.py \
  tests/test_dossier_fetch_state.py \
  tests/test_discovery_surface_integrity.py \
  tests/test_ops_surface_integrity.py \
  tests/test_guide_surface_authority.py \
  tests/test_feature_surface_integrity.py \
  tests/test_rejections_surface_integrity.py \
  tests/test_cc_instant_ibkr.py \
  tests/test_trading_intelligence_improvements.py \
  tests/test_workflow_integrity.py \
  tests/test_opportunity_intelligence.py \
  tests/test_insider_tracker.py \
  tests/test_institutional_13f.py \
  tests/test_event_noise_filter.py \
  tests/test_strategy_curve_health.py \
  -q
```

**Critical regression:** `test_finalize_ranked_payload_authority_completes_without_tcp_probe` — must complete < 2s with `probe_tcp_port` patched to fail.

**Template drift:**

```bash
node scripts/build-cc-template.mjs --check   # CI gate
node scripts/build-cc-template.mjs           # rebuild after partial edit
```

### Product verification (PM)

```bash
bash scripts/verify_10_10.sh   # includes /api/v7/today, /api/v7/stock-intel/{ticker}
```

---

## Operations

### Start server

```bash
python _cc_instant.py          # instant shell :8000, backend :8001
# Or full API directly on :8000 if not using instant path
```

**Ports:** Dashboard `:8000` (instant) → backend `:8001`. If stuck on loading > ~2 min, recovery copy mentions 8000→8001 restart.

**Dev skip backend:** `CC_INSTANT_NO_BACKEND=1`

### Staging soak checklist (condensed)

Full runbook: [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)

| #   | Scenario                  | Pass criteria                                                                          |
| --- | ------------------------- | -------------------------------------------------------------------------------------- |
| 1   | Cold start `mode=loading` | Shell loads; no green TRADE pills; safe-line mentions monitors/Guide/dossier core-only |
| 2   | loading → full            | Ranked/council load or honest fallback; contract strip on decision surfaces            |
| 3   | IBKR LOGIN→READY          | READY + bracket before handoff; no Send to IBKR on WAIT playbook                       |
| 4   | Engine OFF                | ENGINE OFF pill; precomputed board only                                                |
| 5   | Market stale              | `market-strip-stale` + refresh copy; no sizing on stale                                |
| 6   | Route abort               | Dossier CONFIRM ONLY; Discovery fallback funnel                                        |
| 7   | WAIT 30+ min              | Monitors hint; no new green TRADE; counters reconcile                                  |
| 8   | Ops runbook               | `[data-cc="ops-recovery-runbook"]` matches Python `ops_recovery_guide()`               |
| 9   | Soak signals              | Cross-check `soak_confirmation_signals()` vs visible UI                                |

**Sign-off table** in runbook — manual, required for 10/10.

---

## Roadmap forward

### Opportunity intelligence (medium / deep)

Roadmap: [CC_OPPORTUNITY_INTELLIGENCE_ROADMAP.md](./CC_OPPORTUNITY_INTELLIGENCE_ROADMAP.md)

| Horizon      | Items                                                                                                                                                                                                      |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Medium**   | Wire insider to live EDGAR behind flag; event-risk badge on Dashboard/Playbook (downgrade only); 13F on Funds tab; Strategy Curve Console on Backtest Lab; pass `opportunity_hints` from scanner near-miss |
| **Deep**     | Real-time news clustering + stale badges; 13F diff engine; insider cluster across tickers for Discovery; explicit downgrade reasons in decision_truth_model for tier-A negative events                     |
| **Optional** | Hidden "Intel" tab; push on insider_cluster (monitor alert only); crowded-exit sector monitor                                                                                                              |

### Quant / algo

No `CC_QUANT_ALGO_UPGRADE_ROADMAP.md`. Existing algo code lives under `src/algo/` (indicators, vcp_strategy — not fully validated/wired). CC UI has preliminary quant helpers in `cc-helpers.js` only. Any quant upgrade must preserve authority model: research surfaces only unless explicitly scoped to deploy surfaces with full gate stack.

### Product depth (PM roadmap — CC-relevant gaps)

From [PM_PRODUCT_ROADMAP_10_10.md](./PM_PRODUCT_ROADMAP_10_10.md):

| Priority | Gap                                                                                                                                | Status       |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| P0 core  | Best Action, no-setup, near-miss, active sleeve, curve/DD, IB readiness, monitor panel, evidence badges                            | **Done**     |
| P1       | Full playbook card schema in UI; Command tab best_action sync; sector rotation implication; trigger-based watchlist from near_miss | Partial      |
| P1       | Single-stock 10-layer dossier depth (fundamentals, options, events, confidence stack)                                              | Partial      |
| Postpone | Unlimited new tabs; AI as primary ranker; social/influencer main UI; auto bracket submit                                           | Do not build |

Related specs: [PLAYBOOK_10_10_SPEC.md](./PLAYBOOK_10_10_SPEC.md), [SINGLE_STOCK_COMMAND_CENTER.md](./SINGLE_STOCK_COMMAND_CENTER.md).

---

## Monolith split status

Plan: [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md)

| Phase | Item                                      | Status   |
| ----- | ----------------------------------------- | -------- |
| 1.1   | `cc-helpers.js` extracted                 | Done     |
| 1.3   | Python mirror in `fetch_surface_state.py` | Done     |
| 2.0   | `degraded_banners.html`                   | Done     |
| 2.0b  | `ops_recovery_runbook.html`               | Done     |
| 2.1   | `guide.html`                              | Done     |
| 2.2   | `deploy_surfaces.html`                    | Done     |
| 2.3   | `ops.html` full console                   | **Next** |
| 3.x   | Jinja includes (optional)                 | Deferred |

**Success criteria:** shell < 3k lines; largest partial < 4k; no pytest/E2E regression; CI `--check` green.

**Do not extract** ops degraded tables until Python `ops_degraded_copy` parity is automated.

**Out of scope:** Splitting FastAPI routers; moving ranked authority off server; Vite/React rewrite.

---

## Do / Don't rules for AI working on CC

### DO

- Preserve **page gate > card temptation** — deploy chips only on Dashboard + Playbook
- Bind recovery copy in **both** `cc-helpers.js` and `fetch_surface_state.py`
- Use stable selectors: `data-cc`, `data-cc-nav` for any new E2E-relevant markup
- Run `node scripts/build-cc-template.mjs --check` after partial edits; rebuild if needed
- Label intelligence **RESEARCH ONLY** or **MOCK ONLY** when stubbed/degraded
- Use `ibkr_authority_gate_snapshot()` for authority gates — never TCP probes in hot paths
- Keep Guide tab **suspended** — no decision language
- Treat near-miss / monitors as **watch queue**, not deploy queue
- Cross-check `decision_truth_model` before any card-level downgrade wiring
- SettingsView: use `cachedState` buffer until explicit Save (AGENTS.md)
- Minimize diff scope; match existing naming and patterns

### DON'T

- Don't add `may_authorize_deploy` or green TRADE badges on research surfaces (Dossier, Discovery, Funds, Guide)
- Don't wire inputs in SettingsView directly to live `useExtensionState()` (race conditions)
- Don't upgrade tradeability from insider cluster, 13F sponsorship, or strategy curve alone
- Don't call `get_ibkr_service().status()` / `probe_tcp_port()` during ranked authority finalize
- Don't duplicate WARMING copy when instant degraded banner is visible
- Don't imply deploy from playbook WAIT unlock conditions
- Don't hide mock data — expose `data_tier` and `degraded` in API + UI
- Don't split Alpine into multiple roots without explicit plan approval
- Don't add unlimited new nav tabs without PM sign-off
- Don't make AI the primary ranker or build influencer/social as main UI
- Don't auto bracket submit without IB + human confirmation path
- Don't commit secrets; use environment variables

---

## Blockers to 10/10

| Blocker                                | Owner action                                                 | Current state                        |
| -------------------------------------- | ------------------------------------------------------------ | ------------------------------------ |
| `cc-e2e` green streak (3+ main merges) | Monitor CI after merges                                      | Configured; streak not yet confirmed |
| Staging soak sign-off                  | Execute runbook §1–§9; fill sign-off table                   | Manual; not signed                   |
| Monolith: `ops.html` extract           | Phase 2.3 per split plan                                     | Open                                 |
| Backend auto-heal (optional)           | Child health retry in `_cc_instant.py` without trust erosion | Copy-only today                      |
| Jinja includes (optional)              | Phase 3 when instant path allows                             | Deferred                             |

**When 10/10:** CI streak + soak sign-off + no authority regressions → promote score. Authority model unchanged.

---

## Quick reference — canonical doc index

| Doc                                                                                | Use when                                        |
| ---------------------------------------------------------------------------------- | ----------------------------------------------- |
| **This file** (`CC_AI_CONTEXT.md`)                                                 | Full AI context — start here                    |
| [CC_README.md](./CC_README.md)                                                     | Doc index pointer                               |
| [CC_FINAL_VERIFICATION_REVIEW.md](./CC_FINAL_VERIFICATION_REVIEW.md)               | Latest pass details (hang fix, deploy_surfaces) |
| [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)                         | Staging checklist                               |
| [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md)                           | Partial extraction plan                         |
| [CC_OPPORTUNITY_INTELLIGENCE_ROADMAP.md](./CC_OPPORTUNITY_INTELLIGENCE_ROADMAP.md) | Intelligence features                           |
| [SURFACE_AUTHORITY_REFACTOR.md](./SURFACE_AUTHORITY_REFACTOR.md)                   | Header strip root cause + surface modes         |
| [PM_PRODUCT_ROADMAP_10_10.md](./PM_PRODUCT_ROADMAP_10_10.md)                       | Product depth gaps                              |

---

_Copy-paste this entire document to onboard an AI agent on Clarity Console. For surgical tasks, cite the section you need rather than the full file._
