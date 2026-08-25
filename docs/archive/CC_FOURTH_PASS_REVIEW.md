> **Superseded by [`CC_X_ENGINEERING_BACKLOG.md`](../CC_X_ENGINEERING_BACKLOG.md) and [`CC_X_ARCHITECTURE.md`](../CC_X_ARCHITECTURE.md) — retained for history only.**

# CC · Clarity Console — Fourth-Pass Review + Implementation

**Date:** 2026-06-02  
**Baseline:** [CC_THIRD_PASS_REVIEW.md](./CC_THIRD_PASS_REVIEW.md) **9.2/10** · [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md) Phase 1 extended, Phase 2 partial started  
**Method:** Targeted gap review (no re-audit of solved authority/IBKR/data-contract/card-grade work) + implementation + pytest + Playwright expansion + CI job

---

## 1. FOURTH-PASS VERDICT

| Metric                | Value                                                                                                           |
| --------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Pre-pass score**    | **9.2/10** (third-pass reliability + E2E scaffold)                                                              |
| **Post-pass score**   | **9.4/10** — E2E matrix + CI job + operator safe-lines + monolith partial/build; cold-start duration still open |
| **Blockers to 10/10** | E2E green in CI on first runs; `index.html` shell still &gt;13k lines; full backend `mode=full` soak            |

**Summary:** Fourth pass wires **Playwright into CI**, expands **14 operator workflow specs** (WAIT, fallback, warmup/recovery, IBKR, Guide, mission WAIT, dossier core-only, discovery, portfolio stops, playbook handoff), adds **operator safe-action copy** (loading + WAIT), starts **monolith Phase 2.0** (`degraded_banners` partial + `build-cc-template.mjs`). Authority boundaries unchanged.

---

## 2. HIGHEST-ROI REMAINING GAPS

### E2E / workflow safety

| Gap                                           | Status        | Notes                                            |
| --------------------------------------------- | ------------- | ------------------------------------------------ |
| Playwright in CI                              | **Done**      | `cc-e2e` job in `.github/workflows/ci.yml`       |
| Dossier / discovery / portfolio / handoff E2E | **Done**      | New specs in `cc_operator_workflows.spec.ts`     |
| Route-abort fail matrix (visual)              | **Open**      | Pytest integrity covers copy; no abort-based E2E |
| Flaky webServer boot                          | **Mitigated** | 90s timeout, `.venv`/`venv` python resolution    |

### Reliability / cold start

| Gap                              | Status     | Notes                                             |
| -------------------------------- | ---------- | ------------------------------------------------- |
| Loading vs WAIT operator actions | **Done**   | `operatorLoadingSafeLine` in strip + Ops recovery |
| Port 8000→8001 copy              | **Stable** | `loadingSessionRecoveryLine` unchanged            |
| Backend auto-heal                | **Open**   | Copy-only guidance                                |

### Maintainability

| Gap                                 | Status       | Notes                                 |
| ----------------------------------- | ------------ | ------------------------------------- |
| `cc/partials/degraded_banners.html` | **Done**     | Instant banner + warmup strip         |
| `scripts/build-cc-template.mjs`     | **Done**     | Marker inject; `--check` for CI drift |
| Jinja `{% include %}`               | **Deferred** | Instant serves committed `index.html` |

### Daily usefulness

| Gap                   | Status        | Notes                                        |
| --------------------- | ------------- | -------------------------------------------- |
| Mission WAIT subtitle | **Done**      | `todayMissionWaitSubtitle` under panel title |
| Monitor queue label   | **Stable**    | Third-pass `todayMissionMonitorsLabel`       |
| Attention routing     | **Unchanged** | PM strip + authority chips                   |

### Polish

| Gap                  | Status       | Notes                                                |
| -------------------- | ------------ | ---------------------------------------------------- |
| Degraded copy dedupe | **Improved** | Safe-line only when strip visible; banner still wins |
| CTA hierarchy        | **Stable**   | Playbook handoff gated by `playbookCanSendToIbkr`    |

---

## 3. NEXT IMPLEMENTATION WAVE

| Priority | Work                                                | Files                      | Tests               |
| -------- | --------------------------------------------------- | -------------------------- | ------------------- |
| 1        | CI: confirm `cc-e2e` green on main PRs              | `.github/workflows/ci.yml` | 14 Playwright specs |
| 2        | `build-cc-template.mjs --check` in CI before pytest | `ci.yml`                   | drift gate          |
| 3        | Route-abort dossier/discovery E2E                   | `tests/e2e/`               | Playwright          |
| 4        | Extract `guide.html` partial (Phase 2.1)            | `cc/partials/`             | surface integrity   |
| 5        | Ops panel: explicit `health.mode` + `backend_ready` | `cc_header.py`, Ops tab    | ops integrity       |

---

## 4. PLAYWRIGHT / E2E HARDENING PLAN

**Local:**

