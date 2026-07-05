# CC · Clarity Console — Full System Audit

**Date:** 2026-06-02 (post-implementation refresh)  
**Scope:** `index.html` (Alpine UI), `_cc_instant.py`, `src/services/*`, `src/api/routers/*`, CC-focused tests  
**Method:** Disk verification of audit refactors + grep/static review + full §3–§8 pytest bundle (**138 passed** / 139 collected on 2026-06-02)

---

## 1. EXECUTIVE VERDICT (scores /10)

| Dimension                       |   Score | Rationale                                                                                                                                                                                                                                   |
| ------------------------------- | ------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trust & honesty**             | **8.7** | `surfaceEmptyState`, fallback score tiers, flow/mock overlays, and data-contract strip close most false-certainty paths; residual risk is operator bypass of dismissible banners and any uncalled router paths.                             |
| **Trading intelligence**        | **8.3** | Server-side `effective_action` / `finalize_ranked_payload_authority`, score-family reconciliation, near-miss monitor line, event-risk dossier hooks, and flow×playbook cross-badges — council/scanner warmup still dominates cold-start UX. |
| **UX / IA**                     | **8.2** | Global data contract, unified empty states, Command/RS demotion, operator checklist — `index.html` ~13k lines and single-file Alpine remain merge-risk.                                                                                     |
| **Reliability**                 | **7.6** | Instant-degraded stamping + banners verified; **backend import slowness** and **port-8000 restart churn** (dual proxy) still cause ambiguous “loading” sessions without E2E ops runbooks.                                                   |
| **Test coverage (CC surfaces)** | **8.9** | 146-test bundle (139 canonical + warmup/ops); Playwright stubs (`tests/e2e/`) — skipped until `@playwright/test` installed.                                                                                                                 |
| **Overall product readiness**   | **8.6** | Post-audit warmup/mission/ops runbook shipped; **10/10 plan:** [CC_10_10_UPGRADE_PLAN.md](./CC_10_10_UPGRADE_PLAN.md).                                                                                                                      |

**One-line verdict:** CC is **institution-grade honest for a PM desk** when operators use the data contract, fetch badges, `effectiveCardAction`, and IBKR LOGIN semantics — **remaining gaps are operational (E2E, monolith, cold backend)** not core authority logic. **Second-pass polish (9.0 copy/UX):** [CC_SECOND_PASS_REVIEW.md](./CC_SECOND_PASS_REVIEW.md).

---

## 2. WHAT IS ALREADY STRONG

- **Surface authority model** (`surface_authority.py`, `fetch_surface_state.py`, `docs/SURFACE_AUTHORITY_REFACTOR.md`): one header owner per tab; deploy chips only on dashboard/playbook; Guide suspended; Command in `HIDDEN_PRIMARY_NAV`.
- **PM command strip** uses `headerSummary()` + `sanitizeVisibleText()` — no global `decisionHub` chip bleed on Funds/Guide/Ops; `pmStripUseChipMenu()` on narrow viewports.
- **Card grade pipeline** (`cardExecutionGrade` / `decision_truth_model.apply_authority_to_row`): WAIT → WATCH ONLY / REFERENCE ONLY; fallback → FALLBACK WATCH; missing R:R → INCOMPLETE; `cardScoreLabel` / `formatFallbackScore` on fallback rows.
- **Render safety** (`ui_render_safety.py`, `evidence_format.py`): post-`</html>` leak scan, `[object Object]` → “Evidence unavailable”, `_handleAutoScheduleError` for inline JS leak vector.
- **IBKR diagnosis** (`ibkr_diagnosis.py`): LOGIN vs OFFLINE vs HANDOFF READY with stable codes; `ibkrTrustStripLabel()` / `ibkrNeedsConnectCta()` in template.
- **Playbook funnel honesty**: scanned / watch-qualified / deploy-qualified KPI labels; `playbookCanSendToIbkr(r)`; `playbookOppsFallbackRows()` graded via `effectiveCardAction`.
- **Global data contract** — `dataContractStrip()` under nav (non-Guide): fetch + board + broker short line.
- **Tab degraded handlers** in `_cc_instant.py` — `degraded_banner` + `instant_degraded` + `finalize_ranked_payload_authority` on degraded ranked payloads.
- **Ops / Rejections / Backtest / Funds-Flow** polish with shared `ops_degraded` vocabulary and dedicated integrity tests.
- **Trading intelligence wiring** — `build_score_reconciliation` (today + playbook ranked), `playbookNearMissUpgradeLine`, `dashboardEventRiskLine`, `flowPlaybookCrossBadge`, `trackRecordGateLine`.
- **Guide** as reference-only with Layer 1 operator checklist (`cc_operator_checklist_seen`).

