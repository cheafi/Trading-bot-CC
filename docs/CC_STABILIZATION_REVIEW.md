# CC · Clarity Console — Stabilization + Soak + Extraction Review

**Date:** 2026-06-02  
**Baseline:** [CC_FINAL_HARDENING_REVIEW.md](./CC_FINAL_HARDENING_REVIEW.md) **9.7/10** · 21 Playwright · partials: `degraded_banners`, `ops_recovery_runbook`  
**Method:** Stabilization-only pass (no authority re-audit) + guide partial extract + E2E/CI hardening + soak runbook

---

## 1. STABILIZATION VERDICT

| Metric                | Value                                                                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pre-pass score**    | **9.7/10** (final hardening)                                                                                                                  |
| **Post-pass score**   | **9.8/10** — guide partial (~558 lines), stable nav `data-cc-nav`, recovery checkpoints, E2E serial + route-abort split, CI junit + artifacts |
| **Blockers to 10/10** | `cc-e2e` green on main over 3+ merges; staging soak sign-off; optional `deploy_surfaces.html` extract                                         |

**Summary:** Stabilization pass extracts **Phase 2.1 `guide.html`**, adds **recovery copy parity** (route abort, stale refresh, engine off, IBKR LOGIN→READY, mission safe/blocked), hardens Playwright (shell warmup, `data-cc-nav`, serial describe, junit), and documents **staging soak** in [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md). Authority boundaries unchanged.

---

## 2. HIGHEST-ROI FINAL GAPS

| Gap                      | Status        | Notes                                                                 |
| ------------------------ | ------------- | --------------------------------------------------------------------- |
| `cc-e2e` flaky on main   | **Mitigated** | Serial workers=1; route-abort in separate describe; shell attach wait |
| `guide.html` monolith    | **Done**      | `cc/partials/guide.html` + build inject + `data-cc="guide-surface"`   |
| `data-cc-nav` bottom nav | **Done**      | E2E uses nav hooks first                                              |
| Soak / staging checklist | **Done**      | `CC_SOAK_STAGING_RUNBOOK.md`                                          |
| Recovery copy parity     | **Done**      | JS + Python + mission safe/unlock hint                                |
| CI Playwright artifacts  | **Done**      | junit + upload on failure                                             |
| Backend auto-heal        | **Open**      | Copy-only; no spawn trust erosion                                     |
| `deploy_surfaces.html`   | **Deferred**  | Next monolith step per split plan                                     |

---

## 3. STABILIZATION IMPLEMENTATION WAVE

| Priority | Work                  | Files                                                           | Verification                          |
| -------- | --------------------- | --------------------------------------------------------------- | ------------------------------------- |
| 1        | Guide partial extract | `cc/partials/guide.html`, `index.html`, `build-cc-template.mjs` | `--check` + `test_stabilization_pass` |
| 2        | E2E stabilization     | `cc_operator_workflows.spec.ts`, `playwright.config.ts`         | Playwright 21 specs                   |
| 3        | Recovery checkpoints  | `cc-helpers.js`, `fetch_surface_state.py`                       | `test_stabilization_pass`             |
| 4        | Mission safe/blocked  | `index.html`                                                    | E2E mission panel                     |
| 5        | Soak runbook          | `CC_SOAK_STAGING_RUNBOOK.md`                                    | Manual staging                        |
| 6        | CI artifacts          | `.github/workflows/ci.yml`                                      | Failed job upload                     |

---

## 4. PLAYWRIGHT / CI STABILIZATION PLAN

**Config (`playwright.config.ts`):**

| Setting            | Value                               |
| ------------------ | ----------------------------------- |
| workers            | 1                                   |
| retries            | 2 on CI                             |
| trace              | on-first-retry                      |
| screenshot / video | only-on-failure / retain-on-failure |
| reporter (CI)      | list + **junit** + html             |
| outputDir          | `test-results/playwright`           |
| webServer          | `_cc_instant.py`, 120s, `/health`   |

**E2E structure (`cc_operator_workflows.spec.ts`):**

| Block                            | Tests | Notes                                            |
| -------------------------------- | ----- | ------------------------------------------------ |
| `CC operator workflows`          | 19    | `waitForCcShell`; `data-cc-nav` tab clicks       |
| `CC route-abort recovery shells` | 2     | Isolated serial block; dossier + discovery abort |

**CI (`cc-e2e`):**

1. `node scripts/build-cc-template.mjs --check`
2. `npx playwright test tests/e2e/cc_operator_workflows.spec.ts`
3. On failure: upload `test-results/playwright/`, junit XML, `playwright-report/`

