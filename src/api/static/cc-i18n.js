/* cc-i18n.js — bilingual augmentation for Clarity Console.
 *
 * Goal: Traditional Chinese as the PRIMARY displayed language, English kept as
 * reference. Implemented as a runtime DOM augmentation layer rather than editing
 * the 14k-line template, so:
 *   - index.html static content is unchanged (every file-content test + the
 *     JS<->Python recovery-copy parity stay valid),
 *   - English substrings are preserved (assertions that look for them pass),
 *   - one dictionary is the single source of truth (maintainable, reversible).
 *
 * Mechanism: for LITERAL static leaf elements whose trimmed text exactly matches
 * a dictionary key, replace text with "<繁中> · <English>". x-text/x-html bound
 * nodes are skipped so we never fight Alpine reactivity. Idempotent: the
 * augmented string is not itself a key, so re-scans are no-ops.
 *
 * Authority note: this is presentation only. It never changes any data-cc /
 * data-cc-nav selector, never alters authority/banner logic, and is purely
 * additive. Banner copy emitted via x-text (cc-helpers.js) is intentionally not
 * touched here — that is localized in the helpers to preserve parity.
 */
(function () {
  "use strict";

  // English -> 繁體中文. Only literal, static UI labels belong here.
  var ZH = {
    // ── Guide / operator manual ──
    "Operator checklist": "操盤手檢查清單",
    "Page gate beats card rank": "頁面閘門優先於卡片排序",
    "Dashboard first": "先看儀表板",
    "Most common mistakes": "最常見錯誤",
    "When capital is allowed / blocked": "何時允許／禁止動用資金",
    "Capital allowed when": "允許動用資金的條件",
    "Capital blocked when": "禁止動用資金的條件",
    "Data fresh": "資料即時",
    "Engine confirmed": "引擎已確認",
    "Board gate open": "決策閘門開啟",
    "Current Build Reality Check": "目前版本實況檢查",
    "Broker truth": "券商真實狀態",
    "Probe health": "探測健康度",
    "Research": "研究",
    "Research-only": "僅供研究",
    "Diagnostic": "診斷",
    "Execution-dependent": "依賴執行",
    "Conditional": "視條件而定",
    "START HERE": "從這裡開始",
    "Entry Zone": "進場區間",
    "Hard Stop": "硬性止損",
    "Target 1 / 2": "目標 1 / 2",
    "Factor Chips": "因子標籤",
    "Sector Peers": "同業比較",
    "Why Now": "為何是現在",
    // ── Surface names / section headers ──
    "Overview": "總覽",
    "Dashboard": "儀表板",
    "Ranked": "排序",
    "Playbook": "策略簿",
    "Discovery": "探索",
    "Scanners": "掃描器",
    "Portfolio": "持倉",
    "Portfolio & Risk": "持倉與風險",
    "Search / Dossier": "搜尋／檔案",
    "Dossier": "檔案",
    "Funds": "基金",
    "Flow": "資金流",
    "Rejections": "否決",
    "Backtest Lab": "回測室",
    "Market Regime": "市場狀態",
    "Today's Mission": "今日任務",
    "Monitors": "監控清單",
    "Near-Miss": "接近達標",
    "Watch candidates": "觀察候選",
    "Risk": "風險",
    "Positions": "持倉部位",
    "Stops": "止損",
    "Drawdown": "回撤",
    "Sector Leadership": "板塊領導",
    "Breadth": "市場廣度",
    "Evidence": "證據",
    "Action": "操作",
    "Entry": "進場",
    "Stop": "止損",
    "Target": "目標",
    "Confidence": "信心度",
    "Setup": "型態",
    "Catalyst": "催化劑",
    "Key Risks": "主要風險",
    "Rationale": "理由",
    // ── Authority / posture / banner labels (static occurrences only) ──
    "CONFIRM ONLY": "僅確認",
    "Confirm-only — no IBKR handoff or sizing": "僅確認 — 無券商交付或部位估算",
    "Confirm-only — no IBKR handoff or sizing; levels indicative only": "僅確認 — 無券商交付或部位估算；價位僅供參考",
    "Confirm-only — no IBKR handoff or sizing; levels indicative until live dossier loads.": "僅確認 — 無券商交付或部位估算；價位僅供參考，直到即時檔案載入。",
    "EXEC BLOCKED": "禁止執行",
    "Execution truth not confirmed": "執行真實狀態未確認",
    "Research unavailable": "研究資料不可用",
    "INSTANT DEGRADED": "即時降級",
    "BROKER OFFLINE": "券商離線",
    "IBKR OFFLINE": "券商離線",
    "WAIT": "等待",
    "NO_TRADE": "禁止交易",
    "SELECTIVE": "選擇性進場",
    "PILOT": "試點",
    "TRADE": "可交易",
    "Reference only · Decision surfaces suspended": "僅供參考 · 決策介面已暫停",
    "Degraded — fallback watch (monitor-only)": "降級 — 後備觀察（僅監控）",
    "Degraded — confirm-only dossier": "降級 — 僅確認檔案",
    "Degraded / slow / partial data": "降級／緩慢／部分資料",
    // ── Common controls / status (static, non x-text) ──
    "Expand": "展開",
    "Collapse": "收合",
    "Connected": "已連接",
    "Refresh": "重新整理",
    "Retry": "重試",
    "Close": "關閉",
    "Confirm": "確認",
    "Cancel": "取消",
    "Apply": "套用",
    "Reset": "重設",
    "Save": "儲存",
    // ── Card columns, status words, surface terms (expanded coverage) ──
    "Core": "核心",
    "Regime": "市場狀態",
    "Status": "狀態",
    "Mode": "模式",
    "Type": "類型",
    "Ticker": "代碼",
    "Symbol": "代號",
    "Qty": "數量",
    "Size": "部位",
    "Value": "數值",
    "Use": "使用",
    "All": "全部",
    "Strategy": "策略",
    "Sleeve": "策略組",
    "Sleeve override": "策略組覆寫",
    "Sharpe": "夏普值",
    "Thesis": "論點",
    "Timing": "時機",
    "Trades": "交易",
    "Execution": "執行",
    "Handoff": "交付",
    "Broker": "券商",
    "Critical": "危急",
    "Monitor zone": "監控區",
    "Indicative entry": "參考進場",
    "Indicative target": "參考目標",
    "Watch upgrade": "觀察升級",
    "Why ranked here": "為何排在此處",
    "VIX Colour Scale": "VIX 色階",
    "VCP pattern": "VCP 型態",
    "Surface Mode Tags": "介面模式標籤",
    "None urgent": "無緊急事項",
    "Scanner warming": "掃描器預熱中",
    "Sizing suspended in fallback mode": "後備模式下暫停部位估算",
    "Setup forming but not triggered yet": "型態形成中，尚未觸發",
    // status badges (static legend occurrences only; x-text card badges skipped)
    "ENTRY": "進場",
    "STOP": "止損",
    "TARGET": "目標",
    "BUY": "買進",
    "WATCH": "觀察",
    "Watch": "觀察",
    "AVOID": "避免",
    "PAPER": "模擬倉",
    "LIVE": "即時",
    "READY": "就緒",
    "STALE": "過期",
    "BREAKER": "熔斷",
    "OFF": "關閉",
    // ── Status / guidance sentences (static occurrences) ──
    "Setup triggered · entry zone active now": "型態已觸發 · 進場區間現正有效",
    "Service down · signals may be stale": "服務中斷 · 訊號可能過期",
    "Risk-On · full position sizing": "風險偏好 · 全額部位",
    "Regime gate · sit out new risk": "狀態閘門 · 暫不承擔新風險",
    "Positive factor — works for the trade": "正面因子 — 有利於此交易",
    "Negative factor — works against it": "負面因子 — 不利於此交易",
    "No directional signal from this factor": "此因子無方向性訊號",
    "Portfolio advisory · not a new-entry signal": "投組建議 · 非新進場訊號",
    "Partial edge · half size · stop required": "部分優勢 · 半倉 · 須設止損",
    "Normal · standard sizing": "正常 · 標準部位",
    "No sizing guidance in confirm-only mode": "僅確認模式下無部位建議",
    "No hard blocks flagged from Ops snapshot": "Ops 快照未標記硬性阻擋",
    "Monitor · not ready for full size": "監控 · 尚未可全倉",
    "High · reduce size 50%": "高 · 減倉 50%",
    "Elevated · reduce size 25%": "升高 · 減倉 25%",
    "Good setup, wait for pullback to zone": "型態良好，等待回測至區間",
    "Extended or broken · skip new entry": "過度延伸或已破壞 · 略過新進場",
    "Got it — hide until reset": "知道了 — 隱藏至重設",
    "Layer 2 — How to Read the Platform": "第二層 — 如何解讀平台",
    "Layer 3 — Reference Manual": "第三層 — 參考手冊",
    "Illustrative examples only — reference surface, not live board data.": "僅為示意範例 — 參考介面，非即時看板資料。",
    "Health, rejections, ops visibility": "健康度、否決、運維可視性",
    "GATEWAY UP · LOGIN REQUIRED": "閘道已啟動 · 需登入",
    "Funds sleeves marked research/backtest — not live capital.": "基金策略組標記為研究／回測 — 非實盤資金。",
    "Flow surface in synthetic/mock mode — colour only.": "資金流介面為合成／模擬模式 — 僅供顏色參考。",
    "Discovery loading or 0 hits on WAIT day — often correct, not a miss.": "探索載入中或等待日 0 命中 — 通常正確，非遺漏。",
    "Portfolio or broker positions not reconciled after last session.": "上次工作階段後，投組或券商部位尚未對帳。",
    "Mode pill grey or Ops shows no fresh cycle — decisions stale or absent.": "模式標記為灰或 Ops 無最新週期 — 決策過期或缺失。",
    // ── Expand / Ops / loading (static + common labels) ──
    "Expand all": "一鍵展開",
    "Collapse all": "收合全部",
    "Dismiss": "關閉",
    "Loading…": "載入中…",
    "Loading decisions…": "載入決策中…",
    "Loading market data…": "載入市場資料中…",
    "Loading alert log…": "載入警報紀錄中…",
    "Loading reliability…": "載入可靠度中…",
    "Loading strategy health…": "載入策略健康度中…",
    "Loading fundamentals…": "載入基本面中…",
    "Loading peers…": "載入同業中…",
    "Loading options…": "載入期權中…",
    "Loading brief…": "載入晨報中…",
    "Loading readiness…": "載入就緒狀態中…",
    "Test Discord ping": "測試 Discord",
    "Resolve channel": "解析頻道",
    "Notification Events": "通知事件",
    "(optional)": "（選用）",
    "Health": "健康度",
    "Updates": "更新",
    "Error Log": "錯誤紀錄",
    "Operator board sections": "操盤看板區塊",
    "AI Vibe · monitor only": "AI 氛圍 · 僅監控",
    "monitor only": "僅監控",
    "Research / Monitoring only": "研究／監控專用",
    "Confirm-only": "僅確認",
    "Deploy review": "部署審閱",
    "Structure confirm": "結構確認",
    "Command": "指揮台",
    "Shadow Account": "影子帳戶",
    "Strategy Lab": "策略實驗室",
    "Agent": "Agent 盯盤",
    "Ops": "運維",
    "IBKR": "券商",
    "Guide": "指南",
    "More": "更多",
    "Repair": "修復",
    "ENGINE ON": "引擎運行",
    "ENGINE OFF": "引擎關閉",
    "DATA FRESH": "資料即時",
    "DATA STALE": "資料過期",
    "OFFLINE": "離線",
    "CONNECTED": "已連線",
    "Advanced diagnostics": "進階診斷",
    "Advanced diagnostics (collapsed)": "進階診斷（收合）"
  };

  var SEP = " · ";
  var ATTR = "data-zh-done";

  function augment(el) {
    if (!el || el.nodeType !== 1) return;
    if (el.getAttribute(ATTR)) return;
    // Never touch Alpine-bound text — that is owned by the helpers.
    if (el.hasAttribute("x-text") || el.hasAttribute("x-html")) return;
    // Only leaf labels: no child elements (avoids augmenting containers).
    if (el.querySelector("*")) return;
    var key = (el.textContent || "").trim();
    if (!key || !Object.prototype.hasOwnProperty.call(ZH, key)) return;
    el.textContent = ZH[key] + SEP + key;
    el.setAttribute(ATTR, "1");
  }

  var SEL = "span,div,a,button,td,th,h1,h2,h3,h4,h5,p,label,li,strong,b";

  function scan(root) {
    try {
      var nodes = (root || document).querySelectorAll(SEL);
      for (var i = 0; i < nodes.length; i++) augment(nodes[i]);
    } catch (e) {
      /* never let i18n break the app */
    }
  }

  function boot() {
    scan(document);
    try {
      var obs = new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var added = muts[i].addedNodes;
          if (!added) continue;
          for (var j = 0; j < added.length; j++) {
            var n = added[j];
            if (n.nodeType === 1) {
              augment(n);
              scan(n);
            }
          }
        }
      });
      obs.observe(document.body, { childList: true, subtree: true });
    } catch (e) {
      /* observer optional — initial scan already ran */
    }
  }

  if (document.readyState !== "loading") boot();
  else document.addEventListener("DOMContentLoaded", boot);

  // Expose for debugging / future toggle.
  window.CCI18N = { dict: ZH, scan: scan };
})();
