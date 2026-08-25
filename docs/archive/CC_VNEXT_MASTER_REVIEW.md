# Clarity Console vNext — Institutional AI Trading Platform Master Review

**Document:** `docs/CC_VNEXT_MASTER_REVIEW.md`  
**Product:** CC (Clarity Console) · `TradingAI_Bot` repo  
**Version reviewed:** 9.0.0 (`src/core/version.py`)  
**Review date:** 2026-08-25  
**Branch context:** `cc/upgrade-regime-tracking` (recent: BDR brief, screening yield, 1R sizing, deploy gate tightening)  
**Method:** Full-repo architecture read — `docs/CC_CONSOLIDATED_BRIEFING.md`, `docs/ARCHITECTURE.md`, authority/decision/risk/playbook/discovery/ML modules, `index.html` / `cc-app.js`, 175 test files, Docker/ops, recent sprint work. **No runtime pytest executed on host** (per briefing §6).

---

## Non-Negotiable Constraints (Preserved Throughout)

This review **does not** recommend auto-deploy, risk weakening, uncertainty hiding, or card-rank overrides of page gates. All recommendations assume:

| Principle                     | Current enforcement                                                                                          |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Operator Decision OS**      | Daily flow: Dashboard → Playbook → Dossier → Portfolio → IBKR/Ops (`index.html` Guide Layer 1)               |
| **Page gate beats card rank** | `operator_state_contract.py` + Guide checklist; WAIT/NO_TRADE blocks deploy regardless of score              |
| **Research ≠ permission**     | Discovery/Flow/Funds/Agent/Shadow/Reports/Btlab = monitor/research only (`CC_CONSOLIDATED_BRIEFING.md` §2)   |
| **Threshold Governance**      | `decision_truth_model.py` TRADE_RR_THRESHOLD=2.5; brief-sourced rows capped at WATCH until council validates |
| **Alpha QA**                  | Probe vs runtime in `ops_operator_console.py`; funnel labels in `PLAYBOOK_FUNNEL_LAYER_DEFINITIONS`          |
| **Auditability**              | Self-learning audit log, Thompson/feature_ic JSON persistence, BDR from live state                           |
| **EV after costs/risk**       | `risk_limits.py` SSOT; cost-adjusted ranker tests; no excitement-first ranking                               |

---

## 1. Executive Review

### Overall Score: **6.8 / 10**

CC is a **credible small-team Operator Decision OS** with unusually strong authority boundaries for its size. It is **not** yet an institutional data/execution platform comparable to Bloomberg Terminal, FactSet, or a prop-shop stack — and the codebase is honest about many gaps (synthetic Flow, yfinance primary, insufficient ML sample). The score reflects **decision discipline above data depth**.

| Dimension                    | Score | Rationale                                                                                        |
| ---------------------------- | ----: | ------------------------------------------------------------------------------------------------ |
| Authority & decision truth   |   8.5 | `operator_state_contract.py`, `decision_truth_model.py`, rank buckets, BDR brief                 |
| Operator UX & honesty        |   7.5 | Global strip, degraded banners, probe/runtime table — undermined by i18n gaps                    |
| Screening & playbook funnel  |   7.0 | `playbook_signal_universe.py` yield fix; council gate still thin on WAIT days                    |
| Risk & sizing                |   7.0 | Unified `risk_limits.py`; Thompson/1R advisory not yet production-proven                         |
| Data & freshness             |   5.0 | yfinance-first; STALE/CRITICAL gates exist but source quality is retail-grade                    |
| Execution & IBKR             |   6.0 | Ladder + MONITOR badge solid; Docker dev skips IB; handoff not battle-tested                     |
| ML / self-learning           |   5.5 | Architecture present (`self_learning.py`, `feature_ic.py`, `thompson_sizing.py`); sample-starved |
| Architecture maintainability |   5.0 | `main.py` 6,281 lines; 8,350-line `index.html` + 8,535-line `cc-app.js`                          |
| Test coverage                |   7.0 | 175 test files, strong authority-boundary tests; integration/E2E thin                            |
| Institutional data breadth   |   4.0 | No enterprise fundamentals, low-latency feeds, or audited performance ledger at scale            |

### Strengths

1. **Authority contract is real code, not copy** — `build_system_state()` / `build_page_capability()` in `src/services/operator_state_contract.py` with tests in `tests/test_operator_state_contract.py`. Deploy requires `tradeability ∉ {WAIT,NO_TRADE}`, `should_trade`, `board_decision_state.state == DEPLOY`, and `gates_active == false`.

2. **Decision truth separation** — `decision_truth_model.py` explicitly separates macro / opportunity / execution; `format_board_quality_detail()` never labels scan-ranked names as watch-qualified.

3. **Screening yield without gate loosening** — `playbook_signal_universe.py` merges brief rows, tops up from live scan, enriches `rs_rank`; commit `26400c6` caps brief-sourced actions at WATCH until council validates.

4. **BDR operator brief** — `bdr_operator_summary.py` auto-generates investor-grade NOW/BLOCKER/NEXT from live state; surfaced on Today tab (`today7.bdr_summary`).

5. **Ops honesty model** — `ops_operator_console.py` distinguishes probe (disk brief OK) from runtime (engine cycle evidence); warmup degraded mode does not fake OK.

6. **Unified risk SSOT** — `src/core/risk_limits.py` resolves prior conflicts between position manager, portfolio budget, and inline magic numbers.

7. **Research pipeline with hard boundary** — Vibe Agent, Strategy Lab, Shadow, Reports (`research_pipeline.py`, `vibe_agent.py`) stop at Playbook review; `ml_advisory_summary.py` carries explicit `authority_note`.

8. **Test culture for trust** — Dedicated tests: `test_tracking_authority_boundaries.py`, `test_quant_authority_boundaries.py`, `test_vnext_truthful_surfaces.py`, `test_playbook_signal_universe.py`, `test_bdr_operator_summary.py`.

### Weaknesses

