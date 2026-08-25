> **Superseded by [`CC_X_ENGINEERING_BACKLOG.md`](../CC_X_ENGINEERING_BACKLOG.md) and [`CC_X_ARCHITECTURE.md`](../CC_X_ARCHITECTURE.md) — retained for history only.**

# CC X — Full Institutional Alpha OS Review

**Document:** `docs/CC_X_FULL_INSTITUTIONAL_REVIEW.md`  
**Product:** CC X (Clarity Console X) · `TradingAI_Bot`  
**Version reviewed:** 9.0.0 (`src/core/version.py`)  
**Review date:** 2026-08-25  
**Branch:** `cc/upgrade-regime-tracking`  
**Method:** Full-repo read — prior reviews, authority contracts, ~160 services, ~100 engines, 61 routers, 182 test files, scheduler, UI stack. Code-path citations; no host pytest run.  
**Master prompt:** [`CC_X_MASTER_REVIEW_PROMPT.md`](./CC_X_MASTER_REVIEW_PROMPT.md)  
**Roadmap:** [`CC_X_INSTITUTIONAL_ALPHA_OS.md`](./CC_X_INSTITUTIONAL_ALPHA_OS.md)

---

## Non-Negotiable Constraints (Hard Rules)

All recommendations preserve these contracts. **No auto-deploy, no threshold auto-loosening, no fake confidence, no card-rank overrides of page gates.**

| Principle                              | Enforcement module                                                                      |
| -------------------------------------- | --------------------------------------------------------------------------------------- |
| **Research ≠ Deploy authority**        | `surface_authority.py`, `authority: research_only`, Discovery/Flow/Agent/Shadow/Reports |
| **Page Gate > Card Rank**              | `operator_state_contract.py`, Guide Layer 1 checklist; WAIT/NO_TRADE blocks deploy      |
| **No auto trading/deploy**             | `deploy_open` + IBKR handoff ladder; human approval required                            |
| **TRADE_RR_THRESHOLD = 2.5**           | `decision_truth_model.py` — **no auto-loosen**                                          |
| **EV after costs/risk**                | `cost_adjusted_ranker.py`, `risk_limits.py`                                             |
| **ML advisory only**                   | `ml_advisory_summary.py`, `self_learning.py` kill switch, n≥30 floor                    |
| **Capacity downgrade-only**            | `capacity_intelligence.py`, `signal_provenance.py`                                      |
| **Incremental evolution not rewrites** | Adapter `DecisionObject` → `InvestmentObject`; legacy rank fallback until parity        |

**Explicit prohibitions:** auto-loosen thresholds; ML multiplier without sample floor (n≥30); synthetic flow as live; Discovery score implying deploy; screens without EV; auto rule changes from learning; cache `deploy_open=true`.

---

## 1. Executive Review

### Overall Platform Score: **7.2 / 10**

CC remains an unusually disciplined **Operator Decision OS** advancing toward **Institutional Alpha OS**. Since the vNext review (7.0), measurable progress includes `DecisionBoardService` (Sprint 115 partial), Pydantic stubs for `InvestmentObject` and `AlphaObject`, Telegram operator alerts with deploy-gate awareness, and the CC X investment-outcome-first roadmap. The score ceiling is still **retail data depth**, **sample-starved ML**, **monolithic UI/API surfaces**, and **unclosed alpha measurement loop** — not authority design, which is ahead of industry norms for a retail-accessible stack.

**Strategic positioning:** Transform CC X into the world's best **AI investment OS for a disciplined operator pod** — Palantir-shaped decision ontology + Bloomberg-grade density — **without** Citadel latency or RenTech sample size cosplay.

### Subsystem Scorecard

| Subsystem                | Current |  Target | Δ        | Primary lever                                       |
| ------------------------ | ------: | ------: | -------- | --------------------------------------------------- |
| Knowledge Engine         |     4.5 |     9.0 | +4.5     | AlphaObject lifecycle + analog engine (Sprint 121)  |
| Research Engine          |     6.5 |     9.0 | +2.5     | Alpha Factory artifacts + EV Ranking 3.0            |
| Decision Engine          |     7.5 |     9.5 | +2.0     | Decision board SSOT completion + attribution root   |
| Portfolio Engine         |     6.5 |     9.0 | +2.5     | Capital allocation + replacement engine             |
| Execution Engine         |     6.0 |     8.5 | +2.5     | IBKR reconnect hardening + execution quality feed   |
| Intelligence Engine      |     3.0 |     9.0 | +6.0     | `intelligence_engine.py` CEO dashboard (Sprint 126) |
| Investment Object        |     5.0 |     9.0 | +4.0     | Schema exists; wire consumers incrementally         |
| AlphaObject              |     5.5 |     9.0 | +3.5     | Stub + schema; factory birth Sprint 117             |
| Authority/Governance     |     8.0 |     9.5 | +1.5     | Provenance CI gate Sprint 116                       |
| Data Provenance          |     5.5 |     9.0 | +3.5     | Mandatory `source/as_of/mode` on all prices         |
| ML/Learning              |     5.5 |     8.5 | +3.0     | Closed-trade loop + forward outcomes                |
| Opportunity Intelligence |     7.0 |     9.0 | +2.0     | v3 embed + artifact_id chain                        |
| Alpha Factory            |     5.0 |     8.5 | +3.5     | Artifact writer per candidate                       |
| IBKR/Execution           |     6.0 |     8.5 | +2.5     | Handoff audit + chaos tests                         |
| Ops/Scheduler            |     7.0 |     8.5 | +1.5     | Alpha QA panel + learning jobs                      |
| UI/UX                    |     7.0 |     9.0 | +2.0     | Command palette + provenance strip                  |
| Testing/CI               |     7.0 |     9.0 | +2.0     | Playwright E2E + performance k6                     |
| Security                 |     6.5 |     8.5 | +2.0     | Telegram token hygiene + RBAC path                  |
| Commercial Readiness     |     5.5 |     8.5 | +3.0     | Attribution export + broker truth                   |
| **Weighted overall**     | **7.2** | **9.5** | **+2.3** | Tier 1 compounding (see §13)                        |

### Executive Summary

**Strengths (Observed):**

- Authority is executable code: `build_system_state()` / `build_page_capability()` in `operator_state_contract.py` (573 lines) with dedicated test cluster.
- `DecisionBoardService` (`src/services/decision_board_service.py`) now composes identical `deploy_open` for Today, Playbook, cc-header — tested in `tests/test_decision_board_service.py`.
- Decision truth separation in `decision_truth_model.py` (~1,630 lines) prevents scan-ranked names from masquerading as deploy-qualified.
- CC X canonical schemas: `src/core/investment_object.py`, `src/core/alpha_object.py` — Pydantic, `research_only` default, `may_authorize_deploy=false`.
- Telegram alerts (`src/notifications/telegram.py`, `opportunity_telegram_alerts.py`, `system_telegram_alerts.py`) with bilingual branding, dedupe, deploy-gate tests in `tests/test_telegram_opportunity.py`, `tests/test_alert_deploy_gate.py`.
- Sprint 114+ opportunity scanner (`src/engines/opportunity_scanner.py`, 684 lines) with regime-aware dual-engine screening.
- BDR auto-brief (`bdr_operator_summary.py`), unified risk SSOT (`src/core/risk_limits.py`).

**Critical gaps:**

