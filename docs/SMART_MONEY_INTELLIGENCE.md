# Smart Money Intelligence — Leader Tracking System (10/10 Spec)

**Product module:** Smart Money Intelligence (SMI)  
**Not:** influencer gossip wall · celebrity list · social feed  
**Is:** signal-weighted, tier-ranked, capital-vs-commentary separated leader system  

**Integrates with:** Dossier → Ownership tab · `GET /api/v7/stock-intel/{ticker}` · existing `conviction` + `edgar` + `sponsor_index`

---

## 1. Design principles (non-negotiable)

| Rule | Implementation |
|------|----------------|
| Separate source types | 6 buckets A–F, never mixed in one list without labels |
| Tier every signal | T1 hard capital → T4 noise |
| Capital ≠ commentary | `capital_backed: bool` on every row |
| Lag visible | `filing_lag`, `freshness`, `actionability` |
| Multi-source confirmation | `confirmed: single \| multi` |
| Theme + ticker | Signals attach to `ticker` AND optional `theme_id` |
| No fake precision | Political/influencer = soft tier max T3 unless filing |

**Page must answer (every stock):**

1. Is this **real money**?  
2. Is it **fresh**?  
3. Is it **conviction** or hedge/noise?  
4. Is it **actionable now**?  
5. Confirmed by price / flow / fundamentals?

---

## 2. Source taxonomy (6 types)

| Code | Name | Examples | Default max tier |
|------|------|----------|------------------|
| `A` | `great_investor` | Dalio, Cohen/Point72, Hohn, Tiger-cub, compounders, activists | T1–T2 |
| `B` | `political_disclosure` | Congressional STOCK Act, public office holdings | T2–T3 |
| `C` | `fund_13f` | Hedge, mutual, concentrated, sector specialist | T1 (add) T4 (stale) |
| `D` | `insider` | CEO/CFO/founder, cluster buy/sell | T1–T2 |
| `E` | `options_flow` | LEAPS, blocks, sweeps, OI clusters | T1–T2 |
| `F` | `thesis_leader` | Aschenbrenner-class thinkers, substack/X **commentators** | T3 max |

**Style tags (orthogonal):** `macro` · `tech_growth` · `activist` · `value` · `momentum` · `event_driven` · `quality` · `sector_specialist`

**Entity kinds:** `person` · `fund` · `institution` · `political_figure` · `commentator`

---

## 3. Signal tier model (ranking engine core)

### 3.1 Tier definitions

| Tier | Label | Examples | Weight in score |
|------|-------|----------|-----------------|
| **T1** | Hard capital | Insider cluster buy; 13F major add (concentrated fund); activist 13D; repeated LEAPS + OI; large disclosed stake ↑ | 1.0 |
| **T2** | Strong proxy | LEAPS + vol; multi PM same theme; institutional ownership ↑ QoQ; sector allocation shift | 0.6 |
| **T3** | Soft | Respected comment, interview, thesis essay, conference mention | 0.25 |
| **T4** | Noise | Random KOL; stale 13F no change; tiny insider; 0DTE flow only | 0.0 (display only) |

### 3.2 Tier assignment rules (deterministic first, AI second)

```python
# Pseudocode — implement in src/services/smart_money_scorer.py

def assign_tier(signal: Signal) -> int:
    if signal.source_type == "insider":
        if signal.cluster_buy and signal.notional_pct_float >= 0.001:
            return 1
        if signal.direction == "buy" and signal.notional_usd >= 100_000:
            return 1 if signal.officer_role in ("CEO", "CFO", "Chair") else 2
        if signal.notional_usd < 25_000:
            return 4
    if signal.source_type == "fund_13f":
        if signal.position_change_pct >= 0.20 and signal.fund_tier == "A":
            return 1
        if signal.position_change_pct >= 0.05:
            return 2
        if signal.filing_age_days > 120 and not signal.qoq_confirmed:
            return 4
        return 2
    if signal.source_type == "options_flow":
        if signal.leaps and signal.oi_change_pct >= 0.15 and signal.grade in ("A", "B"):
            return 1
        if signal.expiry_dte < 14:
            return 4  # speculative
        return 2
    if signal.source_type == "political_disclosure":
        return 3  # never T1 unless major size + recent
    if signal.source_type == "thesis_leader":
        return 3 if signal.capital_backed else 4
    return 3
```

---

## 4. Per-signal field schema (Leader Signal Record)