1. **Monolithic surfaces** — Single 16,885-line UI stack (`index.html` + `cc-app.js`); `src/api/main.py` at 6,281 lines absorbs router logic that should live in modules.

2. **Retail data dependency** — Primary OHLCV via yfinance; optional Polygon/Alpaca not default. Institutional allocators will reject unlabeled delayed/free feeds for deploy decisions.

3. **Flow is explicitly non-live** — Guide and `FLOW_OVERLAY_DEGRADED_HEADLINES` in `decision_truth_model.py` mark synthetic/offline flow; operators may still overweight colour.

4. **ML stack is warming, not earning** — `self_learning.py` requires ≥30 trades; Ops shows `insufficient_sample`; Thompson arms need closed-trade feedback loop wired to production.

5. **i18n is half-done** — `cc-i18n.js` augments ~300 static literals; Alpine `x-text` API strings remain English on non-Ops tabs (briefing §9).

6. **Architecture doc drift** — `docs/ARCHITECTURE.md` still centers 5,596-line Discord bot; CC FastAPI/dashboard path is the operator product but under-documented relative to Discord.

7. **Polling budget** — `cc-app.js` runs 15s health, 60s freshness/risk alerts, 120s Today/ranked/hub — acceptable locally, risky under yfinance rate limits at scale.

8. **Dual-product repo** — Discord bot + CC dashboard share engines but diverge in entrypoints; increases cognitive load and duplicate surface risk.

### Greatest Opportunities

1. **Compress to “one truth API”** — Consolidate Today + Playbook + header into a single versioned decision payload (`/api/v7/decision/board`) reducing client reconciliation bugs.

2. **Paid data tier with honest labels** — Polygon/Alpaca as opt-in `mode=LIVE` with provenance; keep yfinance as `mode=DEGRADED` not silent fallback.

3. **Alpha QA loop** — Wire closed trades → `learning_loop.py` → feature IC decay alerts → playbook weight down-rank (advisory first, never auto-deploy).

4. **Componentize UI** — `scripts/build-cc-template.mjs` already exists; split tab surfaces into partials (Guide already uses `cc/partials/guide.html` pattern).

5. **Institutional dossier depth** — `opportunity_intelligence.py` (insider/13F/events/strategy-health) is research-only foundation for single-name 360 without breaking authority.

### Greatest Risks

1. **False deploy confidence** — Operator sees ranked cards during brief fallback (`fallback_mode` in system state) and sizes before engine confirms — mitigated by strips but UX fatigue may cause override.

2. **Gate bypass via wrong tab** — Discovery/Flow high scores mistaken for TRADE permission despite Guide warnings — needs persistent surface badges on every card origin.

3. **main.py regression** — Any change to inline routes risks authority regression without contract tests on full HTTP responses.

4. **Sample-starved ML overtrust** — Thompson/self-learning displayed in Ops advanced diagnostics may imply edge where n&lt;30.

5. **IBKR handoff in production** — Bracket OCA path not proven under disconnect/reconnect storms; MONITOR vs HANDOFF READY confusion.

6. **Performance collapse on scan days** — `PLAYBOOK_LIVE_SCAN_LIMIT=120` + scanner matrix batch jobs can stall p95 playbook load.

---

## 2. Institutional Gap Analysis

Comparison against representative institutional workflows. CC is evaluated as an **operator decision OS for a disciplined PM**, not as a replacement for enterprise terminals.

### vs Bloomberg Terminal

| Capability                    | Bloomberg           | CC today                                | Gap                         |
| ----------------------------- | ------------------- | --------------------------------------- | --------------------------- |
| Multi-asset real-time quotes  | Entitlements, BPIPE | yfinance delayed; optional APIs         | **Critical**                |
| Fixed income, FX, commodities | Deep                | Equities/crypto bias                    | **Critical**                |
| NEWS/ANR/CN                   | Integrated          | yfinance headlines + Discord news tasks | **High**                    |
| PORT/OMS hooks                | Terminal-native     | IBKR via `ibkr_service.py` only         | **High**                    |
| Decision audit trail          | MSG, bookmarks      | JSONL alerts, BDR, ops changelog        | **Medium** (good direction) |
| Regime / risk gating          | User-defined        | `regime_router.py` + board gates        | **Low** (CC strength)       |

**Verdict:** CC competes on **discipline and gate logic**, not data breadth. Do not pretend to be Terminal; integrate export hooks (CSV/JSON board snapshot) for operators who also use Bloomberg.

### vs FactSet

| Capability               | FactSet               | CC today                                       | Gap                             |
| ------------------------ | --------------------- | ---------------------------------------------- | ------------------------------- |
| Fundamentals / estimates | Core product          | Sparse in dossier; no consensus pipeline       | **Critical**                    |
| Ownership / 13F          | Lagged but structured | `institutional_13f.py` research API            | **Medium** (needs staleness UX) |
| Portfolio analytics      | Institutional         | Portfolio tab + `portfolio_decision.py`        | **Medium**                      |
| Custom screening         | Formula language      | `scanner_matrix.py` + `opportunity_scanner.py` | **Medium** ( narrower universe) |

**Verdict:** CC’s screener is **regime-aware and honest**; FactSet wins on **fundamental depth**. Priority: label every fundamental field with source + as_of + lag.

### vs Palantir Foundry (decision ontology)

| Capability           | Palantir        | CC today                                 | Gap                           |
| -------------------- | --------------- | ---------------------------------------- | ----------------------------- |
| Entity ontology      | Custom          | Ticker-centric dicts                     | **High**                      |
| Lineage / provenance | Built-in        | Partial (`trust`, `data_contract_strip`) | **Medium**                    |
| Workflow apps        | Drag-build      | Alpine SPA                               | **High** (different paradigm) |
| Audit & permissions  | Enterprise RBAC | API key + page capability                | **Medium**                    |

**Verdict:** CC already implements a **lightweight ontology** via `SystemState` + `PageCapability` + funnel layers — closer to a focused Palantir app than a platform. Extend with artifact IDs linking dossier → playbook row → handoff.

