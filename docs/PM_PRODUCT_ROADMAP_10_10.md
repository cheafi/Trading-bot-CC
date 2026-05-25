# Clarity Console · PM / Product / Developer Roadmap 10/10

**版本：** 2026-05-25  
**基準畫面：** Dashboard PDF — `REGIME UPTREND · WAIT`、空 `TOP IDEAS —`、fund α strip、0 ideas / 0 rejected、flow、morning briefing、AI analysis、sector leaders、no-setup empty state  
**驗證：** `bash scripts/verify_10_10.sh`（含 `/api/v7/today`、`/api/v7/stock-intel/{ticker}`）  
**原則：** 唔係亂加 tab；係喺現有 Today / Playbook / Dossier 架構上 **補返 institutional depth**，保留清晰 hierarchy。

---

## 狀態圖例

| 符號 | 意思 |
|------|------|
| ✅ | 已落地（API + UI 或 API 齊、UI 可用） |
| 🟡 | 部分落地 — 有 payload 但深度 / 視覺 / 證據未達 spec |
| ❌ | 未做或刻意延後 |
| ⬇️ | 應降級（保留但唔做主視覺） |

---

## A. 四欄超詳細 Gap 表（可直接開工）

> **欄位說明：**  
> - **Must-add** = P0，無呢層就仍然似 prototype  
> - **Nice-to-have** = P1，質素加分  
> - **Reduce** = 保留但降 hierarchy  
> - **Postpone** = P2+ 或 Phase 2，而家唔做  

### 1) Must-add — 一定要加返（P0）

| ID | 功能 | 點解（PM） | 驗收標準（Acceptance） | API / 檔案 | 狀態 | Sprint |
|----|------|-----------|------------------------|------------|------|--------|
| M1 | **Best Action Now** | 5 秒答「今日做唔做、做咩、唔做 monitor 咩」 | PM strip + Today 大卡顯示：`capital_stance`、`stance_one_liner`、`best_trade_now` / `best_watch_upgrade`、next review 一句 | `src/services/best_action.py` · `GET /api/v7/today` · `index.html` PM strip L490+、Today L913+ | ✅ | — |
| M2 | **Why No Setup Today** | 將空白變主動診斷 | `no_setup_diagnosis.breakdown` 含：`failed_timing`、`failed_rr`、`failed_execution`、`failed_regime`、`failed_score`、`failed_data`；UI 柱狀或 KPI 可點 | `src/services/today_insights.py::build_no_setup_diagnosis` · `decision.py` | ✅ | — |
| M3 | **Near-miss monitor** | 最接近 pass 嘅名單 | `near_miss[]`：ticker、action、score、gaps、`upgrade_trigger`、entry/stop；可點開 Dossier | `today_insights.py::build_near_miss_candidates` | ✅ | M3.1 加 invalidation 價位 |
| M4 | **Active sleeve / fund manager** | α strip 唔夠 — 要知邊個 active、邊個控資金 | 每 sleeve：`gate_status`、**stance**、**mode**、**controls_capital**、`fund_manager` on today | `model_funds.py` · `build_sleeve_summary` · Today UI | ✅ | — |
| M5 | **Curve / path（唔係淨 α）** | +97% α 易誤導 | `equity_curve_20` spark + `max_drawdown_pct` on strip & active manager card | `model_funds` · PM strip SVG | ✅ | 60d curve P1 |
| M6 | **IB linkage / execution readiness** | 「IBKR OFF」≠ execution ready | `execution_readiness` on `/api/v7/today` + Execution panel | `execution_readiness.py` · `decision.py` | ✅ | live order history P1 |
| M7 | **Monitor panel（核心區）** | Brief 唔等於 monitor console | 固定 **Monitor Now** card (always visible) | `index.html` Today tab | ✅ | watchlist write P1 |
| M8 | **Evidence quality tags** | 每個重要數字要標 live/fallback/stale | `evidence_badges` on today + ops strip pills | `build_evidence_badges` | ✅ | per-KPI expand P1 |

