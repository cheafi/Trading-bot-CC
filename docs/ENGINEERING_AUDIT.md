# Engineering Audit & Improvement Backlog

Evidence-based record of the autonomous engineering pass on `Trading-bot-CC`.
Status values: **Completed · In progress · Blocked · Not started**.

---

## 0. Baseline (established before any change)

| Item | Value |
|------|-------|
| Branch | `feat/quote-provenance-integration` @ `64bcd53d` (in sync with `origin`) |
| Command | `./.venv/bin/python -m pytest tests -q -p no:randomly --ignore=tests/e2e` |
| Baseline result | **308 failed · 1899 passed · 12 errors** (clean `git worktree` at HEAD) |
| Post-change result | **310 failed · 1945 passed · 12 errors** |
| Regression delta | **0 real regressions** |

The two extra "failures" come from untracked iCloud duplicate files
(`tests/test_order_execution_reconciliation 2.py`,
`tests/test_vnext_p0_review 2.py`) that do not exist in the baseline worktree.
A third (`tests/sprints/test_sprint64.py::test_dedup_survives_rebuild`) passes
in isolation and is order-dependent on shared `data/alerts.jsonl` state.

> The pre-existing 308 failures are **not** caused by this work. They are
> dominated by `index.html` string-assertion tests and live-network API tests.
> They remain open — see backlog item B1.

---

## 1. Completed — P0 Financial Safety & Security

### 1.1 Timing-unsafe API key comparison — **Completed**

* **File**: [src/api/deps.py](../src/api/deps.py)
* **Confirmed defect**: `_require_matching_api_key()` and `optional_api_key()`
  compared the submitted key with `!=`. Python string comparison short-circuits
  on the first differing byte, leaking key material through response-time
  differences. Note that `_header_api_key_valid()` (already timing-safe) existed
  in the same module but was bypassed on these two paths.
* **Fix**: both paths now route through `_header_api_key_valid()`
  (`hmac.compare_digest`).
* **Not weakened**: the production fail-closed branch, the
  `CC_DEV_ALLOW_UNAUTH_API` restriction to non-sensitive routes, and the
  same-origin CSRF check on cookie mutations are unchanged.

### 1.2 `days_held` calendar-day approximation — **Completed**

* **Files**: [src/algo/position_manager.py](../src/algo/position_manager.py),
  new [src/core/trading_calendar.py](../src/core/trading_calendar.py)
* **Confirmed defect**: `int(calendar_days * 5 / 7)`. Monday → Friday
  (4 real sessions) returned **2**. This propagated into `avg_hold_days`
  performance reporting and the trade journal.
* **Fix**: new dependency-free NYSE calendar deriving holidays from published
  rules (incl. Good Friday via the Meeus/Jones/Butcher algorithm, Juneteenth
  from 2022, and the Saturday→Friday / Sunday→Monday observance rule).
  Timezone-aware inputs are normalised to the US/Eastern session date.

### 1.3 `max_hold_days` compared against calendar days — **Completed**

* **File**: [src/algo/position_manager.py](../src/algo/position_manager.py)
* **Confirmed defect** (found while fixing 1.2): `check_exit_conditions()`
  compared `(current_date - entry_date).days` against `max_hold_days`, but
  `SignalThresholds.max_hold_*` is specified in **trading** days. Positions were
  time-exited roughly 28% early (7 calendar days per 5 sessions).
* **Fix**: comparison now uses `trading_days_between()`.
* **[RISK vs ALPHA tension]** This holds positions materially longer than
  before. It restores the *intended* holding horizon, but any backtest result
  produced before this change is no longer comparable. See backlog item B2.

### 1.4 Missing market cap silently passed the universe gate — **Completed**

* **File**: [src/engines/signal_engine.py](../src/engines/signal_engine.py)
* **Confirmed defect**: `row.get("market_cap", float("inf")) or float("inf")`.
  Any ticker lacking fundamentals — or carrying a `None`/`NaN`/malformed value —
  was assigned an infinite market cap and therefore **always satisfied**
  `min_market_cap`. Missing data produced false eligibility, i.e. false
  trading confidence.
* **Fix**: market cap is now parsed explicitly; `None`, non-numeric,
  non-positive and non-finite values are classified as **MISSING** and rejected
  with reason `mkt_cap MISSING (data quality)`.