- Monolithic surfaces: `main.py` 6,641 lines, `index.html` 8,611, `cc-app.js` 12,700 — regression and hydration risk.
- Retail primary data (yfinance); provenance not mandatory on all price fields.
- `factor_exposure.py` still `source="mock-factor-stub"` — must not appear on deploy surfaces without degraded banner.
- Learning loop: `closed_trades.jsonl` exists but IBKR→JSONL capture ≥95% not verified; no `forward_outcomes.py`.
- Intelligence Engine, Knowledge Graph, Alpha Monitor, Attribution Tree — designed in CC X doc, **not implemented**.
- No Playwright E2E; no k6 playbook p95 gate in CI.

---

## 2. Architecture Review

### Layer model (investment-outcome-first)

```
Capital → Expected Alpha → Risk Budget → Portfolio → Execution → Measured Alpha → Knowledge
         ↑ six engines share InvestmentObject (decision) + AlphaObject (memory) ↑
```

| Layer        | Primary modules                                                                            | Status                     |
| ------------ | ------------------------------------------------------------------------------------------ | -------------------------- |
| Knowledge    | _planned_ `knowledge_graph.py`, `analog_engine.py`; `alpha_object.py` stub                 | Schema only                |
| Research     | `opportunity_scanner.py`, `validation_lab.py`, `cost_adjusted_ranker.py`                   | Strong; artifacts missing  |
| Decision     | `decision_truth_model.py`, `operator_state_contract.py`, `decision_board_service.py`       | Strong; board SSOT partial |
| Portfolio    | `portfolio_decision_console.py` (1,630 lines), `portfolio_fit.py`, `strategy_allocator.py` | Good copy; mock factor     |
| Execution    | `execution_readiness.py`, `ibkr_service.py`, `slippage_gate_service.py`                    | Partial IBKR in Docker dev |
| Intelligence | _not built_                                                                                | Sprint 126                 |
| Learning     | `learning_loop.py`, `self_learning.py`, `feature_ic.py`                                    | Advisory; loop open        |

### Architecture strengths

1. **Service/router split emerging** — 61 routers under `src/api/routers/`; domain logic in `src/services/` and `src/engines/`.
2. **Authority as first-class** — `surface_authority.py` TAB_SURFACE_MAP; every page gets `PageCapability`.
3. **Instant boot pattern** — `_cc_instant.py` proxy; gzip dashboard cache.
4. **Decision board unification started** — `build_decision_board()` wired in `decision.py`, `playbook.py`, `cc_header.py`.

### Architecture weaknesses

| Weakness                                   | Evidence                                                      | Impact                                 |
| ------------------------------------------ | ------------------------------------------------------------- | -------------------------------------- |
| God-file `main.py`                         | 6,641 lines; inline routes bypass router tests                | Authority regression risk              |
| Dual-product cognitive load                | Discord bot + CC in same repo                                 | Onboarding cost                        |
| No Investment Object consumer wire         | `investment_object.py` exists; rankers still use legacy paths | Schema drift                           |
| Duplicate decision journal paths           | `decision_persistence.py` vs `decision_journal.py`            | Attribution gaps                       |
| Client-side deploy reconciliation remnants | `cc-app.js` 12,700 lines; multi-interval polls                | Drift risk (mitigating via board SSOT) |

### Recommended architecture migrations (incremental)

| Phase | Sprint  | Action                                                            |
| ----- | ------- | ----------------------------------------------------------------- |
| A     | 115–116 | Complete DecisionBoardService; ProvenanceMixin on market fields   |
| B     | 117–119 | Alpha Factory artifacts; IO adapter for new paths only            |
| C     | 121–125 | Knowledge Graph + Attribution Tree; no historical JSONL migration |

**Rollback rule:** Any sprint failing authority cluster reverts IO consumer only — gates remain in `decision_truth_model.py` + `operator_state_contract.py`.

---

## 3. Quant Review (Bias Checks on Scoring Models)

### Models audited

| Model               | Module                                             | Bias / risk                                           | Mitigation                              |
| ------------------- | -------------------------------------------------- | ----------------------------------------------------- | --------------------------------------- |
| TRADE bar           | `decision_truth_model.py`                          | Brief-sourced rows capped WATCH — **good**            | Preserve; no auto-loosen                |
| Regime router       | `regime_router.py`                                 | Crisis NO_TRADE may over-block — acceptable           | Human override via Ops only             |
| Cost-adjusted rank  | `cost_adjusted_ranker.py`, `cost_adjusted_edge.py` | Fee/slippage assumptions retail-grade                 | Label provenance; Polygon upgrade path  |
| Opportunity scanner | `opportunity_scanner.py`                           | Median/MAD normalization — outlier-resistant **good** | Add decay half-life field               |
| Thompson sizing     | `thompson_sizing.py`                               | Small-n oversizing if shown early                     | Hide n&lt;5 — enforced in tests         |
| Self-learning       | `self_learning.py`                                 | Survivorship if only winners logged                   | Require closed-trade JSONL completeness |
| MetaEnsemble        | `learning_loop.py`                                 | Overfit on &lt;30 samples                             | min_sample=30; kill switch default ON   |
| Factor exposure     | `factor_exposure.py`                               | **Mock stub presented as factor** — critical          | Wire live or `degraded=true` hide       |
| ML advisory         | `ml_advisory_summary.py`                           | False precision on cards                              | `authority_note` on every ML surface    |
| Council pipeline    | `expert_council.py`                                | LLM narrative ≠ edge                                  | Council validates brief rows only       |

### Quant score: **6.5 / 10** (target 9.0)

**Biggest quant weaknesses:** retail data lag; no systematic forward-outcome calibration; mock factor on research surfaces; no EV Ranking 3.0 multiplicative decomposition wired.

**Bias checklist (pass/fail):**

- [x] AVOID never in monitor ranking (`build_playbook_rank_buckets`)
- [x] Brief rows cannot skip to TRADE without council
- [x] TRADE_RR_THRESHOLD static at 2.5
- [ ] All scores carry sample size on deploy surfaces
- [ ] Decay/staleness penalizes rank after 2 sessions
- [ ] Backtest grades never labeled live

---

## 4. Portfolio Review

### Current state

| Capability      | Module                                       | Status                                             |
| --------------- | -------------------------------------------- | -------------------------------------------------- |
| Book analytics  | `portfolio_decision_console.py`              | Strong operator copy; local vs broker truth honest |
| Positions       | `portfolio_positions.py`                     | Manual + IBKR partial                              |
| Risk cockpit    | `portfolio_risk_cockpit.py`                  | Heat, stop breach                                  |
| Factor exposure | `factor_exposure.py`                         | **Mock stub**                                      |
| Fit scoring     | `portfolio_fit.py`                           | Heuristic                                          |
| Correlation     | `engines/correlation_risk.py`                | Sector buckets                                     |
| Allocator       | `strategy_allocator.py`, `core_satellite.py` | Sleeve weights advisory                            |
| Drawdown        | `drawdown_sizer.py`, `drawdown_breaker.py`   | Tested; partial UI wire                            |
| Crisis          | `crisis_portfolio_survival.py`               | Regime stress                                      |
| Replacement     | _not built_                                  | Sprint 124                                         |

### Portfolio score: **6.5 / 10** (target 9.0)

**Honest limitations preserved:** `_LOCAL_ONLY_COPY` / `_BROKER_OFFLINE_COPY` in portfolio console prevent false broker sync confidence.

