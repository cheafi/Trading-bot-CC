# CC · Clarity Console — Sprint99 Production Readiness Release Report

**Document type:** Formal release report  
**Date:** 2026-07-14  
**Branch:** `sprint99-fund-productization`  
**HEAD:** `8b09186` — sign-off **PASS**, verdict **RELEASE_READY**  
**Audience:** PM · SRE · Release Manager · Hedge-fund operator  
**SSOT references:** [OPERATOR_DECISION_OS.md](./OPERATOR_DECISION_OS.md) · [SURFACE_AUTHORITY_CONTRACT.md](./SURFACE_AUTHORITY_CONTRACT.md) · [INTELLIGENCE_STACK.md](./INTELLIGENCE_STACK.md) · [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md)

---

## 1. Executive Summary

Sprint99 **Fund Productization** delivers Clarity Console (CC) as an institutional PM decision console with a frozen **Operator Decision OS**: page gate beats card rank, research never equals permission, and analytics never auto-loosen deploy thresholds.

This branch ships:

- A **16-surface authority contract** with automated verifiers and banned-phrase enforcement
- A **five-layer intelligence stack** (persistent learning → Opportunity Intelligence → Alpha Quality → Alpha Review → Threshold Governance) — all collapsed-by-default, `authority effect: none`
- **Surface hardening** across Playbook, Discovery, Dossier, Portfolio, and Funds
- **Export All Pages fix** — non-empty PDF/JSON audit packages via off-screen rendering
- **Release hardening toolchain** — one-command gate (`scripts/cc-release-check.sh`) with template drift, authority language, visible copy, payload snapshot, and targeted pytest suites

At HEAD `8b09186`, automated release sign-off returns **VERDICT: RELEASE_READY** (0 critical failures). CC is promotable for operator use on this branch subject to remaining manual staging soak and CI E2E validation on main (see §9).

---

## 2. Release Status & Verdict

| Metric | Value |
|--------|-------|
| **Branch** | `sprint99-fund-productization` |
| **HEAD commit** | `8b09186` |
| **Automated sign-off** | **PASS** |
| **Verdict** | **RELEASE_READY** |
| **Critical failures** | 0 |
| **Gate command** | `bash scripts/cc-release-check.sh` |

### Verdict logic

| Condition | Verdict |
|-----------|---------|
| 0 critical failures, 0 warnings | `RELEASE_READY` |
| 0 critical, warnings only (e.g. optional perf smoke) | `RELEASE_WITH_WARNINGS` |
| Any critical failure | `RELEASE_BLOCKED` |

### What RELEASE_READY means

- Authority contract, runtime verifiers, and copy audits pass
- Today payload snapshot confirms `may_authorize_deploy: false` when gate closed
- Export smoke tests pass — no silent-empty PDFs
- Intelligence layers remain research/advisory only — no live threshold writes

### What RELEASE_READY does *not* mean

- Full production 10/10 without staging soak sign-off (see §9)
- Green `cc-e2e` Playwright streak on `main` (CI lint may still block downstream jobs)
- Live capital deployment permission — operator must still read Dashboard gate each session

---

## 3. Commit History / Changes

### Chronological / thematic map

| Theme | Commits | Summary |
|-------|---------|---------|
| **Foundation** | `3ce6e5b`, `520b051`, `5dfb65f`, `271bdc6`, `904774c`, `c4ac966` | Freeze Operator Decision OS; UTF-8 repair; shell truth wiring; Playbook authority VM; Today perf; portfolio offline posture |
| **Intelligence stack** | `c30d934`, `6efee22`, `f3c3223`, `8daf48d`, `9cb20f1`, `47480ba` | Decision quality → persistent learning → OI → Alpha QA → Alpha Review → Threshold Governance |
| **Surface hardening** | `a9a5904`, `9f545fb`, `548adfa` | Playbook blocked deploy truth; icon/tooltip UTF-8 repair |
| **Export fix** | `4595e2a` | Off-screen html2canvas render, enriched snapshot, JSON fallback, export smoke test |
| **Release hardening** | `1ffdfe3`, `8b09186` | `cc-release-check.sh`, release audit tests, docs, UI/copy polish, production readiness pass |

### Key commits (detail)

| Hash | Description |
|------|-------------|
| `3ce6e5b` | Freeze Operator Decision OS into enforceable product law |
| `520b051` | Restore UTF-8 emojis and Chinese labels corrupted to `??` in runtime UI |
| `6efee22` | Persistent learning layer with data-backed outcome tracking |
| `f3c3223` | Opportunity Intelligence Engine on persisted evidence |
| `8daf48d` | Alpha Quality Control Tower on OI and persisted learning |
| `9cb20f1` | Alpha Review loop on Alpha QA with human review queue |
| `47480ba` | Threshold Governance with human-gated proposals and shadow testing |
| `4595e2a` | Fix empty Export All Pages — off-screen render + enriched snapshot + JSON fallback |
| `1ffdfe3` / `8b09186` | CC release audit toolchain and complete production readiness pass |