* **Policy**: `UniverseFilter(require_market_cap=False)` allows research and
  backtest universes without fundamentals. Execution paths keep the default
  (`True`) so missing data cannot reach a live decision.

### 1.5 Unvalidated risk configuration — **Completed**

* **File**: [src/core/risk_limits.py](../src/core/risk_limits.py)
* **Confirmed defect**: `_env_float` / `_env_int` were bare casts. A malformed
  value raised an opaque `ValueError` at import time, and — more dangerously —
  any *parseable* value was accepted: `RISK_MAX_POSITION_PCT=-0.05`,
  `RISK_MAX_POSITIONS=0`, `RISK_MAX_DRAWDOWN_PCT=1.5` and `VIX_CRISIS=10`
  all loaded without complaint.
* **Fix**: new `RiskConfigError` plus `lo`/`hi` bounds on every env-overridable
  parameter, NaN/Inf rejection, and a `VIXThresholds.__post_init__` invariant
  enforcing `low < mid < high < crisis`.
* **Fail-closed**: an unsafe risk parameter now aborts application start rather
  than silently arming an uncapped position size.

---

## 2. Tests

* **New**: [tests/test_p0_financial_safety.py](../tests/test_p0_financial_safety.py)
  — 39 tests, **all passing**.
* Coverage: NYSE holiday table (10 parametrised holidays), Juneteenth
  pre-2022 behaviour, weekend spans, reversed ranges, multi-year totals
  (248–254 session sanity band), timezone normalisation, explicit
  `extra_holidays`, the exact Mon→Fri case the old `5/7` formula got wrong,
  the `max_hold_days` early-exit regression, timing-safe key comparison
  (including a source-level guard against reverting to `!=`), and six
  universe data-quality scenarios (missing / `None` / malformed / research
  opt-out / genuinely small cap / valid large cap).

```bash
./.venv/bin/python -m pytest tests/test_p0_financial_safety.py -q
# 39 passed
```

---

## 3. Open backlog

| ID | Priority | Item | Status |
|----|----------|------|--------|
| B1 | P1 | 308 pre-existing test failures, mostly brittle `index.html` string assertions and live-network API tests. Needs triage into "real defect" vs "test fixture rot". | Not started |
| B2 | P1 | Re-run backtests after the `max_hold_days` semantics fix; previous results used a ~28% shorter effective horizon. | Not started |
| B3 | P1 | Audit remaining `float("inf")` / silent-default patterns elsewhere in `signal_engine.py` for the same false-eligibility class of bug. | Not started |
| B4 | P1 | Extend the data-quality classification (`VALID / STALE / MISSING / INVALID / INSUFFICIENT_HISTORY`) to price, volume and history gates, not just market cap. | Not started |
| B5 | P1 | Deduplicate risk policy: `src/engines/portfolio_risk_budget.py` and `src/algo/position_manager.py` still carry their own limits alongside `src/core/risk_limits.py`. | Not started |
| B6 | P2 | Repository hygiene: ~150 untracked iCloud duplicate files (`* 2.py`, `* 3.py`) pollute the working tree and are collected by pytest. Requires owner sign-off before deletion. | Blocked (needs authorization) |
| B7 | P2 | `src/api/main.py` responsibility split (routes / lifecycle / state). | Not started |
| B8 | P2 | Dashboard UI/UX modernization — requires a running server and browser preview to assess honestly. | Blocked (not yet validated in-browser) |
| B9 | P2 | Map the TypeScript / VS Code-extension codebase against the Python trading platform and document ownership. | Not started |

---

## 4. Safety assessment for this batch

| Area | Affected? | Notes |
|------|-----------|-------|
| Authentication | **Yes** | Strengthened only. No requirement relaxed. |
| Risk limits | **Yes** | Validation added. Default values unchanged. |
| Strategy calculations | **Yes** | Holding-period and time-exit semantics corrected; prior backtests invalidated (B2). |
| Signal eligibility | **Yes** | Strictly tightened — names with missing fundamentals are now rejected, so signal count may fall. |
| Portfolio data | No | No schema or record changes. |
| Broker integrations | No | Untouched. |
| Order execution | No | No live-order path modified; all remain disabled by configuration. |
| Production configuration | No | No deployment, credential or env change made. |

**This system is not certified production-ready.** 308 pre-existing test
failures remain untriaged (B1).
