# Playbook / Clarity Console — 10/10 Decision Surface Spec

**Surfaces:** Dashboard (`today7`) · Playbook / Signals tab (`tab==='signals'`, `rankedOpps`)  
**API:** `GET /api/v7/today` · `GET /api/v7/playbook/ranked` · fallbacks (scanner, brief)  
**Review basis:** External institutional PDF review + **observed codebase gaps**

**Overall today:** ~7/10 prototype — strong skeleton, weak differentiation + trust labels.

---

## 1. Verdict alignment (review vs code)

| Review finding | Observed in repo | Root cause |
|----------------|------------------|------------|
| Repeated cards / template feel | `thesis 70 / timing 50 / R:R 3.0` patterns | Brief fallback + default `invalidation` string |
| **UNKNOWN UNKNOWN** on cards | `playbook.py` L326–327 | `_brief_ranked_fallback` sets `stage: "UNKNOWN"`, `leader: "UNKNOWN"` |
| Weak top summary | `TOP IDEAS —`, `As-of: —` | Header not wired to decisive `best_action` object |
| Confidence without calibration | `final_conf` everywhere | Only strategy-health footer explains raw model |
| Fund α strip decorative | `pmStrip.funds` +α% | Not tied to ranked ideas / deploy state |
| WATCH/AVOID thin why | Fields exist but empty on fallback | `why_not`, `upgrade_trigger` not in fallback row |
| Good: R:R, action tiers, IBKR send | Present in UI | Keep |

**10/10 goal (one question):**

> What should I do with capital **now**, why **this** idea, why **now**, how much to trust it, and what would **change** the decision?

---

## 2. Architecture — three layers

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 0: Best Action Now (sticky — NEW)                      │
├─────────────────────────────────────────────────────────────┤
│ LAYER 1: Capital & Sleeve Context (fund strip — REDESIGN)    │
├─────────────────────────────────────────────────────────────┤
│ LAYER 2: Ranked Opportunity Board (cards — ENRICH)         │
├─────────────────────────────────────────────────────────────┤
│ LAYER 3: Evidence Footer (strategy health — keep, link up)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 0 — Best Action Now panel

### 3.1 Fields (API: `today.best_action` + `playbook/ranked` meta)

| Field | Example |
|-------|---------|
| `capital_stance` | `deploy_selectively` \| `hold_cash` \| `reduce_risk` |
| `stance_one_liner` | "UPTREND but WAIT — selective entries only" |
| `best_trade_now` | `{ ticker: QCOM, action: TRADE_NOW, conf: 0.63 }` |
| `best_watch_upgrade` | `{ ticker: AMD, trigger: "reclaim $X on volume" }` |
| `best_avoid_now` | `{ ticker: MSFT, avoid_reason: overextended }` |
| `evidence_quality` | `medium` \| `low` \| `high` |
| `evidence_label` | `Raw model · Limited sample` |
| `execution_readiness` | `{ mode: paper, ibkr_connected: false, bracket_ready: true }` |
| `data_freshness` | `FRESH` \| `STALE` |
| `as_of` | ISO timestamp |

### 3.2 UI placement

- **Dashboard:** expand KPI row → full-width card above top-ranked list  
- **Playbook tab:** duplicate strip under trust-strip (same payload)

### 3.3 Derivation rules (backend)

```python
# src/services/best_action.py (NEW)

capital_stance = map_tradeability(regime.tradeability)  # WAIT → deploy_selectively

best_trade = first(opportunities where action in (TRADE, TRADE_NOW, BUY))

best_watch_upgrade = first(WATCH where upgrade_trigger is not None)

best_avoid = first(AVOID or NO_TRADE with avoid_reason)

evidence_quality = min(data_conf) across top 5 + calibration_state
```

---

## 4. Layer 1 — Sleeve / fund strip (redesign)

**Replace:** Leader +97%α optics-only strip.

### 4.1 New block: `strongest_sleeve_now`

| Field | Purpose |
|-------|---------|
| `sleeve_id` | leader \| balanced \| tactical |
| `regime_fit` | high \| medium \| low |
| `deploy_state` | deploy \| reduce \| paused |
| `live_sample_n` | closed trades count |
| `hit_rate_20` | % |
| `last_rebalance` | date |
| `ideas_from_sleeve` | tickers[] currently in ranked book |
| `curve_spark` | last 20 points (optional) |

### 4.2 UI copy

```text
Strongest sleeve now: Leader · Regime fit: High · Deploy · n=12 trades · 3 ideas from this sleeve
```

**Link:** click sleeve → filter ranked cards `sleeve_source=leader`.

---

## 5. Layer 2 — Opportunity card schema (enriched)

### 5.1 Action taxonomy (10/10)

| Legacy | New enum | Display |
|--------|----------|---------|
| TRADE | `TRADE_NOW` | TRADE NOW |
| — | `BUY_PULLBACK` | BUY PULLBACK |
| LEADER | `LEADER_MONITOR` | LEADER / MONITOR |
| WATCH | `WATCH_TRIGGER` | WATCH FOR TRIGGER |
| AVOID | `AVOID_NOW` | AVOID NOW |
| NO_TRADE | `DO_NOT_TOUCH` | DO NOT TOUCH |