### Key files touched (representative)

| Area | Files |
|------|-------|
| Authority | `src/services/surface_authority.py`, `authority_engine.py`, `operator_surface.py`, `decision_hierarchy.py`, `surface_authority_contract.py` |
| Intelligence | `opportunity_quality_engine.py`, `alpha_quality_evaluator.py`, `alpha_review_service.py`, `threshold_proposal_service.py`, `today_payload_builder.py` |
| UI / shell | `src/api/templates/index.html`, `src/api/static/cc-helpers.js` |
| Release tooling | `scripts/cc-release-check.sh`, `audit-authority-language.py`, `audit-visible-copy.py`, `snapshot-today-payload.py` |
| Tests | `tests/test_cc_release_audit.py`, `test_cc_export_smoke.py`, `test_cc_payload_snapshot.py`, `test_surface_authority_contract.py` |

---

## 4. Architecture & Authority Model

### Constitution (preserved across all surfaces)

1. **Page gate beats card rank** — L1 caps deploy before card scores matter
2. **Research ≠ permission** — Discovery, Flow, Funds, RS, Dossier, Strategy Lab inform; they do not authorize sizing alone
3. **One surface owns header copy** — `build_header_summary`; deploy chips only on Dashboard + Playbook
4. **Scoped truth** — Market / Board / Brief / Broker / Runtime / Authority; no contradictory global freshness pills
5. **Guide suspends decision language** — reference only; runtime not evaluated
6. **PILOT ≠ half-size default** — `pilot_sizing_allowed()` gates sizing
7. **Dossier ≠ decision card** — structure confirmation only; confirm-only hides trade plan and sizing
8. **Ops confirms runtime; IBKR confirms handoff** — engine ON ≠ capital permission; LOGIN ≠ READY

### Authority chain

```
decision_hierarchy.py → authority_engine.py → surface_authority.py
```

| Level | Label | Role |
|-------|-------|------|
| L1 | Page gate | Blocks or permits all deploy surfaces |
| L2 | Board quality | Caps deploy-qualified count |
| L3 | Setup evidence | Thesis / timing / R:R |
| L4 | Execution readiness | Broker + bracket + fill realism |
| L5 | Portfolio restraint | Book fit, turnover, crowding |

### Deploy authority tiers

| Tier | Posture | Allowed | Blocked |
|------|---------|---------|---------|
| `allowed` | TRADE / SELECTIVE | Deploy selectively on qualified names | — |
| `paper_only` | PAPER DEPLOY | Paper simulation drafts | No live handoff |
| `pilot_only` | PILOT | Pilot review; half size only when broker+fresh | No full-size deploy |
| `blocked` | MONITOR ONLY | Monitor candidates, watch rules | No sizing, handoff, pilot entry |

### Surface authority modes (16 enforceable surfaces)

| Mode | Surfaces |
|------|----------|
| `deploy_authority` | Dashboard (`today`), Playbook (`signals`), Portfolio |
| `research_only` | Discovery, Dossier, Funds, RS, Command, Strategy Lab, Backtest Lab, Rejections |
| `confirmation_only` | Flow |
| `ops_probe` | Ops, IBKR |
| `suspended` | Guide, Time Travel (replay overlay) |

### Operator block fields (all decision surfaces)

**NOW / WHY / ALLOWED / BLOCKED / VALID CANDIDATES / NEXT**

---

## 5. Intelligence Stack Map

Built as **collapsed-by-default, authority-effect-none** layers. Analytics never auto-loosen deploy thresholds.

| Layer | Commit | Module | Primary surface | Authority |
|-------|--------|--------|-----------------|-----------|
| Persistent learning | `6efee22` | `decision_quality` block, learning mode, forward outcomes | Dashboard | evidence only |
| Opportunity Intelligence | `f3c3223` | `opportunity_quality_engine`, Discovery OI panel | Discovery (+ Dossier lagged context) | research_only |
| Alpha Quality Control Tower | `8daf48d` | `alpha_quality_evaluator`, `alpha_quality_store` | Dashboard (nested) | evidence only |
| Alpha Review Loop | `9cb20f1` | `alpha_review_service`, `alpha_review_store` | Dashboard + Ops diagnostic | advisory, human review queue |
| Threshold Governance | `47480ba` | `threshold_proposal_service`, `threshold_governance_store` | Dashboard + Ops | review only, shadow proposals |

### Learning mode rules

| Signal | Operator interpretation |
|--------|---------------------------|
| `learning_mode: true` | Sample below calibration — no precise lift/ROI |
| `state_label: Learning mode` | Forward outcomes insufficient |
| `overfit_risk: medium/high` | Success labels capped — no green UI |
| Empty intelligence panels | Neutral/warn empty state — never fake success |

### Global intelligence constraints

- `can_auto_loosen: false` globally
- `no_live_changes_from_analytics: true`
- Threshold proposals stay **shadow** until human `approve_shadow`
- Promotion copy always **send to Playbook review** — never deploy

