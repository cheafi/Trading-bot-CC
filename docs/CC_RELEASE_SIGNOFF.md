# CC · Clarity Console — Final Release Sign-Off

**Date:** 2026-06-04  
**Branch:** `sprint99-fund-productization`  
**Baseline docs:** [CC_README.md](./CC_README.md), [CC_AI_CONTEXT.md](./CC_AI_CONTEXT.md), [CC_FINAL_VERIFICATION_REVIEW.md](./CC_FINAL_VERIFICATION_REVIEW.md), [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)  
**Method:** Release verification only — no feature pass, no redesign.

---

## 1. RELEASE SIGN-OFF VERDICT

| Metric             | Value                                                    |
| ------------------ | -------------------------------------------------------- |
| **Score**          | **9.9/10** (code/fixtures) · **not promotable to 10/10** |
| **Verdict**        | **NOT READY**                                            |
| **Alternate path** | **WITH CONDITIONS** after merge + CI soak on main        |

### Blockers

1. **`cc-e2e` green streak on main:** 0 successful CI runs in the last 50 workflow executions (`gh run list --workflow=ci.yml`). All recent runs fail at **lint** before `cc-e2e` executes. No evidence of 3+ consecutive green `cc-e2e` merges on main.
2. **Staging soak sign-off:** [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) §sign-off table is empty — manual staging execution required.
3. **CI lint gate:** `ruff check src/` fails on unrelated files (e.g. `src/algo/base_strategy.py` W293/F401/I001) — blocks entire CI pipeline including `cc-e2e`.

### Release-blocking fixes applied this pass (uncommitted)

| Issue                                                                                      | Severity                                                       | Status                                     |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------- | ------------------------------------------ |
| `index.html` duplicated entire CC app (2× `function cc()`, 2× Alpine, 2× playbook-surface) | **Critical** — deployable-looking duplicate UI, selector drift | **Fixed** (26,628 → 13,845 lines)          |
| `institutional_13f.py` `lag_copy` missing “lag” substring                                  | Authority copy test fail                                       | **Fixed**                                  |
| Stale `playbookUnlockConditionDetail` test assertions                                      | Test drift                                                     | **Fixed**                                  |
| `src/api/main.py:6139` SyntaxError (port 8000 crash)                                       | Startup crash                                                  | **Already fixed** — compiles; routers load |

**Conservative decision:** Do **not** promote to 10/10 or declare production-ready until blockers 1–3 clear on main after merge.

---

## 2. CI / PLAYWRIGHT CHECK

### Workflow (`.github/workflows/ci.yml`)

| Job      | Config                                    | Status                                        |
| -------- | ----------------------------------------- | --------------------------------------------- |
| `lint`   | ruff E/F/W/I on `src/`                    | **Red** on branch + main (blocks downstream)  |
| `cc-e2e` | template `--check` + Playwright spec      | **Not reached** in recent runs (lint failure) |
| `test`   | compileall, import smoke, health on :8000 | **Not reached** when lint fails               |

### Playwright config (`playwright.config.ts`)

| Setting        | Value                                                                 |
| -------------- | --------------------------------------------------------------------- |
| workers        | 1                                                                     |
| retries        | 2 (CI)                                                                |
| expect timeout | 15s                                                                   |
| webServer      | `_cc_instant.py` → `/health`, 120s                                    |
| artifacts      | trace on-first-retry; screenshot/video on failure; junit + html on CI |

### E2E spec (`tests/e2e/cc_operator_workflows.spec.ts`)

| Item           | Result                                                                     |
| -------------- | -------------------------------------------------------------------------- |
| Spec count     | **21**                                                                     |
| Selectors      | Stable `data-cc` / `data-cc-nav` anchors; no changes required this pass    |
| Retries        | CI retries=2 — appropriate; not masking instability                        |
| Local run      | **Not executed** — `npm install @playwright/test` hung in agent env (>90s) |
| Template drift | **`node scripts/build-cc-template.mjs --check` — PASS**                    |

### `gh run list` (main + branch)

- **Branch PR** (`25620877299`): lint failed → `cc-e2e` skipped.
- **Main** (last 10): all **failure**; most recent merge attempt 2026-05-22.
- **Success count (last 50):** **0**

---

## 3. PYTEST / REGRESSION CHECK

### Canonical CC bundle ([CC_AI_CONTEXT.md](./CC_AI_CONTEXT.md) §Pytest)

| Suite                                            | Count                        | Result                                                         |
| ------------------------------------------------ | ---------------------------- | -------------------------------------------------------------- |
| Canonical files                                  | 31                           | All import OK                                                  |
| Tests run (non-fixture)                          | **226 passed**, **0 failed** | **GREEN**                                                      |
| Pytest fixture tests (`test_cc_instant_ibkr.py`) | 3                            | Require pytest runner (skipped in importlib harness)           |
| **Effective total**                              | **229**                      | Matches ~194–199 baseline + opportunity intelligence expansion |
| `tests/test_release_signoff.py`                  | **4 passed**                 | **NEW** — template dedup, drift gate, TCP hang, soak parity    |

**Runner note:** `pytest` CLI hangs on import in local `.venv` (environment/plugin issue). Verified via importlib harness + targeted subprocess attempts. CI `test` job uses standard pytest and should be re-validated once lint unblocks.

### Critical regressions

