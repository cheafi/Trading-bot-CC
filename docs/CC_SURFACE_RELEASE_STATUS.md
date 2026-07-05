# CC · Clarity Console — Cross-Page Surface Release Status

**Date:** 2026-06-04  
**Branch:** `sprint99-fund-productization` (working tree)  
**HEAD:** `1e08bb1` — fix(render): stop today dashboard chrome bleeding into Discovery tab  
**Audit method:** `index.html` tab guards + `deploy_surfaces` placement, `tests/test_surface_ownership.py`, commits `1e08bb1` / `9c096d4` / `b2c8e4e` / `a367020`, working-tree diff, local pytest + template `--check`.

---

## 一、總覽 · Release posture

| Layer                              | Verdict                                                                                                                                            |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Surface DOM / authority (code)** | **9.5–9.8/10** — today/scanners bleed fixed at HEAD; incremental hardening in working tree (trust-strip, deploy `x-show`, `today-dashboard-body`). |
| **Promotable to 10/10**            | **NOT READY** — global gates below.                                                                                                                |
| **Guide (user-verified)**          | **✅ 9.5/10** — operator reference surface; pytest + partial extract; decision chips suspended by design.                                          |

### Status legend

| Category                | Meaning (已过关 / 未过关)                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------ |
| **✅ Shippable**        | Tab guard + authority mode correct; no known cross-tab chrome leak; automated checks green for this surface. |
| **⚠️ Verify after fix** | Fix landed locally or in WT; needs commit + CI/E2E/manual soak before calling production-safe.               |
| **❌ Release blocker**  | Known defect blocks release for this surface or entire app.                                                  |

---

## 二、逐頁狀態表 · Per-surface matrix

| Surface                         | Authority                                                              | Render integrity                                                                      | Surface ownership                                                                                          | Status                  | Blocker notes                                                                                                                                                                                                          |
| ------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **today** (Overview)            | `dashboard_core` · deploy gate · mission panel + `deploy-status-strip` | `test_ui_render_integrity` · `assert_template_render_safe` · KPI/fallback copy guards | **Full** — `test_surface_ownership.py` (9 tests): stray `</div>`, deploy inside `<main>`, DOM stack parser | **⚠️ Verify after fix** | HEAD `1e08bb1` fixed HTML5 auto-close bleed to Discovery; **WT**: trust-strip `tab==='today'`, `today-dashboard-body` wrapper, deploy partial `x-show` guards. Run `node scripts/build-cc-template.mjs` before commit. |
| **signals** (Ranked / Playbook) | `playbook_core` · Send to IBKR gated `playbookCanSendToIbkr`           | Playbook funnel/unlock/IBKR handoff tests in `test_ui_render_integrity`               | **Partial** — playbook excludes today deploy strip; single `data-cc="playbook-surface"`                    | **✅ Shippable**        | `9c096d4` removed duplicate playbook shell / deploy strip leak. E2E: no Send to IBKR on WAIT.                                                                                                                          |
| **scanners** (Scan / Discovery) | `discovery_research` · research-only posture                           | `test_discovery_surface_integrity.py`                                                 | **Full** — discovery block excludes deploy strip / FALLBACK banner                                         | **✅ Shippable**        | Primary victim of today chrome bleed — **fixed** `1e08bb1`. Manual: route-abort + fallback rows.                                                                                                                       |
| **stock-intel**                 | `dossier_research` (tab `dossier`; API `/api/v7/stock-intel/`)         | `test_dossier_fetch_state.py` · confirm-only / levels copy                            | **Partial** — `data-cc="dossier-surface"`; no separate tab id                                              | **✅ Shippable**        | Same surface as Dossier nav; CONFIRM ONLY authority unchanged.                                                                                                                                                         |
| **portfolio** (Book)            | `portfolio_manual` · per-tab `pfDecision.decision_bar`                 | `test_cc_portfolio_template_cleanup` · pf strip helper tests                          | **Partial** — pf Alpine leak patterns in `test_surface_ownership`; no `portfolio-surface` hook             | **⚠️ Verify after fix** | **WT**: `portfolioSummaryPnlIsPositive()` replaces raw `pf.summary` in `:class`. Sub-anchors: `portfolio-stop-blockers`, `portfolio-dd-sizing`.                                                                        |
| **funds**                       | `funds_research` · no deploy chips                                     | `test_funds_flow_cleanup` · index-fund judgment                                       | **None** — no `test_surface_ownership` slice                                                               | **✅ Shippable**        | More-menu tab; investable/regime stale pills only.                                                                                                                                                                     |
| **flow**                        | `flow_supporting` · mock overlay degraded copy                         | `test_options_flow_radar` · flow summary helpers in render integrity                  | **None**                                                                                                   | **✅ Shippable**        | Opened from dashboard KPI; non-decision overlay when degraded.                                                                                                                                                         |
| **ibkr**                        | `ibkr_execution` · trust strip tab-aware                               | `test_ui_render_integrity` (ibkrTrustStripLabel) · `test_cc_instant_ibkr`             | **None**                                                                                                   | **✅ Shippable**        | No `data-cc="ibkr-surface"`; execution handoff from playbook only when grade permits.                                                                                                                                  |
| **ops**                         | `ops_diagnostic`                                                       | `test_ops_recovery_guide` · soak runbook parity                                       | **Partial** — `data-cc="ops-surface"` · `ops-recovery-runbook` partial                                     | **✅ Shippable**        | Runbook bullets must match Python `ops_recovery_guide()` on staging.                                                                                                                                                   |
| **guide**                       | `guide_reference` · **decision suspended**                             | `test_guide_surface_authority.py` (12+ tests) · `guide.html` partial                  | **Full** — no deploy chips; passive strip only                                                             | **✅ Shippable**        | **User-verified ✅ 9.5/10**. Reference-only trust strip.                                                                                                                                                               |
| **rs**                          | `rs_supporting`                                                        | RS funnel copy via discovery handoff                                                  | **Partial** — `data-cc="rs-surface"` (**WT**)                                                              | **✅ Shippable**        | More-menu; links to Discovery scanners.                                                                                                                                                                                |
| **notrade** (Rejections)        | `rejections_diagnostic`                                                | Workflow / fetch-failed empty states in Alpine                                        | **Partial** — `data-cc="rejections-surface"` (**WT**)                                                      | **✅ Shippable**        | Trust strip + FETCH_FAILED copy; no deploy authority.                                                                                                                                                                  |
| **btlab**                       | `backtest_research`                                                    | Quant UI in `b2c8e4e` (strategy curve, DD sizer)                                      | **Partial** — `data-cc="btlab-surface"` (**WT**)                                                           | **✅ Shippable**        | Research-only; not a deploy gate.                                                                                                                                                                                      |
| **command**                     | `command_research` · explicit “not deploy gate” banner                 | Terminal layout under `x-show="tab==='command'"` (div, not `<main>`)                  | **None**                                                                                                   | **✅ Shippable**        | More-menu advanced aggregate; sizing requires today/signals.                                                                                                                                                           |