### Layer map (L0–L6)

| Layer | Surface | Authority | Default UI |
|-------|---------|-----------|------------|
| L0 Guide | Guide | suspended | Reference only |
| L1 Page gate | Dashboard | deploy/blocked | Operator block + truth strip |
| L2 Board | Playbook | deploy/research | Qualification + ranked cards |
| L3 Research funnel | Discovery | research_only | OI collapsed · shortlist |
| L4 Structure | Dossier | confirm-only | No standalone permission |
| L5 Book fit | Portfolio | risk review | Capacity before risk |
| L6 Execution probe | IBKR / Ops | ops_probe | Connectivity ≠ capital |

---

## 6. Surface-by-Surface Reference

### Navigation model

| Tier | Tabs / entry points |
|------|---------------------|
| **Primary nav** (top + bottom) | Guide · Dashboard · Playbook · Discovery · Portfolio · Dossier · IBKR · Ops |
| **More menu** (`⋯`) | Funds · Flow · RS · Command · Rejections · Backtest Lab · Strategy Lab |
| **Header overlays** | Time Travel (⏪) · Guide modal (📖) · Export All Pages (PDF) |

### Summary matrix

| Surface | Tab ID | Purpose (1 line) | Authority mode | Intelligence shown |
|---------|--------|------------------|----------------|--------------------|
| **Guide** | `guide` | Operator onboarding & constitution | `suspended` | None (conceptual refs only) |
| **Dashboard** | `today` | Morning command center — regime gate | `deploy_authority` | Decision Quality → Alpha QA → Alpha Review → Threshold Review |
| **Playbook** | `signals` | Ranked candidate board — review path | `deploy_authority` / `research_only` on WAIT | Qualification funnel |
| **Discovery** | `scanners` | Scanner hub / research funnel | `research_only` (always) | OI panel (collapsed) |
| **Dossier** | `dossier` | Per-ticker structure confirmation | `research_only` / confirm-only | Lagged OI badges (RESEARCH ONLY) |
| **Portfolio** | `portfolio` | Book construction & risk review | `deploy_authority` / risk review when unsynced | Regime fit from Dashboard context |
| **Funds** | `funds` | Fund Research Lab — sleeve backtest | `research_only` (always) | Model sleeve evidence |
| **Command** | `command` | Advanced aggregate diagnostic | `research_only` | Suggested rules from Playbook |
| **Agent** | (Command sub) | Monitor copilot for watch rules | monitor-only | Audit journal |
| **Strategy Lab** | `stratlab` | Offline strategy draft + validation | `research_only` | Strategy health window |
| **Flow** | `flow` | Options/dark pool confirmation overlay | `confirmation_only` (always) | Evidence ladder |
| **RS** | `rs` | Relative strength vs SPY — funnel input | `research_only` | RS composite, percentile |
| **Rejections** | `notrade` | Gate failure audit | `research_only` / diagnostic | Blocker taxonomy counts |
| **Ops** | `ops` | Engine health & shadow research | `ops_probe` | Alpha Review + Threshold Governance diagnostics |
| **IBKR** | `ibkr` | Broker connectivity & handoff gate | `ops_probe` | Readiness score, sync quality |
| **Backtest Lab** | `btlab` | Walk-forward research | `research_only` | Stability score, walk-forward verdict |
| **Time Travel** | overlay | Historical replay from Morning Brief | `suspended` | Snapshot review only |
| **More menu** | `⋯` | Secondary nav shell | N/A | N/A |
| **Export All Pages** | header/Ops/FAB | One-click audit export | monitor-only framing | Decision Quality collapsed summary |

---

### Guide (`guide`)

| Field | Detail |
|-------|--------|
| **Purpose** | Operator onboarding, constitution, surface-type reference — not a decision surface |
| **Authority** | `suspended` — "Reference only · Decision surfaces suspended" |
| **Key sections** | Layer 1/2/3 manual, Random Walk principles, surface map, blocked-day examples, three surface types (Deploy / Confirm / Research) |
| **Blocked copy** | Illustrative only; no live runtime truth evaluated |
| **Recent hardening** | Full-page surface + modal shortcut; bilingual nav labels (繁體/EN); UTF-8 repair |
| **Can do** | Read workflow, open Dashboard, reset first-visit flag |
| **Cannot do** | Infer deploy authority, read live board state, size or handoff |

---

### Dashboard (`today`)

| Field | Detail |
|-------|--------|
| **Purpose** | Morning command center — regime gate, operator posture, actionable names when authority open |
| **Authority** | `deploy_authority` (downgrades to `blocked` on WAIT/NO_TRADE, IBKR critical fail, stale brief) |
| **Key sections** | Operator block (NOW/WHY/ALLOWED/BLOCKED/VALID/NEXT), scoped truth strip, mission panel, regime/crisis/index/Buffett/principles strips, Opportunity Status, Actionable Today, Decision Quality (collapsed) |
| **Blocked copy** | "MONITOR ONLY · Deploy blocked"; WAIT board stance; degraded/stale banners; card labels capped review-only |
| **Intelligence** | Decision Quality → Alpha Quality → Alpha Review → Threshold Review (all collapsed, `authority effect: none`) |
| **Recent hardening** | CC OS console collapsed on WAIT; perf smoke; payload snapshot contract; score reconciliation alert |
| **Can do** | Read gate, monitor candidates, create watch rules, open Dossier/Playbook, paper draft when `paper_only`, IBKR handoff when READY |
| **Cannot do** | Deploy when tier `blocked`; treat PILOT as half-size default; override page gate with card rank |