### vs Jane Street / Citadel (prop shop)

| Capability           | Prop shop                   | CC today                              | Gap          |
| -------------------- | --------------------------- | ------------------------------------- | ------------ |
| Latency              | Microseconds                | Seconds (polling HTTP)                | **Critical** |
| Alpha research infra | Massive                     | `strategy_optimizer.py`, walk-forward | **Critical** |
| Risk realtime        | Pre-trade checks everywhere | `risk_limits.py` + circuit breaker    | **Medium**   |
| Execution algos      | Custom                      | IBKR brackets                         | **High**     |
| Calibration at scale | Millions of events          | JSONL closed trades                   | **Critical** |

**Verdict:** CC is **not a prop stack**. Appropriate goal: **systematic discipline for discretionary sizing**, not HFT. Never recommend removing human deploy confirmation.

### vs Renaissance (stat arb / ML)

| Capability              | RenTech-style | CC today                                   | Gap                    |
| ----------------------- | ------------- | ------------------------------------------ | ---------------------- |
| Feature factory         | Industrial    | `feature_engine.py`, `feature_ic.py`       | **High**               |
| Out-of-sample rigor     | Extreme       | Walk-forward in optimizer; ML gate D-grade | **High**               |
| Signal decay monitoring | Continuous    | IC decay alerts (advisory)                 | **Medium** (good seed) |
| Overfitting control     | Cultural      | `min_sample_size=30`, kill switch          | **Medium**             |

**Verdict:** CC’s ML is **correctly subordinate to gates**. Expand Alpha QA (decay, calibration Brier) as **monitoring**, not signal generation.

### Summary Positioning

CC vNext should aim to be: **“Institutional-grade operator discipline on retail-accessible infrastructure”** — the Palantir-_shaped_ decision layer for a single PM or small pod, with Bloomberg/FactSet as complementary data sources, not replacements.

---

## 3. Top 100 Improvements

Ranked by expected ROI × trust impact. **Priority:** P0 = safety/truth, P1 = deploy path ROI, P2 = depth, P3 = polish. **ROI:** H/M/L. **Complexity:** S/M/L. **Time:** person-weeks (1 dev).

### Domain A — Authority & Decision Truth (1–12)

| #   | Problem                                | Recommendation                                                              | Expected benefit                     | Risk | Pri | ROI | Cplx | Time |
| --- | -------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------ | ---- | --- | --- | ---- | ---- |
| 1   | Client recomputes deploy state         | Server-authoritative `system_state` on every Today/Playbook/header response | Eliminates UI/server deploy mismatch | Low  | P0  | H   | M    | 1    |
| 2   | Scan-ranked misread as watch-qualified | Enforce `format_board_quality_detail()` in all API consumers                | Stops funnel lie on WAIT days        | Low  | P0  | H   | S    | 0.5  |
| 3   | Brief rows skip council                | Keep WATCH cap (`26400c6`); add audit flag `brief_sourced=true` on rows     | Traceability                         | Low  | P0  | H   | S    | 0.5  |
| 4   | PageCapability not on all tabs         | Extend `build_page_capability()` to Portfolio, IBKR, Command                | Consistent authority chips           | Low  | P0  | H   | M    | 1    |
| 5   | Dossier confirm-only drift             | Hard-block handoff buttons in `dossier.py` when `deploy_open=false`         | Prevents structure-only bypass       | Med  | P0  | H   | S    | 0.5  |
| 6   | BDR not on Playbook                    | Mirror `bdr_summary` subset on ranked API for single glance                 | Faster PM review                     | Low  | P1  | H   | S    | 0.5  |
| 7   | Decision hub vs Today duplication      | Single `decision_hub.py` payload reused by Today                            | Less drift                           | Med  | P1  | M   | M    | 1.5  |
| 8   | Near-miss threshold opaque             | Expose `_near_miss_signals()` hits in row metadata                          | Upgrade ladder clarity               | Low  | P1  | M   | S    | 0.5  |
| 9   | Global strip fatigue                   | Collapse strip when operator acknowledges (session cookie)                  | UX                                   | Med  | P2  | L   | S    | 0.5  |
| 10  | Command tab authority                  | Mark Command as research-only in header poll                                | Stops terminal confusion             | Low  | P1  | M   | S    | 0.25 |
| 11  | Cross-tab authority cache              | `ccHeader.page_authority_mode` stale on tab switch                          | Faster truth                         | Med  | P1  | M   | M    | 1    |
| 12  | Threshold changes untracked            | Version `TRADE_RR_THRESHOLD` changes in changelog + ops                     | Governance                           | Low  | P2  | M   | S    | 0.5  |

### Domain B — Data & Freshness (13–24)

| #   | Problem                       | Recommendation                                                    | Expected benefit     | Risk | Pri | ROI | Cplx | Time |
| --- | ----------------------------- | ----------------------------------------------------------------- | -------------------- | ---- | --- | --- | ---- | ---- |
| 13  | yfinance silent degradation   | Require `mode` + `source` on all price fields                     | Trust                | Low  | P0  | H   | M    | 1    |
| 14  | STALE still shows ranks       | Already gated; add red strikethrough on deploy actions in UI      | Visual safety        | Low  | P0  | H   | S    | 0.5  |
| 15  | No Polygon/Alpaca path in dev | Document + compose profile `CC_DATA_TIER=paid`                    | Institutional opt-in | Med  | P1  | H   | M    | 1    |
| 16  | Freshness poll hammers API    | Consolidate freshness into cc-header poll                         | Perf                 | Low  | P1  | M   | S    | 0.5  |
| 17  | Brief cache age hidden        | Show `brief_latest.json` mtime in data contract strip             | Honesty              | Low  | P1  | M   | S    | 0.25 |
| 18  | Universe count inflated       | `UNIVERSE_SUMMARY` marketing vs scannable                         | Credibility          | Low  | P2  | L   | S    | 0.25 |
| 19  | Crypto suffix bugs            | Already fixed Sprint 23; verify scanner matrix uses same          | Data bugs            | Low  | P1  | M   | S    | 0.5  |
| 20  | Earnings blackout not visible | Surface `earnings_blackout_days` from `risk_limits.py` on dossier | Event risk           | Low  | P1  | M   | M    | 1    |
| 21  | VIX source single-point       | Label VIX source; fallback chain in regime_router                 | Regime truth         | Med  | P1  | M   | S    | 0.5  |
| 22  | No data QA alerts             | Nightly job: cross-check OHLCV gaps → ops blocker                 | Integrity            | Med  | P2  | M   | M    | 2    |
| 23  | Cache invalidation unclear    | TTL table in Guide + ops                                          | Ops clarity          | Low  | P3  | L   | S    | 0.5  |
| 24  | HK/JP data quality            | Tag non-US symbols `data_tier=experimental`                       | Stops false TRADE    | Med  | P1  | H   | M    | 1    |

