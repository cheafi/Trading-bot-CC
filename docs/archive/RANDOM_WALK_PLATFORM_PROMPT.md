# Random Walk Down Wall Street — Clarity Console Engineering Prompt

**Version:** 2026-05-31  
**Usage:** Copy sections into Cursor / Claude / Copilot when extending CC surfaces.  
**Repo anchors:** `src/services/humility_labels.py` · `src/services/cost_adjusted_edge.py` · `src/services/random_walk_guardrails.py` · `src/services/stock_intel.py` · `src/services/decision_truth_model.py` · Guide tab + Dossier in `src/api/templates/index.html`

---

## Mission

Upgrade Clarity Console from **signal theater** to **honest capital deployment discipline** inspired by _A Random Walk Down Wall Street_ and institutional PM practice:

- Markets incorporate information quickly; edge is rare and fragile.
- Raw scores overstate deployability; **net edge after cost** and **portfolio fit** decide.
- Research surfaces **inform**; only gated core surfaces **permit** action.
- Labels express **humility**, not marketing copy.

Do not fake precision. Use proxy heuristics, explicit `model_note`, and consistent vocabulary.

---

## Global principles (constitution — always on)

Wire in **Guide → Random Walk — Global Principles** and reuse in copy reviews:

| #   | Principle                                          | Operator rule                              |
| --- | -------------------------------------------------- | ------------------------------------------ |
| 1   | Markets are noisy in the short run                 | Regime + process > daily tape              |
| 2   | Page-level regime overrides single-name temptation | Board WAIT/NO_TRADE beats card rank        |
| 3   | Research relevance ≠ deploy permission             | Discovery / Flow / Funds / RS = supporting |
| 4   | Cost-adjusted edge > raw signal strength           | Show Raw · Net after cost                  |
| 5   | Portfolio construction > isolated ideas            | Correlation / sector cluster = one bet     |
| 6   | Cash is a valid allocation                         | Patience = active risk mgmt                |
| 7   | Avoid overconfidence in forecasting                | Scenarios + invalidation, not point calls  |
| 8   | Bubble conditions require extra skepticism         | Crowding + extension → discount            |

---

## Humility label vocabulary (unified)

**Module:** `src/services/humility_labels.py`

| Key                                       | Display                                    |
| ----------------------------------------- | ------------------------------------------ |
| `supportive_only`                         | supportive only                            |
| `likely_priced_in`                        | likely priced in                           |
| `evidence_incomplete`                     | evidence incomplete                        |
| `monitoring_only`                         | monitoring only                            |
| `not_enough_advantage_over_passive`       | not enough advantage over passive baseline |
| `research_signal_only`                    | research signal only                       |
| `narrative_rich_evidence_light`           | narrative-rich, evidence-light             |
| `cost_drag_may_erase_weak_edge`           | cost drag may erase weak edge              |
| `high_structure_low_predictive_certainty` | high structure, low predictive certainty   |

**Usage rules:**

- Playbook ranked rows: `guardrail_labels` via `labels_for_playbook_row()` after `enrich_opportunity_row()`.
- Dossier: `random_walk_guardrails.guardrail_labels` from `build_random_walk_guardrails()`.
- Smart money / options: keep `supportive_only` — map to same vocabulary, do not upgrade to TRADE.

---

## Net edge after cost

**Module:** `src/services/cost_adjusted_edge.py` · `compute_net_edge()`

### Formula (0–10 score scale)

```
raw_clamped = clamp(raw_score, 0, 10)
tb = clamp(turnover_burden, 0, 1)  (+0.15 if action ∈ TRADE/BUY/PILOT/SCALE/ADD)
sb = clamp(spread_burden, 0, 1)     (+0.20 if extended; +0.10 if partial_data)
turnover_penalty = tb * 1.2
spread_penalty   = sb * 1.0
net_deploy_score = max(0, raw_clamped - turnover_penalty - spread_penalty)  # 1 dp
weak_edge_after_cost = net_deploy_score < 6.0
display = "Raw X · Net Y after cost"
```

**Surfaces:**

- **Playbook:** `net_edge_display`, `raw_score`, `net_deploy_score` on ranked cards.
- **Dossier:** under thesis quality via `confidence_metrics.net_edge_display` + `cost_realism` section.

Always surface `model_note`: heuristic, not live TCA.

---

## Dossier guardrail fields (anti-illusion)

**Module:** `src/services/random_walk_guardrails.py` · payload key `random_walk_guardrails`

| Field                         | Meaning                                                             |
| ----------------------------- | ------------------------------------------------------------------- |
| `evidence_strength`           | low / low-medium / medium from confluence + why_buy                 |
| `predictive_confidence`       | uncalibrated / very_low / low / moderate from decision confidence % |
| `data_completeness`           | low / medium / high from layer coverage − module errors             |
| `cost_adjusted_expected_edge` | `net_deploy_score`                                                  |
| `guardrail_labels[]`          | humility vocabulary (display strings)                               |

### Four dossier sections (heuristic proxies)

1. **market_efficiency_warning** — RSI extension, chase above entry band, rich narrative + weak confluence.
2. **bubble_crowding_risk** — sector book overlap, RSI + dual MAs, peer crowded leader flag.
3. **cost_realism** — net edge vs 6.0 threshold; meaningful_after_cost boolean.
4. **portfolio_necessity** — `portfolio_fit` label, overlap, sizing context.

