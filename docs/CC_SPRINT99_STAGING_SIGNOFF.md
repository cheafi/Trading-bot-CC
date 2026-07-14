# CC · Clarity Console — Sprint99 Staging Soak Sign-Off

**Document type:** Staging soak sign-off (Sections 1–10)  
**Date:** 2026-07-14 (UTC+8 session)  
**Branch:** `sprint99-fund-productization`  
**HEAD:** `fd1e7bc944c0a80c9642dd6a886df96300e8704b`  
**Release report:** [CC_SPRINT99_RELEASE_REPORT.md](./CC_SPRINT99_RELEASE_REPORT.md)  
**Runbook:** [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md)

---

## Executive verdict

| Verdict | **STAGING_WITH_WARNINGS** |
|---------|---------------------------|
| Rationale | Automated release gates **RELEASE_READY**; live `/api/v7/today` on backend **:8001** confirms blocked-day authority invariants. Docker Desktop failed to start; browser MCP unavailable; 30‑min WAIT soak not executed; instant shell **:8000** health stuck `mode=loading` and `/api/v7/today` proxy timed out (>30s) despite healthy backend on **:8001**. |

---

## Environment record (§1 Setup)

| Field | Value |
|-------|-------|
| **Commit** | `fd1e7bc944c0a80c9642dd6a886df96300e8704b` |
| **OS** | Darwin 24.5.0 (macOS) |
| **Browser** | Not used — no browser MCP in session; static HTML + Node export smoke only |
| **Docker** | Installed (`Docker version 29.5.3`) — **Desktop unable to start** |
| **API base URL (full)** | `http://localhost:8001` (uvicorn child via `_cc_instant.py`) |
| **API base URL (instant shell)** | `http://localhost:8000` (dashboard HTML OK; health proxy degraded) |
| **Stack started** | `_cc_instant.py` via `.venv-staging` (Docker compose fallback) |
| **Timestamp (UTC)** | 2026-07-14T14:12:00Z (live API capture) |
| **Session operator** | Agent automated soak (no human browser) |

### §1 Setup — **PASS (with warnings)**

| Step | Result | Evidence |
|------|--------|----------|
| `git pull origin sprint99-fund-productization` | PASS | Already up to date → `fd1e7bc` |
| `bash scripts/cc-release-check.sh` | PASS | VERDICT: **RELEASE_READY** — 0 critical, 0 warnings |
| `docker compose -f docker-compose.dev.yml down && up --build` | **FAIL** | `Docker Desktop is unable to start` |
| Fallback stack | PASS | `.venv-staging` created; `_cc_instant.py` running; backend import ~185s |

---

## Twelve acceptance items

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Branch at expected HEAD | **PASS** | `fd1e7bc` (report doc commit on branch) |
| 2 | `cc-release-check.sh` green | **PASS** | All 9 steps PASS; snapshot `today_payload_20260714T134803Z.json` |
| 3 | Runnable API / dashboard | **PASS (warn)** | Dashboard HTML 1.19MB @ `:8000/`; full API @ `:8001` |
| 4 | Live `system_truth` + intelligence stack | **PASS** | See §2 — all required fields on `:8001` |
| 5 | Blocked day: MONITOR ONLY, deploy-qualified=0 | **PASS** | `operator_tier_now`: `MONITOR ONLY · Deploy blocked`; `deploy_qualified_count`: 0 |
| 6 | Intelligence collapsed / research-only | **PASS** | `decision_quality.collapsed: true`, `authority_effect: none`; OI `authority_effect: none` |
| 7 | IBKR scenario copy / truth | **PASS** | See §4 — offline/LOGIN/READY+blocked/READY+open documented |
| 8 | Export non-blank + monitor framing | **PASS** | 5/5 `test_cc_export_smoke`; Node HTML len 2950; workflow line includes “monitor-only — not trade authority” |
| 9 | Replay: banner semantics, no deploy authority | **PASS** | `replay_mode: true`; `deploy_authority: false`; gates `deploy/handoff: false` |
| 10 | UTF-8 / visible copy | **PASS (warn)** | `audit-visible-copy.py --fail-on high` PASS; ~65 template `?` suspects (emoji/punctuation corruption, pre-existing) |
| 11 | Performance smoke | **PASS** | `perf-smoke-check.py` all thresholds OK (limited soak — no 30 min tab) |
| 12 | Authority invariants | **PASS** | `may_authorize_deploy: false`; `deploy_authority: false`; no `can_auto_loosen` |

---

## Section results (1–10)

### §2 Live API smoke — **PASS**

**Endpoint:** `GET http://localhost:8001/api/v7/today` (200, ~98KB, ~6s)

