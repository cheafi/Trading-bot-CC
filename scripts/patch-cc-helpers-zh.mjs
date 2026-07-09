#!/usr/bin/env node
/** One-shot patch: comprehensive Chinese clarity helpers in cc-helpers.js */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FILE = path.join(ROOT, 'src/api/static/cc-helpers.js');
let js = fs.readFileSync(FILE, 'utf8');

if (js.includes('scopedFreshnessStripLocalized')) {
  console.log('cc-helpers.js already patched');
  process.exit(0);
}

const BILINGUAL_BLOCK = `
	var FRESHNESS_SCOPE_ZH = {
		Market: "市場",
		Board: "看板",
		Brief: "晨報",
		Broker: "券商",
		Runtime: "運行",
		Authority: "權限",
	}

	var FRESHNESS_STATE_ZH = {
		Fresh: "新鮮",
		Stale: "過期",
		Expired: "已失效",
		Fallback: "備援",
		Offline: "離線",
		Unavailable: "不可用",
		Open: "開放",
		Blocked: "禁止",
		Unknown: "未知",
	}

	function localizeFreshnessState(state) {
		var raw = String(state || "").trim()
		if (!raw) return raw
		var expired = raw.match(/^Expired\\s+(\\d+d)$/i)
		if (expired) return bilingualLine("已失效 " + expired[1], raw)
		var zh = FRESHNESS_STATE_ZH[raw]
		return zh ? bilingualLine(zh, raw) : raw
	}

	function localizeScopedFreshnessStrip(line) {
		var raw = String(line || "").trim()
		if (!raw) return raw
		return raw
			.split(/\\s*·\\s*/)
			.map(function (part) {
				var m = part.match(/^([A-Za-z]+):\\s*(.+)$/)
				if (!m) return part
				var scope = m[1]
				var state = String(m[2] || "").trim()
				var zhScope = FRESHNESS_SCOPE_ZH[scope] || scope
				return scope + ": " + state + " · " + zhScope + "：" + localizeFreshnessState(state)
			})
			.join(" · ")
	}

	function scopedFreshnessStripLocalized(truth) {
		return localizeScopedFreshnessStrip(scopedFreshnessStrip(truth))
	}

	var MISSION_BLOCKER_ZH = {
		"FALLBACK / BRIEF ONLY": "備援 / 僅簡報 — 不可部署",
		"BRIEF EXPIRED — not used for ranking": "晨報已失效 — 不用於排名",
		"BRIEF STALE": "晨報過期 — 敘述僅供參考",
		"Market: Stale": "市場資料過期 — 刷新後再定倉",
		"MARKET DATA UNAVAILABLE": "缺少即時報價",
		"BOARD STALE": "看板過期 — 刷新看板",
		"NO VALID BOARD": "無有效看板 — 今日不做",
		"DATA DEGRADED": "資料已降級",
		"ENGINE OFF": "引擎關閉 — 僅用預算看板",
		"ENGINE UNKNOWN": "引擎狀態不明",
		"IBKR OFFLINE": "IBKR 離線 — 不可交接",
		"EXEC BLOCKED — risk breaker": "執行阻斷 — 熔斷中",
		"BOARD WAIT — no deploy": "看板 WAIT — 僅監察，禁止部署",
		"RESEARCH ONLY — board gate": "僅研究 — 看板門檻關閉",
		"AUTHORITY SUSPENDED": "部署權限已暫停",
		"REGIME WAIT": "體制 WAIT — 等待確認",
		"REGIME NO TRADE": "體制禁止交易",
		"0 deploy-qualified — gates not met": "0 筆可部署 — 門檻未過",
		"FETCH FAILED — not decision-grade": "擷取失敗 — 不可作決策依據",
	}

	function localizeMissionBlocker(label) {
		var raw = String(label || "").trim()
		if (!raw) return raw
		if (raw.indexOf("IBKR") === 0) {
			var tail = raw.replace(/^IBKR\\s*/i, "").trim()
			if (tail === "OFFLINE" || tail === "LOGIN" || tail === "DISCONNECTED") {
				return bilingualLine("IBKR " + (tail === "LOGIN" ? "需登入" : "離線") + " — 不可交接", raw)
			}
		}
		var zh = MISSION_BLOCKER_ZH[raw]
		return zh ? bilingualLine(zh, raw) : raw
	}

	function localizeMissionBlockerList(items) {
		return (items || []).map(localizeMissionBlocker)
	}

	function systemTruthMissionBlockersLocalized(truth) {
		return localizeMissionBlockerList(systemTruthMissionBlockers(truth))
	}
`;