**Critical gap:** No capital allocation engine answering _where next $10K goes_ or _what to sell first_ — designed in CC X, not shipped.

**Sector cap:** `risk_limits.max_sector_pct` exists; quick-add UI enforcement incomplete (`portfolio.py` router).

---

## 5. Opportunity Intelligence Review

### Current state (v2 foundation + Sprint 114)

| Component           | Path                                          | Authority                   |
| ------------------- | --------------------------------------------- | --------------------------- |
| Opportunity Scanner | `src/engines/opportunity_scanner.py`          | Research → Discovery        |
| Intelligence API    | `src/api/routers/opportunity_intelligence.py` | `research_only`             |
| Insider / 13F       | `insider_tracker.py`, `institutional_13f.py`  | Lag-labeled                 |
| Capacity            | `capacity_intelligence.py`                    | Downgrade-only              |
| Playbook universe   | `playbook_signal_universe.py`                 | WATCH cap on brief rows     |
| Telegram opp alerts | `opportunity_telegram_alerts.py`              | Deploy-gated; tests present |

### Opportunity score: **7.0 / 10** (target 9.0)

**Strengths:** Neal dual-engine scanner; median/MAD normalization; provenance via `signal_provenance.py`; Telegram bridge with trade-bar validation.

**Gaps:**

1. No persistent `artifact_id` linking scanner → dossier → playbook row.
2. No theme/macro clustering on Discovery board.
3. Opportunity Intelligence not embedded in Dossier 360 (API exists; UI chips sparse).
4. No explicit score decay / half-life on scanner output.

**v3 design:** See `CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md` §3 — all outputs `may_authorize_deploy: false`.

---

## 6. Learning Review

### Current state

| Component           | Path                      | Status                            |
| ------------------- | ------------------------- | --------------------------------- |
| Decision Journal    | `decision_persistence.py` | JSONL append                      |
| Learning Loop       | `learning_loop.py`        | Closed trades JSONL; MetaEnsemble |
| Self-Learning       | `self_learning.py`        | min_sample=30; audit log          |
| Feature IC          | `feature_ic.py`           | Decay alerts advisory             |
| Thompson            | `thompson_sizing.py`      | Arms need closed-trade feedback   |
| Forward outcomes    | _missing_                 | Sprint 118                        |
| AlphaObject lessons | `alpha_object.py` schema  | Not wired to close loop           |

### Learning score: **6.0 / 10** (target 8.5)

**Rules (preserved):** Self-learning never auto-applies without Ops toggle + n≥30. Threshold changes require changelog — **no auto-loosen**.

**Gap:** IBKR paper fills → `closed_trades.jsonl` capture rate unverified; Brier calibration not tracked systematically.

---

## 7. AI Review

| Surface         | Module                                    | Measurable today           | Gap                                 |
| --------------- | ----------------------------------------- | -------------------------- | ----------------------------------- |
| LLMs            | `ai_service.py`, `catalyst_summarizer.py` | Narrative latency          | No quality score vs outcomes        |
| ML ranking      | MetaEnsemble                              | Win rate when n≥30         | n usually &lt;30                    |
| Scoring         | `opportunity_scanner.py`, council         | Funnel conversion          | No labeled outcome dataset at scale |
| Learning        | `self_learning.py`                        | Adjustments logged         | Apply rate ~0 in prod               |
| Explanation     | BDR, provenance                           | Operator sentence accuracy | ML weights opaque on cards          |
| Vibe Agent      | `vibe_agent.py`                           | Intent → rules             | Monitor only — **good**             |
| Trade review AI | `trade_review_ai_service.py`              | Post-trade narrative       | Not linked to AlphaObject           |

### AI score: **5.5 / 10** (target 8.5)

**Hard AI rules:** No GPT/LLM output changes `action` or `deploy_open`. Simulation grades `research_only` on btlab.

**12-month targets:** Brier &lt;0.22; closed-trade sample ≥50; explanation coverage ≥90% on Playbook cards.

---

## 8. Performance Review (Latency Targets)

All optimizations preserve server-authoritative gates — cache affects **latency only**, never **permission**.

| Surface                  | Current (Observed/Inferred) | Target                     | Module                                         | Authority impact    |
| ------------------------ | --------------------------- | -------------------------- | ---------------------------------------------- | ------------------- |
| Playbook ranked (cached) | 8–15s live scan days        | **&lt;1.5s** p95 cache hit | `playbook_ranked_snapshot.json`, `playbook.py` | Stale banner if old |
| Playbook ranked (live)   | 8–15s                       | **&lt;2s** p95 with SWR    | Snapshot writer universal                      | None                |
| Today load               | 3–5s                        | **&lt;800ms**              | `_cc_instant.py`, gzip                         | None                |
| Dossier core             | Partial instant             | **&lt;500ms** core fields  | `live_dossier.py`                              | None                |
| cc-header poll           | 15s health + 60s freshness  | **1 poll** unified         | `cc_header.py`, `decision_board_service.py`    | Improves truth      |
| Opportunity scan         | 5 min file cache            | Redis/in-memory TTL        | `opportunity_scanner.py`                       | None                |
| API QPS                  | Multi-tab poll storm        | **−40%**                   | Poll consolidation                             | None                |

### Performance score: **5.5 / 10** (target 8.5)

**Forbidden optimizations:** skip gate computation; cache `deploy_open=true`; client-side rank bypass.

---

## 9. UX Review

| Area            | Assessment                        | Evidence                                          |
| --------------- | --------------------------------- | ------------------------------------------------- |
| Navigation      | Good tab model                    | `surface_authority.py` TAB_SURFACE_MAP            |
| Density         | Bloomberg-adjacent Playbook/Today | BDR strip, funnel KPIs                            |
| Authority UX    | Strong                            | Pills, strips, degraded banners                   |
| Workflow        | Documented Operator OS flow       | Guide Layer 1                                     |
| Keyboard        | Weak — no ⌘K palette              | Missing command launcher                          |
| i18n            | Partial                           | `cc-i18n.js`; API strings English on non-Ops tabs |
| Telegram mobile | New — bilingual alerts            | `telegram.py` BRAND_HEADER/FOOTER                 |
| Multi-monitor   | Sticky BDR; no detached panels    | Today only                                        |
| Provenance bar  | Missing on prices                 | Sprint 116                                        |

### UX score: **7.0 / 10** (target 9.0)

**Do not:** add deploy buttons to research tabs; hide blockers without session ack.

---

## 10. Testing Review

### Current coverage (182 test files)

| Category           | Status     | Key tests                                                               |
| ------------------ | ---------- | ----------------------------------------------------------------------- |
| Unit               | Strong     | `test_decision_truth_model.py`, `test_operator_state_contract.py`       |
| Authority/contract | Strong     | `test_quant_authority_boundaries.py`, `test_vnext_truthful_surfaces.py` |
| Decision board     | **New**    | `test_decision_board_service.py`                                        |
| Telegram           | **New**    | `test_telegram_opportunity.py`, `test_alert_deploy_gate.py`             |
| UI render          | Medium     | `test_ui_render_integrity.py`, `test_playbook_render_integrity.py`      |
| E2E Playwright     | **Absent** | Sprint 120                                                              |
| Performance k6     | **Absent** | Sprint 117                                                              |
| Chaos IBKR         | **Absent** | Sprint 118+                                                             |

### Testing score: **7.0 / 10** (target 9.0)