### Domain C — Playbook & Screening (25–34)

| #   | Problem                        | Recommendation                                                         | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | ------------------------------ | ---------------------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 25  | Monitor pool empty on WAIT     | Screening yield top-up (done); tune `PLAYBOOK_MIN_SIGNALS_BEFORE_SCAN` | Operator morale  | Low  | P1  | H   | S    | 0.5  |
| 26  | Live scan latency              | Cache ranked snapshot (`playbook_ranked_snapshot.json`) with SWR       | p95 &lt;2s       | Med  | P1  | H   | M    | 1    |
| 27  | Scanner matrix batch size      | Already raised; profile per regime                                     | Hit rate         | Low  | P2  | M   | S    | 0.5  |
| 28  | Discovery zero-hit UX          | Cached brief leaders + degraded banner (done)                          | Empty state fix  | Low  | P2  | M   | S    | 0    |
| 29  | Opportunity scanner not linked | Show Neal engine tags as research chips on Discovery                   | Depth            | Low  | P2  | M   | M    | 1    |
| 30  | Rejection clusters overlap     | `rejection_clusters_reconcile_note()` (done); surface in UI            | Audit            | Low  | P2  | M   | S    | 0.25 |
| 31  | Upgrade ladder buried          | Promote `playbook_upgrade_ladder.py` section above fold                | Near-miss ROI    | Low  | P1  | H   | S    | 0.5  |
| 32  | Duplicate tickers in buckets   | `build_playbook_rank_buckets()` dedupes; add test for edge cases       | Clean ranks      | Low  | P2  | M   | S    | 0.5  |
| 33  | Sector filter stale            | Tie sector weights to `regime_router` size_scalar                      | Regime-fit       | Med  | P2  | M   | M    | 1.5  |
| 34  | Playbook funnel KPI wrong      | Wire KPI boxes to `filter_funnel` keys not row counts                  | Truth            | Med  | P1  | H   | S    | 0.5  |

### Domain D — Risk & Sizing (35–44)

| #   | Problem                     | Recommendation                                             | Expected benefit    | Risk | Pri | ROI | Cplx | Time |
| --- | --------------------------- | ---------------------------------------------------------- | ------------------- | ---- | --- | --- | ---- | ---- |
| 35  | Legacy magic numbers        | Audit imports: all modules use `risk_limits.RISK`          | Consistency         | Low  | P0  | H   | M    | 1    |
| 36  | 1R sizing not universal     | Sticky BDR 1R (recent commit); extend to Portfolio preview | Sizing discipline   | Low  | P1  | H   | M    | 1    |
| 37  | Thompson cold start         | Hide multiplier when arm n&lt;5; show prior only           | No false confidence | Low  | P1  | H   | S    | 0.5  |
| 38  | Half-Kelly without costs    | Subtract est. slippage/fees in `EdgeCalculator`            | EV truth            | Med  | P1  | H   | M    | 2    |
| 39  | Circuit breaker opaque      | Show breaker state on Today mission panel                  | Operator trust      | Low  | P1  | M   | S    | 0.5  |
| 40  | Sector concentration        | Enforce `max_sector_pct` in portfolio add flow             | Risk                | Med  | P1  | H   | M    | 1.5  |
| 41  | Drawdown sizer disconnected | Wire `test_drawdown_sizer.py` module to live portfolio tab | Dynamic size        | Med  | P2  | M   | M    | 2    |
| 42  | VIX crisis NO_TRADE         | Verify `regime_router` crisis path → board                 | Safety              | Low  | P0  | H   | S    | 0.5  |
| 43  | Pilot tier undefined in UI  | Explain PILOT vs TRADE in Guide + card badge               | Clarity             | Low  | P2  | M   | S    | 0.5  |
| 44  | Risk alerts modal only      | Push CRITICAL to Discord webhook                           | Alerting            | Low  | P2  | M   | S    | 0.5  |

### Domain E — Execution & IBKR (45–52)

| #   | Problem                         | Recommendation                                                | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | ------------------------------- | ------------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 45  | Docker dev skips IB             | `CC_SKIP_IB_INSYNC=1` — document prod checklist               | Dev/prod parity  | Med  | P1  | M   | S    | 0.25 |
| 46  | MONITOR vs READY confusion      | Already badges; add ladder widget on IBKR tab                 | UX               | Low  | P1  | H   | M    | 1    |
| 47  | Bracket poll aggressive         | Review `_bracketPollTimer` interval in cc-app.js              | Load             | Low  | P2  | L   | S    | 0.25 |
| 48  | Handoff without dossier confirm | Require dossier `structure_confirmed` flag before handoff API | Process          | Med  | P1  | H   | M    | 1    |
| 49  | No TCA feedback loop            | `test_execution_tca.py` → surface slippage on Ops             | Alpha QA         | Med  | P2  | M   | M    | 2    |
| 50  | Session reconnect               | Harden `ibkr_session_manager.py` retry/backoff tests          | Reliability      | Med  | P1  | H   | M    | 2    |
| 51  | Paper vs live label             | Enforce `mode=PAPER` on all IBKR responses in dev             | Truth            | Low  | P0  | H   | S    | 0.5  |
| 52  | Order audit trail               | Persist handoff attempts to JSONL                             | Audit            | Med  | P2  | M   | M    | 1.5  |

