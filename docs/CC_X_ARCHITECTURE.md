# CC X — Architecture Source of Truth

**Product:** CC X (Clarity Console X) · `TradingAI_Bot`  
**Version:** 9.0.0 (`src/core/version.py`)  
**Last verified:** 2026-08-25 (code paths cited below)

Work tracking → [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md) · Ops → [`CC_X_PRODUCTION_READINESS.md`](./CC_X_PRODUCTION_READINESS.md) · ADRs → [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md)

> Architecture facts only — no roadmap, scores, or opinions.

---

## Runtime topology

```
Browser (Alpine.js SPA — src/api/templates/index.html, cc-app.js)
    ↓
_cc_instant.py :8000  →  proxy  →  FastAPI uvicorn :8001
    ↓
src/api/routers/*  (domain HTTP)
    ↓
src/services/*     (orchestration, contracts, truth model)
src/engines/*      (regime, signals, council, scanner)
    ↓
External: IBKR (ibkr_service.py), yfinance/Polygon, Discord/Telegram, optional LLM
```

| Layer        | Location                                   | Role                                                     |
| ------------ | ------------------------------------------ | -------------------------------------------------------- |
| Instant boot | `_cc_instant.py`                           | Sub-second shell; proxies API; gzip dashboard cache      |
| API          | `src/api/routers/` (~61 routers)           | HTTP surfaces per tab/domain                             |
| Services     | `src/services/`                            | Authority contracts, decision truth, board, dossier, ops |
| Engines      | `src/engines/`                             | Regime routing, signal generation, opportunity scan      |
| Scheduler    | `src/scheduler/main.py`                    | Premarket / intraday / EOD jobs (US/Eastern)             |
| UI           | `index.html`, `cc-app.js`, `cc-helpers.js` | Alpine.js operator dashboard                             |

---

## Engine boundaries (six logical engines)

Pages (Dashboard, Playbook, Discovery, Portfolio, Dossier) are **views** of shared models. Internal ownership:

| Engine                       | Primary modules                                                                                           | Deploy authority?                       |
| ---------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **Knowledge**                | `alpha_object.py` (schema), dossier assembly (`symbol_dossier.py`, `live_dossier.py`)                     | No — `research_only`                    |
| **Research**                 | `opportunity_scanner.py`, `validation_lab.py`, `cost_adjusted_ranker.py`, `opportunity_intelligence.py`   | No — rank ≠ permission                  |
| **Decision**                 | `decision_truth_model.py`, `operator_state_contract.py`, `decision_board_service.py`, `expert_council.py` | **Only layer that may open deploy**     |
| **Portfolio**                | `portfolio_decision_console.py`, `portfolio_fit.py`, `strategy_allocator.py`, `portfolio_risk_cockpit.py` | Sizing only when gates open             |
| **Execution**                | `execution_readiness.py`, `slippage_gate_service.py`, `ibkr_service.py`, `execution_analytics.py`         | Handoff when gates + broker READY       |
| **Intelligence**             | _not implemented_ (planned: platform IQ metrics)                                                          | No — advisory only                      |
| **Learning** (cross-cutting) | `learning_loop.py`, `self_learning.py`, `feature_ic.py`, `decision_persistence.py`                        | Advisory only; never auto-applies rules |

---

## Canonical objects

### InvestmentObject — decision-layer SSOT

- **File:** `src/core/investment_object.py` (Pydantic)
- **Purpose:** Structured payload for Knowledge → Research → Decision → Portfolio → Execution → Learning
- **Extends:** concepts from `engines/decision_object.py`, `TradeBrief` / `EdgeModel` (`core/models.py`)
- **Authority defaults:** `authority=research_only`, `may_authorize_deploy=false`
- **Rule (enforced in schema docs + tests):** only `decision_truth_model.py` + council + `operator_state_contract.py` may set `deploy_eligible=true`
- **Consumer status:** schema exists; legacy rank paths still primary on Playbook/Today

### AlphaObject — knowledge-layer memory

- **File:** `src/core/alpha_object.py` (Pydantic)
- **Purpose:** Permanent hypothesis → evidence → outcome → lessons archive
- **Authority:** always `research_only`; `may_authorize_deploy` always false
- **Lifecycle stages:** HYPOTHESIS → … → CLOSED → ARCHIVED
- **Consumer status:** schema only; factory birth not wired

### RegimeState — regime SSOT

- **File:** `src/engines/regime_router.py` (`RegimeState` dataclass)
- **Consumed by:** AutoTradingEngine, SignalEngine, API, dashboard, bots
- **Outputs:** regime labels, probabilities, entropy, `should_trade`, `no_trade_reason`

### Decision board block — cross-surface deploy truth

- **File:** `src/services/decision_board_service.py`
- **Function:** `build_decision_board()` composes `system_state`, `deploy_authority`, regime, gate reasons, BDR summary
- **Wired in:**
    - `src/api/routers/decision.py` — Today / board endpoint
    - `src/api/routers/playbook.py` — `attach_decision_board()`
    - `src/api/routers/cc_header.py` — header polling
- **Uses:** `operator_state_contract.attach_system_state`, `decision_truth_model` (no gate weakening)

---

## Authority model

Enforcement modules: `operator_state_contract.py`, `decision_truth_model.py`, `surface_authority.py`.

### Surface authority map (`surface_authority.py` → `TAB_SURFACE_MAP`)