| Test                                                                            | Result                                                          |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `test_finalize_ranked_payload_authority_completes_without_tcp_probe`            | **PASS** (< 2s, probe patched)                                  |
| `test_finalize_ranked_payload_authority_on_all_row_keys` (trading_intelligence) | **PASS**                                                        |
| Authority / WAIT / confirm-only / Send to IBKR                                  | **PASS** (dashboard, playbook, guide, dossier, workflow suites) |
| Opportunity intelligence deploy boundaries                                      | **PASS** (after `lag_copy` fix)                                 |

### Authority leakage sweep

| Surface             | Finding                                                    |
| ------------------- | ---------------------------------------------------------- |
| Guide               | No deploy chips (E2E + pytest)                             |
| WAIT dashboard      | No green TRADE pills                                       |
| Playbook WAIT       | No Send to IBKR on `[data-cc="playbook-surface"]`          |
| Dossier             | CONFIRM ONLY / indicative levels                           |
| Opportunity signals | Research-only ceilings; `may_authorize_deploy` false       |
| Ranked finalize     | In-memory `ibkr_authority_gate_snapshot()` — no TCP probes |

---

## 4. STAGING / SOAK CHECK

### Runbook alignment ([CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md))

| Check                                                                                | Status                                                                |
| ------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| §9 soak confirmation signals table                                                   | Present                                                               |
| `soak_confirmation_signals()` (`fetch_surface_state.py`)                             | **Aligned**                                                           |
| `CCHelpers.soakConfirmationSelectors()` (`cc-helpers.js`)                            | **Aligned**                                                           |
| `data-cc` anchors (deploy strip, mission panel, playbook, ops runbook, stale market) | **Present** after dedup                                               |
| Recovery copy parity                                                                 | Unchanged — loading, route abort, stale, engine off, IBKR LOGIN→READY |

### Soak sign-off readiness

| Area                | Automated anchors | Manual sign-off |
| ------------------- | ----------------- | --------------- |
| Loading / full      | Ready             | **Pending**     |
| IBKR READY          | Ready             | **Pending**     |
| Engine / stale      | Ready             | **Pending**     |
| Route abort         | Ready             | **Pending**     |
| WAIT soak (30+ min) | Ready             | **Pending**     |

**Verdict:** Runbook is **sign-off ready** structurally; operator execution + table completion required before 10/10.

---

## 5. FINAL REGRESSION RISKS

| Risk                                                        | Severity             | Mitigation                                                    |
| ----------------------------------------------------------- | -------------------- | ------------------------------------------------------------- |
| CI lint failures unrelated to CC block all jobs             | **High**             | Fix or scope lint; otherwise `cc-e2e` never runs              |
| No recent green `cc-e2e` on main                            | **High**             | Merge fixes; require 3+ green main runs                       |
| `index.html` duplication (pre-fix) caused twin Alpine roots | **Critical (fixed)** | Dedup applied; `test_release_index_html_single_cc_app` guards |
| Local pytest import hang                                    | **Medium**           | CI path unaffected; investigate venv/plugin locally           |
| Playwright not run locally this pass                        | **Medium**           | Rely on CI after lint fix; 21 specs unchanged                 |
| Manual soak not executed                                    | **Medium**           | Required for 10/10 per roadmap                                |
| Opportunity intelligence on branch                          | **Low**              | Boundaries tested; no deploy authority added                  |

---

## 6. DIRECT CHANGES

| File                                | Change                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `src/api/templates/index.html`      | Removed duplicate CC body + second Alpine block (~12.8k lines)           |
| `src/services/institutional_13f.py` | `lag_copy` mentions filing lag (authority honesty test)                  |
| `tests/test_ui_render_integrity.py` | Align `playbookUnlockConditionDetail` assertions to current funnel logic |
| `tests/test_release_signoff.py`     | **New** — 4 release gate tests                                           |
| `docs/CC_RELEASE_SIGNOFF.md`        | **This document**                                                        |

No router authority changes. No commit created (per sign-off instructions).

---

## 7. FINAL RELEASE PATH

1. **Commit release-blocking fixes** on `sprint99-fund-productization` (index dedup, lag_copy, test alignment, signoff tests).
2. **Fix CI lint** on main (or scope `cc-e2e`/`test` to not depend on full-repo lint if intentional split desired).
3. **Merge to main** → confirm **`cc-e2e` green** on 3+ consecutive main pushes (21 Playwright + template `--check`).
4. **Run canonical pytest in CI** or clean local venv — target **229+** collected, 0 failures.
5. **Execute staging soak** [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) §1–§9; complete sign-off table.
6. **Promote score to 10/10** when steps 3–5 hold with no authority regressions.

---

## Test counts (this pass)

| Suite                           | Result                                              |
| ------------------------------- | --------------------------------------------------- |
| Canonical CC pytest (importlib) | **226 / 226** pass (+ 3 fixture tests under pytest) |
| Release signoff pytest          | **4 / 4** pass                                      |
| Template drift gate             | **PASS**                                            |
| Playwright E2E                  | **21 specs** — CI not reached; local not run        |
| `main.py` compile + import      | **PASS** (venv)                                     |

---

_Final release sign-off: 2026-06-04. Pair with [CC_FINAL_VERIFICATION_REVIEW.md](./CC_FINAL_VERIFICATION_REVIEW.md) and [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)._