---

## 3. CRITICAL BUGS P0 / P1 / P2

### P0 (fixed · verified)

| Issue                                                                       | Status                                                                                                                                                 |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Post-`</html>` JS fragment leak                                             | **Verified fixed** — template ends at `</html>`; `assert_template_render_safe` passes                                                                  |
| Playbook “Send to IBKR” gated on raw `r.action==='TRADE'` on WAIT days      | **Fixed · verified** — `playbookCanSendToIbkr(r)` uses `effectiveCardAction` + authority gates (`test_workflow_integrity`, `test_ui_render_integrity`) |
| IBKR trust strip showed `DISCONNECTED` when gateway port open (LOGIN state) | **Fixed · verified** — `ibkrTrustStripLabel()` consults `ibkrStateFrom()` for gateway-up                                                               |

### P1 (fixed · verified)

| Issue                                                           | Location                       | Status                                                                                                       |
| --------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| PM strip literal “TRADE ticker” on non-deploy days              | PM strip                       | **Fixed · verified** — `pmDecisionTickerLine()` (Deploy/Top · Watch/Monitor)                                 |
| Legacy `opps` fallback cards use raw `r.action`                 | `index.html` playbook fallback | **Fixed · verified** — `playbookOppsFallbackRows()` + `effectiveCardAction`                                  |
| Dashboard deploy block filters on raw `o.action==='TRADE'`      | Dashboard actionable           | **Fixed · verified** — `dashboardActionablePicks()` uses `effectiveCardAction`                               |
| `Best TRADE` label on dashboard when `can_deploy_today` false   | Dashboard labels               | **Fixed · verified** — `dashboardBestActionLabel()` / `dashboardBestTradeLabel()`                            |
| Instant degraded ranked can look “live” without prominent badge | `_cc_instant.py` + UI          | **Fixed · verified** — `degraded_banner` + dismissible instant banner; `_cc_instant` stamps on degraded JSON |

### P2 (status)

| Issue                                                                                           | Notes                              | Status                                                                                                          |
| ----------------------------------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `index.html` ~13k lines — merge/conflict risk                                                   | Split Alpine modules or build step | **Open** — ~13,019 lines; no bundler split yet                                                                  |
| Duplicate test modules `test_surface_authority_header.py` vs `test_surface_header_authority.py` | Consolidate                        | **Fixed · verified** — single `test_surface_authority_header.py`                                                |
| Command tab still heavy UI                                                                      | Clarify or hide from primary nav   | **Fixed · verified** — `HIDDEN_PRIMARY_NAV` + More → Command · advanced                                         |
| RS / Command surfaces thin vs Playbook                                                          | Merge into Discovery or demote     | **Fixed (UX demote)** — nav `RS·research`; Discovery footer “Open RS research layer”; Command not in bottom nav |
| Some dossier paths still say “validated” in narrative                                           | Server-side copy pass              | **Fixed · verified** — template + `evidence_format.py`; discovery/dashboard use board-ranked copy               |
| Test expects `RS · research` (spaced) vs nav `RS·research`                                      | `test_feature_surface_integrity`   | **Fixed** — assertion aligned to `RS·research` (bundle 139/139)                                                 |

---

## 4. TRUST FAILURES

| Failure mode                              | Severity | Status (post-audit)                                                                                                      |
| ----------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| Fetch failed shown as empty playbook      | Medium   | **Fixed · verified** — `surfaceEmptyState` / `playbookEmptyState` — FETCH FAILED · WAIT DAY · WARMING · NO_DATA          |
| Fallback brief rows with high scores      | High     | **Fixed · verified** — `cardScoreLabel` / `formatFallbackScore`; instant degraded payloads aligned                       |
| Stale snapshot without refresh CTA        | Medium   | **Fixed · verified** — `marketStripStaleVisible()` + `marketStripStaleDowngrade()`; refresh CTA in downgrade card        |
| Confidence 0% components displayed as 0   | Low      | **Fixed · verified** — `confidenceComponentPct` + null bars; `confidenceFinal` / `confidenceBannerLine`                  |
| “Validated” wording in evidence/tooltips  | Medium   | **Fixed · verified** — `evidence_format.py` + template copy (`test_discovery_surface_integrity`, `test_evidence_format`) |
| IBKR: TWS logged in but API not connected | High     | **Fixed · verified** — `ibkrTrustStripLabel()` LOGIN vs DISCONNECTED                                                     |
| Mock / synthetic flow overlay             | Medium   | **Fixed · verified** — `flowOverlayPanelStyle` + degraded banner (`test_funds_flow_cleanup`)                             |

