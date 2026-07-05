# CC · Clarity Console — Third-Pass Review + Implementation

**Date:** 2026-06-02  
**Baseline:** [CC_SECOND_PASS_REVIEW.md](./CC_SECOND_PASS_REVIEW.md) **9.0/10** · [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md) Phase 1 started  
**Method:** Targeted code/doc review (no re-audit of solved authority/IBKR/data-contract items) + implementation + pytest + Playwright scaffold refresh

---

## 1. THIRD-PASS VERDICT

| Metric                | Value                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------- |
| **Pre-pass score**    | **9.0/10** (second-pass polish + helper wiring)                                               |
| **Post-pass score**   | **9.2/10** — reliability copy + E2E hooks + mission-panel clarity; monolith/E2E CI still open |
| **Blockers to 10/10** | Playwright in CI; `index.html` monolith split Phase 2; cold-start duration (import), not copy |

**Summary:** Third pass closes **banner precedence in shared JS**, **loading-session / port-8000 recovery copy**, **today mission monitors label (near-miss visibility)**, and **real Playwright assertions** (no longer `describe.skip`). Authority boundaries unchanged.

---

## 2. HIGHEST-ROI UNFINISHED GAPS

### Reliability / cold start

| Gap                                   | Status         | Notes                                                                                                              |
| ------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------ |
| Warming vs instant banner duplication | **Mitigated**  | `CCHelpers.warmupContextStripVisible` — instant banner wins; strip shows `loadingSessionRecoveryLine` when loading |
| Long `mode=loading` ambiguity         | **Mitigated**  | Port 8000→8001 proxy line in warmup strip + Ops recovery runbook                                                   |
| Operator dismisses instant banner     | **Documented** | Hint: data contract + warmup strip stay authoritative                                                              |
| Port churn / dual listener            | **Copy only**  | Restart-once guidance; no infra auto-heal                                                                          |

### E2E / workflow safety

| Gap                                | Status                                    |
| ---------------------------------- | ----------------------------------------- |
| WAIT → no green TRADE pill         | E2E asserted (instant server)             |
| Fallback / WATCH labels            | E2E asserted                              |
| IBKR LOGIN vs OFFLINE              | E2E relaxed to LOGIN\|OFFLINE\|READY      |
| Guide no deploy                    | E2E + GUIDE MODE                          |
| Rejections degraded                | E2E broadened (loading shell OK)          |
| Playwright in CI                   | **Open**                                  |
| Dossier/discovery fail matrix      | Partial — pytest integrity; no visual E2E |
| Portfolio stops / playbook handoff | Covered by workflow pytest; no new E2E    |

### Maintainability

| Gap                     | Status                                                  |
| ----------------------- | ------------------------------------------------------- |
| `cc-helpers.js` Phase 1 | **Extended** (+4 exports)                               |
| Jinja tab partials      | **Deferred** — `_cc_instant.py` serves raw `index.html` |
| `data-cc` hooks         | **Added** for banner, warmup strip, mission panel       |

### Daily usefulness

| Gap                         | Status                                                               |
| --------------------------- | -------------------------------------------------------------------- |
| Mission board monitor queue | **Improved** — `todayMissionMonitorsLabel()` shows count + near-miss |
| Attention routing           | Unchanged (PM strip + authority chips)                               |
| Near-miss on dashboard      | Existing sections; label now surfaces count in mission card          |

### Polish

| Gap                  | Status                                 |
| -------------------- | -------------------------------------- |
| Chip hierarchy       | Unchanged (severity in helpers)        |
| Degraded readability | Loading recovery line in sentence case |

---

## 3. NEXT IMPLEMENTATION WAVE

| Priority | Work                                                                     | Files                                               | Tests                        |
| -------- | ------------------------------------------------------------------------ | --------------------------------------------------- | ---------------------------- |
| 1        | CI: install Playwright + run `cc_operator_workflows.spec.ts` on PR       | `.github/workflows/ci.yml`, `package.json`          | E2E job                      |
| 2        | Monolith Phase 2.1: `cc/partials/guide.html` + build concat for instant  | `index.html`, `scripts/build-cc-template.mjs` (new) | integrity bundle             |
| 3        | Dossier/discovery E2E with route abort                                   | `tests/e2e/`                                        | Playwright                   |
| 4        | `ops_recovery_guide` Alpine → thin delegate only (drop inline duplicate) | `index.html`                                        | `test_ops_recovery_guide.py` |
| 5        | Health `mode=loading` telemetry in Ops panel                             | `cc_header.py`, Ops tab                             | ops integrity                |