**CI gate:** `python -m pytest tests/ -q` + `scripts/verify_10_10.sh` on every PR.

**Property test (existing):** AVOID never in `monitor_rows`.

---

## 11. Commercial Review

**Sell:** _The only AI investment OS that won't let you lie to yourself about deploy authority._

**Target customer:** Solo PM or 2–5 person pod on IBKR, $500K–$10M AUM.

| Buyer lens              | CC today         | Gap                  | Moat                       |
| ----------------------- | ---------------- | -------------------- | -------------------------- |
| Bloomberg               | yfinance delayed | Data entitlements    | Gate logic, BDR workflow   |
| Renaissance             | feature_ic seeds | Sample size          | Honest ML subordination    |
| Professional PM         | Local book JSONL | Audited track record | Operator OS UX             |
| Institutional allocator | No RBAC/export   | Governance           | Attribution tree (planned) |

### Commercial score: **6.5 / 10** (target 8.5)

**Do not claim:** HFT, prop-shop alpha, Terminal replacement, auto-trading.

---

## 12. Security Review

| Area                 | Status              | Evidence / action                     |
| -------------------- | ------------------- | ------------------------------------- |
| API auth             | Dev key in compose  | `API_SECRET_KEY`; prod must rotate    |
| Secrets in code      | Clean — env vars    | Telegram `TELEGRAM_BOT_TOKEN` via env |
| Telegram HTML escape | **Good**            | `escape_html()` in `telegram.py`      |
| Input validation     | Ticker regex        | `validate_ticker()` in telegram       |
| User input in paths  | Rules followed      | Secure Python rules in AGENTS         |
| RBAC / audit ledger  | Not started         | Tier 3 enterprise                     |
| IBKR credentials     | Env vars            | Never logged                          |
| Discord 403          | Documented          | Webhook preferred                     |
| Rate limiting        | Dev mode relaxed    | `CC_ENV=development`                  |
| Dependency audit     | Not in review scope | Run `pip audit` in CI                 |

### Security score: **6.5 / 10** (target 8.5)

**Telegram risk:** Bot token in `.env` — ensure not committed; `notify.py` status endpoint must not leak token.

---

## Subsystem Detail Templates

### Knowledge Engine

| Field               | Value                                                                   |
| ------------------- | ----------------------------------------------------------------------- |
| Current Score       | 4.5 / 10                                                                |
| Target Score        | 9.0 / 10                                                                |
| Biggest Weaknesses  | No `knowledge_graph.py`, no `analog_engine.py`; AlphaObject schema only |
| Expected ROI        | Thesis calibration; +0.2–0.4 Sharpe from analog recall                  |
| Difficulty          | High                                                                    |
| Risk                | Graph rank mistaken for deploy if authority slips                       |
| Dependencies        | AlphaObject birth (117), price history index                            |
| Acceptance Criteria | Analog API n≥5 or `confidence: low`; research_only                      |
| Recommended Sprint  | 121                                                                     |

### Research Engine

| Field               | Value                                              |
| ------------------- | -------------------------------------------------- |
| Current Score       | 6.5 / 10                                           |
| Target Score        | 9.0 / 10                                           |
| Biggest Weaknesses  | No Alpha Factory artifact writer; EV 3.0 not wired |
| Expected ROI        | 30–45 min/day on scan days; audit trail            |
| Difficulty          | Medium                                             |
| Risk                | Stale cache without banner                         |
| Dependencies        | Decision board SSOT, provenance                    |
| Acceptance Criteria | 100% top-12 rows have `artifact_id`                |
| Recommended Sprint  | 117                                                |

### Decision Engine

| Field               | Value                                                            |
| ------------------- | ---------------------------------------------------------------- |
| Current Score       | 7.5 / 10                                                         |
| Target Score        | 9.5 / 10                                                         |
| Biggest Weaknesses  | Attribution root not on board rows; `main.py` inline routes      |
| Expected ROI        | +$15–40K/yr avoided deploy mismatch                              |
| Difficulty          | Medium                                                           |
| Risk                | Low — strengthens gates                                          |
| Dependencies        | `operator_state_contract.py`, `decision_board_service.py`        |
| Acceptance Criteria | Three endpoints identical `deploy_open`; attribution ref on rows |
| Recommended Sprint  | 115 (complete)                                                   |

### Portfolio Engine

| Field               | Value                                                 |
| ------------------- | ----------------------------------------------------- |
| Current Score       | 6.5 / 10                                              |
| Target Score        | 9.0 / 10                                              |
| Biggest Weaknesses  | Mock factor; no replacement engine; sector cap UI gap |
| Expected ROI        | +$5–15K/yr concentration avoidance                    |
| Difficulty          | Medium–High                                           |
| Risk                | Fit score misleading if factor mock                   |
| Dependencies        | Live factor wire (122), IO portfolio_impact           |
| Acceptance Criteria | Sell-first ranked; human confirm; no auto-trade       |
| Recommended Sprint  | 122, 124                                              |

### Execution Engine

| Field               | Value                                            |
| ------------------- | ------------------------------------------------ |
| Current Score       | 6.0 / 10                                         |
| Target Score        | 8.5 / 10                                         |
| Biggest Weaknesses  | Docker dev skips IB; reconnect storms untested   |
| Expected ROI        | Slippage reduction; execution quality score feed |
| Difficulty          | Medium                                           |
| Risk                | Handoff failure during disconnect                |
| Dependencies        | `ibkr_service.py`, `execution_analytics.py`      |
| Acceptance Criteria | HARD blocks handoff; fill vs plan logged         |
| Recommended Sprint  | 118                                              |

### Intelligence Engine

| Field               | Value                                             |
| ------------------- | ------------------------------------------------- |
| Current Score       | 3.0 / 10                                          |
| Target Score        | 9.0 / 10                                          |
| Biggest Weaknesses  | Not implemented; no platform_smarter_today metric |
| Expected ROI        | Process alpha visibility; operator trust          |
| Difficulty          | Medium                                            |
| Risk                | Must not emit trade recommendations               |
| Dependencies        | All quality score inputs (126)                    |
| Acceptance Criteria | Seven scores; `authority: research_only`          |
| Recommended Sprint  | 126                                               |

### Investment Object

| Field               | Value                                                        |
| ------------------- | ------------------------------------------------------------ |
| Current Score       | 5.0 / 10                                                     |
| Target Score        | 9.0 / 10                                                     |
| Biggest Weaknesses  | Schema stub; no consumer wire                                |
| Expected ROI        | Eliminates cross-surface field drift                         |
| Difficulty          | Medium                                                       |
| Risk                | Authority regression if deploy_eligible set outside Decision |
| Dependencies        | Adapter from `DecisionObject`                                |
| Acceptance Criteria | Only Decision Engine sets `deploy_eligible=true`             |
| Recommended Sprint  | 119                                                          |

### AlphaObject

| Field               | Value                                          |
| ------------------- | ---------------------------------------------- |
| Current Score       | 5.5 / 10                                       |
| Target Score        | 9.0 / 10                                       |
| Biggest Weaknesses  | Stub only; no factory birth or lifecycle close |
| Expected ROI        | Institutional memory; faster post-mortems      |
| Difficulty          | Medium                                         |
| Risk                | None on authority — always research_only       |
| Dependencies        | Alpha Factory (117), learning close (125)      |
| Acceptance Criteria | `may_authorize_deploy=false` always            |
| Recommended Sprint  | 117, 125                                       |