### Domain F — ML, Self-Learning & Alpha QA (53–62)

| #   | Problem                           | Recommendation                                              | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | --------------------------------- | ----------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 53  | insufficient_sample UX            | Ops copy done; add Today tab footnote when inactive         | Honesty          | Low  | P1  | M   | S    | 0.25 |
| 54  | ML advisory implies edge          | `ml_advisory_summary.py` authority_note (done); bold in UI  | Safety           | Low  | P0  | H   | S    | 0.25 |
| 55  | Closed trades not flowing         | Wire IBKR fills → `learning_loop.py` JSONL                  | Learning         | Med  | P1  | H   | M    | 2    |
| 56  | Feature IC alerts ignored         | `featureIcDecayAlert()` template exists; link to ops action | Alpha QA         | Low  | P1  | M   | S    | 0.5  |
| 57  | Calibration drift                 | `get_calibration_status()` → downgrade confidence display   | Truth            | Med  | P1  | H   | M    | 1.5  |
| 58  | Self-learning auto-apply fear     | Keep kill switch default; require ops toggle to apply       | Safety           | Low  | P0  | H   | S    | 0    |
| 59  | Meta ensemble opaque              | Show top 3 feature weights in research tab only             | Explainability   | Low  | P2  | M   | M    | 1    |
| 60  | Thompson arms unbounded           | Cap `_MAX_MULTIPLIER` review vs risk_limits                 | Tail risk        | Med  | P2  | M   | S    | 0.5  |
| 61  | GPT validator cost                | Cache narratives per ticker/day                             | Cost             | Low  | P2  | M   | S    | 0.5  |
| 62  | Walk-forward not on playbook rows | Attach optimizer OOS score as research field                | QA               | Med  | P2  | M   | M    | 2    |

### Domain G — UI/UX & i18n (63–74)

| #   | Problem                     | Recommendation                                               | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | --------------------------- | ------------------------------------------------------------ | ---------------- | ---- | --- | --- | ---- | ---- |
| 63  | Dynamic strings English     | Server-side bilingual fields for operator sentences first    | HK operator UX   | Low  | P1  | H   | L    | 3    |
| 64  | 16k-line SPA unmaintainable | Split tabs into partials via build-cc-template.mjs           | Velocity         | Med  | P1  | H   | L    | 4    |
| 65  | Black screen history        | gzip cache + fix script (done); add health self-test on boot | Reliability      | Low  | P2  | M   | S    | 0.5  |
| 66  | Polling storm               | Single SSE or websocket for header+today (future)            | Perf             | Med  | P2  | M   | L    | 3    |
| 67  | Empty WAIT day depressing   | `WAIT_DAY_OK` empty state (tested); ensure copy on all tabs  | UX               | Low  | P2  | M   | S    | 0.5  |
| 68  | Guide too long              | Layer collapse (done); add search                            | UX               | Low  | P3  | L   | M    | 1    |
| 69  | Mobile layout               | PM strip chip menu exists; test narrow viewports             | Mobile ops       | Low  | P3  | L   | M    | 2    |
| 70  | Accessibility               | aria labels on authority pills                               | A11y             | Low  | P3  | L   | M    | 1    |
| 71  | Sticky BDR (recent)         | Verify scroll performance on Today                           | UX               | Low  | P2  | M   | S    | 0.25 |
| 72  | Tooltip ticker tool         | `tt` modal rich; add authority badge                         | Clarity          | Low  | P3  | L   | S    | 0.5  |
| 73  | cc-i18n skips x-text        | Move high-traffic labels to CCHelpers maps                   | i18n             | Med  | P1  | H   | M    | 2    |
| 74  | SettingsView race           | AGENTS.md cachedState pattern for any settings UI            | Bug prevention   | Med  | P2  | M   | S    | 0.5  |

### Domain H — Architecture & Performance (75–84)

| #   | Problem                     | Recommendation                                                | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | --------------------------- | ------------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 75  | main.py 6281 lines          | Extract remaining inline routes to routers                    | Maintainability  | Med  | P1  | H   | L    | 4    |
| 76  | Router load failures silent | `main.py` try/except logs; fail health if P0 router missing   | Ops              | Med  | P1  | H   | S    | 0.5  |
| 77  | Engine singleton test gaps  | Expand `test_vnext_truthful_surfaces.py`                      | Truth            | Low  | P1  | H   | M    | 1    |
| 78  | Discord + CC duplication    | Document single engine SSOT; deprecate duplicate signal paths | Clarity          | Med  | P2  | M   | M    | 2    |
| 79  | ARCHITECTURE.md stale       | Rewrite Layer 0 as CC dashboard + API                         | Onboarding       | Low  | P2  | M   | M    | 1    |
| 80  | No API versioning policy    | Standardize `/api/v7/*` for operator surfaces                 | Stability        | Med  | P2  | M   | M    | 2    |
| 81  | Async scan blocking         | `opportunity_scanner.py` asyncio; ensure engine cycle async   | Perf             | Med  | P1  | H   | M    | 2    |
| 82  | Postgres optional           | Trade outcomes in DB (Sprint 11) — verify docker prod compose | Persistence      | Med  | P2  | M   | M    | 2    |
| 83  | Redis lazy import           | Done Sprint 18; verify cache strategy for playbook            | Perf             | Low  | P2  | M   | S    | 1    |
| 84  | Correlation IDs             | Structured logging exists; wire to UI error banner            | Debug            | Low  | P3  | L   | S    | 0.5  |

### Domain I — Testing & QA (85–92)