| Tab / surface                                         | Default authority   | May deploy?                              |
| ----------------------------------------------------- | ------------------- | ---------------------------------------- |
| `today` (Dashboard)                                   | `deploy_authority`  | When `deploy_open`                       |
| `playbook`                                            | `deploy_authority`  | When `deploy_open`                       |
| `portfolio`                                           | `deploy_authority`  | Sizing when gates open                   |
| `dossier`                                             | `research_only`     | Confirm-only; no standalone handoff      |
| `discovery`, `scanners`                               | `research_only`     | Never                                    |
| `flow`                                                | `confirmation_only` | Never standalone                         |
| `btlab`, `reports`, `strategy-lab`, `shadow`, `agent` | `research_only`     | Never                                    |
| `guide`                                               | `suspended`         | Guide mode — decision surfaces suspended |
| `ops`                                                 | `ops_probe`         | Diagnostic only                          |

### SystemState (`build_system_state` in `operator_state_contract.py`)

Key fields consumed by UI and API:

- `deploy_open` — capital may be sized / reviewed for deploy
- `authority` — `deploy` | `monitor_only` | `research_only`
- `tradeability` — WAIT / NO_TRADE / TRADE labels from regime
- `fallback_mode`, `data_freshness`, broker/engine flags

### Binding deploy gates (any active → deploy closed)

| Gate                                                         | Source                 |
| ------------------------------------------------------------ | ---------------------- |
| `tradeability` = WAIT or NO_TRADE                            | Regime / board         |
| `should_trade` = false                                       | Regime                 |
| `decision_authority.gates_active` = true                     | Truth model            |
| Data STALE / CRITICAL                                        | Freshness contract     |
| `fallback_mode`                                              | Brief / cache fallback |
| Broker OFFLINE / ENGINE_OFF / EXEC_BLOCKED / HANDOFF_BLOCKED | Ops + IBKR state       |

### Playbook ranking rules (`operator_state_contract.py`)

- AVOID / NO_TRADE / BLOCKED → never in monitor ranking
- Monitor ranking = watchQualified + nearMiss (max ~12)
- `structural_valid_for_monitor()` rejects hard_reject rows

### Research vs deploy separation

- `surface_authority.py`: research surfaces carry `research_only` or `confirmation_only`
- `opportunity_quality.py`: **rank ≠ quality ≠ authority** — quality tiers inform monitor priority only
- `decision_truth_model.py`: `TRADE_RR_THRESHOLD = 2.5` (static; no auto-loosen)
- ML / self-learning: advisory only; kill switch default ON; min sample floors in tests

### Cache / authority interaction (2026-08-25)

- `deploy_open` is **recomputed on read** for cached scan bodies — never served stale (`decision.py`)
- Regime errors fail closed to WAIT (commit `8b51620`)

---

## Data flow (deploy path)

```
RegimeRouter (RegimeState)
    → AutoTradingEngine / brief assembly
    → decision_truth_model (TRADE bar, council validation)
    → operator_state_contract (SystemState, PageCapability)
    → decision_board_service.build_decision_board()
    → API: /api/v7/today, playbook ranked, cc-header
    → UI: Mission Brief panel, deploy strip, Playbook cards (display-only)
    → execution_readiness + ibkr_service (human-approved handoff)
    → closed_trades.jsonl → learning_loop (advisory)
```

Research-only path (Discovery / Dossier / Flow) feeds scanner and dossier payloads with `may_authorize_deploy: false`; no bypass of page gate.

---

## Key service index

| Domain              | Modules                                                                         |
| ------------------- | ------------------------------------------------------------------------------- |
| Authority           | `operator_state_contract.py`, `decision_truth_model.py`, `surface_authority.py` |
| Decision board      | `decision_board_service.py`, `bdr_operator_summary.py`, `decision_hub.py`       |
| Opportunity quality | `opportunity_quality.py`, `decision_quality_naval.py`                           |
| Regime              | `regime_router.py`, `regime_service.py`, `macro_regime_engine.py`               |
| Scanner / rank      | `opportunity_scanner.py`, `cost_adjusted_ranker.py`, `playbook.py` router       |
| Portfolio           | `portfolio_decision_console.py`, `portfolio_fit.py`, `risk_limits.py`           |
| Execution           | `execution_readiness.py`, `ibkr_service.py`, `slippage_gate_service.py`         |
| Learning            | `learning_loop.py`, `self_learning.py`, `decision_persistence.py`               |
| Notifications       | `telegram.py`, `opportunity_telegram_alerts.py`, `discord_dispatch.py`          |
| Canonical schemas   | `investment_object.py`, `alpha_object.py`, `engines/decision_object.py`         |

---

## Test anchors (authority regression)

| Test file                                      | Guards                                        |
| ---------------------------------------------- | --------------------------------------------- |
| `tests/test_operator_state_contract.py`        | SystemState, PageCapability, monitor validity |
| `tests/test_decision_board_service.py`         | Board payload consistency                     |
| `tests/test_decision_board_authority_cache.py` | No stale `deploy_open` on cache read          |
| `tests/test_quant_authority_boundaries.py`     | Research ≠ deploy                             |
| `tests/test_vnext_truthful_surfaces.py`        | Surface truth labels                          |
| `tests/test_opportunity_quality.py`            | Quality ≠ authority                           |
| `scripts/verify_10_10.sh`                      | CI authority cluster                          |

---

## Related documents

| Doc                                                                            | Purpose                                  |
| ------------------------------------------------------------------------------ | ---------------------------------------- |
| [`archive/CC_CONSOLIDATED_BRIEFING.md`](./archive/CC_CONSOLIDATED_BRIEFING.md) | Operator-facing authority narrative (§2) |
| [`CC_X_ENGINEERING_BACKLOG.md`](./CC_X_ENGINEERING_BACKLOG.md)                 | All planned work                         |
| [`CC_X_PRODUCTION_READINESS.md`](./CC_X_PRODUCTION_READINESS.md)               | Deploy / soak / chaos                    |
| [`CC_X_DECISION_LOG.md`](./CC_X_DECISION_LOG.md)                               | ADRs                                     |