**M1–M3 已達「可演示」；M4–M8 係由 summary → deployable console 嘅關鍵缺口。**

---

### 2) Nice-to-have — 重要加分（P1）

| ID | 功能 | 點解 | 驗收標準 | 狀態 | Sprint |
|----|------|------|----------|------|--------|
| N1 | **Single-stock conviction stack** | 單股決策中心 | `GET /api/v7/stock-intel/{t}`：unified_decision、fundamentals、technicals、peers table、ownership、options、catalysts、narrative bull/bear、monitor if held | 🟡 | P1.1 補齊 10 層（見 §D） |
| N2 | **Influencer / 13F / politician** | 輔助 signal only | 每條帶 `reliability: lagged/partial/not_tradeable_alone`；唔入主 ranking | ❌ | Phase 2 |
| N3 | **Options intelligence** | LEAPS / IV / OI 唔變噪音 | unusual activity、IV pct、OI surge、skew；Dossier Options tab | 🟡 | P1.2 |
| N4 | **Sector / factor rotation explain** | 點解 healthcare leading | `rotation_implication` + `sleeve_beneficiary` + watchlist priority bump | 🟡 | P1.3 |
| N5 | **UPTREND + WAIT 視覺** | 消除矛盾感 | `regime_wait_explanation[]` bullets + 可選矛盾圖示 | ✅ API · 🟡 UI prominence | P1.4 |
| N6 | **Playbook card schema** | PM 級 ranked card | 每卡：`evidence_badge`、`why_not`、`upgrade_trigger`、sleeve_source | 🟡 ranked enrich 有 · 卡 UI 未全顯示 | P1.5 |
| N7 | **Command tab 同步 Best Action** | 全 tab 一致決策 | Command strip = same `best_action` as Today | ❌ | P1.6 |
| N8 | **Trigger-based watchlist** | 條件觸發寫入 | near_miss → watchlist row with trigger price | ❌ | P1.7 |

---

### 3) Reduce / Demote — 應降級（保留）

| ID | 現況問題 | 目標狀態 | 狀態 |
|----|----------|----------|------|
| R1 | `TOP IDEAS —` 空 dash | 改 **Action: WAIT / No deploy** 或 top ticker | ✅ |
| R2 | AI Analysis 佔位大、NO TRACK RECORD | 改名 **AI Commentary (non-decision)**、預設收合、有 insight 先展開 | 🟡 已改名 · 未收合 |
| R3 | Leader/Balanced/Tactical α 搶眼 | α 降到第二層；第一層 **gate_status + stance + curve snippet** | 🟡 gate 已上 strip |
| R4 | `0 ideas / 0 rejected / — scan` | 改 **Deploy ideas / Filtered out / Near-miss count** + 連去 diagnosis | 🟡 KPI 已改 · 未全連結 |
| R5 | Flow 區塊 | 保留但唔與 Best Action 競爭首屏 | ⬇️ 維持 |
| R6 | Morning briefing | 保留為 context，唔取代 monitor | ⬇️ 維持 |

---

### 4) Postpone — 暫時唔好加

| ID | 項目 | 原因 |
|----|------|------|
| P1 | 無節制新 tab | 已簡化過；再亂加會重蹈覆轍 |
| P2 | AI 做主角 ranking | 未有 calibrated track record |
| P3 | Social / influencer feed 主視覺 | 變八卦，違反 institutional 定位 |
| P4 | Auto bracket submit | 要 IB + 人工確認先行 |
| P5 | Per-ticker reject log UI | 數據量大，P2 再做 |
| P6 | SMS / push alerts | Monitor 穩定後 |

---

## B. 之前 vs 而家 — 四類退化（要補返嘅類型）