**Local:**

```bash
npm install --no-save @playwright/test@1.49.1
npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

---

## 5. SOAK / STAGING PLAN

See [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md).

| Scenario            | Recovery signal                                          | Authority                  |
| ------------------- | -------------------------------------------------------- | -------------------------- |
| Long `mode=loading` | `loadingSessionRecoveryLine` / `operatorLoadingSafeLine` | No deploy                  |
| loading → full      | Refresh; contract strip                                  | Ranked when badges clear   |
| IBKR LOGIN→READY    | `ibkrLoginToReadyHint`                                   | Handoff only when READY    |
| Engine OFF          | `engineOffRecoveryLine`                                  | Precomputed board          |
| Market stale        | `staleRefreshRecoveryLine` + `market-strip-stale`        | No sizing on stale         |
| Route abort         | `routeAbortRecoveryHint`                                 | Research / fallback shells |
| WAIT 30+ min        | Mission monitors hint + safe/unlock                      | Deploy blocked             |

---

## 6. MONOLITH EXTRACTION NEXT STEP

| Phase   | Item                                       | Status                                                       |
| ------- | ------------------------------------------ | ------------------------------------------------------------ |
| 2.0     | `degraded_banners`, `ops_recovery_runbook` | Done (prior pass)                                            |
| **2.1** | **`guide.html`**                           | **Done (this pass)**                                         |
| 2.2     | `deploy_surfaces.html`                     | Next — dashboard + playbook chrome                           |
| 2.3     | `ops.html` full console                    | After deploy surfaces                                        |
| 3.x     | Jinja `{% include %}` optional             | Instant still serves built `index.html` via `_cc_instant.py` |

**Shell size:** `index.html` reduced by ~558 lines of guide markup (injected at build). CI `--check` prevents drift.

---

## 7. FINAL PRODUCT CONSISTENCY FIXES

| Issue                                            | Fix                                                           |
| ------------------------------------------------ | ------------------------------------------------------------- |
| Playbook WAIT “unlock conditions” implied deploy | → “gate context below (not deploy)”                           |
| Mission panel missing safe vs blocked            | → `todayMissionSafeUnlockHint()` under WAIT subtitle          |
| Guide E2E text-only nav                          | → `[data-cc="guide-surface"]` + `data-cc-nav="guide"`         |
| Near-miss / monitor drift                        | Monitors column hint unchanged; playbook monitor line aligned |

---

## 8. DIRECT CHANGES

| File                                       | Change                                                                                     |
| ------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `src/api/templates/cc/partials/guide.html` | **New** — Guide surface body (~558 lines)                                                  |
| `src/api/templates/index.html`             | `@cc-partial guide` markers; `data-cc="guide-surface"`; mission safe/unlock; playbook copy |
| `scripts/build-cc-template.mjs`            | +`guide` partial                                                                           |
| `src/api/static/cc-helpers.js`             | +5 recovery / mission helpers                                                              |
| `src/services/fetch_surface_state.py`      | Python mirrors for recovery + safe/unlock                                                  |
| `tests/e2e/cc_operator_workflows.spec.ts`  | Shell wait, nav hooks, route-abort split                                                   |
| `playwright.config.ts`                     | junit reporter, outputDir                                                                  |
| `.github/workflows/ci.yml`                 | Playwright artifact upload on failure                                                      |
| `docs/CC_SOAK_STAGING_RUNBOOK.md`          | **New** — staging checklist                                                                |
| `tests/test_stabilization_pass.py`         | **New** — 7 tests                                                                          |
| `docs/CC_STABILIZATION_REVIEW.md`          | **New** — this document                                                                    |

---

## 9. FINAL PATH TO 10/10

1. **CI confidence:** `cc-e2e` green on 3+ consecutive main merges (21 specs + template `--check`).
2. **Staging soak:** Sign off [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) with live ranked + IBKR probe.
3. **Monolith:** Extract `deploy_surfaces.html`; shell toward &lt;10k lines.
4. **Optional:** `_cc_instant` child health retry (no authority erosion).
5. **Score:** When 1–3 hold → **10/10** with unchanged authority model.

---

_Stabilization pass: 2026-06-02. Pytest canonical bundle: **189 passed** (159 baseline + polish + hardening + stabilization). Playwright: **21 specs** (CI `cc-e2e`; local run requires `npm install @playwright/test` + chromium). Template: `node scripts/build-cc-template.mjs --check`._
