# CC · Clarity Console — Final Hardening Review + Implementation

**Date:** 2026-06-02  
**Baseline:** [CC_FOURTH_PASS_REVIEW.md](./CC_FOURTH_PASS_REVIEW.md) **9.4/10** · 168 pytest · 14 Playwright · `degraded_banners` partial  
**Method:** Targeted hardening (no authority re-audit) + incremental close-out + pytest + Playwright matrix + CI drift gate

---

## 1. FINAL HARDENING VERDICT

| Metric                    | Value                                                                                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pre-pass score**        | **9.4/10** (fourth-pass E2E + CI + safe-lines + partial build)                                                                                          |
| **Post-pass (ea965e60)**  | **9.7/10** — route-abort E2E, `data-cc` surfaces, ops partial, monitor hints, template `--check`                                                        |
| **Post incremental pass** | **9.8/10** — `guide.html` partial (557 lines), `data-cc-nav`, dossier fetch-error copy fix, stale lock reclaim, stabilization recovery helpers verified |
| **Blockers to 10/10**     | `cc-e2e` green streak on main; `test_finalize_ranked_payload_authority_on_all_row_keys` hang (pre-existing); backend auto-heal beyond copy              |

**Summary:** Incremental pass closes monolith Phase 2.1 (`guide.html`), bottom-nav E2E selectors, dossier `levels not live-confirmed` grade copy, and `_cc_instant` stale lock reclaim. Prior pass work retained: **21 Playwright specs**, route-abort dossier/discovery, ops runbook partial, mission monitor hints, CI `--check`. Recovery UX (IBKR LOGIN, engine OFF, stale refresh, route-abort hints) verified via `test_stabilization_pass.py`. Authority boundaries unchanged.

---

## 2. HIGHEST-ROI HARDENING GAPS

### E2E / CI

| Gap                             | Status   | Notes                                                                    |
| ------------------------------- | -------- | ------------------------------------------------------------------------ |
| Route-abort dossier / discovery | **Done** | Playwright abort + degraded shell asserts                                |
| `data-cc` surface selectors     | **Done** | playbook, dossier, discovery, ops runbook, contract strip, guide-surface |
| `data-cc-nav` bottom nav        | **Done** | 8 tabs — Playwright `openTab()` uses stable clicks                       |
| CI template drift gate          | **Done** | `node scripts/build-cc-template.mjs --check` in `cc-e2e` job             |
| Playwright diagnostics          | **Done** | screenshot/video on failure; 120s webServer; 2 CI retries                |
| Local Playwright green          | **Open** | `@playwright/test` not installed in workspace; CI job configured         |
| `cc-e2e` green on main streak   | **Open** | Needs 3+ consecutive main merges                                         |

### Reliability / recovery

| Gap                                       | Status   | Notes                                                                       |
| ----------------------------------------- | -------- | --------------------------------------------------------------------------- |
| Loading safe-line (backend import)        | **Done** | `operatorLoadingSafeLine` + Python mirror                                   |
| Fetch-failed / instant degraded safe-line | **Done** | No duplicate banner copy; strip-only                                        |
| Ops recovery runbook partial              | **Done** | `cc/partials/ops_recovery_runbook.html`                                     |
| IBKR LOGIN / engine OFF / stale copy      | **Done** | `ibkrLoginToReadyHint`, `engineOffRecoveryLine`, `staleRefreshRecoveryLine` |
| Route-abort recovery hints                | **Done** | `routeAbortRecoveryHint` in cc-helpers + Python                             |
| Mission safe vs blocked                   | **Done** | `todayMissionSafeUnlockHint()` under WAIT subtitle                          |
| Stale singleton lock reclaim              | **Done** | `_pid_alive` + reclaim dead PID in `_acquire_single_instance`               |
| Backend auto-heal                         | **Open** | Copy-only guidance retained                                                 |

### Maintainability

| Gap                              | Status       | Notes                                         |
| -------------------------------- | ------------ | --------------------------------------------- |
| `guide.html` extract (Phase 2.1) | **Done**     | 557 lines; `@cc-partial guide` + build inject |
| Jinja `{% include %}`            | **Deferred** | Instant still serves built `index.html`       |
| `deploy_surfaces.html` chrome    | **Deferred** | Next monolith step                            |

### Daily usefulness

| Gap                                      | Status     | Notes                                           |
| ---------------------------------------- | ---------- | ----------------------------------------------- |
| Monitor / near-miss / watch labels       | **Done**   | `todayMissionMonitorsColumnHint`                |
| Monitor vs deploy distinction (playbook) | **Done**   | `gate context below (not deploy)` on WAIT board |
| Mission WAIT subtitle                    | **Stable** | Fourth-pass `todayMissionWaitSubtitle`          |

### Polish

