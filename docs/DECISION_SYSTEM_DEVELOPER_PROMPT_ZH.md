# Clarity Console — Decision System 超專業 Developer Prompt（中文版 · 可直接 copy 開工）

**North star：** 由「有資料嘅工具頁」→ **top PM / CIO / allocator / risk committee 一開就知點做** 嘅 decision system。  
**唔再做：** 零碎 widget、多 tab 堆數字、無 verdict 嘅 quote 頁。  
**要做：** research depth + smart money layer + allocator layer + monitoring layer + execution layer。

**現況（本輪已落地 baseline）：**
- `GET /api/v7/decision-hub` — 全平台 decision strip + 4-class monitor + fund allocator snapshot
- `GET /api/v7/stock-intel/{ticker}` — dossier 含 `pm_answer`、`smart_money`、`identity`、`layers`
- Today / Funds / Dossier UI 已接 decision strip、PM answer、smart money summary
- Fund console spec：`docs/FUND_CONSOLE_DEVELOPER_PROMPT_ZH.md`

**10/10 驗收：** `bash scripts/verify_10_10.sh` 全綠 + 每個主 surface 30 秒答完決策問題。

---

## 零、全局 Decision Strip（所有主 tab 頂部必見）

### 必答問題（一打開）
| 問題 | 欄位 |
|------|------|
| 今日最值得做邊隻？ | `decision_strip.best_idea_now` |
| 最佳 R:R？ | `decision_strip.best_risk_reward_now` |
| 最佳 momentum？ | `decision_strip.best_momentum_now` |
| 最佳 mean reversion？ | `decision_strip.best_mean_reversion_now` |
| 必須 avoid？ | `decision_strip.avoid_now[]` |
| 市場 posture？ | `decision_strip.market_posture_now` |
| Deploy / Reduce / Wait？ | `decision_strip.deploy_reduce_wait` |

### API
- `GET /api/v7/decision-hub`（45s cache）
- 實作：`src/services/decision_hub.py::build_decision_hub`
- Router：`src/api/routers/decision_hub.py`

### UI
- `#pm-strip` 第二行 DECISION pills（`decisionHub` + `fetchDecisionHub()`）
- Today tab：`Institutional monitor` 四類規則 grid

### 驗收
```bash
curl -s http://127.0.0.1:8000/api/v7/decision-hub | jq '.decision_strip,.monitoring.stock|length'
```

---

## 一、由「資訊頁」升級做「決策頁」（Layer 1）

### Today / Dashboard
**已有：** Best Action、no_setup_diagnosis、near_miss、monitor_triggers、sleeve_summary、evidence_badges、execution_readiness  
**要補：**
- [ ] `avoid_now` 獨立 panel（category: earnings / breadth / IV / failed breakout / insider cluster）
- [ ] `deploy_posture` 大字 + 若 follow / if wrong 一句
- [ ] cross-asset confirmation 行（rates / VIX / USD / oil vs equity stance）

**檔案：** `src/services/today_insights.py`, `src/services/best_action.py`, `src/api/routers/decision.py`  
**UI：** `index.html` tab `today`

### Signals / Playbook
**要補：** 每張 ranked card 頂部 mini decision line：`NOW|WAIT|AVOID` + setup type + evidence badge

### 驗收
打開 Today → 30 秒內能講：出手定觀察、最佳 idea、avoid 幾隻、deploy posture。

---

## 二、Single Stock → Full Investment Dossier（Layer 2）

### 七層結構（API `stock-intel` 必須齊）
| 層 | 欄位前綴 | 內容 |
|----|----------|------|
| A Identity | `identity` | segments, geo, peers, factor tags (growth/quality/cyclical/AI beta…) |
| B Fundamental | `layers.fundamentals` | rev/EPS/margin/FCF/ROIC/debt/valuation vs hist & peers |
| C Technical | `layers.technicals` | MTF trend, MA stack, S/R, RS vs SPY/sector, vol regime, entry/stop/target |
| D Positioning | `layers.positioning` | options flow, OI, short interest, borrow risk |
| E Smart money | `smart_money` + `ownership` | evidence-graded（見 Layer 3） |
| F Catalyst | `catalysts` | earnings, guidance, regulatory, inclusion |
| G PM answer | `pm_answer` | bull/bear/breaks/confirms/setup/action NOW\|WAIT\|AVOID |

### API
- `GET /api/v7/stock-intel/{TICKER}` — `src/services/stock_intel.py`
- UI：`fetchDossier()` → `dos.intel`；PM answer + smart money cards 在 tab bar 之上

### 要補（P1）
- [ ] Fundamental block 接 live yfinance / internal fundamentals（唔好淨 stub）
- [ ] Peer compare table（valuation + growth + 3m RS）
- [ ] Options LEAPS / skew / OI change
- [ ] Catalyst calendar widget（30d forward）
- [ ] Industry chain map（suppliers/customers/downstream）— 新 service `ecosystem_map.py`
- [ ] Variant perception：`market_expects` / `surprise_vector`
- [ ] Quality of move：news / short cover / flow / passive / fundamental