### Authority/Governance

| Field               | Value                                                      |
| ------------------- | ---------------------------------------------------------- |
| Current Score       | 8.0 / 10                                                   |
| Target Score        | 9.5 / 10                                                   |
| Biggest Weaknesses  | Residual client-side reconciliation; inline main.py routes |
| Expected ROI        | Unbounded — prevents capital errors                        |
| Difficulty          | Medium                                                     |
| Risk                | Low                                                        |
| Dependencies        | Board SSOT, CI authority cluster                           |
| Acceptance Criteria | Authority test cluster green every PR                      |
| Recommended Sprint  | 115–116                                                    |

### Data Provenance

| Field               | Value                                              |
| ------------------- | -------------------------------------------------- |
| Current Score       | 5.5 / 10                                           |
| Target Score        | 9.0 / 10                                           |
| Biggest Weaknesses  | yfinance primary; optional provenance on prices    |
| Expected ROI        | Institutional credibility                          |
| Difficulty          | Medium                                             |
| Risk                | STALE behavior must remain                         |
| Dependencies        | `market_data.py`, `brief_data_service.py`          |
| Acceptance Criteria | 100% price fields labeled; STALE hides deploy CTAs |
| Recommended Sprint  | 116                                                |

### ML/Learning

| Field               | Value                                   |
| ------------------- | --------------------------------------- |
| Current Score       | 5.5 / 10                                |
| Target Score        | 8.5 / 10                                |
| Biggest Weaknesses  | Sample &lt;30; forward outcomes missing |
| Expected ROI        | +$8–20K/yr sizing calibration           |
| Difficulty          | Medium–High                             |
| Risk                | Auto-apply weights — **forbidden**      |
| Dependencies        | Closed trades JSONL, scheduler          |
| Acceptance Criteria | Thompson hidden n&lt;5; kill switch ON  |
| Recommended Sprint  | 118                                     |

### Opportunity Intelligence

| Field               | Value                                      |
| ------------------- | ------------------------------------------ |
| Current Score       | 7.0 / 10                                   |
| Target Score        | 9.0 / 10                                   |
| Biggest Weaknesses  | No artifact_id chain; sparse Dossier embed |
| Expected ROI        | 20 min/day research                        |
| Difficulty          | Medium                                     |
| Risk                | Low — research_only                        |
| Dependencies        | v3 API, dossier router                     |
| Acceptance Criteria | 90+ day lag labels; zero mock on deploy    |
| Recommended Sprint  | 119                                        |

### Alpha Factory

| Field               | Value                                              |
| ------------------- | -------------------------------------------------- |
| Current Score       | 5.0 / 10                                           |
| Target Score        | 8.5 / 10                                           |
| Biggest Weaknesses  | No per-candidate JSON artifacts                    |
| Expected ROI        | Audit trail; AlphaObject spawn                     |
| Difficulty          | Medium                                             |
| Risk                | Factory output ≠ permission — enforce              |
| Dependencies        | `artifacts/performance_artifact_writer.py` pattern |
| Acceptance Criteria | Artifacts in `data/artifacts/alpha_factory/`       |
| Recommended Sprint  | 117                                                |

### IBKR/Execution

| Field               | Value                                               |
| ------------------- | --------------------------------------------------- |
| Current Score       | 6.0 / 10                                            |
| Target Score        | 8.5 / 10                                            |
| Biggest Weaknesses  | `CC_SKIP_IB_INSYNC=1` in dev; handoff audit partial |
| Expected ROI        | Execution quality attribution                       |
| Difficulty          | Medium                                              |
| Risk                | Failed brackets on reconnect                        |
| Dependencies        | `ibkr_session_manager.py`                           |
| Acceptance Criteria | MONITOR→READY ladder honest                         |
| Recommended Sprint  | 118                                                 |

### Ops/Scheduler

| Field               | Value                                       |
| ------------------- | ------------------------------------------- |
| Current Score       | 7.0 / 10                                    |
| Target Score        | 8.5 / 10                                    |
| Biggest Weaknesses  | No Alpha QA panel; learning jobs incomplete |
| Expected ROI        | Probe vs runtime trust                      |
| Difficulty          | Low–Medium                                  |
| Risk                | Warmup mode confusion                       |
| Dependencies        | `scheduler/main.py` (715 lines)             |
| Acceptance Criteria | Ops shows Brier, IC decay, calibration      |
| Recommended Sprint  | 118                                         |

### UI/UX

| Field               | Value                                |
| ------------------- | ------------------------------------ |
| Current Score       | 7.0 / 10                             |
| Target Score        | 9.0 / 10                             |
| Biggest Weaknesses  | Monolith parse; no ⌘K; i18n gaps     |
| Expected ROI        | 15 min/day navigation                |
| Difficulty          | Medium                               |
| Risk                | Hydration if partial split wrong     |
| Dependencies        | `build-cc-template.mjs`              |
| Acceptance Criteria | Command palette v0; provenance strip |
| Recommended Sprint  | 120                                  |

### Testing/CI

| Field               | Value                         |
| ------------------- | ----------------------------- |
| Current Score       | 7.0 / 10                      |
| Target Score        | 9.0 / 10                      |
| Biggest Weaknesses  | No E2E; no perf gate          |
| Expected ROI        | Regression safety             |
| Difficulty          | Medium                        |
| Risk                | Flaky E2E if not hermetic     |
| Dependencies        | Docker CI, Playwright         |
| Acceptance Criteria | WAIT → deploy disabled in E2E |
| Recommended Sprint  | 120                           |

### Security

| Field               | Value                                     |
| ------------------- | ----------------------------------------- |
| Current Score       | 6.5 / 10                                  |
| Target Score        | 8.5 / 10                                  |
| Biggest Weaknesses  | No RBAC; dev API key in compose           |
| Expected ROI        | Enterprise adoption                       |
| Difficulty          | High (RBAC)                               |
| Risk                | Token leakage in logs                     |
| Dependencies        | Enterprise tier                           |
| Acceptance Criteria | No secrets in repo; Telegram escape tests |
| Recommended Sprint  | Tier 3                                    |

### Commercial Readiness

| Field               | Value                                 |
| ------------------- | ------------------------------------- |
| Current Score       | 5.5 / 10                              |
| Target Score        | 8.5 / 10                              |
| Biggest Weaknesses  | No export; local book truth           |
| Expected ROI        | Advisor workflow enablement           |
| Difficulty          | Medium                                |
| Risk                | Export must include disclaimer        |
| Dependencies        | Attribution tree (120)                |
| Acceptance Criteria | JSON/CSV export with authority footer |
| Recommended Sprint  | 120                                   |

---

## 13. Top 100 Improvements Ranked by ROI

Grouped by tier. ROI assumes single PM, $500K–$2M book, 200 trading days/year.

### Tier 1 — P0/P1 (ROI #1–20)

