# CC · Clarity Console — Soak / Staging Verification Review

**Date:** 2026-06-04  
**Runbook:** [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)  
**Method:** Final soak pass — copy-only recovery, selector anchors, Python ↔ JS parity, pytest + Playwright hooks. **No authority weakening.**

---

## 1. SOAK READINESS VERDICT

| Verdict    | **CONDITIONAL GO** — staging soak may proceed with manual sign-off                                                                                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Blocker    | `index.html` still contains a legacy duplicated HTML/Alpine block (~lines 13.7k–20.2k) from an earlier partial-marker corruption; runtime uses the second `cc()` definition. Does not weaken gates but adds DOM noise. |
| Authority  | Unchanged — WAIT blocks deploy pills / Send to IBKR; loading/degraded paths remain monitor-only.                                                                                                                       |
| Automation | **26/26** pytest soak subset green; Playwright soak-anchor specs added (not executed in this pass — see §6).                                                                                                           |
| Build      | `node scripts/build-cc-template.mjs --check` green after `$`-safe partial injection fix.                                                                                                                               |

**Recommendation:** Run manual runbook §1–8 on staging; keep tab open 30+ min for §7; file sign-off table in runbook when green.

---

## 2. RUNBOOK GAP REVIEW

| #   | Scenario                    | Status   | Notes                                                                                                                                                                                       |
| --- | --------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Cold start / `mode=loading` | **pass** | Instant shell + contract/warmup strips; `loadingSessionRecoveryLine` + `operatorLoadingSafeLine` on warmup strip; instant banner suppresses duplicate WARMING.                              |
| 2   | loading → full              | **pass** | Health poll + hard refresh path documented; Guide has no authority chips.                                                                                                                   |
| 3   | IBKR LOGIN → READY          | **pass** | `ibkrLoginToReadyHint()` wired under deploy strip + mission safe/unlock; Playbook blocks `Send to IBKR` on WAIT via `playbookCanSendToIbkr`.                                                |
| 4   | Engine OFF                  | **pass** | ENGINE OFF pill on deploy strip; `engineOffRecoveryLine()` checkpoint below strip; mission system blockers include ENGINE OFF.                                                              |
| 5   | Stale market refresh        | **pass** | `[data-cc="market-strip-stale"]` + `staleRefreshRecoveryLine()` appended in downgrade lines.                                                                                                |
| 6   | Route-abort recovery        | **pass** | Dossier banner appends `routeAbortRecoveryHint('dossier')`; Discovery footer shows scanner route-abort copy.                                                                                |
| 7   | WAIT day soak (30+ min)     | **weak** | Mission panel + playbook fallback copy aligned; **manual** 30+ min counter reconciliation still required — no automated long-soak test.                                                     |
| 8   | Ops recovery runbook        | **pass** | `[data-cc="ops-recovery-runbook"]` renders Retry / Blocks capital / Safe in degraded; Alpine `opsRecoveryGuide()` now uses `operatorLoadingSafeLine()` in loading/degraded (Python parity). |
| 9   | Automated soak anchors      | **pass** | All `data-cc` selectors present; Python `soak_confirmation_signals()` ↔ `CCHelpers.soakConfirmationSelectors()` tested.                                                                    |

---

## 3. STAGING HARDENING CHANGES

| Change                                                                                               | Rationale                                                                 |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Fixed `deploy_surfaces` partial marker span (truncated portfolio pill + misplaced `@cc-partial-end`) | Restores injectable partial; removes corrupted `</html>+pf…` fragment     |
| `$`-safe partial injection in `build-cc-template.mjs`                                                | Prevents silent partial apply failure when Alpine expressions contain `$` |
| Deploy strip recovery checkpoints (`engineOffRecoveryLine`, `ibkrLoginToReadyHint`)                  | Runbook §3–4 visible checkpoints without new authority                    |
| Market stale strip includes `staleRefreshRecoveryLine`                                               | Runbook §5 copy anchor                                                    |
| Dossier / Discovery route-abort recovery copy                                                        | Runbook §6 client recovery                                                |
| `opsRecoveryGuide()` safe section delegates to `operatorLoadingSafeLine()`                           | Matches `ops_recovery_guide()` Python                                     |
| Extended `soak_confirmation_signals()` + `soakConfirmationSelectors()`                               | Automation parity for staging sign-off                                    |

