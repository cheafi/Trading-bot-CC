# Fund · Clarity Console — 中文版 Developer Prompt（可直接開工）

**目標：** 由「靚嘅 sleeve summary」→ **allocator / PM / CRO 可指揮資金嘅 fund command center**  
**現況評分：** ~8/10 operating prototype（本輪已加 allocator strip + manager box + 證據層）  
**10/10 標準：** 30 秒答完 8 條 allocator 問題 + 有 path + 有 trust + 有 execution + 有 monitor

---

## 一、Allocator 30 秒必答（Layer 1）

頁面最頂 **`allocator_decision`** 必須顯示：

| 問題 | 欄位 |
|------|------|
| 1. 依家應唔應該 deploy？ | `deploy_capital`, `deploy_posture` |
| 2.  deploy 去邊個 sleeve？ | `where`, `best_sleeve_now` |
| 3. 邊個最值得加倉？ | `marginal_instruction` / allocation |
| 4. 邊個 keep warm？ | `closest_to_reactivation`, `do_not_allocate` |
| 5. 今日減風險 cut 邊？ | `weakest_sleeve`, `if_wrong` |
| 6. 績效 live/paper/backtest？ | `performance_basis`, `performance_evidence` |
| 7. Regime 同 sleeve 一致？ | `regime_display` vs 每 sleeve `regime_fit_decomposed` |
| 8. 跟/唔跟代價？ | `if_follow`, `if_wrong`, `why_not` |

**API：** `GET /api/fund-lab/console` → `allocator_decision`  
**UI：** `fundMonitor.console.allocator_decision`（Funds tab 第一張綠框）

---

## 二、五大 institutional 層（必須有）

### 1) Active fund manager decision layer

每個 sleeve **`manager_box`**：

```json
{
  "manager_state": "ATTACK|DEFEND|NEUTRAL|OFF",
  "capital_deployed_pct": 0-100,
  "idle_cash_pct": 0-100,
  "conviction": "HIGH|MEDIUM|LOW",
  "reason_code": "REGIME_FIT_LOW|...",
  "last_decision": { "date", "action", "summary" },
  "decision_reason": "string",
  "next_trigger": "string",
  "next_action": "ADD|HOLD|WATCH",
  "override_condition": "string"
}
```

**檔案：** `src/services/fund_manager_console.py::build_manager_box`  
**UI：** 每張 sleeve card 內「Fund manager」灰框

---

### 2) Curve / path（績效靈魂）

每 sleeve 必須有：

- `equity_curve_20` / `equity_curve_60`（`fund_lab_service._metrics`）
- SVG mini spark（`sleeveSparkPoints()`）
- `max_drawdown_pct` + `underwater_badge`
- 顯示 **BM return** 與 **Excess α** 分開（唔好 alpha=return）

**公式顯示：** `performance_evidence.formula`  
`excess = fund_total_return − SPY_total_return (same window)`

---

### 3) Evidence-quality layer

每 sleeve **`performance_evidence`**：

- evidence: `backtest`（未 live 前唔好寫 live）
- period, sample, cost_basis, transaction_costs, slippage
- trust_tier: `research_only`

KPI 旁邊要有 label，唔好淨係靚數字。

---

### 4) Allocation engine layer

**`allocation`** 物件：

- `weights[]` — target % per sleeve
- `cash_reserve_pct`
- `strongest_deployable`, `weakest`
- `do_not_allocate_now[]`
- `marginal_instruction`

與 **`allocator_decision.how_much`** 同步。

---

### 5) Monitor / reaction framework

兩塊：

1. **`monitor_triggers`** — 事件型（closest activation, rebalance adds）
2. **`reaction_monitor`** — if/then 規則（VIX, breadth, leadership）

例：

- If VIX > 20 → Tactical upweight  
- If breadth ≥ 50% → Balanced resume candidate  

---

## 三、CRO 層（第二優先，本輪已加 baseline）

- **`risk_governance`** — DD budget vs current DD, stop framework  
- **`holdings_overlap`** — 跨 sleeve 同名 ticker 警告  

未做：factor overlap、correlation budget、sector cap 實時計算。

---

## 四、Regime fit 可解釋

唔好只得一個 15/40/65 數字。

**`regime_fit_decomposed.components`：**

- trend_fit, volatility_fit, breadth_fit, liquidity_fit, correlation_fit  
- `formula_note` — 標明 heuristic，待校準  

---

## 五、Trust killers — 必須修

| 問題 | 修法 |
|------|------|
| Regime unknown vs UPTREND | `regime_display` 來自 regime_cache + Today |
| Alpha = Return | `benchmark_return_pct` on lab payload; show BM separately |
| IBKR OFF 唔夠 | `execution_readiness` 全欄位 strip |
| Page 2 空白 | 非 Funds scope — 查 nav/render/CSS（PDF export artifact） |

---

## 六、UI hierarchy（由上而下）

```
1. Trust strip — regime_display, benchmark %, model_backtest pill
2. Allocator decision strip（綠框）
3. Reaction monitor（if/then）
4. Holdings overlap（如有）
5. Execution readiness
6. Allocation suggestion
7. Monitor triggers
8. Risk governance table
9. Sleeve comparison matrix
10. Sleeve operating cards（manager box + curve + evidence + holdings pills → dossier）
```

---

## 七、API 清單

| Endpoint | 用途 |
|----------|------|
| `GET /api/fund-lab/live` | 全量含 `console` |
| `GET /api/fund-lab/console` | 只要 operating layer |
| `GET /api/v7/today` | 同步 tradeability / best_action（寫入 `app.state.today_v7_cache`） |

---

## 八、檔案清單

| 檔案 | 職責 |
|------|------|
| `src/services/fund_manager_console.py` | 全部 operating 邏輯 |
| `src/services/fund_lab_service.py` | benchmark_return_pct, curves |
| `src/services/model_funds.py` | card 基礎 + stance/mode |
| `src/api/routers/funds.py` | HTTP + context injection |
| `src/api/templates/index.html` | `tab==='funds'` |
| `tests/test_fund_manager_console.py` | 單測 |

---

## 九、驗收標準（Acceptance）

- [ ] Allocator strip 顯示 deploy/where/how much/cash/blockers  
- [ ] 每 sleeve 有 manager box + decomposed fit + performance evidence  
- [ ] Alpha ≠ return when SPY return non-zero  
- [ ] Mini curve + max DD visible  
- [ ] Holdings click → `openDossier(ticker)`  
- [ ] `python3 -m unittest tests.test_fund_manager_console -q` PASS  
- [ ] `curl /api/fund-lab/console | jq .allocator_decision` 有 payload  

---

## 十、P1  backlog（勿與 P0 混做）

1. Rolling alpha vs SPY chart  
2. 12M rolling Sharpe / hit-rate  
3. Live vs training 雙 curve  
4. Sleeve drill-down 全頁（full curve + attribution）  
5. Factor/sector overlap（非 ticker overlap only）  
6. Recent decision log（SQLite）  

---

## 十一、一句給 PM

**而家有 fund manager workflow 雛形，唔再只係三張靚卡。**  
未 live 前，所有績效必須標 **backtest · research_only**，避免 fake precision。

重啟：`docker restart cc_api_dev` → 開 **Funds** tab。