---

### Playbook (`signals`)

| Field | Detail |
|-------|--------|
| **Purpose** | Ranked candidate board — Deploy/Pilot/Watch buckets; review path, not trade ticket |
| **Authority** | `deploy_authority`; WAIT/NO_TRADE → `research_only` |
| **Key sections** | Trust strip + qualification line, authority strip, ranked buckets, filters, rejection clusters, emergency board fallback |
| **Blocked copy** | "NO VALID MONITOR CANDIDATES"; execution gate override; brief fallback warning; filters collapsed when blocked |
| **Intelligence** | Qualification funnel (setup vs deploy-qualified); near-miss upgrade hints |
| **Recent hardening** | `playbookAuthorityViewModel`; banned "taking a Pilot entry"; board mode banners |
| **Can do** | Review ranked names, filter, open Dossier, read blocker themes, monitor upgrade triggers |
| **Cannot do** | Treat card TRADE label as deploy permission when page gate blocked; size from Playbook alone |

---

### Discovery (`scanners`)

| Field | Detail |
|-------|--------|
| **Purpose** | Scanner hub / research funnel — idea generation, not deploy permission |
| **Authority** | `research_only` (always) |
| **Key sections** | Research Funnel panel, decision-intent cards (LEADERS/PULLBACKS/BREAKOUTS/FLOW/NO_TRADE), category tabs, shortlist (max 10), Opportunity Intelligence (collapsed) |
| **Blocked copy** | "Research only · deploy authority unavailable"; warming/degraded banners; FETCH FAILED fallback rows |
| **Intelligence** | OI panel — theme, candidate chips, learning mode; promotion = "send to Playbook review" |
| **Recent hardening** | `discoveryFunnelPanel` viewmodel; scoped run labels; operator NOW/BLOCKER/NEXT chrome |
| **Can do** | Scan, shortlist, promote to Playbook review, open Dossier |
| **Cannot do** | Deploy, size, or treat scan hits as actionable deploy |

---

### Dossier (`dossier`)

| Field | Detail |
|-------|--------|
| **Purpose** | Per-ticker structure confirmation — confirm surface, not standalone deploy verdict |
| **Authority** | `research_only`; confirm-only degraded mode when blocked |
| **Key sections** | Ticker search, sticky command strip, PM 30-second answer, decision stack, candlestick/Nison, structure notes, lagged OI (insider/13F), trade plan (hidden in confirm-only) |
| **Blocked copy** | "Structure Review Only" — no trade plan, no sizing, no handoff; lagged context not used for confirmation |
| **Intelligence** | Lagged OI badges (RESEARCH ONLY); evidence status panel |
| **Recent hardening** | `resolve_dossier_mode` / `dossierRecoveryMode`; sizing blocked display; UTF-8 repair |
| **Can do** | Confirm structure, read thesis/timing/R:R, star/watchlist, open replay |
| **Cannot do** | Standalone deploy; size when confirm-only; treat PM answer verdict as trade ticket |

---

### Portfolio (`portfolio`)

| Field | Detail |
|-------|--------|
| **Purpose** | Book construction and risk review — capacity before adding risk |
| **Authority** | `deploy_authority` for book construction; demotes to risk review when broker unsynced |
| **Key sections** | Operator block, critical risk event (confirmed breach only), broker truth banner, core/satellite bands, risk state, portfolio action priority, positions, heat/correlation |
| **Blocked copy** | "Risk review only"; "Capital actions stay disabled until broker sync"; DEMO SAMPLE watermark; details collapsed when review-only |
| **Intelligence** | Regime fit score, quant cluster hints from Dashboard context |
| **Recent hardening** | `pfRiskVM`; banned demo literals when inactive |
| **Can do** | Reconcile broker, review heat/concentration, trim/add priorities when capital actions enabled |
| **Cannot do** | Deploy new risk when broker local-only or authority blocked; treat demo book as live |

---

### Funds (`funds`)

| Field | Detail |
|-------|--------|
| **Purpose** | Fund Research Lab — sleeve/model backtest context, not live allocation |
| **Authority** | `research_only` (always) |
| **Key sections** | First-screen guardrail, Core index posture (primary), Allocation/execution lock, sleeve research (collapsed), smart money confirmation, comparison table with quarantine lines |
| **Blocked copy** | "research hypothesis only — no live allocation authority"; `allocation_authority: none`; live eligible 0% |
| **Intelligence** | Model sleeve evidence; backtest quarantine summaries |
| **Recent hardening** | Research-only mode hides legacy allocation language; core index posture elevated above sleeves |
| **Can do** | Compare sleeves, read index posture, research fit |
| **Cannot do** | Live allocate, treat backtest as track record, push IBKR from Funds |

