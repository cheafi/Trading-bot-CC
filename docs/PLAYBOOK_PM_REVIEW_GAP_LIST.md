# Playbook · Clarity Console — PM Review Gap List（廣東話）

**Review 基準：**  institutional PDF + 你份升級版 feedback（排序有咗，explanation 未跟上）  
**技術對照：** `docs/PLAYBOOK_10_10_SPEC.md` · `src/api/routers/playbook.py` · `index.html` (Signals / rankedOpps)  
**目標一句：** 由「可讀 ranked list」→「日日開嚟做 capital decision 嘅 action console」

---

## 一、Before vs After（核心差距）

| 維度 | Before（而家 ~7/10） | After（10/10） |
|------|---------------------|----------------|
| **Capital 決策** | 有 30 隻 rank，但冇一句「而家點做」 | **Best Action Now** bar：deploy stance + best trade/watch/avoid + evidence + IB readiness |
| **解釋力** | 卡似 template；Conf ~60% 一式一樣 | 每隻 **why now / why not / upgrade / invalidate** 有差異；**why this over that** |
| **信任** | `UNKNOWN UNKNOWN`、TOP IDEAS 空但下面有 rank | **零 UNKNOWN**；evidence badge；stale/fresh 落喺每張卡 |
| **WATCH** | 次級 label | **Watch→Trade monitor**：trigger price/volume/regime + expiry |
| **Book 風險** | 半導體一窩蜂 rank 上嚟 | **Overlap / correlation cluster** warning |
| **Sleeve / Fund** | α strip 搶眼但未連 deployment | **Idea source + sleeve deploy state + regime fit**；同 Funds tab 打通 |
| **Track Record** | 證據喺另一 tab | Playbook 卡上：**curve spark / hit rate / last 20 trades / DD**（或連結） |
| **執行** | Send to IBKR 但 header IBKR OFF | **Execution readiness**：broker on/off、paper/live、bracket ready、handoff |
| **單股深度** | Playbook 同 Dossier 分離 | Playbook → **Dossier command center** deep link（已起步：`/api/v7/stock-intel`） |
| **Smart money** | 未整合或易變八卦牆 | **Supporting layer only**：insider / options / 13F / commentary，權重 ≤ 主引擎 |

---

## 二、一定要加返（Must-have）

| # | Feature | 點解一定要 | 主要改動位置 |
|---|---------|------------|--------------|
| 1 | **Best Action Now bar** | 答「今日應唔應 deploy capital」 | 新 `src/services/best_action.py`；`today` + `playbook/ranked` payload；`index.html` sticky |
| 2 | **移除 UNKNOWN + 乾淨 empty state** | 信任殺手；PDF 同 code 已確認 | `playbook.py` `_brief_ranked_fallback`；UI `x-if` 唔顯示空欄 |
| 3 | **Per-idea evidence badge** | raw model / training / stale 要落 decision layer | Card schema + `data_conf` / `source` / calibration hook |
| 4 | **Why this over that（Top 5）** | 答「點解係呢隻唔係第二隻」 | Peer compare 或 sector rank delta；`/api/dossier/{t}/peers` 已有基礎 |
| 5 | **Why now / why not / upgrade / invalidate** | 每張卡唔可以再係同一條 invalidation | Enrich ranked row builder；brief fallback 填 `why_not`, `upgrade_trigger` |
| 6 | **Idea source / sleeve / model family** | Playbook ↔ Funds 打通 | `sleeve_id`, `deploy_state`, `regime_fit` from fund monitor API |
| 7 | **IB execution readiness** | Send to IBKR 同 header 狀態一致 | `cc-header` + per-card `execution_readiness` object |
| 8 | **Watch→Trade trigger engine** | WATCH 要可 monitor | `upgrade_trigger`, `trigger_price`, `stale_after` on WATCH rows |
| 9 | **Capital overlap warning** | 同 theme 集中（semi/AI） | Top-N sector clustering in `playbook/ranked` meta |
| 10 | **TOP IDEAS 同 ranked 訊號一致** | 而家「上面空、下面滿」令人困惑 | Wire `today7.top_ranked` = first slice of `rankedOpps` 或 hide empty block |

---

## 三、可以唔加（Nice-to-have / 非 MVP）

| Item | 原因 |
|------|------|
| 更多 technical indicator 喺 Playbook 卡上 | 已有 entry/stop/target；深度應去 Dossier |
| Influencer 做主排序 | 你 review 已講：supporting only，權重細 |
| 即時 full 13F parsing | 滯後 45–90 天；用 lag label + overlap 就夠 |
| 每張卡 embedded 全屏 chart | 性能 + 重複 Dossier；用 deep link |
| 自動落單（無確認） | 違反 CRO；保持 draft + confirm header |