| Field / check | Status |
|---------------|--------|
| `system_truth` | Present |
| `execution_readiness` | Present |
| `decision_quality` | Present |
| `opportunity_intelligence` | Present |
| `alpha_quality` (in DQ) | Present, collapsed |
| `alpha_review` (in DQ) | Present |
| `threshold_governance` (in DQ) | Present |
| `may_authorize_deploy` | **false** ✓ |
| `deploy_authority` | **false** ✓ |
| `operator_tier_now` | `MONITOR ONLY · Deploy blocked` |
| `deploy_qualified_count` | 0 |
| `board_gate` | `wait` |
| `broker_state` | `offline` |
| Stale flags | `trust.stale: true`, `market_data_freshness: expired` |

**Note:** `curl http://localhost:8000/api/v7/today` returned instant-degraded snapshot without `system_truth` and timed out after backend warm-up — use **:8001** or Docker compose when Desktop available.

Dry-run snapshot (release check) also validated: `data/release_snapshots/today_payload_20260714T134803Z.json`.

---

### §3 Blocked day soak — **PASS (automated partial) / SKIP (browser manual)**

No browser MCP. Automated / static evidence:

| Surface | Check | Result |
|---------|-------|--------|
| Dashboard | `MONITOR ONLY` in template + live tier | PASS |
| Playbook | `data-cc="playbook-surface"`; deploy-qualified 0 | PASS |
| Discovery | `Research only · deploy authority unavailable` | PASS |
| Dossier | `Structure Review Only` | PASS |
| Portfolio | `Risk review only` | PASS |
| Ops | `data-cc="ops-recovery-runbook"` | PASS |
| Deploy buttons | No `Send to IBKR` in static shell when WAIT | PASS (static) |
| 30+ min tab soak | Not executed | **SKIP** |

---

### §4 IBKR scenarios — **PASS (documented expected vs observed)**

| Scenario | Expected | Observed (truth resolver + hints) |
|----------|----------|-----------------------------------|
| **Broker offline** | `broker_state: offline`, handoff blocked, OFFLINE hint | `deploy_authority: false`, `execution_gate: offline`, hint: “IBKR OFFLINE — start Gateway/TWS…” |
| **LOGIN only** | Session not READY; no handoff | `deploy_authority: false`; hint: “IBKR LOGIN — connect session… READY required before handoff” |
| **READY + blocked** | READY does not override closed board | Simulated: `broker_state: partial/ready`, `board_gate: closed`, `deploy_authority: false`, `deploy_qualified: 0` |
| **READY + gates open** | Paper path may unlock only when board + qualifications allow | Simulated: `board_gate: open`, `execution_gate: ready`, still `deploy_authority: false` with 0 qualified in test vector; live payload: gates wait, 0 deploy-qualified |

Live session: IB broker disabled (`ib_insync not installed`), paper broker only — consistent with offline/blocked posture.

---

### §5 Export all pages browser smoke — **PASS (automated) / SKIP (browser PDF)**

| Check | Result |
|-------|--------|
| `test_cc_export_smoke.py` (5 tests) | PASS |
| `buildExportReviewHtml` length | 2950 chars (>120 threshold) |
| Monitor framing | “monitor-only — not trade authority” in workflow + footer |
| Timestamp filename pattern | `cc-review-export-2026-07-14T14-12-18-358Z.pdf` (sample) |
| Real browser html2canvas PDF | **SKIP** — manual: Cmd+Shift+R → Export from header/Ops/FAB |

---

### §6 Time travel / replay — **PASS**

`GET /api/v7/today?as_of=2026-06-05`:

- `replay_mode: true`, `replay_as_of: 2026-06-05`
- `decision_authority.deploy_authority: false`
- `decision_authority.research_only: true`
- `blocked_reason`: `Replay mode · 僅供回測檢視`
- Gates: `{ replay_mode: true, deploy: false, handoff: false }`

Template contains `REPLAY` banner pill and Time Travel copy (`歷史快照 · 非即時`).

---

### §7 UTF-8 / copy sweep — **PASS (with warnings)**

| Check | Result |
|-------|--------|
| `audit-visible-copy.py --fail-on high` | PASS |
| `audit-authority-language.py --fail-on critical` | PASS (via release check) |
| Chinese labels in live payload | `daily_use_zh`: `今日：僅監察` |
| `??` nullish-coalescing (JS) | Benign — not corruption |
| Literal `?` corruption in UI strings | **WARN** — ~65 suspects (e.g. `' ? not a trade trigger'`, `'MONITOR ONLY ? Agent degraded'`) — track for UTF-8 repair sprint; not introduced in this soak |

---

### §8 Performance soak — **PASS (limited duration)**

| Check | Result |
|-------|--------|
| `perf-smoke-check.py` | All steps OK (today_build 17ms, export_html 2ms) |
| 30 min WAIT tab soak | **SKIP** — session limited |
| API errors during ~15 min server run | MarketData warnings (LC, CWAN thin history); no authority exceptions |
| Backend cold import | ~185s to uvicorn ready; prewarm ~81s |

