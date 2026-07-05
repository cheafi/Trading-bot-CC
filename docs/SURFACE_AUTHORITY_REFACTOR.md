# Surface Authority Refactor (2026-06)

## Root cause

The PM command strip (`#pm-strip`) bound to **global** `decisionHub.decision_strip` on every tab. Stale playbook/dashboard fields (Idea QCOM · REDUCE · Avoid N) leaked onto Guide, Funds, Flow, RS, Discovery, Portfolio, and Ops.

Secondary:

- **`[object Object]`** — `fmtDisplay()` / evidence fields called `String()` on objects.
- **JS fragment leak** — inline `catch(e){console.warn('auto-schedule failed',e);alert(...)}` on one line could render if script boundaries broke. Fixed via `_handleAutoScheduleError()`.

## Fix

**One surface owns header summary** via `build_header_summary(surface_mode, context)` / Alpine `headerSummary()`.

Deploy chips (`show_decision_chips`) only on `dashboard_core` + `playbook_core`. Decision strip read only when `tab ∈ {today, signals}` via `_boardDecisionStrip()`.

### Surface modes

| Tab id                | Mode                  |
| --------------------- | --------------------- |
| today                 | dashboard_core        |
| signals               | playbook_core         |
| scanners              | discovery_research    |
| dossier / stock-intel | dossier_research      |
| portfolio             | portfolio_manual      |
| funds                 | funds_research        |
| flow                  | flow_supporting       |
| rs                    | rs_supporting         |
| notrade / rejections  | rejections_diagnostic |
| ops                   | ops_diagnostic        |
| ibkr                  | ibkr_execution        |
| btlab / backtest      | backtest_research     |
| guide                 | guide_reference       |

### Fetch states (`fetch_surface_state.py`)

loading, failed_fetch, stale, fallback, partial, probe_only, runtime_unknown, research_only, mock_only, no_data, not_authoritative, execution_blocked

Alpine: `ccFetchJson()` + `ccFetch({normalize:true})` → `surfaceFetchHints[tab]`.

## Files

- `src/services/surface_authority.py`
- `src/services/fetch_surface_state.py`
- `src/services/ui_render_safety.py`
- `src/api/templates/index.html` — `#pm-strip` uses `headerSummary()` only
- `src/api/routers/cc_header.py` — `?tab=` → `header_summary`

## Verify

```bash
pytest tests/test_surface_authority_header.py tests/test_fetch_surface_state.py tests/test_ui_render_integrity.py tests/test_ui_render_safety.py -q
```
