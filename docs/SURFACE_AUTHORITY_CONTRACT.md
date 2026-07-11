# Surface Authority Contract

**16 operator surfaces** — enforceable per-surface law.  
**SSOT:** `src/services/surface_authority_contract.py`  
**Related:** [OPERATOR_DECISION_OS.md](./OPERATOR_DECISION_OS.md), [DAILY_OPERATOR_FLOW.md](./DAILY_OPERATOR_FLOW.md)

---

## Global Rules

| Rule | Enforcement |
|------|-------------|
| Research ≠ deploy permission | All research surfaces |
| Deploy chips only on Dashboard + Playbook | `surface_shows_decision_chips()` |
| Guide suspends decision language | `is_decision_surface_suspended('guide')` |
| Scoped freshness labels | `shellTruthViewModel` / `typed_freshness_display` |
| PILOT ≠ half-size default | `pilot_sizing_allowed()` gate |

### Global Banned Phrases (runtime)

Must not appear in live template bindings unless whitelisted:

`TRADE LIST`, `decision card`, `PILOT = half-size`, `taking a Pilot entry`, `brief fallback`, `Deploy gate open`, `BOARD POSTURE TRADE`, `Current: TRADE`, `Active Fund Manager`, `Max capital band`, `Test deploy override`, `ENGINE undefined`, `DATA FRESH`, `DATA STALE`, `Freshness: live`, `ENGINE ON`, `ENGINE UNKNOWN`, `actionable in Discovery`, `Active sleeves`, `Seed Demo Book`, `Closed-Trade Ledger`, `CRITICAL RISK EVENT`, `Method Not Allowed`

### Whitelist Exceptions

- Test fixtures and sanitizer replacement maps (`removeTradeLanguageWhenBlocked`)
- `LEGACY_BANNED_DO_NOT_RENDER` comments
- Guide illustrative sections marked `Illustrative examples only`
- Explicit legacy anti-pattern documentation sections

---

## Per-Surface Contracts

### 1. Guide (`guide`)

| Field | Value |
|-------|-------|
| Tab ID | `guide` |
| Label | Guide |
| Surface mode | `guide_reference` |
| Authority | `suspended` |
| Source helper | `guideModeStrip` |
| Viewmodel | `guide_mode_strip` |

**Allowed:** reference docs, illustrative examples, operator checklist  
**Blocked:** live deploy authority, runtime truth, board decision chips  
**Banned:** TRADE LIST, decision card, pilot half-size  
**Collapsed:** Layer 3 Reference Manual

---

### 2. Dashboard (`today`)

| Field | Value |
|-------|-------|
| Tab ID | `today` |
| Label | Dashboard |
| Surface mode | `dashboard_core` |
| Authority | `deploy_authority` (downgrades to `blocked`) |
| Source helper | `build_operator_block` |
| Viewmodel | `dashboardOperatorView` |

**Allowed:** regime gate, operator block, deploy chips when fetch OK  
**Blocked:** sizing when tier blocked; raw `today7.tradeability` in trust strip  
**Banned:** Deploy gate open, Current: TRADE, BOARD POSTURE TRADE

---

### 3. Playbook (`signals` → `playbook`)

| Field | Value |
|-------|-------|
| Tab ID | `signals` |
| Label | Playbook |
| Surface mode | `playbook_core` |
| Authority | `deploy_authority` (WAIT → `research_only`) |
| Source helper | `playbookAuthorityViewModel` |
| Viewmodel | `playbookOperatorView` |

**Allowed:** ranked board, qualification via viewmodel, pilot review  
**Blocked:** deploy on WAIT/NO_TRADE; raw regime bindings  
**Banned:** Deploy gate open, taking a Pilot entry, PILOT = half-size

---

### 4. Discovery (`scanners` → `discovery`)

| Field | Value |
|-------|-------|
| Tab ID | `scanners` |
| Label | Discovery |
| Surface mode | `discovery_research` |
| Authority | `research_only` |
| Source helper | `build_research_surface_block` |
| Viewmodel | `discoveryFunnelPanel` |

**Allowed:** scanner funnel, scoped run label, promote to Playbook  
**Blocked:** actionable deploy copy, unscoped freshness  
**Banned:** Freshness: live, brief fallback, ENGINE ON, actionable in Discovery

---

### 5. Dossier (`dossier`)

| Field | Value |
|-------|-------|
| Tab ID | `dossier` |
| Label | Dossier |
| Surface mode | `dossier_research` |
| Authority | `research_only` |
| Source helper | `resolve_dossier_mode` |
| Viewmodel | `dossierRecoveryMode` |

**Allowed:** structure confirmation, ticker chip, confirm-only degraded mode  
**Blocked:** standalone deploy; trade plan in confirm-only; decision card framing  
**Banned:** decision card  
**Collapsed:** trade plan when confirm-only; lagged context

---

### 6. Portfolio (`portfolio`)

| Field | Value |
|-------|-------|
| Tab ID | `portfolio` |
| Label | Portfolio |
| Surface mode | `portfolio_manual` |
| Authority | `deploy_authority` (book construction) |
| Source helper | `build_portfolio_risk_view_model` |
| Viewmodel | `pfRiskVM` |

