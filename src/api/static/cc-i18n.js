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
    "Reset first-visit flag": "重設首次造訪標記",
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
    "Save": "儲存"
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