**UI:** collapsible **Random Walk guardrails** after Decision stack in Dossier tab.

Do not contradict existing **WAIT gates**, **decision stack**, or **honest funnel** copy.

---

## Surface-by-surface application

### Dashboard

- Lead with board tradeability and regime; never imply ranked #1 = deployable.
- When showing top ranked, prefer net edge line if present on row payload.
- Tie to principles 1–3 and 6 (cash valid on WAIT days).

### Playbook

- Ranked cards: Raw · Net after cost + up to 4 guardrail pills.
- Board WAIT disclaimer unchanged; net edge is additive humility.
- `enrich_opportunity_row()` is the single enrichment hook.

### Dossier (stock-intel)

- `build_stock_intel` → `random_walk_guardrails` + `confidence_metrics` net fields.
- PM 30s answer and decision stack remain primary; guardrails are secondary collapsible.

### Portfolio & Risk

- Phase C: core vs satellite sleeve tags; concentration warnings use principle 5.
- Reuse `portfolio_fit` and sector overlap % — do not duplicate risk math.

### Funds

- Phase D: fund selector as **passive baseline** comparator; label active picks that fail `not_enough_advantage_over_passive`.

### Risk framework

- Phase D: map bubble layer to regime + VIX/crowding dashboard strip.
- CRO view: net edge distribution across book, not raw score heatmap.

---

## Core + satellite (Phase C — not yet full)

- **Core:** index-like, risk-budgeted, low turnover — deploy only on high net edge + execution_ready.
- **Satellite:** tactical, size-capped, explicit kill rules.
- UI: sleeve badge on playbook rows and dossier header; portfolio tab shows sleeve weights.

---

## Active vs passive baseline (Phase C–D)

- Display passive benchmark (e.g. SPY total return / factor exposure) as **hurdle**.
- If `net_deploy_score < 6` or `not_enough_advantage_over_passive` label → default stance = hold passive / cash.
- Funds tab: compare manager alpha after fee drag (heuristic fee bps input).

---

## Bubble / crowding layer (Phase D — partial in Sprint B)

**Sprint B (done):** dossier `bubble_crowding_risk` proxy.  
**Phase D (remaining):** dashboard sector heatmap, playbook sector cluster rejection, funds flow crowding score.

Signals: RSI > 70, sector_weight > 30%, extended above entry, narrative density, mock options hype.

---

## Phased roadmap (Phases 1–8)

| Phase | Name                            | Scope                                   | Status       |
| ----- | ------------------------------- | --------------------------------------- | ------------ |
| **1** | Constitution doc + vocabulary   | This prompt, `humility_labels.py`       | ✅           |
| **2** | Guide + global principles UI    | Guide tab 8 principles                  | ✅           |
| **3** | Net edge (Playbook + Dossier)   | `cost_adjusted_edge.py`, enrich + intel | ✅           |
| **4** | Dossier guardrails + 4 sections | `random_walk_guardrails.py`, dossier UI | ✅           |
| **5** | Core + satellite portfolio      | Portfolio tab sleeves, sizing policy    | 🔲 Phase C   |
| **6** | Active vs passive baseline      | Benchmark hurdle, funds compare         | 🔲 Phase C–D |
| **7** | Bubble / crowding full layer    | Cross-surface heatmap + gates           | 🔲 Phase D   |
| **8** | Risk framework integration      | CRO metrics, book-level net edge        | 🔲 Phase D   |

---

## Implementation discipline

1. **Minimal diffs** — extend `decision_truth_model`, `stock_intel`, Alpine dossier/playbook; no page rewrites.
2. **English** in code/comments; UI strings may be bilingual in docs only.
3. **Tests** — `tests/test_random_walk_integration.py` for `compute_net_edge` and guardrail builder.
4. **No commits** unless operator asks.
5. **Verify:** `pytest tests/test_random_walk_integration.py -q` after changes.
6. **Honesty** — every new number needs `model_note` or label explaining proxy nature.

---

## Agent starter prompt (copy below)

```
You are extending Clarity Console Random Walk discipline.

Read: docs/RANDOM_WALK_PLATFORM_PROMPT.md
Code: humility_labels.py, cost_adjusted_edge.py, random_walk_guardrails.py

Before adding UI scores:
- Does net edge use compute_net_edge()?
- Do labels use HUMILITY_LABELS keys?
- Does copy respect board WAIT and decision_stack?

Next sprint priority: Phase 5 core+satellite OR Phase 7 bubble layer per user choice.
```

---

## 中文摘要（bilingual-friendly）

- **随机漫步原则：** 短期噪音大、页面门禁优先、研究≠下单、成本后净优势、组合>个股、现金有效、预测谦逊、泡沫警惕。
- **谦卑标签：** 九条统一词汇，Playbook 与 Dossier 共用。
- **净优势：** Raw 分 − 换手惩罚 − 价差惩罚 = Net 分（启发式，非真实 TCA）。
- **Dossier 四块：** 定价效率警告、泡沫拥挤、成本现实、组合必要性。