| 類型 | Before（你想要） | Now（PDF / 現 UI） | 補返策略 |
|------|------------------|-------------------|----------|
| **1. Rich console → summary** | active control、monitor、execution、sleeve responsibility、curve、evidence | regime + scores + counts + briefing + empty | M1–M8 |
| **2. Posture → clean UI** | attack/defend、active FM、curve、paper/live 清晰 | 易讀但 posture 淺 | M4、M5、M6 |
| **3. Workflow → static** | next trigger、if/then、close-to-pass | status + no-op message | M3、M7 |
| **4. Deployable → informative** | IB、FM、monitor、curve | 睇到資料、唔知點行動 | M5、M6、M4 |

---

## C. 核心十項 — 實作對照（俾 AI / developer 直接對）

| # | 核心項 | 狀態 | 下一步（具體 ticket） |
|---|--------|------|---------------------|
| 1 | Active sleeve / active fund manager | ✅ | — |
| 2 | Sleeve curve / drawdown / path | ✅ | 60d + live vs training label P1 |
| 3 | IB linkage readiness | ✅ | portfolio sync from IBKR tab P1 |
| 4 | Monitor panel | ✅ | auto watchlist triggers P1 |
| 5 | Best Action Now | ✅ | Command tab 已加 macro chip；全寬 sync optional |
| 6 | Why no setup breakdown | ✅ | `failed_freshness` bucket added |
| 7 | Near-miss candidates | ✅ | `invalidation_price`, `distance_to_pass` |
| 8 | Evidence quality tags | ✅ | `evidence_badges` on today payload |
| 9 | Trigger-based watchlist | ❌ | `POST /api/watchlist/trigger` from near_miss |
| 10 | Single-stock deep dive | 🟡 | `stock-intel` + Dossier tabs；補 N1 清單 |

---

## D. Single-stock 10/10 — 十層框架與 repo 對照

| 層 | 內容 | API / UI | 狀態 |
|----|------|----------|------|
| 1 Core overview | sector, cap, regime fit, business summary | `stock-intel` · dossier header | 🟡 |
| 2 Fundamentals | growth, margins, FCF, debt, ROIC, multiples | v9 / stock-intel `fundamentals` | 🟡 |
| 3 Technicals | RSI, MA, structure, S/R, RS, volume | dossier + chart | ✅ |
| 4 Peers | vs sector ETF, top5, rev growth, valuation, YTD/3m/1y | `/api/dossier/{t}/peers` table | ✅ |
| 5 Capital / flow | insider, 13F, politician, influencer | edgar insider · 13F | 🟡 / ❌ influencer |
| 6 Options | IV, OI, LEAPS, skew | dossier options tab | 🟡 |
| 7 Events | earnings, guidance, splits | catalysts | 🟡 |
| 8 Investment view | bull/bear/base, invalidation, entry/stop/target | `narrative` + unified_decision | 🟡 |
| 9 Confidence / evidence | technical/fund/flow conf, freshness | partial trust strip | 🟡 |
| 10 Action layer | BUY/WATCH/AVOID, why now / why not / next | `unified_decision` sticky | ✅ |

**Spec 全文：** [`docs/SINGLE_STOCK_COMMAND_CENTER.md`](./SINGLE_STOCK_COMMAND_CENTER.md)

---

## E. Developer brief（英文 · 可貼 issue / PR）

```text
Upgrade Clarity Console from clean summary → institutional PM decision console.

Preserve:
- Regime-first layout, honest no-setup, 4-bar confidence, cash-is-position,
  AI no-track-record warning, simplified visual hierarchy.

Done (do not regress):
- best_action, no_setup_diagnosis, near_miss, regime_wait_explanation,
  monitor_triggers, sleeve_summary (gate_status), stock-intel aggregator,
  verify_10_10.sh green.

P0 — Must complete next:
1. Active fund manager: stance (attack/neutral/defend/off), mode (live/paper/training),
   controls_capital flag on fund cards + Today strip.
2. Sleeve mini curve + max_drawdown on Today (not alpha-only).
3. Execution readiness panel: IB connected, paper/live, bracket_ready, portfolio_sync,
   order_queue, last_heartbeat, last_order_result.
4. Dedicated Monitor Now panel (not buried in empty state).
5. Evidence badges on regime, funds, AI, scanner KPIs.

P1:
- Full playbook card schema in UI; Command tab best_action sync;
  sector rotation implication; watchlist triggers from near_miss.

Do NOT:
- Add unlimited tabs; make AI primary ranker; build influencer/social feed as main UI.

Goal: In 5 seconds answer — deploy? why not? closest actionable? active sleeve?
evidence trust? what to monitor? execution ready?
```

