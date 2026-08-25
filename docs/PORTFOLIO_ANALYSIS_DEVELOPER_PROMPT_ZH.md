# Portfolio Analysis Page — 超專業 Developer Prompt（中文版 · 可直接 copy）

**目標：** 由「豐富 backtest report」→ **allocator / PM 一開就知點做** 嘅 portfolio decision console  
**現況：** ~7.8/10 research screen；本輪已加 `GET /api/v7/portfolio-decision` + Portfolio tab 決策層 baseline  
**10/10 標準：** 30 秒答完：deploy? rebalance? trim/add? risk rising? IBKR ready?

---

## 頁面層級（Hierarchy — 必守）

| 層級 | 內容 | 禁止 |
|------|------|------|
| 1 頂部 | **What to do now** | 唔好放歷史 heatmap 在頂 |
| 2 中部 | **Why** — regime fit, attribution, benchmark verdict | |
| 3 下半 | **Evidence** — curves, heatmaps, comparison tables | |
| 4 底部 | **Deep drill** — trade log, param compare | |

---

## 一、Portfolio Decision Summary（必加 · 已 baseline）

### 頂部 Allocator Decision Summary 必須顯示

| 欄位 | API 路徑 |
|------|----------|
| Stance: Deploy / Hold / Rebalance / Reduce / Pause | `allocator_summary.stance` |
| Best allocation model | `allocator_summary.best_allocation_model` |
| Last rebalance | `allocator_summary.last_rebalance_date` |
| Risk regime | `allocator_summary.current_risk_regime` |
| Rebalance suggested? | `allocator_summary.rebalance_suggested` |
| Most overweight / underweight | `most_overweight`, `most_underweight` |
| Largest risk contributor | `largest_risk_contributor` |
| Benchmark verdict | `benchmark_relative_verdict` |
| Recommended action | `recommended_action` |
| Confidence / evidence | `confidence`, `evidence_quality` |

**API：** `GET /api/v7/portfolio-decision`  
**Service：** `src/services/portfolio_decision_console.py`  
**UI：** `index.html` tab `portfolio` — 綠框「Portfolio decision」

### 驗收

```bash
curl -s http://127.0.0.1:8000/api/v7/portfolio-decision | jq '.allocator_summary,.allocation_monitor[0]'
```

---

## 二、Return / Risk Attribution（必加 · 已 baseline）

### 必須有

- Contribution to return by asset (`return_attribution.by_return`)
- Contribution to drawdown proxy (`return_attribution.by_risk`)
- Top contributor / detractor
- Notes: allocation effect vs selection effect（完整 Brinson 見 `benchmark_portfolio.py`）

### 要補（P1）

- [ ] Wire `BenchmarkPortfolioEngine` for real Brinson
- [ ] Sharpe contribution by asset
- [ ] Rebalance effect (before/after rebalance dates)

---

## 三、Current Allocation Monitor（必加 · 已 baseline）

| 欄位 | 說明 |
|------|------|
| Asset | ticker |
| Current weight % | 實際 |
| Target weight % | equal-weight 或 policy target |
| Drift % | current − target |
| Action required | TRIM / ADD / HOLD |
| Priority | high / medium / low |
| Reason | 人可讀 |

**下一版：** 接 `PortfolioPolicy.max_single_position_pct`、sector cap、target from fund sleeve

---

## 四、Regime Fit Panel（必加 · 已 baseline）

```json
{
  "current_regime": "UPTREND · TRADE",
  "regime_fit_score": 0-100,
  "aligned_with_regime": true,
  "suggested_posture": "aggressive|neutral|defensive",
  "note": "..."
}
```

**要補：** historical best/worst regime from backtest sleeve curves

---

## 五、Benchmark Intelligence（部分 · 要加深）

**已有：** `benchmark_intel.verdict`, portfolio return proxy  
**要補：**

- [ ] Rolling alpha / beta (60d)
- [ ] Tracking error, information ratio
- [ ] Upside / downside capture
- [ ] Active share
- [ ] Excess return by year / by regime

**檔案：** extend `benchmark_portfolio.py` + portfolio equity series endpoint

---

## 六、Active Fund Manager / Sleeve Monitor（必加 · 已 baseline）

**API：** `portfolio-decision.sleeve_monitor[]` from `fund_manager_console`  
**欄位：** status, stance, capital_deployed_pct, regime_fit, return, excess α, next_trigger, evidence badge

**完整 spec：** `docs/FUND_CONSOLE_DEVELOPER_PROMPT_ZH.md`

---

## 七、IB Linkage / Live State（必加 · 已 baseline）

**API：** `portfolio-decision.execution` — same shape as Today `execution_readiness`