| #   | Problem                    | Recommendation                                                 | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | -------------------------- | -------------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 85  | pytest not in host shell   | CI docker job `python -m pytest tests/ -q`                     | Regression       | Low  | P0  | H   | M    | 1    |
| 86  | E2E browser tests missing  | Playwright smoke: boot → Today → Playbook authority            | UI truth         | Med  | P1  | H   | L    | 3    |
| 87  | WAIT/NO_TRADE matrix       | Parametrize `test_operator_state_contract` across stale+broker | Coverage         | Low  | P1  | H   | S    | 0.5  |
| 88  | Playbook render integrity  | Extend `test_playbook_render_integrity.py` for BDR block       | UI               | Low  | P2  | M   | S    | 0.5  |
| 89  | Sprint tests fragmented    | Group authority tests under `tests/authority/`                 | DX               | Low  | P3  | L   | S    | 0.5  |
| 90  | Property tests for buckets | Hypothesis: AVOID never in monitor_rows                        | Safety           | Low  | P1  | H   | M    | 1    |
| 91  | Load test playbook p95     | k6 script for `/api/playbook/ranked`                           | Perf budget      | Med  | P2  | M   | M    | 1.5  |
| 92  | verify_10_10.sh in CI      | Wire institutional verify script to PR checks                  | Gate             | Low  | P1  | H   | S    | 0.5  |

### Domain J — Ops, Discovery & Research (93–100)

| #   | Problem                      | Recommendation                                            | Expected benefit | Risk | Pri | ROI | Cplx | Time |
| --- | ---------------------------- | --------------------------------------------------------- | ---------------- | ---- | --- | --- | ---- | ---- |
| 93  | Discord 403                  | Webhook-first docs (done); fail setup wizard              | Alerts           | Low  | P1  | H   | S    | 0.25 |
| 94  | Engine off default confusion | Auto-start in dev compose; prod runbook                   | Ops              | Low  | P1  | M   | S    | 0.25 |
| 95  | Research muted silently      | `DISCORD_NOTIFY_RESEARCH=false` — show in notify status   | Clarity          | Low  | P3  | L   | S    | 0.25 |
| 96  | Vibe agent safety            | `vibe_agent_safety.py` contract tests in CI               | Safety           | Low  | P1  | H   | S    | 0.5  |
| 97  | Shadow account unused        | Weekly shadow digest on Reports tab                       | Behavior QA      | Low  | P2  | M   | M    | 1.5  |
| 98  | Backtest lab confusion       | Prominent SYNTHETIC badge on btlab                        | Truth            | Low  | P1  | H   | S    | 0.5  |
| 99  | Public tunnel script         | Recent commit; document security model                    | Access           | Med  | P2  | M   | S    | 0.5  |
| 100 | Advisor briefing page        | `/briefing` for external advisors (done); link from Guide | Onboarding       | Low  | P2  | M   | S    | 0.25 |

---

## 4. Sprint Plan (ROI-Ordered)

Sprints continue from current ~114 (`opportunity_scanner.py` Sprint 114). Each sprint = ~1–2 weeks focused delivery.

### Sprint 101 — Decision Payload Unification (P0)

**Goal:** Single server-built `system_state` + board on Today, Playbook, cc-header.  
**Files:** `decision.py`, `playbook.py`, `cc_header.py`, `operator_state_contract.py`  
**Accept:** Identical `deploy_open` across three endpoints; tests parametrize WAIT/STALE/broker down.  
**ROI:** Highest — eliminates class of authority bugs.

### Sprint 102 — CI Truth Gate (P0)

**Goal:** Docker CI runs full pytest + `scripts/verify_10_10.sh` on PR.  
**Accept:** Red build on `test_operator_state_contract` failure.  
**ROI:** Prevents regression on gates.

### Sprint 103 — Data Provenance v1 (P0)

**Goal:** `mode`, `source`, `as_of` on all Today/Playbook price fields.  
**Files:** `brief_data_service.py`, `decision.py`, `cc-app.js` data contract strip.  
**Accept:** STALE hides deploy CTAs.

### Sprint 104 — Playbook p95 & Snapshot SWR (P1)

**Goal:** Ranked playbook &lt;2s p95 via cache-first + background refresh.  
**Files:** `playbook.py`, `playbook_signal_universe.py`, snapshot writer.  
**Accept:** k6 p95 test; degraded banner when snapshot age &gt; threshold.

### Sprint 105 — i18n Operator Critical Path (P1)

**Goal:** Bilingual server strings for Today/Playbook/Ops operator sentences + blockers.  
**Files:** `operator_state_contract.py`, `cc-helpers.js`, remove duplicate English x-text.  
**Accept:** `test_guide_surface_authority.py` extended.

### Sprint 106 — IBKR Ladder UX + Handoff Audit (P1)

**Goal:** Visual ladder; JSONL handoff log; dossier confirm gate.  
**Files:** `ibkr_service.py`, `ibkr.py`, `dossier.py`, IBKR tab partial.  
**Accept:** Cannot handoff when `deploy_open=false`.

### Sprint 107 — Closed Trade → Learning Loop (P1)

**Goal:** IBKR paper fills append to `data/closed_trades.jsonl`; Thompson update.  
**Files:** `learning_loop.py`, `ibkr_service.py`, `thompson_sizing.py`.  
**Accept:** Ops shows n≥5 with engine on in dev sim.

### Sprint 108 — Cost-Adjusted EV Rank (P1)

**Goal:** Fees/slippage in edge ranker; display net R:R on cards.  
**Files:** `cost_adjusted_ranker` modules, `decision_truth_model.py`.  
**Accept:** Tests from `test_cost_adjusted_ranker.py` pass on API payload.

### Sprint 109 — main.py Router Extraction Phase 1 (P1)

**Goal:** Move 20 largest inline handlers from `main.py` to routers.  
**Accept:** `main.py` &lt;5000 lines; health still mounts all P0 routers.

### Sprint 110 — UI Partial Split (Today + Playbook) (P1)

**Goal:** Extract Today/Playbook to `cc/partials/` via build script.  
**Accept:** `test_ui_render_integrity.py` green; bundle size stable.

### Sprint 111 — Alpha QA Surface (P1)