---

## 4. AUTOMATION PARITY CHECK

| Surface                                 | Python | JS (`cc-helpers.js`) | index.html Alpine             | Status  |
| --------------------------------------- | ------ | -------------------- | ----------------------------- | ------- |
| `loadingSessionRecoveryLine`            | ✓      | ✓                    | ✓ delegates                   | aligned |
| `operatorLoadingSafeLine`               | ✓      | ✓                    | ✓ delegates                   | aligned |
| `engineOffRecoveryLine`                 | ✓      | ✓                    | ✓ new wrapper                 | aligned |
| `staleRefreshRecoveryLine`              | ✓      | ✓                    | ✓ via downgrade lines         | aligned |
| `ibkrLoginToReadyHint`                  | ✓      | ✓                    | ✓ deploy strip                | aligned |
| `routeAbortRecoveryHint`                | ✓      | ✓                    | ✓ dossier + discovery         | aligned |
| `ops_recovery_guide`                    | ✓      | —                    | ✓ inline (now uses safe line) | aligned |
| `soak_confirmation_signals` / selectors | ✓      | ✓                    | ✓ DOM anchors                 | aligned |

---

## 5. DIRECT CHANGES

| File                                                 | Change                                                                                             |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `scripts/build-cc-template.mjs`                      | Replacer function for `$`-safe partial injection                                                   |
| `src/api/templates/cc/partials/deploy_surfaces.html` | Engine/IBKR recovery checkpoints under deploy strip                                                |
| `src/api/templates/index.html`                       | Fixed deploy partial markers; recovery wrappers; ops guide parity; route-abort + stale copy wiring |
| `src/api/static/cc-helpers.js`                       | `dataContractStrip` in `soakConfirmationSelectors()`                                               |
| `src/services/fetch_surface_state.py`                | Extended `soak_confirmation_signals()` copy keys                                                   |
| `tests/test_soak_verification.py`                    | **new** — 8 soak-specific pytest cases                                                             |
| `tests/e2e/cc_operator_workflows.spec.ts`            | +3 soak anchor Playwright specs                                                                    |
| `docs/CC_SOAK_VERIFICATION_REVIEW.md`                | **this document**                                                                                  |

---

## 6. TEST / REGRESSION UPDATES

### Pytest (executed)

```bash
python3.11 -m pytest \
  tests/test_soak_verification.py \
  tests/test_ops_recovery_guide.py \
  tests/test_stabilization_pass.py \
  tests/test_warmup_ux.py \
  tests/test_final_verification.py::test_soak_confirmation_signals_stable \
  tests/test_final_verification.py::test_deploy_surfaces_partial_wired \
  -q
```

**Result:** **26 passed** in ~57s.

### Playwright (not run in this pass)

Requires staging server (`_cc_instant.py` or API on `:8000`):

```bash
npm install --no-save @playwright/test@1.49.1
npx playwright install chromium
npx playwright test tests/e2e/cc_operator_workflows.spec.ts
```

New specs: `soak anchors — data-cc selectors attached`, `recovery copy helpers in static bundle`, `soakConfirmationSelectors` export check.

---

## 7. FINAL SIGN-OFF PATH

| Step | Owner action                                                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------ |
| 1    | Deploy staging build; confirm `node scripts/build-cc-template.mjs --check` green in CI                             |
| 2    | Manual runbook §1–6 on staging (cold start, IBKR, engine OFF, stale, route abort)                                  |
| 3    | §7 WAIT soak — leave tab ≥30 min; confirm no green TRADE deploy pills; counters reconcile or SCORE FAMILIES banner |
| 4    | Ops → Health — verify runbook bullets match `ops_recovery_guide()` snapshot                                        |
| 5    | Run Playwright `cc-e2e` on CI or locally against staging                                                           |
| 6    | Complete sign-off table in [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)                              |
| 7    | (Follow-up) Dedupe legacy HTML/Alpine block in `index.html` — structural cleanup, not authority                    |

**Sign-off criteria for full GO:** Manual §1–8 green + Playwright green + no new green TRADE pills during loading/WAIT soak.

---

_Staging verification pass 2026-06-04. Pair with [CC_STABILIZATION_REVIEW.md](./CC_STABILIZATION_REVIEW.md)._