必須顯示：

- broker connected?
- paper / live
- portfolio_synced (IBKR vs manual)
- trade_handoff_ready
- gateway_reachable

---

## 八、Monitor / Action Needed（必加 · 已 baseline）

**API：** `action_needed[]` — categories: rebalance_drift, concentration, portfolio_heat, STOP_HIT, etc.

**要補：**

- [ ] Correlation spike vs portfolio
- [ ] Benchmark lag warning (rolling 20d)
- [ ] Turnover spike
- [ ] Exposure drift vs sleeve target

---

## 九、Curve Diagnostics（要補）

**已有 placeholder：** `curve_diagnostics`  
**要補：**

- equity curve (book-level)
- underwater curve
- rolling Sharpe / alpha / vol
- rolling drawdown duration

**資料源：** closed trades jsonl + daily mark-to-market

---

## 十、Why This Portfolio Now（已 baseline）

`why_now`: why_works_now, why_may_stop, rebalance_triggers, watch_next

---

## 高 ROI 下一輪（P1 → P2）

| P | Feature | Files |
|---|---------|-------|
| P1 | Rebalance simulator | `portfolio_rebalance_sim.py` |
| P1 | Correlation matrix on portfolio tab | reuse portfolio gate |
| P1 | Scenario shocks (+50bps rates, QQQ -10%) | new service |
| P2 | Compare workspace A vs B | extend compare.html |
| P2 | PM memo export | `pm_memo.py` |
| P2 | Full equity curve attribution | `benchmark_portfolio.py` |

---

## Task 包（copy 俾 AI）

### Task 1 — Decision summary hardening

```
1. Wire last_rebalance_date from fund_persistence / rebalance log
2. Stance logic: include portfolio heat from pfRisk() server-side
3. Evidence: live vs manual vs backtest per field
```

### Task 2 — Attribution depth

```
1. Call BenchmarkPortfolioEngine in build_portfolio_decision
2. Add allocation_effect / selection_effect to return_attribution
3. UI: horizontal bar chart top 5 contributors
```

### Task 3 — Allocation monitor v2

```
1. Target weights from active sleeve target_allocation OR equal-risk
2. Sector bucket drift
3. Estimated trade size in shares (needs live price)
```

### Task 4 — Curve + benchmark rolling

```
1. GET /api/v7/portfolio-equity-curve?period=1y
2. Rolling alpha/beta 20d window
3. UI sparklines in curve_diagnostics section
```

### Task 5 — Rebalance simulator

```
POST /api/v7/portfolio-rebalance-sim {target_weights}
→ turnover, vol change, tracking error estimate
```

### Task 6 — Standalone portfolio analysis page (optional)

```
If keeping separate /performance-lab or new /portfolio-analysis route:
- Reuse portfolio-decision payload as page 1 section
- Move heatmaps/comparison to section 3 evidence only
```

---

## Professional review comment（可直接貼 PR）

The updated portfolio analysis page is materially stronger and closer to institutional allocator quality. Performance summary, allocation history, equity curve, heatmaps, and comparison tables are meaningful improvements.

However, it still reads more like a rich backtest/reporting page than a true portfolio decision console.

**What is working:** performance framing, allocation evolution, research credibility.

**What is missing for 10/10:**

1. Portfolio Decision Summary at top — **in progress via /api/v7/portfolio-decision**
2. Return/risk attribution — baseline done, Brinson P1
3. Current allocation monitor with drift/actions — **done baseline**
4. Regime overlay — **done baseline**
5. Deeper benchmark intelligence — P1
6. Active sleeve monitor — **done baseline**
7. IB linkage state — **done baseline**
8. Action-needed box — **done baseline**

**Final verdict:** Next step is not more charts — it is **decision + attribution + monitor + live linkage**. Target question: **What should I do now with this portfolio?**

---

## 檔案地圖

| 區域 | 路徑 |
|------|------|
| Decision API | `src/services/portfolio_decision_console.py`, `src/api/routers/portfolio_decision.py` |
| Benchmark engine | `src/engines/benchmark_portfolio.py` |
| Fund sleeves | `src/services/fund_manager_console.py` |
| Portfolio holdings | `src/api/routers/portfolio.py` |
| UI | `src/api/templates/index.html` (tab portfolio) |
| Tests | `tests/test_portfolio_decision_console.py` |

---

## Definition of Done

- [ ] `curl /api/v7/portfolio-decision` returns all top-level keys
- [ ] Portfolio tab shows Decision + Action + Allocation table without errors
- [ ] Empty portfolio: stance PAUSE, no crash
- [ ] IBKR connected: execution.broker_connected true in payload
- [ ] unittest `test_portfolio_decision_console` green
