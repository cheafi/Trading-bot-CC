# Validation Report

Evidence log for the autonomous engineering sprints on `Trading-bot-CC`.
Companion to [ENGINEERING_AUDIT.md](ENGINEERING_AUDIT.md).

Status vocabulary: **DONE · IN_PROGRESS · BLOCKED · NOT_STARTED**

---

## Regression methodology

A clean `git worktree` is checked out at the pre-change commit and the same
pytest invocation is run against both trees. Failure *lists* are diffed with
`comm`, not failure *counts* — counts alone hide the case where one test is
fixed while another breaks.

```bash
./.venv/bin/python -m pytest tests -q -p no:randomly --ignore=tests/e2e
```

| Run | Failed | Passed | New regressions |
|------|--------|--------|------------------|
| Baseline @ `64bcd53d` | 308 | 1899 | — |
| After Sprint 1 | 310 | 1945 | **0** |
| After Sprint 2 | 310 | 1988 | **0** |

The 308 pre-existing failures are untriaged and **not** caused by this work
(backlog B1). The +2 delta is untracked iCloud duplicate test files
(`* 2.py`) that do not exist in the baseline worktree.

---

## Sprint 2 — Execution-state correctness & price safety

### S2-1 · Exit state mutated before any fill — **DONE** · P0

* **Files**: [src/algo/position_manager.py](../src/algo/position_manager.py)
* **Root cause**: `check_exit_conditions()` was documented as a check but
  behaved as a command. On a price merely *touching* `target_1r_price` it set
  `partial_exit_1r = True` **and** moved `stop_loss_price` to breakeven —
  before any order was requested, let alone filled.
* **Impact**: two distinct financial defects.
  1. If the subsequent exit order was rejected, or the broker was
     unreachable, the flag was already consumed. The partial-exit level was
     **permanently lost** and never retried — the position rode to the stop
     with full size.
  2. The operator's stop-loss was silently moved on an unfilled touch,
     changing the risk profile of a position whose size had not changed.
* **Change**: `check_exit_conditions()` is now a pure query. A new
  `commit_partial_exit(reason)` records the level **after** a confirmed fill
  and performs the breakeven stop move there, where it is actually justified.
  `update_all_positions()` commits only when `reduce_position()` returns a
  fill; otherwise it logs and leaves the level retryable.
* **Tests**: `TestExitDetectionIsPure`, `TestPartialExitCommit`,
  `TestUpdateAllPositionsLifecycle` — covers touch-without-fill, rejected
  fill, duplicate fill event, out-of-order fill events, repeated polling and
  double-submission.

### S2-2 · Short partial exits booked inverted P&L — **DONE** · P0

* **Files**: [src/algo/position_manager.py](../src/algo/position_manager.py)
* **Root cause**: `reduce_position()` used the long-only formula
  `exit_price - entry_price` with no direction branch, although
  `close_position()` on the same class already branched correctly.
* **Impact**: every short partial exit booked P&L with the wrong sign — a
  profitable short cover was recorded as a loss of equal magnitude. This
  flowed into `current_equity`, `daily_pnl`, `weekly_pnl` and the
  consecutive-loss risk scaler, which would then *reduce* size after
  profitable shorts.
* **Change**: direction-aware sign, plus a zero-entry-price guard on the
  percentage calculation.
* **Tests**: `TestReducePosition::test_short_partial_pnl_sign_is_correct`
  (short from 100, cover 100 shares at 90 → **+1000**, previously −1000).

### S2-3 · Unvalidated prices corrupting portfolio state — **DONE** · P0

* **Files**: new [src/core/price_validation.py](../src/core/price_validation.py),
  [src/algo/position_manager.py](../src/algo/position_manager.py)
* **Root cause**: `update_price()`, `close_position()` and
  `reduce_position()` accepted any float.
* **Impact**: a single `NaN` quote propagated into `unrealized_pnl`, then
  into `current_equity` on exit. Because **every** comparison against `NaN`
  is `False`, `if self.current_equity > self.peak_equity` never fires again —
  peak equity freezes and drawdown reporting is corrupted permanently, with
  no exception raised anywhere.
* **Change**: fail-closed validation with machine-readable reason codes
  (`PRICE_NAN`, `PRICE_INFINITE`, `PRICE_NEGATIVE`, `PRICE_ZERO`,
  `PRICE_MISSING`, `PRICE_NOT_NUMERIC`). Invalid input raises
  `InvalidPriceError` at the position level and is rejected with a log at the
  manager level. A bad price is **never** substituted with a last-known
  value — inventing a price is worse than refusing to act.