Every row in **Leader Consensus Matrix** uses:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `signal_id` | string | ✓ | stable hash |
| `leader_id` | string | ✓ | registry key |
| `leader_name` | string | ✓ | display |
| `source_type` | enum A–F | ✓ | taxonomy |
| `entity_kind` | enum | ✓ | person/fund/… |
| `style` | enum[] | ✓ | tags |
| `signal_type` | enum | ✓ | see §4.1 |
| `direction` | `bullish\|bearish\|neutral` | ✓ | |
| `ticker` | string | ✓ | |
| `theme_id` | string? | | `ai_infra`, `semis`, … |
| `tier` | 1–4 | ✓ | |
| `conviction` | 0–100 | ✓ | §5.2 |
| `relevance` | 0–100 | ✓ | stock/theme fit |
| `freshness` | enum | ✓ | `fresh\|aging\|stale` |
| `freshness_days` | int | ✓ | |
| `filing_lag` | enum | ✓ | `low\|medium\|high` |
| `noise_risk` | enum | ✓ | `low\|medium\|high` |
| `actionability` | enum | ✓ | `high\|medium\|low` |
| `capital_backed` | bool | ✓ | |
| `confirmed` | enum | ✓ | `single\|multi\|unconfirmed` |
| `trust_rating` | enum | ✓ | `high\|medium\|low` |
| `reliability_score` | 0–100 | ✓ | leader historical |
| `notional_usd` | float? | | if applicable |
| `evidence` | object | ✓ | filing id, url, snippet |
| `so_what` | string | ✓ | one line ≤120 chars |
| `warnings` | string[] | | lag, hedge, etc. |

### 4.1 `signal_type` enum (granular — not “mentioned NVDA”)

| Value | Capital? | Typical source |
|-------|----------|----------------|
| `insider_buy` | Yes | Form 4 |
| `insider_sell` | Yes | Form 4 |
| `insider_cluster_buy` | Yes | aggregated Form 4 |
| `13f_major_add` | Yes | 13F-HR |
| `13f_trim` | Yes | 13F |
| `13f_exit` | Yes | 13F |
| `activist_entry` | Yes | SC 13D |
| `leaps_accumulation` | Proxy | options |
| `block_call` / `block_put` | Proxy | options |
| `call_sweep_cluster` | Proxy | options |
| `put_hedge_cluster` | Proxy | hedge flag |
| `political_disclosure_buy` | Soft | STOCK Act |
| `thesis_mention` | No | curated feed |
| `public_comment_bullish` | No | media |
| `sector_style_alignment` | No | rules only |

---

## 5. Leader registry (curated — extend `KNOWN_SPONSORS`)

**File:** `config/leader_registry.yaml` (new) + merge into `sponsor_index.py`

### 5.1 Leader record

```yaml
- id: berkshire_hathaway
  name: Berkshire Hathaway
  entity_kind: fund
  source_types: [A, C]
  styles: [quality, value]
  reliability_score: 92
  default_filing_lag: high
  track_capital: true
  aliases: [BERKSHIRE HATHAWAY INC]

- id: steve_cohen_ecosystem
  name: Point72 / S.A.C. ecosystem
  entity_kind: fund
  source_types: [A, C]
  styles: [tech_growth, momentum]
  reliability_score: 78
  default_filing_lag: high
  track_capital: true
  notes: "Filings lag; use 13F not media quotes"

- id: leopold_aschenbrenner
  name: Leopold Aschenbrenner
  entity_kind: commentator
  source_types: [F]
  styles: [macro, tech_growth]
  reliability_score: 55
  default_filing_lag: low
  track_capital: false
  max_tier: 3
```

**Categories to seed (Phase 1):** 15–20 funds from `KNOWN_SPONSORS` + 5 commentators (manual, no scrape) + insider = per-ticker only.

**Political (Phase 2):** separate feed adapter; label `disclosure_lag: high`, never T1.

### 5.2 Leader scorecard (per leader, global)

| Field | Description |
|-------|-------------|
| `historical_hit_rate` | backtest optional Phase 3 |
| `avg_filing_lag_days` | computed |
| `usefulness_score` | PM-weighted 0–100 |
| `capital_vs_commentary_ratio` | % signals with capital |

---

## 6. Score formulas

### 6.1 Freshness

| `freshness_days` | Label |
|------------------|-------|
| ≤ 7 | `fresh` |
| 8–30 | `aging` |
| > 30 | `stale` |

Override: 13F always `filing_lag: high` if `freshness_days` < 45 but filing period end > 90d ago.

### 6.2 Filing lag (by source)

| Source | Default lag |
|--------|-------------|
| insider Form 4 | medium (2–5d) |
| 13F | high (45–90d) |
| political | high |
| options | low |
| thesis | low |

### 6.3 Relevance to stock (0–100)

```text
relevance = 100 if signal.ticker == subject_ticker
           else theme_overlap_score(ticker, signal.theme_id)  # 40–85
```

Theme map: `config/theme_map.yaml` — ticker → themes[] (e.g. NVDA → ai_infra, semis).

### 6.4 Conviction (per signal, 0–100)

