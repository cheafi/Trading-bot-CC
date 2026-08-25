# CC vNext — Institutional Alpha OS Master Review

**Document:** `docs/CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md`  
**Product:** CC (Clarity Console) · `TradingAI_Bot`  
**Version reviewed:** 9.0.0 (`src/core/version.py`)  
**Review date:** 2026-08-25  
**Branch context:** `cc/upgrade-regime-tracking`  
**Reviewers (personas):** Chief Architect · Quant Research · PM/COO · UX/Bloomberg Designer · Institutional Compliance  
**Method:** Full-repo read — prior `docs/CC_VNEXT_MASTER_REVIEW.md`, `docs/CC_CONSOLIDATED_BRIEFING.md`, authority contracts, 154 service modules, 100 engine modules, 61 API routers, 176 test files, Docker/scheduler/ops. Code-path citations only; no runtime pytest on host.

---

## Non-Negotiable Constraints (Hard Rules — Preserved Throughout)

This review **never** recommends auto-deploy, threshold auto-loosening, uncertainty hiding, fake confidence, or card-rank overrides of page gates. All recommendations assume:

| Principle                     | Current enforcement                                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Operator Decision OS**      | Daily flow: Dashboard → Playbook → Dossier → Portfolio → IBKR/Ops (`index.html` Guide Layer 1)               |
| **Page gate beats card rank** | `operator_state_contract.py` + Guide checklist; WAIT/NO_TRADE blocks deploy regardless of score              |
| **Research ≠ permission**     | Discovery/Flow/Funds/Agent/Shadow/Reports/Btlab = monitor/research only (`CC_CONSOLIDATED_BRIEFING.md` §2)   |
| **Threshold Governance**      | `decision_truth_model.py` TRADE_RR_THRESHOLD=2.5; brief-sourced rows capped at WATCH until council validates |
| **Alpha QA**                  | Probe vs runtime in `ops_operator_console.py`; funnel labels in `PLAYBOOK_FUNNEL_LAYER_DEFINITIONS`          |
| **Auditability**              | Self-learning audit log, Thompson/feature_ic JSON persistence, BDR from live state, `DecisionJournal` JSONL  |
| **EV after costs/risk**       | `risk_limits.py` SSOT; cost-adjusted ranker tests; no excitement-first ranking                               |
| **Human approval**            | Deploy requires operator action; IBKR handoff gated by `deploy_open` + broker ladder                         |
| **Risk-first**                | Circuit breakers, earnings blackout, sector caps in `risk_limits.py`; capacity/slippage downgrade-only       |

**Explicit prohibitions in all vNext work:** no auto-loosen thresholds; no ML multiplier without sample floor; no synthetic flow presented as live; no Discovery score implying deploy.

---

## 1. Executive Assessment

### Overall Platform Score: **7.0 / 10**

CC is an unusually disciplined **Operator Decision OS** for a single PM or small pod — authority contracts are executable code, not marketing copy. It is **not** yet a world-class institutional Alpha OS on data breadth, execution latency, or ML sample depth. The score reflects **decision governance ahead of data/alpha infrastructure**, which is the correct priority order for capital safety.

### Dimension Scores

| Dimension                   | Score | Rationale (this codebase)                                                                                                 |
| --------------------------- | ----: | ------------------------------------------------------------------------------------------------------------------------- |
| **Architecture**            |   6.5 | Strong service/router split emerging; `main.py` still 6,610 lines; dual-product (Discord + CC) cognitive load             |
| **Quant Intelligence**      |   6.5 | `decision_truth_model.py` (1,607 lines), `regime_router`, council pipeline, cost-adjusted edge; retail data limits depth  |
| **ML**                      |   5.5 | `self_learning.py`, `feature_ic.py`, `thompson_sizing.py` present; `min_sample_size=30`; Ops shows `insufficient_sample`  |
| **Learning**                |   6.0 | `learning_loop.py` + `DecisionJournal` JSONL; IBKR→closed_trades wiring partial; forward outcomes thin                    |
| **Portfolio**               |   6.5 | `portfolio_decision_console.py` (1,607 lines) allocator-grade copy; local-book vs broker truth honestly labeled           |
| **Risk**                    |   7.5 | `risk_limits.py` unified SSOT; drawdown sizer, circuit breakers; sector enforcement on quick-add incomplete               |
| **Opportunity Discovery**   |   7.0 | Sprint 114 `opportunity_scanner.py` Neal dual-engine; Discovery↔Playbook bridge incomplete                               |
| **Execution**               |   6.0 | IBKR ladder + MONITOR/HANDOFF badges; Docker dev skips IB; handoff audit JSONL partial                                    |
| **Performance**             |   5.5 | 26k-line UI stack; multi-interval polling (15s health, 60s freshness); snapshot SWR exists but not universal              |
| **Scalability**             |   5.0 | yfinance rate limits; single-node FastAPI; no horizontal playbook fan-out                                                 |
| **Maintainability**         |   5.0 | `index.html` 8,610 + `cc-app.js` 8,743 lines; partial extraction via `build-cc-template.mjs`                              |
| **Testing**                 |   7.0 | 176 test files; strong authority-boundary coverage; E2E/Playwright and load tests absent                                  |
| **UX**                      |   7.0 | BDR strip, authority pills, degraded banners; i18n half-done; density good, keyboard nav weak                             |
| **Explainability**          |   7.5 | BDR, funnel layer defs, `surface_authority.py`, provenance envelopes; ML still opaque on cards                            |
| **Institutional Readiness** |   5.5 | No enterprise data entitlements, audited P&L ledger, or RBAC; governance direction is sound                               |
| **Commercial Value**        |   6.5 | Differentiated Operator OS for disciplined PMs; not sellable as Terminal replacement                                      |
| **Expected Alpha / ROI**    |   6.0 | Process alpha (fewer bad trades) > signal alpha today; 1R sizing + gates likely +0.3–0.8 Sharpe vs undisciplined baseline |
| **PM Productivity**         |   7.0 | BDR auto-brief, playbook funnel, ops probe/runtime table save 30–60 min/day vs spreadsheet workflow                       |
| **Research Productivity**   |   6.5 | Vibe Agent, Strategy Lab, Shadow, Reports pipeline; Opportunity Intelligence APIs research-only                           |