**Goal:** Feature IC + calibration panel on Ops with actionable next steps.  
**Files:** `ml_advisory_summary.py`, ops template, `feature_ic.py`.  
**Accept:** Decay alert links to “review timing weights” copy only — no auto-tune.

### Sprint 112 — Discovery ↔ Playbook Research Bridge (P2)

**Goal:** Discovery rows carry `research_only=true`; one-click “open in Playbook” preserves authority.  
**Files:** `opportunity_scanner.py`, `scanner_matrix.py`, cc-app.js.  
**Accept:** No deploy button on Discovery.

### Sprint 113 — Paid Data Tier (P2)

**Goal:** Polygon path behind `POLYGON_API_KEY`; honest downgrade to yfinance.  
**Files:** `market_data` ingestors, config, freshness service.  
**Accept:** Header shows `DATA_TIER`.

### Sprint 114 — Portfolio Risk Enforcement (P2)

**Goal:** Wire sector/max position checks on quick-add.  
**Files:** `portfolio.py`, `risk_limits.py`, `portfolio_decision.py`.  
**Accept:** `test_risk_critical.py` scenarios in UI.

### Sprint 115 — E2E Authority Smoke (P2)

**Goal:** Playwright: WAIT day → deploy buttons disabled; deploy day → enabled only with mocks.  
**Accept:** CI artifact screenshot on failure.

### Sprint 116 — ARCHITECTURE.md CC Rewrite (P2)

**Goal:** Document CC stack as primary; Discord as satellite.  
**Accept:** New diagram: Browser → instant → FastAPI → engines.

### Sprint 117 — Opportunity Intelligence Dossier Embed (P2)

**Goal:** Insider/13F/events chips on dossier (research-only).  
**Files:** `opportunity_intelligence.py`, dossier router.  
**Accept:** 90+ day lag labels visible.

### Sprint 118 — Shadow Digest (P3)

**Goal:** Weekly shadow vs actual report in Reports library.  
**Files:** `shadow_account.py`, `reports_library.py`.

### Sprint 119 — SSE Header Stream (P3)

**Goal:** Replace 15s/60s polls for header+system_state with one SSE channel.  
**Accept:** Reduced `/health` QPS 50%.

### Sprint 120 — Institutional Export (P3)

**Goal:** Board snapshot JSON/CSV export for external tools (Bloomberg notes).  
**Files:** `decision.py` export endpoint.  
**Accept:** Includes authority disclaimer footer.

---

## 5. Refactoring Plan

### Architecture

| Phase | Action                                                                                  | Outcome                          |
| ----- | --------------------------------------------------------------------------------------- | -------------------------------- |
| A1    | Extract `main.py` routes → existing `src/api/routers/*`                                 | Routers &lt;300 lines each       |
| A2    | Introduce `DecisionBoardService` composing truth model + BDR + rank buckets             | One call site for Today/Playbook |
| A3    | Mark Discord bot as **notification/satellite**; engine SSOT in `auto_trading_engine.py` | Clear product boundary           |
| A4    | Artifact-first responses: write `data/artifacts/board/{date}.json` before UI            | Audit replay                     |

### Performance

- **Cache ladder:** instant gz dashboard → playbook snapshot → live engine → yfinance fetch.
- **Batch yfinance:** Universe builder already staged (Sprint 23); extend to scanner matrix with shared OHLCV cache keyed by date.
- **Poll budget table (target):**

| Endpoint        | Current | Target                   |
| --------------- | ------- | ------------------------ |
| `/health`       | 15s     | 30s (or SSE)             |
| cc-header       | ad hoc  | 60s consolidated         |
| Today7          | 120s    | 120s + ETag              |
| Playbook ranked | on tab  | 60s when tab active only |
| Freshness       | 60s     | merge into header        |

### UX

- **Authority-first chrome:** Every tab shows `PageCapability.authority` pill from server, not client guess (`normalizedAuthorityChipForTab` already exists — make server authoritative).
- **Three empty states only:** NO_DATA, WAIT_DAY_OK, DEGRADED — already tested in `test_top_product_improvements.py`; enforce globally.
- **BDR sticky header** on Today (shipped) — extend minimal strip to Playbook.

### AI

- **Roles:** ADVISOR/REVIEWER/EMBED via `ai_service.py` — never bypass council gates.
- **Narrative cache:** Per ticker/day with `sample_size` and `model` in footer.
- **Kill switches:** `AI_DISABLED`, self-learning `enabled=false` default in prod until n≥30.

### Testing

- **Authority matrix test file:** All combinations of tradeability × freshness × broker × fallback.
- **Contract tests:** OpenAPI snapshots for `/api/v7/decision/*`, `/api/playbook/ranked`.
- **Playwright smoke** on Sprint 115.

### Documentation

- Supersede Discord-centric `ARCHITECTURE.md` with CC-first diagram (Sprint 116).
- Keep `CC_CONSOLIDATED_BRIEFING.md` as advisor paste; link this review as §11.
- Runbook: `docs/CC_VNEXT_MASTER_REVIEW.md` → sprint backlog traceability.

---

## 6. Intelligence Roadmap

All layers respect **authority contracts** — intelligence **informs** monitor ranking and dossier depth; only Playbook + open gates grant deploy.

### Opportunity Intelligence

| Milestone | Deliverable                                           | Authority                  |
| --------- | ----------------------------------------------------- | -------------------------- |
| Q3        | Neal scanner tags on Discovery cards                  | research_only              |
| Q3        | Scanner matrix “validation” bucket → rejection themes | research_only              |
| Q4        | Cross-scanner consensus score (display only)          | monitor ranking input only |
| Q4        | Sector rotation heatmap with regime fit               | research_only              |

**Files:** `opportunity_scanner.py`, `scanner_matrix.py`, `playbook_signal_universe.py`

### Alpha QA