| #   | Improvement                                         | ROI                         | Diff | Sprint |
| --- | --------------------------------------------------- | --------------------------- | ---- | ------ |
| 1   | Complete DecisionBoardService SSOT (all surfaces)   | +$15–40K/yr                 | M    | 115    |
| 2   | Mandatory provenance `source/as_of/mode` on prices  | Institutional credibility   | M    | 116    |
| 3   | CI blocks authority regressions (`verify_10_10.sh`) | Unbounded risk reduction    | L    | 116    |
| 4   | Alpha Factory artifact per candidate                | 30–45 min/day               | M    | 117    |
| 5   | AlphaObject birth at hypothesis                     | Institutional memory        | M    | 117    |
| 6   | Universal playbook snapshot SWR p95 &lt;2s          | 30–45 min/day               | M    | 117    |
| 7   | IBKR → closed_trades.jsonl ≥95% capture             | +$8–20K/yr                  | M-H  | 118    |
| 8   | Forward outcomes T+1/T+5/T+20                       | Brier calibration           | M    | 118    |
| 9   | Real-Time Alpha Monitor (6 KPIs)                    | Measured alpha visibility   | M    | 118    |
| 10  | Thompson/ML hidden n&lt;5/n&lt;30 on cards          | False confidence prevention | L    | 118    |
| 11  | Opportunity Intel v3 Dossier embed                  | 20 min/day                  | M    | 119    |
| 12  | Institutional Research Workspace MVP                | 20 min/day unified view     | M-H  | 119    |
| 13  | InvestmentObject adapter (new paths)                | Schema SSOT                 | M    | 119    |
| 14  | Attribution root on board rows                      | Audit chain start           | M    | 115    |
| 15  | Playwright E2E WAIT → deploy disabled               | Regression safety           | M    | 120    |
| 16  | Board snapshot JSON/CSV export                      | Advisor workflow            | M    | 120    |
| 17  | Extract 25 largest `main.py` handlers               | −regression risk            | M    | 116    |
| 18  | Hide mock factor on deploy surfaces                 | Trust                       | L    | 116    |
| 19  | Sector cap blocks portfolio quick-add               | Concentration prevention    | M    | 122    |
| 20  | Telegram deploy-gate alerts production hardening    | Mobile ops                  | L    | 116    |

### Tier 2 — Foundation (ROI #21–50)

| #   | Improvement                               | ROI                       | Diff | Sprint  |
| --- | ----------------------------------------- | ------------------------- | ---- | ------- |
| 21  | Knowledge Graph MVP                       | Analog recall             | H    | 121     |
| 22  | Analog engine "looked like March 2024"    | Thesis calibration        | M    | 121     |
| 23  | EV Ranking 3.0 decomposition              | Capital-prioritized queue | M    | 122     |
| 24  | Capital Allocation panel                  | Next $10K visibility      | M-H  | 122     |
| 25  | Live factor wire (remove mock)            | Research integrity        | M    | 122     |
| 26  | `marginal_return_on_capital` on IO        | Allocator grade           | M    | 122     |
| 27  | Portfolio replacement rank                | +$5–15K/yr                | M    | 124     |
| 28  | `sell_first_candidates[]` on AlphaObject  | Swap discipline           | M    | 124     |
| 29  | AlphaObject lifecycle close               | Post-mortem speed         | M    | 125     |
| 30  | Research Memory index                     | Institutional recall      | M    | 125     |
| 31  | Attribution tree E2E                      | Full PnL trace            | M-H  | 120,125 |
| 32  | Intelligence Engine daily report          | Platform IQ               | M    | 126     |
| 33  | Command palette ⌘K v0                     | 10 min/day                | L-M  | 120     |
| 34  | Unified header poll (freshness piggyback) | −40% API QPS              | M    | 116     |
| 35  | gzip instant dashboard always             | Today &lt;800ms           | L    | 116     |
| 36  | yfinance async batch per scan             | Scan latency              | M    | 117     |
| 37  | Discovery theme clustering                | Hidden correlation        | M    | 119     |
| 38  | Scanner decay half-life chip              | Stale score prevention    | L    | 119     |
| 39  | `artifact_id` chain scan→playbook         | Audit trail               | M    | 117     |
| 40  | Merge decision journal SSOT               | Attribution               | L    | 118     |
| 41  | Shared `_norm_action` utility             | −400 dup lines            | L    | 115     |
| 42  | ProvenanceMixin on market fields          | Lineage                   | M    | 116     |
| 43  | Ops Alpha QA panel                        | IC decay review           | M    | 118     |
| 44  | Flow synthetic watermark persistent       | Narrative overweight fix  | L    | 116     |
| 45  | i18n Ops remaining strings                | HK operator UX            | M    | Tier 3  |
| 46  | Dossier instant core &lt;500ms            | Research speed            | M    | 117     |
| 47  | k6 playbook p95 CI gate                   | Perf regression           | M    | 117     |
| 48  | Chaos IBKR reconnect test                 | Handoff reliability       | M    | 118     |
| 49  | P2 cache tiered TTL                       | API load                  | L    | Tier 3  |
| 50  | Template partial split Today/Playbook     | Maintainability           | M    | Tier 3  |

### Tier 3 — Scale & polish (ROI #51–80)

| #   | Improvement                             | ROI                    | Diff | Sprint   |
| --- | --------------------------------------- | ---------------------- | ---- | -------- |
| 51  | Historical analog pattern library       | Fewer narrative trades | M    | 123      |
| 52  | Failure_mode on AlphaObject lessons     | Post-mortem quality    | L    | 123      |
| 53  | Pattern library n≥5 or low confidence   | Honest recall          | L    | 123      |
| 54  | Portfolio brain IO consumer             | Fit-delta sim          | M    | 122      |
| 55  | Crisis stress on portfolio tab          | Tail risk visibility   | L    | 122      |
| 56  | Drawdown sizer live wire                | Sizing discipline      | M    | 122      |
| 57  | Book-level capacity rollup              | Scale friction         | M    | 122      |
| 58  | Exit-days-at-20%-ADV helper             | Liquidity clarity      | L    | 122      |
| 59  | Hidden thematic concentration tagger    | AI overlap detection   | M    | 121      |
| 60  | Graph neighbor API                      | Research context       | M    | 121      |
| 61  | Alpha attribution tree export           | Governance             | M    | 120      |
| 62  | Self-learning audit log UI              | Transparency           | L    | 118      |
| 63  | Regime params versioned changelog       | Threshold governance   | L    | 118      |
| 64  | Shadow digest scheduled test            | Behavior audit         | L    | 120      |
| 65  | Walk-forward CI weekly                  | OOS regression         | M    | Tier 3   |
| 66  | LLM cost cap per ticker/day             | OpEx control           | L    | Tier 3   |
| 67  | Explanation `why` on 90% playbook cards | Operator trust         | M    | 119      |
| 68  | Near-miss consolidate in contract       | −dup logic             | L    | 115      |
| 69  | Server-render authority labels          | JS display only        | L    | 116      |
| 70  | Reduced motion for authority pulses     | A11y                   | L    | Tier 3   |
| 71  | Detached monitor Playbook+Dossier       | Multi-monitor PM       | L    | Tier 3   |
| 72  | Keyboard shortcuts G T/P/D              | Power user             | L    | 120      |
| 73  | Data contract strip on every price      | Bloomberg provenance   | M    | 116      |
| 74  | Redis horizontal scan fan-out           | Scale                  | H    | Tier 3   |
| 75  | SSE trigger vs 15s health poll          | Latency                | M    | Tier 3   |
| 76  | ARCHITECTURE.md CC-centric refresh      | Onboarding             | L    | Tier 3   |
| 77  | Discord research mute default preserved | Alert noise            | L    | Done     |
| 78  | System Telegram BDR/regime alerts       | Mobile gate awareness  | L    | Done     |
| 79  | Futu capture notify (if used)           | Alt broker path        | L    | Observed |
| 80  | Decision hub monitor payload unify      | −poll                  | M    | 115      |