### Executive Summary

**Strengths:** Authority is real — `build_system_state()` / `build_page_capability()` in `operator_state_contract.py` (531 lines) with dedicated tests. Decision truth separation in `decision_truth_model.py` prevents scan-ranked names from masquerading as watch-qualified. BDR (`bdr_operator_summary.py`) auto-generates NOW/BLOCKER/NEXT from live state. Unified risk in `src/core/risk_limits.py`. Sprint 114 opportunity scanner adds regime-aware dual-engine screening without breaking gates.

**Gaps:** Monolithic UI/API surfaces, retail-grade primary data (yfinance), sample-starved ML, synthetic Flow overlay, and incomplete closed-trade→learning loop limit measurable alpha claims. Institutional buyers will ask for provenance, broker-synced book truth, and audited performance — CC is honest about local-book limitations (`portfolio_decision_console.py` copy) but has not closed the loop.

**Strategic positioning:** Transform CC into the **world's best AI investment OS for a disciplined operator pod** — Palantir-shaped decision ontology + Bloomberg-grade density on a retail-accessible stack — **without** pretending to be Citadel latency or RenTech sample size. Preserve all authority contracts; compete on **process alpha, explainability, and operational excellence**.

---

## 2. Biggest Weaknesses

Ranked by severity × ROI impact. ROI estimates assume a single PM, $500K–$2M book, 200 trading days/year.

| Severity     | Weakness                                           | Module evidence                                                             | Est. ROI if fixed                                                   | Fix horizon |
| ------------ | -------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------- | ----------- |
| **Critical** | Client/server deploy state drift                   | Today, Playbook, cc-header poll separately; `cc-app.js` reconciles locally  | **+$15–40K/yr** avoided error trades                                | 1–2 wks     |
| **Critical** | Retail data without mandatory provenance labels    | yfinance primary; `market_data.py`; optional Polygon                        | **Institutional adoption blocker**; +0.2 Sharpe from better entries | 2–3 wks     |
| **Critical** | Monolithic `main.py` (6,610 lines) regression risk | Inline routes bypass router tests                                           | **Authority regression** cost unbounded                             | 3–4 wks     |
| **High**     | Closed trades not reliably flowing to learning     | `learning_loop.py` JSONL; `pull_closed_trades_from_learning_loop()` partial | **+$8–20K/yr** from sizing calibration                              | 2 wks       |
| **High**     | ML/Thompson displayed before sample floor          | `ml_advisory_summary.py`; Thompson n&lt;5                                   | **False confidence** → oversizing                                   | 0.5 wk      |
| **High**     | Playbook p95 latency on scan days                  | `PLAYBOOK_LIVE_SCAN_LIMIT=120`; no universal SWR                            | **30–45 min/day** PM wait                                           | 1–2 wks     |
| **High**     | Factor/capacity stubs use mock provenance          | `factor_exposure.py` `source="mock-factor-stub"`                            | Misleading research chips                                           | 2 wks       |
| **Medium**   | i18n: API strings English on non-Ops tabs          | `cc-i18n.js` ~300 literals; Alpine `x-text`                                 | HK operator friction                                                | 3 wks       |
| **Medium**   | Flow synthetic not visually distinct enough        | `FLOW_OVERLAY_DEGRADED_HEADLINES`                                           | Narrative overweight                                                | 1 wk        |
| **Medium**   | Portfolio quick-add sector cap not enforced in UI  | `risk_limits.max_sector_pct`; `portfolio.py`                                | Concentration blow-ups                                              | 1.5 wks     |
| **Medium**   | IBKR handoff untested under reconnect storms       | `ibkr_session_manager.py`                                                   | Execution slippage/failed brackets                                  | 2 wks       |
| **Low**      | ARCHITECTURE.md Discord-centric drift              | `docs/ARCHITECTURE.md`                                                      | Onboarding cost                                                     | 1 wk        |
| **Low**      | Polling storm under multi-tab                      | 15s/60s/120s intervals in `cc-app.js`                                       | API load, yfinance bans                                             | 3 wks       |

---

## 3. Opportunity Intelligence Review + Opportunity Intelligence v3 Design

### Current State (v2 foundation)

| Component           | Path                                          | Role                                  | Authority                     |
| ------------------- | --------------------------------------------- | ------------------------------------- | ----------------------------- |
| Opportunity Scanner | `src/engines/opportunity_scanner.py`          | Neal dual-engine bull/weak screener   | Research input → Discovery    |
| Intelligence API    | `src/api/routers/opportunity_intelligence.py` | Insider, 13F, events, strategy-health | `research_only`               |
| Insider             | `src/services/insider_tracker.py`             | Form 4 context                        | Degraded labels required      |
| Institutional       | `src/services/institutional_13f.py`           | 13F ownership context                 | 45–90 day lag                 |
| Events              | `src/services/event_noise_filter.py`          | Earnings/catalyst risk                | Blackout tie to `risk_limits` |
| Strategy health     | `src/services/strategy_curve_health.py`       | Curve/OOS diagnostics                 | Backtest ≠ live               |
| Capacity            | `src/services/capacity_intelligence.py`       | Scale/friction layer                  | Downgrade-only                |
| Playbook universe   | `src/services/playbook_signal_universe.py`    | Brief merge + live scan top-up        | WATCH cap on brief rows       |