```text
conviction = tier_weight(tier) * 40
           + relevance * 0.25
           + min(notional_score, 20)
           + cluster_bonus(0|15)
           + multi_source_bonus(0|10)
cap at 100
```

### 6.5 Stock-level Smart Money Verdict

Aggregate all signals with `relevance >= 50`, `tier <= 3`:

```text
hard_capital_count = count(tier==1, direction==bullish) - count(tier==1, bearish)
soft_count = count(tier==3)
net_tier_score = sum(direction_sign * tier_weight(tier) * conviction / 100)

smart_money_score = clamp(net_tier_score * 10, -100, 100)  # -100..+100

verdict enum:
  confirmed_accumulation   if hard_capital_count >= 2 and net > 0
  possible_accumulation    if hard_capital_count >= 1 OR (tier2>=2 and net>0)
  mixed                    if bullish and bearish hard both >= 1
  distribution             if hard_capital_count <= -2
  no_meaningful_signal     else
```

**Display:** pill + `signal_quality: low|medium|high` from % T1/T2 in bullish set.

### 6.6 Leader consensus summary (matrix footer)

```json
{
  "bullish_leaders": 4,
  "bearish_leaders": 1,
  "hard_capital_confirmations": 2,
  "soft_mentions": 3,
  "net_smart_money_score": 7,
  "signal_quality": "medium-high",
  "warnings": ["13F data ~60d lag", "1 thesis mention without capital"]
}
```

---

## 7. UI structure — Dossier Ownership tab → Smart Money Intelligence

**Rename tab:** `Ownership` → **`Smart Money`** (or split: Ownership | Smart Money)

### 7.1 Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Smart Money Verdict: [Possible Accumulation]  Score +42      │
│ Hard capital: 2 · Soft: 3 · Quality: Medium-High  ⚠ 13F lag │
├─────────────────────────────────────────────────────────────┤
│ Sub-tabs: [Great Investors][Insider][Political][Options][Thesis] │
├─────────────────────────────────────────────────────────────┤
│ (sub-tab content)                                              │
├─────────────────────────────────────────────────────────────┤
│ Leader Consensus Matrix (collapsed ▼ expand default)          │
├─────────────────────────────────────────────────────────────┤
│ Theme Leader Map: AI Infra — 3 leaders adding (drill-down)    │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Sub-tab default vs drill-down

| Sub-tab | Above fold in sub-tab | Drill-down |
|---------|----------------------|------------|
| **Great Investors** | Top 5 rows: name, signal, tier, direction, lag | Full registry matches, 13F history |
| **Insider** | Cluster badge, buy/sell ratio, last 3 trades | Full Form 4 table, quality score |
| **Political** | Warning banner + last disclosure | History, size vs portfolio |
| **Options** | LEAPS flag, skew, flow grade | Strikes, expiry heatmap |
| **Thesis** | Commentators only, T3 max | Source link, disagreement |

### 7.3 Leader Consensus Matrix columns

| Leader | Type | Style | Signal | Dir | Tier | Conv | Fresh | Trust | Capital | Confirmed |
|--------|------|-------|--------|-----|------|------|-------|-------|---------|-----------|

Sort: `tier ASC`, `conviction DESC`, `freshness_days ASC`.

Filter chips: `T1 only` · `Capital-backed` · `Fresh 7d` · `Hide noise`

### 7.4 Trust strip (module-level)

Always visible:

```text
⚠ 13F filings lag 45–90d · Commentary ≠ capital · Options may be hedge · Political disclosures delayed
```

---

## 8. Theme-level leader tracking

### 8.1 Theme registry (`config/theme_map.yaml`)

```yaml
ai_infra:
  label: AI Infrastructure
  tickers: [NVDA, AMD, AVGO, MU, SMCI]
semis:
  label: Semiconductors
  etf: SMH
```

### 8.2 API

`GET /api/v7/smart-money/theme/{theme_id}` → leaders with signals on any theme ticker in last 90d.

**Dossier widget:** “3 leaders adding **AI Infra** theme (not only NVDA)” — click expands theme view.

---

## 9. API design

### 9.1 Stock payload (embed in stock-intel)

`GET /api/v7/stock-intel/{ticker}` → section `smart_money`:

```json
{
  "verdict": "possible_accumulation",
  "smart_money_score": 42,
  "consensus": { },
  "subtabs": {
    "great_investors": [],
    "insider": [],
    "political": [],
    "options": [],
    "thesis": []
  },
  "matrix": [],
  "theme_leaders": [],
  "warnings": []
}
```