* **Tests**: `TestPriceValidation`, `TestPositionPriceHygiene` — including an
  explicit assertion that a rejected `NaN` leaves prior P&L state untouched.

### S2-4 · Stop-placement side validation — **DONE** · P1

* **Files**: [src/core/price_validation.py](../src/core/price_validation.py)
* **Change**: `validate_stop_placement()` verifies a long stop sits below
  entry and a short stop above it, returning a reason code
  (`STOP_WRONG_SIDE_LONG` / `STOP_WRONG_SIDE_SHORT` / `STOP_MISSING`).
* **Deliberately advisory**: per the brief, no existing user stop is
  auto-modified. The validator reports; the caller decides.
* **Tests**: `TestStopPlacement` — 7 cases including stop-equals-entry and
  `NaN` entry.

---

## Sprint 2 — Verification of previously reported findings

Two of the five findings in the Sprint 2 brief were **already fixed** and
required verification rather than another change.

### S2-5 · Client-side API credential exposure — **DONE (pre-existing)**

* **Verified**: [src/api/main.py](../src/api/main.py#L773) renders
  `index.html` with `{"api_key": ""}`. The only template reference is an
  empty JSON island. A same-origin, HttpOnly, HMAC-signed, portfolio-scoped
  session cookie already exists in
  [src/api/routers/operator_session.py](../src/api/routers/operator_session.py),
  with CSRF mitigation via `_same_origin_for_cookie_mutation()` and a
  privileged tier (`verify_sensitive_api_key`) that accepts the header key
  **only** — never the cookie.
* **No change made.** The architecture already matches the recommendation.
* Sprint 1 closed the remaining gap in this area: the key comparison itself
  is now timing-safe.

### S2-6 · Holding-period consistency — **DONE (Sprint 1)**

* `Position.days_held` and the `max_hold_days` time-exit both use
  [src/core/trading_calendar.py](../src/core/trading_calendar.py).
* Verified no third holding-period implementation exists in
  `position_manager.py`.

### S2-7 · UniverseFilter missing-data behaviour — **DONE (Sprint 1)** for
market cap; **NOT_STARTED** for the remaining fields (backlog B4).

---

## Open backlog

| ID | Priority | Item | Status |
|----|----------|------|--------|
| B1 | P1 | Triage 308 pre-existing failures (mostly `index.html` string assertions + live-network tests) into real defects vs fixture rot | NOT_STARTED |
| B2 | P1 | Re-run backtests after the `max_hold_days` semantics fix | NOT_STARTED |
| B3 | P1 | Audit remaining silent-default patterns in `signal_engine.py` | NOT_STARTED |
| B4 | P1 | Extend `PASS / REJECT / INSUFFICIENT_DATA` classification to price, volume, history, spread, earnings and corporate actions | NOT_STARTED |
| B5 | P1 | Deduplicate risk policy across `portfolio_risk_budget.py`, `position_manager.py`, `risk_limits.py` | NOT_STARTED |
| B10 | P1 | Confidence-score semantics: `ScoreUnifier` / `EdgeChecklist` must distinguish setup quality from calibrated win probability, and surface an explicit *uncalibrated* status | NOT_STARTED |
| B11 | P1 | Wire `validate_stop_placement()` into the trade-proposal path so invalid configurations are rejected pre-trade | NOT_STARTED |
| B6 | P2 | ~150 untracked iCloud duplicate files pollute the tree and are collected by pytest | BLOCKED (needs authorization) |
| B7 | P2 | `src/api/main.py` responsibility split | NOT_STARTED |
| B8 | P2 | Dashboard UI/UX modernization | BLOCKED (needs in-browser validation) |
| B9 | P2 | Map the TypeScript / VS Code-extension codebase vs the Python platform | NOT_STARTED |

---

## Safety assessment — Sprint 2

| Area | Affected? | Notes |
|------|-----------|-------|
| Order execution semantics | **Yes** | Exit state is no longer mutated before a confirmed fill. Strictly safer. |
| Strategy calculations | **Yes** | Short partial-exit P&L sign corrected. Prior short-strategy results were wrong. |
| Portfolio data | **Yes** | Invalid prices can no longer corrupt equity / drawdown. No stored record modified. |
| Risk limits | No | Unchanged this sprint. |
| Authentication | No | Verified only; no change. |
| Broker integrations | No | Untouched. Live-order paths remain disabled by configuration. |
| Production configuration | No | No deployment or credential change. |

**Not production-ready.** B1 remains untriaged.