Map in API; UI shows new labels; filters updated.

### 5.2 Required narrative block (every card)

| Field | Max | Rule |
|-------|-----|------|
| `why_now` | 120 chars | Ticker-specific; **reject** generic template |
| `why_not_perfect` | 120 chars | Required if action ≠ TRADE_NOW |
| `upgrade_trigger` | 120 chars | Required if WATCH_* |
| `invalidation` | 120 chars | Price level + regime clause |
| `avoid_reason` | enum + detail | Required if AVOID_* |

**Avoid reason enum:** `overextended` · `poor_timing` · `crowded` · `weak_rr` · `regime_mismatch` · `low_evidence` · `earnings_risk`

### 5.3 Evidence quality badge (per card)

| Badge | When |
|-------|------|
| `live_tested` | ≥5 closed trades same setup |
| `paper_only` | dry_run engine |
| `model_only` | fallback / no live validation |
| `low_sample` | calibration n < 20 |
| `fresh_today` | data_freshness < 4h |
| `stale` | data_freshness > 8h |

Show next to `Conf XX%`: **`Conf 60% · Model-only`**

### 5.4 Confidence calibration label

| Label | Condition |
|-------|-----------|
| `Calibrated` | bucket Brier ok |
| `Limited sample` | n < 30 |
| `Raw model output` | default |
| `No live validation` | paper + zero closes |

### 5.5 Portfolio context (top 10 cards)

| Field | Example |
|-------|---------|
| `theme_cluster` | semis |
| `correlation_warning` | "Overlaps NVDA/AMD/AVGO — 3/5 book" |
| `sleeve_source` | leader |
| `duplicate_exposure` | bool |

### 5.6 Why this over that (top 5 only)

Already partially in API as `runner_up` — **require** for rank ≤5:

```json
"runner_up": {
  "ticker": "AMD",
  "reason": "QCOM > AMD: cleaner entry, stronger timing (0.71 vs 0.52)"
}
```

### 5.7 State transition monitor

| Field | Example |
|-------|---------|
| `from_action` | WATCH_TRIGGER |
| `to_action` | TRADE_NOW |
| `trigger_condition` | "Close above $189.58 on 1.5× volume" |
| `countdown` | earnings D-3 |

### 5.8 Kill UNKNOWN (critical fix)

**File:** `src/api/routers/playbook.py` `_brief_ranked_fallback`

| Before | After |
|--------|-------|
| `stage: "UNKNOWN"` | `stage: null` + UI hide |
| `leader: "UNKNOWN"` | `leader_status: null` or `"Unclassified"` |

**UI rule:** `index.html` — never render raw `UNKNOWN`; use `x-show` on truthy meaningful values.

```javascript
// display helper
function displayMeta(val, fallback) {
  if (!val || val === 'UNKNOWN' || val === 'unknown') return null;
  return val;
}
```

### 5.9 Differentiation guard (anti-template)

Backend validator `src/services/opportunity_copy.py`:

- Reject `why_now` if identical across >3 tickers in same batch  
- Reject default invalidation string unless price-interpolated  
- Inject ticker-specific tokens: RS rank, extension %, peer name from `runner_up`

---

## 6. API changes

### 6.1 Extend `GET /api/v7/playbook/ranked`

Add top-level:

```json
{
  "best_action": { },
  "sleeve_context": { },
  "calibration": { "state": "raw_model", "n_closed": 0 },
  "opportunities": [ ]
}
```

### 6.2 Extend `GET /api/v7/today`

Mirror `best_action` + `sleeve_context` for Dashboard header.

### 6.3 New aggregate (optional)

`GET /api/v7/playbook/board` — today + ranked + calibration in one call (reduce 503).

---

## 7. UI file changes

| File | Changes |
|------|---------|
| `src/api/templates/index.html` | Best Action Now card; UNKNOWN guard; evidence badges; expanded action labels; sleeve strip |
| `src/api/routers/playbook.py` | Enriched rows; fix fallback; best_action builder |
| `src/services/best_action.py` | **NEW** |
| `src/services/opportunity_copy.py` | **NEW** validation |
| `tests/test_playbook_ranked.py` | no UNKNOWN; required fields by action |

---

## 8. IBKR / execution (strengthen)

Near **Send to IBKR** on each TRADE card:

| Indicator | Source |
|-----------|--------|
| Broker connected | `cc_status.ibkr_connected` |
| Paper / Live | `cc_status.mode` |
| Bracket ready | entry+stop+target all present |
| Handoff integrity | order payload checksum |

Disable send when: not connected · missing stop · earnings blackout · NO_TRADE regime.

---

## 9. Smart money overlay (supporting — not primary)

Link to [SMART_MONEY_INTELLIGENCE.md](./SMART_MONEY_INTELLIGENCE.md):