---

## 四、建議延期（Phase 2+）

| Item | 延期原因 | 依賴 |
|------|----------|------|
| Full calibration buckets on every card | 需要 ≥30 closed trades；strategy health 已誠實披露 | Decision journal + ledger |
| Live leaderboard auto-populate | 要等 engine cycles | Ops / engine running |
| Great-investor commentary feed | 合規 + 噪音；先做 insider/options/13F | Smart Money spec Phase 2 |
| Multi-account sleeve rebalance actions | 複雜度高 | IBKR + portfolio gate |
| Auto correlation matrix 全 book | 可先 top-10 cluster warning | Portfolio positions API |

---

## 五、最高 ROI — 建議實作順序（Top 10）

| 次序 | 工作項 | 預估影響 | 備註 |
|------|--------|----------|------|
| **P0-1** | 清 UNKNOWN + fallback 文案差異化 | 信任 +2 | 已可改 `playbook.py` 幾行 |
| **P0-2** | Best Action Now（API + UI strip） | 可用性 +3 | 見 `PLAYBOOK_10_10_SPEC.md` §3 |
| **P0-3** | Evidence badge on card | 信任 +1 | `live-tested` / `stale-brief` / `training` |
| **P0-4** | IB readiness 同 Send to IBKR 聯動 | 執行一致 +1 | 用現有 `cc-header` + `ibkr.status` |
| **P1-1** | why_now / why_not / upgrade / invalidate 填滿 | 差異化 +2 | 主 pipeline + fallback |
| **P1-2** | Why this over that（top 5） | 決策 +2 | peers API / sector leader compare |
| **P1-3** | Sleeve source strip（取代純 α%） | Capital context +2 | Funds monitor 已有數據 |
| **P1-4** | Watch trigger block | Monitor +2 | WATCH 專用欄位 |
| **P1-5** | Theme overlap warning | 風險 +1 | semi cluster 規則已明顯 |
| **P1-6** | Playbook → Dossier deep link + stock-intel | 單股 +2 | `/api/v7/stock-intel/{t}` 已存在 |

---

## 六、五條決策問題 — 而家答到幾多？

| 問題 | 而家 | 10/10 需要 |
|------|------|------------|
| 1. 今日應唔應 deploy capital？ | 半（regime WAIT 有，但無 stance 一句） | Best Action Now `capital_stance` |
| 2. 點解係呢隻唔係第二隻？ | 弱（只有 score rank） | why this over that |
| 3. 點解係而家唔係等？ | 中（why_now 有但 template 化） | timing_conf + trigger window |
| 4. 錯咗幾時認錯？ | 弱（invalidate 清一色） | 具體價位/結構/regime 條件 |
| 5. 可信程度幾高？ | 半（footer 有 disclaimer，卡上無） | evidence badge + calibration state |

**粗估：而家 2/5～2.5/5；P0+P1 做完應到 4.5/5。**

---

## 七、俾 Developer / AI 嘅英文 brief（可直接貼）

```
Review Playbook as PM decision surface, not ranked signal board.

Keep: TRADE/LEADER/WATCH/AVOID, entry/target/stop/R:R, regime header, Send to IBKR, honest strategy health.

Fix: UNKNOWN labels, templated confidence, empty TOP IDEAS vs filled rank list, decorative fund alpha strip, generic invalidations, disconnected Funds/Track Record/Dossier.

Add: Best Action Now bar, per-idea sleeve source, evidence badges, why-this-over-that, watch→trade triggers, overlap warning, IB execution readiness, optional smart-money as supporting layer only.

Goal: Every idea is trustworthy, comparable, monitorable, executable — not just scored.
```

---

## 八、同 Dossier Command Center 嘅分工

| Surface | 角色 |
|---------|------|
| **Playbook** | 「今日 capital 點分配」— rank + compare + act |
| **Dossier** | 「一隻股票查到底」— unified decision + tabs（已 redesign） |
| **Funds** | Sleeve deploy / paused / regime fit 嘅 source of truth |
| **Track Record** | 長期 evidence；Playbook 只摘 spark / hit rate |

**整合點：** Playbook 每張卡 `Open Command Center` → `fetchDossier()` + `tab=dossier`。

---

## 九、相關檔案速查

- Ranked API：`GET /api/v7/playbook/ranked` → `playbook.py`
- Today / header：`GET /api/v7/today` · `cc-header`
- UNKNOWN 根因：`playbook.py` L326–327 `_brief_ranked_fallback`（P0 已改為空欄位 + 不顯示）
- UI：`index.html` ~L1200–1600 ranked cards · `fetchRankedOpps()`
- 詳細 schema：`docs/PLAYBOOK_10_10_SPEC.md`