**Allowed:** book construction, risk hierarchy, broker truth banner  
**Blocked:** demo tools default; critical risk literal when inactive  
**Banned:** Active sleeves, Seed Demo Book, Closed-Trade Ledger, CRITICAL RISK EVENT

---

### 7. Strategy Lab (`stratlab`)

| Field | Value |
|-------|-------|
| Tab ID | `stratlab` |
| Label | Strategy Lab |
| Surface mode | `strategy_lab_research` |
| Authority | `research_only` |
| Source helper | `build_strategy_lab_page_state` |
| Viewmodel | `strategyLabPageState` |

**Allowed:** offline draft, validation path, committee review  
**Blocked:** deploy; Pine export until validation; Playbook promotion when stale  
**Banned:** Test deploy override, Deploy gate open

---

### 8. Time Travel (replay overlay)

| Field | Value |
|-------|-------|
| Tab ID | — (modal/banner) |
| Label | Time Travel |
| Surface mode | `replay_overlay` |
| Authority | `suspended` |
| Source helper | `replayModeActive` |
| Viewmodel | `ccReplayAsOf` |

**Allowed:** historical replay, snapshot review  
**Blocked:** live deploy; treating replay as current truth  
**Banned:** Deploy gate open, Current: TRADE

---

### 9. Funds (`funds`)

| Field | Value |
|-------|-------|
| Tab ID | `funds` |
| Authority | `research_only` |
| Surface mode | `funds_research` |
| Source helper | `build_research_surface_block` |

**Allowed:** sleeve/model evidence  
**Blocked:** live allocation authority

---

### 10. Flow (`flow`)

| Field | Value |
|-------|-------|
| Tab ID | `flow` |
| Authority | `confirmation_only` |
| Surface mode | `flow_supporting` |
| Source helper | `build_research_surface_block` |

**Allowed:** narrative overlay  
**Blocked:** standalone entry trigger

---

### 11. RS (`rs`)

| Field | Value |
|-------|-------|
| Tab ID | `rs` |
| Authority | `research_only` |
| Surface mode | `rs_supporting` |
| Source helper | `build_research_surface_block` |

**Allowed:** funnel input  
**Blocked:** deploy authority

---

### 12. Command (`command`) — includes Agent sub-surface

| Field | Value |
|-------|-------|
| Tab ID | `command` |
| Authority | `research_only` |
| Surface mode | `command_research` |
| Source helper | `build_research_surface_block` |
| Viewmodel | `agent-page-default` |

**Allowed:** advanced aggregate diagnostic; Agent monitor rules (sub-surface)  
**Blocked:** deploy gate, decision chips, agent sizing/handoff  
**Banned:** Active Fund Manager, Deploy gate open  
**Collapsed:** agent-debate-legacy

---

### 13. Rejections (`notrade`)

| Field | Value |
|-------|-------|
| Tab ID | `notrade` |
| Authority | `research_only` |
| Surface mode | `rejections_diagnostic` |
| Source helper | `build_header_summary` |

**Allowed:** gate failure audit  
**Blocked:** deploy permission

---

### 14. Ops (`ops`)

| Field | Value |
|-------|-------|
| Tab ID | `ops` |
| Authority | `ops_probe` |
| Surface mode | `ops_diagnostic` |
| Source helper | `resolve_engine_state` |
| Viewmodel | `shellTruthViewModel` |

**Allowed:** engine health, probes, shadow research  
**Blocked:** capital permission from runtime alone  
**Banned:** ENGINE ON, ENGINE UNKNOWN in helpers

---

### 15. IBKR (`ibkr`)

| Field | Value |
|-------|-------|
| Tab ID | `ibkr` |
| Authority | `ops_probe` |
| Surface mode | `ibkr_execution` |
| Source helper | `build_header_summary` |

**Allowed:** connectivity, session, brackets  
**Blocked:** LOGIN-only as READY

---

### 16. Backtest Lab (`btlab`)

| Field | Value |
|-------|-------|
| Tab ID | `btlab` |
| Authority | `research_only` |
| Surface mode | `backtest_research` |
| Source helper | `build_header_summary` |

**Allowed:** walk-forward research  
**Blocked:** deployment authority, live track record claims

---

## Tab ID Aliases

| UI tab id | Canonical key |
|-----------|---------------|
| `signals` | `playbook` |
| `scanners` | `discovery` |
| `stock-intel` | `dossier` |
| `rejections` | `notrade` |
| `backtest` | `btlab` |

---

## Release Enforcement

```bash
bash scripts/cc-release-check.sh
python3 scripts/audit-authority-language.py --fail-on critical
python3 scripts/audit-visible-copy.py --fail-on high
```

- Authority language audit scans templates + service payload builders for forbidden deploy/trade phrases outside approved contexts.
- Visible copy audit flags `??`, mojibake, and corrupted UI prefixes.
- Export All Pages must produce non-empty degraded fallback — never silent empty PDF.
- Intelligence panels (Decision Quality, OI, Threshold Review) default **collapsed**; learning mode is neutral, not success.