---

## F. Sprint 建議（交 coder 開工順序）

### P0.2 — Active fund manager（2–3d）

```yaml
backend:
  - extend fund card model: stance, mode, controls_capital, recent_dd_pct
  - build_sleeve_summary: active_today, strongest_live vs strongest_training
frontend:
  - PM strip: "Active: Leader · ATTACK · PAPER · controls $X"
files:
  - src/api/routers/funds.py
  - src/services/today_insights.py
  - src/api/templates/index.html (PM strip)
```

### P0.3 — Sleeve curve strip（2d）

```yaml
backend:
  - fund cards include equity_curve_20d, equity_curve_60d (or sparkline points)
frontend:
  - replace α-only pill with spark + DD%
files:
  - fund persistence / performance_lab reuse
```

### P0.4 — Execution readiness（1–2d）

```yaml
backend:
  - execution_readiness object on /api/v7/today + /api/ops/cc-header
  - fields: connected, mode, bracket_ready, portfolio_synced, queue_healthy,
    last_heartbeat, last_order_ok, last_order_fail
frontend:
  - collapsible "Execution" row under Best Action card
files:
  - src/services/ibkr_service.py
  - src/api/routers/ops.py (or decision.py)
```

### P0.5 — Monitor panel（1d）

```yaml
frontend:
  - fixed right column or section "Monitor Now" always visible on Today
  - list monitor_triggers + link to watchlist / dossier
```

### P0.6 — Evidence badges（1–2d）

```yaml
backend:
  - regime.evidence, today.trust.scanner, fund.evidence_badge per card
frontend:
  - reusable <EvidenceBadge source quality />
```

### P1 — Playbook + Command + rotation（3–5d）

See `docs/PLAYBOOK_10_10_SPEC.md`, `docs/PLAYBOOK_PM_REVIEW_GAP_LIST.md`.

---

## G. 測試清單

```bash
# 全量
bash scripts/verify_10_10.sh

# 單項
curl -s http://127.0.0.1:8000/api/v7/today | jq '.best_action,.no_setup_diagnosis,.near_miss,.monitor_triggers,.sleeve_summary'
curl -s http://127.0.0.1:8000/api/v7/stock-intel/AAPL | jq '.unified_decision,.ticker'
python3 -m unittest tests.test_best_action tests.test_today_insights tests.test_stock_intel -q
```

---

## H. 相關文件

| 文件 | 用途 |
|------|------|
| [`CC_DASHBOARD_10_10_GAP_LIST.md`](./CC_DASHBOARD_10_10_GAP_LIST.md) | Today tab 精簡 gap |
| [`PLAYBOOK_10_10_SPEC.md`](./PLAYBOOK_10_10_SPEC.md) | Playbook card schema |
| [`PLAYBOOK_PM_REVIEW_GAP_LIST.md`](./PLAYBOOK_PM_REVIEW_GAP_LIST.md) | Playbook 專項 |
| [`SINGLE_STOCK_COMMAND_CENTER.md`](./SINGLE_STOCK_COMMAND_CENTER.md) | Dossier 十層 engineering |

---

## I. 一句總結（俾 stakeholder）

**而家個 console 已經由「空 TOP IDEAS」升級到有 Best Action、診斷、near-miss、monitor triggers 同 stock-intel；verify 10/10 綠。**

**要真正 PM-grade deployable，下一輪 P0 唔係再靚 UI，而係：active fund manager + curve/drawdown + execution readiness panel + 固定 Monitor 區 + 全區 evidence badges。**

Influencer / social 一律 Phase 2 supporting only.