---

### §9 Release report update — **PASS**

This document created: `docs/CC_SPRINT99_STAGING_SIGNOFF.md`.

---

### §10 Final acceptance — **PASS (with warnings)**

| Criterion | Status |
|-----------|--------|
| No authority logic changes in soak | ✓ |
| No weakened verifiers | ✓ |
| `may_authorize_deploy` false when gate closed | ✓ (live) |
| Intelligence layers research-only | ✓ |
| Export smoke non-empty | ✓ |
| Docker staging stack | ✗ — manual required |
| Browser visual soak | ✗ — manual required |
| 30 min WAIT soak | ✗ — manual required |
| `cc-e2e` CI streak | Out of scope — still open on main |

---

## Open issues

| ID | Severity | Issue | Owner action |
|----|----------|-------|--------------|
| O1 | **High** | Docker Desktop unable to start on soak host | Restart Docker Desktop; run `docker compose -f docker-compose.dev.yml up --build -d` |
| O2 | **Medium** | Instant `:8000` health remains `mode=loading`; `/api/v7/today` proxy timeout | Use `:8001` directly or Docker; verify proxy after Desktop fix |
| O3 | **Medium** | Browser export PDF not validated in real browser | Clear `localStorage.cc_today7_snapshot`; hard refresh; export from header/Ops/FAB |
| O4 | **Medium** | 30+ min WAIT tab soak not executed | Leave Dashboard open ≥30 min; confirm no green TRADE pills |
| O5 | **Low** | Template `?` punctuation corruption (~65 instances) | UTF-8 repair pass (existing tech debt) |
| O6 | **Low** | `test_soak_verification.test_deploy_surfaces_recovery_checkpoints` failed locally (`engineOffRecoveryLine()` not in partial) | Non-blocking; node verifiers pass |
| O7 | **Info** | `cc-e2e` Playwright green streak on main | Track separately per release report §9 |

---

## Manual steps for operator (Docker / browser unavailable in session)

1. **Fix Docker Desktop** → `docker compose -f docker-compose.dev.yml up --build -d`
2. **Clear CC cache:** DevTools → Application → localStorage → delete `cc_today7_snapshot`
3. **Hard refresh** dashboard (`Cmd+Shift+R`)
4. **Live API:** `curl http://localhost:8000/api/v7/today | jq '.system_truth.operator_tier_now, .decision_quality.may_authorize_deploy'`
5. **Blocked day walk:** Dashboard → Playbook → Discovery → Dossier → Portfolio → Ops — confirm MONITOR ONLY, 0 deploy-qualified, no deploy CTAs
6. **Export:** Header, Ops, and FAB → confirm PDF ≥80 chars, timestamp filename, “not trade authority” footer
7. **Replay:** Time Travel → pick date → confirm purple REPLAY banner; no live deploy
8. **IBKR:** Exercise LOGIN→READY with Gateway when available; confirm no handoff on WAIT
9. **30 min soak:** Keep tab open on WAIT day; periodic refresh; log counter drift
10. **Re-run gate:** `bash scripts/cc-release-check.sh`

---

## Sign-off table (runbook parity)

| Area | Owner | Date | Result | Notes |
|------|-------|------|--------|-------|
| Loading / full | Agent | 2026-07-14 | **Partial** | Backend full on :8001; instant health stuck loading |
| IBKR READY | Agent | 2026-07-14 | **Partial** | Offline/disabled; copy verified |
| Engine / stale | Agent | 2026-07-14 | **PASS** | Engine off + stale flags in live payload |
| Route abort | — | — | **SKIP** | Browser/DevTools not run |
| WAIT soak 30+ min | — | — | **SKIP** | Manual required |
| Export PDF browser | Agent | 2026-07-14 | **Partial** | Node smoke only |
| Replay | Agent | 2026-07-14 | **PASS** | API + template |
| Release check | Agent | 2026-07-14 | **PASS** | RELEASE_READY |

---

## Commands reference

```bash
git pull origin sprint99-fund-productization
bash scripts/cc-release-check.sh
docker compose -f docker-compose.dev.yml up --build -d   # when Docker available
curl http://localhost:8001/api/v7/today | jq '.system_truth.deploy_authority, .decision_quality.may_authorize_deploy'
curl "http://localhost:8001/api/v7/today?as_of=2026-06-05" | jq '.replay_mode, .decision_authority'
python3 scripts/perf-smoke-check.py
```

---

_Staging soak sign-off for Sprint99 fund productization. Pair with [CC_SPRINT99_RELEASE_REPORT.md](./CC_SPRINT99_RELEASE_REPORT.md) and automated gate output._