---

### Command (`command`) + Agent sub-surface

| Field | Detail |
|-------|--------|
| **Purpose** | Advanced aggregate diagnostic terminal; Agent = monitor copilot for watch rules |
| **Authority** | `research_only` (Command); Agent monitor-only, no sizing/handoff |
| **Key sections** | Agent page default (NOW/WHY/ALLOWED/BLOCKED/RULES/NEXT), macro strip, setup queue, 3-column decision board, intent inbox / rule builder, authority guardrail test |
| **Blocked copy** | "Monitor copilot"; "no deploy authority"; degraded status note |
| **Intelligence** | Suggested rules from Playbook; audit journal |
| **Recent hardening** | Agent collapsed by default; `testAgentAuthorityGuardrail()`; legacy debate collapsed |
| **Can do** | Build monitor rules, run PM routines, fetch decision hub, catalyst calendar |
| **Cannot do** | Deploy gate, decision chips, agent sizing, live handoff |

---

### Strategy Lab (`stratlab`)

| Field | Detail |
|-------|--------|
| **Purpose** | Offline strategy draft + validation — calibrate hypotheses, not deploy |
| **Authority** | `research_only` |
| **Key sections** | Authority card (NOW/WHY/ALLOWED/BLOCKED/NEXT), validation status, draft generator, committee review, per-strategy health (collapsed) |
| **Blocked copy** | "Research strategy hypotheses — no deploy authority"; actions gated by `strategyLabActionEnabled()` |
| **Intelligence** | Strategy health window (n, hit rate, Sharpe) |
| **Recent hardening** | Send to Playbook **review** (not promote); Pine export gated on validation |
| **Can do** | Generate/save draft, refresh context, run validation path |
| **Cannot do** | Deploy override, export Pine until validated, promote when stale |

---

### Flow (`flow`)

| Field | Detail |
|-------|--------|
| **Purpose** | Options/dark pool narrative overlay — confirmation support, not entry trigger |
| **Authority** | `confirmation_only` (always) |
| **Key sections** | Operator block, regime context, calibration card, actionable top 3, watch-for-confirm, bullish/bearish/crowded buckets, live vs mock flow |
| **Blocked copy** | "CONFIRMATION ONLY — no deploy authority from flow"; mock rows "NOT_ACTIONABLE" |
| **Intelligence** | Evidence ladder (stock confirmed or not) |
| **Recent hardening** | Degraded overlay banners; IB handoff only on LIVE actionable |
| **Can do** | Scan flow, open Dossier for confirmation, IB draft on confirmed LIVE |
| **Cannot do** | Standalone entry; treat mock flow as decision color |

---

### RS (`rs`)

| Field | Detail |
|-------|--------|
| **Purpose** | Relative strength vs SPY — Discovery funnel input |
| **Authority** | `research_only` |
| **Key sections** | Regime strip, sector filters, actionable top 3, sector rotation, live leaders table, stale watchlist (NOT actionable) |
| **Blocked copy** | Stale bucket grayed; links to Discovery, not deploy |
| **Intelligence** | RS composite, percentile, acceleration |
| **Recent hardening** | Explicit "Discovery funnel input" header; LIVE vs STALE pills |
| **Can do** | Compute RS universe, open Dossier, feed Discovery shortlist |
| **Cannot do** | Deploy from RS labels; treat stale cache as leaders |

---

### Rejections (`notrade`)

| Field | Detail |
|-------|--------|
| **Purpose** | Gate failure audit — why names were blocked |
| **Authority** | `research_only` / diagnostic |
| **Key sections** | Decision audit intro, top rejection reasons strip, regime/funnel reasons, per-ticker blocker cards with upgrade triggers |
| **Blocked copy** | "Audit shell — API warming up"; "A rejected stock is not automatically bearish" |
| **Intelligence** | Blocker taxonomy counts |
| **Recent hardening** | Degraded fetch banners aligned with Ops copy patterns |
| **Can do** | Audit blockers, open Dossier for context, refresh log |
| **Cannot do** | Override gates; treat rejection as bearish thesis |

---

### Ops (`ops`)

| Field | Detail |
|-------|--------|
| **Purpose** | Engine health, diagnostics, shadow research — runtime truth, not capital permission |
| **Authority** | `ops_probe` |
| **Key sections** | Health (verdict, blockers, recovery runbook, diagnostic last-run lines), Updates/changelog, Error log, Alpha Review diagnostic, Threshold Governance diagnostic (acknowledge/approve_shadow/reject/defer), Export All Pages button |
| **Blocked copy** | "Connectivity ≠ capital permission"; engine conflict vs probe health distinguished |
| **Intelligence** | Alpha Review + Threshold Governance ops panels; last-run timestamps for evaluate/review/propose |
| **Recent hardening** | `cc-release-check.sh` integration; `opsDiagnosticLastRunLines`; export in trust strip |
| **Can do** | Diagnose runtime, read changelog, triage errors, acknowledge threshold proposals, export review PDF |
| **Cannot do** | Grant deploy authority from engine ON alone; auto-apply threshold changes |

