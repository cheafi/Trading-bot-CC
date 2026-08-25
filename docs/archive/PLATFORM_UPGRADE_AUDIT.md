# Clarity Console — Platform Upgrade Audit

**Date:** 2026-05-31  
**Scope:** Product diagnosis, IA, scoring, data/logic, UX, copy, roadmap, file plan  
**Builds on:** Random Walk sprint (`docs/RANDOM_WALK_PLATFORM_PROMPT.md`), decision truth model, playbook fallback, dossier guardrails, IBKR health, ops separation  
**Session implementation:** Section 9 items (decision hierarchy, score families, passive baseline, anti-overtrading, crowding, surface authority, dashboard wiring)

---

## 1. Product diagnosis

### Strong (keep, extend)

| Area                                                                        | Why it works                                                              |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **3-layer decision model** (`decision_truth_model.build_three_layer_model`) | Macro → Opportunity → Execution separates backdrop from deploy permission |
| **Honest funnel**                                                           | Raw scanner vs council-validated counts — kills score theater             |
| **Playbook 3-layer fallback**                                               | Full → compressed → emergency; board_mode labels authority                |
| **Dossier decision stack + unified confidence**                             | Thesis vs timing vs execution visible; why-not populated                  |
| **Random Walk guardrails**                                                  | `humility_labels`, `cost_adjusted_edge`, `random_walk_guardrails`         |
| **IBKR health state machine**                                               | Critical vs workflow checks; handshake spam fixed                         |
| **Ops probe vs runtime**                                                    | `ops_operator_console` — connectivity ≠ capital permission                |
| **Portfolio risk hierarchy**                                                | Heat post-breach, simple add position                                     |
| **WAIT-day copy**                                                           | Dashboard explains uptrend + WAIT without contradiction                   |

### Misleading (fix copy or demote visual weight)

| Issue                                              | Remediation                                                       |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| Single **fit score** on cards read as “buy signal” | Split into score families; show Gross · Net after cost            |
| **AI narrative** on WAIT days                      | Already gated — keep collapsed; never imply deploy                |
| **Funds backtest returns**                         | Label “research evidence — not deploy authority” (partially done) |
| **Flow radar** when mock/stale                     | “Confirmation only” pill (done); never rank above board           |
| **RS / Discovery ranks**                           | Research funnel — not playbook substitute                         |
| **Connected** IBKR badge                           | Distinguish connected vs synced vs bracket-ready                  |

### Underbuilt (highest ROI gaps)

| Gap                                                | Priority                                         |
| -------------------------------------------------- | ------------------------------------------------ |
| **L1–L5 decision hierarchy** surfaced on Dashboard | P0 — implemented this session                    |
| **Passive baseline strip** (SPY/QQQ/EW)            | P0 — implemented stub + live fetch               |
| **Anti-overtrading / restraint governor**          | P0 — implemented                                 |
| **Score family separation** in UI tooltips         | P1 — backend ready; tooltip UX deferred          |
| **Crowding / narrative heat** on playbook cards    | P1 — stub wired to rows                          |
| **Surface authority labels** per tab               | P1 — helper + partial dashboard                  |
| **Turnover / recent trade feed** into restraint    | P2 — needs trade memory integration              |
| **Live TCA** for net edge                          | P3 — stay heuristic per Random Walk constitution |

### Over-complex (simplify or merge)

| Area                                              | Action                                                                                            |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Multiple overlapping “today” summaries            | **Today's decision** is primary — demote legacy regime-only blocks when `todays_decision` present |
| Sprint test sprawl (`tests/sprints/test_sprint*`) | Keep for regression; don’t expose to operators                                                    |
| Duplicate confidence paths (4-layer + council)    | Document: council wins on board; 4-layer for dossier technicals                                   |
| Agent orchestrator / PM arena                     | Demote to labs — not daily driver                                                                 |
| 50+ indicator engines                             | Do not add; use existing confluence + gates                                                       |

### Remove / merge / demote

| Item                                    | Action                                                     |
| --------------------------------------- | ---------------------------------------------------------- |
| Raw scanner ≥8 as tradeability input    | **Removed** from honest tradeability — keep in funnel only |
| Emergency playbook as silent full board | **Keep** emergency mode but board_mode + authority label   |
| Cosmetic sparklines on WAIT days        | Demote below fold                                          |
| Discord alpha vs passive in bot         | Align vocabulary with `humility_labels` (future)           |

---

## 2. New information architecture

### Page roles & hierarchy