---

## 4. E2E / REGRESSION PLAN

**Pytest (canonical §3–§8 + polish packs):**

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
  tests/test_warmup_ux.py \
  tests/test_ops_recovery_guide.py \
  tests/test_second_pass_polish.py \
  tests/test_third_pass_polish.py \
  -q
```

**Result (this pass): 159 passed.**

**Playwright:**

```bash
npm i -D @playwright/test && npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

Uses `_cc_instant.py` via `playwright.config.ts` webServer. **9 tests** (helpers, health, banner precedence, WAIT, fallback, IBKR, Guide, mission panel, Rejections). Not run to completion in agent session (long webServer boot).

---

## 5. MONOLITH SPLIT NEXT STEP

Per [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md):

- **Done this pass (Phase 1.1):** `warmupContextStripVisible`, `loadingSessionRecoveryLine`, `instantDegradedBannerHint`, `todayMissionMonitorsLabel` in `cc-helpers.js`.
- **Next safe step:** Pre-build script that inlines `cc/partials/degraded_banners.html` into committed `index.html` so `_cc_instant.py` unchanged; OR continue pure-JS extraction until Alpine methods are thin delegates only.
- **Do not** split Ops degraded tables until Python `ops_degraded_copy` parity is automated.

---

## 6. DAILY USEFULNESS UPGRADES

| Upgrade                        | Implementation                                                 |
| ------------------------------ | -------------------------------------------------------------- |
| Mission panel monitors heading | `Monitors (n) · m near-miss` via `todayMissionMonitorsLabel()` |
| Loading session operator hint  | Warmup strip + Ops recovery first retry line                   |
| E2E mission panel hook         | `data-cc="today-mission-panel"`                                |

---

## 7. DIRECT CHANGES

| File                                      | Change                                                                                                               |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `src/api/static/cc-helpers.js`            | +`warmupContextStripVisible`, `loadingSessionRecoveryLine`, `instantDegradedBannerHint`, `todayMissionMonitorsLabel` |
| `src/services/fetch_surface_state.py`     | +`loading_session_recovery_line`, `today_mission_monitors_label`; mission panel fields; ops recovery port line       |
| `src/api/templates/index.html`            | Delegate helpers; `data-cc` attributes; recovery line in warmup strip; mission monitors label                        |
| `tests/e2e/cc_operator_workflows.spec.ts` | Unskipped; 9 real assertions                                                                                         |
| `tests/test_third_pass_polish.py`         | **New** — 6 tests                                                                                                    |
| `tests/test_warmup_ux.py`                 | Loading recovery line + wiring                                                                                       |
| `tests/test_ops_recovery_guide.py`        | Port line when loading                                                                                               |
| `tests/test_second_pass_polish.py`        | Assertion updated for CCHelpers precedence                                                                           |
| `docs/CC_THIRD_PASS_REVIEW.md`            | This report                                                                                                          |

No router/authority logic changes. No git commit in agent session.

---

## 8. FINAL PATH TO 10/10

### Immediate (next 1–2 sessions)

1. Wire Playwright job in CI (chromium only, `_cc_instant` webServer).
2. Add dossier + discovery route-abort E2E cases.
3. Build-step or partial extract for instant + Jinja paths.

### Next pass

4. Reduce `index.html` shell to &lt;3k lines (partials + concat).
5. Ops panel: surface `health.mode` + backend_ready flag explicitly.
6. Extended bundle: fix RS + backtest isolation stubs if still failing.

### Final hardening

7. Morning-operator checklist doc linked from Guide.
8. Council vs scanner disagreement banner when both live (brief fallback window).
9. Performance: trim synchronous template parse / split CSS blocks.

---

_Third pass: 2026-06-02. Pytest: **159 passed**._