- Small pill on card: `Smart $: Possible accumulation`  
- Drill → Dossier Smart Money tab  
- **Never** upgrade action tier from influencer alone (max T3)

---

## 10. Top 15 upgrades → implementation map

| # | Upgrade | Priority | Sprint |
|---|---------|----------|--------|
| 1 | Best Action Now panel | P0 | 1 |
| 2 | Remove/replace UNKNOWN | P0 | 1 |
| 3 | why_now / why_not / upgrade / invalidation | P0 | 1 |
| 4 | Evidence quality badge | P0 | 1 |
| 5 | Calibration label on conf | P0 | 1 |
| 6 | Sleeve block w/ regime fit | P1 | 2 |
| 7 | Action taxonomy 6-way | P1 | 2 |
| 8 | avoid_reason enum | P1 | 2 |
| 9 | State transition monitor | P1 | 2 |
| 10 | why-this-over-that top 5 | P1 | 2 |
| 11 | Portfolio overlap warning | P2 | 2 |
| 12 | IBKR readiness on send | P1 | 2 |
| 13 | Hit rate / curve on sleeve | P2 | 3 |
| 14 | Smart money pill | P2 | 3 |
| 15 | Anti-template copy validator | P1 | 2 |

---

## 11. Acceptance criteria (10/10 sign-off)

- [ ] User answers capital stance in **<5 seconds** from header  
- [ ] Zero visible `UNKNOWN` on Playbook cards  
- [ ] Top TRADE card has unique `why_now` (≠ other tickers)  
- [ ] Every WATCH has `upgrade_trigger`; every AVOID has `avoid_reason`  
- [ ] Confidence shows calibration state on card  
- [ ] Fund strip shows deploy/fit/sample — not only α%  
- [ ] Send IBKR disabled with explicit reason when blocked  
- [ ] Fallback brief shows `source: brief_fallback` + degraded badges  
- [ ] Top 3 have `runner_up` comparison  

---

## 12. Cursor implementation prompt (paste-ready)

```text
Upgrade Playbook / Dashboard to 10/10 institutional decision surface per docs/PLAYBOOK_10_10_SPEC.md.

P0:
1. Add src/services/best_action.py — build best_action from ranked + regime
2. Extend GET /api/v7/playbook/ranked and /api/v7/today with best_action, sleeve_context, calibration
3. Fix _brief_ranked_fallback: never emit stage/leader "UNKNOWN"; null + varied why_now/invalidation
4. Add opportunity_copy validator — block duplicate why_now across batch
5. index.html: Best Action Now sticky card on Dashboard + Playbook
6. index.html: evidence badge + calibration label next to Conf %
7. index.html: hide UNKNOWN meta; expand action taxonomy labels

P1:
8. Redesign pmStrip → strongest_sleeve_now with deploy/fit/sample/ideas_from_sleeve
9. Card fields: why_not_perfect, upgrade_trigger, avoid_reason enum, state_transition
10. runner_up required for rank <= 5
11. IBKR send gate with readiness chips

Tests: tests/test_playbook_ranked.py — assert no UNKNOWN in JSON; best_action present when opportunities exist.

Do not add social feed. Smart money = optional pill linking to Dossier per SMART_MONEY_INTELLIGENCE.md.
```

---

## 13. Cantonese gap checklist（逐項 — 交 developer）

| 項目 | 現狀 | 10/10 做法 |
|------|------|------------|
| 頂部摘要 | REGIME · WAIT，TOP IDEAS — | **Best Action Now** 一行講晒 deploy/最佳 trade/避開邊隻 |
| UNKNOWN | brief fallback 寫死 | **後端唔出、前端唔顯示** |
| 卡片重複 | 同一 invalidation / conf 模板 | **每隻股獨立 why_now** + validator |
| 信心數字 | 得個 % | 加 **Model-only / Calibrated / Low sample** |
| Fund α | 靓但唔知點用 | 改 **而家最强 sleeve + deploy 狀態 + 邊幾隻 idea 來自呢個 sleeve** |
| WATCH | 得 label | 加 **upgrade_trigger**（幾時升級做 TRADE） |
| AVOID | 得 label | 加 **avoid_reason**（overextended / crowded…） |
| 同業比較 | runner_up 有但未強制 | **Top 5 必有**「點解唔揀 AMD」 |
| 組合風險 | 無 | **semis 扎堆警告** |
| IBKR | 有 send | 加 **connected / paper / bracket ready** |
| 監控 | 靜態 | **WATCH→TRADE 條件** |
| Smart money | 無 | **次要 pill**，唔主導 action |

---

## 14. Cross-references

- Single stock depth: [SINGLE_STOCK_COMMAND_CENTER.md](./SINGLE_STOCK_COMMAND_CENTER.md)  
- Smart money: [SMART_MONEY_INTELLIGENCE.md](./SMART_MONEY_INTELLIGENCE.md)  
- Existing ranked UI: `index.html` ~L1421–1570  
- Fallback bug: `playbook.py` `_brief_ranked_fallback` L326–327  

---

*Version 1.0 — Playbook 10/10 — Engineering handoff.*