---

### IBKR (`ibkr`)

| Field | Detail |
|-------|--------|
| **Purpose** | Broker connectivity, session, brackets — execution handoff gate |
| **Authority** | `ops_probe` |
| **Key sections** | Repair checklist, session state (LOGIN vs READY), execution readiness (critical + workflow rows), bracket status, order form, positions sync, partial mode banner |
| **Blocked copy** | "LOGIN-only ≠ READY"; "Action surface — manual handoff available" in partial mode |
| **Intelligence** | Readiness score, sync quality |
| **Recent hardening** | `ibkrRepairChecklistSteps`; explicit critical vs workflow weight note |
| **Can do** | Connect, verify brackets, handoff when READY, paper mode default |
| **Cannot do** | Treat LOGIN as execution-ready; deploy without bracket alignment |

---

### Backtest Lab (`btlab`)

| Field | Detail |
|-------|--------|
| **Purpose** | Walk-forward research — historical simulation, not deployment evidence |
| **Authority** | `research_only` |
| **Key sections** | Ticker/strategy/period picker, walk-forward windows, attribution ranked, strategy curve console, authority/evidence/action lines |
| **Blocked copy** | "Research shell — API warming up"; authority block states not live track record |
| **Intelligence** | Stability score, walk-forward verdict |
| **Recent hardening** | `btLabAuthorityBlock()` honest framing; degraded shell on warmup |
| **Can do** | Run lab, review walk-forward, read attribution |
| **Cannot do** | Claim live edge; deploy based on backtest alone |

---

### Time Travel (replay overlay)

| Field | Detail |
|-------|--------|
| **Purpose** | Whole-console historical replay from Morning Brief snapshots |
| **Authority** | `suspended` — replay overlay, not live deploy surface |
| **Key sections** | Date picker, Enter replay / Exit live, purple REPLAY banner across all tabs, per-Dossier replay |
| **Blocked copy** | "Replay mode · 歷史快照 · 非即時"; not current truth |
| **Intelligence** | Snapshot review only |
| **Recent hardening** | `ccReplayAsOf` localStorage persistence; `refreshReplaySurfaces()` |
| **Can do** | Review historical board/Dashboard/Playbook as-of date |
| **Cannot do** | Trade on replay data; treat as live authority |

---

### More menu (`⋯`)

| Field | Detail |
|-------|--------|
| **Purpose** | Secondary nav for advanced/diagnostic surfaces without cluttering primary workflow |
| **Contents** | Funds, Flow, RS, Command, Rejections, Backtest Lab, Strategy Lab |
| **Recent hardening** | `hidden_from_primary_nav` for Command; bilingual labels |
| **Can do** | Switch to any secondary surface |
| **Cannot do** | Imply deploy authority from menu placement |

---

### Export All Pages (cross-cutting)

| Field | Detail |
|-------|--------|
| **Purpose** | One-click audit export for PM review / compliance snapshot |
| **Authority framing** | "monitor only · not trade authority" |
| **Output** | PDF via html2pdf + html2canvas (off-screen 794px render); JSON fallback on failure; timestamped `cc-review-YYYY-MM-DDTHHMM.pdf` |
| **Contents** | Issues page + all surfaces summary + Decision Quality collapsed lines + Guide workflow condensed |
| **Fix (`4595e2a`)** | Off-screen `#cc-export-print-root`, enriched snapshot, minimum 80-char guard, JSON fallback |
| **Entry points** | Header PDF button, Ops trust strip, mobile FAB |
| **Can do** | Download review package from header, Ops, or FAB |
| **Cannot do** | Serve as trade authority or live deploy permission |

---

## 7. Export & Release Tooling

### One-command gate

```bash
bash scripts/cc-release-check.sh
```

| Step | Pass condition |
|------|----------------|
| Template drift | `build-cc-template.mjs --check` |
| Runtime contract | `verify-runtime-contract.mjs` |
| Surface authority | `verify-surface-authority-contract.mjs` |
| Authority language | `audit-authority-language.py --fail-on critical` |
| Visible copy | `audit-visible-copy.py --fail-on high` |
| Payload snapshot | `snapshot-today-payload.py` (`may_authorize_deploy: false`) |
| Perf smoke | `perf-smoke-check.py` (optional warn) |
| Pytest suites | authority copy, release audit, export smoke, payload snapshot, surface authority |

### Focused pytest (manual)

```bash
python -m pytest tests/test_cc_release_audit.py tests/test_cc_export_smoke.py tests/test_cc_payload_snapshot.py tests/test_cc_authority_copy_contract.py tests/test_surface_authority_contract.py -q
```