### 驗收
```bash
curl -s http://127.0.0.1:8000/api/v7/stock-intel/AAPL | jq '.pm_answer.action_now,.smart_money.usefulness,.identity'
```

---

## 三、Smart Money / Influencer Tracking（Layer 3）— 成熟做法

### 禁止
- 「某人買咗」= bullish
- 13F 當即時信號
- 社交熱度當 alpha

### 必須：四維評分（每條 source）
```json
{
  "evidence_type": "13f|form_4|schedule_13d|options_flow|public_mention|macro_only|social_speculation",
  "signal_quality": "confirmed_filing|delayed_filing|inferred|rumor",
  "relevance": "single_stock|sector|macro_only|not_actionable",
  "timeliness": "recent|medium_lag|stale_informative|unknown"
}
```

### 股票頁 Summary（已有 shape）
```json
{
  "insider": "neutral|bullish|bearish",
  "hedge_fund_trend": "accumulating|trimming|unknown",
  "politician_trend": "none|minor|notable",
  "options_flow": "bullish_LEAPS|short_term_noise|no_data",
  "confidence": "low|medium|high",
  "usefulness": "supportive_only — not standalone trigger"
}
```

### 要補
- [ ] Politician trades feed（STOCK Act）+ cluster detection
- [ ] 13F leaderboard + QoQ change（lag warning 常駐）
- [ ] Influencer mention monitor（weight < filing）
- [ ] `conviction_score_by_source` 加權合成

**檔案：** 擴 `stock_intel._smart_money_summary`；新 `src/services/smart_money_tracker.py`

---

## 四、Fund / Sleeve Allocator Console（Layer 4）

**Spec 全文：** `docs/FUND_CONSOLE_DEVELOPER_PROMPT_ZH.md`  
**API：** `GET /api/fund-lab/console` → `allocator_decision`, `manager_box`, curves, monitor

### 30 秒必答（allocator）
1. Deploy 定唔 deploy？  
2. Deploy 去邊個 sleeve？  
3. 邊個加倉 / cut？  
4. Performance 係 live / paper / backtest？  
5. Regime 同 sleeve 一致？  
6. 跟/唔跟代價？  
7. IBKR handoff ready？  
8. Next trigger 係乜？

### 要補
- [ ] Live IBKR position sync vs model holdings diff
- [ ] Target weight vs current weight 每日 delta
- [ ] Paper / live toggle 喺 execution layer

---

## 五、Backtest → Research Lab（Layer 5）

### 現況
基本：ticker + strategy + period + run

### 目標配置面板
- universe, benchmark, regime filter, position size, rebalance, cost, slippage, max positions, stop/TP model

### 結果必須
- Summary：CAGR, maxDD, Sharpe, Sortino, Calmar, win rate, expectancy, payoff, turnover
- Curves：equity, drawdown, rolling Sharpe/win rate, underwater duration
- Attribution：year / month / regime / sector / setup / cap / vol regime
- Trades：entry/exit, MFE/MAE, slippage, rule-followed flag
- Robustness：walk-forward, OOS, param sensitivity, Monte Carlo, post-cost decay

**檔案：** 擴 `src/api/routers/live.py` backtest + 新 `src/services/backtest_lab.py`  
**UI：** `index.html` `bt` state → multi-panel layout

---

## 六、Quote / Lookup → Research Workstation（Layer 6）

### 六 panel（同一頁，唔係空 search box）
1. Quick identity  
2. Technical snapshot  
3. Fundamental snapshot  
4. Positioning snapshot  
5. Peer compare  
6. PM verdict box  

**做法：** Quote tab 預設載入 `stock-intel` + compact 6-grid；search 只係改 ticker。

---

## 七、Commands → Operating Hub（Layer 7）

### 必須有
- categories, most used, quick-run, recent, pinned, favorites
- result preview pane
- macros：`morning_briefing`, `scan_momentum`, `insider_buys_week`, `avoid_now_list`, `pm_memo_one_stock`

**API 建議：**
- `POST /api/v7/commands/run` body `{macro, args}`
- `GET /api/v7/commands/catalog`

**UI：** Commands tab 左 catalog、右 preview；唔好淨係 markdown list。

---

## 八、Institutional Monitoring System（Layer 8）

### 四類（decision-hub 已有 framework）
| 類 | 例子 |
|----|------|
| Stock | price level, RSI zone, unusual vol, earnings, insider filing, options spike |
| Portfolio | size breach, correlation, sector concentration, stop, drawdown |
| Market | VIX, breadth, rates, sector rotation, USD/yields/oil |
| Smart money | insider cluster, multi-HF add same name, LEAPS build-up |

### 要補
- [ ] User-defined rules + alert dispatch（Discord / email）
- [ ] `GET /api/v7/monitors/active` 持久化

---

## 九、User Type Hierarchy（Layer 9）

每頁 footer 或 info chip：

| Persona | 主用頁 |
|---------|--------|
| Discretionary PM | today, command, dossier, signals |
| Allocator | funds, today, portfolio |
| Risk officer | ops, portfolio, funds |
| Analyst | dossier, signals, flow |
| Execution trader | ibkr, portfolio, ops |
| Research analyst | dossier, flow, signals |