**Strengths:** Sprint 114 scanner uses median/MAD normalization — outlier-resistant. Capacity layer correctly reuses `cost_adjusted_edge` and aligns with `slippage_gate_service` participation ceilings. Provenance via `signal_provenance.py` envelopes.

**Gaps:**

1. Discovery rows lack persistent `artifact_id` linking scanner run → dossier → playbook row.
2. No cross-name theme/macro clustering on Discovery board.
3. `factor_exposure.py` is mock-stub — must not appear on deploy surfaces without `degraded=true`.
4. Opportunity Intelligence not embedded in Dossier 360 (API exists; UI chips sparse).
5. No explicit **half-life / decay** field on scanner scores.

### Opportunity Intelligence v3 Design

**Goal:** Single-name and universe 360 that **informs** the council pipeline without granting deploy. All v3 outputs carry `authority: research_only` and `may_authorize_deploy: false`.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Opportunity Intelligence v3                   │
├──────────────┬──────────────┬──────────────┬──────────────────────┤
│ Universe Scan│ Name 360     │ Portfolio Fit│ Alpha QA Overlays  │
│ (Scanner v2) │ (Dossier)    │ (Book context)│ (decay, analogs)  │
├──────────────┴──────────────┴──────────────┴──────────────────────┤
│ Artifact Store: data/artifacts/opportunity/{run_id}/{ticker}.json │
│ Provenance: source, as_of, lag_days, mode (LIVE|DEGRADED|MOCK)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ (research bridge only)
                    Playbook rank input (WATCH cap preserved)
                              │
                              ▼
              Council + decision_truth_model (deploy gate)