```bash
npm install --no-save @playwright/test@1.49.1
npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

**Config:** `playwright.config.ts` — `_cc_instant.py` webServer, 90s boot, `CC_E2E_SKIP_SERVER` for external base URL.

**Coverage (14 tests):**

| Test              | Asserts                                                       |
| ----------------- | ------------------------------------------------------------- |
| cc-helpers load   | `operatorLoadingSafeLine`, `todayMissionWaitSubtitle` exports |
| health            | `mode` ∈ loading\|full                                        |
| banner precedence | Instant banner hides warmup strip                             |
| warmup recovery   | Cold start / Safe now / WARMING when strip visible            |
| WAIT dashboard    | No green `TRADE` pills                                        |
| Playbook fallback | Fallback rank / WATCH ONLY                                    |
| Playbook handoff  | No `Send to IBKR` on WAIT                                     |
| IBKR              | LOGIN \| OFFLINE \| READY                                     |
| Guide             | No deploy chips; GUIDE MODE                                   |
| Mission panel     | Today focus / Deploy blocked / Monitors                       |
| Rejections        | Degraded or loading shell                                     |
| Dossier           | Load core only / CONFIRM ONLY                                 |
| Discovery         | Fallback / WAIT funnel / Tier 1                               |
| Portfolio         | Set stop / Risk blocker / heat                                |

---

## 5. RELIABILITY / RECOVERY UX PLAN

| Surface        | Operator signal            | Action                                                    |
| -------------- | -------------------------- | --------------------------------------------------------- |
| Instant banner | INSTANT DEGRADED           | Wait for `/health mode=full`; dismiss does not lift gates |
| Warmup strip   | WARMING + port line        | Retry after ~2 min; restart once                          |
| Safe line      | `operatorLoadingSafeLine`  | Lists safe tabs (Guide, monitors, core dossier)           |
| Mission panel  | `todayMissionWaitSubtitle` | WAIT → monitors only, no deploy                           |
| Ops runbook    | `ops_recovery_guide`       | Uses safe-line when loading                               |

**Python parity:** `operator_loading_safe_line`, `today_mission_wait_subtitle` in `fetch_surface_state.py`.

---

## 6. MONOLITH SPLIT NEXT STEP

Per [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md):

- **Done (Phase 2.0):** `cc/partials/degraded_banners.html` + markers in `index.html` + `scripts/build-cc-template.mjs`.
- **Next:** `cc/partials/guide.html` or `ops.html`; run build before commit; add `--check` to CI.
- **Do not** split Ops degraded tables until Python `ops_degraded_copy` parity is automated.

---

## 7. DAILY USEFULNESS UPGRADES

| Upgrade                 | Implementation                                   |
| ----------------------- | ------------------------------------------------ |
| WAIT mission subtitle   | `todayMissionWaitSubtitle()` under mission title |
| Loading safe actions    | `operatorLoadingSafeLine()` in warmup strip      |
| Portfolio blockers hook | `data-cc="portfolio-stop-blockers"` for E2E      |
| Monitor label           | Unchanged third-pass helper                      |

---

## 8. DIRECT CHANGES

| File                                                  | Change                                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------------------ |
| `src/api/static/cc-helpers.js`                        | +`operatorLoadingSafeLine`, `todayMissionWaitSubtitle`                   |
| `src/services/fetch_surface_state.py`                 | Mirror helpers; Ops recovery uses safe-line when loading                 |
| `src/api/templates/index.html`                        | Partial markers; mission subtitle; portfolio `data-cc`; Alpine delegates |
| `src/api/templates/cc/partials/degraded_banners.html` | **New** — instant banner + warmup strip                                  |
| `scripts/build-cc-template.mjs`                       | **New** — partial inject / `--check`                                     |
| `tests/e2e/cc_operator_workflows.spec.ts`             | 9 → **14** tests                                                         |
| `playwright.config.ts`                                | Python path resolution; 90s webServer; CI retries                        |
| `.github/workflows/ci.yml`                            | **`cc-e2e` job**                                                         |
| `tests/test_fourth_pass_polish.py`                    | **New** — 6 tests                                                        |
| `docs/CC_FOURTH_PASS_REVIEW.md`                       | This report                                                              |

No router/authority logic changes. No git commit in agent session.

---

## 9. FINAL PATH TO 10/10

### Immediate (next 1–2 sessions)

1. Green `cc-e2e` on CI; fix any tab-label flakes.
2. `node scripts/build-cc-template.mjs --check` in CI.
3. Route-abort dossier + discovery E2E.

### Next pass

4. Extract Guide partial; shell &lt;3k lines with concat.
5. Ops panel: `health.mode` + `backend_ready` telemetry.
6. Morning-operator checklist linked from Guide.

### Final hardening

7. Council vs scanner disagreement banner (brief fallback window).
8. Trim synchronous template parse / split CSS blocks.
9. Extended pytest bundle: RS + backtest isolation stubs if still failing.

---

_Fourth pass: 2026-06-02. Pytest canonical bundle: **168 passed** (159 baseline + 9 fourth-pass). Playwright: **14 specs** — run locally/CI via commands above._