### UTF-8 / visible copy repair

```bash
python3 scripts/audit-visible-copy.py --fail-on high
python3 scripts/repair-visible-copy.py   # if needed
```

### Threshold shadow rules

- Proposals stay **shadow** until human `approve_shadow` on Ops
- Analytics never writes live thresholds
- Ops panel: acknowledge / reject / defer only

### Non-negotiable constraints (preserved)

- Deploy chips only on Dashboard + Playbook
- Banned runtime phrases enforced (e.g. `Deploy gate open`, `TRADE LIST`, `PILOT = half-size`, `Active Fund Manager`)
- Intelligence panels default collapsed; `authority effect: none`
- Export never silent-empty; always monitor-only framing
- Guide / Time Travel / Replay: suspended decision surfaces

---

## 8. Test & Verifier Results

### Automated release gate (HEAD `8b09186`)

| Check | Result at HEAD |
|-------|----------------|
| `cc-release-check.sh` | **VERDICT: RELEASE_READY** |
| Critical failures | **0** |
| Warnings | **0** |
| Template drift | **PASS** |
| Runtime contract verifier | **PASS** — **9/9** release gates |
| Surface authority verifier | **PASS** — **16/16** surfaces enforced |
| Authority language audit | **PASS** — 0 CRITICAL (98 findings: 3 HIGH, rest MEDIUM) |
| Visible copy audit | **PASS** — 0 HIGH (`??` / mojibake) |
| Today payload snapshot | **PASS** — `may_authorize_deploy: false` when gate closed |
| Perf smoke | **PASS** — today_build 2ms, export_html 0ms (all under thresholds) |
| Core inline tests (no pytest) | **PASS** — **18/18** |
| Export smoke | **PASS** — non-empty PDF/JSON fallback |
| Release audit pytest | **PASS** (inline fallback when pytest unavailable) |

### Verifier scorecard

| Suite | Count | Status |
|-------|-------|--------|
| Runtime contract gates | 9/9 | PASS |
| Surface authority contract | 16/16 | PASS |
| Release inline smoke tests | 18/18 | PASS |
| `cc-release-check.sh` steps | 9/9 | PASS |

### Targeted pytest suites (release bundle)

| Suite | Scope |
|-------|-------|
| `test_cc_release_audit.py` | Release gate regressions |
| `test_cc_export_smoke.py` | Export All Pages non-empty output |
| `test_cc_payload_snapshot.py` | Today payload contract keys |
| `test_cc_authority_copy_contract.py` | Banned phrase / authority copy |
| `test_surface_authority_contract.py` | 16-surface contract enforcement |

### Authority leakage sweep (verified)

| Surface | Finding |
|---------|---------|
| Guide | No deploy chips |
| WAIT Dashboard | No green TRADE pills |
| Playbook WAIT | No Send to IBKR when gate blocked |
| Dossier | CONFIRM ONLY / indicative levels |
| Discovery / OI | Research-only ceilings |
| Ranked finalize | In-memory IBKR gate snapshot — no TCP probes in tests |

### Known CI / E2E gaps (not blocking RELEASE_READY on branch)

| Item | Status |
|------|--------|
| `cc-e2e` Playwright (21 specs) on `main` | May be blocked by repo-wide `ruff` lint failures |
| Staging soak sign-off table | Manual execution pending — see [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) |
| Full canonical pytest (229+) in CI | Re-validate after merge to main |

---

## 9. Remaining Limitations & Manual Sign-off Steps

### Manual runtime sign-off (required — automated gates cannot substitute)

Automated sign-off at `8b09186` passed with **Docker down** and no live API. Operators must complete these steps before live promotion:

| Step | Action | Why |
|------|--------|-----|
| **1. Docker** | `docker compose -f docker-compose.dev.yml up -d` (or prod-local stack) | Live `/api/v7/today`, `system_truth`, and `stale_cache` require running API |
| **2. localStorage** | Clear `localStorage.cc_today7_snapshot` (or full site data) before testing | Stale CC hydrate cache can mask fresh gate truth and export content |
| **3. Browser export** | Hard refresh (Cmd+Shift+R) → Export All Pages from header, Ops, or FAB → confirm PDF ≥ 80 chars / JSON fallback | Validates `4595e2a` off-screen render fix in real browser (html2canvas) |
| **4. Live API smoke** | `curl http://localhost:8000/api/v7/today` — confirm `system_truth` + `execution_readiness` present | Offline snapshot omits `stale_cache`; live response required for full truth |
| **5. Optional pytest** | `pip install pytest` then run full canonical bundle | Heavy suites (`test_surface_authority_contract`, `test_release_signoff`) may hang locally; covered by node verifiers + 18/18 inline smoke |

### Before merge to main

- [x] Run `bash scripts/cc-release-check.sh` — **RELEASE_READY** at `8b09186`
- [ ] Run `node scripts/build-cc-template.mjs --check` after any partial edit
- [ ] Export All Pages smoke — header, Ops, FAB; verify timestamp filename; no empty PDF
- [ ] Visual spot-check: no `??` corruption in UI copy
- [ ] Complete manual runtime sign-off table above (Docker + localStorage + browser export)