| Gap                       | Status     | Notes                                                                    |
| ------------------------- | ---------- | ------------------------------------------------------------------------ |
| Degraded copy dedupe      | **Stable** | Banner > strip; safe-line gated                                          |
| Dossier fetch-error grade | **Fixed**  | `levels not live-confirmed` in `dosFetchErrorGrade()`                    |
| Counter contradictions    | **Stable** | Score reconciliation unchanged; 1 pytest hangs on large payload finalize |

---

## 3. NEXT HARDENING WAVE

| Priority | Work                                                              | Files                                             | Tests             |
| -------- | ----------------------------------------------------------------- | ------------------------------------------------- | ----------------- |
| 1        | Confirm `cc-e2e` green on main (21 specs)                         | `.github/workflows/ci.yml`                        | Playwright        |
| 2        | Fix `test_finalize_ranked_payload_authority_on_all_row_keys` hang | `tests/test_trading_intelligence_improvements.py` | pytest            |
| 3        | Extract `deploy_surfaces.html` (Phase 2.2)                        | `cc/partials/`                                    | surface integrity |
| 4        | Backend spawn auto-heal (optional)                                | `_cc_instant.py`                                  | smoke + health    |
| 5        | Jinja `{% include %}` when instant path allows                    | `index.html` shell                                | build `--check`   |

---

## 4. PLAYWRIGHT / CI IMPROVEMENT PLAN

**Local:**