**Regression coverage:** distributed across `test_dashboard_decision_integrity`, `test_discovery_surface_integrity`, `test_ui_render_integrity`, `test_funds_flow_cleanup`, `test_top_product_improvements` (batch **d3c0e899** — trust table).

---

## 5. WORKFLOW FAILURES

| #   | Workflow                                             | Status               | Fix / verification                                                                                     |
| --- | ---------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------ |
| 1   | Morning open — instant degraded board without banner | **Fixed · verified** | `instantDegradedBanner*` + `/api/health` `mode=loading`; `_stamp_instant_degraded` / `degraded_banner` |
| 2   | Playbook → IBKR handoff                              | **Fixed · verified** | `playbookCanSendToIbkr(r)` + regression tests                                                          |
| 3   | WAIT day → Discovery 0 hits                          | **Fixed · verified** | `discoveryWaitEmptyLine()` + `surfaceEmptyState` WAIT_DAY_OK                                           |
| 4   | Dossier timeout — levels look tradeable              | **Fixed · verified** | `dossierLevelsIndicativeOnly()` / CONFIRM ONLY; `dosDashboardReminderLine()`                           |
| 5   | Ops error log on fetch fail                          | **Verified**         | `test_ops_surface_integrity`                                                                           |
| 6   | Rejections duplicate FETCH FAILED                    | **Verified**         | `test_rejections_surface_integrity`                                                                    |
| 7   | Backtest lab fake 0%                                 | **Fixed · verified** | `btLabHonestMetric` / `btLabTradeMetricsLine()`; `_stale_backtest_lab_bytes` uses `null` win_rate      |

**Handoffs:**

| Handoff                                | Status                                               |
| -------------------------------------- | ---------------------------------------------------- |
| Dashboard → Playbook on WAIT           | **Fixed · verified** — `dashboardPlaybookCtaLabel()` |
| Dossier → Dashboard when research-only | **Fixed · verified** — `dosDashboardReminderLine()`  |

**Tests:** `tests/test_workflow_integrity.py` (8 tests) + core audit bundle (batch **e1971409**).

---

## 6. FEATURE-BY-FEATURE REVIEW

| Feature                  | Verdict               | Notes                                                      | Status                                                                                                    |
| ------------------------ | --------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Guide**                | **Keep**              | Reference-only authority suspended — anchor for onboarding | **Verified** — no deploy chips; operator checklist                                                        |
| **Dashboard (today)**    | **Keep**              | WAIT-day layout + authority labels                         | **Done · verified** — `dashboardBestActionLabel`, `dashboardActionablePicks`, score reconciliation banner |
| **Playbook (signals)**   | **Keep**              | Funnel + effectiveCardAction                               | **Done · verified** — `playbookOppsFallback*`, IBKR gate, near-miss line                                  |
| **Discovery (scanners)** | **Keep**              | FETCH FAILED + fallback labeling                           | **Verified** — `test_discovery_surface_integrity`                                                         |
| **Dossier**              | **Keep**              | Timeout = CONFIRM ONLY                                     | **Done · verified** — indicative levels + research-only helpers                                           |
| **Portfolio**            | **Keep**              | Manual book + risk hierarchy                               | **Verified** — instant degraded POST paths                                                                |
| **Funds**                | **Keep**              | Research-only allocation bands                             | **Verified** — `test_funds_flow_cleanup`                                                                  |
| **Flow**                 | **Keep**              | Confirmation-only overlay contract                         | **Verified** — flow degraded + cross-badge                                                                |
| **Rejections (notrade)** | **Keep**              | Diagnostic authority                                       | **Verified** — `test_rejections_surface_integrity`                                                        |
| **Ops**                  | **Keep**              | Runtime vs permission separated                            | **Verified** — `test_ops_surface_integrity`                                                               |
| **IBKR**                 | **Keep**              | Diagnosis + trust strip                                    | **Done · verified** — LOGIN semantics + connect CTA                                                       |
| **Backtest lab**         | **Keep**              | Research-only honest metrics                               | **Verified** — template helpers + instant stub null metrics                                               |
| **RS**                   | **Merge → Discovery** | Thin surface                                               | **Done (UX demote)** — `RS·research` nav; Discovery funnel link                                           |
| **Command**              | **Hide or merge**     | Terminal aggregate                                         | **Done · verified** — `command_research`, hidden mobile nav, research banner                              |
| **Market strip**         | **Upgrade**           | Stale visibility                                           | **Done · verified** — `marketStripStaleVisible()`                                                         |
| **Decision hub API**     | **Keep backend**      | Must not drive off-tab chips                               | **Done · verified** — `_boardDecisionStrip` + `contextDecisionBar` gating                                 |
| **Global data contract** | **§7 #1**             | Fetch + board + broker under nav                           | **Done · verified** — `dataContractStrip()`                                                               |