### Before production 10/10 promotion

- [ ] **Staging soak** — execute [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) §1–§9; complete sign-off table (30+ min WAIT, IBKR READY, route-abort, engine OFF scenarios)
- [ ] **CI E2E** — require 3+ consecutive green `cc-e2e` runs on `main` after lint unblock
- [ ] **Threshold governance** — any shadow proposals require explicit human `approve_shadow`; never auto-apply
- [ ] **Broker truth** — confirm Portfolio capital actions disabled until broker sync on staging

### Operational limitations (by design)

- Intelligence analytics do not grant deploy permission
- Dossier never standalone deploy verdict
- Flow / RS / Discovery never entry triggers
- Time Travel is historical only — exit replay before live action
- PILOT tier requires `pilot_sizing_allowed()` — not automatic half-size
- Export PDF quality depends on browser canvas rendering — always verify in target browser

---

## 10. Operator Quick Reference

### Morning operator sequence (all days)

```
Dashboard → Playbook → Dossier (confirm) → Portfolio (capacity)
  → Discovery / Flow / RS (ideas only)
  → IBKR (handoff only when READY)
  → Ops (if stale / conflict)
```

### Never start from

| Surface | Reason |
|---------|--------|
| Guide | Reference only — no live runtime |
| Strategy Lab | Draft hypotheses — no deploy path |
| Time Travel | Historical replay — not live authority |
| Rejections | Audit only — explains blocks, does not override |

### Blocked day (MONITOR ONLY)

1. **Dashboard** — confirm `MONITOR ONLY · Deploy blocked`; read scoped truth strip
2. **Playbook** — 0 deploy-qualified; review-only labels
3. **Discovery / Flow / RS** — research funnel only; promote to Playbook review
4. **Dossier** — Structure Review Only · 僅結構確認; no trade plan
5. **Portfolio** — risk review only; capital actions disabled if broker unsynced
6. **Ops** — repair stale scopes from runbook

### Blocked-copy reference (canonical operator language)

| Surface | Blocked / degraded copy (EN · 繁體 where shown) |
|---------|--------------------------------------------------|
| **Dashboard** | `MONITOR ONLY · Deploy blocked` · WAIT board stance · degraded/stale banners |
| **Playbook** | `NO VALID MONITOR CANDIDATES` · execution gate override · filters collapsed when blocked |
| **Discovery** | `Research only · deploy authority unavailable` · `send to Playbook review` (never deploy) |
| **Dossier** | `Structure Review Only` · `僅結構確認` · no trade plan / sizing / handoff |
| **Portfolio** | `Risk review only` · `Capital actions stay disabled until broker sync` |
| **Funds** | `research hypothesis only — no live allocation authority` |
| **Flow** | `CONFIRMATION ONLY — no deploy authority from flow` |
| **Strategy Lab** | `Research strategy hypotheses — no deploy authority` |
| **Export** | `monitor only · not trade authority` |
| **Time Travel** | `Replay mode · 歷史快照 · 非即時` |

### Allowed day (Authority Open)

1. **Dashboard** — regime primary; all scopes Fresh or acceptable
2. **Playbook** — filter execution-ready; deploy-qualified count > 0
3. **Dossier** — structure confirmation for top names (still not standalone permission)
4. **Portfolio** — heat, correlation, restraint governor clear
5. **IBKR** — session READY (not LOGIN-only); bracket aligned
6. **Execute** — only after L1–L5 pass; Dashboard + Playbook agree

### Pilot tier reminder

**PILOT ≠ half-size default.** Review Pilot bucket first. Half-size only when `pilot_sizing_allowed()` returns true (broker online, brief/board fresh, pilot-eligible count ≥ 1).

### Release verification command

```bash
bash scripts/cc-release-check.sh
# Expected: VERDICT: RELEASE_READY
```

---

## Appendix — Related documentation

| Document | Purpose |
|----------|---------|
| [CC_README.md](./CC_README.md) | Documentation index |
| [CC_AI_CONTEXT.md](./CC_AI_CONTEXT.md) | Full AI agent context |
| [DAILY_OPERATOR_FLOW.md](./DAILY_OPERATOR_FLOW.md) | Blocked/allowed day flowcharts |
| [CC_SURFACE_RELEASE_STATUS.md](./CC_SURFACE_RELEASE_STATUS.md) | Cross-page render/ownership matrix |
| [CC_RELEASE_SIGNOFF.md](./CC_RELEASE_SIGNOFF.md) | Prior sign-off audit (pre-`8b09186` baseline) |
| [CC_SOAK_STAGING_RUNBOOK.md](./CC_SOAK_STAGING_RUNBOOK.md) | Staging soak procedure |

---

_Report generated for Sprint99 fund productization release. Pair with automated gate output from `scripts/cc-release-check.sh` at deploy time._
