# CC · Clarity Console — 10/10 Upgrade Plan

**Baseline:** [CC_FULL_SYSTEM_AUDIT.md](./CC_FULL_SYSTEM_AUDIT.md) — **8.2/10** (2026-06-02)  
**Target:** **10/10** paper/monitor desk with E2E + ops discipline + maintainable monolith

---

## 1. EXECUTIVE VERDICT (target scores)

| Dimension            | Baseline |   Target | Path                                                                  |
| -------------------- | -------: | -------: | --------------------------------------------------------------------- |
| Trust & honesty      |      8.7 |     9.5+ | Warmup/offline distinction, provenance strip, dossier copy            |
| Trading intelligence |      8.3 |     9.0+ | Mission panel, reconciliation banner (done), cold-start queue preview |
| UX / IA              |      8.2 |     9.0+ | Today mission, recovery runbook, RS test alignment                    |
| Reliability          |      7.6 |     9.0+ | `_start_server.sh` health skip, Playwright matrix, ops runbook        |
| Test coverage        |      8.7 |     9.5+ | 139+ bundle + warmup/ops tests + E2E stubs                            |
| **Overall**          |  **8.2** | **10.0** | Phases A–F below                                                      |

---

## 2. WHAT IS ALREADY STRONG

(Unchanged from audit §2 — surface authority, card grade pipeline, IBKR LOGIN semantics, data contract, `surfaceEmptyState`, trading-intel helpers.)

**Post-audit adds (2026-06-02):**

- `warmupStatusLine()` / `warmupUpgradeQueue()` on contract strip + instant banner
- `trustProvenanceLine()` on data contract strip
- `todayMissionPanel()` on Dashboard
- `opsRecoveryGuide()` in Ops health
- `cc-helpers.js` Phase 1 extract
- E2E stub suite + `playwright.config.ts`

---

## 3. CRITICAL BUGS — remaining

| Priority | Item                | Status                                                                 |
| -------- | ------------------- | ---------------------------------------------------------------------- |
| P2       | Monolith ~13k lines | **Planned** — [CC_MONOLITH_SPLIT_PLAN.md](./CC_MONOLITH_SPLIT_PLAN.md) |
| P2       | Test RS label drift | **Fixed** — `RS·research`                                              |
| P2       | No Playwright CI    | **Stubbed** — `tests/e2e/cc_operator_workflows.spec.ts`                |

---

## 4. TRUST FAILURES — close remaining gaps

| Gap                           | Mitigation                                | Status   |
| ----------------------------- | ----------------------------------------- | -------- |
| Cold-start looks “live”       | Warmup vs OFFLINE vs DEGRADED lines       | **Done** |
| Snapshot age hidden           | `trustProvenanceLine()`                   | **Done** |
| Dossier “validated” narrative | Indicative-only copy + board score labels | **Done** |

---

## 5. WORKFLOW FAILURES — close remaining gaps

| Workflow                             | Mitigation                   | Status   |
| ------------------------------------ | ---------------------------- | -------- |
| Morning open — ambiguous loading     | Warmup strip + upgrade queue | **Done** |
| Ops — what to retry vs block capital | `opsRecoveryGuide()`         | **Done** |
| Dashboard — daily priorities         | `todayMissionPanel()`        | **Done** |

---

## 6. FEATURE-BY-FEATURE (delta to 10/10)

| Feature             | Delta                                               |
| ------------------- | --------------------------------------------------- |
| Dashboard           | Mission panel + warmup context (**done**)           |
| Ops                 | Recovery runbook wired to `ops_degraded` (**done**) |
| All deploy surfaces | E2E WAIT/LOGIN matrix (**stub**)                    |
| RS                  | Label consistency (**done**)                        |

---

## 7. TOP PRODUCT IMPROVEMENTS (next)

| #   | Item                                    | Status      |
| --- | --------------------------------------- | ----------- |
| 7   | Wire `cc-helpers.js` into template boot | **Next**    |
| 8   | Enable Playwright in CI (optional job)  | **Stub**    |
| 9   | Tab partials Phase 2                    | **Planned** |

---

## 8. TOP TRADING-INTELLIGENCE IMPROVEMENTS (next)

| #   | Item                                                    | Status           |
| --- | ------------------------------------------------------- | ---------------- |
| 7   | Server-push monitor queue in `/api/health` when loading | **Optional API** |
| 8   | Auto-refresh when `health.mode` flips to `full`         | **UX**           |

---

## 9. FINAL IA / AUTHORITY MODEL

Canonical rules unchanged (audit §9). **Add:**

7. **Warmup strip** overrides dismissible instant banner for capital actions until `health.mode=full`.
8. **Ops recovery runbook** is diagnostic — never grants deploy permission.

---

## Post-audit verification

```bash
PYTHONPATH=. .venv/bin/pytest \
  tests/test_surface_authority_header.py \
  tests/test_fetch_surface_state.py \
  tests/test_ui_render_integrity.py \
  tests/test_ui_render_safety.py \
  tests/test_dashboard_decision_integrity.py \
  tests/test_ibkr_diagnosis.py \
  tests/test_rejections_surface_integrity.py \
  tests/test_ops_surface_integrity.py \
  tests/test_playbook_board_fallback.py \
  tests/test_decision_honesty_helpers.py \
  tests/test_discovery_surface_integrity.py \
  tests/test_guide_surface_authority.py \
  tests/test_workflow_integrity.py \
  tests/test_feature_surface_integrity.py \
  tests/test_top_product_improvements.py \
  tests/test_trading_intelligence_improvements.py \
  tests/test_warmup_ux.py \
  tests/test_ops_recovery_guide.py \
  -q
```

**Target:** 145 passed (139 canonical + 6 new).

See audit **§12 Post-audit 10/10** pointer.