---

## 三、DOM / partial 審計 · index.html structure

### Tab guards (`x-show="tab==='…'"`)

| Tab id      | Container | `data-cc` anchor                     |
| ----------- | --------- | ------------------------------------ |
| `today`     | `<main>`  | `today-surface`                      |
| `signals`   | `<main>`  | `playbook-surface`                   |
| `scanners`  | `<main>`  | `discovery-surface`                  |
| `dossier`   | `<main>`  | `dossier-surface` (= stock-intel UX) |
| `portfolio` | `<main>`  | (section anchors only)               |
| `funds`     | `<main>`  | —                                    |
| `flow`      | `<main>`  | —                                    |
| `ibkr`      | `<main>`  | —                                    |
| `ops`       | `<main>`  | `ops-surface`                        |
| `guide`     | `<main>`  | `guide-surface`                      |
| `rs`        | `<main>`  | `rs-surface`                         |
| `notrade`   | `<main>`  | `rejections-surface`                 |
| `btlab`     | `<main>`  | `btlab-surface`                      |
| `command`   | `<div>`   | —                                    |

### `deploy_surfaces` partial

- Markers: `<!-- @cc-partial deploy_surfaces -->` … `<!-- @cc-partial-end deploy_surfaces -->`
- **Location:** inside today `<main>`, wrapped by `data-cc="today-deploy-chrome"` + `x-show="tab==='today'"` (HEAD + WT).
- **Injection:** `scripts/build-cc-template.mjs` — **must run** after editing `cc/partials/deploy_surfaces.html`.

### Orphan / bleed history (systemic DOM)

| Issue                                                                                                      | Affected tabs                                                           | Fix                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Stray `</div>` after today `<main>` open → HTML5 auto-closed `<main>`, deploy chrome visible on other tabs | **today → scanners** (primary), potentially all tabs under broken stack | **`1e08bb1`** removed stray close; tests `test_today_main_opens_without_stray_div_close`, `test_today_main_dom_stack_owns_deploy_strip` |
| Duplicate playbook shell + deploy strip leak                                                               | **signals**                                                             | **`9c096d4`**                                                                                                                           |
| Global trust-strip / surface-authority on non-today tabs                                                   | **guide, funds, flow, portfolio, ops, …**                               | **WT**: trust-strip `tab==='today'`; authority template `(today \|\| signals)` only                                                     |
| Partial ↔ index drift                                                                                     | CI `cc-e2e` template `--check`                                          | Run `node scripts/build-cc-template.mjs`                                                                                                |