### Tier 4 — Enterprise & 9.8+ vision (ROI #81–100)

| #   | Improvement                               | ROI                | Diff | Sprint    |
| --- | ----------------------------------------- | ------------------ | ---- | --------- |
| 81  | Enterprise RBAC                           | Commercial         | H    | Tier 3    |
| 82  | Audited P&L ledger                        | Institutional      | H    | Long-term |
| 83  | Multi-tenant book isolation               | SaaS               | H    | Long-term |
| 84  | Polygon primary with yfinance fallback    | Data quality       | M    | Tier 3    |
| 85  | Broker-synced book truth default          | PM trust           | H    | Long-term |
| 86  | Compliance export SOC2 path               | Enterprise         | H    | Long-term |
| 87  | Feature factory with IC governance        | Quant maturity     | H    | Long-term |
| 88  | Cross-asset knowledge graph               | Macro linkage      | H    | 121+      |
| 89  | Options flow live (Polygon)               | Flow quality       | M-H  | Tier 3    |
| 90  | Influencer layer structured overlay       | Supplemental intel | M    | Long-term |
| 91  | Multi-monitor detached panels             | UX                 | L    | Tier 3    |
| 92  | i18n completion all tabs                  | HK market          | M    | Tier 3    |
| 93  | PM Memory thesis drift auto-alerts        | Monitoring         | M    | 123       |
| 94  | Compare engine overlay                    | Relative value     | M    | Tier 3    |
| 95  | Rebalance sim portfolio embed             | Research           | L    | 122       |
| 96  | Validation lab → playbook row link        | Backtest ≠ live    | M    | 119       |
| 97  | Council outcome tracking                  | Calibration        | M    | 118       |
| 98  | Platform error log → Ops digest           | Reliability        | L    | 116       |
| 99  | TypedDict SystemState strict mypy         | Type safety        | M    | 116       |
| 100 | Investment Object full consumer migration | 9.5 architecture   | H    | 125       |

---

## Top 5 Recommendations (Full Template)

### #1 — Complete Decision Board Unification

| Field                | Detail                                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Problem**          | Client/server deploy state drift across Today, Playbook, header                                                |
| **Evidence**         | `cc-app.js` multi-poll; `DecisionBoardService` partial — wired in `decision.py`, `playbook.py`, `cc_header.py` |
| **Root Cause**       | Historically independent payload builders per surface                                                          |
| **Business Impact**  | Wrong-size or wrong-day deploy attempts                                                                        |
| **Operator Impact**  | 15 min/day reconciliation; trust erosion                                                                       |
| **Expected ROI**     | +$15–40K/yr                                                                                                    |
| **Risk**             | Low                                                                                                            |
| **Difficulty**       | Medium                                                                                                         |
| **Priority**         | P0                                                                                                             |
| **Affected Files**   | `decision_board_service.py`, `decision.py`, `playbook.py`, `cc_header.py`, `cc-app.js`                         |
| **Migration Plan**   | Server-only `deploy_open`; client display-only; deprecate local reconcile                                      |
| **Acceptance Tests** | `test_decision_board_service.py` parametrize WAIT/STALE/broker; three endpoints identical hash                 |
| **Rollback Plan**    | Revert router attach; keep `build_decision_board` — no gate logic change                                       |

### #2 — Evidence Lineage Gate (Provenance CI)

| Field                | Detail                                                                           |
| -------------------- | -------------------------------------------------------------------------------- |
| **Problem**          | Retail data without mandatory lineage labels                                     |
| **Evidence**         | yfinance primary; `ProvenanceBlock` in IO schema but not enforced on live prices |
| **Root Cause**       | Incremental feature growth without ProvenanceMixin                               |
| **Business Impact**  | Institutional adoption blocker                                                   |
| **Operator Impact**  | Silent stale prices → bad entries                                                |
| **Expected ROI**     | Credibility + ~0.2 Sharpe from better entries                                    |
| **Risk**             | Low                                                                              |
| **Difficulty**       | Medium                                                                           |
| **Priority**         | P0                                                                               |
| **Affected Files**   | `market_data.py`, `brief_data_service.py`, `decision.py`, CI workflow            |
| **Migration Plan**   | Additive fields; STALE behavior unchanged                                        |
| **Acceptance Tests** | STALE hides deploy CTAs; contract test failure blocks CI                         |
| **Rollback Plan**    | Provenance fields optional fallback — gates unchanged                            |

### #3 — Alpha Factory + AlphaObject Birth

| Field                | Detail                                                                    |
| -------------------- | ------------------------------------------------------------------------- |
| **Problem**          | No persistent hypothesis artifact from scan → deploy                      |
| **Evidence**         | `alpha_object.py` stub; no `data/artifacts/alpha_factory/` writer         |
| **Root Cause**       | Research pipeline ends at rank, not artifact                              |
| **Business Impact**  | No audit trail; no institutional memory                                   |
| **Operator Impact**  | 30–45 min/day re-research on scan days                                    |
| **Expected ROI**     | Time + audit                                                              |
| **Risk**             | Medium — must stay research_only                                          |
| **Difficulty**       | Medium                                                                    |
| **Priority**         | P1                                                                        |
| **Affected Files**   | `opportunity_scanner.py`, `alpha_object.py`, `artifacts/*`, `playbook.py` |
| **Migration Plan**   | Write-only sidecar; rank logic unchanged                                  |
| **Acceptance Tests** | 100% top-12 have `artifact_id` + `alpha_id`                               |
| **Rollback Plan**    | Disable writer; playbook uses legacy rank                                 |

### #4 — Learning Loop Closure + Forward Outcomes

| Field                | Detail                                                                                |
| -------------------- | ------------------------------------------------------------------------------------- |
| **Problem**          | Closed trades not reliably feeding ML; no forward marks                               |
| **Evidence**         | `learning_loop.py` reads JSONL; IBKR capture unverified; no `forward_outcomes.py`     |
| **Root Cause**       | Execution layer not wired to learning scheduler jobs                                  |
| **Business Impact**  | Sample-starved ML; miscalibrated sizing                                               |
| **Operator Impact**  | Thompson/self-learn show insufficient_sample                                          |
| **Expected ROI**     | +$8–20K/yr                                                                            |
| **Risk**             | Medium — must not auto-apply                                                          |
| **Difficulty**       | Medium–High                                                                           |
| **Priority**         | P1                                                                                    |
| **Affected Files**   | `learning_loop.py`, `ibkr_service.py`, `scheduler/main.py`, new `forward_outcomes.py` |
| **Migration Plan**   | Nightly job; advisory-only ML                                                         |
| **Acceptance Tests** | Sim fill appends JSONL; kill switch default ON                                        |
| **Rollback Plan**    | Disable scheduler job; JSONL append-only preserved                                    |

### #5 — Real-Time Alpha Monitor

| Field                | Detail                                                    |
| -------------------- | --------------------------------------------------------- |
| **Problem**          | Platform optimizes signal counts, not measured alpha      |
| **Evidence**         | CC X doc defines 6 KPIs; no `alpha_monitor.py`            |
| **Root Cause**       | Engineering-first metrics legacy                          |
| **Business Impact**  | Cannot prove process alpha                                |
| **Operator Impact**  | Ops shows engine stats not alpha produced/lost            |
| **Expected ROI**     | Process visibility → better discipline                    |
| **Risk**             | Low — research_only                                       |
| **Difficulty**       | Medium                                                    |
| **Priority**         | P1                                                        |
| **Affected Files**   | New `alpha_monitor.py`, `ops_operator_console.py`, Ops UI |
| **Migration Plan**   | Ops panel additive                                        |
| **Acceptance Tests** | Six KPIs visible; authority research_only                 |
| **Rollback Plan**    | Hide panel; no gate impact                                |

