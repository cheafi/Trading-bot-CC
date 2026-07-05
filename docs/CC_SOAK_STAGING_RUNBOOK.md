# CC · Clarity Console — Soak / Staging Runbook

**Purpose:** Manual staging checklist after stabilization pass. Copy-only recovery — no fake authority or auto-deploy.

**Prereqs:** Staging with `_cc_instant.py` or full API on `:8000` / `:8001`; `node scripts/build-cc-template.mjs --check` green; Playwright `cc-e2e` green on CI.

---

## 1. Cold start / long loading (`mode=loading`)

| Step | Action                                         | Pass criteria                                                    |
| ---- | ---------------------------------------------- | ---------------------------------------------------------------- |
| 1.1  | Open `/` fresh (no cache)                      | Instant shell loads; contract strip or warmup strip visible      |
| 1.2  | Poll `/health` until `mode=full`               | ≤ ~2 min typical; recovery line mentions port 8000→8001 if stuck |
| 1.3  | Dismiss instant degraded banner (if shown)     | Warmup strip does **not** duplicate WARMING copy                 |
| 1.4  | Read `operatorLoadingSafeLine` on warmup strip | Mentions safe actions: monitors, Guide, dossier core-only        |

**Fail:** Green TRADE deploy pills while `mode=loading` or FETCH FAILED.

---

## 2. Mode transitions (loading → full)

| Step | Action                                 | Pass criteria                                                     |
| ---- | -------------------------------------- | ----------------------------------------------------------------- |
| 2.1  | Note strip text at `loading`           | WARMING + backend import                                          |
| 2.2  | After `mode=full`, hard refresh once   | Ranked / council payloads load or honest fallback                 |
| 2.3  | Switch Overview → Playbook → Discovery | No authority chip on Guide; decision surfaces show contract strip |

---

## 3. IBKR LOGIN → READY

| Step | Action                            | Pass criteria                                               |
| ---- | --------------------------------- | ----------------------------------------------------------- |
| 3.1  | Open IBKR tab                     | LOGIN, OFFLINE, or READY visible                            |
| 3.2  | If LOGIN: connect per ops runbook | Session moves toward READY (not deploy by itself)           |
| 3.3  | Mission panel / safe hint         | `ibkrLoginToReadyHint` copy: READY + bracket before handoff |
| 3.4  | Playbook on WAIT                  | No `Send to IBKR` on `[data-cc="playbook-surface"]`         |

---

## 4. Engine OFF

| Step | Action                            | Pass criteria                                    |
| ---- | --------------------------------- | ------------------------------------------------ |
| 4.1  | Stop engine (Ops) or simulate OFF | ENGINE OFF pill on dashboard strip               |
| 4.2  | Mission blockers                  | ENGINE OFF in system blockers                    |
| 4.3  | Safe hint                         | `engineOffRecoveryLine` — precomputed board only |

---

## 5. Stale market refresh

| Step | Action                                      | Pass criteria                                      |
| ---- | ------------------------------------------- | -------------------------------------------------- |
| 5.1  | If `[data-cc="market-strip-stale"]` visible | Copy: snapshot stale / not decision-grade          |
| 5.2  | Trigger market refresh (if available)       | Strip clears or downgrade persists honestly        |
| 5.3  |                                             | `staleRefreshRecoveryLine` — refresh before sizing |

---

## 6. Route-abort recovery (client)

| Step | Action                              | Pass criteria                                         |
| ---- | ----------------------------------- | ----------------------------------------------------- |
| 6.1  | DevTools: block `/api/dossier/*`    | Dossier surface shows CONFIRM ONLY / research shell   |
| 6.2  | Unblock; retry Load core only       | No handoff CTA from shell                             |
| 6.3  | Block `/api/v7/playbook/scanners**` | Discovery fallback / WAIT funnel; no deploy authority |

---

## 7. WAIT day soak (30+ min)

| Step | Action                           | Pass criteria                                                         |
| ---- | -------------------------------- | --------------------------------------------------------------------- |
| 7.1  | Dashboard mission panel          | Today focus; monitors hint; safe/unlock line                          |
| 7.2  | Playbook                         | Fallback rank / WATCH ONLY; near-miss ≠ deploy                        |
| 7.3  | Leave tab open; periodic refresh | No new green TRADE pills; counters reconcile or SCORE FAMILIES banner |

---

## 8. Ops recovery runbook

| Step | Action             | Pass criteria                                                                     |
| ---- | ------------------ | --------------------------------------------------------------------------------- |
| 8.1  | Ops → Health       | `[data-cc="ops-recovery-runbook"]` with Retry / Blocks capital / Safe in degraded |
| 8.2  | Cross-check Python | `ops_recovery_guide()` matches visible bullets                                    |

---

## 9. Soak confirmation signals (automated anchors)

Cross-check visible UI against Python `soak_confirmation_signals()` and `CCHelpers.soakConfirmationSelectors()`.

| Signal           | Selector / copy                       | Pass                                                                         |
| ---------------- | ------------------------------------- | ---------------------------------------------------------------------------- |
| Instant degraded | `[data-cc="instant-degraded-banner"]` | Banner dismissible; warmup strip hidden when shown                           |
| Warmup           | `[data-cc="warmup-context-strip"]`    | `loadingSessionRecoveryLine` + `operatorLoadingSafeLine` when `mode=loading` |
| Deploy strip     | `[data-cc="deploy-status-strip"]`     | IBKR + ENGINE pills; no green TRADE on WAIT                                  |
| Mission          | `[data-cc="today-mission-panel"]`     | Safe/unlock hint; blockers vs monitors columns                               |
| Playbook         | `[data-cc="playbook-surface"]`        | No Send to IBKR on WAIT                                                      |
| Market stale     | `[data-cc="market-strip-stale"]`      | `staleRefreshRecoveryLine` when visible                                      |
| Ops runbook      | `[data-cc="ops-recovery-runbook"]`    | Retry / Safe in degraded                                                     |

---

## Sign-off

| Area           | Owner | Date | Notes |
| -------------- | ----- | ---- | ----- |
| Loading / full |       |      |       |
| IBKR READY     |       |      |       |
| Engine / stale |       |      |       |
| Route abort    |       |      |       |
| WAIT soak      |       |      |       |

---

_Stabilization pass 2026-06-02. Pair with [CC_STABILIZATION_REVIEW.md](./CC_STABILIZATION_REVIEW.md)._