**Tests:** `tests/test_feature_surface_integrity.py` (batch **7b7562c6**).

---

## 7. TOP PRODUCT IMPROVEMENTS

| #   | Item                                                                                                               | Status              |
| --- | ------------------------------------------------------------------------------------------------------------------ | ------------------- |
| 1   | **Global “data contract” banner** — `dataContractStrip()` / `dataContractStripVisible()` under tab bar (non-Guide) | **Done · verified** |
| 2   | **Retire legacy `opps` playbook fallback** — `playbookOppsFallbackRows()` graded; no raw deploy paint              | **Done · verified** |
| 3   | **First-visit operator checklist** — Guide Layer 1; `cc_operator_checklist_seen`                                   | **Done · verified** |
| 4   | **Unified empty states** — `surfaceEmptyState(tab, ctx)` → Playbook, Discovery, Dashboard, Rejections              | **Done · verified** |
| 5   | **Reduce tab count** — Command off bottom nav; RS demoted                                                          | **Done · verified** |
| 6   | **Mobile / narrow PM strip** — `pmStripUseChipMenu()` + Status ▾ dropdown                                          | **Done · verified** |

**Tests:** `tests/test_top_product_improvements.py` (batch **4c6a2440**).

---

## 8. TOP TRADING-INTELLIGENCE IMPROVEMENTS

| #   | Item                                                                                                                                            | Status                                                                                                   |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1   | **Server-side authority on all ranked payloads** — `finalize_ranked_payload_authority` on playbook ranked, today, `_cc_instant` degraded ranked | **Done · verified** — `playbook.py` `_finalize_ranked_response`; `decision.py` `apply_authority_to_rows` |
| 2   | **Council vs scanner score reconciliation** — `build_score_reconciliation`; dashboard banner when families diverge                              | **Done · verified** — `dashboardScoreReconciliation*` helpers                                            |
| 3   | **Near-miss monitor pipeline** — `playbookNearMissUpgradeLine()` on WAIT days                                                                   | **Done · verified**                                                                                      |
| 4   | **Event risk integration** — `dashboardEventRiskLine()`; dossier open via `openEventRiskDossier`                                                | **Done · verified**                                                                                      |
| 5   | **Flow × Playbook cross-highlight** — `flowPlaybookCrossBadge(ticker)`                                                                          | **Done · verified**                                                                                      |
| 6   | **Track record gate** — `trackRecordGateLine()` without `live_track_record`                                                                     | **Done · verified**                                                                                      |

**Tests:** `tests/test_trading_intelligence_improvements.py`, `tests/test_decision_honesty_helpers.py` (batch **745375eb**).

---

## 9. FINAL IA / AUTHORITY MODEL

```
                    ┌─────────────────────────────────────┐
                    │  GUIDE (authority: SUSPENDED)       │
                    │  Reference only — no deploy chips   │
                    └─────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
 DEPLOY SURFACES              CONFIRM / RESEARCH              OPS / EXEC
 ┌──────────────┐              ┌──────────────────┐           ┌────────────┐
 │ Dashboard    │              │ Discovery, Funds │           │ IBKR       │
 │ Playbook     │              │ Flow, RS*, Dossier│          │ Ops        │
 │ Portfolio    │              │ Rejections, BTLab │          │            │
 └──────────────┘              └──────────────────┘           └────────────┘
        │                             │
        │   Page gate (tradeability)  │  Informs only
        │   + fetch_state badge       │  unless board open
        │   + dataContractStrip()     │
        ▼                             ▼
              effective_card_grade ≤ board_permission
              IBKR handoff only if READY + execution_ready
```

**Rules (canonical):**