---

## 14. Next 10 Sprint Roadmap (116–125)

| Sprint  | Headline                                                                    | P   | Key deliverables                                                                          |
| ------- | --------------------------------------------------------------------------- | --- | ----------------------------------------------------------------------------------------- |
| **116** | **Market Data → Evidence chain — CI blocks authority regressions**          | P0  | ProvenanceMixin; CI full pytest + verify_10_10; mock factor hide; main.py extract batch 1 |
| **117** | **Every candidate gets an AlphaObject — auditable hypothesis from day one** | P1  | Alpha Factory writer; AlphaObject spawn; playbook SWR p95 &lt;2s; k6 gate                 |
| **118** | **Alpha Produced/Lost/Preserved today — not signal counts**                 | P1  | `alpha_monitor.py`; `forward_outcomes.py`; IBKR→JSONL; Ops Alpha QA                       |
| **119** | **One investment, eleven tabs — workspace not bigger Dossier**              | P1  | Institutional workspace MVP; Opp Intel v3 embed; IO adapter                               |
| **120** | **PnL → Market Data traceability — Playwright + audit export**              | P1  | `attribution_tree.py`; E2E CI; board export; ⌘K v0                                        |
| **121** | **CC remembers — analog hits with failure modes**                           | P1  | `knowledge_graph.py` MVP; `analog_engine.py`; theme clustering                            |
| **122** | **Where next $10K goes — marginal ROC after cost and fit**                  | P1  | Capital allocation panel; `ev_ranking.py`; live factor; sector cap UI                     |
| **123** | **Pattern library with n, date range, outcome R**                           | P2  | Enriched analogs; failure_mode lessons; Knowledge tab only                                |
| **124** | **What to sell first — fit-delta and marginal ROC ranked**                  | P2  | Replacement chip; `sell_first_candidates[]`; human confirm                                |
| **125** | **Hypothesis → outcome → lesson — AlphaObject archived forever**            | P2  | Lifecycle close; Research Memory index; attribution complete                              |

Sprint **115** (in progress): Capital-First Decision Board + Attribution Root — `DecisionBoardService` landed; complete attribution ref on all rows.

Sprint **126** (follow-on): Intelligence Engine CEO Dashboard — seven quality scores + `platform_smarter_today`.

---

## 15. Horizon Buckets

### Quick wins (&lt;1 day each)

| Item                                               | Files                                     | ROI                  |
| -------------------------------------------------- | ----------------------------------------- | -------------------- |
| Thompson/ML hide n&lt;5 on Ops/cards               | `ml_advisory_summary.py`, `cc-helpers.js` | Trust                |
| Flow synthetic diagonal watermark                  | `flow_decision_surface.py`, CSS           | Narrative discipline |
| Mock factor `degraded=true` on Portfolio           | `factor_exposure.py`, portfolio router    | Trust                |
| Telegram dedupe tune `TELEGRAM_ALERT_COOLDOWN_SEC` | `telegram.py`                             | Alert noise          |
| gzip dashboard always serve                        | `_cc_instant.py`                          | Today load           |
| Authority label server-render pass 1               | `surface_authority.py`                    | −JS drift            |

### High ROI (&lt;1 week each)

| Item                            | Sprint | ROI               |
| ------------------------------- | ------ | ----------------- |
| Decision board SSOT completion  | 115    | +$15–40K/yr       |
| Provenance on all price fields  | 116    | Credibility       |
| CI authority gate on every PR   | 116    | Regression safety |
| Playbook universal snapshot SWR | 117    | 30–45 min/day     |
| Sector cap quick-add block      | 122    | Concentration     |
| Unified header poll             | 116    | −40% QPS          |
| Command palette v0              | 120    | 10 min/day        |

### Major (&lt;1 month each)

| Item                                 | Sprint  | ROI                |
| ------------------------------------ | ------- | ------------------ |
| Alpha Factory + AlphaObject birth    | 117     | Memory + audit     |
| Forward outcomes + closed trade loop | 118     | +$8–20K/yr         |
| Institutional workspace MVP          | 119     | 20 min/day         |
| Attribution tree E2E                 | 120,125 | Governance         |
| Knowledge graph + analog engine      | 121     | Thesis calibration |
| Capital allocation + EV 3.0          | 122     | Deployment quality |
| Portfolio replacement engine         | 124     | +$5–15K/yr         |

### Long-term vision (9.8–10.0)

- **Measured alpha platform:** every decision resolves through Attribution Tree to market data; Alpha Monitor drives daily Ops review.
- **Institutional memory:** AlphaObject archive with analog recall — "CC remembers, not GPT."
- **Intelligence Engine:** daily `platform_smarter_today` with seven quality scores — CEO dashboard for AI, not trade generator.
- **Broker-synced book truth** with honest local-book fallback.
- **Enterprise RBAC + audited export** for allocator/advisor workflows.
- **Polygon-primary data** with provenance and degraded fallback ladder.
- **Sample-rich ML** (n≥50 closed trades) advisory-only with full audit trail.
- **Sub-second Playbook** cache-hit with live-scan freshness indicators.
- **Zero authority drift** — E2E CI proves WAIT blocks deploy on every release.

---

## Appendix — Key Module Index

| Domain            | Primary modules                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------- |
| Investment Object | `src/core/investment_object.py`, `engines/decision_object.py`                                 |
| Alpha Object      | `src/core/alpha_object.py`                                                                    |
| Decision Board    | `src/services/decision_board_service.py`                                                      |
| Authority         | `operator_state_contract.py`, `decision_truth_model.py`, `surface_authority.py`               |
| Telegram          | `notifications/telegram.py`, `opportunity_telegram_alerts.py`, `system_telegram_alerts.py`    |
| Opportunity       | `engines/opportunity_scanner.py`, `api/routers/opportunity_intelligence.py`                   |
| Portfolio         | `portfolio_decision_console.py`, `portfolio_fit.py`, `strategy_allocator.py`                  |
| Learning          | `learning_loop.py`, `self_learning.py`, `feature_ic.py`                                       |
| Scheduler         | `src/scheduler/main.py`                                                                       |
| UI                | `index.html`, `cc-app.js`, `cc-i18n.js`                                                       |
| Tests             | 182 files; authority cluster under `tests/test_*authority*`, `test_decision_board_service.py` |

---

## Relation to Prior Documents

This review **executes** [`CC_X_MASTER_REVIEW_PROMPT.md`](./CC_X_MASTER_REVIEW_PROMPT.md) and **extends** [`CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md`](./CC_VNEXT_INSTITUTIONAL_MASTER_REVIEW.md) (7.0) and [`CC_X_INSTITUTIONAL_ALPHA_OS.md`](./CC_X_INSTITUTIONAL_ALPHA_OS.md) with code-verified progress on DecisionBoardService, AlphaObject/InvestmentObject stubs, and Telegram alerts. Overall score **7.2** reflects incremental authority hardening without closing data/ML/Intelligence gaps.

---

_End of CC X Full Institutional Review._