js = js.replace(
  'function bilingualLine(zh, en) {\n\t\tif (zh && en) return zh + " · " + en\n\t\treturn zh || en || ""\n\t}\n\n\tvar OPERATOR_WHY_ZH',
  `function bilingualLine(zh, en) {\n\t\tif (zh && en) return zh + " · " + en\n\t\treturn zh || en || ""\n\t}\n${BILINGUAL_BLOCK}\n\tvar OPERATOR_WHY_ZH`,
);

js = js.replace(
  'return bilingualLine("不可定倉、不可交接 IBKR、不可試單", raw)',
  'return bilingualLine("不定倉、不交接券商、不可試探倉", raw)',
);

js = js.replace(
  `function globalTruthStrip(truth) {
\t\tvar t = truth || {}
\t\tif (t.truth_strip) return String(t.truth_strip)
\t\tif (typeof scopedFreshnessStrip === "function") return scopedFreshnessStrip(t)
\t\treturn "Monitor only — see scoped truth strip"
\t}`,
  `function globalTruthStrip(truth) {
\t\tvar t = truth || {}
\t\tif (t.truth_strip) return localizeScopedFreshnessStrip(String(t.truth_strip))
\t\tif (typeof scopedFreshnessStrip === "function") return scopedFreshnessStripLocalized(t)
\t\treturn bilingualLine("僅監察 — 請查看上方狀態列", "Monitor only — see scoped truth strip")
\t}`,
);

js = js.replace('badge: "Agent 盯盤 · Monitor only"', 'badge: "Agent 盯盤 · 僅監察 · Monitor only"');

js = js.replace(
  `\t\treturn out
\t}

\tfunction systemTruthMissionBlockers(truth) {`,
  `\t\treturn out.map(localizeMissionBlocker)
\t}

\tfunction systemTruthMissionBlockers(truth) {`,
);

js = js.replace(
  `if (!n && !nm) return "Monitors"
\t\tvar prefix = n && (isNaN(wq) || wq === 0) ? "Fallback monitors" : "Monitors"
\t\tvar base = n ? prefix + " (" + n + ")" : prefix
\t\treturn nm ? base + " · " + nm + " near-miss" : base`,
  `if (!n && !nm) return bilingualLine("監察清單", "Monitors")
\t\tvar prefix = n && (isNaN(wq) || wq === 0) ? bilingualLine("備援監察", "Fallback monitors") : bilingualLine("監察清單", "Monitors")
\t\tvar base = n ? prefix + " (" + n + ")" : prefix
\t\treturn nm ? base + " · " + nm + " " + bilingualLine("筆近失", "near-miss") : base`,
);

js = js.replace(
  'return "No card-level gate flags"',
  'return bilingualLine("無卡片級門檻標記", "No card-level gate flags")',
);
js = js.replace('return "None flagged"', 'return bilingualLine("無標記", "None flagged")');