```

**v3 API additions** (new router or extend `/api/v7/intelligence`):

| Endpoint                   | Payload                                | Notes                                 |
| -------------------------- | -------------------------------------- | ------------------------------------- |
| `GET /v3/universe`         | ScannerResult + theme clusters         | Cached 5 min; regime-aware engine tag |
| `GET /v3/name/{ticker}`    | Merged insider+13F+events+capacity+fit | Single dossier embed payload          |
| `GET /v3/analogs/{ticker}` | Historical pattern matches             | Research only; show n and date range  |
| `GET /v3/decay/{ticker}`   | Score half-life estimate               | From `feature_ic` decay curves        |

**Data contract (every field):**

```json
{
	"ticker": "NVDA",
	"score": 82.4,
	"authority": "research_only",
	"may_authorize_deploy": false,
	"provenance": {
		"source": "opportunity_scanner",
		"as_of": "2026-08-25T14:30:00Z",
		"mode": "DEGRADED",
		"lag_days": 0
	},
	"decay": { "half_life_sessions": 3, "confidence": "low" }
}
```

**UI:** Discovery cards show `research_only` chip + engine tag (bull/weak). One-click "Open in Dossier" preserves authority — no deploy CTA. Playbook bridge copies `artifact_id` for audit trail.

**Acceptance:** `test_opportunity_intelligence.py` extended; mock factor never on Today/Playbook without degraded banner; AVOID never in monitor ranking (existing contract test).

---

## 4. Alpha Factory Design

The Alpha Factory is CC's **research production line** — from edge hypothesis to portfolio-fit deploy candidate — with hard gates at each stage. It does **not** auto-deploy.

### Pipeline stages

| Stage                          | Module(s)                                                      | Output                       | Gate                            |
| ------------------------------ | -------------------------------------------------------------- | ---------------------------- | ------------------------------- |
| **Edge source**                | `opportunity_scanner.py`, `scanner_matrix.py`, `signal_engine` | Ranked candidates + tags     | Regime router selects engine    |
| **Expected alpha**             | `cost_adjusted_edge.py`, `cost_adjusted_ranker`                | Net edge after fees/slippage | Below floor → WATCH only        |
| **Capacity**                   | `capacity_intelligence.py`                                     | scales_clean → pilot_only    | Downgrade-only                  |
| **Crowding**                   | `factor_exposure.py`, `crowding_narrative.py`                  | crowding label               | High → research flag            |
| **Persistence**                | `leader_persistence.py`, `leader_tracking_service.py`          | Leader streak days           | Feeds council confidence        |
| **Half-life / decay**          | `feature_ic.py`                                                | IC decay alerts              | Advisory; no auto weight change |
| **Risk**                       | `risk_limits.py`, `random_walk_guardrails.py`                  | R:R, ATR, blackout           | TRADE_RR_THRESHOLD=2.5          |
| **Analogs**                    | _v3 new_                                                       | Pattern match set            | Research tab only               |
| **Factor/theme/macro**         | `factor_exposure.py`, `macro_trend.py`, `index_regime.py`      | Exposure vector              | Book overlap check              |
| **Institutional confirmation** | `institutional_13f.py`, `insider_tracker.py`                   | 13F/insider context          | Lag-labeled                     |
| **Execution quality**          | `execution_readiness.py`, `slippage_gate_service.py`           | Spread/participation         | Blocks handoff if HARD          |
| **Portfolio fit**              | `portfolio_fit.py`, `portfolio_decision_console.py`            | fit_score, concentration     | Cannot override deploy gate     |

### Alpha Factory artifact schema

Write per-candidate artifacts to `data/artifacts/alpha_factory/{date}/{ticker}.json`:

```json
{
	"ticker": "MSFT",
	"edge_source": "bull_scanner",
	"expected_alpha_bps": 45,
	"capacity_class": "scale_pilot_only",
	"crowding": "moderate",
	"persistence_days": 12,
	"half_life_sessions": 4,
	"factor_exposure": { "beta": 1.05, "sector": "Technology" },
	"execution_quality": "clean",
	"portfolio_fit": 72,
	"institutional_confirmation": { "13f_trend": "accumulating", "lag_days": 45 },
	"authority": "research_only",
	"deploy_eligible": false,
	"gate_reasons": ["board WAIT", "R:R 2.1 < 2.5"]
}
```

### Operating principles

1. **Factory output ≠ permission** — only `decision_truth_model` + council + `operator_state_contract` may set `deploy_open`.
2. **Decay is first-class** — stale scanner scores (>2 sessions) show amber decay chip.
3. **Capacity is downgrade-only** — aligns with `SIGNAL_CAPACITY` in `signal_provenance.py`.
4. **No fake confidence** — Thompson/ML multipliers hidden when n&lt;5 arms or n&lt;30 self-learn.

---

## 5. Portfolio Intelligence

### Current State

| Capability      | Module                          | Status                                      |
| --------------- | ------------------------------- | ------------------------------------------- |
| Book analytics  | `portfolio_decision_console.py` | Strong operator copy; local vs broker truth |
| Positions       | `portfolio_positions.py`        | Manual entries                              |
| Risk cockpit    | `portfolio_risk_cockpit.py`     | Heat, stop breach honesty                   |
| Factor exposure | `factor_exposure.py`            | Mock stub — needs live wire                 |
| Fit scoring     | `portfolio_fit.py`              | Heuristic; beta wire pending                |
| Rebalance sim   | `rebalance_sim.py`              | Research                                    |
| Core/satellite  | `core_satellite.py`             | Sleeve model                                |
| Allocator       | `strategy_allocator.py`         | Fund sleeve weights                         |
| Drawdown sizer  | `drawdown_sizer.py`             | Tested; not fully wired to live tab         |
| Crisis survival | `crisis_portfolio_survival.py`  | Regime stress                               |

**Honest limitations (preserved):** `_LOCAL_ONLY_COPY` and `_BROKER_OFFLINE_COPY` in `portfolio_decision_console.py` prevent false broker sync confidence.

### Portfolio Intelligence vNext

**Target:** Allocator-grade book view that answers: _What do I own, what risk am I running, what should I trim/add, and does a new name fit?_ — all subordinate to page gates.

| Layer                    | Feature                                      | Module plan                                           |
| ------------------------ | -------------------------------------------- | ----------------------------------------------------- |
| **Factor/theme/sector**  | Live sector weights vs `RISK.max_sector_pct` | Wire `factor_exposure` to real sectors from positions |
| **Correlation**          | Name-pair and sector correlation buckets     | Extend `correlation_risk.py`                          |
| **Capacity**             | Book-level ADV usage                         | Aggregate `capacity_intelligence` per name            |
| **Liquidity**            | Exit-days-at-20% ADV                         | New helper on capacity module                         |
| **Drawdown**             | Rolling DD vs circuit breakers               | Wire `drawdown_sizer` to portfolio tab                |
| **Heat**                 | Planned R vs breached stops                  | Already in console; unify with playbook 1R            |
| **Tail risk**            | Scenario shock (% book −2σ day)              | `scenarios.py` router + portfolio embed               |
| **Macro**                | Regime size scalar overlay                   | `regime_router` → portfolio banner                    |
| **Hidden concentration** | Thematic overlap (e.g., "AI" across sectors) | Theme tagger on positions                             |
| **Optimizer**            | Mean-variance or risk-parity **simulation**  | Research-only in `rebalance_sim.py`                   |
| **Capital allocator**    | Sleeve budgets from `strategy_allocator.py`  | Advisory targets                                      |
| **Cash optimizer**       | Deploy dry powder vs `risk_off_max_exposure` | BDR integration                                       |
| **Replacement engine**   | "Swap X for Y" when fit higher               | Rank by fit delta; human confirms                     |

**Replacement engine flow (no auto-trade):**

1. New playbook name scores fit 85; lowest-fit holding scores 42.
2. Portfolio shows "Replacement candidate" chip with R delta and sector impact.
3. Operator must confirm on Portfolio tab; deploy gate still required for add.

**Acceptance:** Sector cap blocks quick-add in UI; stop-breach shows unmanaged risk copy (existing); broker-sync path labeled when IBKR connected.

---

## 6. Learning Engine vNext

### Current State

| Component            | Path                                                      | Status                                |
| -------------------- | --------------------------------------------------------- | ------------------------------------- |
| Decision Journal     | `src/engines/decision_persistence.py` (`DecisionJournal`) | JSONL append                          |
| Forward Outcomes     | Partial via journal                                       | No systematic T+1/T+5 mark            |
| Learning Loop        | `src/engines/learning_loop.py`                            | Closed trades JSONL; MetaEnsemble     |
| Self-Learning        | `src/engines/self_learning.py`                            | min_sample=30; kill switch; audit log |
| Feature IC           | `src/engines/feature_ic.py`                               | Decay alerts advisory                 |
| Thompson Sizing      | `src/engines/thompson_sizing.py`                          | Arms need closed-trade feedback       |
| Threshold Governance | `decision_truth_model.py` TRADE_RR_THRESHOLD              | Static; changes need changelog        |
| Regime learning      | `self_learning.py` regime-conditioned params              | Separate param sets per regime        |

### Learning Engine vNext Design

```
Deploy decision (DecisionJournal)
        │
        ▼
Forward Outcomes (T+1, T+5, T+20 session marks)
        │
        ▼
Closed Trade (IBKR fill → closed_trades.jsonl)
        │
        ├──► Feature IC update (feature_ic.py)
        ├──► Thompson arm update (thompson_sizing.py)
        ├──► Self-learning cycle (self_learning.py) — advisory apply only
        └──► Alpha QA Review (Ops panel)
