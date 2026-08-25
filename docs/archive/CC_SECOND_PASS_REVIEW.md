> **Superseded by [`CC_X_ENGINEERING_BACKLOG.md`](../CC_X_ENGINEERING_BACKLOG.md) and [`CC_X_ARCHITECTURE.md`](../CC_X_ARCHITECTURE.md) — retained for history only.**

# CC · Clarity Console — Second-Pass Polish Review

**Date:** 2026-06-02  
**Baseline:** [CC_FULL_SYSTEM_AUDIT.md](./CC_FULL_SYSTEM_AUDIT.md) **8.6/10** · [CC_10_10_UPGRADE_PLAN.md](./CC_10_10_UPGRADE_PLAN.md)  
**Scope:** Operator UX consistency, copy deduplication, `cc-helpers.js` wiring, `fetch_surface_state.py` severity vocabulary  
**Method:** Targeted grep/static review (no full re-audit) + `tests/test_second_pass_polish.py` + canonical §3–§8 pytest bundle

---

## 1. Executive Summary

Second pass closes **operator-visible repetition** (warmup + instant banner + data contract), **split retry CTAs** (“Retry shortly” vs “API still loading”), and **pill severity drift** between PM strip and data contract. `cc-helpers.js` is now loaded before Alpine; Python and JS share `severity_badge_class` / `surface_warmup_loading_line` contracts.

**Verdict: 9.0/10** for paper/monitor desk UX honesty and copy discipline — up from **8.6** on polish dimensions; remaining 1.0 is E2E + monolith split (unchanged).

**Follow-up:** [CC_THIRD_PASS_REVIEW.md](./CC_THIRD_PASS_REVIEW.md) — **9.2/10** post-pass (loading recovery copy, helper precedence, Playwright assertions).

---

## 2. Repo / Architecture / File Audit

| Area           | Files touched                                            |
| -------------- | -------------------------------------------------------- |
| Template       | `src/api/templates/index.html`                           |
| Static helpers | `src/api/static/cc-helpers.js`                           |
| Server copy    | `src/services/fetch_surface_state.py`                    |
| Tests          | `tests/test_second_pass_polish.py`                       |
| Docs           | This file; one-line pointer in `CC_FULL_SYSTEM_AUDIT.md` |

No router or authority logic changes — presentation and vocabulary only.

---

## 3. Before vs Now Gap Analysis

| Gap (baseline)                                        | Second-pass fix                                                                                           |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Warmup line repeated in instant banner + global strip | `warmupContextStripVisible()` hides strip when instant banner active; removed inline warmup inside banner |
| “API still loading” duplicated on Ops tab             | `opsGlobalLoadingLine()` + `surfaceWarmupLoadingLine('ops_diagnostic')` — single sentence                 |
| “Retry shortly” vs “Refresh” vs “Retry recommended”   | Ops unavailable/retry copy aligned to “Retry in a few seconds…”; loading lines centralized                |
| PM strip vs data contract pill classes hand-coded     | `severityBadgeClass()` + `dataContractFetchStateKey()`                                                    |
| `cc-helpers.js` not loaded                            | `<script src="/static/cc-helpers.js">` before Alpine                                                      |
| Mission panel on Guide / deploy tone on WAIT          | `tab==='today'` guard; `todayMissionPanelTitle()` → “Today focus” on WAIT                                 |
| IBKR LOGIN: disconnect + connect CTA noise            | Hide last-disconnect when connect CTA; suppress full banner when LOGIN                                    |

---

## 4. Page-by-Page Review (delta only)

| Page                        | Delta score | Notes                                                             |
| --------------------------- | ----------- | ----------------------------------------------------------------- |
| Dashboard                   | A           | Mission panel WAIT copy; no duplicate warmup under instant banner |
| Playbook / Signals          | A           | Shared warmup strip logic                                         |
| Ops                         | A−          | Single global loading line vocabulary                             |
| IBKR                        | A           | Connect CTA primary on LOGIN; less disconnect duplication         |
| Guide                       | A           | Mission panel not shown (tab guard)                               |
| Dossier / Flow / Funds / RS | B+          | Tab-specific warmup lines via `surfaceWarmupLoadingLine(mode)`    |

---

## 5. Frontend / State / Routing Audit

- **Badge casing:** ALL CAPS retained on small pills (`FETCH FAILED`, `EXEC BLOCKED`); body/sentence case for banner headlines (`Instant degraded — …`).
- **Severity pills:** `pr` / `pa` / `pg` / `pw` from one `severityBadgeClass(state)` path.
- **Empty states:** Existing `surfaceEmptyState` wrappers unchanged; WARMING detail still uses shared loading sentence (not duplicated per tab block in Ops).

---

## 6. Data / Correctness / Reliability Audit

- `fetch_surface_state.py`: added `STATE_FAILED_FETCH_FALLBACK`, `severity_badge_class`, `surface_warmup_loading_line`, `surface_warmup_next_action`.
- Alpine delegates to `CCHelpers` when present; inline fallbacks preserve offline behavior if script fails to load.
- No change to `normalize_fetch_state` priority or IBKR diagnosis codes.

---

## 7. Top 10 Highest-ROI Improvements (this pass)

1. Wire `cc-helpers.js` in template boot
2. `warmupContextStripVisible()` dedupe
3. `severityBadgeClass()` on PM strip + data contract
4. Unified `surfaceWarmupLoadingLine(mode)`
5. Ops global loading single line
6. Remove “Retry shortly” fragment
7. Instant banner sentence-case + no duplicate API loading line
8. Mission panel Guide/WAIT guards
9. IBKR LOGIN connect-first strip
10. `test_second_pass_polish.py` regression pack

---

## 8. Top 10 Trust Killers (remaining)

1. No Playwright CI on WAIT/LOGIN visuals
2. Monolith ~13k lines merge risk
3. Cold backend import → long `mode=loading`
4. Operator dismisses instant banner and ignores data contract
5. Uncalled router paths (unchanged from audit)
6. Extended pytest bundle RS/backtest isolation failures (optional pack)
7. Council vs scanner disagreement during brief fallback (mitigated, not eliminated)
8. Dossier levels on partial load (indicative copy exists)
9. Port 8000 dual-proxy churn (ops)
10. Mock flow overlay on provider outage

---

## 9. Top 10 Fake-Sophistication Elements (unchanged watchlist)

1. Deploy KPI labels on degraded board without badge read
2. High fallback scores without `cardScoreLabel`
3. “Validated” narrative in third-party dossier paths (mostly fixed)
4. Backtest win-rate 0% without null guard (fixed in lab helpers)
5. Command tab as deploy gate (demoted)
6. Flow as entry trigger (confirmation-only copy)
7. RS as deploy authority (research-only)
8. Ops green when engine off
9. Synthetic flow without MOCK ONLY badge
10. Stale snapshot without refresh CTA (mitigated on market strip)

---

## Implementation log

| Item                                      | Status                                |
| ----------------------------------------- | ------------------------------------- |
| `cc-helpers.js` severity + warmup exports | Done                                  |
| Template script tag + Alpine delegation   | Done                                  |
| `fetch_surface_state.py` parity helpers   | Done                                  |
| `tests/test_second_pass_polish.py`        | Done                                  |
| Pytest canonical bundle + second pass     | **152 passed** (146 baseline + 6 new) |

---

## Final verdict

**9.0/10** — CC is **operator-grade consistent** on degraded copy and pill semantics; trust model from first audit intact. Ship next: Playwright matrix (Phase E) and monolith Phase 1 split per [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md).

_Second pass: 2026-06-02. No git commit in agent session._