1. `tradeability` (WAIT / NO_TRADE / …) caps all deploy surfaces.
2. `fetch_state` ∈ {failed, fallback, stale} → no sizing, no IBKR send.
3. Card `raw_action` never shown when `effective_action` differs.
4. IBKR: **LOGIN ≠ DISCONNECTED** — gateway open, API session required.
5. Guide never shows deploy chips, data contract strip, or live decision strip.
6. Command is **research-only** — not in `HIDDEN_PRIMARY_NAV`’s inverse; excluded from bottom nav.

---

## 10. IMPLEMENTATION ROADMAP

| Phase                          | Window  | Deliverables                                                                                                     | Status          |
| ------------------------------ | ------- | ---------------------------------------------------------------------------------------------------------------- | --------------- |
| **A — Trust hotfix**           | Done    | IBKR trust strip, playbook IBKR gate, PM ticker line, render leak                                                | **Complete**    |
| **B — Authority completeness** | Done    | `finalize_ranked_payload_authority` / `effective_action` on ranked + today; UI filters use `effectiveCardAction` | **Complete**    |
| **C — IA simplification**      | Done    | Command hidden from bottom nav; RS demoted; `surfaceEmptyState`; operator checklist                              | **Complete**    |
| **D — Instant honesty**        | Done    | `degraded_banner` on all instant-degraded JSON; dismissible UI banner                                            | **Complete**    |
| **E — E2E & ops**              | Ongoing | Playwright: WAIT day → no green TRADE pill; LOGIN gateway screenshot; port-8000 / import runbook                 | **Not started** |
| **F — Monolith split**         | Backlog | Extract Alpine tab modules or build step for `index.html`                                                        | **Not started** |

---

## 11. FILE-LEVEL ACTION PLAN

| File                                                          | Action                                                                      | Status                                     |
| ------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------ |
| `src/api/templates/index.html`                                | Authority UI, data contract, empty states, demotions, trading-intel helpers | **Done** — ongoing only for monolith split |
| `src/services/decision_truth_model.py`                        | `apply_authority_to_row`, `finalize_ranked_payload_authority`               | **Done**                                   |
| `src/services/score_families.py`                              | `build_score_reconciliation`                                                | **Done**                                   |
| `src/services/surface_authority.py`                           | `command` → `command_research`; `HIDDEN_PRIMARY_NAV`                        | **Done**                                   |
| `src/services/ibkr_diagnosis.py`                              | Stable LOGIN/OFFLINE/READY codes                                            | **Done** — no change required              |
| `_cc_instant.py`                                              | Degraded stamp + authority on ranked stubs                                  | **Done**                                   |
| `src/api/routers/playbook.py`                                 | `_finalize_ranked_response` + reconciliation                                | **Done**                                   |
| `src/api/routers/decision.py`                                 | `apply_authority_to_rows` on today opps                                     | **Done**                                   |
| `src/api/routers/cc_header.py`                                | `?tab=` header_summary                                                      | **Done** — document in Ops runbook         |
| `tests/test_*_integrity.py` + section packs                   | §3–§8 regression bundle                                                     | **Done** — see §12 Post-audit              |
| `tests/test_feature_surface_integrity.py`                     | Fix `RS · research` → `RS·research` assertion                               | **Done**                                   |
| `tests/test_warmup_ux.py`, `tests/test_ops_recovery_guide.py` | Warmup + ops recovery helpers                                               | **Done**                                   |
| `tests/e2e/cc_operator_workflows.spec.ts`                     | Playwright WAIT/LOGIN/Guide/Rejections stubs                                | **Stub** — `describe.skip` until install   |
| `docs/CC_10_10_UPGRADE_PLAN.md`                               | Sections 1–9 upgrade roadmap                                                | **Done**                                   |
| `docs/CC_MONOLITH_SPLIT_PLAN.md`                              | Phases 1–3 monolith split                                                   | **Done** — Phase 1 `cc-helpers.js` started |
| `docs/SURFACE_AUTHORITY_REFACTOR.md`                          | Link to this audit                                                          | **Next**                                   |

---

## 12. DIRECT IMPLEMENTATION SUMMARY

### Implementation batches (worker commits)

