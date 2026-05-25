# Clarity Console · Dashboard (Today) — 10/10 Gap List

> **完整四欄 roadmap（Must / Nice / Reduce / Postpone + Sprint + 實作狀態）：**  
> [`docs/PM_PRODUCT_ROADMAP_10_10.md`](./PM_PRODUCT_ROADMAP_10_10.md)

**Review 基準：** PM/CIO 級 feedback（capital deployment page，唔係 retail summary）  
**API：** `GET /api/v7/today` · UI：`tab==='today'` · PM strip 全 tab 共用  
**目標 5 秒內答到：** 做唔做 · 點解唔做 · 最接近 actionable 係乜 · 邊個 sleeve active · 信唔信 evidence · 下一步 monitor 乜

---

## 四欄 Gap Table

| 項目 | Must-add（一定要） | Nice-to-have | Remove / Demote | Postpone |
|------|-------------------|--------------|-----------------|----------|
| **Best Action Now** | ✅ 已加 API+Dashboard 大卡 | 同步 Command strip 全寬 | 空 TOP IDEAS `—` headline | — |
| **Why no setup 分解** | ✅ `no_setup_diagnosis.breakdown` | 點擊 KPI 展開 funnel 圖 | 純「0 ideas」KPI | per-ticker reject log |
| **Near-miss** | ✅ `near_miss[]` + UI | Peer compare on near-miss | — | auto-alert 推送 |
| **UPTREND+WAIT 解釋** | ✅ `regime_wait_explanation` | 視覺矛盾圖示 | regime 同 AI 重複段落 | — |
| **Sleeve deployability** | ✅ `sleeve_summary` + strip gate_status | 全 curve spark | 純 α% strip 搶眼 | live 20-trade 每 sleeve |
| **Evidence badges** | partial（sleeve model_only） | 每 KPI 一個 badge | — | calibration buckets |
| **Monitor triggers** | ✅ `monitor_triggers` | 自動 watchlist 寫入 | — | SMS/IB alert |
| **IB readiness** | ✅ in `best_action.execution_readiness` | 每 CTA 灰化規則 | — | auto bracket submit |
| **AI block** | 改名 AI Commentary + 降級 | 僅有 insight 時展開 | 佔首屏大半 | AI 驅動 ranking |
| **Fund α strip** | gate_status 取代純 α | hit rate / DD on strip | 無 deploy 語境嘅 α | — |
| **0 rejected KPI** | 改為 Filtered out 總數 | 逐條 reject 原因 | 孤立 0 數字 | — |
| **Deep link Dossier** | `openDossier()` 已有 | Playbook 卡連結 | — | — |
| **Smart money** | — | insider/options 摘要 | 主引擎 influencer | Phase 2 |

---

## Before → After

| 維度 | Before | After（本輪） |
|------|--------|---------------|
| 第一眼 | TOP IDEAS — + 搶眼 α | **Action: WAIT / No deploy** + sleeve gate |
| 0 setup 日 | 空狀態文字 only | **分解 + near-miss + monitor** |
| UPTREND+WAIT | 看似矛盾 | **Why WAIT in uptrend** bullets |
| KPI | 0 ideas / 0 rejected | **Deploy ideas + Filtered out + near-miss hint** |
| AI | 大塊 paraphrase | **Commentary (non-decision)** |

---

## 已落地檔案

| 檔案 | 作用 |
|------|------|
| `src/services/today_insights.py` | diagnosis, near_miss, wait_explanation, monitor, sleeve_summary |
| `src/services/best_action.py` | capital stance + execution_readiness |
| `src/api/routers/decision.py` | today payload 擴充 |
| `src/api/templates/index.html` | PM strip, Best Action, no-setup blocks |
| `docs/PLAYBOOK_PM_REVIEW_GAP_LIST.md` | Playbook 專項 |
| `docs/PLAYBOOK_10_10_SPEC.md` | 技術 schema |

---

## Developer brief（英文 · 可貼）

```
Upgrade Today dashboard to PM capital-deployment console.

Preserve: regime-first, honest empty state, decision rules, 4-bar confidence, cash-is-position, AI no-track-record warning.

Add: best_action, no_setup_diagnosis, near_miss, regime_wait_explanation, monitor_triggers, sleeve_summary with gate_status.

Remove: empty TOP IDEAS dash; demote alpha-only fund strip; demote AI to optional commentary.

Goal: 5-second answers on deploy?, why not?, closest actionable?, active sleeve?, evidence trust?, what to monitor?
```

---

## 測試

```bash
python3 -m unittest tests.test_best_action tests.test_today_insights -q
python3 -m py_compile src/services/today_insights.py src/api/routers/decision.py
```