### 9.2 Dedicated endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v7/smart-money/{ticker}` | Full SMI payload |
| `GET /api/v7/smart-money/{ticker}/matrix` | Matrix only (light poll) |
| `GET /api/v7/smart-money/theme/{theme_id}` | Theme map |
| `GET /api/v7/smart-money/leaders` | Registry scorecards |
| `POST /api/v7/smart-money/{ticker}/refresh` | Force EDGAR/options refresh |

### 9.3 Data pipeline (compose)

| Sub-tab | Existing | New |
|---------|----------|-----|
| Great Investors | `sponsor_index.KNOWN_SPONSORS`, `lookup_13f` | leader_registry match |
| Insider | `edgar` Form 4, `conviction.insider` | cluster detector |
| Political | — | Phase 2 adapter (manual/CSV) |
| Options | `OptionsFlowRadar`, `conviction.options` | LEAPS classifier |
| Thesis | — | Phase 2 curated entries only |

**Service:** `src/services/smart_money_intelligence.py` — orchestrates, scores, tiers.

---

## 10. Dashboard integration

| Surface | Behavior |
|---------|----------|
| Dossier | Smart Money tab (this spec) |
| Today ranked card | `smart_money_score` badge if \|score\| > 40 |
| Command Board | Import matrix summary to right rail |
| Verify script | Optional `GET smart-money/NVDA` 200 |

---

## 11. AI usage (strictly bounded)

| Allowed | Forbidden |
|---------|-----------|
| Summarize thesis to 1 line | Invent fund positions |
| Detect contradiction in comments | Upgrade T3 → T1 |
| Theme clustering labels | Scrape random X |

**Endpoint:** `POST /api/v7/smart-money/{ticker}/narrative` — input: matrix JSON only; output: `agreement_summary`, `key_risk_one_liner`.

---

## 12. Top 20 highest-impact additions

1. Signal tier engine (T1–T4)  
2. Leader registry YAML + aliases  
3. Leader Consensus Matrix UI  
4. Stock smart money verdict  
5. Capital vs commentary split  
6. Insider cluster detector  
7. 13F sponsor extend (QoQ delta when data available)  
8. LEAPS conviction classifier  
9. Freshness + lag badges on every row  
10. `so_what` one-liner per signal  
11. Multi-source confirmation logic  
12. Theme leader map  
13. Great Investors sub-tab  
14. Options sub-tab (wire live/mock badge)  
15. Trust warning strip  
16. Filter: T1 only / capital-backed  
17. `smart_money` section in stock-intel  
18. Noise filter (hide T4 default off)  
19. Leader scorecard page (settings)  
20. Follow-the-leader backtest (Phase 3)

---

## 13. Top 10 caution / trust rules (show in UI)

1. 13F is quarterly — **not real-time**  
2. Political disclosure — **high lag**, often small size  
3. Influencer bullish ≠ **position**  
4. Options puts may be **hedge**  
5. Insider **sell** often routine (10b5-1)  
6. Tiny insider trades = **T4**  
7. Stale 13F without QoQ change = **noise**  
8. **Crowding** — many funds same name  
9. **Single-source** — don’t treat as confirmed  
10. Past leader performance **≠** future  

---

## 14. Implementation phases

### Phase 1 — Core (MVP 10/10 shell)

- [ ] `leader_registry.yaml` (20 funds + metadata)  
- [ ] `smart_money_scorer.py` tier + verdict  
- [ ] `GET /api/v7/smart-money/{ticker}`  
- [ ] Dossier sub-tabs + matrix + verdict strip  
- [ ] Wire insider + 13F + options from existing conviction/edgar  

### Phase 2 — Depth

- [ ] Insider cluster + transaction table  
- [ ] Theme map + theme API  
- [ ] Political disclosure CSV adapter  
- [ ] Curated thesis_leader entries (manual)  

### Phase 3 — Advanced

- [ ] Follow-the-leader backtest  
- [ ] QoQ 13F position delta (if data source added)  
- [ ] Automated thesis ingest (high bar)  

---

## 15. Acceptance criteria

- [ ] No signal row without `tier`, `capital_backed`, `filing_lag`, `so_what`  
- [ ] Commentators cannot appear as T1  
- [ ] T4 hidden by default  
- [ ] Verdict derivable from matrix (deterministic)  
- [ ] User can answer “real money?” in <5s  
- [ ] Mock options shows provider badge  
- [ ] 13F rows show lag warning  
- [ ] Not a social media feed (no infinite scroll tweets)  

---

## 16. Cross-reference

- Parent page spec: [SINGLE_STOCK_COMMAND_CENTER.md](./SINGLE_STOCK_COMMAND_CENTER.md) — Layer E + Ownership tab  
- Existing code: `src/services/sponsor_index.py`, `src/api/routers/conviction.py`, `src/api/routers/edgar_api.py`

---

*Version 1.0 — Signal-weighted Leader / Smart Money Intelligence — Engineering handoff.*