```

**Decision Journal vNext fields:**

- `decision_id`, `ticker`, `action`, `regime`, `sector`, `theme`, `vol_bucket`, `macro_state`
- `gate_snapshot` (deploy_open, tradeability, gates_active)
- `operator_rationale` (optional text)

**Forward Outcomes service** (new: `src/engines/forward_outcomes.py`):

- Nightly scheduler job marks open decisions at T+1/T+5/T+20
- Stores to `data/forward_outcomes.jsonl`
- Powers calibration Brier without waiting for trade close

**Persistent Learning rules:**

1. Self-learning **never** auto-applies without Ops toggle + sample ≥30.
2. Threshold changes (e.g., TRADE_RR_THRESHOLD) require explicit version bump in changelog — **no auto-loosen**.
3. Regime/sector/theme/vol/macro buckets tracked separately for attribution.

**Alpha QA / Review panel (Ops):**

- Win rate by regime, sector, setup grade
- Feature IC decay list with "review weights" copy only
- Calibration Brier trend
- Shadow vs actual digest link

**Threshold Governance:**

- All tunable params in `TUNABLE_RULES` with min/max bounds
- Regime-specific overrides stored in `models/regime_params.json`
- Audit every adjustment in `models/self_learning_audit.jsonl`

---

## 7. AI Review (Measurable Outcomes Only)

| AI surface           | Module                                     | Measurable today             | Gap                                 |
| -------------------- | ------------------------------------------ | ---------------------------- | ----------------------------------- |
| **LLMs**             | `ai_service.py`, `catalyst_summarizer.py`  | Narrative generation latency | No quality score vs outcomes        |
| **ML ranking**       | MetaEnsemble in learning loop              | Win rate when n≥30           | n usually &lt;30                    |
| **Scoring**          | `opportunity_scanner.py`, council          | Funnel conversion rates      | No labeled outcome dataset at scale |
| **Learning**         | `self_learning.py`                         | Adjustments logged           | Apply rate ~0 in prod               |
| **Explanation**      | BDR, funnel defs, provenance               | Operator sentence accuracy   | ML weights opaque on cards          |
| **Simulation**       | `backtest_lab.py`, `validation_lab.py`     | Walk-forward grades          | Not linked to playbook rows         |
| **Decision support** | `best_action.py`, `ml_advisory_summary.py` | Blocker identification       | No A/B on deploy quality            |

**Measurable outcome targets (12-month):**

| Metric                                 | Baseline        | Target                  | Measurement                |
| -------------------------------------- | --------------- | ----------------------- | -------------------------- |
| Deploy decision calibration (Brier)    | Unknown         | &lt;0.22                | `get_calibration_status()` |
| Closed-trade sample for ML             | &lt;10          | ≥50                     | `learning_loop.summary()`  |
| False deploy attempts blocked          | High confidence | 100% in WAIT            | E2E authority tests        |
| Feature IC alert → review action       | 0% tracked      | 80% acknowledged in Ops | Ops changelog              |
| LLM narrative cost per ticker/day      | Unbounded       | &lt;$0.02               | Cache per ticker/day       |
| Explanation coverage on Playbook cards | ~40%            | ≥90% fields with `why`  | Render integrity test      |

**AI rules (hard):**

- `ml_advisory_summary.py` `authority_note` on every ML surface
- No GPT/LLM output changes `action` or `deploy_open`
- Simulation grades displayed as `research_only` on btlab
- Ranker weights visible in Ops/research tabs only — not on deploy cards

---

## 8. UX Review

**Reference palettes:** Bloomberg (density, keyboard), Apple (clarity, motion), Linear (speed, command palette), Raycast (launcher), Notion (docs), Palantir (ontology, lineage).

### Current UX inventory

| Area              | Assessment                                                  | Evidence                               |
| ----------------- | ----------------------------------------------------------- | -------------------------------------- |
| **Navigation**    | Good tab model; Command hidden appropriately                | `surface_authority.py` TAB_SURFACE_MAP |
| **Density**       | Bloomberg-adjacent on Playbook/Today                        | BDR strip, funnel KPIs                 |
| **Workflow**      | Operator OS flow documented in Guide                        | Layer 1 checklist                      |
| **Keyboard**      | Weak — no global command palette                            | Missing `⌘K` launcher                  |
| **Multi-monitor** | Sticky BDR helps; no detached panels                        | Today tab only                         |
| **Tablet**        | PM strip chip menu exists                                   | Narrow viewport untested               |
| **Mobile**        | Functional read-only possible                               | Polling heavy                          |
| **Authority UX**  | Strong — pills, strips, degraded banners                    | `resolve_authority()`                  |
| **i18n**          | Partial — operator sentences bilingual; API strings English | `cc-i18n.js`                           |
| **Empty states**  | WAIT_DAY_OK pattern tested                                  | Consistent across tabs needed          |

### UX vNext recommendations (ranked)

1. **Command palette** (`⌘K`): jump to ticker dossier, Playbook, Ops blockers — Raycast pattern.
2. **Single decision payload** — eliminate client-side deploy reconciliation (reduces cognitive load).
3. **Data contract strip** on every price: source, as_of, mode — Bloomberg provenance bar.
4. **Keyboard shortcuts:** `G T` Today, `G P` Playbook, `G D` Dossier, `/` search ticker.
5. **Detached monitor layout:** Playbook rank left, Dossier right — multi-monitor PM setup.
6. **Flow/Discovery synthetic watermark** — persistent diagonal badge, not just headline.
7. **Partial template split** — `build-cc-template.mjs` for Today/Playbook/Portfolio.
8. **Reduced motion mode** — respect `prefers-reduced-motion` for authority strip pulses.

**Do not:** add deploy buttons to research tabs; hide blockers behind dismiss without session ack logged.

---

## 9. PM Workflow (Full Day)

| Phase          | Time (ET)   | CC surface                         | Actions                                                           | Authority                |
| -------------- | ----------- | ---------------------------------- | ----------------------------------------------------------------- | ------------------------ |
| **Morning**    | 07:00–09:00 | Today + BDR                        | Read NOW/BLOCKER/NEXT; check tradeability, regime, data freshness | Monitor until gate opens |
| **Research**   | 09:00–10:00 | Discovery + Dossier + Opp Intel v3 | Scan universe; open name 360; check capacity/fit                  | Research only            |
| **Committee**  | 10:00–10:30 | Today board + Ops                  | Review council output; probe vs runtime; ML advisory footnote     | Board gate               |
| **Portfolio**  | 10:30–11:00 | Portfolio                          | Heat check; sector weights; replacement candidates                | Sizing when deploy_open  |
| **Execution**  | 11:00–15:30 | Playbook → Dossier confirm → IBKR  | 1R sizing; bracket handoff; MONITOR→READY ladder                  | Deploy when gates open   |
| **Monitoring** | Intraday    | Today + position alerts            | Position alerts; circuit breaker; stale data banner               | Auto-monitor             |
| **Review**     | 15:45–16:00 | Rejections + Shadow                | Why names failed; behavior vs shadow                              | Audit                    |
| **Learning**   | 16:00–16:15 | Ops Alpha QA                       | Forward outcomes; IC decay; calibration                           | Advisory                 |
| **EOD**        | 16:15–16:30 | Reports + Decision Journal         | Export board snapshot; journal append                             | Archive                  |

**WAIT day workflow:** Discovery + near-miss upgrade ladder + Rejections audit — **no deploy path**. BDR headline: "NO TRADE. Monitor only."

**Fallback day workflow:** `fallback_mode` active → deploy paused; probe may show OK but runtime strip blocks sizing.

---

## 10. Performance Review (10× Speed Without Changing Authority)

All optimizations preserve server-authoritative gates — cache only affects **latency**, never **permission**.

| #   | Optimization                      | Current              | Target                | Module                                         | Authority impact           |
| --- | --------------------------------- | -------------------- | --------------------- | ---------------------------------------------- | -------------------------- |
| 1   | Playbook ranked SWR               | Live scan every load | Cache-first &lt;200ms | `playbook_ranked_snapshot.json`, `playbook.py` | None — stale banner if old |
| 2   | Unified decision payload          | 3 polls reconcile    | 1 poll                | `decision_hub.py`, `cc_header.py`              | Improves truth             |
| 3   | Consolidate freshness into header | 60s separate poll    | Piggyback on header   | `data_freshness_service.py`                    | None                       |
| 4   | gzip instant dashboard            | Partial              | Always serve `.gz`    | `_cc_instant.py`                               | None                       |
| 5   | Opportunity scanner cache         | 5 min file cache     | Redis/in-memory TTL   | `opportunity_scanner.py`                       | None                       |
| 6   | yfinance batch fetch              | Sequential           | Async batch per scan  | `market_data.py`                               | None                       |
| 7   | Dossier instant core              | Partial              | Core fields &lt;500ms | `test_dossier_instant_core.py` path            | None                       |
| 8   | Reduce health poll                | 15s                  | 30s + SSE trigger     | `cc-app.js`                                    | None                       |
| 9   | Template partials                 | 17k monolith parse   | Split bundles         | `build-cc-template.mjs`                        | None                       |
| 10  | P2 cache TTL expansion            | 120s                 | Tiered 30s/300s       | `p2_cache.py`                                  | None                       |

**Expected combined impact:** Playbook p95 8–15s → **&lt;1.5s** (cache hit); Today load 3–5s → **&lt;800ms**; API QPS −40% from poll consolidation.

**Forbidden "optimizations":** skip gate computation; cache `deploy_open=true`; client-side rank bypass.

---

## 11. Code Review

### Duplication

| Duplication          | Locations                                                                 | Refactor                                        |
| -------------------- | ------------------------------------------------------------------------- | ----------------------------------------------- |
| Deploy gate checks   | `main.py`, routers, `cc-app.js`                                           | Single `DecisionBoardService`                   |
| Action normalization | `operator_state_contract`, `bdr_operator_summary`, `decision_truth_model` | Shared `_norm_action` in `src/utils/actions.py` |
| Near-miss logic      | `operator_state_contract`, `playbook_near_miss.py`                        | Consolidate in contract module                  |
| Authority labels     | `surface_authority.py`, `cc-helpers.js`                                   | Server-render labels; JS display only           |
| Risk magic numbers   | Legacy modules                                                            | Audit → `risk_limits.py` only                   |

### Dead code candidates

- Discord-centric paths in `main.py` if CC is primary (mark deprecated, don't delete yet)
- Duplicate decision journal: `decision_persistence.py` vs `decision_journal.py` — merge SSOT
- Unused polling handlers in `cc-app.js` after SSE (future)

### Abstractions needed

1. **`DecisionBoardService`** — composes truth model + BDR + rank buckets for Today/Playbook/header.
2. **`ProvenanceMixin`** — mandatory `source/as_of/mode` on all market fields.
3. **`ArtifactWriter`** — extend `artifacts/performance_artifact_writer.py` pattern to alpha factory.

### Module boundaries

| Boundary | Rule                                      |
| -------- | ----------------------------------------- |
| Routers  | HTTP only; no business logic &gt;20 lines |
| Services | Domain logic; no FastAPI imports          |
| Engines  | Signal/generation; subordinate to gates   |
| Core     | SSOT: risk, version, config               |

### Typing

- Add `TypedDict` for `SystemState`, `PageCapability`, `ScannerResult`
- Mypy strict on `operator_state_contract.py`, `decision_truth_model.py`, `risk_limits.py`

### Concrete refactoring plan

| Phase | Action                                           | Lines removed | Timeline   |
| ----- | ------------------------------------------------ | ------------- | ---------- |
| R1    | Extract 25 largest `main.py` handlers to routers | ~1,500        | Sprint 116 |
| R2    | `DecisionBoardService`                           | ~400 dup      | Sprint 115 |
| R3    | UI partial split (Today, Playbook, Portfolio)    | ~3,000 moved  | Sprint 117 |
| R4    | Merge decision journal modules                   | ~200 dup      | Sprint 118 |
| R5    | Shared action/rank utilities                     | ~150 dup      | Sprint 115 |

---

## 12. Testing Review

### Current coverage (176 files)

| Category                  | Status | Key tests                                                                                                        |
| ------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------- |
| **Unit**                  | Strong | `test_decision_truth_model.py`, `test_operator_state_contract.py`                                                |
| **Integration**           | Medium | `test_pipeline_integration.py`, `test_dashboard_decision_integrity.py`                                           |
| **Contract/authority**    | Strong | `test_quant_authority_boundaries.py`, `test_tracking_authority_boundaries.py`, `test_vnext_truthful_surfaces.py` |
| **UI**                    | Medium | `test_ui_render_integrity.py`, `test_playbook_render_integrity.py`                                               |
| **Performance**           | Weak   | No k6/ locust playbook p95                                                                                       |
| **Chaos**                 | Absent | No IBKR disconnect injection                                                                                     |
| **Simulation**            | Medium | `test_backtest_lab_cleanup.py`, sprint btlab tests                                                               |
| **Backtest/walk-forward** | Medium | Strategy optimizer tests                                                                                         |
| **Shadow**                | Weak   | `shadow_account.py` tested minimally                                                                             |
| **E2E**                   | Absent | No Playwright                                                                                                    |

### Testing vNext matrix

| Layer        | Tool               | Scenario                                 |
| ------------ | ------------------ | ---------------------------------------- |
| Authority    | pytest parametrize | WAIT × STALE × broker_down × fallback    |
| Contract     | JSON schema        | `/api/v7/decision/board` payload         |
| UI           | Playwright         | Deploy buttons disabled on WAIT day      |
| Performance  | k6                 | `/api/playbook/ranked` p95 &lt;2s cached |
| Chaos        | pytest + mock IB   | Reconnect during handoff                 |
| Walk-forward | CI weekly          | Optimizer OOS grade regression           |
| Shadow       | Scheduled test     | Shadow digest generates                  |

**CI gate:** Docker job `python -m pytest tests/ -q` + `scripts/verify_10_10.sh` on every PR.

**Property test:** Hypothesis — AVOID never in `monitor_rows` (`build_playbook_rank_buckets`).

---

## 13. Commercial Review

### vs institutional expectations

| Buyer lens          | Expectation                                 | CC today                       | Gap             | CC moat                  |
| ------------------- | ------------------------------------------- | ------------------------------ | --------------- | ------------------------ |
| **Bloomberg**       | Real-time multi-asset, entitlements         | yfinance delayed               | Critical data   | Gate logic, BDR workflow |
| **Renaissance**     | Industrial feature factory, OOS rigor       | feature_ic, walk-forward seeds | Sample size     | Honest ML subordination  |
| **Citadel**         | Microsecond execution, pre-trade everywhere | IBKR brackets, seconds latency | Not comparable  | Discretionary discipline |
| **Jane Street**     | Market-making infrastructure                | N/A                            | Not comparable  | Risk-first sizing        |
| **OpenAI**          | LLM decision support                        | Local + cloud LLM advisory     | No outcome loop | Authority preservation   |
| **Professional PM** | Audited track record, broker sync           | Local book, JSONL              | Persistence     | Operator OS UX           |

### Commercial positioning

**Sell:** "The only AI investment OS that won't let you lie to yourself about deploy authority."

**Target customer:** Solo PM or 2–5 person pod running systematic discretion on IBKR, $500K–$10M AUM.

**Pricing axis (future):** Base OS + paid data tier + optional cloud sync — never paywall safety gates.

**Do not claim:** HFT, prop-shop alpha, Terminal replacement, auto-trading without human deploy.

**Export hook (Sprint 120):** Board snapshot JSON/CSV with authority disclaimer for advisors using Bloomberg notes.

---

## 14. Roadmap: Sprints 115–120

### Sprint 115 — Decision Board Unification (P0)

| Field                               | Detail                                                                                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Objectives**                      | Single server-built `DecisionBoardService` payload shared by Today, Playbook, cc-header; identical `deploy_open` everywhere                       |
| **Expected ROI**                    | **+$15–40K/yr** avoided deploy mismatch errors; 15 min/day less reconciliation                                                                    |
| **Hit-rate / yield / productivity** | Zero authority drift incidents; PM trust +1 tier                                                                                                  |
| **Difficulty**                      | Medium                                                                                                                                            |
| **Risk**                            | Low — strengthens gates                                                                                                                           |
| **Dependencies**                    | `operator_state_contract.py`, `decision_hub.py`, `bdr_operator_summary.py`                                                                        |
| **Acceptance tests**                | Parametrize WAIT/STALE/broker/fallback; three endpoints return identical `system_state.deploy_open`; `test_dashboard_decision_integrity.py` green |

### Sprint 116 — Data Provenance & CI Truth Gate (P0)

| Field                               | Detail                                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Objectives**                      | Mandatory `source/as_of/mode` on all price fields; Docker CI runs full pytest + `verify_10_10.sh` |
| **Expected ROI**                    | Institutional credibility; prevents silent yfinance degradation                                   |
| **Hit-rate / yield / productivity** | 100% price fields labeled; CI blocks authority regressions                                        |
| **Difficulty**                      | Medium                                                                                            |
| **Risk**                            | Low                                                                                               |
| **Dependencies**                    | `brief_data_service.py`, `market_data.py`, GitHub Actions / Docker CI                             |
| **Acceptance tests**                | STALE hides deploy CTAs; red CI on `test_operator_state_contract` failure                         |

### Sprint 117 — Playbook 10× Performance + Alpha Factory Artifacts (P1)

| Field                               | Detail                                                                                                         |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Objectives**                      | Universal playbook snapshot SWR; write Alpha Factory artifacts per candidate; p95 &lt;2s                       |
| **Expected ROI**                    | **30–45 min/day** saved on scan days; audit trail for research                                                 |
| **Hit-rate / yield / productivity** | p95 playbook &lt;2s cached; 100% top-12 rows have `artifact_id`                                                |
| **Difficulty**                      | Medium                                                                                                         |
| **Risk**                            | Medium — stale cache must show banner                                                                          |
| **Dependencies**                    | Sprint 115 decision payload; `playbook_signal_universe.py`, snapshot writer                                    |
| **Acceptance tests**                | k6 p95; degraded banner when snapshot age &gt; threshold; artifacts written to `data/artifacts/alpha_factory/` |

### Sprint 118 — Learning Loop Closure + Forward Outcomes (P1)

| Field                               | Detail                                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------- |
| **Objectives**                      | IBKR paper fills → `closed_trades.jsonl`; nightly forward outcome marks; Ops Alpha QA panel |
| **Expected ROI**                    | **+$8–20K/yr** from calibrated sizing; ML sample ≥30 within 90 days                         |
| **Hit-rate / yield / productivity** | Closed-trade capture ≥95%; Brier tracked weekly                                             |
| **Difficulty**                      | Medium–High                                                                                 |
| **Risk**                            | Medium — must not auto-apply learning                                                       |
| **Dependencies**                    | `learning_loop.py`, `ibkr_service.py`, scheduler                                            |
| **Acceptance tests**                | Sim fill appends JSONL; Thompson hidden when n&lt;5; self-learning kill switch default ON   |

### Sprint 119 — Opportunity Intelligence v3 + Dossier Embed (P1)

| Field                               | Detail                                                                                   |
| ----------------------------------- | ---------------------------------------------------------------------------------------- |
| **Objectives**                      | v3 name 360 API; insider/13F/events/capacity chips on Dossier; Discovery research bridge |
| **Expected ROI**                    | **20 min/day** research time saved; fewer concentration mistakes                         |
| **Hit-rate / yield / productivity** | Dossier 360 coverage ≥80%; zero mock factor on deploy surfaces                           |
| **Difficulty**                      | Medium                                                                                   |
| **Risk**                            | Low — research_only preserved                                                            |
| **Dependencies**                    | `opportunity_intelligence.py`, `insider_tracker.py`, dossier router                      |
| **Acceptance tests**                | 90+ day lag labels visible; `may_authorize_deploy: false` on all v3 payloads             |

### Sprint 120 — E2E Authority + Institutional Export (P1)

| Field                               | Detail                                                                                     |
| ----------------------------------- | ------------------------------------------------------------------------------------------ |
| **Objectives**                      | Playwright E2E: WAIT → deploy disabled; board snapshot JSON/CSV export; command palette v0 |
| **Expected ROI**                    | Regression safety; advisor workflow enablement                                             |
| **Hit-rate / yield / productivity** | E2E green in CI; export used in weekly PM review                                           |
| **Difficulty**                      | Medium                                                                                     |
| **Risk**                            | Low                                                                                        |
| **Dependencies**                    | Sprints 115–116 authority stable                                                           |
| **Acceptance tests**                | Playwright screenshot on failure; export includes authority disclaimer footer              |

---

## Appendix A — Key Module Index

| Domain      | Primary modules                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------------------- |
| Authority   | `operator_state_contract.py`, `surface_authority.py`, `decision_truth_model.py`                         |
| BDR         | `bdr_operator_summary.py`, `best_action.py`                                                             |
| Playbook    | `playbook_signal_universe.py`, `playbook_operator_intelligence.py`, `playbook_upgrade_ladder.py`        |
| Opportunity | `opportunity_scanner.py`, `opportunity_intelligence.py` (router)                                        |
| Portfolio   | `portfolio_decision_console.py`, `portfolio_fit.py`, `capacity_intelligence.py`                         |
| Risk        | `risk_limits.py`, `drawdown_sizer.py`, `slippage_gate_service.py`                                       |
| ML/Learning | `self_learning.py`, `learning_loop.py`, `feature_ic.py`, `thompson_sizing.py`, `ml_advisory_summary.py` |
| Execution   | `ibkr_service.py`, `execution_readiness.py`, `execution_analytics.py`                                   |
| Ops         | `ops_operator_console.py`, `data_freshness_service.py`                                                  |
| UI          | `index.html`, `cc-app.js`, `cc-helpers.js`, `cc-i18n.js`                                                |
| Scheduler   | `src/scheduler/main.py`                                                                                 |
| Tests       | 176 files; authority cluster under `tests/test_*authority*`                                             |

## Appendix B — Relation to Prior Review

This document **extends** `docs/CC_VNEXT_MASTER_REVIEW.md` (v9.0, score 6.8) with institutional Alpha OS framing, Alpha Factory / Portfolio Intelligence / Learning vNext designs, and sprints 115–120 re-scoped for decision unification and learning closure. Non-negotiable constraints are unchanged. Overall score raised to **7.0** reflecting Sprint 114 opportunity scanner and continued authority hardening — data and ML gaps remain the primary ceiling.

**Operational roadmap:** See [`CC_X_INSTITUTIONAL_ALPHA_OS.md`](./CC_X_INSTITUTIONAL_ALPHA_OS.md) for CC X **investment-outcome-first** architecture: six core engines (including Intelligence Engine), Investment Object + **AlphaObject** schemas, Alpha Attribution Tree, Capital Allocation Engine, Real-Time Alpha Monitor KPIs, Institutional Research Workspace, Tier 1–3 priorities, sprints **115–126**, and migration path.

---

_End of CC vNext Institutional Alpha OS Master Review._