| Milestone | Deliverable                                | Authority               |
| --------- | ------------------------------------------ | ----------------------- |
| Q3        | Feature IC decay → ops blocker (advisory)  | no deploy effect        |
| Q3        | Calibration Brier trend on Ops             | confidence display only |
| Q4        | Walk-forward OOS attached to strategy rows | research field          |
| Q4        | Shadow account weekly digest               | research_only           |

**Files:** `feature_ic.py`, `self_learning.py`, `shadow_account.py`, `validation_lab.py`

### Decision Quality

| Milestone | Deliverable                                                  | Authority               |
| --------- | ------------------------------------------------------------ | ----------------------- |
| Q3        | BDR brief on Today + Playbook                                | monitor/deploy guidance |
| Q3        | Rejection cluster reconciliation in UI                       | audit                   |
| Q4        | Decision persistence replay (`test_decision_persistence.py`) | audit                   |
| Q4        | “What changed since open” diff on Today                      | monitor                 |

**Files:** `bdr_operator_summary.py`, `decision_truth_model.py`, `decision_hub.py`

### Discovery

| Milestone | Deliverable                                     | Authority         |
| --------- | ----------------------------------------------- | ----------------- |
| Q3        | Zero-hit → brief leaders fallback (done)        | degraded research |
| Q3        | Intent buckets (Leaders/Pullbacks/Flow) labeled | research_only     |
| Q4        | Unified discovery API with hub_status           | research_only     |

**Files:** `opportunity_scanner.py` router, `test_discovery_brief_leaders.py`

### Portfolio

| Milestone | Deliverable                                | Authority              |
| --------- | ------------------------------------------ | ---------------------- |
| Q3        | 1R sticky sizing preview                   | sizing when gates open |
| Q4        | Sector/heat enforcement on add             | blocks oversize        |
| Q4        | Sleeve summary on Today (`sleeve_summary`) | allocation research    |
| Q4        | TCA slippage feedback                      | Alpha QA input         |

**Files:** `portfolio_decision.py`, `risk_limits.py`, execution TCA modules

### Macro

| Milestone | Deliverable                                     | Authority        |
| --------- | ----------------------------------------------- | ---------------- |
| Q3        | `regime_router.py` entropy in header            | board input      |
| Q3        | Index regime summary on Today                   | monitor          |
| Q4        | FRED macro router (`macro_fred.py`) integration | research_only    |
| Q4        | Crisis regime NO_TRADE drill tests              | gate enforcement |

**Files:** `regime_router.py`, `macro_fred.py`, `test_crisis_regime.py`

---

## 7. Final Vision

### What CC Becomes

Clarity Console vNext is **not** an autonomous trading bot or a Bloomberg clone. It becomes:

> **A regime-aware Operator Decision OS** — the single place a PM starts each session to learn whether capital may move, which names earned monitor attention versus deploy qualification, what blocks execution, and what evidence supports or contradicts a thesis — with every surface labeled for authority, freshness, and sample size.

Within 12–18 months at current velocity (Sprints 101–120+), CC should present to an institutional allocator as:

1. **Board-first** — Today tab answers “trade or wait” in &lt;10 seconds with BDR brief and explicit blockers.
2. **Funnel-honest** — Playbook never conflates scanned, watch-qualified, and deploy-qualified counts.
3. **Research-rich, permission-poor** — Discovery, Flow, intelligence APIs deepen conviction without shortcuts to deploy.
4. **Execution-modest** — IBKR handoff with audit trail, paper/live truth, no hidden auto-orders.
5. **Alpha-humble** — ML/Thompson/self-learning visible as **QA and sizing hints** after sample thresholds, never as magic alpha.

### Target Quote (from Institutional Master Brief)

> _“If I were managing real capital and wanted this system to help me find high-quality opportunities, avoid weak trades, size better, allocate better, and improve long-term wealth creation with disciplined risk, would this feature genuinely help — or is it mostly noise, decoration, or fragile prototype behavior?”_

CC vNext passes this test when **gates, labels, and sample sizes** make the honest answer visible — even when the answer is **“monitor only today.”** That is the product winning over signal theater.

### Operator Decision OS — Closing Principles

From Guide (`index.html` Layer 1) and `operator_state_contract.py`:

- **Page gate beats card rank** — WAIT / NO_TRADE before any attractive card.
- **Research ≠ permission** — Discovery, Flow, Funds, RS never grant deploy.
- **Threshold Governance** — R:R 2.5 deploy bar, council validation for brief-sourced names.
- **Alpha QA** — Probe ≠ runtime; IC decay and calibration are advisory.
- **Auditability** — BDR, artifacts, handoff logs, self-learning audit trail.

---

## Appendix — Key Files Referenced

| Area               | Path                                                                                      |
| ------------------ | ----------------------------------------------------------------------------------------- |
| Authority contract | `src/services/operator_state_contract.py`                                                 |
| Decision truth     | `src/services/decision_truth_model.py`                                                    |
| Risk SSOT          | `src/core/risk_limits.py`                                                                 |
| BDR brief          | `src/services/bdr_operator_summary.py`                                                    |
| Playbook universe  | `src/services/playbook_signal_universe.py`                                                |
| Regime             | `src/engines/regime_router.py`                                                            |
| Scanners           | `src/engines/scanner_matrix.py`, `src/engines/opportunity_scanner.py`                     |
| ML advisory        | `src/services/ml_advisory_summary.py`                                                     |
| Self-learning      | `src/engines/self_learning.py`, `learning_loop.py`, `thompson_sizing.py`, `feature_ic.py` |
| UI                 | `src/api/templates/index.html`, `src/api/static/cc-app.js`, `cc-helpers.js`, `cc-i18n.js` |
| Ops honesty        | `src/services/ops_operator_console.py`                                                    |
| Engine             | `src/engines/auto_trading_engine.py`                                                      |
| Briefing           | `docs/CC_CONSOLIDATED_BRIEFING.md`                                                        |
| Tests              | `tests/test_operator_state_contract.py`, `tests/test_vnext_truthful_surfaces.py`          |

---

_End of master review. No code changes were made except this document._