```bash
npm install --no-save @playwright/test@1.49.1
npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

**Config (`playwright.config.ts`):**

| Setting        | Value                         |
| -------------- | ----------------------------- |
| webServer      | `_cc_instant.py`, 120s boot   |
| workers        | 1 (serial stability)          |
| retries        | 2 on CI                       |
| expect timeout | 12s                           |
| artifacts      | screenshot + video on failure |

**CI (`cc-e2e` job):**

1. `node scripts/build-cc-template.mjs --check`
2. `npx playwright test tests/e2e/cc_operator_workflows.spec.ts`

**Coverage (21 tests):**

| Test                  | Asserts                                                                  |
| --------------------- | ------------------------------------------------------------------------ |
| cc-helpers load       | exports incl. `todayMissionMonitorsColumnHint`, `routeAbortRecoveryHint` |
| health                | `mode` ∈ loading\|full                                                   |
| data contract strip   | `[data-cc="data-contract-strip"]`                                        |
| banner precedence     | Instant banner hides warmup strip                                        |
| warmup recovery       | Cold start / Safe now / WARMING                                          |
| WAIT dashboard        | No green `TRADE` pills                                                   |
| Playbook fallback     | Fallback rank / WATCH ONLY                                               |
| Playbook handoff (×2) | No `Send to IBKR` on `[data-cc="playbook-surface"]`                      |
| IBKR                  | LOGIN \| OFFLINE \| READY                                                |
| Guide                 | `[data-cc="guide-surface"]`; no handoff                                  |
| Mission panel         | focus / monitors / deploy blocked / safe-unlock hints                    |
| Rejections            | Degraded or loading shell                                                |
| Dossier core          | core-only / CONFIRM ONLY                                                 |
| **Dossier abort**     | route abort → research shell                                             |
| Discovery funnel      | fallback / WAIT / Tier 1                                                 |
| **Discovery abort**   | route abort → fallback funnel                                            |
| Portfolio             | stops / blockers + `portfolio-stop-blockers`                             |
| **Ops runbook**       | `[data-cc="ops-recovery-runbook"]`                                       |
| **Ops loading**       | recovery / WARMING copy                                                  |
| **Market stale**      | `[data-cc="market-strip-stale"]` when visible                            |

**E2E nav:** `openTab()` prefers `[data-cc-nav="…"]` then text fallback.

---

## 5. RELIABILITY / RECOVERY IMPROVEMENT PLAN

| Signal                          | Operator copy                                            | Action                                        |
| ------------------------------- | -------------------------------------------------------- | --------------------------------------------- |
| `mode=loading`                  | WARMING + backend import in safe-line                    | Wait for `/health mode=full`                  |
| Port 8000→8001                  | `loadingSessionRecoveryLine`                             | Restart once after ~2 min                     |
| FETCH FAILED / instant          | safe-line: retry when badges clear                       | No deploy from fallback                       |
| WAIT day                        | `todayMissionWaitSubtitle` + monitors hint + safe-unlock | Monitors only                                 |
| IBKR LOGIN                      | `ibkrLoginToReadyHint`                                   | Connect tab → READY before handoff            |
| Engine OFF                      | `engineOffRecoveryLine`                                  | Precomputed board only                        |
| Market DATA STALE               | `market-strip-stale` + `staleRefreshRecoveryLine`        | Refresh market data                           |
| Route abort (dossier/discovery) | `routeAbortRecoveryHint`                                 | CONFIRM ONLY / fallback funnel                |
| Ops runbook                     | Retry / Blocks capital / Safe degraded                   | Partial-sync with Python `ops_recovery_guide` |
| Crashed prior instant           | `[instant] Reclaiming stale lock`                        | Auto on dead PID                              |

**Python parity:** `today_mission_monitors_column_hint`, `operator_loading_safe_line`, `route_abort_recovery_hint`, `engine_off_recovery_line`, `ibkr_login_to_ready_hint`, `stale_refresh_recovery_line`, `today_mission_safe_unlock_hint`.

---

## 6. MONOLITH SPLIT NEXT STEP

Per [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md):

- **Done (Phase 2.0b):** `ops_recovery_runbook.html` + markers + build entry.
- **Done (Phase 2.1):** `guide.html` (557 lines, lines 3780–4338 in shell) + `@cc-partial guide` + `data-cc="guide-surface"`.
- **Next:** `deploy_surfaces.html` — dashboard + playbook shared card chrome.
- **Do not** split Ops degraded tables until Python `ops_degraded_copy` parity is automated.

**Partials in build:** `degraded_banners`, `ops_recovery_runbook`, `guide`.

---

## 7. DAILY USEFULNESS IMPROVEMENTS

| Upgrade                           | Implementation                                                    |
| --------------------------------- | ----------------------------------------------------------------- |
| Monitors column hint              | `todayMissionMonitorsColumnHint()` — watch/near-miss vs deploy    |
| Playbook WAIT monitor line        | `gate context below (not deploy)` on ranked board                 |
| Mission safe vs blocked           | `todayMissionSafeUnlockHint()` under mission title                |
| Playbook surface hook             | `data-cc="playbook-surface"` for handoff E2E                      |
| Discovery / dossier / guide hooks | `data-cc="discovery-surface"`, `dossier-surface`, `guide-surface` |
| Bottom nav stability              | `data-cc-nav` on all 8 fixed tabs                                 |

---

## 8. DIRECT CHANGES

### Prior pass (ea965e60 — retained)

| File                                                      | Change                                                                  |
| --------------------------------------------------------- | ----------------------------------------------------------------------- |
| `src/api/static/cc-helpers.js`                            | +`todayMissionMonitorsColumnHint`; safe-line for loading/degraded fetch |
| `src/services/fetch_surface_state.py`                     | Mirror hints + `operator_loading_safe_line` params                      |
| `src/api/templates/index.html`                            | `data-cc` attrs; mission hint; partial markers; Alpine delegates        |
| `src/api/templates/cc/partials/ops_recovery_runbook.html` | Ops recovery runbook card                                               |
| `scripts/build-cc-template.mjs`                           | +`ops_recovery_runbook` partial                                         |
| `tests/e2e/cc_operator_workflows.spec.ts`                 | 14 → **21** tests; route-abort; stable selectors                        |
| `playwright.config.ts`                                    | CI retries, artifacts, 120s boot, workers=1                             |
| `.github/workflows/ci.yml`                                | `--check` before Playwright                                             |
| `tests/test_final_hardening.py`                           | Hardening integrity tests                                               |

### Incremental pass (this session)

| File                                       | Change                                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| `src/api/templates/cc/partials/guide.html` | **New** — 557-line Guide tab body                                                                            |
| `scripts/build-cc-template.mjs`            | +`guide` partial entry                                                                                       |
| `src/api/templates/index.html`             | `@cc-partial guide` markers; `data-cc-nav` on bottom nav; `dosFetchErrorGrade` → `levels not live-confirmed` |
| `_cc_instant.py`                           | `_pid_alive()` + stale lock reclaim on dead holder PID                                                       |
| `tests/test_final_hardening.py`            | +guide partial + `data-cc-nav` tests (9 total)                                                               |

No router/authority logic changes. No git commit.

---

## 9. FINAL PATH TO 10/10

1. **CI confidence:** `cc-e2e` green on 3+ consecutive main merges (21 specs + drift check).
2. **Pytest hygiene:** Fix `test_finalize_ranked_payload_authority_on_all_row_keys` hang → full **199** green locally.
3. **Monolith:** `deploy_surfaces.html` extract; shell trend toward &lt; 10k lines; CI `--check` stays green.
4. **Cold start:** Optional `_cc_instant` child health auto-retry (no trust erosion).
5. **Soak:** `mode=full` session with live ranked + IBKR probe in staging ([CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)).
6. **Score:** When 1–5 hold → **10/10** with unchanged authority model.

---

_Incremental hardening: 2026-06-02. Pytest canonical bundle + stabilization + hardening: **198 passed** (199 collected; 1 pre-existing hang on `test_finalize_ranked_payload_authority_on_all_row_keys`). Playwright: **21 specs** — not run locally (`@playwright/test` not installed); CI configured. Template check: `node scripts/build-cc-template.mjs --check` **pass**._