```
Authority stack (top wins):
  L1 Dashboard gate (regime + honest tradeability + restraint)
  L2 Playbook board (ranked, board_mode aware)
  L3 Dossier (research depth, guardrails)
  L4 Portfolio (book construction, heat, sizing)
  L5 Execution (IBKR, brackets, send)

Supporting (never authorize alone):
  Discovery, Flow, Funds, RS, Ops probes
```

| Tab           | Role                 | Authority                               | Feeds                      |
| ------------- | -------------------- | --------------------------------------- | -------------------------- |
| **Dashboard** | Daily deploy posture | **Permits / blocks**                    | Playbook, portfolio, IBKR  |
| **Playbook**  | Ranked opportunities | **Permits** when `board_mode=full_live` | Council pipeline, fallback |
| **Dossier**   | Single-name 360      | **Research only**                       | stock_intel, guardrails    |
| **Portfolio** | Book + risk          | **Permits sizing** within limits        | positions, heat, fit       |
| **Discovery** | Universe scan        | Research                                | Scanner matrix             |
| **Flow**      | Options narrative    | Confirmation                            | flow_decision_surface      |
| **Funds**     | Model evidence       | Research                                | fund_manager_console       |
| **IBKR**      | Broker health        | Ops / execution                         | ibkr_health                |
| **Ops**       | Runtime vs probe     | Ops                                     | ops_operator_console       |

### Research vs execution mapping

| Signal source            | Maps to        | May authorize?            |
| ------------------------ | -------------- | ------------------------- |
| Regime / VIX / breadth   | L1 page gate   | Indirect (blocks all)     |
| Council fit + confidence | L2–L3 setup    | Yes, via action tier      |
| Net edge after cost      | L3 humility    | No — adjusts rank/size    |
| Portfolio overlap        | L5 restraint   | No — blocks or sizes down |
| Flow / smart money       | Dossier / Flow | **Never alone**           |
| Backtest / funds         | Funds tab      | **Never**                 |

---

## 3. Scoring architecture

### Score families (canonical)

Implemented in `src/services/score_families.py`:

| Family                    | Measures                   | Scale          | UI rule                 |
| ------------------------- | -------------------------- | -------------- | ----------------------- |
| Evidence                  | Data conf + calibration n  | 0–1            | Show calibration note   |
| Freshness                 | Quote/module age           | tier / minutes | Stale → spread penalty  |
| Board investability       | Council validated score    | 0–10           | **Not** raw scanner     |
| Setup quality             | Pattern / trigger grade    | grade / 0–10   | Supporting only         |
| Risk geometry             | R:R, stops                 | ratio + gates  | R:R < 2.5 → pilot/watch |
| Deployability             | Action + execution_ready   | label + bool   | **Permission field**    |
| Portfolio contribution    | Sector alignment / overlap | fit label      | Correlated = one bet    |
| Cost-adjusted edge        | Gross → net                | 0–10           | Always show both        |
| Crowding / narrative heat | Extension, cluster         | low/med/high   | Discount size           |
| Passive replacement risk  | vs SPY/QQQ                 | low/med/high   | Cash valid              |
| Simplicity challenge      | Complexity justified?      | verdict        | Dashboard strip         |

### Role separation (no mystery numbers)

| Term                    | Meaning                                    | Must not imply               |
| ----------------------- | ------------------------------------------ | ---------------------------- |
| **Thesis quality**      | Bull-case evidence strength                | Deploy permission            |
| **Decision confidence** | Composite model confidence                 | Hit rate (unless calibrated) |
| **Deployability**       | Passes action + execution gates            | Rank order                   |
| **Rank**                | Action tier → validated score → sector adj | Intrinsic value              |

---

## 4. Data / logic architecture

### New / extended modules (this session)

| Module                  | Responsibility                                    |
| ----------------------- | ------------------------------------------------- |
| `decision_hierarchy.py` | L1–L5 evaluation, binding level, can_deploy flags |
| `score_families.py`     | Family metadata, score_card, complexity_verdict   |
| `passive_baseline.py`   | SPY/QQQ/RSP 20d strip, beats-passive proxy        |
| `anti_overtrading.py`   | Restraint governor, turnover burden               |
| `crowding_narrative.py` | Bubble/crowding heuristic                         |
| `surface_authority.py`  | Tab authority labels                              |
| `cost_adjusted_edge.py` | Extended: gross_edge_score, compute_gross_vs_net  |

### Interactions