js = js.replace(
  `if (o.waitDay && o.hasSystem) {
\t\t\treturn "System blockers · gate flags"
\t\t}
\t\tif (o.waitDay) {
\t\t\treturn "Gate flags"
\t\t}
\t\treturn o.hasSystem ? "System blockers" : "Blockers"`,
  `if (o.waitDay && o.hasSystem) {
\t\t\treturn bilingualLine("系統阻斷 · 門檻標記", "System blockers · gate flags")
\t\t}
\t\tif (o.waitDay) {
\t\t\treturn bilingualLine("門檻標記", "Gate flags")
\t\t}
\t\treturn o.hasSystem ? bilingualLine("系統阻斷", "System blockers") : bilingualLine("阻斷項", "Blockers")`,
);

js = js.replace(
  'var DOSSIER_CONFIRM_ONLY_SIZING = "No sizing guidance in confirm-only mode"',
  'var DOSSIER_CONFIRM_ONLY_SIZING = "Confirm-only 不定倉 · No sizing guidance in confirm-only mode"',
);

js = js.replace(
  'var DOSSIER_MONITOR_RULE_HINT = "Alert only · 僅提醒，不可定倉、不可交接 · no sizing · no handoff"',
  'var DOSSIER_MONITOR_RULE_HINT = "Alert only · 僅提醒 — 不定倉、不交接券商 · no sizing · no handoff"',
);

const PLAYBOOK_GATE = `
	function playbookCardGateLine(status, detail) {
		var su = String(status || "WATCH").toUpperCase().replace(/[^A-Z0-9]+/g, " ").trim()
		var d = String(detail || "").trim()
		if (!d) {
			if (su === "BLOCKED") return bilingualLine("禁止部署 — 門檻未齊", "Deploy blocked — gates incomplete")
			if (su === "AVOID" || su === "NO TRADE") return bilingualLine("避免 — 不可部署", "Avoid — not deploy-ready")
			return String(status || "WATCH").replace(/_/g, " ") + " — " + bilingualLine("僅監察", "monitor only")
		}
		d = d.replace(/^(AVOID|BLOCKED|WATCH|NO_TRADE|PILOT|FALLBACK WATCH)\\s*[·\\-\\—:\\u2014]\\s*/i, "").trim()
		if (su === "BLOCKED") return bilingualLine("禁止部署 — " + d, "Deploy blocked — " + d)
		if (su === "AVOID" || su === "NO TRADE") return bilingualLine("避免 — " + d, "Avoid — " + d)
		return String(status || "WATCH").replace(/_/g, " ") + " — " + d
	}

	function localizeHeaderSurface(copy) {
		return copy || {}
	}

	function localizeFetchStateCopy(copy) {
		return copy || {}
	}

	function surfaceEmptyStateCopy(kind) {
		return { headline: "", detail: "", badge: kind || "", cta: "" }
	}
`;

js = js.replace('\tvar WORKSTATION_PANEL_TITLES = {', PLAYBOOK_GATE + '\n\tvar WORKSTATION_PANEL_TITLES = {');

js = js.replace(
  '\t\tscopedFreshnessStrip: scopedFreshnessStrip,\n\t\tsystemTruthMissionBlockers: systemTruthMissionBlockers,',
  `\t\tscopedFreshnessStrip: scopedFreshnessStrip,
\t\tscopedFreshnessStripLocalized: scopedFreshnessStripLocalized,
\t\tlocalizeScopedFreshnessStrip: localizeScopedFreshnessStrip,
\t\tlocalizeMissionBlocker: localizeMissionBlocker,
\t\tlocalizeMissionBlockerList: localizeMissionBlockerList,
\t\tsystemTruthMissionBlockers: systemTruthMissionBlockers,
\t\tsystemTruthMissionBlockersLocalized: systemTruthMissionBlockersLocalized,
\t\tplaybookCardGateLine: playbookCardGateLine,
\t\tlocalizeHeaderSurface: localizeHeaderSurface,
\t\tlocalizeFetchStateCopy: localizeFetchStateCopy,
\t\tsurfaceEmptyStateCopy: surfaceEmptyStateCopy,`,
);

fs.writeFileSync(FILE, js);
console.log('patched', FILE);