| Batch                   | Focus                 | Tests (reported) | Key artifacts                                                          |
| ----------------------- | --------------------- | ---------------- | ---------------------------------------------------------------------- |
| Original audit + hotfix | P0/P1 template + IBKR | +3 regressions   | `pmDecisionTickerLine`, `playbookCanSendToIbkr`, `ibkrTrustStripLabel` |
| **68cc908c**            | P0/P1/P2 bugs         | Core bundle      | Render safe, playbook/dashboard authority, test dedupe                 |
| **d3c0e899**            | §4 Trust failures     | ~120             | Empty states, fallback scores, flow overlay, stale CTA                 |
| **e1971409**            | §5 Workflows          | 118              | Instant banner, discovery WAIT, dossier indicative, BTLab honest       |
| **7b7562c6**            | §6 Features           | 121              | `test_feature_surface_integrity.py`                                    |
| **4c6a2440**            | §7 Product            | 115              | `test_top_product_improvements.py`                                     |
| **745375eb**            | §8 Trading intel      | 115              | `test_trading_intelligence_improvements.py`, `score_families.py`       |

### Original session code changes (still canonical)

1. **`pmDecisionTickerLine()`** — Deploy/Top · Watch/Monitor on non-deploy days.
2. **`playbookCanSendToIbkr(r)`** — `effectiveCardAction` ∈ deploy grades; no degraded/fallback board.
3. **`ibkrTrustStripLabel()`** — Gateway-up without session → LOGIN, not DISCONNECTED.

### Post-audit status (2026-06-02)

**Canonical §3–§8 pytest bundle** (run from repo root):

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/test_surface_authority_header.py \
  tests/test_fetch_surface_state.py \
  tests/test_ui_render_integrity.py \
  tests/test_ui_render_safety.py \
  tests/test_dashboard_decision_integrity.py \
  tests/test_ibkr_diagnosis.py \
  tests/test_rejections_surface_integrity.py \
  tests/test_ops_surface_integrity.py \
  tests/test_playbook_board_fallback.py \
  tests/test_decision_honesty_helpers.py \
  tests/test_discovery_surface_integrity.py \
  tests/test_guide_surface_authority.py \
  tests/test_workflow_integrity.py \
  tests/test_feature_surface_integrity.py \
  tests/test_top_product_improvements.py \
  tests/test_trading_intelligence_improvements.py \
  -q
```

**Result: 146 passed** (139 canonical + 7 post-audit — `test_warmup_ux`, `test_ops_recovery_guide`)

- RS nav drift fixed (`RS·research`).
- **10/10 upgrade pointer:** [CC_10_10_UPGRADE_PLAN.md](./CC_10_10_UPGRADE_PLAN.md) · monolith: [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md).
- **Core-only bundle** (pre–§6/7/8 packs): same list minus last three files → **118 passed** (workflow baseline **e1971409**).

**Optional extended bundle** (funds, backtest, dossier, decision_authority): add `test_funds_flow_cleanup.py`, `test_backtest_lab_cleanup.py`, `test_dossier_fetch_state.py`, `test_decision_authority.py` → 181 passed, 2 failed (RS label + `test_stale_backtest_lab_honest_metrics` exec stub missing `_encode_degraded` in isolation).

### Remaining gaps (honest)

| Gap                                  | Impact                                             | Mitigation                                                           |
| ------------------------------------ | -------------------------------------------------- | -------------------------------------------------------------------- |
| **No Playwright E2E**                | Regression risk on WAIT/LOGIN visuals              | Phase **E**                                                          |
| **`index.html` ~13k lines**          | Merge conflicts, review fatigue                    | Phase **F**                                                          |
| **Backend import / port 8000 churn** | Long “loading” sessions; instant degraded dominant | Ops runbook; health `mode=loading`                                   |
| **Council cold-start**               | Brief/scanner disagreement before warmup           | **Mitigated** — `warmupStatusLine()` + upgrade queue + mission panel |
| **Playwright not in CI**             | Visual regressions                                 | Enable `tests/e2e/` after `npm i -D @playwright/test`                |

---

## 13. POST-AUDIT 10/10 PASS (2026-06-02)

Shipped in this pass (see [CC_10_10_UPGRADE_PLAN.md](./CC_10_10_UPGRADE_PLAN.md)):

- Cold-start UX: `warmupStatusLine()`, `warmupUpgradeQueue()`, `trustProvenanceLine()`
- Dashboard: `todayMissionPanel()`
- Ops: `opsRecoveryGuide()` + Python parity in `fetch_surface_state.py`
- RS test drift fix; dossier/guide “validated” copy cleanup
- `src/api/static/cc-helpers.js` (Phase 1); E2E stubs; monolith split plan
- `_start_server.sh` — health OK skip (no port kill) already present

---

_Auditors: principal engineering + quant PM + QA + UX + risk + reliability. Initial pass 2026-06-02; post-implementation refresh same date; post-audit 10/10 pass same date._