**No orphan closing tags detected** by current `test_surface_ownership` suite after `1e08bb1` + WT (42/42 render + ownership tests pass locally).

---

## 四、`test_surface_ownership.py` 覆蓋範圍

| Covered                                                              | Not covered                                                           |
| -------------------------------------------------------------------- | --------------------------------------------------------------------- |
| today `<main>` open / stack / deploy strip nesting                   | portfolio, funds, flow, ibkr, ops, guide, rs, notrade, btlab, command |
| discovery excludes deploy chrome                                     | per-tab `<main>` sibling structure (implicit)                         |
| playbook excludes today deploy chrome                                |                                                                       |
| deploy partial markers only in today section                         |                                                                       |
| pf Alpine leak patterns (global HTML scan)                           |                                                                       |
| Playwright hooks: today / playbook / discovery / deploy-status-strip |                                                                       |

**Related suites (not in ownership file):** `test_discovery_surface_integrity.py`, `test_guide_surface_authority.py`, `test_surface_authority_header.py`, `test_ui_render_integrity.py`, `test_release_signoff.py`.

---

## 五、近期 commits · Render / API context

| Commit      | Summary                                                                                                                          | Surfaces touched                      |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| **1e08bb1** | Stop today dashboard chrome bleeding into Discovery; wrap `deploy_surfaces` in `x-show="tab==='today'"`; surface ownership tests | **today**, **scanners**               |
| **9c096d4** | Remove duplicate playbook shell and deploy strip leak regressions                                                                | **signals**                           |
| **b2c8e4e** | Quant strategy curve, cost rank, DD sizer, execution analytics UI + tests                                                        | **btlab**, portfolio DD widgets       |
| **a367020** | Wire quant + opportunity intelligence routers (`main.py` imports)                                                                | API backing **signals** / intel paths |

---

## 六、Working tree · 待提交修復

| File                                                 | Change                                                                                                                           | Impact                                       |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| `src/api/templates/index.html`                       | Trust-strip scope; `today-dashboard-body`; authority strip scope; rs/notrade/btlab `data-cc`; portfolio PnL helper; partial sync | **today**, **portfolio**, secondary surfaces |
| `src/api/templates/cc/partials/deploy_surfaces.html` | `x-show="tab==='today'"` on deploy strip + recovery lines                                                                        | **today** (all tabs if leak regressed)       |
| `tests/test_ui_render_integrity.py`                  | Assertion drift fixes                                                                                                            | CI pytest                                    |
| `src/services/institutional_13f.py`                  | `lag_copy` authority substring                                                                                                   | Opportunity intel copy tests                 |
| Docs deletions / new CC docs                         | Housekeeping                                                                                                                     | —                                            |

**Local verification (2026-06-04):** `node scripts/build-cc-template.mjs --check` **PASS** after sync · `pytest tests/test_surface_ownership.py tests/test_ui_render_integrity.py` **42 passed**.

**Not in WT (still global):** `cc-e2e` green streak on main, staging soak sign-off table empty, repo-wide `ruff` lint red.

---

## 七、Global release blockers · 全局限速

| Blocker                         | Severity   | Notes                                                                                                                               |
| ------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **`cc-e2e` on main**            | ❌ High    | 0 green runs in last 50 workflow executions per [CC_RELEASE_SIGNOFF.md](./CC_RELEASE_SIGNOFF.md); lint fails before Playwright job. |
| **CI lint (`ruff check src/`)** | ❌ High    | Unrelated failures (e.g. `src/algo/base_strategy.py`) block entire pipeline.                                                        |
| **Staging soak sign-off**       | ❌ Medium  | [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) §sign-off table empty — manual 30+ min WAIT, IBKR READY, route-abort.    |
| **Port 8000 / startup**         | ✅ Cleared | `main.py` SyntaxError noted fixed in signoff doc; `_cc_instant.py` health for E2E.                                                  |
| **Template drift**              | ⚠️ WT      | Fails `--check` if partial edited without `build-cc-template.mjs` — **resolved after sync in audit pass**.                          |

---

## 八、建議下一步 · Operator checklist

1. **Commit** render/ownership WT + run full canonical pytest bundle from [CC_AI_CONTEXT.md](./CC_AI_CONTEXT.md).
2. **Unblock CI lint** or scope ruff so `cc-e2e` (21 specs) runs on main.
3. **Manual soak** per runbook on staging — prioritize **today → scanners → signals** tab switch while engine OFF / IBKR LOGIN.
4. **Do not promote 10/10** until 3+ green `cc-e2e` on main + soak table signed.

---

_Generated for cross-page status review. Table language: English. Section headers: Cantonese-friendly where noted._