```mermaid
flowchart TD
  Regime[Regime Service] --> Today[/api/v7/today]
  Council[Sector Pipeline / Council] --> Today
  Council --> Playbook[/api/v7/playbook/ranked]
  Today --> DH[decision_hierarchy]
  Today --> PB[passive_baseline]
  Today --> AO[anti_overtrading]
  Playbook --> Enrich[enrich_opportunity_row]
  Enrich --> CAE[cost_adjusted_edge]
  Enrich --> CN[crowding_narrative]
  Enrich --> SF[score_families]
  Enrich --> HL[humility_labels]
  Dossier[stock_intel] --> RW[random_walk_guardrails]
```

### Gating rules (unchanged + reinforced)

1. **Page gate** — `should_trade` + honest tradeability override raw scores
2. **Board gate** — `execution_ready` count ≥ 1 for full deploy narrative
3. **Setup gate** — score ≥ 8, thesis/timing ≥ 65%, R:R ≥ 2.5 for TRADE
4. **Execution gate** — IBKR critical checks + bracket levels
5. **Restraint gate** — WAIT board, weak net edge, turnover cooldown

---

## 5. UX improvements per page

### Dashboard

- ✅ Passive baseline + complexity challenge strip (this session)
- ✅ Restraint headline when active — "Restraint is correct today"
- ✅ L1–L5 collapsible hierarchy panel (this continuation)
- ✅ Expected advantage + complexity justified pills on passive strip
- 🔲 Surface authority chips in header (data wired; UI chip row deferred)

### Playbook

- ✅ Net edge on cards (`net_edge_display`)
- ✅ Guardrail label chips
- ✅ Crowding attached to rows (backend)
- ✅ Restraint banner when `restraint_high` (ranked response)
- ✅ Minimal score_card deployability on cards
- 🔲 board_mode authority banner on every load
- 🔲 Score family tooltip on hover

### Dossier

- ✅ Decision stack, guardrails, cost realism (prior work)
- 🔲 Link crowding score to playbook row vocabulary

### Portfolio

- ✅ Critical risk hierarchy, add position (prior work)
- ✅ Core + satellite architecture — role tags, exposure bands (this continuation)
- 🔲 Show passive replacement risk per holding

### Discovery / Flow / Funds

- 🔲 Persistent “RESEARCH ONLY” / “CONFIRMATION ONLY” header from `surface_authority`
- Flow: keep confirmation warning when not live-sourced

### IBKR / Ops

- ✅ Critical vs workflow (prior work)
- 🔲 Link L4 execution blocked state to Dashboard hierarchy

---

## 6. Copy rewrite suggestions

| Old / risky             | New (honest)                                                |
| ----------------------- | ----------------------------------------------------------- |
| “High conviction setup” | “Passes validated board bar” / “Pilot-eligible — half size” |
| “Strong buy signal”     | “TRADE-grade on council — confirm bracket + IBKR”           |
| “AI recommends”         | “AI commentary — not deploy authority”                      |
| “Connected”             | “IBKR connected — verify sync + brackets before send”       |
| “Top ranked #1”         | “Ranked #1 on action tier — see why-not if WATCH”           |
| “Beats the market”      | “Net edge plausibly survives cost drag — heuristic only”    |
| “Opportunity alert”     | “Research signal — board gate applies”                      |
| “Uptrend — deploy”      | “Uptrend backdrop — board WAIT until bar cleared”           |

Key phrases to reuse everywhere: _page gate > card appeal_, _research ≠ permission_, _cash is valid_, _Gross · Net after cost_.

---

## 7. Engineering roadmap

### Quick wins (1–3 days) — partial done this session

- [x] `decision_hierarchy.py` + today payload
- [x] `score_families.py` + row attachment
- [x] `passive_baseline.py` + dashboard strip
- [x] `anti_overtrading.py` + restraint in today
- [x] `crowding_narrative.py` + row attachment
- [x] `surface_authority.py`
- [x] Gross vs net in `cost_adjusted_edge.py`
- [x] L1–L5 visual panel on Dashboard (collapsible)
- [x] Core + satellite portfolio architecture
- [x] Playbook restraint banner + ranked `restraint` payload
- [x] Surface authority chips in `index.html` header (all tabs strip)
- [x] Playbook `surface_authority` in ranked response

### Medium (1–2 weeks)

- Trade memory → `recent_trade_count_5d` for restraint
- Live benchmark cache for passive strip (reduce stub fallback)
- Score family tooltips on playbook cards
- Unify Flow/Funds/Discovery headers with authority helper
- Cross-link dossier crowding ↔ playbook row
- Passive replacement risk per portfolio holding

### Deep (1+ month)

- Calibrated hit rates when n ≥ 30 (replace “model prior” copy)
- Portfolio-level passive alpha attribution
- Turnover-aware position sizing integration
- Optional TCA feed for net edge (replace heuristic)