**API：** `decision_hub.user_roles`（已有）  
**UI：** Guide modal 加 persona → default tab map

---

## 高 ROI 功能（優先序）

| P | Feature | Owner files |
|---|---------|-------------|
| P0 | Decision hub strip 全 tab | `decision_hub.py`, `index.html` pm-strip |
| P0 | Dossier PM answer + smart money | `stock_intel.py`, dossier UI |
| P0 | Fund allocator console | `fund_manager_console.py` |
| P1 | Avoid-now engine（分類） | `today_insights.py` |
| P1 | Portfolio risk cockpit | `portfolio_risk.py`（新） |
| P1 | Catalyst calendar | `catalyst_calendar.py`（新） |
| P1 | PM memo generator | `pm_memo.py`（新） |
| P2 | Backtest lab | `backtest_lab.py` |
| P2 | Commands power center | `commands_hub.py` |
| P2 | Evidence-quality 全平台 label | 各 response `trust` / `evidence` |

---

## Evidence-Quality 規則（全平台）

任何 impress 數字旁邊必須有：
```json
{
  "basis": "live|paper|backtest|model",
  "sample_size": 120,
  "period": "2020-2025",
  "gross_net": "net",
  "cost_assumption": "10bps/side"
}
```
**禁止** backtest sleeve 顯示成 live alpha。

---

## 實作任務包（copy 俾 AI / coder）

### Task A — Dashboard decision upgrade
```
1. Extend today_insights.build_avoid_list() with categories: earnings, breadth, IV, breakout_fail, insider_cluster
2. Surface on Today tab + merge into decision_hub.decision_strip.avoid_now
3. Add cross_asset_confirmation block to /api/v7/today (rates, vix, dxy, oil vs stance)
4. Tests in tests/test_today_insights.py
```

### Task B — Institutional dossier depth
```
1. Expand stock_intel identity + fundamentals from dossier live endpoints
2. Add peers compare matrix endpoint GET /api/dossier/{t}/peer-matrix
3. UI: 6-layer accordion on dossier; PM verdict sticky footer
4. unittest tests/test_stock_intel.py for pm_answer + smart_money grading
```

### Task C — Smart money tracker
```
1. New smart_money_tracker.py with evidence scoring
2. Wire politician + 13F delta + options unusual
3. Never emit BUY without signal_quality >= confirmed_filing OR live options grade A/B
```

### Task D — Allocator console hardening
```
1. IBKR sync status on fund console execution layer
2. target_weight vs current_weight daily on each sleeve card
3. See FUND_CONSOLE_DEVELOPER_PROMPT_ZH.md sections 1-5
```

### Task E — Monitoring + alerts
```
1. Persist monitors; CRUD /api/v7/monitors
2. Evaluator job on scan cycle
3. Discord webhook from existing notify path
```

### Task F — Backtest lab UI
```
1. backtest_lab service with attribution + robustness
2. Replace bt tab with config + results + trade table
```

### Task G — Commands power center
```
1. catalog + run macro endpoints
2. UI quick actions row (morning briefing, avoid list, insider scan)
```

### Task H — Portfolio risk cockpit
```
1. correlation matrix, factor exposure, concentration alerts, top risk contributor, scenario stress
2. GET /api/v7/portfolio-risk
3. Portfolio tab section above positions
```

---

## 檔案地圖

| 區域 | 路徑 |
|------|------|
| Decision hub | `src/services/decision_hub.py`, `src/api/routers/decision_hub.py` |
| Today | `src/services/today_insights.py`, `src/api/routers/decision.py` |
| Dossier | `src/services/stock_intel.py`, `src/api/routers/stock_intel.py` |
| Funds | `src/services/fund_manager_console.py`, `src/api/routers/funds.py` |
| UI | `src/api/templates/index.html` |
| Verify | `scripts/verify_10_10.sh`, `scripts/test_api_endpoints.sh` |
| Roadmap | `docs/PM_PRODUCT_ROADMAP_10_10.md` |

---

## 驗收清單（Definition of Done）

- [ ] `bash scripts/verify_10_10.sh` → `10/10 PASS`
- [ ] `/api/v7/decision-hub` 回 `decision_strip` + `monitoring` 四類非空
- [ ] `/api/v7/stock-intel/AAPL` 回 `pm_answer` + `smart_money`
- [ ] pm-strip 見 Idea / Mom / MR / R:R / Deploy / Avoid
- [ ] Dossier 見 PM answer + smart money（supporting only 文案）
- [ ] Funds tab 見 allocator_decision + manager_box
- [ ] Smart money 無 gossip 式「某人買咗=bullish」
- [ ] 每個 KPI 有 evidence basis label

---

## Blunt verdict

下一步 **唔係加 tab**，係三條主線做深：
1. **單股 institutional dossier**  
2. **Fund / sleeve allocator console 做真**  
3. **Smart money / options / insider 做成熟（evidence-ranked）**  

本 prompt 可直接貼去 Claude / Copilot / Cursor Agent；按 Task A→H 分批 PR，每批跑 `verify_10_10.sh`。