---

## 8. File-by-file implementation plan

| Path                                         | Action                                                          |
| -------------------------------------------- | --------------------------------------------------------------- |
| `src/services/decision_hierarchy.py`         | **NEW** — L1–L5 constants + evaluators                          |
| `src/services/score_families.py`             | **NEW** — families, score_card, complexity_verdict              |
| `src/services/passive_baseline.py`           | **NEW** — strip + async live fetch                              |
| `src/services/anti_overtrading.py`           | **NEW** — restraint governor                                    |
| `src/services/crowding_narrative.py`         | **NEW** — crowding heuristic                                    |
| `src/services/surface_authority.py`          | **NEW** — tab authority resolver                                |
| `src/services/cost_adjusted_edge.py`         | **EXTEND** — gross/net aliases, compute_gross_vs_net            |
| `src/services/decision_truth_model.py`       | **EXTEND** — crowding + score_card in enrich                    |
| `src/api/routers/decision.py`                | **WIRE** — hierarchy, passive, restraint, authority in `/today` |
| `src/api/templates/index.html`               | **WIRE** — passive/complexity strip, fetchToday7 fields         |
| `src/services/core_satellite.py`             | **NEW** — sleeve roles, exposure bands                          |
| `src/services/decision_hierarchy.py`         | **EXTEND** — `can_deploy_at_level` gating helper                |
| `src/services/passive_baseline.py`           | **EXTEND** — insufficient book / local-only honesty             |
| `src/services/anti_overtrading.py`           | **EXTEND** — restraint_score, banner copy                       |
| `src/services/portfolio_decision_console.py` | **WIRE** — core_satellite in payload                            |
| `src/api/routers/playbook.py`                | **WIRE** — restraint on ranked response                         |
| `src/api/templates/index.html`               | **WIRE** — hierarchy panel, portfolio bands, playbook restraint |
| `tests/test_platform_upgrade_modules.py`     | **NEW** — unit tests                                            |
| `docs/RANDOM_WALK_PLATFORM_PROMPT.md`        | **REFERENCE** — cross-linked constitution                       |
| `docs/PLATFORM_UPGRADE_AUDIT.md`             | **THIS DOC**                                                    |

---

## 9. Session implementation summary

### Done (prior session)

1. Created `decision_hierarchy.py`, `score_families.py`, `passive_baseline.py`, `anti_overtrading.py`, `crowding_narrative.py`, `surface_authority.py`
2. Extended `cost_adjusted_edge.py` with gross/net explicit fields
3. Extended `enrich_opportunity_row` with crowding + score_card
4. Wired `/api/v7/today` with `decision_hierarchy`, `passive_baseline`, `complexity_challenge`, `restraint`, `surface_authority`
5. Dashboard UI strip for passive baseline + complexity + restraint
6. Tests in `tests/test_platform_upgrade_modules.py`

### Done (continuation — Phases C–F + D)

7. **`core_satellite.py`** — sleeve role tags (core passive / active stock / tactical / cash), exposure bands, insufficient-book honesty
8. **`passive_baseline.py`** — `insufficient_data`, `expected_advantage_label`, `complexity_justified`, portfolio context from `/today`
9. **`anti_overtrading.py`** — `restraint_score`, `restraint_high`, banner "Restraint is correct today"
10. **`decision_hierarchy.py`** — `can_deploy_at_level()` gating helper
11. **Portfolio UI** — core + satellite card with role allocation bands
12. **Dashboard UI** — L1–L5 collapsible hierarchy; passive strip pills
13. **Playbook** — restraint on ranked response + banner; deployability from score_card on cards
14. Extended tests for core_satellite, passive insufficient book, restraint score, gating helper

### Deferred to roadmap

- Book-mode dossier panels (巴芒 / Turtle / 乱世) — docs + stubs wired; full UI deferred
- Playbook ranked response metadata for authority
- Trade-memory-fed turnover
- L1–L5 visual hierarchy panel
- Live-only passive baseline (fetch exists; stub fallback when quotes fail)

---

## Cross-reference: Random Walk platform

See `docs/RANDOM_WALK_PLATFORM_PROMPT.md` for:

- Global principles A–J (aligned with user constitution)
- Humility label vocabulary (unchanged)
- Net edge formula (extended with Gross naming)
- Dossier guardrail fields (unchanged)
- Playbook card fields: add `score_card`, `crowding_narrative`, `passive_replacement_risk`

This audit **extends** Random Walk with institutional hierarchy (L1–L5), passive baseline, and restraint — without breaking existing honest gates or adding indicators.
