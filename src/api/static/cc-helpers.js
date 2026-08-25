/**
 * CC · Clarity Console — Phase 1 Alpine companion helpers.
 * Loaded before Alpine in index.html; mirrors fetch_surface_state.py copy.
 */
;(function (global) {
	"use strict"

	var SEVERITY_BADGE_CLASS = {
		failed_fetch: "pr",
		failed_fetch_fallback: "pr",
		execution_blocked: "pr",
		stale: "pa",
		fallback: "pa",
		partial: "pa",
		loading: "pa",
		probe_only: "pw",
		runtime_unknown: "pw",
		research_only: "pw",
		mock_only: "pw",
		no_data: "pw",
		not_authoritative: "pw",
		ok: "pg",
		unavailable: "pr",
		retry_recommended: "pa",
	}

	var SURFACE_WARMUP_LOADING_LINES = {
		dossier_research: "Dossier warming — retry after core panels load.",
		backtest_research: "Backtest warming — research shell may appear before live stats load.",
		funds_research: "Funds warming — sleeve cards refresh when the API is ready.",
		rejections_diagnostic: "Rejections warming — blocker audit will fill in shortly.",
		flow_supporting: "Flow warming — research shell may appear before live provider connects.",
		ops_diagnostic: "Ops warming — refresh in a few seconds.",
		ibkr_execution: "IBKR warming — probe status may show LOGIN; wait for /health mode=full.",
		"": "Backend warming — retry in a few seconds.",
	}

	function severityBadgeClass(state) {
		var s = String(state || "").toLowerCase()
		return SEVERITY_BADGE_CLASS[s] || "pw"
	}

	function surfaceWarmupLoadingLine(surfaceMode) {
		var key = String(surfaceMode || "").trim()
		return SURFACE_WARMUP_LOADING_LINES[key] || SURFACE_WARMUP_LOADING_LINES[""]
	}

	function warmupStatusLine(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		if (o.apiReachable === false) {
			return _opsBilingual(
				"離線 — API 不可達；快取 snapshot 可能過期",
				"OFFLINE - API unreachable; cached snapshot may be stale",
			)
		}
		if (mode === "loading") {
			return _opsBilingual("預熱中 — full 前只 monitor", "WARMING - monitor-only until full")
		}
		if (o.instantDegraded || o.fetchFailed) {
			return _opsBilingual(
				"降級 — 僅 snapshot 直至 live ranked 返回",
				"DEGRADED - snapshot only until live ranked data returns",
			)
		}
		if (mode === "full") {
			return _opsBilingual(
				"即時 — fetch badges 清除後 ranked 為權威",
				"LIVE - ranked payloads are authoritative when fetch badges clear",
			)
		}
		return _opsBilingual(
			"載入中 — 探測 health 前勿視 board 為 live",
			"LOADING - probing health before treating the board as live",
		)
	}

	function warmupUpgradeQueue(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		if (mode !== "loading" && !o.briefFallback) return ""
		var parts = [
			_opsBilingual("live ranked playbook", "live ranked playbook"),
			_opsBilingual("today council reconciliation", "today council reconciliation"),
			_opsBilingual("dossier enrichment", "dossier enrichment"),
		]
		if (o.nearMiss || o.briefFallback) {
			parts.unshift(
				_opsBilingual(
					"monitor queue (brief near-miss + top watch)",
					"monitor queue (brief near-miss + top watch)",
				),
			)
		}
		return _opsBilingual("下一步", "Next") + ": " + parts.join(" · ")
	}

	/** Instant banner wins over warmup strip — avoids duplicate WARMING copy. */
	function warmupContextStripVisible(opts) {
		var o = opts || {}
		if (o.tab === "guide") return false
		if (!(o.warmupStatusLine || o.warmupUpgradeQueue)) return false
		if (o.instantBannerVisible) return false
		return !!o.dataContractStripVisible
	}

	function loadingSessionRecoveryLine(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		var ccMode = String(o.ccMode || "").toUpperCase()
		if (mode !== "loading" && ccMode !== "LOADING") return ""
		return _opsBilingual(
			"冷啟動 — 等待 /health mode=full；載入逾 ~2 分鐘可重啟一次",
			"Cold start - wait for /health mode=full; restart once if loading exceeds ~2 min",
		)
	}

	function instantDegradedBannerHint(healthData) {
		var h = healthData || {}
		if (String(h.mode || "").toLowerCase() === "loading") {
			var up = Math.round(Number(h.uptime_seconds) || 0)
			return (
				"Wait for /health mode=full before sizing or IBKR handoff · uptime " +
				up +
				"s · data contract stays authoritative if you dismiss"
			)
		}
		return "Refresh when fetch badges clear · page gates still apply"
	}

	function todayMissionMonitorsLabel(monitors, nearMissCount, watchQualified) {
		var n = (monitors || []).length
		var nm = Number(nearMissCount) || 0
		var wq = Number(watchQualified)
		if (!n && !nm) return _opsBilingual("監控", "Monitors")
		var prefix =
			n && (isNaN(wq) || wq === 0)
				? _opsBilingual("後備監控", "Fallback monitors")
				: _opsBilingual("監控", "Monitors")
		var base = n ? prefix + " (" + n + ")" : prefix
		return nm ? base + " · " + nm + " " + _opsBilingual("接近達標", "near-miss") : base
	}

	/** Clarifies monitor vs near-miss vs deploy — attention routing without tradability. */
	function todayMissionQuantClusterLines(hints) {
		var list = hints || []
		var lines = []
		for (var i = 0; i < list.length && lines.length < 3; i++) {
			var h = list[i] || {}
			var label = String(h.label || "").trim()
			if (!label) label = String(h.cluster || "").trim()
			var detail = String(h.detail || "").trim()
			var line =
				label +
				(detail && detail.length <= 72
					? " — " + detail
					: " — " + _opsBilingual("只供 monitor，不可 deploy", "monitor only, not deploy"))
			if (line && lines.indexOf(line) < 0) lines.push(line)
		}
		return lines
	}

	function todayBoardHeroSynthesisLine(opts) {
		var o = opts || {}
		if (!o.waitDay) return ""
		var parts = []
		var hints = o.quantClusterHints || []
		if (hints.length) {
			var h0 = hints[0] || {}
			var label = String(h0.label || "").trim()
			if (!label) label = String(h0.cluster || "").trim()
			var detail = String(h0.detail || "").trim()
			if (label) {
				var qp = label
				if (detail && detail.length <= 48) qp += " (" + detail + ")"
				else if (detail) qp += " — monitor context"
				parts.push(qp)
			}
		}
		var diag = o.noSetupDiagnosis || {}
		var blocker = String(diag.primary_blocker || diag.headline || "").trim()
		if (blocker) parts.push(blocker)
		if (!parts.length) return ""
		return (
			_opsBilingual("Monitor 脈絡", "Monitor context") +
			": " +
			parts.join(" · ") +
			" " +
			_opsBilingual("— 非 deploy 許可", "— not deploy permission")
		)
	}

	function todayExecutionReadinessDiagnostic(er) {
		var e = er || {}
		var sub = e.sub_status || {}
		var gaps = []
		if (sub.broker_transport !== "up") gaps.push(_opsBilingual("傳輸 down", "transport down"))
		if (sub.session_auth !== "active") gaps.push(_opsBilingual("session 未啟動", "session inactive"))
		if (sub.engine !== "on") gaps.push(_opsBilingual("引擎 off", "engine off"))
		if (sub.handoff_readiness !== "ready") gaps.push(_opsBilingual("handoff 阻擋", "handoff blocked"))
		if (sub.bracket_readiness !== "ready") gaps.push(_opsBilingual("bracket 草稿", "bracket draft"))
		if (e.circuit_breaker) gaps.push(_opsBilingual("熔斷 on", "breaker on"))
		if (!gaps.length && e.trade_handoff_ready) return ""
		var reasons = (e.degraded_reasons || []).slice(0, 2)
		var base =
			_opsBilingual("執行診斷", "Exec diagnostic") +
			": " +
			(gaps.length
				? gaps.join(" · ")
				: String(e.readiness_label || _opsBilingual("路徑不完整", "path incomplete")))
		if (reasons.length) base += " — " + reasons.join("; ")
		return base + " " + _opsBilingual("(非 deploy 權威)", "(not deploy authority)")
	}

	function playbookStrategyDecayLine(row) {
		var r = row || {}
		return String(r.strategy_decay_line || "").trim()
	}

	function todayMissionMonitorsColumnHint(opts) {
		var o = opts || {}
		var wq = Number(o.watchQualified)
		var mc = Number(o.monitorCount) || 0
		if (!isNaN(wq) && wq > 0) {
			return localizeUiText(
				wq + " watch-qualified on funnel — mission tickers are attention queue, not extra KPI count",
			)
		}
		if (mc > 0) {
			return localizeUiText(
				"Fallback monitors — scan / near-miss queue; filter_funnel is authority for watch-qualified",
			)
		}
		if (o.waitDay) {
			return localizeUiText("Near-miss · watch queue — priority only, not deploy on WAIT")
		}
		return localizeUiText("Watch / near-miss — ranking for attention, not handoff permission")
	}

	function playbookWhatToMonitorLine(opts) {
		var o = opts || {}
		if (!o.waitDay) return ""
		var sym = String(o.topSymbol || "")
			.trim()
			.toUpperCase()
		var nm = Number(o.nearMissCount) || 0
		var parts = []
		if (sym) parts.push(sym + " upgrade triggers")
		if (nm) parts.push(nm + " near-miss row" + (nm === 1 ? "" : "s"))
		parts.push("deploy unlock checklist below")
		return (
			_opsBilingual("只 monitor", "Monitor only") +
			" - " +
			parts.join(" · ") +
			" " +
			_opsBilingual("— 無 deploy 權威", "— no deploy authority")
		)
	}

	function todayMissionWaitSubtitle(opts) {
		if (!opts || !opts.waitDay) return ""
		return localizeUiText("Deploy blocked — use monitors and Playbook ranking only")
	}

	function todayMissionSystemBlockers(opts) {
		var o = opts || {}
		var out = []
		if (!o.ibkrReady) {
			var ib = String(o.ibkrShort || "OFFLINE")
				.trim()
				.toUpperCase()
			out.push(ib.indexOf("IBKR") === 0 ? ib : "IBKR " + ib)
		}
		if (!o.engineRunning) {
			out.push("ENGINE OFF")
		}
		if (o.breaker) {
			out.push("EXEC BLOCKED")
		}
		var tier = String(o.dataTier || "").toUpperCase()
		if (tier === "STALE" || tier === "CRITICAL") {
			out.push("DATA " + tier)
		}
		var fb = String(o.fetchBadge || "").toUpperCase()
		if (fb === "FALLBACK") {
			out.push("BRIEF ONLY")
		} else if (fb === "FETCH FAILED") {
			out.push("FETCH FAILED")
		}
		if (o.briefFallback || o.instantDegraded) {
			var hasFb = out.some(function (x) {
				return x.indexOf("FALLBACK") >= 0 || x.indexOf("BRIEF") >= 0
			})
			if (!hasFb) {
				out.push("BRIEF ONLY")
			}
		}
		return out
	}

	function todayMissionBlockersTitle(opts) {
		var o = opts || {}
		if (o.waitDay && o.hasSystem) {
			return _opsBilingual("系統阻擋 · 閘門標記", "System blockers · gate flags")
		}
		if (o.waitDay) {
			return _opsBilingual("閘門標記", "Gate flags")
		}
		return o.hasSystem ? _opsBilingual("系統阻擋", "System blockers") : _opsBilingual("阻擋", "Blockers")
	}

	function todayMissionEmptyBlockersCopy(opts) {
		var o = opts || {}
		if ((o.systemBlockers || []).length && !(o.cardGates || []).length) {
			return _opsBilingual("無卡片級閘門標記", "No card-level gate flags")
		}
		return _opsBilingual("未標記", "None flagged")
	}

	function localizeIbkrBracketReason(reason) {
		var r = String(reason || "").trim()
		if (!r) return ""
		if (r.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(r)) return r
		var map = {
			"Bracket builder is available but not fully configured. Do not treat a connected broker alone as sufficient protection; confirm stop / target logic before transmit.":
				"Bracket 建構器可用但未完整設定；勿將「已連線」當作足夠保護，送出前請確認止損／目標邏輯。 · Bracket builder available — confirm stop/target before transmit.",
			"Connect IB Gateway session first": "請先連線 IB Gateway · Connect IB Gateway session first",
			"Waiting for nextValidId / order queue":
				"等待 nextValidId／訂單佇列 · Waiting for nextValidId / order queue",
			"Bracket preview pending stop + target fields":
				"Bracket 預覽待填止損＋目標 · Bracket preview pending stop + target",
			"Bracket builder ready — parent + OCA children on transmit":
				"Bracket 已就緒 — 送出時 parent + OCA 子單 · Bracket builder ready on transmit",
		}
		return map[r] || r
	}

	function localizeOperatorCopy(text) {
		var t = String(text || "").trim()
		if (!t) return ""
		var map = {
			"gates active": "閘門生效 · gates active",
			"refresh live data": "重新整理即時資料 · refresh live data",
			"verify execution readiness": "確認執行就緒 · verify execution readiness",
			"API fetch failed": "API 擷取失敗 · API fetch failed",
			"live provider not connected": "即時供應商未連線 · live provider not connected",
			"await live fund data": "等待即時基金資料 · await live fund data",
			"live fund/index posture unavailable": "即時基金／指數姿態不可用 · live fund/index posture unavailable",
			"size only deploy-qualified": "僅對 deploy-qualified 估算部位 · size only deploy-qualified",
			"review levels; no handoff until gates open":
				"檢視價位；閘門開啟前勿 handoff · review levels; no handoff until gates open",
			"confirm in Playbook only": "僅於 Playbook 確認 · confirm in Playbook only",
			"run live scan": "執行即時掃描 · run live scan",
			"index/core posture only": "僅指數／核心姿態 · index/core posture only",
			"no sleeve allocation today; repair market data first":
				"今日不做 sleeve 配置；先修復市場資料 · no sleeve allocation today; repair market data first",
		}
		if (map[t]) return map[t]
		return t
	}

	function localizeOpsRuntimeText(text) {
		var t = String(text || "").trim()
		if (!t) return ""
		if (t.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(t)) return t
		var exact = {
			"Probe only — runtime unconfirmed": "僅探測 — 執行時未確認 · Probe only — runtime unconfirmed",
			"Probe failed — no runtime path": "探測失敗 — 無執行路徑 · Probe failed — no runtime path",
			"Probe failed or component down": "探測失敗或元件離線 · Probe failed or component down",
			"Probe warming — reachability not confirmed":
				"探測預熱 — 可達性未確認 · Probe warming — reachability not confirmed",
			"Probe available · runtime unknown": "探測可用 · 執行時未知 · Probe available · runtime unknown",
			"Runtime none this session": "本 session 無執行時證據 · Runtime none this session",
			"No cycle executed": "未執行 cycle · No cycle executed",
			"No cycle executed this session": "本 session 未執行 cycle · No cycle executed this session",
			"Cycle executed — regime output present":
				"已執行 cycle — 體制輸出存在 · Cycle executed — regime output present",
			"Engine off — no runtime path": "引擎關閉 — 無執行路徑 · Engine off — no runtime path",
			"Session active — no order test this session":
				"Session 已連線 — 本 session 未測試下單 · Session active — no order test this session",
			"Gateway reachable — session inactive":
				"Gateway 可達 — session 未啟動 · Gateway reachable — session inactive",
			"Live handoff exercised this session":
				"本 session 已演練 live handoff · Live handoff exercised this session",
			"Not connected — IBKR tab → Connect (Gateway may still be up; no TCP probe)":
				"未連線 — 至 IBKR 分頁 Connect（Gateway 可能仍運行；無 TCP 探測） · Not connected — IBKR tab → Connect (Gateway may still be up; no TCP probe)",
			"Connect failed — verify Gateway host:port and API client ID":
				"連線失敗 — 請確認 Gateway host:port 與 API client ID · Connect failed — verify Gateway host:port and API client ID",
			"Handshake incomplete — retry Connect on IBKR tab":
				"握手未完成 — 請於 IBKR 分頁重試 Connect · Handshake incomplete — retry Connect on IBKR tab",
			"No cache generated": "未產生快取 · No cache generated",
			"No runtime sample": "無執行時樣本 · No runtime sample",
			"Probe OK": "探測 OK · Probe OK",
			Warming: "預熱中 · Warming",
			FAIL: "失敗 · FAIL",
			Connected: "已連線 · Connected",
			Disconnected: "未連線 · Disconnected",
			Available: "可用 · Available",
			Down: "離線 · Down",
			"Gateway OK": "Gateway 正常 · Gateway OK",
			"Not connected": "未連線 · Not connected",
			"Session active": "Session 已連線 · Session active",
			"Service unavailable": "服務不可用 · Service unavailable",
			"Service available, no runtime output this session":
				"服務可用，本 session 無執行輸出 · Service available, no runtime output this session",
			"Service available, runtime output this session":
				"服務可用，本 session 有執行輸出 · Service available, runtime output this session",
			"Connected — live handoff exercised": "已連線 — 已演練 live handoff · Connected — live handoff exercised",
			"Connected — handoff not exercised this session":
				"已連線 — 本 session 未演練 handoff · Connected — handoff not exercised this session",
			"Gateway reachable — no live handoff possible":
				"Gateway 可達 — 無法 live handoff · Gateway reachable — no live handoff possible",
			"Unreachable, no live handoff possible":
				"不可達，無法 live handoff · Unreachable, no live handoff possible",
			"Probe failed — no runtime consumption possible":
				"探測失敗 — 無法執行時消費 · Probe failed — no runtime consumption possible",
			"Consumed in last completed engine cycle":
				"最近完成的 engine cycle 已消費 · Consumed in last completed engine cycle",
			"Brief on disk — not consumed by engine this session":
				"磁碟 brief 存在 — 本 session engine 未消費 · Brief on disk — not consumed by engine this session",
			"Reachable, but not recently consumed by a completed engine cycle":
				"可達，但最近完成的 engine cycle 未消費 · Reachable, but not recently consumed by a completed engine cycle",
			"Not loaded": "未載入 · Not loaded",
			"Insufficient sample": "樣本不足 · Insufficient sample",
			Inactive: "未啟用 · Inactive",
			Active: "有效 · Active",
			Stale: "過期 · Stale",
			"Engine not running": "引擎未運行 · Engine not running",
			"Click refresh or start engine": "點擊重新整理或啟動引擎 · Click refresh or start engine",
			"Evidence available": "已有證據 · Evidence available",
			"Data older than threshold": "資料超過閾值 · Data older than threshold",
		}
		if (exact[t]) return exact[t]
		if (/^Need (\d+)\+ observations \(have (\d+)\)$/.test(t)) {
			var need = t.match(/^Need (\d+)\+ observations \(have (\d+)\)$/)
			return _opsBilingual("需 " + need[1] + "+ 筆觀測（現有 " + need[2] + "）", t)
		}
		if (/^Consumed in completed cycle/.test(t)) {
			return (
				"於完成的 cycle 中已消費（" +
				t.replace(/^Consumed in completed cycle \(/, "").replace(/\)$/, "") +
				"） · " +
				t
			)
		}
		if (/^Routed in session/.test(t)) {
			return "本 session 已路由 · " + t
		}
		if (/^Insufficient sample/.test(t)) {
			return "樣本不足 · " + t
		}
		if (/^\d+ cached recs generated$/.test(t)) {
			return "已產生 " + t.replace(" cached recs generated", "") + " 筆快取 rec · " + t
		}
		if (/^\d+ closed trades in runtime sample$/.test(t)) {
			return "執行時樣本含 " + t.replace(" closed trades in runtime sample", "") + " 筆平倉 · " + t
		}
		if (/^Backend warming/.test(t) || /^Backend child failed/.test(t)) {
			return "後端預熱／失敗 · " + t
		}
		// System verdict + detail
		var verdictMap = {
			"NOT READY FOR LIVE EXECUTION": _opsBilingual("未就緒 — 不宜 live 執行", "NOT READY FOR LIVE EXECUTION"),
			"NOT READY FOR PAPER EXECUTION": _opsBilingual("未就緒 — 不宜 paper 執行", "NOT READY FOR PAPER EXECUTION"),
			"PAPER EXECUTION READY": _opsBilingual("Paper 執行就緒", "PAPER EXECUTION READY"),
			"LIVE EXECUTION READY": _opsBilingual("Live 執行就緒", "LIVE EXECUTION READY"),
			"API WARMING — NOT RUNNABLE": _opsBilingual("API 預熱 — 不可運行", "API WARMING — NOT RUNNABLE"),
			"Circuit breaker active — do not deploy capital": _opsBilingual(
				"熔斷生效 — 勿部署資金",
				"Circuit breaker active — do not deploy capital",
			),
			"Engine stopped — infrastructure may be up but trading loop is off": _opsBilingual(
				"引擎已停 — 基礎設施可能正常但交易迴圈關閉",
				"Engine stopped — infrastructure may be up but trading loop is off",
			),
			"Paper/dry-run path can accept handoff after checklist": _opsBilingual(
				"Paper/dry-run 路徑 — 檢查清單後可 handoff",
				"Paper/dry-run path can accept handoff after checklist",
			),
			"Paper mode — complete operator checklist before trusting signals": _opsBilingual(
				"Paper 模式 — 信任訊號前請完成操作檢查清單",
				"Paper mode — complete operator checklist before trusting signals",
			),
			"Engine running live — verify gates and risk before deploy": _opsBilingual(
				"引擎 live 運行 — 部署前請確認閘門與風險",
				"Engine running live — verify gates and risk before deploy",
			),
			"Live mode — blockers remain on execution path": _opsBilingual(
				"Live 模式 — 執行路徑仍有阻擋",
				"Live mode — blockers remain on execution path",
			),
		}
		if (verdictMap[t]) return verdictMap[t]
		// Execution readiness layers
		var layerMap = {
			"Service reachable": _opsBilingual("服務可達", "Service reachable"),
			"Engine running": _opsBilingual("引擎運行", "Engine running"),
			"Scheduler alive": _opsBilingual("排程存活", "Scheduler alive"),
			"Session auth": _opsBilingual("Session 驗證", "Session auth"),
			"Order path tested": _opsBilingual("下單路徑已測", "Order path tested"),
			"Engine handoff": _opsBilingual("引擎 handoff", "Engine handoff"),
			"Last successful cycle": _opsBilingual("上次成功 cycle", "Last successful cycle"),
			"Gateway / market data probe": _opsBilingual("Gateway／市場資料探測", "Gateway / market data probe"),
			"Trading loop": _opsBilingual("交易迴圈", "Trading loop"),
			"IBKR login / Alpaca keys": _opsBilingual("IBKR 登入／Alpaca 金鑰", "IBKR login / Alpaca keys"),
			"Paper/live order exercised this session": _opsBilingual(
				"本 session 已演練 paper/live 下單",
				"Paper/live order exercised this session",
			),
			"Broker + engine ready for orders": _opsBilingual("券商＋引擎可下單", "Broker + engine ready for orders"),
			"No cycle timestamp": _opsBilingual("無 cycle 時間戳", "No cycle timestamp"),
			"NOT ACTIVE": _opsBilingual("未啟用", "NOT ACTIVE"),
			"NONE TODAY": _opsBilingual("今日無", "NONE TODAY"),
		}
		if (layerMap[t]) return layerMap[t]
		// Next actions + blockers (common)
		var opsCopyMap = {
			"Start trading engine": _opsBilingual("啟動交易引擎", "Start trading engine"),
			"Loop is stopped — nothing else will run": _opsBilingual(
				"迴圈已停 — 其他程序不會運行",
				"Loop is stopped — nothing else will run",
			),
			"Verify scheduler heartbeat": _opsBilingual("確認排程心跳", "Verify scheduler heartbeat"),
			"Run one full engine scan cycle": _opsBilingual(
				"執行一次完整 engine 掃描 cycle",
				"Run one full engine scan cycle",
			),
			"Confirms signal + cache pipeline": _opsBilingual("確認訊號＋快取管線", "Confirms signal + cache pipeline"),
			"Confirm broker auth / paper session login": _opsBilingual(
				"確認券商驗證／paper session 登入",
				"Confirm broker auth / paper session login",
			),
			"Gateway up but IBKR session not active": _opsBilingual(
				"Gateway 正常但 IBKR session 未啟動",
				"Gateway up but IBKR session not active",
			),
			"Start IB Gateway / verify host:port": _opsBilingual(
				"啟動 IB Gateway／確認 host:port",
				"Start IB Gateway / verify host:port",
			),
			"Broker path unreachable": _opsBilingual("券商路徑不可達", "Broker path unreachable"),
			"Refresh recommendation cache": _opsBilingual("重新整理推薦快取", "Refresh recommendation cache"),
			"Today tab needs cached ranked recs": _opsBilingual(
				"今日分頁需要快取排名推薦",
				"Today tab needs cached ranked recs",
			),
			"Inspect filter funnel / regime gate": _opsBilingual(
				"檢查篩選漏斗／體制閘門",
				"Inspect filter funnel / regime gate",
			),
			"Cycles ran but zero signals": _opsBilingual("已跑 cycle 但零訊號", "Cycles ran but zero signals"),
			"Monitor positions, alerts, and last successful times": _opsBilingual(
				"監控持倉、警示與上次成功時間",
				"Monitor positions, alerts, and last successful times",
			),
			"Core loop appears healthy": _opsBilingual("核心迴圈看似健康", "Core loop appears healthy"),
			"Wait for /health mode=full on :8001": _opsBilingual(
				"等待 /health mode=full（:8001）",
				"Wait for /health mode=full on :8001",
			),
			"Full backend runs component probes and engine telemetry": _opsBilingual(
				"完整後端會跑元件探測與引擎遙測",
				"Full backend runs component probes and engine telemetry",
			),
			"Refresh Ops health panel": _opsBilingual("重新整理 Ops 健康面板", "Refresh Ops health panel"),
			"Probe vs runtime table updates after import completes": _opsBilingual(
				"import 完成後探測 vs 執行時表會更新",
				"Probe vs runtime table updates after import completes",
			),
			"No engine cycle this session": _opsBilingual("本 session 無 engine cycle", "No engine cycle this session"),
			"No successful engine cycle this session": _opsBilingual(
				"本 session 無成功 engine cycle",
				"No successful engine cycle this session",
			),
			"No engine cycle completed today": _opsBilingual(
				"今日未完成 engine cycle",
				"No engine cycle completed today",
			),
			"No scheduler job confirmed today": _opsBilingual("今日未確認排程工作", "No scheduler job confirmed today"),
			"Recommendation cache empty": _opsBilingual("推薦快取為空", "Recommendation cache empty"),
			"Broker gateway reachable but session auth inactive": _opsBilingual(
				"Gateway 可達但 session 驗證未啟動",
				"Broker gateway reachable but session auth inactive",
			),
			"Signal pipeline produced zero signals today": _opsBilingual(
				"訊號管線今日產出零訊號",
				"Signal pipeline produced zero signals today",
			),
			"Broker path not reachable — paper handoff unavailable": _opsBilingual(
				"券商路徑不可達 — paper handoff 不可用",
				"Broker path not reachable — paper handoff unavailable",
			),
			"Backend importing on :8001": _opsBilingual("後端 :8001 匯入中", "Backend importing on :8001"),
			"Market data probe not confirmed — wait for full API": _opsBilingual(
				"市場資料探測未確認 — 等待完整 API",
				"Market data probe not confirmed — wait for full API",
			),
			"Not available — engine not started this session": _opsBilingual(
				"不可用 — 本 session 引擎未啟動",
				"Not available — engine not started this session",
			),
			"No cycle executed yet": _opsBilingual("尚未執行 cycle", "No cycle executed yet"),
			"No cache generated yet": _opsBilingual("尚未產生快取", "No cache generated yet"),
			"— none this session": _opsBilingual("— 本 session 無", "— none this session"),
			"Not market silence": _opsBilingual("非市場沉寂", "Not market silence"),
			RUNNING: _opsBilingual("運行中", "RUNNING"),
			STOPPED: _opsBilingual("已停止", "STOPPED"),
			TRIPPED: _opsBilingual("已觸發", "TRIPPED"),
			CLEAR: _opsBilingual("正常", "CLEAR"),
			"DRY RUN / PAPER": _opsBilingual("模擬／Paper", "DRY RUN / PAPER"),
			"LIVE TRADING": _opsBilingual("Live 交易", "LIVE TRADING"),
			healthy: _opsBilingual("健康", "healthy"),
			degraded: _opsBilingual("降級", "degraded"),
			blocked: _opsBilingual("阻擋", "blocked"),
			inactive: _opsBilingual("未啟用", "inactive"),
			"Decision machines aligned — monitor constraints": _opsBilingual(
				"決策機器對齊 — 監控約束",
				"Decision machines aligned — monitor constraints",
			),
			"Mixed machine health — check Ops panel": _opsBilingual(
				"機器健康混合 — 請查 Ops 面板",
				"Mixed machine health — check Ops panel",
			),
			"Engine stopped — no scan cycle today": _opsBilingual(
				"引擎已停 — 今日無掃描 cycle",
				"Engine stopped — no scan cycle today",
			),
			"No engine cycle executed this session": _opsBilingual(
				"本 session 未執行 engine cycle",
				"No engine cycle executed this session",
			),
			"Signal pipeline not executed today": _opsBilingual(
				"今日訊號管線未執行",
				"Signal pipeline not executed today",
			),
			"Recommendation cache empty": _opsBilingual("推薦快取為空", "Recommendation cache empty"),
			"Candidates evaluated but none passed gates": _opsBilingual(
				"已評估候選但均未過閘",
				"Candidates evaluated but none passed gates",
			),
			"Pipeline ran — scanner selective / regime filters": _opsBilingual(
				"管線已跑 — 掃描選擇性／體制篩選",
				"Pipeline ran — scanner selective / regime filters",
			),
			"Zero signals — root cause not classified": _opsBilingual(
				"零訊號 — 根因未分類",
				"Zero signals — root cause not classified",
			),
			"Phase 9 engines failed to load — check server logs": _opsBilingual(
				"Phase 9 引擎載入失敗 — 請查伺服器日誌",
				"Phase 9 engines failed to load — check server logs",
			),
			LOADED: _opsBilingual("已載入", "LOADED"),
			OFFLINE: _opsBilingual("離線", "OFFLINE"),
			"Treat this page as a diagnostics surface until fresh runtime evidence exists.": _opsBilingual(
				"待有新執行時證據前，請將此頁視為診斷介面。",
				"Treat this page as a diagnostics surface until fresh runtime evidence exists.",
			),
			"API warming — engine runtime evidence unavailable. Boards elsewhere may show brief or snapshot fallback only.":
				_opsBilingual(
					"API 預熱 — 執行時引擎證據不可用。其他分頁可能僅顯示 brief 或 snapshot fallback。",
					"API warming — engine runtime evidence unavailable. Boards elsewhere may show brief or snapshot fallback only.",
				),
			"Runtime override active — engine is stopped. Any board state shown elsewhere is cached, fallback, or precomputed output, not fresh engine execution from this session.":
				_opsBilingual(
					"執行時覆寫生效 — 引擎已停。其他分頁顯示的 board 狀態為快取、fallback 或預先計算，非本 session 新鮮引擎執行。",
					"Runtime override active — engine is stopped. Any board state shown elsewhere is cached, fallback, or precomputed output, not fresh engine execution from this session.",
				),
			"Signals today: 0 — API warming — not evidence the market produced zero opportunities.": _opsBilingual(
				"今日訊號：0 — API 預熱 — 非市場零機會的證據。",
				"Signals today: 0 — API warming — not evidence the market produced zero opportunities.",
			),
			"Signals today: 0 — Reason: no engine cycle executed this session — not evidence that the market produced zero opportunities.":
				_opsBilingual(
					"今日訊號：0 — 原因：本 session 未執行 engine cycle — 非市場零機會的證據。",
					"Signals today: 0 — Reason: no engine cycle executed this session — not evidence that the market produced zero opportunities.",
				),
			"Backend crash detected — see blockers above.": _opsBilingual(
				"偵測到後端崩潰 — 見上方阻擋項。",
				"Backend crash detected — see blockers above.",
			),
			"Warming probes — see Recovery runbook. Do not treat FAIL as final until backend is full.": _opsBilingual(
				"探測預熱中 — 見 Recovery runbook。後端未 full 前勿將 FAIL 視為最終狀態。",
				"Warming probes — see Recovery runbook. Do not treat FAIL as final until backend is full.",
			),
		}
		if (opsCopyMap[t]) return opsCopyMap[t]
		if (
			/^Signals today: 0 — pipeline ran \((\d+) cycle\(s\)\) — scanner\/regime filters may have rejected all candidates\.$/.test(
				t,
			)
		) {
			var sc = t.match(/^Signals today: 0 — pipeline ran \((\d+) cycle\(s\)\)/)
			return _opsBilingual("今日訊號：0 — 管線已跑（" + sc[1] + " cycle）— 掃描／體制篩選可能拒絕所有候選。", t)
		}
		if (/^Signals today: (\d+) — from engine runtime this session\.$/.test(t)) {
			var st = t.match(/^Signals today: (\d+)/)
			return _opsBilingual("今日訊號：" + st[1] + " — 來自本 session 引擎執行時。", t)
		}
		if (/^Signals today: (\d+)$/.test(t)) {
			var st2 = t.match(/^Signals today: (\d+)$/)
			return _opsBilingual("今日訊號：" + st2[1], t)
		}
		if (/^(\d+) machines blocked — respect constraints before deploy$/.test(t)) {
			var mb = t.match(/^(\d+) machines blocked/)
			return _opsBilingual(mb[1] + " 台機器阻擋 — 部署前請遵守約束", t)
		}
		if (/^(\d+) machines degraded — verify facts and process$/.test(t)) {
			var md = t.match(/^(\d+) machines degraded/)
			return _opsBilingual(md[1] + " 台機器降級 — 請核實事實與流程", t)
		}
		if (/^Scheduler: /.test(t)) {
			return _opsBilingual("排程：" + t.slice(11), t)
		}
		if (/^Market data tier: /.test(t)) {
			return _opsBilingual("市場資料層級：" + t.slice(18), t)
		}
		if (/^Backend crash: /.test(t)) {
			return _opsBilingual("後端崩潰：" + t.slice(15), t)
		}
		if (/^API process up/.test(t) || /^API up/.test(t) || t === "API startup time unavailable") {
			return localizeOpsMetricReason(t)
		}
		if (
			/^Live regime probe/.test(t) ||
			/^Start engine or run a cycle/.test(t) ||
			/^Run a scan cycle/.test(t) ||
			/^Regime probe/.test(t) ||
			/^Last regime probe/.test(t)
		) {
			return localizeOpsMetricReason(t)
		}
		if (
			/^(\d+) cached recommendation/.test(t) ||
			/^Start engine, then run/.test(t) ||
			/^Cycle ran but cache empty/.test(t)
		) {
			return localizeOpsMetricReason(t)
		}
		return t
	}

	function localizeOpsMetricReason(t) {
		var s = String(t || "").trim()
		if (!s) return ""
		if (s.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(s)) return s
		var map = {
			Unknown: _opsBilingual("未知", "Unknown"),
			"API startup time unavailable": _opsBilingual("API 啟動時間不可用", "API startup time unavailable"),
			"Probe pending": _opsBilingual("探測待執行", "Probe pending"),
			"No cycle yet": _opsBilingual("尚無 cycle", "No cycle yet"),
			"Probe failed": _opsBilingual("探測失敗", "Probe failed"),
			"API shell only — engine not started": _opsBilingual(
				"僅 API shell — 引擎未啟動",
				"API shell only — engine not started",
			),
			"Regime probe unavailable during warmup": _opsBilingual(
				"預熱期間體制探測不可用",
				"Regime probe unavailable during warmup",
			),
			"Live regime probe — engine loop not running": _opsBilingual(
				"Live 體制探測 — engine 迴圈未運行",
				"Live regime probe — engine loop not running",
			),
			"Live regime probe — no scan cycle yet": _opsBilingual(
				"Live 體制探測 — 尚無掃描 cycle",
				"Live regime probe — no scan cycle yet",
			),
			"Last regime probe this session": _opsBilingual(
				"本 session 上次體制探測",
				"Last regime probe this session",
			),
			"Start engine or run a cycle to probe regime path": _opsBilingual(
				"啟動引擎或跑 cycle 以探測體制路徑",
				"Start engine or run a cycle to probe regime path",
			),
			"Run a scan cycle to measure regime latency": _opsBilingual(
				"跑掃描 cycle 以量測體制延遲",
				"Run a scan cycle to measure regime latency",
			),
			"Regime probe unavailable this session": _opsBilingual(
				"本 session 體制探測不可用",
				"Regime probe unavailable this session",
			),
			"Start engine, then run a scan cycle to populate cache": _opsBilingual(
				"啟動引擎後跑掃描 cycle 以填入快取",
				"Start engine, then run a scan cycle to populate cache",
			),
			"Run a scan cycle to generate recommendation cache": _opsBilingual(
				"跑掃描 cycle 以產生推薦快取",
				"Run a scan cycle to generate recommendation cache",
			),
			"Cycle ran but cache empty — inspect signal pipeline": _opsBilingual(
				"已跑 cycle 但快取為空 — 請檢查訊號管線",
				"Cycle ran but cache empty — inspect signal pipeline",
			),
		}
		if (map[s]) return map[s]
		if (/^API process up \((.+)\) — trading engine stopped$/.test(s)) {
			var m1 = s.match(/^API process up \((.+)\) — trading engine stopped$/)
			return _opsBilingual("API 運行中（" + m1[1] + "）— 交易引擎已停", s)
		}
		if (/^API up \((.+)\) — no engine cycles this session yet$/.test(s)) {
			var m2 = s.match(/^API up \((.+)\) — no engine cycles this session yet$/)
			return _opsBilingual("API 運行中（" + m2[1] + "）— 本 session 尚無 engine cycle", s)
		}
		if (/^API up since /.test(s)) {
			return _opsBilingual("API 自 " + s.slice(12) + " 起運行", s)
		}
		if (/^(\d+) cached recommendation\(s\)$/.test(s)) {
			var mc = s.match(/^(\d+)/)
			return _opsBilingual(mc[1] + " 筆快取推薦", s)
		}
		return s
	}

	function localizeOpsDictKey(key) {
		var k = String(key || "")
			.trim()
			.toLowerCase()
		var map = {
			last_engine_error: _opsBilingual("上次引擎錯誤", "last engine error"),
			last_failed_job: _opsBilingual("上次失敗工作", "last failed job"),
			last_heartbeat: _opsBilingual("上次心跳", "last heartbeat"),
			last_cycle: _opsBilingual("上次 cycle", "last cycle"),
			scheduler_detail: _opsBilingual("排程詳情", "scheduler detail"),
			last_successful_engine_cycle: _opsBilingual("上次成功 engine cycle", "last successful engine cycle"),
			last_recommendation_refresh: _opsBilingual("上次推薦更新", "last recommendation refresh"),
			last_broker_heartbeat: _opsBilingual("上次券商心跳", "last broker heartbeat"),
			last_paper_order_test: _opsBilingual("上次 paper 下單測試", "last paper order test"),
			last_ibkr_disconnect: _opsBilingual("上次 IBKR 斷線", "last ibkr disconnect"),
			last_ibkr_restore: _opsBilingual("上次 IBKR 恢復", "last ibkr restore"),
			last_scheduler_run: _opsBilingual("上次排程執行", "last scheduler run"),
			market_data: _opsBilingual("市場資料", "market data"),
			signal_engine: _opsBilingual("訊號引擎", "signal engine"),
			execution_mode: _opsBilingual("執行模式", "execution mode"),
			broker_path: _opsBilingual("券商路徑", "broker path"),
			portfolio_sync: _opsBilingual("持倉同步", "portfolio sync"),
		}
		return map[k] || k.replace(/_/g, " ")
	}

	function localizeOpsMachineField(field, value) {
		var f = String(field || "")
			.trim()
			.toLowerCase()
		var v = String(value || "").trim()
		if (!v) return ""
		if (f === "health") return localizeOpsRuntimeText(v)
		var labelMap = {
			"Data Integrity": _opsBilingual("資料完整性", "Data Integrity"),
			Regime: _opsBilingual("體制", "Regime"),
			Playbook: _opsBilingual("策略簿", "Playbook"),
			Dossier: _opsBilingual("檔案", "Dossier"),
			Portfolio: _opsBilingual("持倉", "Portfolio"),
			Execution: _opsBilingual("執行", "Execution"),
			Review: _opsBilingual("覆盤", "Review"),
			Learning: _opsBilingual("學習", "Learning"),
		}
		var constraintMap = {
			"No action on unknown or stale facts": _opsBilingual(
				"未知或過期事實不得行動",
				"No action on unknown or stale facts",
			),
			"WAIT / NO_TRADE binds all downstream machines": _opsBilingual(
				"WAIT／NO_TRADE 約束所有下游機器",
				"WAIT / NO_TRADE binds all downstream machines",
			),
			"Rank ≠ permission — evidence grade required": _opsBilingual(
				"排名≠許可 — 需證據等級",
				"Rank ≠ permission — evidence grade required",
			),
			"Research-only when process grade C or D": _opsBilingual(
				"流程等級 C/D 時僅研究",
				"Research-only when process grade C or D",
			),
			"Portfolio machine cannot override regime gate": _opsBilingual(
				"持倉機器不得覆寫體制閘門",
				"Portfolio machine cannot override regime gate",
			),
			"No live deploy without tested execution path": _opsBilingual(
				"未測試執行路徑不得 live 部署",
				"No live deploy without tested execution path",
			),
			"Judge process quality independent of P&L": _opsBilingual(
				"獨立於損益評估流程品質",
				"Judge process quality independent of P&L",
			),
			"Every failure must produce a machine update": _opsBilingual(
				"每次失敗須產出機器更新",
				"Every failure must produce a machine update",
			),
		}
		if (f === "label" && labelMap[v]) return labelMap[v]
		if (f === "constraint" && constraintMap[v]) return constraintMap[v]
		return localizeOpsRuntimeText(v)
	}

	function opsSystemVerdictTitle() {
		return _opsBilingual("系統裁決", "System verdict")
	}
	function opsDecisionMachinesTitle() {
		return _opsBilingual("決策機器", "Decision machines")
	}
	function opsExecutionReadinessTitle() {
		return _opsBilingual("執行就緒層", "Execution readiness layers")
	}
	function opsExecutionReadinessHint() {
		return _opsBilingual(
			"僅探測狀態顯示灰／琥珀 — 非綠色交易就緒",
			"Probe-only states shown gray/amber — not green trading-ready",
		)
	}
	function opsBlockersTitle() {
		return _opsBilingual("根因／阻擋", "Root cause / blockers")
	}
	function opsNextActionsTitle() {
		return _opsBilingual("下一步操作", "Next operator actions")
	}
	function opsEngineStateTitle() {
		return _opsBilingual("引擎狀態", "Engine State")
	}
	function opsUptimeLatencyTitle() {
		return _opsBilingual("運行時間與延遲", "Uptime & Latency")
	}
	function opsExperimentalModulesTitle() {
		return _opsBilingual("實驗模組", "Experimental modules")
	}
	function opsProbeVerdictNote() {
		return _opsBilingual(
			"探測 OK ≠ 執行時健康。資本決策前請先看上方探測 vs 執行時表。",
			"Probe OK ≠ runtime health. Use the probe vs runtime table above before capital.",
		)
	}
	function opsMetricLabel(name) {
		var n = String(name || "")
			.trim()
			.toLowerCase()
		var map = {
			uptime: _opsBilingual("運行時間", "Uptime"),
			"regime latency": _opsBilingual("體制延遲", "Regime Latency"),
			"cached recs": _opsBilingual("快取推薦", "Cached Recs"),
			engine: _opsBilingual("引擎", "Engine"),
			"circuit breaker": _opsBilingual("熔斷器", "Circuit Breaker"),
			cycles: _opsBilingual("Cycles", "Cycles"),
			"signals today": _opsBilingual("今日訊號", "Signals Today"),
		}
		return map[n] || name
	}

	function opsHttp500BannerText() {
		return _opsBilingual(
			"Ops 不可用 — 執行時狀態端點失敗（HTTP 500）。探測可能仍通過，但在端點恢復前請勿信任 live 引擎狀態、快取與工作證據。",
			"OPS UNAVAILABLE — runtime status endpoint failed (HTTP 500). Probe checks may still pass, but live engine state, cache, and job evidence cannot be trusted until the runtime endpoint recovers.",
		)
	}
	function opsPaperLiveBoundaryTitle() {
		return _opsBilingual("Paper／Live 邊界", "Paper / live boundary")
	}
	function opsLastSuccessfulTimesTitle() {
		return _opsBilingual("上次成功時間", "Last successful times")
	}
	function opsOperationalEventsTitle() {
		return _opsBilingual("營運事件", "Operational events")
	}
	function opsWhyNoSignalsTitle() {
		return _opsBilingual("今日為何無訊號？", "Why no signals today?")
	}
	function opsFailedFreshnessHint() {
		return _opsBilingual(
			"failed_freshness = 掃描器快取預熱中，非 7 項獨立失敗。",
			"failed_freshness = scanner cache warming, not 7 separate failures.",
		)
	}
	function opsPhase9EnginesTitle() {
		return _opsBilingual("Phase 9 引擎", "Phase 9 Engines")
	}
	function opsPhase9LoadFailed() {
		return _opsBilingual(
			"Phase 9 引擎載入失敗 — 請查伺服器日誌",
			"Phase 9 engines failed to load — check server logs",
		)
	}
	function opsCacheStatisticsTitle() {
		return _opsBilingual("快取統計", "Cache Statistics")
	}
	function opsSelfLearningEngineTitle() {
		return _opsBilingual("自學習引擎", "Self-Learning Engine")
	}
	function opsSelfLearnLabel(key) {
		var k = String(key || "")
			.trim()
			.toLowerCase()
		var map = {
			enabled: _opsBilingual("已啟用", "Enabled"),
			adjustments: _opsBilingual("調整", "Adjustments"),
			trades: _opsBilingual("交易", "Trades"),
			this_cycle: _opsBilingual("本 Cycle", "This Cycle"),
		}
		return map[k] || key
	}
	function opsWhatThisMeansTitle() {
		return _opsBilingual("這代表什麼", "What this means")
	}
	function opsBoardStateCachedNote() {
		return _opsBilingual(
			"其他分頁的 board 狀態可能是快取、fallback 或預先計算 — 非本 session engine 已執行的證據。",
			"Board state elsewhere may be cached, fallback, or precomputed — not proof the engine ran this session.",
		)
	}
	function opsEngineStoppedHelpCopy() {
		return _opsBilingual(
			"啟動交易迴圈以執行 cycle、快取與執行時證據。或在 Docker/env 設定 CC_AUTO_START_ENGINE=1 於開機啟動。",
			"Start the trading loop for cycles, cache, and runtime evidence. Or set CC_AUTO_START_ENGINE=1 in Docker/env to start on boot.",
		)
	}
	function opsStartEngineLabel(starting) {
		return starting ? _opsBilingual("啟動中…", "Starting…") : _opsBilingual("▶ 啟動引擎", "▶ Start engine")
	}
	function opsViewErrorLogLabel() {
		return _opsBilingual("檢視錯誤日誌", "View Error Log")
	}
	function opsRecoveryRunbookTitle() {
		return _opsBilingual("恢復手冊", "Recovery runbook")
	}
	function opsBlocksCapitalTitle() {
		return _opsBilingual("阻擋資金", "Blocks capital")
	}
	function opsSafeDegradedTitle() {
		return _opsBilingual("降級模式可安全操作", "Safe in degraded mode")
	}
	function opsNoHardBlocksCopy() {
		return _opsBilingual("Ops 快照未標記硬性阻擋", "No hard blocks flagged from Ops snapshot")
	}
	function opsPlatformUpdatesTitle() {
		return _opsBilingual("平台更新", "Platform updates")
	}
	function opsSessionErrorLogTitle() {
		return _opsBilingual("Session 錯誤日誌", "Session error log")
	}
	function opsSeeRecoveryRunbookPrefix() {
		return _opsBilingual("見上方恢復手冊", "See Recovery runbook above")
	}
	function opsBootTimeLine(iso) {
		if (!iso) return ""
		var s = String(iso).slice(0, 19)
		return _opsBilingual("開機：" + s, "Boot: " + s)
	}
	function opsLastCycleLine(iso) {
		if (!iso) return ""
		var s = String(iso).slice(0, 19)
		return _opsBilingual("上次 cycle：" + s, "Last cycle: " + s)
	}
	function opsIbkrSessionInactiveTitle() {
		return _opsBilingual("IBKR session 未啟動", "IBKR session not active")
	}
	function opsIbkrGatewayReachableNote() {
		return _opsBilingual(
			"Gateway 訊號存在 — 請於 IBKR 分頁確認登入。",
			"Gateway signals present — confirm login on IBKR tab.",
		)
	}
	function opsIbkrNoSessionNote() {
		return _opsBilingual(
			"尚無 IB API session。請啟動 IB Gateway/TWS，然後 Connect。已停用 Raw TCP 探測（CC_SKIP_IB_INSYNC 避免日誌刷屏）。",
			"No IB API session yet. Start IB Gateway/TWS, then Connect. Raw TCP probes are disabled (CC_SKIP_IB_INSYNC avoids log spam).",
		)
	}
	function opsOpenIbkrConnectLabel() {
		return _opsBilingual("開啟 IBKR 分頁 → Connect", "Open IBKR tab → Connect")
	}
	function opsCriticalGapsPrefix() {
		return _opsBilingual("執行時缺口", "Runtime gaps")
	}
	function opsCriticalFlagText(flag) {
		var map = {
			"runtime HTTP 500": _opsBilingual("執行時 HTTP 500", "runtime HTTP 500"),
			"engine stopped": _opsBilingual("引擎已停", "engine stopped"),
			"0 cycles": _opsBilingual("0 cycles", "0 cycles"),
			"no cache": _opsBilingual("無快取", "no cache"),
		}
		return map[flag] || localizeOpsRuntimeText(flag)
	}
	function opsNoCycleSessionWarning() {
		return _opsBilingual(
			"本 session 未執行 engine cycle — 下方運行時間與延遲僅反映 API 開機，非交易迴圈活動。",
			"No engine cycle executed this session — uptime and latency below reflect API boot only, not trading loop activity.",
		)
	}
	function opsNoCacheWarning() {
		return _opsBilingual(
			"推薦快取為空 — 今日／訊號 board 可能顯示過期或預先計算輸出。",
			"Recommendation cache empty — Today/Signals boards may show stale or precomputed output.",
		)
	}
	function opsTradesTodayPill(count) {
		var n = count || 0
		return _opsBilingual("今日交易：" + n, "Trades today: " + n)
	}
	function opsRunCycleLabel() {
		return _opsBilingual("▶ 執行 Cycle", "▶ Run Cycle")
	}
	function opsSelfLearnEnabledLabel(enabled) {
		return enabled ? _opsBilingual("是", "YES") : _opsBilingual("已停用", "DISABLED")
	}
	function opsHttp500IntroSuffix() {
		return _opsBilingual("執行時狀態路徑回傳 HTTP 500。", "The runtime status path is failing with HTTP 500.")
	}
	function opsWhyNoSignalsCell(w) {
		if (!w) return ""
		if ((w.count || 0) > 0) return String(w.count)
		if (w.note) return localizeOpsRuntimeText(w.note)
		return ""
	}
	function localizeOpsWhyNoSignalsGate(gate) {
		var g = String(gate || "").trim()
		if (!g) return ""
		var codeMap = {
			no_cycle_run: _opsBilingual("無 cycle 執行", "no cycle run"),
			pipeline_not_executed: _opsBilingual("管線未執行", "pipeline not executed"),
			cache_empty: _opsBilingual("快取為空", "cache empty"),
			candidates_failed_gates: _opsBilingual("候選未過閘", "candidates failed gates"),
			selective_scanner: _opsBilingual("選擇性掃描", "selective scanner"),
			unknown: _opsBilingual("未知", "unknown"),
		}
		if (codeMap[g]) return codeMap[g]
		return localizeOpsDictKey(g)
	}

	function localizeOpsComponentName(name) {
		var n = String(name || "").trim()
		var map = {
			market_data: "市場資料 · Market data",
			regime_router: "體制路由 · Regime router",
			broker: "券商 · Broker",
			leaderboard: "排行榜 · Leaderboard",
			learning_loop: "學習迴圈 · Learning loop",
		}
		return map[n] || n.replace(/_/g, " ")
	}

	function _opsBilingual(zh, en) {
		return zh + " · " + en
	}

	/** Dynamic Alpine / API copy — 繁中 · English (Dashboard, Playbook, Ops chrome). */
	function localizeUiText(text) {
		var t = String(text || "").trim()
		if (!t) return ""
		if (t.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(t)) return t
		var exact = {
			Monitors: _opsBilingual("監控", "Monitors"),
			"Fallback monitors": _opsBilingual("後備監控", "Fallback monitors"),
			"Deploy blocked — use monitors and Playbook ranking only": _opsBilingual(
				"部署已阻 — 只用 monitor 同 Playbook 排序",
				"Deploy blocked — use monitors and Playbook ranking only",
			),
			"Deploy blocked - use monitors and Playbook ranking only": _opsBilingual(
				"部署已阻 — 只用 monitor 同 Playbook 排序",
				"Deploy blocked — use monitors and Playbook ranking only",
			),
			"Blocked: deploy · Safe: monitors · near-miss · Playbook ranking": _opsBilingual(
				"阻擋：deploy · 安全：monitor、near-miss、Playbook 排序",
				"Blocked: deploy · Safe: monitors · near-miss · Playbook ranking",
			),
			"Blocked: IBKR handoff · Safe: dossier core-only · monitor queue": _opsBilingual(
				"阻擋：IBKR handoff · 安全：檔案核心欄、monitor queue",
				"Blocked: IBKR handoff · Safe: dossier core-only · monitor queue",
			),
			"Blocked: new cycle sizing · Safe: Guide · monitors until engine ON": _opsBilingual(
				"阻擋：新 cycle sizing · 安全：Guide、monitor 直至引擎 ON",
				"Blocked: new cycle sizing · Safe: Guide · monitors until engine ON",
			),
			"Near-miss · watch queue — priority only, not deploy on WAIT": _opsBilingual(
				"Near-miss · watch queue — WAIT 日只排優先，不可 deploy",
				"Near-miss · watch queue — priority only, not deploy on WAIT",
			),
			"Watch / near-miss — ranking for attention, not handoff permission": _opsBilingual(
				"Watch／near-miss — 注意力排序，非 handoff 許可",
				"Watch / near-miss — ranking for attention, not handoff permission",
			),
			"Fallback monitors — scan / near-miss queue; filter_funnel is authority for watch-qualified": _opsBilingual(
				"後備 monitor — 掃描／near-miss queue；filter_funnel 為 watch-qualified 權威",
				"Fallback monitors — scan / near-miss queue; filter_funnel is authority for watch-qualified",
			),
			"Monitor context: ": _opsBilingual("Monitor 脈絡", "Monitor context"),
			" — not deploy permission": _opsBilingual(" — 非 deploy 許可", " — not deploy permission"),
			"monitor only, not deploy": _opsBilingual("只供 monitor，不可 deploy", "monitor only, not deploy"),
			" — monitor context": _opsBilingual(" — monitor 脈絡", " — monitor context"),
			"System blockers": _opsBilingual("系統阻擋", "System blockers"),
			"System blockers · gate flags": _opsBilingual("系統阻擋 · 閘門標記", "System blockers · gate flags"),
			"Gate flags": _opsBilingual("閘門標記", "Gate flags"),
			Blockers: _opsBilingual("阻擋", "Blockers"),
			"No card-level gate flags": _opsBilingual("無卡片級閘門標記", "No card-level gate flags"),
			"None flagged": _opsBilingual("未標記", "None flagged"),
			"Today focus": _opsBilingual("今日重點", "Today focus"),
			"Today mission": _opsBilingual("今日任務", "Today mission"),
			"Best deploy": _opsBilingual("最佳 deploy", "Best deploy"),
			"Top candidate": _opsBilingual("頭號候選", "Top candidate"),
			"Best trade": _opsBilingual("最佳交易", "Best trade"),
			"Top monitor": _opsBilingual("頭號 monitor", "Top monitor"),
			"Top promotion": _opsBilingual("頭號升級", "Top promotion"),
			"Top watch": _opsBilingual("頭號 watch", "Top watch"),
			"Best monitor": _opsBilingual("最佳 monitor", "Best monitor"),
			"Often correct on WAIT — monitor funnel, not deploy.": _opsBilingual(
				"WAIT 日常正確 — 監控 funnel，非 deploy",
				"Often correct on WAIT — monitor funnel, not deploy.",
			),
			"deploy-qualified": _opsBilingual("deploy-qualified", "deploy-qualified"),
			"watch-qualified": _opsBilingual("watch-qualified", "watch-qualified"),
			scanned: _opsBilingual("已掃描", "scanned"),
			"monitor-only pipeline": _opsBilingual("只供 monitor pipeline", "monitor-only pipeline"),
			"0 near-miss": _opsBilingual("0 near-miss", "0 near-miss"),
			"Closest monitor upgrade": _opsBilingual("最接近 monitor 升級", "Closest monitor upgrade"),
			"Closest to upgrade": _opsBilingual("最接近升級", "Closest to upgrade"),
			"All four must clear together — see checklist:": _opsBilingual(
				"四項須同時通過 — 見清單：",
				"All four must clear together — see checklist:",
			),
			"Unlock deploy requires all 4 conditions together: tradeability SELECTIVE+, ≥1 deploy-qualified setup, live broker handoff, and ≥1 watch-qualified name on fresh data (scan-ranked alone does not qualify).":
				_opsBilingual(
					"解鎖 deploy 須四項齊備：tradeability SELECTIVE+、≥1 deploy-qualified、live broker handoff、≥1 watch-qualified（僅 scan-ranked 不足）。",
					"Unlock deploy requires all 4 conditions together: tradeability SELECTIVE+, ≥1 deploy-qualified setup, live broker handoff, and ≥1 watch-qualified name on fresh data (scan-ranked alone does not qualify).",
				),
			"Deploy-qualified count — authority suspended; watch-qualified names are in the middle KPI": _opsBilingual(
				"Deploy-qualified 計數 — 權限暫停；watch-qualified 在中間 KPI",
				"Deploy-qualified count — authority suspended; watch-qualified names are in the middle KPI",
			),
			"Deploy-qualified setups in top board": _opsBilingual(
				"頂板 deploy-qualified 型態",
				"Deploy-qualified setups in top board",
			),
			"Watch-qualified — council monitor bar from filter_funnel (same as Playbook strip). Near-miss rows are a separate upgrade layer.":
				_opsBilingual(
					"Watch-qualified — filter_funnel council monitor bar（同 Playbook strip）。Near-miss 為獨立升級層。",
					"Watch-qualified — council monitor bar from filter_funnel (same as Playbook strip). Near-miss rows are a separate upgrade layer.",
				),
			"Scanned — universe evaluated by the scan pipeline": _opsBilingual(
				"已掃描 — 掃描管線評估的 universe",
				"Scanned — universe evaluated by the scan pipeline",
			),
			"Scanned = universe evaluated · Watch-qualified = monitor / near-miss pool · Deploy-qualified = execution-ready · Near-miss = upgrade layer (not deploy) · Monitor ranking = priority only, not permission.":
				_opsBilingual(
					"Scanned＝universe 評估 · Watch-qualified＝monitor／near-miss pool · Deploy-qualified＝execution-ready · Near-miss＝升級層（非 deploy）· Monitor ranking＝優先序（非許可）",
					"Scanned = universe evaluated · Watch-qualified = monitor / near-miss pool · Deploy-qualified = execution-ready · Near-miss = upgrade layer (not deploy) · Monitor ranking = priority only, not permission.",
				),
			"Scanned — universe evaluated by the scan pipeline.": _opsBilingual(
				"已掃描 — 掃描管線評估的 universe",
				"Scanned — universe evaluated by the scan pipeline.",
			),
			"Watch-qualified — met the monitor bar / near-miss pool; not deploy-ready.": _opsBilingual(
				"Watch-qualified — 達 monitor bar／near-miss pool；非 deploy-ready",
				"Watch-qualified — met the monitor bar / near-miss pool; not deploy-ready.",
			),
			"Deploy-qualified — execution-ready (timing, R:R, handoff).": _opsBilingual(
				"Deploy-qualified — execution-ready（時機、R:R、handoff）",
				"Deploy-qualified — execution-ready (timing, R:R, handoff).",
			),
			"Near-miss — upgrade layer: closest monitor upgrade; not deploy-ready.": _opsBilingual(
				"Near-miss — 升級層：最接近 monitor 升級；非 deploy-ready",
				"Near-miss — upgrade layer: closest monitor upgrade; not deploy-ready.",
			),
			"Monitor ranking — relative scan priority on WAIT days; rank ≠ deploy permission.": _opsBilingual(
				"Monitor ranking — WAIT 日掃描相對優先；rank ≠ deploy 許可",
				"Monitor ranking — relative scan priority on WAIT days; rank ≠ deploy permission.",
			),
			"Evidence unavailable": _opsBilingual("證據不可用", "Evidence unavailable"),
			"Feature IC decay detected — review Ops ML panel": _opsBilingual(
				"Feature IC 衰減 — 請查 Ops ML 面板",
				"Feature IC decay detected — review Ops ML panel",
			),
			"Decision authority degraded": _opsBilingual("決策權限降級", "Decision authority degraded"),
			"Loading…": _opsBilingual("載入中…", "Loading…"),
			Loading: _opsBilingual("載入中", "Loading"),
			"Panel unavailable": _opsBilingual("面板不可用", "Panel unavailable"),
			"No fallback available": _opsBilingual("無後備可用", "No fallback available"),
			"Fallback unavailable": _opsBilingual("後備不可用", "Fallback unavailable"),
			"Error log unavailable": _opsBilingual("錯誤日誌不可用", "Error log unavailable"),
			"No errors logged this session": _opsBilingual("本 session 無錯誤紀錄", "No errors logged this session"),
			"Unable to confirm whether errors were logged this session.": _opsBilingual(
				"無法確認本 session 是否有錯誤紀錄",
				"Unable to confirm whether errors were logged this session.",
			),
			"Built-in fallback — edit data/changelog.json for release notes.": _opsBilingual(
				"內建後備 — 編輯 data/changelog.json 以更新 release notes",
				"Built-in fallback — edit data/changelog.json for release notes.",
			),
			"CC platform": _opsBilingual("CC 平台", "CC platform"),
			LATEST: _opsBilingual("最新", "LATEST"),
			"DEPLOY. Selective sizing at 1R when brackets ready.": _opsBilingual(
				"DEPLOY — bracket 就緒時以 1R 選擇性 sizing",
				"DEPLOY. Selective sizing at 1R when brackets ready.",
			),
			"SELECTIVE. Deploy when gates open.": _opsBilingual(
				"SELECTIVE — 閘門開啟後 deploy",
				"SELECTIVE. Deploy when gates open.",
			),
			"SELECTIVE. Review deploy-qualified — verify execution ladder.": _opsBilingual(
				"SELECTIVE — 複核 deploy-qualified，確認 execution ladder",
				"SELECTIVE. Review deploy-qualified — verify execution ladder.",
			),
			"NO TRADE. Monitor only.": _opsBilingual("NO TRADE — 只 monitor", "NO TRADE. Monitor only."),
			"Deploy window — size only at 1R with bracket; gates cleared.": _opsBilingual(
				"Deploy 窗口 — 僅以 1R＋bracket sizing；閘門已清",
				"Deploy window — size only at 1R with bracket; gates cleared.",
			),
			"Selective day — verify checklist before any handoff.": _opsBilingual(
				"SELECTIVE 日 — handoff 前確認清單",
				"Selective day — verify checklist before any handoff.",
			),
			"Preservation / monitor day — ideas exist but deploy bar not met.": _opsBilingual(
				"守護／monitor 日 — 有 idea 但未達 deploy bar",
				"Preservation / monitor day — ideas exist but deploy bar not met.",
			),
			"Monitor-only day — protect capital until tradeability improves.": _opsBilingual(
				"只 monitor 日 — 待 tradeability 改善前守護資金",
				"Monitor-only day — protect capital until tradeability improves.",
			),
			"Monitor session — no full-size deploy until gates open.": _opsBilingual(
				"Monitor session — 閘門開啟前勿全倉 deploy",
				"Monitor session — no full-size deploy until gates open.",
			),
			"GUIDE MODE · Reference only · Decision surfaces suspended": _opsBilingual(
				"GUIDE 模式 · 只供參考 · 決策面已暫停",
				"GUIDE MODE · Reference only · Decision surfaces suspended",
			),
			"Runtime not evaluated here": _opsBilingual("此處不評估 runtime", "Runtime not evaluated here"),
			"Follow Dashboard monitor queue and near-miss upgrade candidates.": _opsBilingual(
				"跟 Dashboard monitor queue 同 near-miss 升級候選",
				"Follow Dashboard monitor queue and near-miss upgrade candidates.",
			),
			"Refresh Dashboard + Playbook after data / IBKR repair.": _opsBilingual(
				"資料／IBKR 修復後重新整理 Dashboard＋Playbook",
				"Refresh Dashboard + Playbook after data / IBKR repair.",
			),
			"Regime gate closed — capital preservation overrides individual setups.": _opsBilingual(
				"體制閘門關閉 — 守護資金優先於個別 setup",
				"Regime gate closed — capital preservation overrides individual setups.",
			),
			"No deploy-qualified setups — patience and monitor queue are the active decision.": _opsBilingual(
				"無 deploy-qualified — 耐心同 monitor queue 為主決策",
				"No deploy-qualified setups — patience and monitor queue are the active decision.",
			),
			"transport down": _opsBilingual("傳輸 down", "transport down"),
			"session inactive": _opsBilingual("session 未啟動", "session inactive"),
			"engine off": _opsBilingual("引擎 off", "engine off"),
			"handoff blocked": _opsBilingual("handoff 阻擋", "handoff blocked"),
			"bracket draft": _opsBilingual("bracket 草稿", "bracket draft"),
			"breaker on": _opsBilingual("熔斷 on", "breaker on"),
			"path incomplete": _opsBilingual("路徑不完整", "path incomplete"),
			Connected: _opsBilingual("已連線", "Connected"),
			Ready: _opsBilingual("就緒", "Ready"),
			Yes: _opsBilingual("是", "Yes"),
			No: _opsBilingual("否", "No"),
			Up: _opsBilingual("正常", "Up"),
			Down: _opsBilingual("離線", "Down"),
			OK: _opsBilingual("正常", "OK"),
			Transport: _opsBilingual("傳輸", "Transport"),
			Session: _opsBilingual("Session", "Session"),
			Engine: _opsBilingual("引擎", "Engine"),
			Handoff: _opsBilingual("Handoff", "Handoff"),
			Bracket: _opsBilingual("Bracket", "Bracket"),
			Execution: _opsBilingual("執行", "Execution"),
			Broker: _opsBilingual("券商", "Broker"),
			Mode: _opsBilingual("模式", "Mode"),
			Gateway: _opsBilingual("Gateway", "Gateway"),
			Heartbeat: _opsBilingual("心跳", "Heartbeat"),
			"Position sync": _opsBilingual("持倉同步", "Position sync"),
			"Order queue": _opsBilingual("訂單佇列", "Order queue"),
			Manual: _opsBilingual("手動", "Manual"),
			"Trade Now": _opsBilingual("可交易", "Trade Now"),
			"Pilot Only": _opsBilingual("僅試點", "Pilot Only"),
			"High conviction · low conflict · sector leader. Size at 1R.": _opsBilingual(
				"高 conviction · 低衝突 · 板塊領導 — 以 1R sizing",
				"High conviction · low conflict · sector leader. Size at 1R.",
			),
			"Position size vs 1R stop": _opsBilingual("部位 vs 1R 止損", "Position size vs 1R stop"),
			"Resize if stop widens >15%": _opsBilingual("止損拉闊 >15% 時調整", "Resize if stop widens >15%"),
			"Research only — does not override deploy gates or BDR decision.": _opsBilingual(
				"僅供研究 — 不覆寫 deploy 閘門或 BDR 決策",
				"Research only — does not override deploy gates or BDR decision.",
			),
			"Captures API failures, engine state, broker events, and dossier timeouts during this API session. Informational — optional features like Discord being unconfigured are not logged as errors.":
				_opsBilingual(
					"記錄本 API session 的 API 失敗、引擎狀態、券商事件、檔案逾時。資訊性 — Discord 未設定等可選功能不記為錯誤。",
					"Captures API failures, engine state, broker events, and dossier timeouts during this API session. Informational — optional features like Discord being unconfigured are not logged as errors.",
				),
			"When the API returns 503/500, the signal engine is stopped, IBKR disconnects, or dossier aggregation times out, entries appear here with plain-English detail and suggested actions.":
				_opsBilingual(
					"API 503/500、引擎停止、IBKR 斷線或檔案聚合逾時時，此處顯示詳情同建議操作。",
					"When the API returns 503/500, the signal engine is stopped, IBKR disconnects, or dossier aggregation times out, entries appear here with plain-English detail and suggested actions.",
				),
			"Release notes for CC · Clarity Console. Maintained in data/changelog.json — not live git history.":
				_opsBilingual(
					"CC · Clarity Console release notes。維護於 data/changelog.json — 非 live git 歷史。",
					"Release notes for CC · Clarity Console. Maintained in data/changelog.json — not live git history.",
				),
		}
		if (exact[t]) return exact[t]
		if (/^(\d+) near-miss$/.test(t)) {
			var nm1 = t.match(/^(\d+)/)
			return nm1[1] + " " + _opsBilingual("接近達標", "near-miss")
		}
		if (/^(\d+) near-miss monitor$/.test(t)) {
			var nm2 = t.match(/^(\d+)/)
			return nm2[1] + " " + _opsBilingual("接近達標 monitor", "near-miss monitor")
		}
		if (/^(\d+) near-miss \(not watch-qualified\)$/.test(t)) {
			var nm3 = t.match(/^(\d+)/)
			return nm3[1] + " " + _opsBilingual("接近達標（非 watch-qualified）", "near-miss (not watch-qualified)")
		}
		if (/^(\d+) watch-qualified on funnel — mission tickers are attention queue, not extra KPI count$/.test(t)) {
			var wq = t.match(/^(\d+)/)
			return _opsBilingual(wq[1] + " funnel watch-qualified — 任務代碼為注意力 queue，非額外 KPI", t)
		}
		if (/^(\d+) scanned · (\d+) funnel watch-qualified · (\d+) deploy-qualified/.test(t)) {
			var pf = t.match(/^(\d+) scanned · (\d+) funnel watch-qualified · (\d+) deploy-qualified(.*)$/)
			if (pf) {
				return _opsBilingual(
					pf[1] +
						" 已掃描 · " +
						pf[2] +
						" funnel watch-qualified · " +
						pf[3] +
						" deploy-qualified" +
						(pf[4] || ""),
					t,
				)
			}
		}
		if (/^(\d+) sh · ([\d.]+)% · \$([\d]+) @ 1R$/.test(t)) {
			var sz = t.match(/^(\d+) sh · ([\d.]+)% · \$([\d]+) @ 1R$/)
			return _opsBilingual(sz[1] + " 股 · " + sz[2] + "% · $" + sz[3] + " @ 1R", t)
		}
		if (/^Feature IC decay · .+ — sizing confidence reduced \(advisory only\)$/.test(t)) {
			return _opsBilingual("Feature IC 衰減 — sizing 信心降低（僅 advisory）", t)
		}
		if (/^Evidence score /.test(t) || /^Evidence quality · /.test(t) || /^Evidence · /.test(t)) {
			return _opsBilingual(t.replace(/^Evidence (score |quality · |· )?/, "證據$1"), t)
		}
		if (/^board score /.test(t)) return _opsBilingual("board 分數 " + t.slice(12), t)
		if (/^data quality /.test(t)) return _opsBilingual("資料品質 " + t.slice(12), t)
		if (t === "calibrated") return _opsBilingual("已校準", "calibrated")
		if (/^(\d+) blocker\(s\)$/.test(t)) {
			var bc = t.match(/^(\d+)/)
			return bc[1] + " " + _opsBilingual("項阻擋", "blocker(s)")
		}
		if (/^(\d+) log$/.test(t)) {
			var lg = t.match(/^(\d+)/)
			return lg[1] + " " + _opsBilingual("筆紀錄", "log")
		}
		if (/^Track .+ for upgrade triggers — Playbook monitor queue only\.$/.test(t)) {
			return _opsBilingual("追蹤升級觸發 — 僅 Playbook monitor queue", t)
		}
		if (/^Current status: /.test(t)) return _opsBilingual("現況：" + t.slice(16), t)
		if (/^Mode · .+ · Runtime not evaluated here$/.test(t)) {
			return _opsBilingual(
				t.replace("Mode · ", "模式 · ").replace(" · Runtime not evaluated here", " · 此處不評估 runtime"),
				t,
			)
		}
		if (/^The issue is not idea scarcity/.test(t)) {
			return _opsBilingual("問題非 idea 不足 — 而是質素不足", t)
		}
		if (/^Exec diagnostic: /.test(t)) {
			return _opsBilingual("執行診斷：" + t.slice(16).replace(" (not deploy authority)", ""), t)
		}
		if (/^Monitor only - /.test(t)) {
			return _opsBilingual("只 monitor — " + t.slice(14), t)
		}
		if (/^Wait for \/health mode=full, then refresh Dashboard and Playbook$/.test(t)) {
			return _opsBilingual("等待 /health mode=full，然後重新整理 Dashboard 同 Playbook", t)
		}
		if (/^Refresh Ops health · Error log · Updates panels$/.test(t)) {
			return _opsBilingual("重新整理 Ops health · 錯誤日誌 · 更新面板", t)
		}
		if (/^Start engine \(Ops health\) or set CC_AUTO_START_ENGINE=1$/.test(t)) {
			return _opsBilingual("啟動引擎（Ops health）或設定 CC_AUTO_START_ENGINE=1", t)
		}
		if (/^No engine cycle — Today\/Signals may be precomputed only$/.test(t)) {
			return _opsBilingual("無 engine cycle — Today／Signals 可能僅預先計算", t)
		}
		if (/^Risk breaker ON — blocks new entries until cleared$/.test(t)) {
			return _opsBilingual("Risk breaker ON — 清除前阻擋新進場", t)
		}
		if (/^IBKR session inactive — no handoff until LOGIN→READY on IBKR tab$/.test(t)) {
			return _opsBilingual("IBKR session 未啟動 — IBKR 分頁 LOGIN→READY 前無 handoff", t)
		}
		if (/^Monitor-only: near-miss, Discovery context, Guide checklist$/.test(t)) {
			return _opsBilingual("只 monitor：near-miss、Discovery 脈絡、Guide 清單", t)
		}
		if (/^Read data contract strip — FETCH FAILED \/ FALLBACK suspends sizing$/.test(t)) {
			return _opsBilingual("閱讀 data contract strip — FETCH FAILED／FALLBACK 暫停 sizing", t)
		}
		if (/^Paper review and dossier research when board is WAIT$/.test(t)) {
			return _opsBilingual("WAIT 板面時可 paper 複核同檔案研究", t)
		}
		if (/^Ops diagnostics do not override Dashboard deploy gate$/.test(t)) {
			return _opsBilingual("Ops 診斷不覆寫 Dashboard deploy 閘門", t)
		}
		if (/^R:R .+ — below 2.5 deploy bar$/.test(t)) {
			return _opsBilingual("R:R 低於 2.5 deploy bar", t)
		}
		if (/^AVOID — not monitor\/deploy priority$/.test(t)) {
			return _opsBilingual("AVOID — 非 monitor／deploy 優先", t)
		}
		if (/^Not execution-ready$/.test(t)) return _opsBilingual("非 execution-ready", t)
		if (/^Monitor — timing \/ confirmation pending$/.test(t)) {
			return _opsBilingual("Monitor — 時機／確認待定", t)
		}
		if (/^Current: /.test(t)) return _opsBilingual("現況：" + t.slice(9), t)
		return localizeOpsRuntimeText(t)
	}

	function localizeOpsAdvancedDiagnosticsCopy(text) {
		var t = String(text || "").trim()
		if (!t) return ""
		if (t.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(t)) return t
		var map = {
			"Engine off or insufficient trade sample — Ops experimental panels below (self-learning, Thompson sizing, execution metrics) need runtime evidence before they affect capital. Dossier / stock-intel research loads from market data independently.":
				"引擎關閉或交易樣本不足 — 下方 Ops 實驗面板（自學、Thompson 部位、執行指標）需有執行期證據後才會影響資金。檔案／個股研究獨立於市場資料載入。 · Engine off or insufficient trade sample — Ops experimental panels below (self-learning, Thompson sizing, execution metrics) need runtime evidence before they affect capital. Dossier / stock-intel research loads from market data independently.",
			"Engine off or insufficient trade sample — Ops experimental panels below (self-learning, Thompson sizing, execution metrics) need runtime evidence before they affect capital. Dossier research loads from market data independently.":
				"引擎關閉或交易樣本不足 — 下方 Ops 實驗面板（自學、Thompson 部位、執行指標）需有執行期證據後才會影響資金。檔案研究獨立於市場資料載入。 · Engine off or insufficient trade sample — Ops experimental panels below (self-learning, Thompson sizing, execution metrics) need runtime evidence before they affect capital. Dossier research loads from market data independently.",
		}
		if (map[t]) return map[t]
		return localizeOpsRuntimeText(t)
	}

	function opsAdvancedDiagnosticsTitle() {
		return _opsBilingual("進階診斷", "Advanced diagnostics")
	}

	function opsAdvancedDiagnosticsCollapsedTitle() {
		return _opsBilingual("進階診斷（收合）", "Advanced diagnostics (collapsed)")
	}

	function localizeOpsAdvancedSectionKey(key) {
		var k = String(key || "")
			.trim()
			.toLowerCase()
		var map = {
			self_learning: _opsBilingual("自學", "self learning"),
			thompson_sizing: _opsBilingual("Thompson 部位", "thompson sizing"),
			feature_ic: _opsBilingual("因子 IC", "feature ic"),
			pipeline_stats: _opsBilingual("管線統計", "pipeline stats"),
			execution_metrics: _opsBilingual("執行指標", "execution metrics"),
		}
		return map[k] || k.replace(/_/g, " ")
	}

	function localizeOpsAdvancedSectionLabel(label) {
		var t = String(label || "").trim()
		if (!t) return ""
		if (t.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(t)) return t
		var map = {
			"Not loaded": _opsBilingual("未載入", "Not loaded"),
			"Insufficient sample": _opsBilingual("樣本不足", "Insufficient sample"),
			Inactive: _opsBilingual("未啟用", "Inactive"),
			Active: _opsBilingual("有效", "Active"),
			Stale: _opsBilingual("過期", "Stale"),
		}
		if (map[t]) return map[t]
		return localizeOpsRuntimeText(t)
	}

	function localizeOpsAdvancedSectionDetail(detail) {
		var t = String(detail || "").trim()
		if (!t) return ""
		if (t.indexOf(" · ") > 0 && /[\u4e00-\u9fff]/.test(t)) return t
		var map = {
			"Engine not running": _opsBilingual("引擎未運行", "Engine not running"),
			"Click refresh or start engine": _opsBilingual("點擊重新整理或啟動引擎", "Click refresh or start engine"),
			"Evidence available": _opsBilingual("已有證據", "Evidence available"),
			"Data older than threshold": _opsBilingual("資料超過閾值", "Data older than threshold"),
			"Start engine or refresh ops console for evidence.": _opsBilingual(
				"請啟動引擎或重新整理 Ops 主控台以取得證據",
				"Start engine or refresh ops console for evidence.",
			),
		}
		if (map[t]) return map[t]
		var need = t.match(/^Need (\d+)\+ observations \(have (\d+)\)$/)
		if (need) {
			return _opsBilingual("需 " + need[1] + "+ 筆觀測（現有 " + need[2] + "）", t)
		}
		return localizeOpsRuntimeText(t)
	}

	function formatOperatorSentence(opts) {
		var o = opts || {}
		var now = localizeOperatorCopy(o.now || "")
		var blocker = localizeOperatorCopy(o.blocker || "")
		var nextAction = localizeOperatorCopy(o.nextAction || o.next_action || "")
		var parts = []
		if (now) parts.push("現況 · NOW: " + now)
		if (blocker) parts.push("阻擋 · BLOCKER: " + blocker)
		if (nextAction) parts.push("下一步 · NEXT: " + nextAction)
		return {
			now: now,
			blocker: blocker,
			next_action: nextAction,
			scope: String(o.scope || ""),
			line: parts.join(" · "),
		}
	}

	function pageOperatorSentence(tab, systemState, ctx) {
		var ss = systemState || {}
		var o = ctx || {}
		if (o.page_capability && o.page_capability.operator_sentence) {
			return formatOperatorSentence(o.page_capability.operator_sentence)
		}
		var blocked = localizeOperatorCopy(ss.blocker_compact || "部署權限暫停")
		var repair = localizeOperatorCopy(ss.repair_priority || "重新整理儀表板＋策略簿 · refresh Dashboard + Playbook")
		var tb = String(ss.tradeability || "WAIT").toUpperCase()
		var tabSafe = String(tab || "today")
		var fetchState = String(o.fetch_state || "ok").toLowerCase()
		var mockOnly = !!o.mock_only
		var deployOpen = !!ss.deploy_open
		if (tabSafe === "today" && ss.operator_sentence && ss.operator_sentence.now) {
			return formatOperatorSentence(ss.operator_sentence)
		}
		var base = {
			now: "今日狀態：" + tb + " · 只可監察",
			blocker: blocked,
			nextAction: "只跟進 monitor queue；" + repair,
			scope: "dashboard",
		}
		if (tabSafe === "signals") {
			base = {
				now: deployOpen ? "Deploy review · 可檢視 deploy-qualified" : "無可部署名單 · No deploy names",
				blocker: deployOpen
					? localizeOperatorCopy("verify execution readiness")
					: localizeOperatorCopy("board gate " + tb + " + 0 deploy-qualified"),
				nextAction: deployOpen
					? localizeOperatorCopy("size only deploy-qualified")
					: localizeOperatorCopy("只追蹤 near-miss upgrade candidates · track near-miss upgrades only"),
				scope: "playbook",
			}
		} else if (tabSafe === "scanners") {
			base = {
				now:
					fetchState === "failed_fetch"
						? "Scanner unavailable · 掃描暫不可用"
						: "Discovery research · 研究模式",
				blocker: fetchState === "failed_fetch" ? localizeOperatorCopy("API fetch failed") : blocked,
				nextAction: localizeOperatorCopy("用 cached leaders 或 retry scan · use cached leaders or retry"),
				scope: "discovery",
			}
		} else if (tabSafe === "dossier" || tabSafe === "stock-intel") {
			base = {
				now: "Structure confirm · 結構確認",
				blocker: blocked,
				nextAction: localizeOperatorCopy("review levels; no handoff until gates open"),
				scope: "dossier",
			}
		} else if (tabSafe === "flow") {
			base = {
				now: "Flow unavailable / mock · Flow 暫不可用",
				blocker: mockOnly ? localizeOperatorCopy("live provider not connected") : blocked,
				nextAction: mockOnly
					? "今日忽略 flow · Ignore flow today"
					: localizeOperatorCopy("confirm in Playbook only"),
				scope: "flow",
			}
		} else if (tabSafe === "funds") {
			base = {
				now: fetchState === "failed_fetch" ? "Allocation blocked · 配置暫停" : "Funds research · 研究模式",
				blocker: blocked,
				nextAction:
					fetchState === "failed_fetch"
						? localizeOperatorCopy("no sleeve allocation today; repair market data first")
						: localizeOperatorCopy("index/core posture only"),
				scope: "funds",
			}
		} else if (tabSafe === "guide") {
			base = {
				now: "Reference manual · 參考手冊",
				blocker: "",
				nextAction: "儀表板 → 策略簿 → 檔案 每日流程 · Dashboard → Playbook → Dossier daily flow",
				scope: "guide",
			}
		} else if (tabSafe === "agent") {
			base = {
				now: "Vibe Agent · 熬夜盯盤副駕 · Research / Monitoring only",
				blocker: blocked,
				nextAction: "檢視警報 → Playbook 確認 → 檔案 · Review alerts → Playbook → Dossier",
				scope: "agent",
			}
		} else if (tabSafe === "strategy-lab") {
			base = {
				now: "Strategy Lab · 策略實驗室 · draft + validation",
				blocker: blocked,
				nextAction: "產生草稿 → 驗證 → watch rule → Playbook · Generate → validate → watch rule",
				scope: "strategy-lab",
			}
		} else if (tabSafe === "shadow") {
			base = {
				now: "Shadow Account · 影子帳戶 · behavior diagnostics",
				blocker: blocked,
				nextAction: "比對實際 vs 規則路徑；改善 watch rules · Compare actual vs rule path",
				scope: "shadow",
			}
		} else if (tabSafe === "reports") {
			base = {
				now: "Reports · 報告庫 · inspectable research runs",
				blocker: blocked,
				nextAction: "匯出 MD/JSON；行動前於 Playbook 確認 · Export MD/JSON; confirm in Playbook",
				scope: "reports",
			}
		} else if (tabSafe === "portfolio") {
			base = {
				now: "持倉與風險 · Portfolio & risk",
				blocker: deployOpen ? localizeOperatorCopy("sizing 需閘門開啟 · sizing needs open gates") : blocked,
				nextAction: deployOpen
					? "依 deploy-qualified 調整部位 · size per deploy-qualified"
					: "檢視止損／熱度；新倉僅 monitor · review stops/heat",
				scope: "portfolio",
			}
		} else if (tabSafe === "ops") {
			base = {
				now: "運維 · Ops · health / engine / alerts",
				blocker: blocked,
				nextAction: "檢查 /health、引擎、Discord · check health, engine, Discord",
				scope: "ops",
			}
		} else if (tabSafe === "ibkr") {
			base = {
				now: "IBKR · 券商連線與交付",
				blocker: blocked,
				nextAction: "Gateway → Session → Bracket → Handoff · 逐步確認交付梯",
				scope: "ibkr",
			}
		} else if (tabSafe === "btlab" || tabSafe === "backtest") {
			base = {
				now: "回測室 · Backtest Lab · historical simulation",
				blocker: "回測通過 ≠ 交易許可 · backtest pass ≠ trade permission",
				nextAction: "只作研究；確認請回 Playbook · research only; confirm in Playbook",
				scope: "btlab",
			}
		}
		return formatOperatorSentence(base)
	}

	function buildClientSystemState(opts) {
		var o = opts || {}
		var tb = String(o.tradeability || "WAIT").toUpperCase()
		var blocked = String(o.blocker || "部署權限暫停")
		var repair = String(o.repair || "refresh Dashboard + Playbook")
		var dataTier = String(o.data_tier || (o.degraded ? "STALE" : "FRESH")).toUpperCase()
		var deployOpen = !!o.deploy_open
		var fallback = !!o.fallback_mode
		var globalStrip = !deployOpen || fallback || dataTier !== "FRESH"
		return {
			tradeability: tb,
			deploy_open: deployOpen,
			data_freshness: dataTier,
			blocker_compact: blocked,
			repair_priority: repair,
			global_strip_active: globalStrip,
			operator_sentence: formatOperatorSentence({
				now: "今日狀態：" + tb + " · 只可監察",
				blocker: "原因：" + blocked,
				nextAction: "下一步：只跟進 monitor queue；" + repair,
				scope: "global",
			}),
		}
	}

	/** PM strip / trust strip chip tiers — primary authority first, context second. */
	function partitionHeaderChips(chips, opts) {
		var o = opts || {}
		var primary = []
		var secondary = []
		var infra = []
		if (o.authorityChip) {
			primary.push({ label: o.authorityChip, class: "authority", tier: "primary" })
		}
		if (o.tradeability) {
			primary.push({ label: String(o.tradeability), class: "tradeability", tier: "primary" })
		}
		if (o.fetchBadge) {
			infra.push({ label: String(o.fetchBadge), class: "fetch", tier: "infra" })
		}
		if (o.ibkrChip) {
			infra.push({ label: String(o.ibkrChip), class: "ibkr", tier: "infra" })
		}
		if (o.dataChip) {
			infra.push({ label: String(o.dataChip), class: "data", tier: "infra" })
		}
		;(chips || []).forEach(function (c) {
			var cls = String((c && c.class) || "")
			if (cls === "deploy" || cls === "idea") {
				primary.push(Object.assign({}, c, { tier: "primary" }))
			} else if (cls === "avoid") {
				secondary.push(Object.assign({}, c, { tier: "secondary" }))
			} else {
				secondary.push(Object.assign({}, c, { tier: "secondary" }))
			}
		})
		if (o.modeChip) {
			secondary.push({ label: String(o.modeChip), class: "mode", tier: "secondary" })
		}
		if (o.freshnessChip) {
			secondary.push({ label: String(o.freshnessChip), class: "freshness", tier: "secondary" })
		}
		return { primary: primary, secondary: secondary, infra: infra }
	}

	/** One-time recovery hint after route abort — research shell only, no authority. */
	function routeAbortRecoveryHint(surface) {
		var s = String(surface || "").toLowerCase()
		if (s === "dossier" || s === "dossier_research") {
			return _opsBilingual("路由失敗 — 重試或只載核心欄", "Route failed — retry or Load core only")
		}
		if (s === "discovery" || s === "scanners") {
			return _opsBilingual(
				"掃描路由失敗 — 重試 Run Scanners；後備 funnel 非 deploy 權威",
				"Scanner route failed — retry Run Scanners; fallback funnel is not deploy authority",
			)
		}
		return _opsBilingual(
			"擷取失敗 — badges 恢復後重試；monitor queue 同 Guide 仍安全",
			"Fetch failed — retry when badges clear; monitor queue and Guide remain safe",
		)
	}

	function staleRefreshRecoveryLine() {
		return _opsBilingual(
			"市場 snapshot 過期 — sizing 前請重新整理市場資料",
			"Market snapshot stale — refresh market data before using levels for sizing",
		)
	}

	function engineOffRecoveryLine() {
		return _opsBilingual(
			"引擎 OFF — 於 Ops 啟動；board 可能僅預先計算",
			"Engine OFF - start the engine in Ops; board may be precomputed only",
		)
	}

	/** IBKR recovery copy — aligned with ibkr_diagnosis short codes (not deploy gate). */
	function ibkrLoginToReadyHint(state) {
		var st = state || {}
		var short = String(st.short || "").toUpperCase()
		var hint = String(st.hint || "").trim()
		if (short === "OFFLINE" || short === "NO IBAPI" || short === "API OFF" || st.level === "offline") {
			return hint || "IBKR OFFLINE - start Gateway/TWS and confirm API port"
		}
		if (short === "BLOCKED") {
			return "IBKR BLOCKED - clear the risk gate before handoff"
		}
		if (short === "READY" || st.handoff || st.level === "ready") {
			return hint || "IBKR READY - handoff path verified; confirm bracket alignment before transmit"
		}
		if (short === "LOGIN" || short === "HANDSHAKE" || (st.gw && !st.connected)) {
			return hint || "IBKR LOGIN - connect the session on the IBKR tab; READY required before handoff"
		}
		if (short === "MONITOR" || short === "PARTIAL" || st.level === "partial") {
			return hint || "IBKR PARTIAL - session up; confirm bracket and portfolio sync before handoff"
		}
		return hint || "IBKR OFFLINE - start Gateway/TWS and reconnect from the IBKR tab"
	}

	/** Resolve IBKR host for UI — loopback inside Docker maps to host.docker.internal. */
	function ibkrSyncHostFromStatus(host, docker) {
		var h = String(host || "").trim()
		if (!h) h = docker ? "host.docker.internal" : "127.0.0.1"
		if (docker && ["127.0.0.1", "localhost", "::1"].indexOf(h.toLowerCase()) >= 0) {
			return "host.docker.internal"
		}
		return h
	}

	function ibkrHostPlaceholder(docker) {
		return docker ? "host.docker.internal" : "127.0.0.1"
	}

	/** Mission panel — safe vs blocked unlock (no fake authority). */
	function todayMissionSafeUnlockHint(opts) {
		var o = opts || {}
		if (o.waitDay) {
			return localizeUiText("Blocked: deploy · Safe: monitors · near-miss · Playbook ranking")
		}
		if (!o.ibkrReady) {
			return localizeUiText("Blocked: IBKR handoff · Safe: dossier core-only · monitor queue")
		}
		if (!o.engineRunning) {
			return localizeUiText("Blocked: new cycle sizing · Safe: Guide · monitors until engine ON")
		}
		return ""
	}

	/** Staging soak anchors — mirrors fetch_surface_state.soak_confirmation_signals(). */
	function soakConfirmationSelectors() {
		return {
			instantDegraded: '[data-cc="instant-degraded-banner"]',
			warmupStrip: '[data-cc="warmup-context-strip"]',
			deployStrip: '[data-cc="deploy-status-strip"]',
			missionPanel: '[data-cc="today-mission-panel"]',
			playbookSurface: '[data-cc="playbook-surface"]',
			playbookCostRankPill: '[data-cc="playbook-cost-rank-pill"]',
			playbookStrategyDecayLine: '[data-cc="playbook-strategy-decay-line"]',
			execAnalyticsSample: '[data-cc="exec-analytics-sample"]',
			regimeStackStrip: '[data-cc="regime-stack-strip"]',
			aiReasonCodes: '[data-cc="ai-reason-codes"]',
			marketStale: '[data-cc="market-strip-stale"]',
			opsRunbook: '[data-cc="ops-recovery-runbook"]',
			dataContractStrip: '[data-cc="data-contract-strip"]',
		}
	}

	/** Opportunity intelligence — always research / monitor, never deploy chip. */
	function opportunityIntelligenceBadge(payload) {
		var p = payload || {}
		if (p.degraded || p.instant_degraded) return "MOCK / DEGRADED"
		var tier = String(p.data_tier || "").toLowerCase()
		if (tier === "mock") return "MOCK ONLY"
		return "RESEARCH ONLY"
	}

	var DOSSIER_CONFIRM_ONLY_SIZING = "Confirm-only - no sizing or IBKR handoff"

	function dossierQuoteAvailable(data) {
		var d = data || {}
		if (d.quote_pending || d.quote_unavailable) return false
		var p = Number(d.price)
		return !isNaN(p) && p > 0
	}

	function dossierPriceDisplay(data) {
		if (!dossierQuoteAvailable(data)) return "Quote unavailable"
		return "$" + Number(data.price).toFixed(2)
	}

	function dossierChangePctDisplay(data) {
		if (!dossierQuoteAvailable(data)) return "—"
		var c = Number(data.change_pct)
		if (isNaN(c)) return "—"
		return (c >= 0 ? "+" : "") + c.toFixed(2) + "%"
	}

	function dossierConfirmOnlySizingLine() {
		return DOSSIER_CONFIRM_ONLY_SIZING
	}

	function dossierSizingDisplay(blocked, reason) {
		if (!blocked) return ""
		var r = String(reason || "")
		if (r === "confirm_only") return "—"
		if (r === "failed" || r === "partial") return "Blocked"
		return "—"
	}

	function dossierSizingExplanation(blocked, reason) {
		if (!blocked) return ""
		var r = String(reason || "")
		if (r === "confirm_only") return DOSSIER_CONFIRM_ONLY_SIZING
		if (r === "failed" || r === "partial") return "Sizing blocked until live dossier data loads"
		if (r === "rr_unavailable") return "Sizing unavailable - R:R not confirmed"
		return "Size unavailable"
	}

	function dossierTradePlanNote(opts) {
		var o = opts || {}
		var note = String(o.note || o.setup_type || "").trim()
		var researchOnly = !!o.research_only
		var levelsBlank = !!o.levels_blank
		if (researchOnly && levelsBlank) {
			return "Live structure unavailable - confirm-only dossier"
		}
		if (levelsBlank) return "Live structure unavailable"
		if (note) return note
		return "Structure-based plan"
	}

	function opportunityIntelDegraded(payload) {
		var p = payload || {}
		return !!(p.degraded || p.instant_degraded || String(p.data_tier || "").toLowerCase() === "mock")
	}

	function insiderContextLabel(quality, payload) {
		var degraded = opportunityIntelDegraded(payload)
		var q = String(quality || "").toLowerCase()
		var map = {
			supportive_only: degraded ? "Supportive context (mock/lagged)" : "Supportive context",
			notable_accumulation: degraded ? "Possible accumulation (mock/lagged)" : "Notable accumulation (lagged)",
			notable_distribution: degraded ? "Possible distribution (mock/lagged)" : "Distribution risk (lagged)",
			noise: degraded ? "Routine Form 4 (mock)" : "Routine Form 4",
			insufficient_data: degraded ? "Insufficient history (mock)" : "Insufficient history",
		}
		return map[q] || (degraded ? "Insider context (mock/lagged)" : "Insider context (lagged)")
	}

	function institutionalSponsorshipLabel(verdict, payload) {
		var v = String(verdict || "").trim()
		if (!v) return "—"
		if (!opportunityIntelDegraded(payload)) return v
		var low = v.toLowerCase()
		if (low.indexOf("added sponsorship") >= 0) {
			return "Illustrative added sponsorship (mock/lagged)"
		}
		if (low.indexOf("mixed") >= 0 || low.indexOf("unchanged") >= 0) {
			return "Illustrative mixed / unchanged (mock/lagged)"
		}
		return v + " (mock/lagged)"
	}

	function eventRiskDowngradeOnly(events) {
		var list = events || []
		for (var i = 0; i < list.length; i++) {
			if (list[i] && list[i].impact_framing === "risk_downgrade") return true
		}
		return false
	}

	function strategyCurveHealthPill(state) {
		var s = String(state || "").toLowerCase()
		if (s === "paused" || s === "monitor") return "pr"
		if (s === "pilot" || s === "reduced") return "pa"
		return "pw"
	}

	function quantResearchBadge(payload) {
		var p = payload || {}
		if (p.degraded || p.instant_degraded) return "MOCK / DEGRADED"
		if (p.data_mode === "research_only" || p.research_only) return "RESEARCH ONLY"
		if (p.data_mode === "ops_probe") return "OPS CONTEXT"
		return "RESEARCH ONLY"
	}

	function costRankTag(row) {
		var r = row || {}
		var label = String(r.cost_rank_label || "").toLowerCase()
		if (label === "net_survives") return "Net survives cost"
		if (label === "cost_too_high") return "Cost drag high"
		return "Monitor only (cost)"
	}

	function costRankPillClass(row) {
		var r = row || {}
		var label = String(r.cost_rank_label || "").toLowerCase()
		if (label === "net_survives") return "pg"
		if (label === "cost_too_high") return "pa"
		return "pw"
	}

	function indexRegimeStripLine(summary, strip) {
		var s = summary || {}
		var st = strip || {}
		var line = String(st.line || s.strip_line || s.summary || "").trim()
		if (!line) return "Index regime unavailable — MOCK/DEGRADED"
		if (s.degraded || st.degraded) return line.indexOf("MOCK") >= 0 ? line : "MOCK/DEGRADED · " + line
		return line + " — monitor only, not deploy"
	}

	function regimeFitTag(row) {
		var fit = String((row || {}).regime_fit || "").toLowerCase()
		if (fit === "aligned") return "Regime aligned"
		if (fit === "stressed_filter") return "Stressed filter"
		if (fit === "wait_filter") return "WAIT filter"
		if (fit === "lag_vs_index") return "Lags index"
		return "Selective filter"
	}

	function regimeFitPillClass(row) {
		var fit = String((row || {}).regime_fit || "").toLowerCase()
		if (fit === "aligned") return "pg"
		if (fit === "stressed_filter" || fit === "lag_vs_index") return "pr"
		if (fit === "wait_filter") return "pa"
		return "pw"
	}

	function indexLeadershipTag(row) {
		var tag = String((row || {}).index_leadership || "").toLowerCase()
		if (tag === "outperform") return "Leads index"
		if (tag === "lag") return "Lags index"
		if (tag === "inline") return "Inline index"
		return "Index rel. unknown"
	}

	function indexLeadershipDossierLine(block) {
		var b = block || {}
		var summary = String(b.summary || "").trim()
		if (b.degraded && summary.indexOf("MOCK") < 0) {
			return (summary || "Relative leadership unavailable") + " — MOCK/DEGRADED · confirm-only"
		}
		return (summary || "Relative leadership — confirm-only") + " — not deploy authority"
	}

	function drawdownSizingLine(sizing) {
		var s = sizing || {}
		if (!s.sizing_mode || s.sizing_mode === "blocked") {
			return "DD sizing blocked — confirm-only / research / stale"
		}
		return (
			(s.sizing_label || s.sizing_mode) +
			" · " +
			(s.size_multiplier != null ? s.size_multiplier + "× template" : "")
		)
	}

	function quantSleeveHint(alloc) {
		var a = alloc || {}
		var route = a.routing || a.sleeve_strip || {}
		if (!route.strongest && !route.weakest) return ""
		var s = route.strongest && route.strongest.name ? route.strongest.name : "—"
		var w = route.weakest && route.weakest.name ? route.weakest.name : "—"
		return "Quant hint: strongest sleeve " + s + " · weakest " + w + " (not a trade route)"
	}

	function aiReasonCodeLine(code) {
		var c = code || {}
		var msg = String(c.message || "").trim()
		if (!msg) return "AI context — explanatory only, not deploy authority"
		return msg + " — monitor only"
	}

	function execAnalyticsSample(analytics) {
		var a = analytics || {}
		var label = String(a.sample_state_label || (a.fill_quality && a.fill_quality.status_label) || "").trim()
		if (!label) return "Execution analytics unavailable — monitor only"
		return label + " — not deploy authority"
	}

	function regimeStackStripLine(summary) {
		var s = summary || {}
		var line = String(s.strip_line || "").trim()
		if (!line) return "Regime stack unavailable — MOCK/DEGRADED"
		if (s.degraded && line.indexOf("MOCK") < 0) return "MOCK/DEGRADED · " + line
		return line + " — monitor only, not deploy"
	}

	function allocatorStanceHint(stance) {
		var a = stance || {}
		var sug = String(a.suggestion || "").trim()
		if (sug) return sug
		return quantSleeveHint(a)
	}

	function aiContradictionDossierLine(hint, degraded) {
		var text = String(hint || "").trim()
		if (!text) return ""
		if (degraded && text.indexOf("MOCK") < 0) text = text + " — MOCK/DEGRADED"
		return text + " — confirm-only, not deploy authority"
	}

	/** Safe operator actions while loading or on WAIT (no deploy authority). */
	function operatorLoadingSafeLine(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		if (mode === "loading" || String(o.ccMode || "").toUpperCase() === "LOADING") {
			return (
				"安全操作：monitor queue、指南、檔案核心欄 — 等 /health mode=full 後才 sizing 或 IBKR handoff · " +
				"Safe now: monitor queue, Guide, dossier core-only — wait for full health before sizing"
			)
		}
		if (o.fetchFailed || o.instantDegraded) {
			return (
				"安全操作：指南、monitor、檔案核心 — 擷取恢復後重試；後備不可部署 · " +
				"Safe now: Guide, monitors, dossier core-only — retry when fetch clears"
			)
		}
		if (o.waitDay) {
			return "安全操作：near-miss monitor、探索脈絡、Playbook 排序 — WAIT 日禁止部署 · Safe now: near-miss monitors, Discovery — deploy blocked on WAIT"
		}
		return ""
	}

	global.CCHelpers = {
		severityBadgeClass: severityBadgeClass,
		surfaceWarmupLoadingLine: surfaceWarmupLoadingLine,
		warmupStatusLine: warmupStatusLine,
		warmupUpgradeQueue: warmupUpgradeQueue,
		warmupContextStripVisible: warmupContextStripVisible,
		loadingSessionRecoveryLine: loadingSessionRecoveryLine,
		instantDegradedBannerHint: instantDegradedBannerHint,
		todayMissionMonitorsLabel: todayMissionMonitorsLabel,
		todayMissionQuantClusterLines: todayMissionQuantClusterLines,
		todayBoardHeroSynthesisLine: todayBoardHeroSynthesisLine,
		todayExecutionReadinessDiagnostic: todayExecutionReadinessDiagnostic,
		playbookStrategyDecayLine: playbookStrategyDecayLine,
		todayMissionMonitorsColumnHint: todayMissionMonitorsColumnHint,
		playbookWhatToMonitorLine: playbookWhatToMonitorLine,
		todayMissionWaitSubtitle: todayMissionWaitSubtitle,
		todayMissionSystemBlockers: todayMissionSystemBlockers,
		todayMissionBlockersTitle: todayMissionBlockersTitle,
		todayMissionEmptyBlockersCopy: todayMissionEmptyBlockersCopy,
		formatOperatorSentence: formatOperatorSentence,
		localizeOperatorCopy: localizeOperatorCopy,
		localizeUiText: localizeUiText,
		localizeIbkrBracketReason: localizeIbkrBracketReason,
		localizeOpsRuntimeText: localizeOpsRuntimeText,
		localizeOpsComponentName: localizeOpsComponentName,
		localizeOpsAdvancedDiagnosticsCopy: localizeOpsAdvancedDiagnosticsCopy,
		opsAdvancedDiagnosticsTitle: opsAdvancedDiagnosticsTitle,
		opsAdvancedDiagnosticsCollapsedTitle: opsAdvancedDiagnosticsCollapsedTitle,
		localizeOpsAdvancedSectionKey: localizeOpsAdvancedSectionKey,
		localizeOpsAdvancedSectionLabel: localizeOpsAdvancedSectionLabel,
		localizeOpsAdvancedSectionDetail: localizeOpsAdvancedSectionDetail,
		localizeOpsMetricReason: localizeOpsMetricReason,
		localizeOpsDictKey: localizeOpsDictKey,
		localizeOpsMachineField: localizeOpsMachineField,
		opsSystemVerdictTitle: opsSystemVerdictTitle,
		opsDecisionMachinesTitle: opsDecisionMachinesTitle,
		opsExecutionReadinessTitle: opsExecutionReadinessTitle,
		opsExecutionReadinessHint: opsExecutionReadinessHint,
		opsBlockersTitle: opsBlockersTitle,
		opsNextActionsTitle: opsNextActionsTitle,
		opsEngineStateTitle: opsEngineStateTitle,
		opsUptimeLatencyTitle: opsUptimeLatencyTitle,
		opsExperimentalModulesTitle: opsExperimentalModulesTitle,
		opsProbeVerdictNote: opsProbeVerdictNote,
		opsMetricLabel: opsMetricLabel,
		opsHttp500BannerText: opsHttp500BannerText,
		opsPaperLiveBoundaryTitle: opsPaperLiveBoundaryTitle,
		opsLastSuccessfulTimesTitle: opsLastSuccessfulTimesTitle,
		opsOperationalEventsTitle: opsOperationalEventsTitle,
		opsWhyNoSignalsTitle: opsWhyNoSignalsTitle,
		opsFailedFreshnessHint: opsFailedFreshnessHint,
		opsPhase9EnginesTitle: opsPhase9EnginesTitle,
		opsPhase9LoadFailed: opsPhase9LoadFailed,
		opsCacheStatisticsTitle: opsCacheStatisticsTitle,
		opsSelfLearningEngineTitle: opsSelfLearningEngineTitle,
		opsSelfLearnLabel: opsSelfLearnLabel,
		opsWhatThisMeansTitle: opsWhatThisMeansTitle,
		opsBoardStateCachedNote: opsBoardStateCachedNote,
		opsEngineStoppedHelpCopy: opsEngineStoppedHelpCopy,
		opsStartEngineLabel: opsStartEngineLabel,
		opsViewErrorLogLabel: opsViewErrorLogLabel,
		opsRecoveryRunbookTitle: opsRecoveryRunbookTitle,
		opsBlocksCapitalTitle: opsBlocksCapitalTitle,
		opsSafeDegradedTitle: opsSafeDegradedTitle,
		opsNoHardBlocksCopy: opsNoHardBlocksCopy,
		opsPlatformUpdatesTitle: opsPlatformUpdatesTitle,
		opsSessionErrorLogTitle: opsSessionErrorLogTitle,
		opsSeeRecoveryRunbookPrefix: opsSeeRecoveryRunbookPrefix,
		opsBootTimeLine: opsBootTimeLine,
		opsLastCycleLine: opsLastCycleLine,
		opsIbkrSessionInactiveTitle: opsIbkrSessionInactiveTitle,
		opsIbkrGatewayReachableNote: opsIbkrGatewayReachableNote,
		opsIbkrNoSessionNote: opsIbkrNoSessionNote,
		opsOpenIbkrConnectLabel: opsOpenIbkrConnectLabel,
		opsCriticalGapsPrefix: opsCriticalGapsPrefix,
		opsCriticalFlagText: opsCriticalFlagText,
		opsNoCycleSessionWarning: opsNoCycleSessionWarning,
		opsNoCacheWarning: opsNoCacheWarning,
		opsTradesTodayPill: opsTradesTodayPill,
		opsRunCycleLabel: opsRunCycleLabel,
		opsSelfLearnEnabledLabel: opsSelfLearnEnabledLabel,
		opsHttp500IntroSuffix: opsHttp500IntroSuffix,
		opsWhyNoSignalsCell: opsWhyNoSignalsCell,
		localizeOpsWhyNoSignalsGate: localizeOpsWhyNoSignalsGate,
		pageOperatorSentence: pageOperatorSentence,
		buildClientSystemState: buildClientSystemState,
		playbookWhatToMonitorLine: playbookWhatToMonitorLine,
		partitionHeaderChips: partitionHeaderChips,
		operatorLoadingSafeLine: operatorLoadingSafeLine,
		routeAbortRecoveryHint: routeAbortRecoveryHint,
		staleRefreshRecoveryLine: staleRefreshRecoveryLine,
		engineOffRecoveryLine: engineOffRecoveryLine,
		ibkrLoginToReadyHint: ibkrLoginToReadyHint,
		ibkrSyncHostFromStatus: ibkrSyncHostFromStatus,
		ibkrHostPlaceholder: ibkrHostPlaceholder,
		todayMissionSafeUnlockHint: todayMissionSafeUnlockHint,
		soakConfirmationSelectors: soakConfirmationSelectors,
		opportunityIntelligenceBadge: opportunityIntelligenceBadge,
		dossierQuoteAvailable: dossierQuoteAvailable,
		dossierPriceDisplay: dossierPriceDisplay,
		dossierChangePctDisplay: dossierChangePctDisplay,
		dossierConfirmOnlySizingLine: dossierConfirmOnlySizingLine,
		dossierSizingDisplay: dossierSizingDisplay,
		dossierSizingExplanation: dossierSizingExplanation,
		dossierTradePlanNote: dossierTradePlanNote,
		institutionalSponsorshipLabel: institutionalSponsorshipLabel,
		insiderContextLabel: insiderContextLabel,
		eventRiskDowngradeOnly: eventRiskDowngradeOnly,
		strategyCurveHealthPill: strategyCurveHealthPill,
		quantResearchBadge: quantResearchBadge,
		costRankTag: costRankTag,
		costRankPillClass: costRankPillClass,
		indexRegimeStripLine: indexRegimeStripLine,
		regimeFitTag: regimeFitTag,
		regimeFitPillClass: regimeFitPillClass,
		indexLeadershipTag: indexLeadershipTag,
		indexLeadershipDossierLine: indexLeadershipDossierLine,
		drawdownSizingLine: drawdownSizingLine,
		quantSleeveHint: quantSleeveHint,
		aiReasonCodeLine: aiReasonCodeLine,
		execAnalyticsSample: execAnalyticsSample,
		regimeStackStripLine: regimeStackStripLine,
		allocatorStanceHint: allocatorStanceHint,
		aiContradictionDossierLine: aiContradictionDossierLine,
	}
})(typeof window !== "undefined" ? window : globalThis)

/* CC_APP_BUNDLE_START — cc() Alpine app (source: cc-app.js) */
function ccStoredObject(key) {
	try {
		const raw = localStorage.getItem(key)
		if (!raw) return {}
		const parsed = JSON.parse(raw)
		return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {}
	} catch (e) {
		try {
			localStorage.removeItem(key)
		} catch (_e) {}
		return {}
	}
}
function ccNormalizeTab(tab, fallback) {
	const safeFallback = fallback || "today"
	const value = String(tab || "").trim()
	if (!value) return safeFallback
	const allowed = new Set([
		"guide",
		"today",
		"signals",
		"scanners",
		"portfolio",
		"dossier",
		"leaders",
		"funds",
		"flow",
		"rs",
		"command",
		"notrade",
		"ops",
		"ibkr",
		"btlab",
		"agent",
		"strategy-lab",
		"shadow",
		"reports",
	])
	return allowed.has(value) ? value : safeFallback
}
function cc() {
	return {
		tab: ccNormalizeTab(
			(function () {
				try {
					const qs = new URLSearchParams(location.search || "")
					return qs.get("tab") || "today"
				} catch (e) {
					return "today"
				}
			})(),
			"today",
		),
		tabs: [
			{ id: "guide", icon: "📖", label: "Guide 指南" },
			{ id: "today", icon: "🎯", label: "Dashboard 儀表板" },
			{ id: "signals", icon: "📋", label: "Playbook 策略簿" },
			{ id: "scanners", icon: "🔬", label: "Discovery 探索" },
			{ id: "portfolio", icon: "💼", label: "Portfolio 持倉與風險" },
			{ id: "dossier", icon: "🔍", label: "Dossier 檔案" },
		],
		moreTabs: [
			{ id: "agent", icon: "🤖", label: "Agent 盯盤 · monitor" },
			{ id: "strategy-lab", icon: "🧪", label: "Strategy Lab 策略實驗室" },
			{ id: "shadow", icon: "🧾", label: "Shadow 影子帳戶" },
			{ id: "reports", icon: "📚", label: "Reports 報告庫" },
			{ id: "funds", icon: "💼", label: "Funds 基金" },
			{ id: "flow", icon: "💧", label: "Flow 資金流" },
			{ id: "rs", icon: "📈", label: "RS 相對強度 · research" },
			{ id: "command", icon: "🖥", label: "Command 指揮台 · advanced", hidden_from_primary_nav: true },
			{ id: "notrade", icon: "🚫", label: "Rejections 否決" },
			{ id: "ops", icon: "⚙️", label: "Ops 運維" },
			{ id: "ibkr", icon: "⚡", label: "IBKR 券商" },
			{ id: "btlab", icon: "🧪", label: "Backtest Lab 回測室" },
		],

		showMore: false,
		dataContractDismissed: false,
		pmStripChipMenuOpen: false,
		cc_status: {
			mode: "PAPER",
			breaker: false,
			breaker_reason: "",
			ibkr_connected: false,
			ibkr_mode: "paper",
			ibkr_gateway: false,
			ibkr_monitoring: false,
			ibkr_health_label: "",
			uptime_s: 0,
			last_fetch: 0,
		},
		ccHeader: {
			decision_authority: null,
			page_authority_mode: "diagnostic",
			portfolio_context: null,
			header_summary: null,
		},
		surfaceFetchHints: {},
		live: false,
		clock: "",
		regime: {},
		indices: [],
		macro: [],
		sectors: [],
		asia: [],
		trust: {},
		marketStrip: {
			loading: false,
			error: "",
			source: "",
			lastOk: null,
			snapshotAt: null,
			renderedAt: null,
			fromPulse: false,
		},
		sig: {
			mode: "—",
			source: "",
			as_of: "",
			recs: [],
			strategy_scores: {},
			no_trade_reason: null,
			scan_meta: null,
		},
		dos: {
			ticker: "",
			loading: false,
			loadingEnrich: false,
			status: "idle_no_query",
			data: null,
			intel: null,
			oppIntel: null,
			oppIntelLoading: false,
			error: "",
			partialNotice: "",
			fetchDetail: "",
			failedModule: "",
			staleAt: null,
			subTab: "decision",
			showSignals: true,
			chartPeriod: "6mo",
			benchPeriod: "1y",
			chartSignals: [],
			benchStats: null,
			benchSummary: null,
			benchMonthly: null,
			benchQuarterly: null,
			benchYearly: null,
			benchTab: "monthly",
			buyPrice: "",
			advice: null,
			adviceLoading: false,
			peers: null,
			peersLoading: false,
			conviction: null,
			convictionLoading: false,
			optionsData: null,
			optionsLoading: false,
		},
		playbookFocusTicker: "",
		pf: {
			loading: false,
			source: "manual",
			positions: [],
			alerts: [],
			summary: null,
			corrPreview: null,
			showAdd: false,
			showAdvanced: false,
			addTicker: "",
			addShares: 0,
			addEntry: 0,
			addStop: 0,
			addT1r: 0,
			addT2r: 0,
			addNotes: "",
			addSleeve: "",
			addSector: "",
			addError: "",
			addSuccess: "",
			editTicker: null,
		},
		pfDecision: null,
		pfDecisionLoading: false,
		pfQuantSizing: null,
		pfEquity: null,
		pfEquityLoading: false,
		platformExtras: { catalyst: null, pmMemo: null, loading: false },
		aosMonitors: { rules: [], alerts: [], loading: false },
		vibeAgent: {
			loading: false,
			error: "",
			status: null,
			brief: null,
			rules: [],
			alerts: [],
			intents: [],
			journal: [],
			intentText: "",
			intentPlan: null,
			guardrail: null,
			page_capability: null,
			safety: null,
			ruleDraft: { name: "", asset: "", ruleType: "price_zone_touch", condition: "", expiryDays: 14 },
			paused: false,
		},
		strategyLab: {
			loading: false,
			error: "",
			prompt: "",
			draft: null,
			validation: null,
			committee: null,
			pipeline: null,
			page_capability: null,
			safety: null,
			pineExport: "",
		},
		shadowAccount: { loading: false, error: "", tradesJson: "", result: null, page_capability: null },
		reportsLib: { loading: false, error: "", reports: [], selected: null, exportText: "", page_capability: null },
		ledgerView: {
			loading: false,
			loaded: false,
			rows: [],
			stats: null,
			filterStrategy: "",
			filterDirection: "",
			filterTicker: "",
			expanded: false,
		},
		factory: {
			loading: false,
			ticker: "SPY",
			period: "2y",
			mode: "demo",
			result: null,
			detail: null,
			showDetail: false,
			sortBy: "score",
		},
		brief: { loading: false, data: null },
		bt: { ticker: "AAPL", strategy: "all", period: "5y", loading: false, result: null },
		// ── DEAD-CODE WARNING (no UI binding, kept only because JS methods still reference them) ──
		// To be removed once the corresponding fetch* methods are deleted: factory, benchBT, fundMonitor, pmStrip, tradeIntel, tt, bt
		// Already deleted (true orphans): perfTracker, fundLab, modelFunds, tradeJournal, apiEndpoints, oppScanner, rsData, rsFilter, rejectsData, noTradeData
		benchBT: { period: "5y", benchmark: "SPY", loading: false, data: null, error: "" },
		fundMonitor: {
			loading: false,
			data: null,
			console: null,
			error: "",
			lastRefresh: null,
			autoRefreshTimer: null,
			benchmark: "SPY",
			activeFund: null,
		},
		leadersPanel: { loading: false, data: null, error: "" },
		pmStrip: { funds: [], lastFetch: 0 },
		desk: { portfolio: null, monitor: null, strategies: null },
		leadersDash: {},
		leadersView: "hub",
		leadersHub: { loading: false, leaders: [] },
		leadersFilter: { category: "", quality: "", search: "" },
		leadersDetail: null,
		leadersConsensus: { items: [] },
		leadersConsensusVerified: false,
		leadersFlow: { items: [] },
		leadersBaskets: { baskets: [] },
		leadersAlerts: { alerts: [] },
		tradeIntel: {
			loading: false,
			data: null,
			error: "",
			confData: null,
			mistakesData: null,
			aiLoading: false,
			aiError: "",
			aiReview: null,
			selectedTradeKey: "",
		},
		ibkr: {
			connected: false,
			mode: "paper",
			host: "127.0.0.1",
			docker: false,
			loading: false,
			pingResult: null,
			account: null,
			positions: [],
			readiness: null,
			diagnostics: null,
			health: null,
			health_label: "",
			session_usable: false,
			monitoring_only: false,
			openOrders: [],
			recentFills: [],
			portfolioCompare: { manual: 0, broker: 0, note: "" },
			lastSyncedAt: null,
			orderPreview: null,
			orderForm: {
				symbol: "",
				secType: "STK",
				action: "BUY",
				qty: 1,
				orderType: "MKT",
				limitPrice: "",
				stopPrice: "",
				tif: "DAY",
				useBracket: false,
				targetPrice: "",
				trail: false,
				trailKind: "percent",
				trailValue: "",
			},
			orderResult: null,
			orderError: "",
			statusLoading: false,
			statusFetchError: "",
			lastRefresh: null,
			workingBracket: null,
			bracketArchive: [],
		},
		ops: {
			running: false,
			cycle_count: 0,
			signals_today: 0,
			trades_today: 0,
			circuit_breaker: false,
			circuit_breaker_reason: "",
			dry_run: true,
			components: {},
			engineStarting: false,
		},
		opsPanel: "health",
		changelogPanel: {
			loading: false,
			loaded: false,
			error: "",
			timeout: false,
			version: "",
			product: "CC",
			entries: [],
		},
		errorLog: { loading: false, error: "", entries: [], total: 0, filter: "all" },
		providers: {
			yfinance: false,
			regime_router: false,
			alpaca: { configured: false, connected: false, paper: true },
		},
		opsDetail: {},
		today7: {
			regime: null,
			top_ranked: [],
			filter_funnel: null,
			avoid_list: [],
			avoid_grouped: null,
			bucket_quality: [],
			decision_model: null,
			decision_hierarchy: null,
			passive_baseline: null,
			complexity_challenge: null,
			restraint: null,
			surface_authority: null,
			crisis_regime: null,
			naval_clarity: null,
			buffett_clarity: null,
			index_fund_posture: null,
			principles_posture: null,
			todays_decision: null,
			decision_authority: null,
			bdr_summary: null,
			tradeability: "",
			what_changed: [],
			event_risks: [],
			best_family: null,
			pulse: null,
			narrative: "",
			ai_narrative: null,
			ai_loading: false,
			ai_provider: "",
			ai_model: "",
			ai_error: "",
			ai_configured: false,
			ai_setup_hint: "",
			date: "",
			trust: {},
			best_action: null,
			overlap_warning: null,
			near_miss: [],
			no_setup_diagnosis: null,
			quant_cluster_hints: [],
			unlock_deploy: null,
			regime_wait_explanation: [],
			monitor_triggers: [],
			sleeve_summary: null,
			quant_alloc: null,
			execution_readiness: null,
			evidence_badges: null,
			cross_asset_confirmation: null,
			index_regime_summary: null,
			regime_strip: null,
			regime_stack_summary: null,
			allocator_stance: null,
			ai_reason_codes: [],
			score_reconciliation: null,
			ai_commentary_open: false,
			avoid_collapsed: true,
		},
		btLab: {
			ticker: "AAPL",
			strategy: "all",
			period: "6mo",
			loading: false,
			data: null,
			quantCurve: null,
			error: "",
			walkForward: true,
		},
		dosWorkstation: { loading: false, data: null },
		pfScenario: { loading: false, list: [], result: null, selected: "" },
		pfRebalanceTargets: "",
		pfStopSetter: { open: false, ticker: "", stop: "" },
		decisionHub: null,
		opps: [],
		oppsSort: "score",
		selfLearn: {
			status: null,
			triggering: false,
			lastResult: "",
			calibration: null,
			calibBuckets: null,
			ab: null,
			ledger: null,
			lastAutoSchedule: null,
			feedback: null,
		},
		stratHealth: { loading: false, data: null, window: 30, err: "" },
		histVar: { loading: false, data: null, err: "", last_run: 0 },
		freshness: null,
		risk_alerts: null,
		alerts_history: null,
		showAlertsModal: false,
		uiExpandAll: false,
		bdrPanelOpen: false,
		playbookSizing: {},
		brief_status: null,
		brief_regen_loading: false,
		tt: {
			show: false,
			ticker: "AAPL",
			date: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
			strategy: "all",
			loading: false,
			data: null,
			err: "",
			result: null,
		},
		exec: { metrics: null },
		risk: { summary: null },
		rl: { thompson: null, featureIC: null },
		notifyLog: { events: [], discord_configured: false, discord_status: null, loading: false, loaded: false },
		scannerHub: {
			loading: false,
			data: null,
			category: null,
			duration_ms: 0,
			last_run: null,
			universe: 0,
			error: "",
			expanded: false,
		},
		rsPanel: { loading: false, data: null, error: "", sectorFilter: "", expanded: false },
		rankedOpps: {
			loading: false,
			refreshing: false,
			fetch_failed: false,
			rows: [],
			actionFilter: "",
			sectorFilter: "",
			source: "playbook",
			board_mode: "",
			board_mode_label: "",
			board_message: "",
			board_explanation: "",
			snapshot_timestamp: "",
			rejection_clusters: [],
			rejection_clusters_note: "",
			unlock_deploy: null,
			emergency: null,
			bestAction: null,
			decision_authority: null,
			overlapWarning: null,
			warning: "",
			avoid_grouped: null,
			bucket_quality: [],
			near_miss: [],
			avoid_collapsed: true,
			filter_funnel: null,
			degraded_banner: "",
			instant_degraded: false,
			operator_board: null,
			watch_queues: null,
			watch_intelligence_summary: null,
			ai_vibe: null,
			board_posture: null,
			paper_automation: null,
			auto_execution: null,
			monitor_auto_actions: null,
			operator_sections_open: false,
			compact_rows: null,
			rank_buckets: null,
			system_state: null,
		},
		flowPanel: { loading: false, data: null, radar: null, decision: null, error: "" },
		opsConsole: { loading: false, data: null, error: "" },
		opsRuntime: { loading: false, http_status: null, ok: false, error: "", data: null },
		rejectionsPanel: { loading: false, data: null, error: "", regimeReasons: [], regime: null },
		rejectionsClusterExpanded: {},
		cmd: {
			loading: false,
			activeTicker: "",
			decision: null,
			agent: null,
			agentError: "",
			agentJournal: [],
			agentReliability: null,
			agentReliabilityError: "",
			agentReliabilityLoading: false,
			watchlistRows: [], // [{ticker,action,confidence,rs_state}]
			error: "",
		},
		_failCount: 0,
		_retryTimer: null,
		_fundRetryTimer: null,
		apiError: "",
		healthData: null,
		healthMode: "loading",
		instantDegradedBanner: "",
		instantDegradedDismissed: false,
		ac: { query: "", results: [], show: false, target: "", selIdx: -1, timer: null },
		ccStarred: ccStoredObject("ccStarred"),
		ccLoved: ccStoredObject("ccLoved"),
		ccWatchlist: ccStoredObject("ccWatchlist"),
		init() {
			this.tab = ccNormalizeTab(this.tab, "today")
			this.dataContractDismissed = localStorage.getItem("cc_data_contract_dismissed") === "1"
			if (typeof window !== "undefined") {
				window.addEventListener("resize", () => {
					this.pmStripChipMenuOpen = false
				})
			}
			this.tick()
			setInterval(() => this.tick(), 1000)
			this.fetchHealth()
			setInterval(() => this.fetchHealth(), 15000)
			// Phase 1 — critical path (avoid burst 503s on cold start)
			this.fetchCcStatus()
			setInterval(() => this.fetchCcStatus(), 30000)
			this.fetchToday7()
			setInterval(() => this.fetchToday7(), 120000)
			setTimeout(() => this.fetchMarketStrip(), 400)
			setInterval(() => this.fetchMarketStrip(), 180000)
			// Signals feed loads on tab switch only (avoids duplicate /api/recommendations traffic)
			// Phase 2 — secondary panels (staggered)
			setTimeout(() => {
				this.fetchRanked()
				this.fetchFlow()
			}, 600)
			setTimeout(() => {
				this.fetchFunds()
			}, 1200)
			setTimeout(() => {
				this.fetchDecisionHub()
				this.fetchPortfolio()
				this.fetchAosMonitors()
				this.fetchAIStatus()
			}, 2000)
			setTimeout(() => {
				this.fetchDesk()
				this.fetchLeadersDashboard()
			}, 3000)
			setInterval(() => this.fetchDesk(), 120000)
			setInterval(() => this.fetchLeadersDashboard(), 300000)
			setInterval(() => this.fetchDecisionHub(), 120000)
			setInterval(() => this.fetchPortfolio(), 180000)
			// Per-strategy realized analytics (cheap; refresh every 10min)
			this.fetchStrategyHealth()
			setInterval(() => this.fetchStrategyHealth(), 600000)
			// Data freshness watchdog (every 60s; cheap — already-cached histories)
			this.fetchFreshness()
			setInterval(() => this.fetchFreshness(), 60000)
			// Position-level risk alerts (every 60s)
			this.fetchRiskAlerts()
			setInterval(() => this.fetchRiskAlerts(), 60000)
			// Morning brief freshness check (every 5 min — cheap, just stats a file)
			this.fetchBriefStatus()
			setInterval(() => this.fetchBriefStatus(), 300000)
			this.hydrateRankedFromCache()
			this.hydrateToday7FromCache()
			this.hydrateScannersFromCache()
			this.fetchWarmupBriefBoard()
			setTimeout(() => {
				if (!this.playbookBoardHasContent()) this.fetchWarmupBriefBoard()
			}, 400)
			setTimeout(() => {
				if (this.rankedOpps.loading) this.rankedOpps.loading = false
				if (this.rankedOpps.refreshing) this.rankedOpps.refreshing = false
			}, 10000)
			try {
				this.instantDegradedDismissed = sessionStorage.getItem("cc_instant_degraded_dismissed") === "1"
			} catch (e) {}
		},
		async fetchStrategyHealth() {
			// Per-strategy realized Sharpe / hit-rate / expectancy from closed-trade ledger.
			this.stratHealth.loading = true
			this.stratHealth.err = ""
			try {
				const w = Number(this.stratHealth.window) || 30
				const r = await fetch("/api/strategy-health/per-strategy?window=" + w, {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) {
					this.stratHealth.err = "HTTP " + r.status
					this.stratHealth.data = null
					return
				}
				this.stratHealth.data = await r.json()
			} catch (e) {
				this.stratHealth.err = e.message
				this.stratHealth.data = null
			} finally {
				this.stratHealth.loading = false
			}
		},
		async fetchFreshness() {
			try {
				const r = await fetch("/api/data/freshness")
				if (!r.ok) return
				this.freshness = await r.json()
			} catch (e) {
				/* silent — pill simply won't show */
			}
		},
		async fetchRiskAlerts() {
			// Position-level risk scan: stop proximity/breach, drawdown, concentration, stale quotes
			try {
				const r = await fetch("/api/portfolio/risk-alerts", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				this.risk_alerts = await r.json()
			} catch (e) {
				/* silent — pill simply won't show */
			}
		},
		async fetchAlertsHistory() {
			try {
				const r = await fetch("/api/portfolio/alerts-history?limit=50", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				this.alerts_history = await r.json()
			} catch (e) {
				/* silent */
			}
		},
		async clearAlertDedupe() {
			try {
				await fetch("/api/portfolio/alerts-clear-dedupe", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				this.fetchRiskAlerts()
			} catch (e) {}
		},
		openReplayForDossier() {
			// Pre-fill Time-Travel modal with current dossier ticker, defaulting to 30 days ago.
			const tk = (this.dos?.ticker || "").trim().toUpperCase()
			if (!tk) {
				alert("No ticker selected in dossier")
				return
			}
			const d = new Date()
			d.setDate(d.getDate() - 30)
			this.tt.ticker = tk
			this.tt.date = d.toISOString().slice(0, 10)
			this.tt.strategy = "all"
			this.tt.data = null
			this.tt.err = ""
			this.tt.show = true
		},
		async runTimeTravel() {
			const tk = (this.tt.ticker || "").trim().toUpperCase()
			const dt = this.tt.date
			if (!tk || !dt) {
				this.tt.err = "Ticker + date required"
				return
			}
			this.tt.err = ""
			this.tt.loading = true
			this.tt.data = null
			try {
				const url =
					"/api/live/time-travel?ticker=" +
					encodeURIComponent(tk) +
					"&target_date=" +
					encodeURIComponent(dt) +
					"&strategy=" +
					encodeURIComponent(this.tt.strategy || "all")
				const r = await fetch(url, {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) {
					let msg = "HTTP " + r.status
					try {
						const j = await r.json()
						msg = j.detail || j.error || msg
					} catch (e) {}
					this.tt.err = this.formatReplayError(typeof msg === "string" ? msg : (msg && msg[0]) || msg)
					return
				}
				this.tt.data = await r.json()
			} catch (e) {
				this.tt.err = this.formatReplayError(e.message)
			} finally {
				this.tt.loading = false
			}
		},
		async fetchBriefStatus() {
			try {
				const r = await fetch("/api/brief/status", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				this.brief_status = await r.json()
			} catch (e) {
				/* silent */
			}
		},
		async regenerateBrief() {
			if (!confirm("Regenerate morning brief now? Runs the generator (≈60s).")) return
			this.brief_regen_loading = true
			try {
				const r = await fetch("/api/brief/regenerate", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				const j = await r.json()
				if (j.ok) {
					const note = j.rolled_forward
						? " (rolled forward — live fetch unavailable; re-run when yfinance works)"
						: ""
					alert(
						"✓ Brief updated: " +
							(j.after?.date || "") +
							" — " +
							(j.after?.size_bytes || 0) +
							" bytes" +
							note,
					)
				} else {
					alert("⛔ Regen failed: " + (j.error || j.stderr_tail || "unknown"))
				}
				this.fetchBriefStatus()
			} catch (e) {
				alert("Regen error: " + e.message)
			} finally {
				this.brief_regen_loading = false
			}
		},
		async rotateAlerts() {
			if (!confirm("Trim data/alerts.jsonl to last 5000 rows? Older rows archived to .bak")) return
			try {
				const r = await fetch("/api/portfolio/alerts-rotate?keep=5000", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				const j = await r.json()
				alert(
					j.ok
						? "✓ Rotated: trimmed " +
								j.trimmed +
								", remaining " +
								j.remaining +
								(j.archive ? " → " + j.archive : "")
						: "⛔ " + (j.error || "failed"),
				)
				this.fetchAlertsHistory()
			} catch (e) {
				alert("Rotate error: " + e.message)
			}
		},
		async ccFetch(url, opts = {}) {
			if (opts.json || opts.normalize) return this.ccFetchJson(url, opts)
			const tries = opts.retries ?? 3
			const backoff = opts.backoff ?? 700
			const timeoutMs = opts.timeoutMs ?? 0
			for (let i = 0; i < tries; i++) {
				try {
					const init = { ...(opts.init || {}) }
					if (/^\/api\//.test(url)) {
						const headers =
							init.headers && typeof init.headers === "object" && !Array.isArray(init.headers)
								? { ...init.headers }
								: {}
						init.headers = { "X-API-Key": window._apiKey || "dev-secret-local", ...headers }
					}
					const extSignal = init.signal
					if (timeoutMs > 0 || extSignal) {
						const ctrl = new AbortController()
						init.signal = ctrl.signal
						let timer = null
						if (timeoutMs > 0) timer = setTimeout(() => ctrl.abort(), timeoutMs)
						if (extSignal) extSignal.addEventListener("abort", () => ctrl.abort(), { once: true })
						try {
							const r = await fetch(url, init)
							if (timer) clearTimeout(timer)
							if ((r.status === 503 || r.status === 502) && i < tries - 1) {
								await new Promise((res) => setTimeout(res, backoff * (i + 1)))
								continue
							}
							return r
						} catch (e) {
							clearTimeout(timer)
							if (i === tries - 1) throw e
						}
					} else {
						const r = await fetch(url, init)
						if ((r.status === 503 || r.status === 502) && i < tries - 1) {
							await new Promise((res) => setTimeout(res, backoff * (i + 1)))
							continue
						}
						return r
					}
				} catch (e) {
					if (i === tries - 1) throw e
					await new Promise((res) => setTimeout(res, backoff * (i + 1)))
				}
			}
			return null
		},
		normalizeFetchError(msg) {
			const s = String(msg || "").trim()
			if (!s) return "failed_fetch"
			if (
				/failed to fetch|networkerror|network error|load failed|fetch failed|HTTP fail|HTTP 0|no-trade HTTP/i.test(
					s,
				)
			)
				return "failed_fetch"
			if (/HTTP 503|HTTP 502|warming up/i.test(s)) return "stale"
			if (/timeout|aborted/i.test(s)) return "failed_fetch"
			return null
		},
		inferSurfaceHints(data) {
			if (!data || typeof data !== "object") return {}
			const trust = data.trust || {}
			const fresh = data.freshness || {}
			const hints = {}
			const degraded = !!(
				data.degraded ||
				data.hub_status === "degraded" ||
				trust.stale ||
				fresh.stale ||
				fresh.tier === "STALE" ||
				trust.source === "instant-degraded" ||
				data.source === "instant-degraded" ||
				data.source === "brief-fallback"
			)
			const mock = !!(fresh.synthetic || data.mock_only || trust.synthetic || data.research_only)
			if (degraded) hints.stale = true
			if (mock) hints.mock_only = true
			if (data.research_only || mock || degraded) hints.research_only = true
			return hints
		},
		async ccFetchJson(url, opts = {}) {
			const loadingTab = opts.tab || this.tab
			this.surfaceFetchHints[loadingTab] = {
				...(this.surfaceFetchHints[loadingTab] || {}),
				loading: true,
				error: "",
			}
			try {
				const r = await this.ccFetch(url, opts)
				if (!r) {
					const msg = this.surfaceFetchStateMessage("failed_fetch")
					this.surfaceFetchHints[loadingTab] = { loading: false, error: msg, failed_fetch: true }
					return { ok: false, status: 0, error: msg, fetch_state: "failed_fetch" }
				}
				if (!r.ok) {
					let detail = "HTTP " + r.status
					try {
						const j = await r.json()
						detail = j.detail || j.error || detail
					} catch (_e) {}
					const state =
						this.normalizeFetchError(String(detail)) || (r.status === 503 ? "stale" : "failed_fetch")
					const msg = this.surfaceFetchStateMessage(
						state,
						this.normalizeFetchError(String(detail)) ? null : detail,
					)
					this.surfaceFetchHints[loadingTab] = {
						loading: false,
						error: msg,
						failed_fetch: state === "failed_fetch",
						stale: state === "stale",
					}
					return { ok: false, status: r.status, error: msg, fetch_state: state }
				}
				const data = await r.json()
				const hints = { loading: false, error: "", ...this.inferSurfaceHints(data) }
				this.surfaceFetchHints[loadingTab] = hints
				let fetchState = "ok"
				if (hints.mock_only) fetchState = "mock_only"
				else if (hints.research_only) fetchState = "research_only"
				else if (hints.stale) fetchState = "stale"
				return { ok: true, status: r.status, data, fetch_state: fetchState }
			} catch (e) {
				const raw = String((e && e.message) || e || "fetch failed")
				const state = this.normalizeFetchError(raw) || "failed_fetch"
				const msg = this.surfaceFetchStateMessage(state, this.normalizeFetchError(raw) ? null : raw)
				this.surfaceFetchHints[loadingTab] = { loading: false, error: msg, failed_fetch: true }
				return { ok: false, status: 0, error: msg, fetch_state: state }
			}
		},
		surfaceFetchErrorLine(msg, tab) {
			const s = String(msg || "")
			const mode = (this._SURFACE_MODES || {})[tab || this.tab] || ""
			if (/Failed to fetch|NetworkError|Load failed|fetch failed|ECONNREFUSED|warming up|API warming/i.test(s)) {
				if (mode === "dossier_research") return "Live dossier fetch failed from " + this.dosFetchServiceName()
				return this.surfaceWarmupLoadingLine(mode)
			}
			if (/HTTP 0|No response|fail$/i.test(s)) {
				if (mode === "dossier_research") return "Live dossier fetch failed from " + this.dosFetchServiceName()
				return "Instant server unreachable — start with ./_start_server.sh"
			}
			if (/HTTP 503/i.test(s)) {
				if (mode === "dossier_research")
					return "Live dossier fetch failed from " + this.dosFetchServiceName() + " (API warming up)"
				return this.surfaceWarmupLoadingLine(mode)
			}
			if (mode === "dossier_research" && (!s || /stock intel unavailable|research unavailable/i.test(s)))
				return "Live dossier fetch failed from " + this.dosFetchServiceName()
			return s || "Request failed"
		},
		dossierFetchStateCopy(state, detail, service) {
			const svc = String(service || this.dosFetchServiceName() || "market_data_service")
			if (state === "failed_fetch") {
				return {
					badge: "CONFIRM ONLY",
					title: "即時研究暫不可用 · confirm-only",
					explanation: "核心資料暫時未齊 · 只可確認結構，不可 sizing。",
					next_action: "Retry 重試 live fetch；Load core only 保留 core；Load enrichments 補回擴展研究。",
					state: "failed_fetch",
				}
			}
			if (state === "loading") {
				return {
					badge: "LOADING",
					title: "載入 Dossier 研究中",
					explanation: "正在從 " + svc + " 抓取 live research；空面板唔代表結論。",
					next_action: "等 core 載入完成，或者 Retry。",
					state: "loading",
				}
			}
			if (state === "stale") {
				return {
					badge: "CONFIRM ONLY",
					title: "顯示快取研究",
					explanation: "目前只顯示 cached core；live fetch 未完成。",
					next_action: "Retry 後再確認 levels / verdict；未恢復前不可 sizing。",
					state: "stale",
				}
			}
			if (state === "partial") {
				if (svc.includes("instant-degraded")) {
					let explanation = "Core shell 已載入，但仍未回到 live research。"
					if (detail) explanation += " (" + String(detail) + ")"
					return {
						badge: "CONFIRM ONLY",
						title: "核心模式 · confirm-only",
						explanation,
						next_action: "Load enrichments 或 Retry；恢復前只可確認結構，不可 sizing / handoff。",
						state: "partial",
					}
				}
				let explanation = "部分研究 modules 未回來；證據仍未完整。"
				if (detail) explanation += " (" + String(detail) + ")"
				return {
					badge: "CONFIRM ONLY",
					title: "部分研究載入",
					explanation,
					next_action: "Retry 或 Load enrichments；完整前只可 confirm。",
					state: "partial",
				}
			}
			return this.surfaceFetchStateCopy(state, detail)
		},
		dosFetchServiceName() {
			const trust = this.dos?.data?.trust || this.dos?.intel?.dossier?.trust
			return (trust && trust.source) || "market_data_service"
		},
		_dossierIntelDegraded(intel) {
			if (!intel || typeof intel !== "object") return false
			const trust = intel.trust || intel.dossier?.trust || {}
			const src = String(trust.source || intel.source || "")
			return !!(
				intel.partial ||
				intel.degraded ||
				intel.research_only ||
				intel.instant_degraded ||
				trust.stale ||
				src.includes("instant-degraded") ||
				src === "brief-fallback"
			)
		},
		_dossierPartialNoticeFromIntel(intel) {
			if (!intel) return ""
			const mod = intel.module_errors || {}
			const missing = (intel.missing_modules || []).map((m) => String(m)).filter(Boolean)
			if (
				mod.dossier &&
				this._dossierIntelDegraded(intel) &&
				!/^Live dossier fetch failed/i.test(String(mod.dossier))
			) {
				const base = String(mod.dossier)
				return missing.length ? base + " · Missing: " + missing.slice(0, 4).join(", ") : base
			}
			if (intel.partial_notice) return String(intel.partial_notice)
			if (mod.dossier && !this._dossierIntelDegraded(intel)) {
				const base = String(mod.dossier)
				return missing.length ? base + " · Missing: " + missing.slice(0, 4).join(", ") : base
			}
			if (this._dossierIntelDegraded(intel)) {
				const svc = (intel.trust || intel.dossier?.trust || {}).source || "cached"
				const base = "核心資料已載入 · confirm-only shell；live research 未齊，不可 sizing。"
				return missing.length ? base + " · 缺少 · " + missing.slice(0, 3).join(" · ") : base
			}
			return ""
		},
		dosShowsFetchBanner() {
			if (this.dos.status === "idle_no_query") return false
			if (this.dos.error) return true
			if (this.dos.status === "stale_fallback" && this.dos.error) return true
			if (this.dos.status === "partial_loaded" && this.dos.partialNotice) return true
			if (this.dossierResearchOnly() && this.dos.ticker) return true
			return false
		},
		dossierPageOperatorCompact() {
			const p = this.pageOperatorSentence()
			const t = String(this.dos.ticker || "—").toUpperCase()
			let pbAct = ""
			const pb = (this.rankedOpps.rows || []).find((r) => String(r.ticker || "").toUpperCase() === t)
			if (pb) pbAct = String(pb.action || pb.effective_action || "").toUpperCase()
			const missing = this.dosFetchBannerMissingLine()
			return {
				now: (pbAct ? `${t} · Playbook ${pbAct}` : t) + " · confirm structure",
				blocker: missing || p.blocker || "live research incomplete",
				next_action: "Retry · core only · enrichments — no sizing/handoff until live",
			}
		},
		dossierConfirmOnlyOnce() {
			return this.dossierResearchOnly() || this.dosShowsFetchBanner()
		},
		dosFetchBannerKind() {
			if (this.dos.status === "failed" || (this.dos.error && !this.dosHasLoadedData())) return "error"
			if (this.dos.status === "stale_fallback" && this.dos.error) return "stale"
			if (this.dos.status === "partial_loaded" && (this.dos.partialNotice || this.dos.error)) return "partial"
			if (this.dos.error) return "error"
			return "partial"
		},
		dosFetchBannerHeadline() {
			return "核心暫不可用 · confirm-only"
		},
		dosFetchBannerBadge() {
			return "CONFIRM ONLY"
		},
		dosFetchBannerNowLine() {
			const gate = this.dossierGateSnapshotLine()
			const opened = this.dosOpenContextLine()
			const exists = this.dosFetchBannerExistsLine()
			return [gate, opened, exists].filter(Boolean).join(" · ")
		},
		dosFetchBannerBlockerLine() {
			const missing = this.dosFetchBannerMissingLine()
			const bits = ["現時只可確認結構", "不可 sizing / handoff"]
			if (missing) bits.push(missing.replace(/^缺少 · /, "缺少 · "))
			return bits.join(" · ")
		},
		dosFetchBannerExistsLine() {
			const bits = ["現有資料"]
			if (this.dos.data?.price != null) bits.push("quote")
			if (this.dos.intel?.pm_answer) bits.push("decision stack")
			if (this.dosHasCached()) bits.push("cached core")
			return bits.length > 1 ? bits.join(" · ") : "現有資料 · core-only"
		},
		dosFetchBannerMissingLine() {
			const missing = (this.dos.missing_modules || []).slice(0, 4)
			if (missing.length) return "缺少 · " + missing.join(" · ")
			if (this.dosFetchBannerKind() === "partial") return "缺少 · live research modules"
			return "缺少 · live core / enrichments"
		},
		dosFetchBannerRestoreLine() {
			const kind = this.dosFetchBannerKind()
			if (kind === "partial")
				return "Retry / Load enrichments 可補回即時研究 modules；Load core only 只保留 confirm-only core。"
			return "Retry 重試 live fetch；Load core only 保留 confirm-only core；Load enrichments 補回擴展研究。"
		},
		dossierGateSnapshotLine() {
			const cs = this.ccState()
			const tb = String(
				cs.tradeability_state?.tradeability || this.canonicalTradeability() || "WAIT",
			).toUpperCase()
			const bs = String(cs.board_decision_state?.state || "").toUpperCase()
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			const parts = []
			if (tb) parts.push("盤面 " + tb)
			if (bs && bs !== "DEPLOY") parts.push(bs.replace(/_/g, " "))
			if (
				es &&
				[
					"EXEC_BLOCKED",
					"ENGINE_OFF",
					"GATEWAY_DOWN",
					"IBAPI_MISSING",
					"SESSION_INACTIVE",
					"HANDOFF_BLOCKED",
				].includes(es)
			)
				parts.push("執行 " + es.replace(/_/g, " "))
			return parts.length ? parts.join(" · ") : ""
		},
		dosOpenContextLine() {
			const ctx = this.dos?.open_context || {}
			const from = String(ctx.from || "").toLowerCase()
			const t = String(this.dos.ticker || "").toUpperCase()
			if (!from || !t) return ""
			if (from === "scanners") {
				const s = String(ctx.scanner || "").trim()
				const why = String(ctx.discovery_reason || "").trim()
				const bits = ["來自 Discovery"]
				if (s) bits.push(s)
				if (why) bits.push(why.slice(0, 120))
				return bits.join(" · ")
			}
			if (from === "signals") {
				const rk = ctx.playbook_rank != null ? "#" + ctx.playbook_rank : ""
				const lbl = String(ctx.playbook_label || "").trim()
				return ["來自 Playbook", rk, lbl].filter(Boolean).join(" · ")
			}
			if (from === "today") {
				return "來自 Dashboard"
			}
			return "來自 " + from
		},
		dosFetchBannerDetail() {
			const kind = this.dosFetchBannerKind()
			const gate = this.dossierGateSnapshotLine()
			const opened = this.dosOpenContextLine()
			const prefix = [gate, opened].filter(Boolean).join(" · ")
			if (kind === "partial") {
				const note = this.dos.partialNotice || this.dos.fetchDetail || ""
				const copy = this.dossierFetchStateCopy("partial", note, this.dosFetchServiceName())
				const body = note || copy.explanation
				return prefix ? prefix + " · " + body : body
			}
			const detail = this.dosFetchErrorDetail()
			if (kind === "error") {
				const hint = this.routeAbortRecoveryHint("dossier")
				const body = hint ? (detail ? detail + " · " + hint : hint) : detail
				return prefix ? prefix + " · " + body : body
			}
			return prefix ? prefix + " · " + detail : detail
		},
		dosFetchBannerGrade() {
			const kind = this.dosFetchBannerKind()
			if (kind === "partial")
				return "Retry / Load enrichments 補回 live research；Load core only 保留 confirm-only core。"
			return "Retry 重試 live fetch；恢復前只可 confirm-only。"
		},
		dosFetchErrorHeadline() {
			return this.dosFetchBannerHeadline()
		},
		dosFetchErrorDetail() {
			const raw = this.dos.fetchDetail || ""
			const isDev = !!(this.isDevMode && this.isDevMode())
			let msg = "即時研究抓取失敗 · 目前顯示 core-only"
			if (this.dos.status === "stale_fallback") msg = "即時研究抓取失敗 · 目前顯示快取 core"
			if (isDev && raw) return msg + " (" + raw + ")"
			return msg
		},
		dosFetchErrorGrade() {
			return "Confirm-only — no sizing / IBKR handoff until live research returns"
		},
		_syncDossierFetchHints(extra = {}) {
			const loading = !!(
				this.dos.loading ||
				this.dos.status === "loading_core" ||
				this.dos.status === "loading_enrichments"
			)
			let error = ""
			let failed_fetch = false
			let stale = false
			let partial = false
			if (this.dos.status === "failed" || (this.dos.error && !this.dosHasLoadedData())) {
				error = this.dosFetchErrorDetail()
				failed_fetch = true
			} else if (this.dos.status === "stale_fallback" && this.dos.error) {
				error = this.dosFetchErrorDetail()
				stale = true
			} else if (this.dos.status === "partial_loaded" && (this.dos.partialNotice || this.dos.error)) {
				error = this.dos.partialNotice || this.dos.error
				partial = true
			}
			this.surfaceFetchHints.dossier = { loading, error, failed_fetch, stale, partial, ...extra }
		},
		btLabDegradedLine() {
			const t = this.btLab.data || {}
			const note =
				(t.evidence && t.evidence.trust && t.evidence.trust.reason) ||
				(t.trust && t.trust.reason) ||
				(t.walk_forward && t.walk_forward.note) ||
				""
			return note || "Full walk-forward lab pending API warm-up — research-only, not deployment authority."
		},
		formatReplayError(msg) {
			const s = String(msg || "")
			if (
				/could not convert string to float/i.test(s) ||
				/Invalid replay input/i.test(s) ||
				/Invalid research input/i.test(s)
			) {
				const m = s.match(/'([^']+)'/)
				return m ? "Invalid replay input: expected numeric value, received " + m[1] : "Invalid replay input"
			}
			return s || "Replay failed"
		},
		parseRR(v) {
			if (v == null || v === "") return 0
			if (typeof v === "number" && !Number.isNaN(v)) return v
			const s = String(v).trim()
			if (!s) return 0
			const n = Number(s)
			if (!Number.isNaN(n)) return n
			const parts = s.split(/[:/]/)
			if (parts.length === 2) {
				const a = Number(parts[0]),
					b = Number(parts[1])
				if (a > 0 && b > 0) return b / a
			}
			return 0
		},
		rrBelowTradeGate(v) {
			const rr = this.parseRR(v)
			return rr > 0 && rr < 2.0
		},
		pluralize(n, singular, plural) {
			const nn = Number(n)
			const p = plural != null ? plural : singular + "s"
			return nn === 1 ? singular : p
		},
		portfolioSummaryPositionsLabel() {
			const n = Number((this.pf && this.pf.summary && this.pf.summary.total_positions) || 0)
			if (!n) return "No positions"
			return `${n} ${this.pluralize(n, "position")}`
		},
		portfolioSummaryStripVisible() {
			return Number((this.pf && this.pf.summary && this.pf.summary.total_positions) || 0) >= 1
		},
		portfolioSummaryStripLine() {
			if (!this.portfolioSummaryStripVisible()) return ""
			const val = Number((this.pf && this.pf.summary && this.pf.summary.total_value) || 0)
			const dollars = Number.isFinite(val) ? val.toLocaleString() : "—"
			return `${this.portfolioSummaryPositionsLabel()} · $${dollars}`
		},
		portfolioSummaryValueShortLine() {
			const s = this.pf && this.pf.summary
			if (!s) return ""
			const val = Number(s.total_value)
			if (!Number.isFinite(val)) return ""
			return `Value $${val.toLocaleString()}`
		},
		portfolioSummaryMoneyLine(field) {
			const s = this.pf && this.pf.summary
			if (!s) return "—"
			const val = Number(s[field])
			return Number.isFinite(val) ? "$" + val.toLocaleString() : "—"
		},
		portfolioSummaryPnlIsPositive() {
			const s = this.pf && this.pf.summary
			if (!s) return false
			const pnl = Number(s.total_pnl)
			return Number.isFinite(pnl) && pnl >= 0
		},
		portfolioSummaryPnlLine() {
			const s = this.pf && this.pf.summary
			if (!s) return "—"
			const pnl = Number(s.total_pnl)
			if (!Number.isFinite(pnl)) return "—"
			const sign = pnl >= 0 ? "+" : ""
			const pct = s.total_pnl_pct
			const pctPart = pct != null && pct !== "" ? ` (${pct}%)` : ""
			return sign + pnl.toLocaleString() + pctPart
		},
		riskAlertsStripVisible() {
			return Number((this.risk_alerts && this.risk_alerts.count) || 0) >= 1
		},
		riskAlertsStripLine() {
			const n = Number((this.risk_alerts && this.risk_alerts.count) || 0)
			return n >= 1 ? `${n} RISK ALERTS` : ""
		},
		pfVar95MethodBadge() {
			const q = this.pfRisk && this.pfRisk() ? this.pfRisk().var95Quality : ""
			if (q === "historical") return (this.pfRisk().var95Tier || "historical").toLowerCase()
			if (q === "position-vol") return "parametric · live vol"
			return "parametric"
		},
		isDevMode() {
			try {
				const qs = new URLSearchParams(location.search || "")
				if (qs.get("dev") === "1" || qs.get("debug") === "1") return true
			} catch (e) {}
			try {
				return localStorage.getItem("cc_dev") === "1"
			} catch (e) {
				return false
			}
		},
		formatTargetWeights(targetsObj) {
			const t = targetsObj || {}
			const entries = Object.entries(t)
				.map(([k, v]) => [
					String(k || "")
						.toUpperCase()
						.trim(),
					Number(v),
				])
				.filter(([k, v]) => k && Number.isFinite(v))
			if (!entries.length) return ""
			entries.sort((a, b) => b[1] - a[1])
			return entries.map(([k, v]) => k + " " + v + "%").join(" · ")
		},
		portfolioTargetsPlaceholder() {
			if (this.isDevMode()) return "Targets JSON (debug)"
			return "Target weights: AAPL 40% · MSFT 30%"
		},
		portfolioPrimaryRiskBlocker() {
			const positions = (this.pf && this.pf.positions) || []
			if (!positions.length) return { message: "", ticker: "", ctaLabel: "" }
			const missing = []
			for (const p of positions) {
				const stop = Number(p.stop_price || p.current_stop || p.initial_stop || p.stop || 0)
				const stopDefined = !!(p.stop_defined || stop > 0)
				const px = p.current_price || p.last_price || p.entry_price || 0
				const sh = p.shares || p.quantity || 0
				const val = px * sh || p.market_value || 0
				if (!stopDefined) missing.push({ ticker: (p.ticker || p.symbol || "").toUpperCase(), val })
			}
			if (!missing.length) return { message: "", ticker: "", ctaLabel: "" }
			missing.sort((a, b) => b.val - a.val)
			const t = missing[0].ticker || "—"
			const n = missing.length
			const msg =
				"stop missing on " +
				t +
				(n > 1 ? " (" + n + " " + this.pluralize(n, "position") + " without stops)" : "")
			return { message: msg, ticker: t, ctaLabel: "SET STOP" }
		},
		portfolioOpenStopSetter() {
			const b = this.portfolioPrimaryRiskBlocker()
			this.portfolioOpenStopForTicker(b.ticker || "")
		},
		portfolioOpenStopForTicker(ticker) {
			const t = String(ticker || "")
				.toUpperCase()
				.trim()
			if (!t) return
			this.pfStopSetter = { open: true, ticker: t, stop: "" }
			try {
				const el = document.getElementById("pf-stop-setter")
				if (el) el.scrollIntoView({ behavior: "smooth", block: "center" })
			} catch (e) {}
		},
		async portfolioSaveStop() {
			const t = (this.pfStopSetter && this.pfStopSetter.ticker) || ""
			const stop = Number((this.pfStopSetter && this.pfStopSetter.stop) || 0)
			if (!t || !stop || stop <= 0) {
				alert("Stop must be > 0")
				return
			}
			try {
				const r = await fetch("/api/portfolio/position", {
					method: "PUT",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ ticker: t, stop_price: stop }),
				})
				if (r.ok) {
					this.pfStopSetter.open = false
					await this.fetchPortfolio()
				} else {
					const msg = await r.text()
					alert("Stop update failed: " + msg)
				}
			} catch (e) {
				alert("Stop update failed")
			}
		},
		currentSurfaceCcState() {
			let cs = null
			if (this.tab === "today") cs = this.today7.cc_state
			else if (this.tab === "signals") cs = this.rankedOpps.cc_state
			else if (this.tab === "dossier" || this.tab === "stock-intel") cs = this.dos?.cc_state
			else if (this.tab === "portfolio") cs = this.pfDecision?.cc_state
			else if (this.tab === "ibkr") cs = this.ccHeader.cc_state || this.today7.cc_state
			else cs = this.ccHeader.cc_state
			if (!cs || typeof cs !== "object") {
				cs =
					this.ccHeader.cc_state ||
					this.today7.cc_state ||
					this.rankedOpps.cc_state ||
					this.dos?.cc_state ||
					this.pfDecision?.cc_state
			}
			return cs && typeof cs === "object" ? cs : {}
		},
		currentSurfaceAuthorityStrip() {
			if (this.tab === "signals" && this.rankedOpps?.surface_authority) return this.rankedOpps.surface_authority
			if (this.tab === "today" && this.today7?.surface_authority) return this.today7.surface_authority
			return this.today7?.surface_authority || this.rankedOpps?.surface_authority || null
		},
		authorityChipPillClass(chip) {
			const a = String(chip?.authority || "").toLowerCase()
			if (a === "deploy_authority") return "pg"
			if (a === "blocked") return "pr"
			if (a === "confirmation_only" || a === "research_only") return "pa"
			if (a === "monitor_only" || a === "pilot_only" || a === "suspended") return "pw"
			return "pw"
		},
		ccState() {
			const cs = this.currentSurfaceCcState()
			return cs && typeof cs === "object" ? cs : {}
		},
		decisionAuthority() {
			const cs = this.ccState()
			const b = cs.board_decision_state
			if (b && typeof b === "object" && b.gates != null) return b
			if (this.tab === "today") return this.today7.decision_authority || this.ccHeader.decision_authority || {}
			if (this.tab === "signals")
				return this.rankedOpps.decision_authority || this.ccHeader.decision_authority || {}
			if (this.tab === "portfolio" && this.pfDecision?.cc_state?.board_decision_state)
				return this.pfDecision.cc_state.board_decision_state || {}
			if ((this.tab === "dossier" || this.tab === "stock-intel") && this.dos?.cc_state?.board_decision_state)
				return this.dos.cc_state.board_decision_state || {}
			return (
				this.ccHeader.decision_authority ||
				this.today7.decision_authority ||
				this.rankedOpps.decision_authority ||
				{}
			)
		},
		executionState() {
			const cs = this.ccState()
			const ex = cs.execution_state
			return ex && typeof ex === "object" ? ex : {}
		},
		ccFreshnessState() {
			const cs = this.ccState()
			const trust = this.today7.trust || {}
			const market = trust.stale
				? "STALE"
				: String(trust.freshness || "").toUpperCase() === "DEGRADED"
					? "STALE"
					: "FRESH"
			const da = this.decisionAuthority()
			const src = String(da.source || "")
			const board =
				src === "stale_cache" || src === "fallback_brief" || da.degraded || da.gates_active ? "STALE" : "FRESH"
			let dossier = ""
			if ((this.tab === "dossier" || this.tab === "stock-intel" || (this.dos && this.dos.ticker)) && this.dos) {
				const df = this.dos.intel?.dossier_freshness
				const tier = String(df?.worst_tier || "").toUpperCase()
				if (tier === "CRITICAL") dossier = "CRITICAL"
				else if (tier === "STALE" || tier === "UNKNOWN") dossier = "STALE"
				else if (
					this.dos.status === "failed" ||
					this.dos.status === "stale_fallback" ||
					this.dos.status === "partial_loaded"
				)
					dossier = "STALE"
			}
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			const execution =
				es === "EXEC_BLOCKED"
					? "CRITICAL"
					: [
								"ENGINE_OFF",
								"GATEWAY_DOWN",
								"IBAPI_MISSING",
								"SESSION_INACTIVE",
								"HANDOFF_BLOCKED",
								"DISCONNECTED",
						  ].includes(es)
						? "STALE"
						: "FRESH"
			const tiers = [
				["market", market],
				["board", board],
				["dossier", dossier],
				["execution", execution],
			].filter(([, t]) => t)
			let worstTier = "FRESH"
			let worstDomain = ""
			for (const [d, t] of tiers) {
				if (t === "CRITICAL") {
					worstTier = "CRITICAL"
					worstDomain = d
					break
				}
				if (t === "STALE" && worstTier !== "CRITICAL") {
					worstTier = "STALE"
					worstDomain = worstDomain || d
				}
			}
			const asOf = String(cs.freshness_state?.as_of || trust.as_of || "")
			return { market, board, dossier, execution, worst_tier: worstTier, worst_domain: worstDomain, as_of: asOf }
		},
		systemState() {
			if (this.tab === "signals" && this.rankedOpps.system_state) return this.rankedOpps.system_state
			if (this.today7?.system_state && typeof this.today7.system_state === "object")
				return this.today7.system_state
			if (this.ccHeader?.system_state) return this.ccHeader.system_state
			return this._clientSystemState()
		},
		_clientSystemState() {
			const cs = this.ccState()
			const ss = this.ccHeader?.system_state || {}
			const fs = cs.freshness_state || {}
			const opts = {
				tradeability: this.canonicalTradeability() || ss.tradeability || "WAIT",
				blocker: ss.blocker_compact || this.primaryBlockerLine() || "部署權限暫停",
				repair: ss.repair_priority || "refresh Dashboard + Playbook",
				degraded: this.pageAuthorityIsDegraded(),
				deploy_open: !!ss.deploy_open,
				fallback_mode: !!ss.fallback_mode || String(fs.board_source || "").includes("fallback"),
				data_tier: String(
					fs.worst_tier || ss.data_freshness || (this.pageAuthorityIsDegraded() ? "STALE" : "FRESH"),
				),
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.buildClientSystemState)
				return CCHelpers.buildClientSystemState(opts)
			return {
				tradeability: opts.tradeability,
				blocker_compact: opts.blocker,
				repair_priority: opts.repair,
				global_strip_active: opts.degraded,
			}
		},
		globalSystemStripVisible() {
			if (this.tab === "guide") return false
			const ss = this.systemState()
			return !!(ss && ss.global_strip_active)
		},
		suppressSecondaryWarnings() {
			return this.globalSystemStripVisible()
		},
		dashboardSecondaryStripsVisible() {
			return !this.globalSystemStripVisible()
		},
		pageOperatorSentence() {
			const cap =
				this.tab === "today"
					? this.today7?.page_capability
					: this.tab === "signals"
						? this.rankedOpps?.page_capability
						: this.tab === "agent"
							? this.vibeAgent?.page_capability
							: this.tab === "strategy-lab"
								? this.strategyLab?.page_capability
								: this.tab === "shadow"
									? this.shadowAccount?.page_capability
									: this.tab === "reports"
										? this.reportsLib?.page_capability
										: this.ccHeader?.page_capability
			const ctx = {
				page_capability: cap || null,
				fetch_state: this.surfaceFetchStateKey?.() || this.dataContractFetchStateKey?.() || "",
				mock_only:
					this.tab === "flow" &&
					(!!this.flowPanel?.decision?.freshness?.synthetic || this.flowOverlayDegraded?.()),
			}
			if (this.tab === "funds" && this.fundsFetchFailedShell()) ctx.fetch_state = "failed_fetch"
			if (this.tab === "scanners" && this.scannerHub?.error) ctx.fetch_state = "failed_fetch"
			if (typeof CCHelpers !== "undefined" && CCHelpers.pageOperatorSentence)
				return CCHelpers.pageOperatorSentence(this.tab, this.systemState(), ctx)
			return { now: "—", blocker: "—", next_action: "—", line: "" }
		},
		globalSystemStripLine() {
			const os = this.systemState()?.operator_sentence
			if (os?.now) return [os.now, os.blocker, os.next_action].filter(Boolean).join(" · ")
			const p = this.pageOperatorSentence()
			if (p?.line) return p.line
			return ""
		},
		globalSystemRepairLine() {
			return this.systemState()?.repair_priority || this.primaryBlockerLine() || ""
		},
		dashboardTopMonitors() {
			const fromApi = (this.today7.dashboard_monitors || []).filter(Boolean)
			if (fromApi.length) return fromApi.slice(0, 3)
			const p = this.todayMissionPanel()
			return (p.monitors || []).slice(0, 3)
		},
		_SURFACE_MODES: {
			today: "dashboard_core",
			signals: "playbook_core",
			scanners: "discovery_research",
			dossier: "dossier_research",
			"stock-intel": "dossier_research",
			portfolio: "portfolio_manual",
			funds: "funds_research",
			flow: "flow_supporting",
			rs: "rs_supporting",
			notrade: "rejections_diagnostic",
			rejections: "rejections_diagnostic",
			guide: "guide_reference",
			ops: "ops_diagnostic",
			ibkr: "ibkr_execution",
			btlab: "backtest_research",
			backtest: "backtest_research",
			command: "command_research",
		},
		_HEADER_BASE: {
			dashboard_core: {
				badge: "BOARD GATE",
				title: "Dashboard — 今日 deploy 姿態",
				explanation: "Regime + board gate + deploy posture。只有 tradeability 同 execution 對齊先可 sizing。",
				next_action: "先睇 tradeability，再睇 top ranked。",
			},
			playbook_core: {
				badge: "BOARD REVIEW",
				title: "Playbook — 排序機會",
				explanation: "Ranked board；只有 board_mode 完整，而且名稱 execution-ready，先可 Deploy。",
				next_action: "先篩 execution-ready rows，再交叉確認 Dashboard gate。",
			},
			discovery_research: {
				badge: "RESEARCH ONLY",
				title: "Discovery — 全市場掃描",
				explanation: "只屬 scanner funnel input；呢度出現嘅候選本身唔授權交易。",
				next_action: "有興趣嘅名稱送去 Playbook 或 Dossier。",
			},
			dossier_research: {
				badge: "RESEARCH ONLY",
				title: "Dossier — 單一標的研究",
				explanation: "每隻 ticker 嘅證據整理；唔可單獨當成 deploy permission。",
				next_action: "行動前先去 Dashboard 確認 board posture。",
			},
			portfolio_manual: {
				badge: "BOOK CONSTRUCTION",
				title: "Portfolio — 倉位與風險層級",
				explanation: "手動 book construction 同風險管理；override 由你決定，唔係由 scanner 自動決定。",
				next_action: "再平衡前先對齊 manual book 同 IBKR。",
			},
			funds_research: {
				badge: "MODEL EVIDENCE",
				title: "Funds — sleeve 研究",
				explanation: "Model sleeves 同 backtest 證據；backtest ≠ live track record。",
				next_action: "落資金前仍要 live validation。",
			},
			flow_supporting: {
				badge: "CONFIRMATION ONLY",
				title: "Flow — options 敘事輔助",
				explanation: "Flow 只支援 scan-ranked 名稱；唔可作為單獨入場觸發。",
				next_action: "先確認 Playbook + Dossier 一致。",
			},
			rs_supporting: {
				badge: "RESEARCH ONLY",
				title: "Relative strength — Discovery 輸入",
				explanation: "RS 只幫手排序 funnel 候選；唔代表 deploy authority。",
				next_action: "交叉核對 sector regime 同 Playbook；經 Discovery 提升。",
			},
			command_research: {
				badge: "RESEARCH ONLY",
				title: "Command — 進階聚合",
				explanation: "Terminal aggregate 視圖；只係深度 decision dump，唔係 deploy gate。",
				next_action: "Deploy authority 仍以 Dashboard + Playbook 為準。",
			},
			rejections_diagnostic: {
				badge: "AUDIT TRAIL",
				title: "Rejections — 閘門失敗紀錄",
				explanation: "解釋名稱點解過唔到 gates；屬診斷用途，唔係 deploy permission。",
				next_action: "整理 watchlist，再回到 Playbook 睇可行 board。",
			},
			backtest_research: {
				badge: "BACKTEST ONLY",
				title: "Backtest Lab — walk-forward 研究",
				explanation: "Walk-forward 研究；backtest ≠ live track record。",
				next_action: "用 lab 睇 walk-forward diagnostics；落 sizing 前仍要 live validation。",
			},
			guide_reference: {
				badge: "GUIDE MODE",
				title: "Guide — 參考頁",
				explanation: "文檔同 workflow 參考；呢度唔評估 runtime。",
				next_action: "準備好先返 Dashboard 睇 live board posture。",
			},
			ops_diagnostic: {
				badge: "OPS / CONNECTIVITY",
				title: "Ops — runtime 診斷",
				explanation: "Engine 健康同 providers 狀態；workflow status ≠ capital permission。",
				next_action: "返 Dashboard 前先修好 stale provider 或 breaker。",
			},
			ibkr_execution: {
				badge: "EXECUTION GATE",
				title: "IBKR — broker handoff",
				explanation: "連線同落單準備度；關鍵錯誤會直接阻止 execution。",
				next_action: "先連 gateway，再確認 session_usable。",
			},
		},
		pageSurface() {
			const m = this._SURFACE_MODES || {}
			return m[this.tab] || "discovery_research"
		},
		surfaceShowsDecisionChips(mode) {
			return mode === "dashboard_core" || mode === "playbook_core"
		},
		sanitizeVisibleText(v) {
			if (v == null || v === "") return ""
			const s = String(v)
			if (/led',e\);alert\(/i.test(s) || /\[object Object\]/i.test(s))
				return s.includes("[object Object]") ? "Evidence unavailable" : ""
			if (/catch\s*\(\s*\w+\s*\)/i.test(s) && /alert\s*\(/i.test(s) && /\}\s*,\s*\}\}/.test(s)) return ""
			return s.trim()
		},
		_surfaceModeForTab(t) {
			const alias = this.tabAuthorityAlias(t)
			if (alias === "today") return "dashboard_core"
			if (alias === "playbook") return "playbook_core"
			if (alias === "discovery") return "discovery_research"
			return (this._SURFACE_MODES || {})[t] || this.pageSurface()
		},
		normalizedAuthorityChipForTab(t, rawEntry) {
			const mode = this._surfaceModeForTab(t)
			const entry = rawEntry && typeof rawEntry === "object" ? { ...rawEntry } : {}
			const tb = String(this.canonicalTradeability() || "WAIT").toUpperCase()
			const bs = String(this.ccState().board_decision_state?.state || "").toUpperCase()
			const da = this.decisionAuthority()
			const es = String(this.executionState().state || "").toUpperCase()
			const hardBlocked =
				[
					"EXEC_BLOCKED",
					"ENGINE_OFF",
					"GATEWAY_DOWN",
					"IBAPI_MISSING",
					"SESSION_INACTIVE",
					"HANDOFF_BLOCKED",
				].includes(es) ||
				tb === "NO_TRADE" ||
				bs === "SUSPENDED" ||
				da.authority_level === "suspended"
			const degraded =
				this.pageAuthorityIsDegraded() ||
				tb === "WAIT" ||
				bs === "RESEARCH_ONLY" ||
				da.degraded ||
				da.gates_active
			const needsResearch =
				mode === "discovery_research" ||
				mode === "rs_supporting" ||
				mode === "funds_research" ||
				mode === "backtest_research" ||
				mode === "command_research"
			if (mode === "dossier_research") {
				return {
					...entry,
					badge: "CONFIRM ONLY",
					short: "只可確認結構 · no sizing",
					authority: "confirmation_only",
					authority_label: "Dossier is confirm-only — confirm structure only, no sizing or handoff",
				}
			}
			if (mode === "flow_supporting") {
				return {
					...entry,
					badge: "CONFIRM ONLY",
					short: "只作確認輔助 · not executable here",
					authority: "confirmation_only",
					authority_label: "Flow is confirmation-only — supporting overlay, not an execution surface",
				}
			}
			if (mode === "portfolio_manual" || mode === "rejections_diagnostic" || mode === "ops_diagnostic") {
				return {
					...entry,
					badge: hardBlocked ? "BLOCKED" : "MONITOR ONLY",
					short: mode === "portfolio_manual" ? "先對齊倉位真相 · monitor first" : "診斷頁面 · monitor first",
					authority: hardBlocked ? "blocked" : "monitor_only",
					authority_label: "This surface is monitor/diagnostic only",
				}
			}
			if (mode === "ibkr_execution") {
				if (this.ibkr.readiness?.full_handoff_ready) {
					return {
						...entry,
						badge: "HANDOFF READY",
						short: "Broker 已就緒 · execution ready",
						authority: "deploy_authority",
						authority_label: "IBKR handoff is ready",
					}
				}
				return {
					...entry,
					badge: hardBlocked ? "BLOCKED" : "MONITOR ONLY",
					short: "先修 broker checklist · then reconnect",
					authority: hardBlocked ? "blocked" : "monitor_only",
					authority_label: "Broker handoff is not ready yet",
				}
			}
			if (needsResearch) {
				return {
					...entry,
					badge: "RESEARCH ONLY",
					short: "可比較研究，不可執行 · not executable here",
					authority: "research_only",
					authority_label: "Research surface only — compare candidates, not executable here",
				}
			}
			if (mode === "dashboard_core" || mode === "playbook_core") {
				const canDeploy = !!this.today7.todays_decision?.can_deploy_today && !degraded && !hardBlocked
				if (canDeploy) {
					return {
						...entry,
						badge: "DEPLOY",
						short: "Board + broker + execution 已對齊",
						authority: "deploy_authority",
						authority_label: "Deploy authority open",
					}
				}
				return {
					...entry,
					badge: hardBlocked ? "BLOCKED" : "MONITOR ONLY",
					short: hardBlocked
						? this.primaryBlockerChip() + " · no deploy authority"
						: "盤面未開閘 · ranked for review only",
					authority: hardBlocked ? "blocked" : "monitor_only",
					authority_label: hardBlocked
						? "Deploy blocked by board / broker / execution truth"
						: "Board not open — monitor only",
				}
			}
			return {
				...entry,
				badge: "MONITOR ONLY",
				short: "Authority capped on this surface",
				authority: "monitor_only",
				authority_label: "Authority capped on this surface",
			}
		},
		_normalizeFetchState(ctx) {
			if (ctx.loading) return "loading"
			if (ctx.failed_fetch_with_fallback) return "failed_fetch_fallback"
			if (ctx.error) return "failed_fetch"
			if (ctx.execution_blocked) return "execution_blocked"
			if (ctx.runtime_unknown) return "runtime_unknown"
			if (ctx.probe_only) return "probe_only"
			if (ctx.mock_only) return "mock_only"
			if (ctx.research_only) return "research_only"
			if (ctx.fallback) return "fallback"
			if (ctx.stale) return "stale"
			if (ctx.partial) return "partial"
			if (ctx.empty) return "no_data"
			return "ok"
		},
		surfaceFetchStateCopy(state, detail) {
			const copy = {
				loading: {
					badge: "LOADING",
					title: "資料載入中 · Loading",
					explanation: "即時資料仍在載入；唔好把快取內容當成 deploy authority。",
					next_action: "等抓取完成，或者 refresh 分頁。",
				},
				failed_fetch: {
					badge: "FETCH FAILED",
					title: "載入失敗 · Fetch failed",
					explanation: "Network 或 server 錯誤令今次無法 fresh read。",
					next_action: "先 Retry；如果持續失敗，再睇 Ops diagnostics。",
				},
				failed_fetch_fallback: {
					badge: "FETCH FAILED",
					title: "即時抓取失敗 · 顯示 fallback",
					explanation: "你而家見到嘅係 fallback watchlist samples，唔係即時 scanner 輸出。",
					next_action: "Sizing 前先去 Playbook 確認；API 恢復後再 Retry。",
				},
				stale: {
					badge: "STALE",
					title: "資料過時 · Stale",
					explanation: "上次成功抓取已經過時；目前 ranking 同 posture 未必反映現況。",
					next_action: "行動前先 refresh 呢個 surface。",
				},
				fallback: {
					badge: "FALLBACK",
					title: "後備畫面 · Fallback",
					explanation:
						"即時 scanner 暫不可用；目前只顯示 brief / snapshot fallback，唔係 execution-grade board。",
					next_action: "等 live API 恢復後返 Dashboard；目前名稱只可 Monitor。",
				},
				partial: {
					badge: "PARTIAL",
					title: "部分載入 · Partial",
					explanation: "部分 modules 失敗；而家只見到不完整 evidence。",
					next_action: "Sizing 前先檢查 Ops → Data Providers。",
				},
				probe_only: {
					badge: "PROBE ONLY",
					title: "連線探針 · Probe",
					explanation: "Ops probe 只證明 wiring，唔係可投資訊號。",
					next_action: "先修復 provider health，再信 downstream surfaces。",
				},
				runtime_unknown: {
					badge: "RUNTIME UNKNOWN",
					title: "Runtime 未明 · Unknown",
					explanation: "Engine 或 backend 狀態未能確認。",
					next_action: "先去 Ops 確認 engine + provider health。",
				},
				mock_only: {
					badge: "MOCK ONLY",
					title: "示意資料 · Mock",
					explanation: "Synthetic / mock rows，唔係真實市場事件。",
					next_action: "唔好把 mock rows 提升出 research preview。",
				},
				research_only: {
					badge: "RESEARCH ONLY",
					title: "研究頁面 · Research",
					explanation: "目前只屬 degraded / model data；唔代表 deploy authority。",
					next_action: "Sizing 前先回 Dashboard / Playbook 確認。",
				},
				execution_blocked: {
					badge: "EXEC BLOCKED",
					title: "執行封鎖 · Blocked",
					explanation: "Broker offline、breaker 觸發，或關鍵 IBKR 檢查失敗。",
					next_action: "落單前先去 IBKR 頁修復連線。",
				},
				no_data: {
					badge: "NO DATA",
					title: "暫無資料 · No data",
					explanation: "抓取成功，但呢個 surface 今次回傳空集合。",
					next_action: "WAIT 日呢種情況屬正常；耐心本身就係正確動作。",
				},
				not_authoritative: {
					badge: "NOT AUTHORITATIVE",
					title: "非授權頁面 · Not authoritative",
					explanation: "Deploy chips 只屬 Dashboard / Playbook。",
					next_action: "切去 Dashboard 睇 board gate 同 deploy posture。",
				},
				ok: { badge: "", title: "即時頁面 · Live", explanation: "", next_action: "" },
			}
			const base = { ...(copy[state] || copy.failed_fetch), state: state || "failed_fetch" }
			if (detail) base.explanation = (base.explanation + " (" + String(detail) + ")").trim()
			return base
		},
		surfaceFetchStateMessage(state, detail) {
			const c = this.surfaceFetchStateCopy(state, detail)
			return c.badge ? c.badge + " — " + c.explanation : c.explanation
		},
		opsDegradedCopy(state, detail) {
			const copy = {
				loading: {
					badge: "LOADING",
					title: "載入中 · Loading",
					explanation: "Ops panel 仲載入緊；空面板唔等於健康。",
					next_action: "等抓取完成，或者 refresh 呢個 tab。",
				},
				fallback: {
					badge: "FALLBACK",
					title: "後備模式 · Fallback",
					explanation: "Live Ops 抓取失敗；目前顯示 built-in fallback，唔係權威 release notes。",
					next_action: "API 恢復後再 Retry；如要改 canonical notes，編輯 data/changelog.json。",
				},
				unavailable: {
					badge: "UNAVAILABLE",
					title: "暫不可用 · Unavailable",
					explanation: "無法載入 Ops panel；session state 未能確認。",
					next_action: "幾秒後再 Retry；確認 API 正在運行，再 refresh Ops。",
				},
				runtime_unknown: {
					badge: "RUNTIME UNKNOWN",
					title: "Runtime 未明 · Unknown",
					explanation: "呢個 panel 未能確認 engine/backend runtime evidence。",
					next_action: "去 Ops health 重新確認 engine + provider 狀態。",
				},
				retry_recommended: {
					badge: "RETRY",
					title: "建議重試 · Retry",
					explanation: "Network/server error 阻止 fresh Ops read。",
					next_action: "幾秒後再 Retry；如持續失敗，用 Ops diagnostics 排查。",
				},
			}
			const base = { ...(copy[state] || copy.unavailable), state: state || "unavailable" }
			if (detail) base.explanation = (base.explanation + " (" + String(detail) + ")").trim()
			return base
		},
		opsDegradedLine(state, detail) {
			const c = this.opsDegradedCopy(state, detail)
			return c.badge ? c.badge + " — " + c.explanation : c.explanation
		},
		opsInferDegradedState(ctx) {
			const c = ctx || {}
			if (c.loading) return "loading"
			if (c.runtime_unknown) return "runtime_unknown"
			if (c.error && (c.fallback || c.timed_out)) return "fallback"
			if (c.error) {
				const s = String(c.error).toLowerCase()
				if (/failed to fetch|networkerror|load failed|timeout|http 503|http 502|warming up/.test(s))
					return "retry_recommended"
				return "unavailable"
			}
			if (c.fallback) return "fallback"
			return "ok"
		},
		opsApiWarmupMessage(raw) {
			const s = String(raw || "")
			return /Failed to fetch|NetworkError|Load failed|fetch failed|ECONNREFUSED|warming up|API warming|HTTP 503|HTTP 502/i.test(
				s,
			)
		},
		opsAnyPanelLoading() {
			return !!(
				this.opsConsole?.loading ||
				this.opsRuntime?.loading ||
				this.changelogPanel?.loading ||
				this.errorLog?.loading
			)
		},
		opsGlobalLoadingLine() {
			if (this.tab !== "ops") return ""
			const line = this.surfaceWarmupLoadingLine("ops_diagnostic")
			if (this.opsAnyPanelLoading()) return line
			const errs = [
				this.opsConsole?.error,
				this.opsRuntime?.error,
				this.changelogPanel?.error,
				this.errorLog?.error,
			].filter(Boolean)
			for (const e of errs) {
				if (this.opsApiWarmupMessage(e)) return line
			}
			const hints = this.surfaceFetchHints || {}
			for (const key of ["ops_updates", "ops_error_log"]) {
				const h = hints[key]
				if (!h) continue
				if (h.loading) return line
				if (h.error && this.opsApiWarmupMessage(h.error)) return line
			}
			return ""
		},
		opsPanelLoadingShort() {
			return this._uiText("Loading…")
		},
		opsPanelLoadingTimeoutSuffix() {
			return this._uiText("Loading…") + " (8s timeout)"
		},
		opsUpdatesPanelTitle() {
			if (this.changelogPanel?.loading) return this._uiText("Loading")
			if (!this.changelogPanel?.error) return ""
			const hasEntries = (this.changelogPanel.entries || []).length > 0
			const state = this.opsInferDegradedState({
				error: this.changelogPanel.error,
				fallback: hasEntries,
				timed_out: !!this.changelogPanel.timeout,
			})
			if (state === "unavailable") return this._uiText("Panel unavailable")
			if (state === "fallback") {
				if (this.changelogPanel.timeout) return this._uiText("No fallback available")
				return this._uiText("Fallback unavailable")
			}
			return this.opsDegradedCopy(state).title
		},
		opsSubNavLabel(key) {
			const map = {
				health: "⚙️ " + this._uiText("Health"),
				updates: "📋 " + this._uiText("Updates"),
				errors: "🧾 " + this._uiText("Error Log"),
			}
			return map[key] || key
		},
		opsBlockerCountLabel() {
			const n = this.opsConsole.data?.blockers?.length || 0
			return n ? this._uiText(n + " blocker(s)") : ""
		},
		opsLogCountLabel() {
			const n = this.errorLog.entries.length || 0
			return n ? this._uiText(n + " log") : ""
		},
		opsChangelogIntro() {
			return this._uiText(
				"Release notes for CC · Clarity Console. Maintained in data/changelog.json — not live git history.",
			)
		},
		opsErrorLogIntro() {
			return this._uiText(
				"Captures API failures, engine state, broker events, and dossier timeouts during this API session. Informational — optional features like Discord being unconfigured are not logged as errors.",
			)
		},
		opsErrorLogEmptyTitle() {
			return this._uiText("No errors logged this session")
		},
		opsErrorLogEmptyDetail() {
			return this._uiText(
				"When the API returns 503/500, the signal engine is stopped, IBKR disconnects, or dossier aggregation times out, entries appear here with plain-English detail and suggested actions.",
			)
		},
		opsErrorLogUnavailableTitle() {
			return this._uiText("Error log unavailable")
		},
		opsErrorLogUnavailableDetail() {
			return this._uiText("Unable to confirm whether errors were logged this session.")
		},
		opsChangelogEntryTitle(entry) {
			return this._uiText((entry && entry.title) || "")
		},
		opsChangelogEntrySummary(entry) {
			return this._uiText((entry && entry.summary) || "")
		},
		opsLatestPillLabel() {
			return this._uiText("LATEST")
		},
		opsProviderRuntimeFallbackLabel(probeOk) {
			const H = window.CCHelpers || {}
			const line = probeOk ? "Probe available · runtime unknown" : "Probe only — runtime unconfirmed"
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(line) : line
		},
		opsFormatEvidence(text) {
			const H = window.CCHelpers || {}
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(text) : String(text || "")
		},
		opsComponentLabel(name) {
			const H = window.CCHelpers || {}
			return H.localizeOpsComponentName ? H.localizeOpsComponentName(name) : String(name || "").replace(/_/g, " ")
		},
		opsProbeLabel(text) {
			return this.opsFormatEvidence(text)
		},
		opsProviderProbeLine(probe) {
			const p = this.opsFormatEvidence(probe)
			return p ? "探測 · Probe: " + p : ""
		},
		_opsH() {
			return window.CCHelpers || {}
		},
		_uiText(t) {
			const H = this._opsH()
			return H.localizeUiText ? H.localizeUiText(t) : String(t || "")
		},
		opsSystemVerdictText() {
			const H = this._opsH()
			const t = this.opsConsole.data?.system_verdict || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsVerdictDetailText() {
			const H = this._opsH()
			const t = this.opsConsole.data?.verdict_detail || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsBlockerText(b) {
			const H = this._opsH()
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(String(b || "")) : String(b || "")
		},
		opsNextActionText(na) {
			const H = this._opsH()
			const t = (na && na.action) || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsNextActionWhy(na) {
			const H = this._opsH()
			const t = (na && na.why) || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsExecutionLayerField(row, field) {
			const H = this._opsH()
			const t = (row && row[field]) || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(String(t)) : String(t)
		},
		opsOperationalEventKey(k) {
			const H = this._opsH()
			return H.localizeOpsDictKey ? H.localizeOpsDictKey(k) : String(k || "").replace(/_/g, " ")
		},
		opsOperationalEventValue(v) {
			return this.opsFormatEvidence(v)
		},
		opsDictKeyLabel(k) {
			const H = this._opsH()
			return H.localizeOpsDictKey ? H.localizeOpsDictKey(k) : String(k || "").replace(/_/g, " ")
		},
		opsMachineLabel(m) {
			const H = this._opsH()
			return H.localizeOpsMachineField ? H.localizeOpsMachineField("label", m?.label) : String(m?.label || "")
		},
		opsMachineConstraint(m) {
			const H = this._opsH()
			return H.localizeOpsMachineField
				? H.localizeOpsMachineField("constraint", m?.constraint)
				: String(m?.constraint || "")
		},
		opsMachineHealthText(m) {
			const H = this._opsH()
			return H.localizeOpsMachineField ? H.localizeOpsMachineField("health", m?.health) : String(m?.health || "")
		},
		opsMachineHeadlineText() {
			const H = this._opsH()
			const t = this.opsConsole.data?.machines_health?.headline || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsSystemVerdictTitle() {
			const H = this._opsH()
			return H.opsSystemVerdictTitle ? H.opsSystemVerdictTitle() : "系統裁決 · System verdict"
		},
		opsDecisionMachinesTitle() {
			const H = this._opsH()
			return H.opsDecisionMachinesTitle ? H.opsDecisionMachinesTitle() : "決策機器 · Decision machines"
		},
		opsExecutionReadinessTitle() {
			const H = this._opsH()
			return H.opsExecutionReadinessTitle
				? H.opsExecutionReadinessTitle()
				: "執行就緒層 · Execution readiness layers"
		},
		opsExecutionReadinessHint() {
			const H = this._opsH()
			return H.opsExecutionReadinessHint
				? H.opsExecutionReadinessHint()
				: "僅探測狀態顯示灰／琥珀 — 非綠色交易就緒 · Probe-only states shown gray/amber — not green trading-ready"
		},
		opsBlockersTitle() {
			const H = this._opsH()
			return H.opsBlockersTitle ? H.opsBlockersTitle() : "根因／阻擋 · Root cause / blockers"
		},
		opsNextActionsTitle() {
			const H = this._opsH()
			return H.opsNextActionsTitle ? H.opsNextActionsTitle() : "下一步操作 · Next operator actions"
		},
		opsEngineStateTitle() {
			const H = this._opsH()
			return H.opsEngineStateTitle ? H.opsEngineStateTitle() : "引擎狀態 · Engine State"
		},
		opsUptimeLatencyTitle() {
			const H = this._opsH()
			return H.opsUptimeLatencyTitle ? H.opsUptimeLatencyTitle() : "運行時間與延遲 · Uptime & Latency"
		},
		opsExperimentalModulesTitle() {
			const H = this._opsH()
			return H.opsExperimentalModulesTitle ? H.opsExperimentalModulesTitle() : "實驗模組 · Experimental modules"
		},
		opsProbeVerdictNote() {
			const H = this._opsH()
			return H.opsProbeVerdictNote
				? H.opsProbeVerdictNote()
				: "探測 OK ≠ 執行時健康。資本決策前請先看上方探測 vs 執行時表。 · Probe OK ≠ runtime health. Use the probe vs runtime table above before capital."
		},
		opsMetricLabel(name) {
			const H = this._opsH()
			return H.opsMetricLabel ? H.opsMetricLabel(name) : name
		},
		opsMetricDisplayText(metricKey, field, fallback) {
			const H = this._opsH()
			const raw =
				this.opsConsole.data?.metrics_display?.[metricKey]?.[field] ||
				(field === "display" && metricKey === "uptime" ? this.opsDetail.uptime : "") ||
				fallback ||
				""
			if (field === "reason") return H.localizeOpsMetricReason ? H.localizeOpsMetricReason(raw) : raw
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(String(raw)) : String(raw)
		},
		opsEngineRunLabel() {
			const H = this._opsH()
			const t = this.ops.running ? "RUNNING" : "STOPPED"
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsCircuitBreakerLabel() {
			const H = this._opsH()
			const t = this.ops.circuit_breaker ? "TRIPPED" : "CLEAR"
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsDryRunLabel() {
			const H = this._opsH()
			const t = this.ops.dry_run ? "DRY RUN / PAPER" : "LIVE TRADING"
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsLastTimeValue(v) {
			if (!v) return this.opsFormatEvidence("— none this session")
			return String(v).slice(0, 19).replace("T", " ")
		},
		opsProbeRuntimeFallbackRows() {
			const warming = !!(
				this.opsConsole.data?.degraded ||
				this.opsConsole.data?.diagnostics?.warming_mode ||
				this.healthMode === "loading"
			)
			const names = ["market_data", "regime_router", "broker"]
			const comps = this.ops.components || {}
			return names.map((name) => {
				const ok = !!comps[name]
				const probe = warming && !ok ? "Warming" : ok ? "Probe OK" : "FAIL"
				const probeClass = warming && !ok ? "text-amber-300" : ok ? "text-gray-400" : "text-red-400"
				const runtime = warming
					? this.opsDegradedLine("runtime_unknown")
					: this.opsDegradedLine(ok ? "runtime_unknown" : "unavailable")
				return { name, probe, probeClass, runtime }
			})
		},
		_boardDecisionStrip() {
			if (!this.surfaceShowsDecisionChips(this.pageSurface())) return null
			if (this.tab !== "today" && this.tab !== "signals") return null
			return this.decisionHub && this.decisionHub.decision_strip
		},
		headerContext() {
			const mode = this.pageSurface()
			const hints = this.surfaceFetchHints[this.tab] || {}
			const strip = this._boardDecisionStrip()
			const ctx = {
				tradeability: this.canonicalTradeability(),
				regime_trend: this.canonicalRegimeTrend(),
				loading: !!hints.loading,
				error: hints.error || "",
				stale: !!(this.today7.trust && this.today7.trust.stale) || !!hints.stale,
				fallback:
					(mode === "dashboard_core" && this.todayUsesBriefFallback()) ||
					(mode === "playbook_core" && this.playbookUsesBriefFallback()) ||
					!!hints.fallback,
				mock_only: !!hints.mock_only,
				research_only: !!hints.research_only,
				execution_blocked:
					!!this.cc_status.breaker || this.degradedExecutionUnavailable() || !!hints.execution_blocked,
				partial: !!hints.partial,
				empty: !!hints.empty,
			}
			if (this.surfaceShowsDecisionChips(mode) && strip) {
				ctx.deploy_label = strip.deploy_reduce_wait || ""
				ctx.best_idea_ticker = (strip.best_idea_now && strip.best_idea_now.ticker) || ""
				ctx.avoid_count = (strip.avoid_now || []).length
			}
			if (mode === "dossier_research" && this.dos.ticker) ctx.ticker = this.dos.ticker
			if (mode === "portfolio_manual") {
				const pc = this.ccHeader.portfolio_context || {}
				ctx.position_count = pc.position_count != null ? pc.position_count : (this.pf.positions || []).length
			}
			if (mode === "flow_supporting") {
				ctx.flow_count = this.flowPanelCount()
				ctx.loading = ctx.loading || this.flowPanel.loading
				if (
					this.flowPanel.decision?.degraded ||
					this.flowPanel.decision?.freshness?.synthetic ||
					this.flowPanel.decision?.mock_only
				) {
					ctx.mock_only = true
					ctx.stale = true
					ctx.research_only = true
				}
			}
			if (mode === "ibkr_execution") ctx.ibkr_label = this.ibkrUnifiedShort() || "IBKR"
			if (mode === "playbook_core" && this.rankedOpps.loading && !this.playbookBoardHasContent())
				ctx.loading = true
			if (mode === "discovery_research") {
				ctx.loading = ctx.loading || this.scannerHub.loading
				if (this.scannerDiscoveryHasFallbackRows()) {
					ctx.fallback = true
					ctx.failed_fetch_with_fallback = true
					ctx.error = ""
				} else {
					ctx.error = ctx.error || this.scannerHub.error || ""
				}
				ctx.mock_only = ctx.mock_only || this.scannerUsesBriefFallback()
				if (this.discoveryHeaderMode()) ctx.research_only = true
			}
			if (mode === "ops_diagnostic" && (!this.live || !(this.ops && this.ops.running))) {
				ctx.runtime_unknown = !!hints.runtime_unknown || !this.cc_status.last_fetch
			}
			if (mode === "rejections_diagnostic") {
				const rHints = this.surfaceFetchHints.notrade || {}
				ctx.loading = !!(rHints.loading || this.rejectionsPanel.loading) && !rHints.failed_fetch
				if (rHints.failed_fetch && rHints.error) {
					ctx.error = rHints.error
				} else if (rHints.error) {
					ctx.error = rHints.error
				}
				if (this.rejectionsPanel.data?.degraded || this.rejectionsPanel.data?.trust?.stale) ctx.stale = true
				if (this.rejectionsPanel.data?.research_only) ctx.research_only = true
				if (
					!ctx.loading &&
					!ctx.error &&
					this.rejectionsPanel.data &&
					!(this.rejectionsPanel.data.no_trade_signals || []).length
				)
					ctx.empty = true
			}
			if (mode === "funds_research") {
				ctx.loading = ctx.loading || this.fundMonitor.loading
				if (
					this.fundMonitor.data?.degraded ||
					this.fundMonitor.data?.research_only ||
					this.fundMonitor.data?.trust?.stale
				)
					ctx.stale = true
				if (this.fundMonitor.data?.research_only) ctx.research_only = true
			}
			if (mode === "backtest_research") {
				ctx.loading = ctx.loading || this.btLab.loading
				if (this.btLab.data?.degraded || this.btLab.data?.research_only || this.btLab.data?.trust?.stale)
					ctx.stale = true
				if (this.btLab.data?.research_only) ctx.research_only = true
			}
			if (mode === "dossier_research") {
				ctx.loading =
					ctx.loading ||
					this.dos.loading ||
					this.dos.status === "loading_core" ||
					this.dos.status === "loading_enrichments"
				const hints = this.surfaceFetchHints.dossier || {}
				if (hints.loading) ctx.loading = true
				if (this.dos.status === "failed" || (this.dos.error && !this.dosHasLoadedData())) {
					ctx.error = hints.error || this.dosFetchErrorDetail()
					ctx.fetch_detail = this.dos.fetchDetail || ""
				} else if (this.dos.status === "stale_fallback" && this.dos.error) {
					ctx.stale = true
					ctx.error = hints.error || this.dosFetchErrorDetail()
				} else if (this.dos.status === "partial_loaded" && (this.dos.partialNotice || this.dos.error)) {
					ctx.partial = true
					ctx.error = this.dos.partialNotice || this.dos.error
				} else if (hints.failed_fetch && hints.error) {
					ctx.error = hints.error
				}
			}
			if (mode === "rs_supporting" && this.rsPanel.data?.degraded) ctx.stale = true
			return ctx
		},
		headerSummary() {
			const cached = this.ccHeader.header_summary
			if (cached && cached.surface_mode === this.pageSurface() && !this.surfaceFetchHints[this.tab]) return cached
			const mode = this.pageSurface()
			const base = { ...(this._HEADER_BASE[mode] || this._HEADER_BASE.discovery_research) }
			const ctx = this.headerContext()
			let fetchState = this._normalizeFetchState(ctx)
			if (mode === "discovery_research" && ctx.failed_fetch_with_fallback) fetchState = "failed_fetch_fallback"
			if (!this.surfaceShowsDecisionChips(mode) && fetchState === "ok") fetchState = "not_authoritative"
			const fetchBadges = {
				loading: "LOADING",
				stale: "STALE",
				fallback: "FALLBACK",
				partial: "PARTIAL",
				failed_fetch: "FETCH FAILED",
				failed_fetch_fallback: "FETCH FAILED",
				mock_only: "MOCK ONLY",
				research_only: "RESEARCH ONLY",
				execution_blocked: "EXEC BLOCKED",
				no_data: "NO DATA",
				not_authoritative: "NOT AUTHORITATIVE",
				probe_only: "PROBE ONLY",
				runtime_unknown: "RUNTIME UNKNOWN",
				ok: "",
			}
			const chips = []
			if (this.surfaceShowsDecisionChips(mode) && ["ok", "stale", "fallback"].includes(fetchState)) {
				const chipAuth = this.normalizedAuthorityChipForTab(this.tab, { badge: "", authority: "monitor_only" })
				const deployLbl = String(ctx.deploy_label || "").toUpperCase()
				if (chipAuth.badge === "DEPLOY" && ctx.deploy_label)
					chips.push({ label: String(ctx.deploy_label), class: "deploy" })
				else if (ctx.deploy_label && deployLbl && !["DEPLOY", "TRADE", "ALLOCATE"].includes(deployLbl))
					chips.push({ label: String(ctx.deploy_label), class: "pa" })
				else if (this.pageAuthorityIsDegraded() || this.isWaitDay())
					chips.push({ label: chipAuth.badge || "MONITOR ONLY", class: "pa" })
				if (ctx.best_idea_ticker) chips.push({ label: "Idea " + ctx.best_idea_ticker, class: "idea" })
				if (ctx.avoid_count > 0) chips.push({ label: "Avoid " + ctx.avoid_count, class: "avoid" })
			} else if (mode === "dossier_research" && ctx.ticker) {
				chips.push({ label: String(ctx.ticker).toUpperCase(), class: "ticker" })
			} else if (mode === "portfolio_manual") {
				const pc = this.ccHeader.portfolio_context || {}
				chips.push({ label: "Portfolio mode", class: "book" })
				chips.push({ label: pc.book_label || this.portfolioHeaderBookLabel(), class: "book" })
				chips.push({ label: pc.positions_label || this.portfolioHeaderPositionsLabel(), class: "book" })
				if (
					(pc.broker_sync || "unavailable") === "unavailable" ||
					this.portfolioHeaderBrokerSyncUnavailable()
				) {
					chips.push({ label: pc.broker_sync_label || "Broker sync unavailable", class: "avoid" })
				}
				chips.push({ label: pc.rebalance_label || "Rebalance support only", class: "deploy" })
			} else if (mode === "flow_supporting") {
				chips.push({ label: "Flow hits " + String(ctx.flow_count || 0), class: "flow" })
			} else if (mode === "ibkr_execution") {
				chips.push({ label: String(ctx.ibkr_label || "IBKR"), class: "ibkr" })
			}
			// header chips when !discoveryHeaderMode() && decisionHub
			// Avoid repeating the same title twice (title + subtitle).
			// Only show a subtitle when it adds new information.
			const subtitle =
				this.surfaceShowsDecisionChips(mode) && !this.discoveryHeaderMode() && this.decisionHub
					? this.canonicalRegimeLine()
					: mode === "discovery_research"
						? "Research-only · " + this.canonicalRegimeLine()
						: ""
			const showChips =
				this.surfaceShowsDecisionChips(mode) &&
				!this.discoveryHeaderMode() &&
				!!this.decisionHub &&
				["ok", "stale", "fallback"].includes(fetchState)
			let badge = mode === "guide_reference" ? base.badge : fetchBadges[fetchState] || base.badge
			let explanation =
				fetchState === "failed_fetch_fallback"
					? this.surfaceFetchStateCopy("failed_fetch_fallback").explanation
					: base.explanation
			let nextAction =
				fetchState === "failed_fetch_fallback"
					? this.surfaceFetchStateCopy("failed_fetch_fallback").next_action
					: base.next_action
			if (mode === "dossier_research" && fetchState === "failed_fetch") {
				const dc = this.dossierFetchStateCopy("failed_fetch", ctx.fetch_detail, this.dosFetchServiceName())
				badge = dc.badge
				explanation = dc.explanation
				nextAction = dc.next_action
			} else if (mode === "dossier_research" && fetchState === "loading") {
				const dc = this.dossierFetchStateCopy("loading", null, this.dosFetchServiceName())
				badge = dc.badge
				explanation = dc.explanation
				nextAction = dc.next_action
			} else if (mode === "dossier_research" && fetchState === "stale") {
				const dc = this.dossierFetchStateCopy("stale", null, this.dosFetchServiceName())
				badge = dc.badge
				explanation = dc.explanation
				nextAction = dc.next_action
			} else if (mode === "dossier_research" && fetchState === "partial") {
				const dc = this.dossierFetchStateCopy("partial", ctx.error, this.dosFetchServiceName())
				badge = dc.badge
				explanation = dc.explanation
				nextAction = dc.next_action
			} else if (mode === "rejections_diagnostic" && (fetchState === "failed_fetch" || fetchState === "stale")) {
				const rs = fetchState === "stale" ? "fallback" : this.rejectionsInferDegradedState()
				const oc = this.opsDegradedCopy(rs)
				badge = oc.badge
				explanation = oc.explanation
				nextAction = oc.next_action
			}
			const normalizedChip = this.normalizedAuthorityChipForTab(this.tab, {
				badge: base.badge,
				authority: "monitor_only",
				short: base.next_action,
				authority_label: base.explanation,
			})
			if (
				["ok", "not_authoritative"].includes(fetchState) ||
				mode === "dashboard_core" ||
				mode === "playbook_core"
			) {
				badge = normalizedChip.badge || badge
			}
			return {
				surface_mode: mode,
				badge,
				title: base.title,
				subtitle,
				explanation,
				next_action: nextAction,
				fetch_state: fetchState,
				show_decision_chips: showChips,
				show_regime_strip: mode !== "guide_reference",
				chips,
				authority_badge: base.badge,
			}
		},
		pageAuthorityMode() {
			if (this.tab === "guide") return "guide_reference"
			const surface = this.pageSurface()
			if (!this.surfaceShowsDecisionChips(surface)) return surface
			const mode = String(this.ccHeader.page_authority_mode || "").toLowerCase()
			if (mode && mode !== "active") return mode
			if (!this.live || this.cc_status.breaker) return "diagnostic"
			if (this.todayUsesBriefFallback() || this.decisionAuthority().source === "fallback_brief")
				return "fallback_board"
			const da = this.decisionAuthority()
			const trust = this.today7.trust || {}
			const cs = this.ccState()
			const bs = String(cs.board_decision_state?.state || "").toUpperCase()
			if (
				this.isWaitDay() ||
				da.degraded ||
				da.gates_active ||
				bs === "SUSPENDED" ||
				bs === "RESEARCH_ONLY" ||
				da.authority_level === "suspended" ||
				da.authority_level === "research" ||
				trust.stale ||
				this.playbookBoardWait()
			)
				return "degraded_board"
			return "active"
		},
		pageAuthorityIsDegraded() {
			return this.pageAuthorityMode() !== "active"
		},
		scannerResearchOnlyPosture() {
			if (this.isWaitDay() || this.playbookBoardWait()) return true
			if (this.todayUsesBriefFallback() || this.playbookUsesBriefFallback()) return true
			return this.scannerUsesBriefFallback() || this.scannerDataStale()
		},
		scannerUsesBriefFallback() {
			const d = this.scannerHub.data || {}
			if (String(d.score_display_mode || "") === "fallback_rank") return true
			const ul = String(d.universe_label || "").toLowerCase()
			if (ul === "synthetic_default") return true
			const diag = d.diagnostics || {}
			const fresh = String(diag.data_freshness || "").toLowerCase()
			if (["synthetic", "warming", "stale"].includes(fresh)) return true
			const hub = String(d.hub_status || "").toLowerCase()
			return hub === "warming" || hub === "degraded"
		},
		scannerDataStale() {
			if (this.today7.trust && this.today7.trust.stale) return true
			return this.scannerUsesBriefFallback()
		},
		discoveryHeaderMode() {
			return this.tab === "scanners" && this.scannerResearchOnlyPosture()
		},
		portfolioHeaderMode() {
			return this.tab === "portfolio" || this.pageSurface() === "portfolio_manual"
		},
		portfolioHeaderCtx() {
			const ctx = this.ccHeader && this.ccHeader.portfolio_context
			if (ctx && typeof ctx === "object") return ctx
			const src = this.pfBrokerSource()
			const count = (this.pf.summary && this.pf.summary.total_positions) || (this.pf.positions || []).length || 0
			const manual = src.pill === "MANUAL" || this.pf.source === "manual"
			const brokerOk = !!(this.cc_status && this.cc_status.ibkr_connected)
			return {
				book_label: manual ? "Manual book" : src.pill,
				positions_label: count ? `${count} ` + this.pluralize(count, "position") : "No positions",
				broker_sync: brokerOk ? "ok" : "unavailable",
				rebalance_label: "Rebalance support only",
			}
		},
		portfolioHeaderBookLabel() {
			return this.portfolioHeaderCtx().book_label || "Manual book"
		},
		portfolioHeaderPositionsLabel() {
			return this.portfolioHeaderCtx().positions_label || "No positions"
		},
		portfolioHeaderBrokerSyncUnavailable() {
			const sync = this.portfolioHeaderCtx().broker_sync
			return sync === "unavailable" || !this.cc_status || !this.cc_status.ibkr_connected
		},
		portfolioHeaderLine() {
			const ctx = this.portfolioHeaderCtx()
			const parts = [ctx.book_label || "Manual book", ctx.positions_label || "No positions"]
			if (this.portfolioHeaderBrokerSyncUnavailable()) parts.push("Broker sync unavailable")
			parts.push(ctx.rebalance_label || "Rebalance support only")
			return parts.join(" · ")
		},
		pfLocalStorageKey() {
			return "cc_portfolio_local_holdings"
		},
		hydratePortfolioFromLocal() {
			try {
				const raw = localStorage.getItem(this.pfLocalStorageKey())
				if (!raw) return null
				const data = JSON.parse(raw)
				return Array.isArray(data.holdings) ? data : null
			} catch (e) {
				return null
			}
		},
		savePortfolioToLocal(holdings) {
			try {
				localStorage.setItem(
					this.pfLocalStorageKey(),
					JSON.stringify({ holdings, updated_at: new Date().toISOString(), source: "manual" }),
				)
			} catch (e) {
				console.warn("portfolio local save failed", e)
			}
		},
		mergeLocalPortfolioHoldings(holdings) {
			const local = this.hydratePortfolioFromLocal()
			if (!local || !local.holdings || !local.holdings.length) return holdings || []
			const merged = [...(holdings || [])]
			const seen = new Set(merged.map((p) => (p.ticker || p.symbol || "").toUpperCase()))
			local.holdings.forEach((h) => {
				const t = (h.ticker || "").toUpperCase()
				if (!t || seen.has(t)) return
				merged.push(h)
				seen.add(t)
			})
			return merged
		},
		buildLocalPosition(body) {
			const entry = Number(body.entry_price)
			const shares = Number(body.shares)
			const stop = Number(body.stop_price || 0)
			const stopDefined = stop > 0
			const risk = stopDefined ? Math.abs(entry - stop) : 0
			let t1r = Number(body.target_1r || 0)
			let t2r = Number(body.target_2r || 0)
			if (stopDefined && !t1r) t1r = Math.round((entry + risk) * 100) / 100
			if (stopDefined && !t2r) t2r = Math.round((entry + 2 * risk) * 100) / 100
			return {
				ticker: String(body.ticker || "").toUpperCase(),
				shares,
				entry_price: entry,
				avg_cost: entry,
				current_price: entry,
				stop_price: stopDefined ? stop : 0,
				target_1r: stopDefined ? t1r : 0,
				target_2r: stopDefined ? t2r : 0,
				market_value: Math.round(entry * shares * 100) / 100,
				cost_basis: Math.round(entry * shares * 100) / 100,
				unrealized_pnl: 0,
				pnl_pct: 0,
				stop_defined: stopDefined,
				quote_pending: true,
				status: "OPEN",
				added_at: new Date().toISOString(),
				notes: body.notes || "",
				source: "local",
			}
		},
		applyLocalPortfolioAdd(body) {
			const pos = this.buildLocalPosition(body)
			const merged = this.mergeLocalPortfolioHoldings(this.pf.positions || [])
			const next = merged.filter((p) => (p.ticker || p.symbol || "").toUpperCase() !== pos.ticker)
			next.push(pos)
			this.savePortfolioToLocal(next)
			this.pf.positions = next
			this.pf.source = "manual"
			const totalVal = next.reduce((s, p) => s + (p.market_value || p.entry_price * p.shares || 0), 0)
			const totalCost = next.reduce((s, p) => s + (p.cost_basis || p.entry_price * p.shares || 0), 0)
			this.pf.summary = {
				total_positions: next.length,
				total_value: Math.round(totalVal * 100) / 100,
				total_cost: Math.round(totalCost * 100) / 100,
				total_pnl: Math.round((totalVal - totalCost) * 100) / 100,
				total_pnl_pct: totalCost ? Math.round((totalVal / totalCost - 1) * 10000) / 100 : 0,
			}
			return pos
		},
		surfaceEmptyState(tab, ctx) {
			const c = ctx || {}
			const hintsKey = tab === "notrade" ? "notrade" : tab === "signals" ? "signals" : tab
			const hints = this.surfaceFetchHints[hintsKey] || {}
			const loading = !!(
				c.loading ||
				hints.loading ||
				(tab === "signals" &&
					(this.rankedOpps.loading || (!this.playbookBoardHasContent() && this.rankedOpps.refreshing))) ||
				(tab === "scanners" && this.scannerHub.loading) ||
				(tab === "notrade" && this.rejectionsPanel.loading)
			)
			if (loading) {
				return {
					kind: "WARMING",
					headline: "Surface warming",
					detail: "API still loading — do not treat empty panels as proof of zero ideas.",
					badge: "WARMING",
					cta: "Wait or refresh",
				}
			}
			const failed = !!(
				c.failed_fetch ||
				hints.failed_fetch ||
				(tab === "signals" && this.playbookFetchFailed()) ||
				(tab === "scanners" && this.scannerHub.error && !this.scannerDiscoveryHasFallbackRows()) ||
				(tab === "notrade" && this.rejectionsFetchFailed())
			)
			if (failed) {
				const err = c.error || hints.error || this.scannerHub.error || ""
				const rejectDetail =
					tab === "notrade" && !err
						? "Fresh rejection data unavailable; no blocked signals shown"
						: (err ? String(err) + " — " : "") + "Retry when the badge clears before sizing or handoff."
				return {
					kind: "FETCH_FAILED",
					headline: tab === "notrade" ? "Rejections unavailable" : "Fetch failed",
					detail: rejectDetail,
					badge: "FETCH FAILED",
					cta: "Retry fetch",
				}
			}
			const waitOk = !!(
				c.wait_day_ok ||
				(tab === "signals" && this.playbookBoardWait()) ||
				(tab === "scanners" && this.discoveryWaitZeroHits()) ||
				(tab === "today" && this.isWaitDay() && this.dashboardHasNoBoardData())
			)
			if (waitOk) {
				return {
					kind: "WAIT_DAY_OK",
					headline: "Empty board — often correct on WAIT",
					detail: tab === "scanners" ? this.discoveryWaitEmptyLine() : this.playbookEmptyComment(),
					badge: "WAIT DAY OK",
					cta: "Review monitor funnel",
				}
			}
			return {
				kind: "NO_DATA",
				headline: "No rows in this batch",
				detail:
					c.detail ||
					(tab === "signals"
						? this.playbookEmptyComment()
						: tab === "notrade"
							? "No blocked signals in current pipeline batch."
							: "Nothing to show yet."),
				badge: "NO DATA",
				cta: "Refresh",
			}
		},
		playbookEmptyState() {
			const es = this.surfaceEmptyState("signals", {})
			return {
				kind: es.kind,
				badge: es.badge,
				title: es.headline,
				detail: es.detail,
				cta: es.cta || "🔄 Refresh playbook",
			}
		},
		discoveryEmptyState() {
			return this.surfaceEmptyState("scanners", {})
		},
		dashboardEmptyState() {
			return this.surfaceEmptyState("today", { wait_day_ok: this.isWaitDay() && this.dashboardHasNoBoardData() })
		},
		rejectionsEmptyState() {
			return this.surfaceEmptyState("notrade", {
				empty: !(this.rejectionsPanel.data?.no_trade_signals || []).length,
			})
		},
		dismissDataContract() {
			this.dataContractDismissed = true
			try {
				localStorage.setItem("cc_data_contract_dismissed", "1")
			} catch (e) {}
		},
		dataContractFetchBadge() {
			const hs = this.headerSummary()
			if (hs && hs.badge) return hs.badge
			const hints = this.surfaceFetchHints[this.tab] || {}
			if (hints.loading) return "LOADING"
			if (hints.failed_fetch) return "FETCH FAILED"
			if (hints.stale) return "STALE"
			if (hints.fallback) return "FALLBACK"
			return "LIVE"
		},
		dataContractBrokerShort() {
			if (this.tab === "ibkr") return this.ibkrTrustStripLabel()
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			if (st.short === "READY" || st.handoff) return "READY"
			if (st.gw && !st.connected) return "LOGIN"
			if (st.short && st.short !== "OFFLINE") return st.short
			return this.cc_status.ibkr_connected ? "READY" : "OFFLINE"
		},
		dataContractStripVisible() {
			return (this.tab === "today" || this.tab === "signals") && !this.dataContractDismissed
		},
		dataContractStrip() {
			return {
				fetch: this.dataContractFetchBadge(),
				board: this.canonicalRegimeLine() || this.canonicalTradeability() || "—",
				broker: this.dataContractBrokerShort(),
				dismissible: true,
			}
		},
		severityBadgeClass(state) {
			if (typeof CCHelpers !== "undefined" && CCHelpers.severityBadgeClass)
				return CCHelpers.severityBadgeClass(state)
			const s = String(state || "").toLowerCase()
			if (s === "failed_fetch" || s === "failed_fetch_fallback" || s === "execution_blocked") return "pr"
			if (s === "stale" || s === "fallback" || s === "partial" || s === "loading") return "pa"
			if (s === "ok") return "pg"
			return "pw"
		},
		surfaceWarmupLoadingLine(surfaceMode) {
			const mode = String(surfaceMode || (this._SURFACE_MODES || {})[this.tab] || "")
			if (typeof CCHelpers !== "undefined" && CCHelpers.surfaceWarmupLoadingLine)
				return CCHelpers.surfaceWarmupLoadingLine(mode)
			return "API still loading — retry in a few seconds."
		},
		dataContractFetchStateKey() {
			const f = String(this.dataContractStrip().fetch || "").toUpperCase()
			const map = {
				"FETCH FAILED": "failed_fetch",
				"EXEC BLOCKED": "execution_blocked",
				STALE: "stale",
				FALLBACK: "fallback",
				LOADING: "loading",
				PARTIAL: "partial",
				"MOCK ONLY": "mock_only",
				"RESEARCH ONLY": "research_only",
				"NO DATA": "no_data",
				"NOT AUTHORITATIVE": "not_authoritative",
				"PROBE ONLY": "probe_only",
				"RUNTIME UNKNOWN": "runtime_unknown",
			}
			return map[f] || "ok"
		},
		warmupContextStripVisible() {
			const opts = {
				tab: this.tab,
				warmupStatusLine: this.warmupStatusLine(),
				warmupUpgradeQueue: this.warmupUpgradeQueue(),
				instantBannerVisible: this.instantDegradedBannerVisible(),
				dataContractStripVisible: this.dataContractStripVisible(),
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.warmupContextStripVisible)
				return CCHelpers.warmupContextStripVisible(opts)
			if (opts.tab === "guide") return false
			if (!(opts.warmupStatusLine || opts.warmupUpgradeQueue)) return false
			if (opts.instantBannerVisible) return false
			return opts.dataContractStripVisible
		},
		loadingSessionRecoveryLine() {
			const opts = {
				healthMode: String(this.healthMode || this.healthData?.mode || "").toLowerCase(),
				ccMode: String(this.cc_status?.mode || ""),
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.loadingSessionRecoveryLine)
				return CCHelpers.loadingSessionRecoveryLine(opts)
			if (opts.healthMode !== "loading" && opts.ccMode !== "LOADING") return ""
			return "Cold start: port 8000 instant shell may proxy to :8001 — wait for /health mode=full; restart once if loading exceeds ~2 min"
		},
		todayMissionMonitorsLabel() {
			const p = this.todayMissionPanel()
			const { watch } = this.playbookFunnelCounts(this.today7.filter_funnel, null)
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionMonitorsLabel)
				return CCHelpers.todayMissionMonitorsLabel(p.monitors, (this.today7.near_miss || []).length, watch)
			const n = (p.monitors || []).length
			const nm = (this.today7.near_miss || []).length
			if (!n && !nm) return "Monitors"
			const prefix = n && !watch ? "Fallback monitors" : "Monitors"
			const base = n ? prefix + " (" + n + ")" : prefix
			return nm ? base + " · " + nm + " near-miss" : base
		},
		todayMissionWaitSubtitle() {
			const opts = { waitDay: !!this.isWaitDay() }
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionWaitSubtitle)
				return CCHelpers.todayMissionWaitSubtitle(opts)
			return opts.waitDay ? "Deploy blocked — use monitors and Playbook ranking only" : ""
		},
		todayMissionMonitorsColumnHint() {
			const p = this.todayMissionPanel()
			const { watch } = this.playbookFunnelCounts(this.today7.filter_funnel, null)
			const opts = { waitDay: !!this.isWaitDay(), watchQualified: watch, monitorCount: (p.monitors || []).length }
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionMonitorsColumnHint)
				return CCHelpers.todayMissionMonitorsColumnHint(opts)
			if (watch > 0)
				return watch + " watch-qualified on funnel — mission tickers are attention queue, not extra KPI count"
			if (opts.monitorCount > 0)
				return "Fallback monitors — scan / near-miss queue; filter_funnel is authority for watch-qualified"
			return opts.waitDay
				? "Near-miss · watch queue — priority only, not deploy on WAIT"
				: "Watch / near-miss — ranking for attention, not handoff permission"
		},
		todayMissionQuantClusterLines() {
			const hints = this.today7?.quant_cluster_hints || []
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionQuantClusterLines)
				return CCHelpers.todayMissionQuantClusterLines(hints)
			return hints
				.slice(0, 3)
				.map((h) => {
					const label = String(h?.label || "").trim()
					const detail = String(h?.detail || "").trim()
					return label
						? label + (detail && detail.length <= 72 ? " — " + detail : " — 只供 Monitor，唔可 Deploy")
						: ""
				})
				.filter(Boolean)
		},
		todayBoardHeroSynthesisLine() {
			const opts = {
				waitDay: !!(this.isWaitDay() || this.playbookBoardWait()),
				quantClusterHints: this.today7?.quant_cluster_hints || [],
				noSetupDiagnosis: this.today7?.no_setup_diagnosis || null,
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayBoardHeroSynthesisLine)
				return CCHelpers.todayBoardHeroSynthesisLine(opts)
			if (!opts.waitDay) return ""
			const parts = []
			const h0 = (opts.quantClusterHints || [])[0]
			if (h0) {
				const label = String(h0.label || h0.cluster || "").trim()
				const detail = String(h0.detail || "").trim()
				if (label)
					parts.push(
						label +
							(detail && detail.length <= 48 ? " (" + detail + ")" : detail ? " — monitor context" : ""),
					)
			}
			const diag = opts.noSetupDiagnosis || {}
			const blocker = String(diag.primary_blocker || diag.headline || "").trim()
			if (blocker) parts.push(blocker)
			return parts.length ? "綜合提示 · 只供 Monitor：" + parts.join(" · ") + " · 唔代表 deploy permission" : ""
		},
		todayExecutionReadinessDiagnostic() {
			const er = this.today7?.execution_readiness || {}
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayExecutionReadinessDiagnostic)
				return CCHelpers.todayExecutionReadinessDiagnostic(er)
			const sub = er.sub_status || {}
			const gaps = []
			if (sub.broker_transport !== "up") gaps.push("transport down")
			if (sub.session_auth !== "active") gaps.push("session inactive")
			if (sub.engine !== "on") gaps.push("engine off")
			if (sub.handoff_readiness !== "ready") gaps.push("handoff blocked")
			if (sub.bracket_readiness !== "ready") gaps.push("bracket draft")
			if (er.circuit_breaker) gaps.push("breaker on")
			if (!gaps.length && er.trade_handoff_ready) return ""
			const reasons = (er.degraded_reasons || []).slice(0, 2).filter(Boolean)
			let base = "Exec diagnostic: " + (gaps.length ? gaps.join(" · ") : er.readiness_label || "path incomplete")
			if (reasons.length) base += " — " + reasons.join("; ")
			return base + " · 只供診斷"
		},
		playbookStrategyDecayLine(r) {
			if (typeof CCHelpers !== "undefined" && CCHelpers.playbookStrategyDecayLine)
				return CCHelpers.playbookStrategyDecayLine(r)
			return String(r?.strategy_decay_line || "").trim()
		},
		todayMissionSafeUnlockHint() {
			const er = this.today7?.execution_readiness || {}
			const ib = this.ibkrStateFrom(er)
			const opts = {
				waitDay: !!this.isWaitDay(),
				ibkrReady: ib.level === "ready",
				engineRunning: !!this.ops.running,
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionSafeUnlockHint)
				return CCHelpers.todayMissionSafeUnlockHint(opts)
			if (opts.waitDay) return "Blocked: deploy · Safe: monitors · near-miss · Playbook ranking"
			if (!opts.ibkrReady) return "Blocked: IBKR handoff · Safe: dossier core-only · monitor queue"
			if (!opts.engineRunning) return "Blocked: new cycle sizing · Safe: Guide · monitors until engine ON"
			return ""
		},
		operatorLoadingSafeLine() {
			const opts = {
				healthMode: String(this.healthMode || this.healthData?.mode || "").toLowerCase(),
				ccMode: String(this.cc_status?.mode || ""),
				waitDay: !!this.isWaitDay(),
				fetchFailed: !!this.surfaceFetchHints[this.tab]?.failed_fetch,
				instantDegraded: !!this.instantDegradedBannerVisible(),
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.operatorLoadingSafeLine)
				return CCHelpers.operatorLoadingSafeLine(opts)
			if (opts.healthMode === "loading" || opts.ccMode === "LOADING")
				return "Safe now: monitor queue, Guide checklist, dossier core-only — wait for backend import + /health mode=full before sizing or IBKR handoff"
			if (opts.fetchFailed || opts.instantDegraded)
				return "Safe now: Guide, monitors, dossier core-only — retry when fetch badges clear; no deploy from fallback"
			if (opts.waitDay)
				return "Safe now: near-miss monitors, Discovery context, Playbook ranking — deploy blocked on WAIT"
			return ""
		},
		routeAbortRecoveryHint(surface) {
			if (typeof CCHelpers !== "undefined" && CCHelpers.routeAbortRecoveryHint)
				return CCHelpers.routeAbortRecoveryHint(surface)
			return "Fetch failed — retry when badges clear; monitor queue and Guide remain safe"
		},
		staleRefreshRecoveryLine() {
			if (typeof CCHelpers !== "undefined" && CCHelpers.staleRefreshRecoveryLine)
				return CCHelpers.staleRefreshRecoveryLine()
			return "Market snapshot stale — refresh market data before using levels for sizing"
		},
		engineOffRecoveryLine() {
			if (typeof CCHelpers !== "undefined" && CCHelpers.engineOffRecoveryLine)
				return CCHelpers.engineOffRecoveryLine()
			return "Engine OFF — start engine in Ops or set CC_AUTO_START_ENGINE=1; board may be precomputed only"
		},
		ibkrLoginToReadyHint() {
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			if (typeof CCHelpers !== "undefined" && CCHelpers.ibkrLoginToReadyHint)
				return CCHelpers.ibkrLoginToReadyHint(st)
			const short = String(st.short || "").toUpperCase()
			if (short === "OFFLINE" || st.level === "offline")
				return "IBKR OFFLINE — start Gateway/TWS and confirm API port; Connect on IBKR tab when reachable"
			if (short === "LOGIN" || (st.gw && !st.connected))
				return "IBKR LOGIN — connect session on IBKR tab; READY required before handoff (bracket aligned)"
			if (st.handoff || st.level === "ready")
				return "IBKR READY — handoff path verified; confirm bracket alignment before transmit"
			return "IBKR partial — session up; confirm bracket and portfolio sync before handoff"
		},
		warmupStatusLine() {
			const mode = String(this.healthMode || this.healthData?.mode || "").toLowerCase()
			const offline = !this.healthData && this.healthMode === "loading" && !!this.apiError
			const opts = {
				healthMode: mode,
				apiReachable:
					!offline && !/failed to fetch|networkerror|econnrefused/i.test(String(this.apiError || "")),
				instantDegraded: !!(
					this.today7.instant_degraded ||
					this.rankedOpps.instant_degraded ||
					this.pageAuthorityIsDegraded() ||
					this.todayUsesBriefFallback()
				),
				fetchFailed: !!this.surfaceFetchHints[this.tab]?.failed_fetch,
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.warmupStatusLine) {
				const line = CCHelpers.warmupStatusLine(opts)
				if (mode === "full" && !opts.instantDegraded && !opts.fetchFailed) return ""
				return line
			}
			if (!opts.apiReachable) return "OFFLINE — API unreachable · instant snapshot may be stale"
			if (mode === "loading" || this.cc_status.mode === "LOADING")
				return "WARMING — backend importing modules · brief/monitor queue only until full"
			if (opts.instantDegraded)
				return "DEGRADED — instant snapshot · council/scanner may disagree until live ranked loads"
			if (mode === "full") return ""
			return "LOADING — probing /health before treating board as live"
		},
		warmupUpgradeQueue() {
			const mode = String(this.healthMode || this.healthData?.mode || "").toLowerCase()
			const opts = {
				healthMode: mode,
				briefFallback: !!(this.todayUsesBriefFallback() || this.pageAuthorityIsDegraded()),
				nearMiss: !!(this.today7.near_miss || []).length,
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.warmupUpgradeQueue)
				return CCHelpers.warmupUpgradeQueue(opts)
			if (mode !== "loading" && !opts.briefFallback) return ""
			const parts = ["live ranked playbook", "today council reconciliation", "dossier enrichment"]
			if (opts.nearMiss || opts.briefFallback) parts.unshift("monitor queue (brief near-miss + top watch)")
			return "When API ready: " + parts.join(" · ")
		},
		todayMissionPanelTitle() {
			return this.isWaitDay() ? this._uiText("Today focus") : this._uiText("Today mission")
		},
		trustProvenanceLine() {
			const t = this.today7.trust || this.trust || {}
			const src = String(t.source || "market_data_service").replace(/_/g, " ")
			const fresh = String(t.freshness || "REAL_TIME")
			let age = ""
			const streams = (this.freshness && this.freshness.streams) || []
			const worst = streams.reduce((m, s) => Math.max(m, Number(s.age_min) || 0), 0)
			if (worst > 0) age = worst < 60 ? worst + "m ago" : Math.round(worst / 60) + "h ago"
			else if (this.staleSnapshotContext()) age = "historical snapshot"
			return [src, fresh, age].filter(Boolean).join(" · ")
		},
		todayMissionSystemBlockersList() {
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			const opts = {
				ibkrReady: st.level === "ready" || st.handoff || !!this.cc_status.ibkr_connected,
				ibkrShort: this.ibkrUnifiedShort(this.today7.execution_readiness),
				engineRunning: !!this.ops.running,
				breaker: !!this.cc_status.breaker,
				dataTier: String(this.freshness?.worst_tier || ""),
				briefFallback: !!(this.todayUsesBriefFallback() || this.pageAuthorityIsDegraded()),
				instantDegraded: !!(this.today7.instant_degraded || this.instantDegradedBannerVisible()),
				fetchBadge: this.dataContractFetchBadge(),
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionSystemBlockers)
				return CCHelpers.todayMissionSystemBlockers(opts)
			const out = []
			if (!opts.ibkrReady) out.push("IBKR " + String(opts.ibkrShort || "OFFLINE").toUpperCase())
			if (!opts.engineRunning) out.push("ENGINE OFF")
			if (opts.breaker) out.push("EXEC BLOCKED — risk breaker")
			if (["STALE", "CRITICAL"].includes(String(opts.dataTier).toUpperCase())) out.push("DATA " + opts.dataTier)
			if (opts.briefFallback || opts.instantDegraded) out.push("FALLBACK / BRIEF ONLY")
			return out
		},
		todayMissionBlockersTitle() {
			const sys = this.todayMissionSystemBlockersList()
			const opts = { waitDay: !!this.isWaitDay(), hasSystem: !!sys.length }
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionBlockersTitle)
				return CCHelpers.todayMissionBlockersTitle(opts)
			return opts.waitDay && opts.hasSystem
				? "System blockers · gate flags"
				: opts.waitDay
					? "Gate flags"
					: opts.hasSystem
						? "System blockers"
						: "Blockers"
		},
		todayMissionEmptyBlockersCopy() {
			const p = this.todayMissionPanel()
			const opts = { systemBlockers: p.system_blockers, cardGates: p.card_gates }
			if (typeof CCHelpers !== "undefined" && CCHelpers.todayMissionEmptyBlockersCopy)
				return CCHelpers.todayMissionEmptyBlockersCopy(opts)
			if (opts.systemBlockers.length && !opts.cardGates.length) return "No card-level gate flags"
			return "None flagged"
		},
		todayMissionPanel() {
			const td = this.today7.todays_decision || {}
			const cardGates = []
			;(td.risk_blockers || []).forEach((rb) => {
				const s = String(rb).trim()
				if (s && !cardGates.includes(s)) cardGates.push(s)
			})
			;(td.why_not_aggressive || []).slice(0, 2).forEach((w) => {
				const s = String(w).trim()
				if (s && !cardGates.includes(s)) cardGates.push(s)
			})
			const system_blockers = this.todayMissionSystemBlockersList()
			const blockers = []
			system_blockers.forEach((s) => {
				if (s && !blockers.includes(s)) blockers.push(s)
			})
			cardGates.forEach((s) => {
				if (s && !blockers.includes(s)) blockers.push(s)
			})
			const monitors = []
			const reject = new Set(["AVOID", "NO_TRADE", "BLOCKED"])
			const add = (t) => {
				const x = String(t || "")
					.toUpperCase()
					.replace(/[^A-Z0-9.^]/g, "")
				if (x && x.length <= 8 && !monitors.includes(x)) monitors.push(x)
			}
			const fromApi = (this.today7.dashboard_monitors || []).filter(Boolean)
			if (fromApi.length) {
				fromApi.forEach(add)
			} else {
				;(this.today7.near_miss || []).forEach((nm) => {
					if (!reject.has(String(nm.action || "").toUpperCase())) add(nm.ticker)
				})
				;(this.today7.top_ranked || []).forEach((r) => {
					if (!reject.has(String(r.action || "").toUpperCase())) add(r.ticker)
				})
				if (td.best_watch?.ticker) add(td.best_watch.ticker)
			}
			return {
				system_blockers: system_blockers.slice(0, 5),
				card_gates: cardGates.slice(0, 3),
				blockers: blockers.slice(0, 5),
				monitors: monitors.slice(0, 3),
				quant_cluster_lines: this.todayMissionQuantClusterLines(),
			}
		},
		headerChipGroups() {
			const hs = this.headerSummary()
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			const dataTier = this.ccFreshnessState().worst_tier || this.freshness?.worst_tier
			const opts = {
				authorityChip: this.pageAuthorityIsDegraded()
					? this.instantDegradedBannerVisible()
						? "INSTANT DEGRADED"
						: "MONITOR ONLY"
					: "",
				tradeability: this.canonicalTradeability(),
				fetchBadge: hs.badge || this.dataContractFetchBadge(),
				ibkrChip: "IBKR " + this.ibkrUnifiedShort(this.today7.execution_readiness),
				dataChip: dataTier && ["STALE", "CRITICAL"].includes(dataTier) ? "DATA " + dataTier : "",
				modeChip: this.trust?.mode || "",
				freshnessChip: this.trust?.freshness || "",
				chips: hs.chips || [],
			}
			if (hs.show_decision_chips && this.pageAuthorityIsDegraded()) {
				opts.authorityChip = ""
				opts.dataChip = ""
				opts.ibkrChip = ""
				opts.modeChip = ""
				opts.freshnessChip = ""
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.partitionHeaderChips)
				return CCHelpers.partitionHeaderChips(hs.chips, opts)
			return {
				primary: (hs.chips || []).filter((c) => c.class === "deploy" || c.class === "idea"),
				secondary: (hs.chips || []).filter((c) => c.class !== "deploy" && c.class !== "idea"),
				infra: [],
			}
		},
		opsRecoveryGuide() {
			const mode = String(this.healthMode || this.healthData?.mode || "").toLowerCase()
			const retry = []
			const blocks = []
			const safe = []
			const portLine = this.loadingSessionRecoveryLine()
			if (mode === "loading") {
				if (portLine) retry.push(portLine)
				retry.push("Wait for /health mode=full, then refresh Dashboard and Playbook")
			} else retry.push("Refresh Ops health · Error log · Updates panels")
			if (!this.ops.running) retry.push("Start engine (Ops health) or set CC_AUTO_START_ENGINE=1")
			if (!this.ops.running) blocks.push("No engine cycle — Today/Signals may be precomputed only")
			if (this.cc_status.breaker) blocks.push("Risk breaker ON — blocks new entries until cleared")
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			if (!st.connected && !this.cc_status.ibkr_connected)
				blocks.push("IBKR session inactive — no handoff until LOGIN→READY on IBKR tab")
			if (this.pageAuthorityIsDegraded() || mode === "loading") {
				const safeLine = this.operatorLoadingSafeLine()
				if (safeLine) safe.push(safeLine)
				else safe.push("Monitor-only: near-miss, Discovery context, Guide checklist")
				safe.push("Read data contract strip — FETCH FAILED / FALLBACK suspends sizing")
			} else {
				safe.push("Paper review and dossier research when board is WAIT")
				safe.push("Ops diagnostics do not override Dashboard deploy gate")
			}
			return {
				retry: retry.map((ln) => this._uiText(ln)),
				blocks_capital: blocks.map((ln) => this._uiText(ln)),
				safe_degraded: safe.map((ln) => this._uiText(ln)),
			}
		},
		pmStripNarrow() {
			return typeof window !== "undefined" && window.innerWidth < 768
		},
		pmStripUseChipMenu() {
			const chips = this.headerSummary().chips || []
			return this.pmStripNarrow() || chips.length > 4
		},
		pmStripChipMenuToggle() {
			this.pmStripChipMenuOpen = !this.pmStripChipMenuOpen
			if (!this.pmStripChipMenuOpen) return
			this.$nextTick(() => {
				try {
					const strip = document.getElementById("pm-strip")
					if (strip) strip.scrollIntoView({ behavior: "smooth", block: "nearest" })
					const drop = document.querySelector(".pm-strip-chip-drop")
					if (drop) drop.scrollIntoView({ behavior: "smooth", block: "nearest" })
				} catch (e) {}
			})
		},
		ibkrScrollSessionIntoView() {
			try {
				const el = document.getElementById("ibkr-session-state")
				if (el) el.scrollIntoView({ behavior: "smooth", block: "start" })
			} catch (e) {}
		},
		ibkrApplyStatusPayload(d) {
			if (!d || typeof d !== "object") return
			this.ibkr.statusFetchError = ""
			this.ibkr.connected = !!(d.session_usable || d.connected)
			this.ibkr.session_usable = !!(d.session_usable || d.connected)
			this.ibkr.monitoring_only = !!d.monitoring_only
			this.ibkr.mode = (d.mode || "paper").toLowerCase()
			this.ibkr.readiness = d.readiness || null
			this.ibkr.diagnostics = d.diagnostics || null
			this.ibkr.health = d.health || (d.readiness && d.readiness.health) || null
			this.ibkr.health_label = d.health_label || (this.ibkr.health && this.ibkr.health.summary_label) || ""
			this.ibkr.diagnosis = d.diagnosis || null
			this.ibkr.gateway_reachable = !!d.gateway_reachable
			this.ibkr.api_port_open = !!d.api_port_open
			if (typeof d.docker === "boolean") this.ibkr.docker = !!d.docker
			this.ibkr.host =
				window.CCHelpers && CCHelpers.ibkrSyncHostFromStatus
					? CCHelpers.ibkrSyncHostFromStatus(d.host || this.ibkr.host, !!d.docker)
					: d.host || this.ibkr.host
			if (d.readiness && d.readiness.portfolio_sync_reason) {
				this.ibkr.portfolioCompare.note = d.readiness.portfolio_sync_reason
			}
			this.ibkr.lastRefresh = new Date().toLocaleTimeString()
		},
		ibkrFormatConnectError(httpStatus, d) {
			const raw = String((d && d.detail) || (d && d.error) || (d && d.message) || "").trim()
			const isNet = /Failed to fetch|NetworkError|Load failed|fetch failed|ECONNREFUSED/i.test(raw)
			if (isNet || (!raw && !httpStatus)) {
				return "API unreachable — run ./_start_server.sh and wait for /health mode=full before Connect."
			}
			if (httpStatus === 503 || /warming up|API warming|still loading|backend importing|mode=full/i.test(raw)) {
				return raw || "API still loading — wait for /health mode=full, then Connect."
			}
			return raw || "Connection failed"
		},
		ibkrApplyStatusFetchFailure(httpStatus, rawMsg) {
			const msg = String(rawMsg || "").trim()
			const isNet = /Failed to fetch|NetworkError|Load failed|fetch failed|ECONNREFUSED/i.test(msg)
			const warming =
				httpStatus === 503 || /warming up|API warming|still loading|backend importing|mode=full/i.test(msg)
			let line = isNet
				? "Status fetch failed — API unreachable (browser “Load failed”). Confirm CC is running on :8000/:8001, then refresh."
				: warming
					? "API still loading — transport probe only until /health mode=full. Gateway may show LOGIN; Connect starts the API session when the backend is ready."
					: "Status fetch failed" +
						(httpStatus ? " (HTTP " + httpStatus + ")" : "") +
						(msg ? ": " + msg.slice(0, 140) : "")
			this.ibkr.statusFetchError = line
			if (!this.ibkr.diagnosis || !this.ibkr.diagnosis.hint) {
				this.ibkr.diagnosis = {
					short: isNet ? "OFFLINE" : "ERROR",
					label: isNet ? "API unreachable" : "Status check failed",
					hint: line,
					code: isNet ? "api_unreachable" : "status_fetch_failed",
				}
			}
			this.ibkr.health_label = this.ibkr.health_label || this.ibkr.diagnosis.label || ""
		},
		async ibkrOpenConnectFlow() {
			if (this.tab !== "ibkr") this.switchTab("ibkr")
			await this.ibkrFetchStatus({ scrollToSession: true })
		},
		playbookBridgeRowsFromTop5(rows) {
			return (rows || [])
				.filter((r) => r && r.ticker)
				.map((r, i) => ({
					ticker: r.ticker,
					score: Number(r.score) || 0,
					action: "WATCH",
					raw_action: "WATCH",
					grade: r.grade || "C",
					setup: r.strategy || r.setup || "brief_fallback",
					why_now: Array.isArray(r.why_now)
						? r.why_now.join(" · ")
						: r.why_now || "Brief fallback bridge — monitor only",
					score_display_mode: "fallback_rank",
					evidence_badge: "brief-fallback",
					confidence_fallback_only: true,
					card_display_mode: "reference_only",
					execution_ready: false,
					rank: r.rank || i + 1,
					entry_price: r.entry_price,
					stop_price: r.stop_price,
					target_price: r.target_price,
					risk_reward: r.risk_reward,
				}))
		},
		playbookBridgeFromCaches() {
			const top = this.playbookBridgeRowsFromTop5(this.today7?.top_ranked || [])
			if (top.length) return top
			try {
				const snap = JSON.parse(localStorage.getItem("cc_playbook_ranked_snapshot") || "null")
				if (snap && (snap.opportunities || []).length)
					return this.playbookBridgeRowsFromTop5(snap.opportunities.slice(0, 30))
			} catch (e) {}
			try {
				const today = JSON.parse(localStorage.getItem("cc_today7_snapshot") || "null")
				if (today && (today.top_5 || []).length) return this.playbookBridgeRowsFromTop5(today.top_5)
			} catch (e) {}
			return []
		},
		playbookOppsFallbackRows() {
			if ((this.rankedOpps.rows || []).length) return []
			return (this.opps || []).filter((r) => {
				const g = String(this.cardExecutionGrade(r) || this.effectiveCardAction(r) || "").toUpperCase()
				if (["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"].includes(g)) return false
				if (["AVOID", "NO_TRADE", "BLOCKED"].includes(g)) return false
				return [
					"FALLBACK WATCH",
					"FALLBACK CANDIDATE",
					"WATCH ONLY",
					"WATCH",
					"PILOT",
					"REFERENCE ONLY",
					"RESEARCH ONLY",
				].includes(g)
			})
		},
		playbookOppsFallbackVisible() {
			return this.rankedOpps.rows.length === 0 && this.playbookOppsFallbackRows().length > 0
		},
		gradedLegacyOpps() {
			return this.playbookOppsFallbackRows()
		},
		playbookFetchFailed() {
			if (this.playbookIsEmergencyBoard()) return true
			if (this.rankedOpps.fetch_failed) return true
			const hints = this.surfaceFetchHints.signals || {}
			return !!(hints.failed_fetch && !this.playbookBoardHasContent())
		},
		cardScoreLabel(row) {
			const r = row || {}
			if (this.cardIsFallbackRow(r) || String(r.score_display_mode || "") === "fallback_rank") {
				const fb = this.formatFallbackScore(r)
				if (String(fb).includes("Fallback rank")) return fb
				return "Rank " + fb
			}
			const n = r.score != null ? r.score : r.strength != null ? r.strength : null
			return n != null && !Number.isNaN(Number(n)) ? Number(n).toFixed(1) : "—"
		},
		cardScorePillClass(row) {
			if (this.cardIsFallbackRow(row) || String(row?.score_display_mode || "") === "fallback_rank") return "pa"
			const n = Number(row?.score ?? 0)
			return n >= 8 ? "pg" : n >= 6 ? "pa" : "pr"
		},
		confidenceComponentPct(val) {
			if (val == null || val === "") return "—"
			const n = Number(val)
			if (!Number.isFinite(n) || n <= 0) return "—"
			const pct = n <= 1 ? Math.round(n * 100) : Math.round(n)
			return pct + "%"
		},
		flowOverlayPanelStyle() {
			if (!this.flowOverlayDegraded()) return ""
			return "opacity:0.58;filter:saturate(0.72)"
		},
		formatFallbackScore(row) {
			const r = row || {}
			const mode = String(r.score_display_mode || "")
			const source = String(r.score_source || r.source || "").toLowerCase()
			const status = String(r.status || r.freshness || "").toLowerCase()
			const isFallback =
				mode === "fallback_rank" || source.includes("brief") || status === "monitor" || r.strategy === "brief"
			if (!isFallback) {
				const n = r.strength != null ? r.strength : r.score != null ? r.score : r.max_score
				return n != null && n !== "" ? String(n) : "—"
			}
			if (r.score_display_label) return String(r.score_display_label)
			if (r.priority_tier) return "Fallback rank · " + String(r.priority_tier).toLowerCase()
			if (r.score_display) return "Fallback rank · " + String(r.score_display).toLowerCase()
			const n = Number(r.strength ?? r.score ?? r.max_score)
			if (!Number.isNaN(n) && n > 0) {
				if (n >= 7.5) return "Fallback rank · high"
				if (n >= 6) return "Fallback rank · medium"
				return "Fallback rank · low"
			}
			return "Indicative rank (fallback)"
		},
		scannerScoreLabel(h) {
			const row = h || {}
			if (String(row.score_display_mode || "") === "fallback_rank" || this.scannerUsesBriefFallback()) {
				return this.formatFallbackScore(row)
			}
			const n = row.strength != null ? row.strength : row.score != null ? row.score : null
			return "Score " + (n != null ? n : "—")
		},
		topMonitorCandidates(limit = 3) {
			const tickers = []
			const seen = new Set()
			const add = (t) => {
				const x = String(t || "")
					.toUpperCase()
					.replace(/[^A-Z0-9.^]/g, "")
				if (!x || x.length > 8 || seen.has(x)) return
				seen.add(x)
				tickers.push(x)
			}
			;(this.today7.near_miss || []).forEach((nm) => add(nm.ticker))
			;(this.today7.top_ranked || []).forEach((r) => add(r.ticker))
			;(this.rankedOpps.rows || []).forEach((r) => add(r.ticker))
			const td = this.today7.todays_decision
			if (td?.best_watch?.ticker) add(td.best_watch.ticker)
			return tickers.slice(0, limit)
		},
		degradedPmMonitorLine() {
			const names = this.topMonitorCandidates(3)
			return names.length ? "Top monitor candidates " + names.join("/") : "Top monitor candidates —"
		},
		primaryBlockerChip() {
			const cs = this.ccState()
			const tb = String(
				cs.tradeability_state?.tradeability || this.canonicalTradeability() || "WAIT",
			).toUpperCase()
			const bs = String(cs.board_decision_state?.state || "").toUpperCase()
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			if (es === "EXEC_BLOCKED") return "EXEC BLOCKED"
			if (es === "ENGINE_OFF") return "ENGINE OFF"
			if (["GATEWAY_DOWN", "IBAPI_MISSING", "SESSION_INACTIVE"].includes(es)) return es.replace(/_/g, " ")
			if (es === "HANDOFF_BLOCKED") return "HANDOFF BLOCKED"
			if (tb === "NO_TRADE") return "NO TRADE"
			if (tb === "WAIT") return "WAIT"
			if (tb === "SELECTIVE") return "SELECTIVE"
			if (bs && bs !== "DEPLOY") return bs.replace(/_/g, " ")
			return "MONITOR ONLY"
		},
		primaryBlockerLine() {
			const cs = this.ccState()
			const tb = String(
				cs.tradeability_state?.tradeability || this.canonicalTradeability() || "WAIT",
			).toUpperCase()
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			const blockers = Array.isArray(ex.blockers) ? ex.blockers : []
			if (tb === "NO_TRADE") return "盤面閘門 NO_TRADE · 只可 Monitor。"
			if (tb === "WAIT") return "盤面閘門 WAIT · 只可 Monitor。"
			if (es === "EXEC_BLOCKED") return "執行封鎖 · circuit breaker。"
			if (es === "ENGINE_OFF") return "執行封鎖 · engine off。"
			if (["GATEWAY_DOWN", "IBAPI_MISSING", "SESSION_INACTIVE"].includes(es)) {
				const b = blockers.find((x) => x && x.domain === "broker") || blockers[0] || {}
				const lbl = String(b.label || "Broker gate").trim()
				return lbl ? "執行閘門 · " + lbl + "." : "執行閘門 · broker unavailable。"
			}
			if (es === "HANDOFF_BLOCKED") return "Board gate 阻止 handoff · 先到 Dashboard / Playbook 確認。"
			const bs = String(cs.board_decision_state?.state || "").toUpperCase()
			if (bs === "SUSPENDED") return "Board authority 已暫停 · 不可 sizing / IBKR handoff。"
			if (bs === "RESEARCH_ONLY") return "Research-only 姿態 · 先去 Playbook 確認，暫不可 sizing。"
			return this.degradedPmMonitorLine()
		},
		pmDecisionTickerLine() {
			const td = this.today7.todays_decision
			if (!td) return ""
			const deploy = !!td.can_deploy_today
			const lead = deploy ? "Deploy" : "Top"
			const trail = deploy ? "Watch" : "Monitor"
			return lead + " " + (td.best_trade?.ticker || "None") + " · " + trail + " " + (td.best_watch?.ticker || "—")
		},
		dashboardBestTradeLabel() {
			const td = this.today7.todays_decision
			if (!td || !td.can_deploy_today || this.isWaitDay())
				return td?.best_trade?.ticker ? "Top watch" : "Best monitor"
			return "Best TRADE"
		},
		dashboardActionablePicks() {
			if (this.pageAuthorityIsDegraded() || !this.today7.todays_decision?.can_deploy_today) return []
			return (this.today7.top_ranked || []).filter((o) => {
				const act = String(this.effectiveCardAction(o) || "").toUpperCase()
				return o.execution_ready && ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(act)
			})
		},
		instantDegradedBannerLine() {
			if (this.instantDegradedBanner) return this.instantDegradedBanner
			const trust = this.today7.trust || {}
			if (trust.degraded_banner) return trust.degraded_banner
			if (this.today7.degraded_banner) return this.today7.degraded_banner
			if (this.rankedOpps.degraded_banner) return this.rankedOpps.degraded_banner
			const src = String(trust.source || this.trust?.source || "")
			if (
				this.today7.instant_degraded ||
				this.rankedOpps.instant_degraded ||
				src.includes("instant-degraded") ||
				src === "brief-fallback"
			)
				return "Instant degraded — snapshot only · not suitable for sizing or IBKR handoff"
			if (this.healthData && this.healthData.mode === "loading")
				return "Backend warming — brief/monitor queue until health mode is full"
			if (this.cc_status.mode === "LOADING" || this.ccHeader.page_authority_mode === "diagnostic")
				return "Backend warming — refresh when health mode is full"
			return ""
		},
		instantDegradedBannerHint() {
			if (typeof CCHelpers !== "undefined" && CCHelpers.instantDegradedBannerHint)
				return CCHelpers.instantDegradedBannerHint(this.healthData)
			if (this.healthData && this.healthData.mode === "loading")
				return (
					"Wait for /health mode=full before sizing or IBKR handoff · uptime " +
					Math.round(this.healthData.uptime_seconds || 0) +
					"s"
				)
			return "Refresh when fetch badges clear · page gates still apply on WAIT days"
		},
		instantDegradedBannerVisible() {
			if (this.instantDegradedDismissed) return false
			if (String(this.healthMode || "").toLowerCase() === "loading") return true
			return !!this.instantDegradedBannerLine()
		},
		dismissInstantDegradedBanner() {
			this.instantDegradedDismissed = true
			try {
				sessionStorage.setItem("cc_instant_degraded_dismissed", "1")
			} catch (e) {}
		},
		captureInstantDegradedBanner(data) {
			if (!data || typeof data !== "object") return
			const b = data.degraded_banner
			if (typeof b === "string" && b.trim()) this.instantDegradedBanner = b.trim()
			else if (b && typeof b === "object") {
				const line = [b.headline, b.message, b.detail].filter(Boolean).join(" — ")
				if (line) this.instantDegradedBanner = line
			}
			if (
				data.degraded ||
				data.instant_degraded ||
				String(data.trust?.source || "").includes("instant-degraded") ||
				data.source === "instant-degraded"
			) {
				if (!this.instantDegradedBanner) {
					this.instantDegradedBanner = String(
						data.trust?.reason ||
							data.board_message ||
							data.narrative ||
							"Backend importing — snapshot only",
					).slice(0, 220)
				}
			}
			if (data.degraded_banner) this.today7.degraded_banner = data.degraded_banner
			if (data.instant_degraded) this.today7.instant_degraded = true
		},
		applyWarmupBoardFromHealth(h) {
			if (!h || String(h.mode || "").toLowerCase() === "full") return
			const fb = h.fallback_board || {}
			const rows = fb.opportunities || []
			if (!rows.length) return
			if ((this.rankedOpps.rows || []).length || (this.today7.top_ranked || []).length) return
			this.applyRankedPayload(
				{
					...fb,
					board_message: fb.board_message || "Warmup brief board — monitor only, not deploy authority",
					instant_degraded: true,
					degraded: true,
				},
				{ fromCache: true },
			)
			if (!(this.today7.top_ranked || []).length)
				this.today7.top_ranked = this.playbookBridgeRowsFromTop5(rows.slice(0, 5))
		},
		async fetchWarmupBriefBoard() {
			try {
				const r = await fetch("/api/v7/warmup/brief-board", { signal: AbortSignal.timeout(5000) })
				if (r.ok) {
					const d = await r.json()
					if ((d.opportunities || []).length) {
						if ((this.rankedOpps.rows || []).length) return
						this.applyRankedPayload(d, { fromCache: true })
						if (!(this.today7.top_ranked || []).length)
							this.today7.top_ranked = this.playbookBridgeRowsFromTop5(
								(d.opportunities || []).slice(0, 5),
							)
						this.rankedOpps.loading = false
						return
					}
				}
				const sr = await fetch("/api/v7/playbook/ranked/snapshot?limit=30", {
					signal: AbortSignal.timeout(5000),
				})
				if (sr.ok) {
					const snap = await sr.json()
					if ((snap.opportunities || []).length && !this.rankedOpps.rows.length)
						this.applyRankedPayload(snap, { fromSnapshot: true, fromCache: true })
				}
			} catch (e) {
				console.warn("warmup brief-board", e)
			} finally {
				if (this.playbookBoardHasContent()) this.rankedOpps.loading = false
			}
		},
		async fetchHealth() {
			try {
				const r = await fetch("/api/health", { signal: AbortSignal.timeout(5000) })
				if (!r.ok) {
					this.healthMode = "loading"
					return
				}
				const h = await r.json()
				this.healthData = h
				this.healthMode = String(h.mode || "full").toLowerCase()
				this.captureInstantDegradedBanner(h)
				this.applyWarmupBoardFromHealth(h)
				if (this.healthMode === "loading" && !this.playbookBoardHasContent()) this.fetchWarmupBriefBoard()
			} catch (e) {
				this.healthMode = "loading"
			}
		},
		playbookCanSendToIbkr(r) {
			if (!r || !r.execution_ready || !r.entry_price || !r.stop_price) return false
			if (this.pageAuthorityIsDegraded() || this.playbookBoardWait() || this.playbookUsesBriefFallback())
				return false
			const ud = this.rankedOpps.unlock_deploy || this.today7.unlock_deploy
			if (ud && !ud.unlocked) return false
			const da = this.decisionAuthority()
			if (da && da.authority_level && da.authority_level !== "deploy") return false
			if (da && da.allows_trade_labels === false) return false
			const er = this.today7.execution_readiness || this.rankedOpps.bestAction?.execution_readiness
			if (er && er.trade_handoff_ready === false) return false
			const act = String(this.effectiveCardAction(r) || "").toUpperCase()
			return ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(act)
		},
		cardEvidenceTier(r) {
			if (!r) return ""
			const src = String(r.source || r.data_source || "").toLowerCase()
			if (r.fallback_brief || src.includes("brief") || src.includes("fallback")) return "brief · 簡報"
			if (r.stale || r.data_stale || (r.data_freshness_minutes || 0) > 480) return "stale · 過期"
			if (src.includes("live") || r.execution_ready) return "live · 即時"
			if (r.training_only || r.research_only) return "research · 研究"
			return r.evidence_badge || "monitor · 監控"
		},
		cardEvidenceTierClass(r) {
			const t = this.cardEvidenceTier(r)
			if (t.includes("live")) return "pg"
			if (t.includes("stale") || t.includes("brief")) return "pa"
			if (t.includes("research")) return "pb"
			return "pw"
		},
		async adviseSizeForRow(r) {
			if (!r || !r.ticker || !r.entry_price || !r.stop_price) return
			const tk = r.ticker
			if (this.playbookSizing[tk]?.loading) return
			this.playbookSizing = { ...this.playbookSizing, [tk]: { loading: true, error: "", data: null } }
			try {
				const q = new URLSearchParams({
					ticker: tk,
					entry_price: String(r.entry_price),
					stop_price: String(r.stop_price),
					signal_score: String(r.score || r.final_score || 70),
					signal_grade: String(r.grade || "B"),
					strategy: String(r.strategy || "UNKNOWN"),
					regime: String(this.today7.regime?.regime || this.canonicalTradeability() || "UNKNOWN"),
				})
				const resp = await this.ccFetch("/api/v7/size/advise?" + q.toString())
				if (!resp || !resp.ok) throw new Error("HTTP " + (resp ? resp.status : "fail"))
				const data = await resp.json()
				if (data.error) throw new Error(data.error)
				this.playbookSizing = { ...this.playbookSizing, [tk]: { loading: false, error: "", data } }
			} catch (e) {
				this.playbookSizing = {
					...this.playbookSizing,
					[tk]: { loading: false, error: String(e.message || e), data: null },
				}
			}
		},
		playbookSizeLine(r) {
			const s = this.playbookSizing[r?.ticker]
			if (!s?.data) return ""
			const d = s.data
			const shares = d.shares || 0
			const pct = d.final_size_pct || 0
			const risk = d.total_risk_usd || 0
			return shares ? this._uiText(`${shares} sh · ${pct}% · $${Math.round(risk)} @ 1R`) : ""
		},
		playbookCanSizeRow(r) {
			return !!(r && r.entry_price && r.stop_price && r.entry_price > r.stop_price)
		},
		bdrDecisionLine() {
			return this._uiText((this.today7.bdr_summary || {}).decision_line || "")
		},
		bdrPlainEnglishRead() {
			return this._uiText((this.today7.bdr_summary || {}).plain_english_read || "")
		},
		bdrBestConciseNote() {
			return this._uiText((this.today7.bdr_summary || {}).best_concise_note || "")
		},
		bdrHardGateLine(g) {
			if (!g) return ""
			return this._uiText(String(g.label || "") + " — " + String(g.detail || ""))
		},
		bdrMainIssue(row) {
			return this._uiText((row && row.main_issue) || "")
		},
		bdrActionBullet(ln) {
			return "• " + this._uiText(String(ln || ""))
		},
		bdrUnlockChecklistLine(c) {
			if (!c) return ""
			const head = (c.met ? "✓" : "✗") + " " + String(c.label || "") + ": " + String(c.current || "")
			return this._uiText(head) + " → " + this._uiText(String(c.target || ""))
		},
		bdrDecisionPillClass() {
			const c = (this.today7.bdr_summary || {}).decision_code || ""
			if (c === "DEPLOY") return "pg"
			if (c === "SELECTIVE") return "pb"
			return "pa"
		},
		bdrShouldAutoOpen() {
			const c = (this.today7.bdr_summary || {}).decision_code || ""
			return c === "NO_TRADE" || c === "SELECTIVE" || this.isWaitDay()
		},
		featureIcDecayAlert() {
			const st = this.today7.feature_ic_status
			return !!(st && ((st.alerts || []).length || st.status === "decay_detected"))
		},
		featureIcDecayLine() {
			const st = this.today7.feature_ic_status
			if (!st) return ""
			const alerts = (st.alerts || []).slice(0, 3).join(", ")
			return alerts
				? this._uiText(`Feature IC decay · ${alerts} — sizing confidence reduced (advisory only)`)
				: this._uiText("Feature IC decay detected — review Ops ML panel")
		},
		mlAdvisoryLineText(ln) {
			const t = this._uiText(String(ln || ""))
			return t ? "• " + t : ""
		},
		mlAdvisoryAuthorityNote() {
			const note =
				(this.today7.ml_advisory && this.today7.ml_advisory.authority_note) ||
				"Research only — does not override deploy gates or BDR decision."
			return this._uiText(note)
		},
		mlAdvisoryActive() {
			return !!(this.today7.ml_advisory && this.today7.ml_advisory.active)
		},
		mlAdvisoryLines() {
			return (this.today7.ml_advisory && this.today7.ml_advisory.lines) || []
		},
		mlAdvisoryStatus() {
			return (this.today7.ml_advisory && this.today7.ml_advisory.status) || "inactive"
		},
		mlAdvisoryShow() {
			return this.mlAdvisoryActive() || this.mlAdvisoryLines().length > 0 || this.featureIcDecayAlert()
		},
		peerCompareLine(r) {
			if (!r || !r.runner_up) return ""
			const vs = r.runner_up.ticker || "—"
			const reason = r.runner_up.reason || ""
			return `${r.ticker} vs ${vs}: ${reason}`
		},
		async fetchSelfLearnStatus() {
			try {
				const r = await this.ccFetch("/api/v7/learning")
				if (!r || !r.ok) return
				const d = await r.json()
				const s = d.summary || {}
				this.selfLearn.status = {
					closed_trades_available: s.total_trades || 0,
					engine_state: { enabled: true, total_adjustments: 0, adjustments_this_cycle: 0 },
				}
			} catch (e) {
				console.warn("fetchSelfLearnStatus", e)
			}
		},
		degradedDecisionAuthorityLine() {
			const dc = this.decisionAuthority().degraded_copy || {}
			return dc.decision_authority_line || "Decision authority degraded"
		},
		degradedExecutionUnavailable() {
			if (this.playbookBrokerOffline() || this.dashboardBrokerOffline()) return true
			const ex = this.today7.execution_readiness || {}
			return !!(ex.readiness_label && String(ex.readiness_label).toLowerCase().includes("offline"))
		},
		formatEvidence(v) {
			if (v == null || v === "") return this._uiText("Evidence unavailable")
			if (typeof v === "string") {
				const s = this.sanitizeVisibleText(v.trim())
				if (!s || /\[object Object\]/i.test(s)) return this._uiText("Evidence unavailable")
				return this._uiText(s)
			}
			if (typeof v === "number" || typeof v === "boolean") return String(v)
			if (Array.isArray(v)) {
				const parts = v
					.map((x) => this.formatEvidence(x))
					.filter((x) => x && x !== this._uiText("Evidence unavailable"))
				return parts.length ? parts.join(" · ") : this._uiText("Evidence unavailable")
			}
			if (typeof v === "object") {
				if (v.label) return this._uiText(String(v.label))
				if (v.tier) return this._uiText(String(v.tier))
				if (v.badge) return this._uiText(String(v.badge))
				const bits = []
				if (v.validated_score != null) bits.push(this._uiText("board score " + v.validated_score))
				if (v.data_conf != null)
					bits.push(
						this._uiText(
							"data quality " +
								(Number(v.data_conf) <= 1 ? Number(v.data_conf) * 100 : Number(v.data_conf)).toFixed(
									0,
								) +
								"%",
						),
					)
				if (v.calibration_available) bits.push(this._uiText("calibrated"))
				if (bits.length) return bits.join(" · ")
				return this._uiText("Evidence unavailable")
			}
			return this._uiText("Evidence unavailable")
		},
		playbookEvidenceLine(v) {
			if (v == null || v === "") return this._uiText("Evidence unavailable")
			if (typeof v === "string") return this._uiText(this.sanitizeVisibleText(v.trim()) || "Evidence unavailable")
			if (typeof v === "object") {
				const bits = []
				if (v.validated_score != null) bits.push(this._uiText("Evidence score " + v.validated_score))
				if (v.data_conf != null)
					bits.push(
						this._uiText(
							"data quality " +
								(Number(v.data_conf) <= 1 ? Number(v.data_conf) * 100 : Number(v.data_conf)).toFixed(
									0,
								) +
								"%",
						),
					)
				if (v.calibration_available) bits.push(this._uiText("calibrated"))
				return bits.length ? bits.join(" · ") : this.formatEvidence(v)
			}
			return this.formatEvidence(v)
		},
		todayUsesBriefFallback() {
			const da = this.decisionAuthority()
			if (da.source === "fallback_brief" || da.gates?.fallback_brief) return true
			const t = this.today7.trust || {}
			return (
				String(t.source || "")
					.toLowerCase()
					.includes("brief") ||
				String(t.reason || "")
					.toLowerCase()
					.includes("fallback")
			)
		},
		authorityDegradedBanner() {
			const da = this.decisionAuthority()
			const dc = da.degraded_copy || {}
			const stale = this.staleSnapshotContext()
			if (!da.degraded && !this.todayUsesBriefFallback() && !stale) return ""
			const parts = [
				dc.system_mode === "degraded" ? "System mode: degraded" : null,
				dc.decision_authority_line || null,
				stale || dc.fallback_board_line || null,
			].filter(Boolean)
			return parts.join(" · ")
		},
		staleSnapshotContext() {
			const t = this.today7.trust || {}
			const da = this.decisionAuthority()
			const stale = !!(
				t.stale ||
				da.source === "stale_cache" ||
				this.freshness?.worst_tier === "STALE" ||
				this.freshness?.worst_tier === "CRITICAL"
			)
			if (!stale && !this.todayUsesBriefFallback()) return ""
			const lines = da.degraded_copy?.stale_snapshot_lines
			if (Array.isArray(lines) && lines.length) return lines.join(" · ")
			const parts = [
				"Fallback board",
				"Historical snapshot only",
				"Not suitable for execution decisions",
				"Refresh required for decision use",
			]
			const date = t.as_of || this.today7.date || this.rankedOpps.snapshot_timestamp
			if (date) parts.push("Source snapshot · " + String(date).slice(0, 10))
			return parts.join(" · ")
		},
		dashboardBestActionLabel(kind) {
			const deploy =
				!!this.today7?.todays_decision?.can_deploy_today &&
				!this.isWaitDay() &&
				!this.todayDeployAuthoritySuspended() &&
				!this.pageAuthorityIsDegraded()
			if (kind === "trade") return deploy ? this._uiText("Best deploy") : this._uiText("Top candidate")
			if (kind === "action") return deploy ? this._uiText("Best trade") : this._uiText("Top monitor")
			if (kind === "watch") return this._uiText("Top monitor")
			if (kind === "pilot") return this._uiText("Top promotion")
			return deploy ? "TRADE" : this._uiText("Monitor")
		},
		dashboardPlaybookCtaLabel() {
			if (
				this.isWaitDay() ||
				!this.today7?.todays_decision?.can_deploy_today ||
				this.todayDeployAuthoritySuspended()
			) {
				return "去 Playbook 複核 monitor ranking"
			}
			return "去 Playbook 打開 deploy-qualified board"
		},
		discoveryWaitZeroHits() {
			return (
				(this.isWaitDay() || this.canonicalTradeability() === "WAIT") &&
				String(this.scannerTotalHits()) === "0" &&
				!this.scannerDiscoveryHasFallbackRows() &&
				!this.scannerHub.loading
			)
		},
		discoveryWaitEmptyLine() {
			return this._uiText("Often correct on WAIT — monitor funnel, not deploy.")
		},
		dossierLevelsIndicativeOnly() {
			return this.dossierResearchOnly()
		},
		dossierActionsBlocked() {
			return this.dossierResearchOnly() || this.dossierSizingBlocked()
		},
		dossierActionsBlockedTitle() {
			if (this.dossierSizingBlockedReason() === "confirm_only") return "Confirm-only — no IBKR handoff or sizing"
			if (this.dossierSizingBlockedReason() === "partial" || this.dossierSizingBlockedReason() === "failed")
				return "Research incomplete — actions blocked"
			return "Decision-grade research required before handoff"
		},
		dossierRrUnavailable() {
			const rr = this.dosUnified().rr_ratio_display || this.dosUnified().rr_ratio
			if (rr == null || rr === "" || rr === "—") return true
			return this.parseRR(rr) <= 0
		},
		dossierSizingBlocked() {
			const intel = this.dos?.intel
			if (intel?.sizing_blocked || intel?.size_info?.sizing_blocked) return true
			if (this.dossierResearchOnly()) return true
			if (this.dossierRrUnavailable()) return true
			const confLine = String(this.dosFormatDecisionConfidence() || intel?.confidence_label || "").toLowerCase()
			if (confLine.includes("pending calibration")) return true
			return false
		},
		dossierSizingBlockedReason() {
			const hints = this.surfaceFetchHints?.dossier || {}
			if (this.dos.status === "failed" || hints.failed_fetch) return "failed"
			const intel = this.dos?.intel
			const label = String(this.dosUnified().label || this.dos?.intel?.decision_bar?.verdict || "").toUpperCase()
			if (["CONFIRM ONLY", "RESEARCH ONLY", "REFERENCE ONLY"].includes(label)) return "confirm_only"
			const confLine = String(this.dosFormatDecisionConfidence() || intel?.confidence_label || "").toLowerCase()
			if (confLine.includes("pending calibration")) return "confirm_only"
			if (
				intel?.load_phase === "core" ||
				intel?.partial ||
				this._dossierIntelDegraded(intel) ||
				this.dos.status === "partial_loaded"
			)
				return "partial"
			if (this.dossierRrUnavailable()) return "rr_unavailable"
			return "blocked"
		},
		dosQuoteAvailable() {
			const d = this.dos?.data
			if (window.CCHelpers && CCHelpers.dossierQuoteAvailable) return CCHelpers.dossierQuoteAvailable(d)
			if (!d || d.quote_pending || d.quote_unavailable) return false
			const p = Number(d.price)
			return !isNaN(p) && p > 0
		},
		dosPriceDisplay() {
			const d = this.dos?.data
			if (window.CCHelpers && CCHelpers.dossierPriceDisplay) return CCHelpers.dossierPriceDisplay(d)
			return this.dosQuoteAvailable() ? "$" + Number(d.price).toFixed(2) : "Quote unavailable"
		},
		dosChangePctDisplay() {
			const d = this.dos?.data
			if (window.CCHelpers && CCHelpers.dossierChangePctDisplay) return CCHelpers.dossierChangePctDisplay(d)
			if (!this.dosQuoteAvailable()) return "—"
			const c = Number(d.change_pct)
			if (isNaN(c)) return "—"
			return (c >= 0 ? "+" : "") + c.toFixed(2) + "%"
		},
		dosQuoteToneClass() {
			if (!this.dosQuoteAvailable()) return "text-amber-300"
			return (this.dos?.data?.change_pct || 0) >= 0 ? "text-green-400" : "text-red-400"
		},
		dosSizeDisplay() {
			if (this.dossierSizingBlocked()) {
				const r = this.dossierSizingBlockedReason()
				if (window.CCHelpers && CCHelpers.dossierSizingDisplay) return CCHelpers.dossierSizingDisplay(true, r)
				if (r === "confirm_only") return "—"
				if (r === "failed" || r === "partial") return "Blocked"
				return "—"
			}
			const sh = this.dosSizeShares()
			return sh > 0 ? sh + " sh" : "Size unavailable"
		},
		dosSizeExplanationVisible() {
			const ex = this.dosSizeExplanation()
			if (!ex) return false
			return ex !== this.dosSizeDisplay()
		},
		ibkrNeedsConnectCta() {
			const st = this.ibkrStateFrom(this.ibkr.readiness || this.today7.execution_readiness || {})
			return !!(st.gw && !st.connected)
		},
		isDeployGrade(opp) {
			const act = String(this.effectiveCardAction(opp) || "").toUpperCase()
			return ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(act)
		},
		marketStripStaleVisible() {
			if (this.marketStripStaleDowngrade()) return true
			const tier = String(this.freshness?.worst_tier || "").toUpperCase()
			const t = this.today7.trust || {}
			return !!(t.stale || tier === "STALE" || tier === "CRITICAL" || this.staleSnapshotContext())
		},
		dossierResearchOnly() {
			if (this.dos.loading || this.dos.status === "loading_core" || this.dos.status === "loading_enrichments")
				return false
			if (this.dos.status === "failed" || this.dos.status === "stale_fallback") return true
			const intel = this.dos?.intel
			if (intel?.research_only || intel?.partial || intel?.load_phase === "core") return true
			if (intel && this._dossierIntelDegraded(intel)) return true
			if (this.dos.status === "partial_loaded") return true
			if (this.surfaceFetchHints?.dossier?.failed_fetch) return true
			const label = String(this.dosUnified().label || this.dos?.intel?.decision_bar?.verdict || "").toUpperCase()
			if (["RESEARCH ONLY", "CONFIRM ONLY", "REFERENCE ONLY", "WATCH ONLY", "PASS"].includes(label)) return true
			const confLine = String(this.dosFormatDecisionConfidence() || intel?.confidence_label || "").toLowerCase()
			if (confLine.includes("pending calibration")) return true
			if (this.dossierRrUnavailable()) return true
			return false
		},
		dosShowsDeployLevels() {
			return !this.dossierResearchOnly()
		},
		dosLevelColumnLabel(field) {
			if (!this.dossierResearchOnly())
				return field === "entry"
					? "Entry zone"
					: field === "stop"
						? "Stop"
						: field === "target"
							? "T1 / T2"
							: field === "size"
								? "Size @1%"
								: "R:R"
			if (field === "entry") return "Indicative entry"
			if (field === "stop") return "Monitor zone"
			if (field === "target") return "Indicative target"
			if (field === "size") return "Sizing"
			return "Indicative R:R"
		},
		dosDashboardReminderLine() {
			if (!this.dossierResearchOnly()) return ""
			return "Research-only 結論 · sizing 或 IBKR handoff 前，先去 Dashboard 確認 board gate。"
		},
		btLabHonestMetric(label, val) {
			return this.btLabMetricDisplay(label, val)
		},
		btLabHonestStabilityScore() {
			if (this.btLabMetricsPending()) return "pending"
			const s = this.btLab.data?.walk_forward?.stability_score
			if (s == null || s === "" || Number.isNaN(Number(s))) return "pending"
			return s
		},
		cardIsFallbackRow(opp) {
			if (!opp) return false
			if (
				opp.card_display_mode === "reference_only" ||
				opp.levels_indicative_only ||
				opp.confidence_fallback_only ||
				opp.deploy_authority === false
			)
				return true
			if (this.todayUsesBriefFallback() || this.playbookUsesBriefFallback()) return true
			const eb = String(opp.evidence_badge || "").toLowerCase()
			return eb.includes("brief") || eb.includes("fallback") || eb.includes("stale-brief")
		},
		cardShowsDeployLevels(opp) {
			if (this.cardIsFallbackRow(opp) || this.pageAuthorityIsDegraded() || this.playbookBoardWait()) return false
			const g = String(this.cardExecutionGrade(opp) || "").toUpperCase()
			return ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(g)
		},
		cardShowsExecutableSizing(opp) {
			if (!opp || !opp.entry_price || !opp.stop_price || opp.entry_price <= opp.stop_price) return false
			if (this.pageAuthorityIsDegraded() || this.todayUsesBriefFallback() || this.cardIsFallbackRow(opp))
				return false
			const g = String(this.cardExecutionGrade(opp) || "").toUpperCase()
			return ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(g)
		},
		cardSizingPct(opp) {
			if (!this.cardShowsExecutableSizing(opp)) return ""
			return (
				Math.min(
					10,
					Math.max(0.1, (0.01 / (Math.abs(opp.entry_price - opp.stop_price) / opp.entry_price)) * 100),
				).toFixed(1) + "%"
			)
		},
		cardSizingNote(opp) {
			if (!opp) return ""
			if (this.pageAuthorityIsDegraded() || this.todayUsesBriefFallback() || this.cardIsFallbackRow(opp))
				return "Sizing suspended in fallback mode"
			if (
				opp.entry_price &&
				opp.stop_price &&
				opp.entry_price > opp.stop_price &&
				!this.cardShowsExecutableSizing(opp)
			)
				return "Indicative sizing only"
			return ""
		},
		cardReferenceBanner(opp) {
			if (
				this.pageAuthorityIsDegraded() ||
				this.isWaitDay() ||
				this.playbookBoardWait() ||
				this.cardIsFallbackRow(opp) ||
				!this.today7.todays_decision?.can_deploy_today
			)
				return "只可監察 · monitor only — 未開 deploy authority"
			return ""
		},
		cardExecutionGrade(opp) {
			if (!opp) return "—"
			const raw = String(opp.raw_action || opp.action || "WATCH").toUpperCase()
			const da = this.decisionAuthority()
			const tb = String(this.canonicalTradeability() || "").toUpperCase()
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			const gates = {
				regime_wait: tb === "WAIT" || tb === "NO_TRADE",
				engine_off: es === "ENGINE_OFF" || !this.ops?.running,
				data_stale:
					!!(
						this.ccFreshnessState().worst_tier &&
						["STALE", "CRITICAL"].includes(this.ccFreshnessState().worst_tier)
					) || !!(this.today7.trust?.stale || da.gates?.data_stale),
				broker_offline:
					["GATEWAY_DOWN", "IBAPI_MISSING", "SESSION_INACTIVE"].includes(es) || this.dashboardBrokerOffline(),
				exec_blocked: es === "EXEC_BLOCKED" || !!(this.cc_status?.breaker || da.gates?.exec_blocked),
				handoff_blocked: es === "HANDOFF_BLOCKED",
				fallback_brief:
					this.todayUsesBriefFallback() || da.source === "fallback_brief" || !!da.gates?.fallback_brief,
				scanner_loading: !!da.gates?.scanner_loading,
			}
			const gatesActive = Object.values(gates).some(Boolean) || !!da.gates_active || !!da.degraded
			const tradeActions = ["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"]
			const rr = opp.risk_reward
			const rrOk = rr != null && rr !== "" && rr !== "—" && Number(this.parseRR(rr) || 0) > 0
			if (tradeActions.includes(raw)) {
				if (gates.fallback_brief || opp.card_display_mode === "reference_only") return "FALLBACK WATCH"
				if (gates.exec_blocked || gates.broker_offline || gates.engine_off) return "BLOCKED"
				if (gates.handoff_blocked) return "HANDOFF BLOCKED"
				if (!rrOk) return "INCOMPLETE"
				if (gatesActive || !da.allows_trade_labels) {
					if (da.source === "stale_cache" || gates.data_stale) return "REFERENCE ONLY"
					if (gates.regime_wait || gates.data_stale || gates.scanner_loading) return "WATCH ONLY"
					if (da.authority_level === "suspended") return "NOT EXECUTION-GRADE"
					return "RESEARCH ONLY"
				}
				if (!opp.execution_ready) return "WATCH ONLY"
			}
			const srv = String(opp.effective_grade || opp.effective_action || "").toUpperCase()
			if ((opp.effective_grade || opp.effective_action) && srv && srv !== raw)
				return opp.effective_grade || opp.effective_action
			if (gates.fallback_brief && tradeActions.includes(raw)) return "FALLBACK WATCH"
			if (raw === "PILOT" && (gatesActive || this.playbookBoardWait() || !da.allows_trade_labels))
				return "PILOT (MONITOR)"
			return opp.effective_action || opp.action || "—"
		},
		effectiveCardAction(opp) {
			return this.cardExecutionGrade(opp)
		},
		cardActionDisplay(opp) {
			const a = String(this.effectiveCardAction(opp) || "").toUpperCase()
			if (a !== "PILOT") return this.effectiveCardAction(opp)
			const ps = String(opp?.pilot_state || "").toUpperCase()
			if (ps === "PILOT_RESEARCH_ONLY") return "PILOT (RESEARCH)"
			return "PILOT"
		},
		effectiveCardActionClass(opp) {
			const a = String(this.effectiveCardAction(opp) || "").toUpperCase()
			if (["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].includes(a)) return "pg"
			if (["BLOCKED", "AVOID", "NO_TRADE"].includes(a)) return "pr"
			if (
				[
					"FALLBACK CANDIDATE",
					"FALLBACK WATCH",
					"INCOMPLETE",
					"NOT EXECUTION-GRADE",
					"RESEARCH ONLY",
					"REFERENCE ONLY",
					"WATCH ONLY",
				].includes(a)
			)
				return "pa"
			if (a === "PILOT") return "pb"
			return "pa"
		},
		cardActionDisplayClass(opp) {
			const a = String(this.cardActionDisplay(opp) || "").toUpperCase()
			if (a.startsWith("PILOT (")) return "pa"
			if (a === "PILOT") return "pb"
			return this.effectiveCardActionClass(opp)
		},
		confidenceFinal(opp) {
			const cb = opp?.confidence_breakdown
			if (opp?.confidence_unavailable || (cb && cb.unavailable)) return null
			const comps = [
				cb?.thesis ?? opp?.thesis_conf ?? 0,
				cb?.timing ?? opp?.timing_conf ?? 0,
				cb?.execution ?? opp?.exec_conf ?? 0,
				cb?.data ?? opp?.data_conf ?? 0,
			]
			const present = comps.filter((v) => Number(v) > 0)
			if (!present.length) return null
			const v = cb?.final ?? opp?.final_conf
			if (v == null || v === "") return null
			return Number(v)
		},
		confidenceFinalLabel(opp) {
			const v = this.confidenceFinal(opp)
			if (v == null || Number.isNaN(v))
				return this.confidenceIsFallback(opp)
					? ""
					: opp?.confidence_fallback_only || this.cardIsFallbackRow(opp)
						? "Fallback only"
						: "Unavailable"
			const pct = v <= 1 ? Math.round(v * 100) : Math.round(v)
			return pct + "%"
		},
		confidenceIsFallback(opp) {
			if (!opp) return false
			if (opp.confidence_fallback_only || opp.confidence_label) return true
			if (this.confidenceFinal(opp) != null && !Number.isNaN(this.confidenceFinal(opp))) return false
			return this.cardIsFallbackRow(opp)
		},
		confidenceBannerLine(opp) {
			const label = opp?.confidence_label || "Fallback estimate — non-comparable"
			return "4D Confidence: " + label
		},
		confidenceComponents(opp) {
			const cb = opp?.confidence_breakdown || {}
			if (this.confidenceFinal(opp) == null && (opp?.confidence_unavailable || this.cardIsFallbackRow(opp))) {
				return [
					["Thesis", null],
					["Timing", null],
					["Exec", null],
					["Data", null],
				]
			}
			return [
				["Thesis", cb.thesis ?? opp?.thesis_conf ?? 0],
				["Timing", cb.timing ?? opp?.timing_conf ?? 0],
				["Exec", cb.execution ?? opp?.exec_conf ?? 0],
				["Data", cb.data ?? opp?.data_conf ?? 0],
			]
		},
		topRankedIsTrade() {
			if (this.pageAuthorityIsDegraded() || this.todayUsesBriefFallback()) return false
			const da = this.decisionAuthority()
			if (da.gates_active || da.authority_level === "suspended" || !da.allows_trade_labels) return false
			const r = (this.today7.top_ranked || [])[0]
			if (!r || this.cardIsFallbackRow(r)) return false
			const act = String(this.effectiveCardAction(r) || "").toUpperCase()
			return !!(r.execution_ready && ["TRADE", "BUY", "BUY_ON_DIP"].includes(act))
		},
		topRankedHeroLabel() {
			const td = this.today7.todays_decision
			if (
				td &&
				td.hero_label &&
				!(this.pageAuthorityIsDegraded() || this.isWaitDay() || this.todayUsesBriefFallback())
			)
				return td.hero_label
			if (
				this.pageAuthorityIsDegraded() ||
				this.isWaitDay() ||
				this.todayUsesBriefFallback() ||
				this.playbookBoardWait()
			)
				return "#1 監察候選 · monitor candidate"
			const r = (this.today7.top_ranked || [])[0]
			if (!r) return ""
			const act = String(this.effectiveCardAction(r) || "").toUpperCase()
			if (this.topRankedIsTrade()) return "#1 部署候選 · deploy candidate"
			if (act === "PILOT" || act === "WATCH" || act === "WATCH ONLY") return "#1 監察候選 · monitor candidate"
			return "#1 監察候選 · monitor candidate"
		},
		dashboardOperatorNowLine() {
			const td = this.today7.todays_decision
			if (this.pageAuthorityIsDegraded())
				return "Now · " + (this.canonicalTradeability() || "WAIT") + " · 只可 Monitor"
			if (td?.can_deploy_today) return "Now · " + (this.canonicalTradeability() || "—") + " · 可部署"
			return "Now · " + (this.canonicalTradeability() || "WAIT") + " · 只作排序複核"
		},
		dashboardOperatorBlockerLine() {
			return this.primaryBlockerLine()
		},
		dashboardOperatorNextActionLine() {
			if (this.pageAuthorityIsDegraded())
				return "下一步 · 先修 broker / runtime / board blocker，再回 Dashboard / Playbook 複核。"
			const td = this.today7.todays_decision
			if (td?.can_deploy_today) return "下一步 · 只檢查 deploy-qualified setup，唔好讓 card rank 越過 page gate。"
			return "下一步 · 先睇 top monitor candidates，再去 Playbook 做 ranking review。"
		},
		playbookOperatorNowLine() {
			if (this.pageAuthorityIsDegraded() || this.playbookBoardWait())
				return "Now · " + (this.canonicalTradeability() || "WAIT") + " · 只可 Monitor"
			return "Now · " + (this.canonicalTradeability() || "—") + " · 只作排序複核"
		},
		playbookOperatorBlockerLine() {
			return this.primaryBlockerLine()
		},
		playbookOperatorNextActionLine() {
			if (this.pageAuthorityIsDegraded() || this.playbookBoardWait()) return this.playbookWhatToMonitorLine()
			return "下一步 · 只複核 top ranked names；broker、board、execution 三者全部放行前唔好當成 execution。"
		},
		dayStateLabel() {
			const ds = (this.today7.todays_decision && this.today7.todays_decision.day_state) || ""
			if (ds === "A_GRADE_TRADE_DAY") return "A 級部署日 · A-grade trade day"
			if (ds === "TRADE_DAY") return "部署日 · Trade day"
			if (ds === "PILOT_WATCH_DAY") return "觀察日 · Monitor day"
			if (ds === "NO_TRADE_DAY") return "停手日 · No-trade day"
			const tb = (this.today7.tradeability || "").replace(/_/g, " ")
			return tb || "—"
		},
		ibkrStateFrom(ex, cc) {
			const exObj = ex || {}
			const ccObj = cc || this.cc_status || {}
			const diag = exObj.diagnosis || this.ibkr.diagnosis || {}
			if (diag.short && diag.label)
				return {
					short: diag.short,
					label: diag.label,
					level:
						diag.short === "READY"
							? "ready"
							: diag.short === "OFFLINE" || diag.short === "NO IBAPI"
								? "offline"
								: "partial",
					sub: exObj.sub_status || {},
					connected: !!(
						exObj.session_usable ||
						exObj.broker_connected ||
						exObj.ibkr_connected ||
						this.ibkr.session_usable
					),
					gw: !!(exObj.gateway_reachable || diag.gateway_reachable || ccObj.ibkr_gateway),
					handoff: !!exObj.trade_handoff_ready,
					monitoring: !!(exObj.monitoring_only || this.ibkr.monitoring_only),
					health: exObj.health || this.ibkr.health || {},
					hint: diag.hint || "",
				}
			if (exObj.unified_short)
				return {
					short: exObj.unified_short,
					label: exObj.unified_label || exObj.health_label || exObj.unified_short,
					level: exObj.level || "partial",
					sub: exObj.sub_status || {},
					connected: !!(exObj.session_usable || exObj.broker_connected || exObj.ibkr_connected),
					gw: !!exObj.gateway_reachable,
					handoff: !!exObj.trade_handoff_ready,
					monitoring: !!exObj.monitoring_only,
					health: exObj.health || {},
				}
			const gw =
				exObj.gateway_reachable != null
					? !!exObj.gateway_reachable
					: !!(ccObj.ibkr_gateway || this.ibkr.gateway_reachable)
			const connected = !!(
				exObj.session_usable ||
				exObj.broker_connected ||
				exObj.ibkr_connected ||
				ccObj.ibkr_connected
			)
			const monitoring = !!(exObj.monitoring_only || ccObj.ibkr_monitoring)
			const mode = String(exObj.mode || exObj.paper_or_live || ccObj.ibkr_mode || "paper").toLowerCase()
			const bracket = !!(exObj.bracket_order_ready || exObj.bracket_ready)
			const handoff = !!(exObj.trade_handoff_ready || (connected && bracket && !monitoring))
			const engine = exObj.engine_running != null ? !!exObj.engine_running : this.ops?.running && !ccObj.breaker
			const breaker = !!(exObj.circuit_breaker || ccObj.breaker)
			const healthLabel = exObj.health_label || ccObj.ibkr_health_label || ""
			let short = "OFFLINE",
				label = "BROKER OFFLINE",
				level = "offline"
			if (breaker) {
				short = "BLOCKED"
				label = "CIRCUIT BREAKER"
				level = "blocked"
			} else if (handoff) {
				short = mode.toUpperCase()
				label = mode.toUpperCase() + " · HANDOFF READY"
				level = "ready"
			} else if (connected && monitoring) {
				short = "MONITOR"
				label = healthLabel || mode.toUpperCase() + " · MONITOR / MANUAL"
				level = "partial"
			} else if (connected) {
				short = "PARTIAL"
				label = healthLabel || mode.toUpperCase() + " · PARTIALLY READY"
				level = "partial"
			} else if (gw) {
				short = "LOGIN"
				label = "GATEWAY UP · LOGIN REQUIRED"
				level = "partial"
			}
			return {
				short,
				label,
				level,
				sub: {
					broker_transport: gw ? "up" : "down",
					session_auth: connected ? "active" : "inactive",
					engine: engine ? "on" : "off",
					handoff_readiness: handoff ? "ready" : connected ? "monitoring" : "blocked",
					bracket_readiness: bracket ? "ready" : "draft",
				},
				connected,
				gw,
				handoff,
				monitoring,
				health: exObj.health || {},
			}
		},
		ibkrPillStyle() {
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			const mode = (this.cc_status.ibkr_mode || "paper").toLowerCase()
			if (st.level === "blocked") return "background:#7f1d1d;color:#fca5a5;border:1px solid #ef4444"
			if (st.level === "ready")
				return mode === "live"
					? "background:#7f1d1d;color:#fca5a5;border:1px solid #ef4444"
					: "background:#1e3a5f;color:#93c5fd;border:1px solid #3b82f6"
			if (st.connected || st.monitoring) return "background:#422006;color:#fde68a;border:1px solid #f59e0b"
			if (st.gw) return "background:#422006;color:#fde68a;border:1px solid #f59e0b"
			return "background:#3f3f46;color:#a1a1aa;border:1px solid #52525b"
		},
		ibkrPillDotStyle() {
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			const mode = (this.cc_status.ibkr_mode || "paper").toLowerCase()
			if (st.level === "ready") return mode === "live" ? "background:#ef4444" : "background:#3b82f6"
			if (st.connected || st.monitoring || st.gw) return "background:#f59e0b"
			return "background:#71717a"
		},
		ibkrTrustStripLabel() {
			const op = this.ibkr.readiness?.operating
			if (op && op.badge) return op.badge + " · " + this.ibkr.mode.toUpperCase()
			if (this.ibkr.health_label) return this.ibkr.health_label
			if (this.ibkr.health && this.ibkr.health.summary_label) return this.ibkr.health.summary_label
			if (this.ibkr.session_usable || this.ibkr.connected) return "MONITOR · " + this.ibkr.mode.toUpperCase()
			if (this.ibkr.diagnostics && this.ibkr.diagnostics.health && this.ibkr.diagnostics.health.summary_label)
				return this.ibkr.diagnostics.health.summary_label
			const st = this.ibkrStateFrom(this.today7.execution_readiness || {})
			if (st.gw && !st.connected) return st.label || "GATEWAY UP · LOGIN REQUIRED"
			if (st.short && st.short !== "OFFLINE") return st.label || st.short
			return "DISCONNECTED"
		},
		ibkrTrustStripStyle() {
			if (this.ibkr.session_usable || this.ibkr.connected) {
				return this.ibkr.monitoring_only ? "color:var(--amber)" : "color:var(--green)"
			}
			if (this.ibkr.health && this.ibkr.health.account_status === "ok") return "color:var(--amber)"
			return "color:var(--red)"
		},
		ibkrMaskAccount(id) {
			const s = String(id || "").trim()
			if (!s || s === "—") return "—"
			if (s.length <= 4) return s + "*"
			return s.slice(0, Math.min(7, s.length)) + "*"
		},
		ibkrAccountLoadedLabel() {
			const acct = this.ibkr.diagnostics?.account_id || this.ibkr.account?.account || ""
			const loaded =
				!!(this.ibkr.readiness?.critical_rows || []).find((r) => r.key === "account" && r.state === "ready") ||
				this.ibkr.health?.account_status === "ok"
			if (loaded && acct) return "Account loaded: " + this.ibkrMaskAccount(acct)
			if (loaded) return "Account loaded"
			return "Account — not loaded"
		},
		ibkrPageOperating() {
			return this.ibkr.readiness?.operating || {}
		},
		ibkrPageBadge() {
			const op = this.ibkrPageOperating()
			if (op.badge) return op.badge
			if (this.ibkr.readiness?.full_handoff_ready) return "HANDOFF READY"
			if (this.ibkr.session_usable || this.ibkr.connected) return "MONITOR"
			return "OFFLINE"
		},
		ibkrPageBadgeClass() {
			const b = this.ibkrPageBadge()
			if (b === "HANDOFF READY") return "pg"
			if (b === "OFFLINE") return "pr"
			return "pa"
		},
		ibkrPageBannerShort() {
			const op = this.ibkrPageOperating()
			if (op.short_comment && this.ibkr.connected) return op.short_comment
			if (this.ibkr.diagnosis && this.ibkr.diagnosis.label) return this.ibkr.diagnosis.label
			if (this.ibkr.health_label) return this.ibkr.health_label
			return "Broker status loading…"
		},
		ibkrPageBannerFull() {
			const op = this.ibkrPageOperating()
			return op.full_comment || ""
		},
		ibkrPageModeLabel() {
			return this.ibkrPageOperating().mode_label || "—"
		},
		ibkrCriticalRows() {
			return (
				this.ibkr.readiness?.critical_rows ||
				(this.ibkr.readiness?.rows || []).filter((r) => r.category === "critical")
			)
		},
		ibkrWorkflowRows() {
			return (
				this.ibkr.readiness?.workflow_rows ||
				(this.ibkr.readiness?.rows || []).filter((r) => r.category === "workflow")
			)
		},
		ibkrFarmRows() {
			return (
				this.ibkr.readiness?.farm_rows || (this.ibkr.readiness?.rows || []).filter((r) => r.category === "farm")
			)
		},
		ibkrReadinessScore() {
			const r = this.ibkr.readiness || {}
			const ready = r.ready_count || 0
			const total = r.total || 8
			return ready + "/" + total
		},
		ibkrReadinessWeightNote() {
			const r = this.ibkr.readiness || {}
			if (r.critical_ok && !r.workflow_ok) {
				return "Important: not all checks carry equal weight. Core connectivity is healthy, but workflow-critical items remain partial."
			}
			if (!r.critical_ok) {
				return "Important: not all checks carry equal weight. Critical connectivity gaps block execution authority even when workflow items pass."
			}
			if (r.full_handoff_ready) return "All critical and workflow gates satisfied."
			return "Important: not all checks carry equal weight. Review critical vs workflow sections separately."
		},
		ibkrRepairChecklist() {
			const diag = this.ibkr.diagnosis || {}
			const code = String(diag.code || "").toLowerCase()
			const host = String(this.ibkr.host || "127.0.0.1")
			const mode = String(this.ibkr.mode || "paper").toLowerCase()
			const port =
				Number((this.ibkr.diagnostics && this.ibkr.diagnostics.port) || (mode === "paper" ? 7497 : 4001)) || 0
			const sessionReady = !!(this.ibkr.session_usable || this.ibkr.connected)
			const gatewayReachable = !!(this.ibkr.gateway_reachable || this.ibkr.api_port_open || sessionReady)
			const accountReady =
				!!(this.ibkr.health && this.ibkr.health.account_status === "ok") ||
				this.ibkrAccountLoadedLabel().startsWith("Account loaded")
			const syncReady =
				String(this.ibkr.readiness?.portfolio_sync_status || "").toLowerCase() === "ready" &&
				!this.ibkrBookMismatch()
			const handoffReady = !!this.ibkr.readiness?.full_handoff_ready
			const bracketStatus = String(this.ibkr.readiness?.bracket_status || "").toLowerCase()
			const bracketReady = bracketStatus === "ready"
			const bracketPartial = bracketStatus === "partial" && sessionReady
			const bracketDetail =
				typeof CCHelpers !== "undefined" && CCHelpers.localizeIbkrBracketReason
					? CCHelpers.localizeIbkrBracketReason(this.ibkr.readiness?.bracket_reason)
					: this.ibkr.readiness?.bracket_reason || ""
			return [
				{
					key: "ibapi",
					label: "1. Install ibapi",
					done: code !== "ibapi_missing",
					detail: code === "ibapi_missing" ? "Server runtime 未裝 ibapi。" : "ibapi runtime 已可用。",
				},
				{
					key: "gateway",
					label: "2. Open Gateway / TWS",
					done: gatewayReachable,
					detail: gatewayReachable ? "Gateway / TWS socket 可達。" : "先啟動 IB Gateway 或 TWS。",
				},
				{
					key: "api",
					label: "3. Enable API",
					done: !!this.ibkr.api_port_open,
					detail: this.ibkr.api_port_open ? "API socket 已打開。" : "在 TWS / Gateway 啟用 Socket clients。",
				},
				{
					key: "host-port",
					label: "4. Check host / port",
					done: !["mode_port_mismatch", "wrong_host_docker", "api_port_unreachable"].includes(code),
					detail:
						"目前 " +
						host +
						":" +
						port +
						" · " +
						(code === "wrong_host_docker"
							? "Docker 請改用 host.docker.internal。"
							: code === "mode_port_mismatch"
								? "paper/live mode 與 port 唔一致。"
								: "host / port 設定可用。"),
				},
				{
					key: "session",
					label: "5. Connect session",
					done: sessionReady,
					detail: sessionReady ? "App session 已建立。" : "按 Connect，等待 nextValidId / session_usable。",
				},
				{
					key: "account",
					label: "6. Verify account read",
					done: accountReady,
					detail: accountReady ? this.ibkrAccountLoadedLabel() : "Account summary 尚未讀取完成。",
				},
				{
					key: "sync",
					label: "7. Verify positions / orders read",
					done: syncReady,
					detail: syncReady
						? "Broker positions / orders 已對齊。"
						: this.ibkrBookMismatch()
							? "Broker truth 與 local book 未對齊。"
							: "仍需刷新 positions / orders。",
				},
				{
					key: "handoff",
					label: "8. Bracket / handoff ready · 括號單／交付就緒",
					done: handoffReady && bracketReady,
					partial: bracketPartial && !handoffReady,
					detail:
						handoffReady && bracketReady
							? "Bracket 與 handoff 已就緒 · Bracket and handoff ready"
							: bracketDetail || "仍未達 bracket／handoff ready · Not yet bracket/handoff ready",
				},
			]
		},
		ibkrBracketReasonLine() {
			const raw = this.ibkr.readiness?.bracket_reason || ""
			if (typeof CCHelpers !== "undefined" && CCHelpers.localizeIbkrBracketReason)
				return CCHelpers.localizeIbkrBracketReason(raw) || "—"
			return raw || "—"
		},
		ibkrRepairPrimaryLine() {
			if (this.ibkr.readiness?.full_handoff_ready) return "IBKR 已到 handoff-ready。"
			if (this.ibkrPageBannerShort()) return this.ibkrPageBannerShort()
			return "IBKR 尚未 ready。"
		},
		ibkrRepairBlockerLine() {
			if (this.ibkr.diagnosis?.hint) return this.ibkr.diagnosis.hint
			if (this.ibkr.statusFetchError) return this.ibkr.statusFetchError
			return "目前仍有 broker / session / bracket gate 未通過。"
		},
		ibkrRepairNextActionLine() {
			const next = this.ibkrRepairChecklist().find((row) => !row.done)
			return next
				? "下一步 · " + next.label.replace(/^\d+\.\s*/, "") + "。"
				: "下一步 · 回到 Playbook / Dashboard 確認 authority 同 execution gates。"
		},
		ibkrBookMismatch() {
			return !!(this.ibkr.readiness?.book_mismatch || this.ibkr.readiness?.portfolio_sync_status === "mismatch")
		},
		ibkrPartialMode() {
			return !this.ibkr.readiness?.full_handoff_ready
		},
		ibkrOrderEntryGateActive() {
			return this.isWaitDay() && this.playbookDeployableCount() < 1 && this.ibkrBookMismatch()
		},
		ibkrUnifiedShort(ex) {
			return this.ibkrStateFrom(ex).short
		},
		ibkrUnifiedLabel(ex) {
			return this.ibkrStateFrom(ex).label
		},
		canonicalTradeability() {
			const cs = this.ccState()
			const tb0 = cs.tradeability_state?.tradeability
			if (tb0) return String(tb0).toUpperCase()
			const td = this.today7.todays_decision
			return String(
				this.today7.tradeability ||
					td?.regime?.tradeability ||
					this.today7.regime?.tradeability ||
					this.rankedOpps.bestAction?.tradeability ||
					"WAIT",
			).toUpperCase()
		},
		canonicalRegimeTrend() {
			const td = this.today7.todays_decision
			return String(this.today7.regime?.trend || td?.regime?.trend || "—").toUpperCase()
		},
		canonicalRegimeLine() {
			const trend = this.canonicalRegimeTrend()
			const tb = String(this.canonicalTradeability() || "—").replace(/_/g, " ")
			if (!trend || trend === "—") return tb
			return trend + " · " + tb
		},
		scannerRowAlignmentLine(m) {
			if (!m) return "—"
			const align = String(m.regime_alignment || "—").toUpperCase()
			const status = String(m.status || m.urgency || "monitor").replace(/_/g, " ")
			return align + " · " + status
		},
		discoveryVerdictConfirmedLabel() {
			const dv = this.scannerHub.data?.discovery_verdict || {}
			if (dv.best_confirmed_label) return dv.best_confirmed_label
			if (this.scannerDiscoveryHasFallbackRows()) return "Top fallback candidate"
			if (this.scannerUsesBriefFallback()) return "Top fallback candidate"
			return "Most represented scanner sample"
		},
		discoveryVerdictQualityLabel() {
			if (this.scannerDiscoveryHasFallbackRows()) return "FETCH FAILED · heuristic"
			const d = this.scannerHub.data || {}
			const hub = String(d.hub_status || "").toLowerCase()
			if (hub === "warming" || hub === "degraded") return "WARMING"
			return (d.scanner_quality && d.scanner_quality.label) || "Candidates for monitoring only"
		},
		scannerDiscoveryHasFallbackRows() {
			return !!(this.scannerHub.error && this.scannerHubIsRenderable(this.scannerHub.data))
		},
		scannerDiscoveryFetchHintLine() {
			// Keep fallback wording in the primary banner only.
			if (this.scannerDiscoveryHasFallbackRows()) return ""
			if (this.scannerHub.error && !this.scannerHub.data) return "即時掃描失敗 · Retry 或檢查 Ops"
			if (this.scannerUsesBriefFallback()) return "目前只顯示 fallback rows · 只可 Monitor"
			if (this.discoveryHeaderMode()) return "Discovery 屬 research-only · 只可 Monitor"
			return ""
		},
		discoveryFallbackBannerLine() {
			return "即時掃描失敗 · 目前顯示 fallback samples；Discovery 仍屬 research-only，先到 Playbook 確認。 Live fetch failed — showing fallback watchlist samples. Research-only fallback results — not live scanner output. Confirm in Playbook before sizing."
		},
		discoveryPrimaryHeadline() {
			const d = this.scannerHub.data || {}
			const uni = d.universe_size || d.diagnostics?.symbols_scanned || this.scannerHub.universe || 0
			const merged = (d.merged_top_names || []).length
			const deploy = this.discoveryVerdictDeployCount()
			if (this.scannerDiscoveryHasFallbackRows() || this.scannerHub.error) return "掃描即時資料暫不可用"
			if (d && d.diagnostics && d.diagnostics.reason_no_hits) return "目前無新的研究候選"
			if (d && (d.hub_status === "warming" || d.hub_status === "degraded")) return "掃描器暖機中"
			if (uni > 0)
				return (
					"Discovery 研究候選池 · " +
					uni +
					" scanned · " +
					merged +
					" merged" +
					(deploy === 0 ? " · deploy 0" : "")
				)
			return "Discovery 研究候選池"
		},
		discoveryVerdictDeployCount() {
			const v = (this.scannerHub.data || {}).discovery_verdict || {}
			if (v.deploy_qualified != null) return Number(v.deploy_qualified) || 0
			const f = this.rankedOpps.filter_funnel || {}
			return Number(f.deploy_qualified_setups ?? f.execution_ready_setups ?? 0) || 0
		},
		discoveryNearMissStripRows() {
			const d = this.scannerHub.data || {}
			if ((d.near_miss_strip || []).length) return d.near_miss_strip
			const merged = (d.merged_top_names || [])
				.filter((m) => String(m.action || "").toUpperCase() !== "TRADE")
				.slice(0, 8)
			return merged.map((m) => ({ ...m, monitor_label: "near_miss", research_only: true }))
		},
		discoveryNearMissStripVisible() {
			if (this.discoveryVerdictDeployCount() > 0) return false
			return this.discoveryNearMissStripRows().length > 0
		},
		discoveryPrimaryBlockerLine() {
			const d = this.scannerHub.data || {}
			if (this.scannerDiscoveryHasFallbackRows())
				return "即時掃描失敗 · 目前顯示 fallback samples；Discovery 仍屬 research-only，先到 Playbook 確認。"
			if (this.scannerHub.error && !d) return "即時掃描失敗 · 可 Retry，或先檢查 Ops。"
			if (d && d.diagnostics && d.diagnostics.reason_no_hits) return String(d.diagnostics.reason_no_hits)
			if (d && (d.hub_status === "warming" || d.hub_status === "degraded"))
				return "目前只有 cached / brief rows；Discovery 仍屬 research-only，待 Playbook 確認。"
			if (d.research_note) return d.research_note
			return "Discovery 屬 research-only；就算分數高，仍要經 Playbook 驗證 board 同 execution gates。"
		},
		discoveryPrimaryNextActionLine() {
			if (this.discoveryShowCachedLeaders())
				return "下一步 · 用 cached leaders 做 research；Playbook 驗證後才可 monitor upgrade。"
			if (this.scannerDiscoveryHasFallbackRows() || this.scannerHub.error)
				return "下一步 · Retry scanner；若仍失敗，先開 Playbook / Dashboard 驗證 board gate。"
			if (this.scannerHub.data?.diagnostics?.reason_no_hits)
				return "下一步 · 保持監察；WAIT / NO_TRADE 日出現零命中屬正常。"
			return "下一步 · 用 Playbook 驗證 blocker、upgrade trigger，同埋 execution readiness。"
		},
		scannerHubHeaderNote() {
			if (this.scannerDiscoveryHasFallbackRows()) {
				return (
					"Discovery 只係 scanner funnel。盤面 " +
					this.canonicalRegimeLine() +
					" · 下方 rows 係 fallback samples，唔係即時掃描輸出。"
				)
			}
			const d = this.scannerHub.data || {}
			if (d.research_note) return d.research_note
			return (
				"Discovery 只係 scanner funnel。盤面 " +
				this.canonicalRegimeLine() +
				" · WAIT / NO_TRADE 日出現零命中屬正常。"
			)
		},
		scannerDiscoveryEmptyMessage() {
			if (this.discoveryShowCachedLeaders())
				return "Live scan unavailable — cached leaders below (research only)."
			if (this.scannerDiscoveryHasFallbackRows())
				return "Fallback watchlist samples visible — see cached leaders."
			if (this.scannerHub.error)
				return (
					"Scanner hub could not load: " +
					this.scannerHub.error +
					". Retry or open Dashboard for board posture."
				)
			if (this.discoveryWaitZeroHits()) return this.discoveryWaitEmptyLine()
			return "Decision-intent scanners 仍屬 research-only；未經 Playbook 確認前只可 Monitor。WAIT 日零命中屬正常。"
		},
		discoveryPromotionPack(h) {
			const cs = this.ccState()
			const tb = String(
				cs.tradeability_state?.tradeability || this.canonicalTradeability() || "WAIT",
			).toUpperCase()
			const bs = String(cs.board_decision_state?.state || "").toUpperCase()
			const ex = this.executionState()
			const es = String(ex.state || "").toUpperCase()
			const missing = []
			if (tb === "NO_TRADE" || tb === "WAIT") missing.push("盤面 " + tb)
			if (bs !== "DEPLOY") missing.push("board deploy gate 未開")
			if (es === "EXEC_BLOCKED") missing.push("circuit breaker")
			if (es === "ENGINE_OFF") missing.push("engine off")
			if (["GATEWAY_DOWN", "IBAPI_MISSING", "SESSION_INACTIVE"].includes(es))
				missing.push("broker " + es.replace(/_/g, " ").toLowerCase())
			if (es === "HANDOFF_BLOCKED") missing.push("board handoff blocked")
			if (!missing.length) return { stage: "PLAYBOOK_REVIEW", headline: "可送去 Playbook 複核", missing: [] }
			return { stage: "BLOCKED", headline: "未能升級 — 目前只可 research-only", missing: missing.slice(0, 2) }
		},
		discoveryPromotionHeadline(h) {
			const p = this.discoveryPromotionPack(h)
			return p.headline
		},
		discoveryPromotionMissingLine(h) {
			const p = this.discoveryPromotionPack(h)
			return (p.missing || []).length ? "尚欠 · " + p.missing.join(" · ") : ""
		},
		playbookFunnelCounts(funnel, _rows) {
			const f = funnel || {}
			const scanned = f.universe_scanned ?? f.universe ?? 0
			let watch = f.watch_qualified_setups
			if (watch == null) watch = f.near_miss_setups ?? f.watch_setups ?? 0
			let deploy = f.deploy_qualified_setups
			if (deploy == null) deploy = f.execution_ready_setups ?? 0
			return { scanned: Number(scanned) || 0, watch: Number(watch) || 0, deploy: Number(deploy) || 0 }
		},
		playbookBoardScanPoolCount(funnel, rows) {
			const f = funnel || {}
			const { watch, scanned } = this.playbookFunnelCounts(f, rows)
			const rowN = (rows || []).length
			const wq = Number(watch) || 0
			if (wq > 0) return rowN > wq ? rowN : 0
			for (const k of ["triggered_setups", "high_score_setups", "raw_signal_candidates"]) {
				const n = Number(f[k]) || 0
				if (n > 0) return n
			}
			if (rowN > 0) return rowN
			return Number(scanned) || 0
		},
		playbookFunnelLabel(funnel, rows) {
			const { scanned, watch, deploy } = this.playbookFunnelCounts(funnel, rows)
			let s = scanned + " scanned · " + watch + " funnel watch-qualified · " + deploy + " deploy-qualified"
			const pool = this.playbookBoardScanPoolCount(funnel, rows)
			if (Number(watch) > 0 && pool > Number(watch)) s += " · " + pool + " board scan pool"
			return this._uiText(s)
		},
		playbookLayerDefinitions() {
			const defs = {
				scanned: "Scanned — universe evaluated by the scan pipeline.",
				watch_qualified: "Watch-qualified — met the monitor bar / near-miss pool; not deploy-ready.",
				deploy_qualified: "Deploy-qualified — execution-ready (timing, R:R, handoff).",
				near_miss: "Near-miss — upgrade layer: closest monitor upgrade; not deploy-ready.",
				monitor_ranking: "Monitor ranking — relative scan priority on WAIT days; rank ≠ deploy permission.",
			}
			const out = {}
			Object.keys(defs).forEach((k) => {
				out[k] = this._uiText(defs[k])
			})
			return out
		},
		playbookLayerDefinitionsNote() {
			return this._uiText(
				"Scanned = universe evaluated · Watch-qualified = monitor / near-miss pool · Deploy-qualified = execution-ready · Near-miss = upgrade layer (not deploy) · Monitor ranking = priority only, not permission.",
			)
		},
		playbookUnlockConditionDetail(c) {
			const raw = String((c && c.detail) || "")
			if (!raw) return ""
			if (c && c.key === "board") {
				const funnel = this.rankedOpps.filter_funnel || this.today7.filter_funnel
				const { watch } = this.playbookFunnelCounts(funnel, null)
				const wq = Number(watch) || 0
				const stale = raw.includes("STALE") ? " · data STALE" : ""
				const rows = this.rankedOpps.rows || null
				if (wq > 0) {
					const pool = this.playbookBoardScanPoolCount(funnel, rows)
					if (pool > wq) return wq + " funnel watch-qualified · " + pool + " board scan pool" + stale
					return wq + " funnel watch-qualified" + stale
				}
				const sr = this.playbookBoardScanPoolCount(funnel, rows)
				if (sr >= 1) return sr + " scan-ranked (not watch-qualified)" + stale
				return "0 watch-qualified" + stale
			}
			return raw
				.replace(/\b(\d+)\s+validated\b/gi, (m, n) => n + " scan-ranked (not watch-qualified)")
				.replace(/\bboard-ranked\s*\(watch-qualified\)/gi, "watch-qualified")
				.replace(/\bvalidated\b/gi, "scan-ranked")
		},
		playbookClosestUpgradeLabel() {
			if (this.playbookBoardWait() || this.playbookBrokerOffline() || this.playbookDeployQualifiedCount() < 1) {
				return this._uiText("Closest monitor upgrade")
			}
			return this._uiText("Closest to upgrade")
		},
		playbookDeployQualifiedCount() {
			const { deploy } = this.playbookFunnelCounts(
				this.rankedOpps.filter_funnel || this.today7.filter_funnel,
				null,
			)
			return deploy
		},
		playbookRejectionClustersNote() {
			const note = this.rankedOpps.rejection_clusters_note || ""
			if (note) return note
			const clusters = this.rankedOpps.rejection_clusters || []
			const filtered = Number((this.rankedOpps.avoid_grouped || {}).total) || 0
			if (!clusters.length || !filtered) return ""
			const sum = clusters.reduce((a, c) => a + (Number(c.count) || 0), 0)
			if (sum === filtered) return ""
			return (
				"Cluster counts (" +
				sum +
				") group by blocker theme; " +
				filtered +
				" names in the filtered list — themes can overlap."
			)
		},
		dashboardUnlockDeployIntro() {
			return this._uiText(
				"Unlock deploy requires all 4 conditions together: tradeability SELECTIVE+, ≥1 deploy-qualified setup, live broker handoff, and ≥1 watch-qualified name on fresh data (scan-ranked alone does not qualify).",
			)
		},
		honestFunnelLabel(funnel, rows) {
			return this.playbookFunnelLabel(funnel, rows)
		},
		todayDeployAuthoritySuspended() {
			const da = this.decisionAuthority()
			if (this.pageAuthorityIsDegraded() || this.todayUsesBriefFallback()) return true
			if (da.authority_level === "suspended" || da.gates_active) return true
			const src = String(da.source || "").toLowerCase()
			if (src && src !== "live") return true
			return false
		},
		kpiDeployQualifiedLabel() {
			return this._uiText("deploy-qualified")
		},
		kpiDeployQualifiedCount() {
			const { deploy } = this.playbookFunnelCounts(this.today7.filter_funnel, null)
			return deploy
		},
		kpiDeployQualifiedHint() {
			const nm = (this.today7.near_miss || []).length
			if (this.todayDeployAuthoritySuspended())
				return nm ? this._uiText(nm + " near-miss monitor") : this._uiText("monitor-only pipeline")
			return nm ? this._uiText(nm + " near-miss") : this._uiText("0 near-miss")
		},
		kpiDeployQualifiedTitle() {
			if (this.todayDeployAuthoritySuspended())
				return this._uiText(
					"Deploy-qualified count — authority suspended; watch-qualified names are in the middle KPI",
				)
			return this._uiText("Deploy-qualified setups in top board")
		},
		kpiWatchQualifiedLabel() {
			return this._uiText("watch-qualified")
		},
		kpiWatchQualifiedCount() {
			const { watch } = this.playbookFunnelCounts(this.today7.filter_funnel, null)
			return watch
		},
		kpiWatchQualifiedHint() {
			const nm = (this.today7.near_miss || []).length
			const { watch } = this.playbookFunnelCounts(this.today7.filter_funnel, null)
			if (watch || !nm) return ""
			return this._uiText(nm + " near-miss (not watch-qualified)")
		},
		kpiWatchQualifiedTitle() {
			return this._uiText(
				"Watch-qualified — council monitor bar from filter_funnel (same as Playbook strip). Near-miss rows are a separate upgrade layer.",
			)
		},
		kpiScannedLabel() {
			return this._uiText("scanned")
		},
		kpiScannedTitle() {
			return this._uiText("Scanned — universe evaluated by the scan pipeline")
		},
		kpiScannedCount() {
			const f = this.today7.filter_funnel
			if (f && (f.universe_scanned != null || f.universe != null))
				return Number(f.universe_scanned ?? f.universe) || 0
			const hits = this.scannerTotalHits()
			if (hits && hits !== "0") return hits
			return 0
		},
		_marketStripIsoSlice(iso) {
			if (!iso) return ""
			return String(iso).slice(0, 19)
		},
		marketStripSnapshotIso() {
			const t = this.today7.trust || {}
			return this.marketStrip.snapshotAt || t.as_of || this.marketStrip.lastOk || ""
		},
		marketStripSnapshotLine() {
			const iso = this.marketStripSnapshotIso()
			if (!iso) return ""
			return "Snapshot as of " + this._marketStripIsoSlice(iso)
		},
		marketStripRenderLine() {
			const iso = this.marketStrip.renderedAt
			if (!iso) return ""
			const via = this.marketStrip.fromPulse ? "pulse fallback render" : "page render"
			return via + " " + this._marketStripIsoSlice(iso)
		},
		marketStripStaleSnapshotLine() {
			const iso = this.marketStripSnapshotIso() || this.today7.date || ""
			if (!iso) return ""
			return "Snapshot as of " + this._marketStripIsoSlice(iso)
		},
		marketStripStaleRenderLine() {
			return this.marketStripRenderLine()
		},
		_marketDataSnapshotOld(iso) {
			try {
				const d = new Date(iso)
				if (Number.isNaN(d.getTime())) return false
				return Date.now() - d.getTime() > 86400000
			} catch (_) {
				return false
			}
		},
		marketStripStaleDowngrade() {
			const t = this.today7.trust || {}
			const tier = String(this.freshness?.worst_tier || "").toUpperCase()
			const stale = !!(t.stale || tier === "STALE" || tier === "CRITICAL" || this.staleSnapshotContext())
			if (!stale) return false
			const src = String(this.marketStrip.source || t.source || "").toLowerCase()
			const asOf = this.marketStripSnapshotIso()
			return (
				src.includes("snapshot") ||
				src.includes("disk") ||
				src.includes("cache") ||
				src.includes("pulse") ||
				src.includes("brief") ||
				this._marketDataSnapshotOld(asOf)
			)
		},
		marketStripStaleDowngradeLines() {
			const lines = this.decisionAuthority().degraded_copy?.stale_snapshot_lines
			const base =
				Array.isArray(lines) && lines.length
					? lines.slice()
					: [
							"Historical snapshot only",
							"Not suitable for execution decisions",
							"Refresh required for decision use",
						]
			const recovery = this.staleRefreshRecoveryLine()
			if (recovery && !base.includes(recovery)) base.push(recovery)
			return base
		},
		marketPulseIndices() {
			const pulse = (this.today7 && this.today7.pulse) || {}
			const rows =
				Array.isArray(pulse.indices) && pulse.indices.length
					? pulse.indices
					: Array.isArray(this.indices)
						? this.indices
						: []
			return rows.map((ix) => this.normalizeMarketItem(ix)).filter((ix) => ix && (ix.symbol || ix.name))
		},
		dashboardHasNoBoardData() {
			const hasTop = (this.today7.top_ranked || []).length > 0
			const hasNear = (this.today7.near_miss || []).length > 0
			const hasWatch = !!this.today7.todays_decision?.best_watch?.ticker
			return !hasTop && !hasNear && !hasWatch
		},
		playbookVisibleRows() {
			const filter = String(this.rankedOpps.actionFilter || "").toUpperCase()
			const focus = String(this.playbookFocusTicker || "")
				.toUpperCase()
				.trim()
			const base = (this.rankedOpps.rows || []).filter((row) => {
				const act = String(row.action || "").toUpperCase()
				if (filter) return act === filter
				return !["AVOID", "NO_TRADE"].includes(act)
			})
			if (!focus) return base
			const focused = base.filter((r) => String(r.ticker || "").toUpperCase() === focus)
			return focused.length ? focused : base
		},
		playbookRowsCompactMode() {
			if (this.rankedOpps.compact_rows === true) return true
			if (this.rankedOpps.compact_rows === false) return false
			return this.playbookBoardWait() || this.pageAuthorityIsDegraded() || this.playbookUsesBriefFallback()
		},
		playbookToggleCompactRows() {
			this.rankedOpps.compact_rows = !this.playbookRowsCompactMode()
		},
		playbookRowsCompactLabel() {
			return this.playbookRowsCompactMode() ? "Compact rows" : "Expanded rows"
		},
		playbookUseCompactCards(r) {
			return !!r && this.playbookRowsCompactMode()
		},
		playbookEffectivePostureLabel() {
			const bp = this.rankedOpps.board_posture
			if (bp?.effective_posture) return String(bp.effective_posture).replace(/_/g, " ")
			if (this.playbookBoardWait()) return "WAIT"
			return this.canonicalTradeability() || "MONITOR"
		},
		playbookCardStatus(r) {
			return this.effectiveCardAction(r) || "WATCH"
		},
		playbookCardBlockers(r) {
			if (!r) return []
			const blockers = []
			const push = (v) => {
				const s = String(v || "").trim()
				if (!s) return
				if (blockers.some((x) => x.toUpperCase() === s.toUpperCase())) return
				blockers.push(s)
			}
			push(this.playbookCardPrimaryBlocker(r))
			if (r.rr_below_trade_threshold || this.rrBelowTradeGate(r.risk_reward)) push("R:R below TRADE threshold")
			const whyNot = Array.isArray(r.why_not) ? r.why_not : [r.why_not]
			whyNot.filter(Boolean).slice(0, 2).forEach(push)
			const reasons = (r.reasons_against || []).slice(0, 2)
			reasons.forEach(push)
			if (String(r.pilot_state || "").toUpperCase() === "PILOT_RESEARCH_ONLY") push("Pilot not executable yet")
			return blockers.slice(0, 2)
		},
		playbookCompactEvidenceLine(r) {
			if (!r) return "Evidence quality — pending"
			if (r.evidence_quality) return "Evidence quality · " + this.formatEvidence(r.evidence_quality)
			if (r.setup_evidence) {
				const se = r.setup_evidence || {}
				const bits = ["Evidence quality"]
				if (se.sample_size != null && se.sample_size !== "") bits.push("n=" + se.sample_size)
				if (se.win_rate != null) {
					const wr = se.win_rate <= 1 ? se.win_rate * 100 : se.win_rate
					bits.push("WR " + Number(wr).toFixed(0) + "%")
				}
				if (se.avg_r != null) bits.push("avgR " + Number(se.avg_r).toFixed(1))
				return bits.join(" · ")
			}
			if (r.decision_grade) return "Evidence quality · Grade " + r.decision_grade
			return "Evidence quality — pending"
		},
		playbookCardGateLine(r) {
			const status = String(this.playbookCardStatus(r) || "WATCH").trim()
			let detail = String(this.playbookCardPrimaryBlocker(r) || "").trim()
			const norm = (s) =>
				String(s || "")
					.toUpperCase()
					.replace(/[^A-Z0-9]+/g, " ")
					.trim()
			const su = norm(status)
			if (!detail) {
				if (su === "BLOCKED") return "Deploy blocked · gates 未齊"
				if (su === "AVOID" || su === "NO TRADE") return "Avoid · 未達 deploy-ready"
				return status.replace(/_/g, " ") + " · 只可 Monitor"
			}
			detail = detail
				.replace(/^(AVOID|BLOCKED|WATCH|NO_TRADE|PILOT|FALLBACK WATCH)\s*[·\-\—:\u2014]\s*/i, "")
				.trim()
			const du = norm(detail)
			if (!detail || du === su || su.includes(du) || du.includes(su)) {
				if (su === "BLOCKED") return "Deploy blocked · gates 未齊"
				if (su === "AVOID" || su === "NO TRADE") return "Avoid · 未達 deploy-ready"
				return status.replace(/_/g, " ") + " · 只可 Monitor"
			}
			if (su === "BLOCKED") return "Deploy blocked · " + detail
			if (su === "AVOID" || su === "NO TRADE") return "Avoid · " + detail
			return status.replace(/_/g, " ") + " · " + detail
		},
		playbookCardMonitorLine(r) {
			return this.playbookCardGateLine(r)
		},
		playbookCardPrimaryBlocker(r) {
			const oi = r?.operator_insight?.blocker
			if (oi && String(oi).trim()) return oi
			const dep = r.score_card?.deployability_label
			if (dep && String(dep).toUpperCase() !== "DEPLOY" && String(dep).toUpperCase() !== "TRADE") return dep
			const wn = Array.isArray(r.why_not) ? r.why_not[0] : r.why_not || ""
			if (wn) return wn
			if (r.why_wait) return r.why_wait
			const ra = (r.reasons_against || [])[0]
			if (ra) return ra
			if (r.rr_below_trade_threshold || this.rrBelowTradeGate(r.risk_reward)) return "R:R below TRADE threshold"
			return "Deploy gates incomplete"
		},
		playbookCardUpgradeTrigger(r) {
			return r.upgrade_trigger || this.playbookSymbolUpgrade(r) || "Confirm volume + timing before upgrade"
		},
		playbookDisplayRows() {
			const buckets = this.rankedOpps.rank_buckets
			if (buckets && Array.isArray(buckets.monitor_rows)) return buckets.monitor_rows
			const reject = new Set(["AVOID", "NO_TRADE", "BLOCKED"])
			const near = (this.rankedOpps.near_miss || []).filter((r) => {
				const a = String(r.action || r.effective_action || "").toUpperCase()
				return !reject.has(a) && !r.hard_reject
			})
			return near
		},
		playbookBucketRows(key) {
			const b = this.rankedOpps.rank_buckets?.buckets
			return b && b[key] ? b[key] : []
		},
		playbookBucketLabel(key) {
			const labels = {
				deployQualified: "Deploy-qualified",
				pilotQualified: "Pilot-qualified",
				watchQualified: "Watch-qualified",
				nearMiss: "Near-miss upgrade",
				rejectedAvoid: "Rejected / Avoid",
			}
			return labels[key] || key
		},
		playbookMonitorSectionLabel() {
			const b = this.rankedOpps.rank_buckets
			if (b?.monitor_section_label) return b.monitor_section_label
			return this.playbookDisplayRows().length ? "Monitor ranking" : "No valid monitor candidates"
		},
		playbookRejectedDisplayRows() {
			const b = this.rankedOpps.rank_buckets?.buckets?.rejectedAvoid
			if (b?.length) return b
			return (this.rankedOpps.rows || []).filter((r) =>
				["AVOID", "NO_TRADE"].includes(String(r.action || "").toUpperCase()),
			)
		},
		playbookNoValidMonitors() {
			return (
				this.playbookBoardHasContent() &&
				!this.playbookDisplayRows().length &&
				(this.playbookRejectedDisplayRows().length > 0 ||
					!!(this.rankedOpps.rank_buckets && !this.rankedOpps.rank_buckets.has_valid_monitors))
			)
		},
		derivePlaybookNearMiss(opps) {
			const rows = opps || []
			const reject = new Set(["AVOID", "NO_TRADE", "BLOCKED"])
			const watch = rows
				.filter(
					(x) =>
						!reject.has(String(x.action || "").toUpperCase()) &&
						["WATCH", "PILOT"].includes(String(x.action || "").toUpperCase()) &&
						(x.score || 0) >= 6,
				)
				.slice(0, 8)
			if (watch.length) return watch
			return [...rows]
				.filter((r) => !reject.has(String(r.action || "").toUpperCase()))
				.sort((a, b) => (b.score || 0) - (a.score || 0))
				.filter((r) => (r.score || 0) >= 4)
				.slice(0, 3)
				.map((r) => ({
					...r,
					action: "WATCH",
					whats_missing:
						r.whats_missing || "Ranked by scan but blocked by deploy gates — monitor for upgrade",
				}))
		},
		playbookBoardHasContent() {
			return (
				this.playbookVisibleRows().length > 0 ||
				(this.rankedOpps.near_miss || []).length > 0 ||
				(this.rankedOpps.rejection_clusters || []).length > 0 ||
				((this.rankedOpps.avoid_grouped || {}).total || 0) > 0 ||
				this.playbookOppsFallbackVisible()
			)
		},
		playbookEmptyComment() {
			if (this.playbookFetchFailed()) {
				return (
					this.rankedOpps.emergency?.detail ||
					this.rankedOpps.board_explanation ||
					"Live ranked fetch failed — not an empty market day."
				)
			}
			if (this.rankedOpps.emergency?.detail || this.rankedOpps.board_explanation) {
				return this.rankedOpps.emergency?.detail || this.rankedOpps.board_explanation
			}
			if (this.playbookBoardWait()) {
				return "No deployable setups, but watchlist / near-miss rows should still appear when brief or cached board data exists. If this stays blank, refresh playbook or start the engine so live validation can populate the board."
			}
			return "Live ranked pipeline returned no rows. Refresh playbook or check API / engine status."
		},
		dashboardBrokerOffline() {
			const ex = this.today7.execution_readiness || {}
			const st = this.ibkrStateFrom(ex)
			return st.level !== "ready" && !st.handoff
		},
		dashboardWaitTopComment(compact) {
			let s =
				"WAIT · 今日唔做 full deploy。盤面只產生 watch-quality names，暫時冇名稱同時通過 thesis、timing、R:R 同 execution。今日應以監察為主，唔好強行出手。"
			if (this.dashboardBrokerOffline()) {
				s += " Broker offline，execution 暫不可用；目前未有 setup 可升級到 deploy。"
			} else {
				s += " 目前未有 setup 可升級到 deploy。"
			}
			if (compact)
				return (
					"WAIT · 先 Monitor，唔好強行做。今日唔做 full deploy" +
					(this.dashboardBrokerOffline() ? "；broker offline。" : "。")
				)
			return s
		},
		dashboardWhyNotDeployComment() {
			const f = this.today7.filter_funnel || {}
			const ns = this.today7.no_setup_diagnosis || {}
			const { scanned, watch, deploy } = this.playbookFunnelCounts(f, null)
			const scannedN = scanned || ns.total_evaluated || 0
			const watchN = watch || ns.watch_qualified_count || 0
			const deployN = deploy || ns.deployable_count || 0
			return (
				"The issue is not idea scarcity — it is quality scarcity. " +
				scannedN +
				" names were scanned, " +
				watchN +
				" reached watch-qualified status, but " +
				deployN +
				" passed the deploy gate because timing, R:R, and execution readiness remain incomplete. In this state, the system should prefer patience over participation."
			)
		},
		dashboardUnlockDeployStatus() {
			const u = this.today7.unlock_deploy
			if (u && u.summary && !String(u.summary).startsWith("Blocked:")) return this._uiText(u.summary)
			const watchQualified =
				(this.today7.no_setup_diagnosis?.watch_qualified_count || 0) > 0 ||
				(this.playbookFunnelCounts(this.today7.filter_funnel, null).watch || 0) > 0
			const near = (this.today7.near_miss || []).length > 0
			const watch = !!this.today7.todays_decision?.best_watch
			const boardPresent = watchQualified || near || watch || (this.today7.top_ranked || []).length > 0
			const deployable = this.playbookDeployableCount()
			const parts = [
				boardPresent ? "board present" : "board thin",
				deployable >= 1 ? "deploy ready" : "deploy absent",
			]
			if (this.dashboardBrokerOffline()) parts.push("broker offline")
			return this._uiText("Current status: " + parts.join(", ") + ".")
		},
		ibkrSubStatus(ex) {
			const exObj = ex || {}
			if (exObj.sub_status && Object.keys(exObj.sub_status).length) return exObj.sub_status
			return this.ibkrStateFrom(ex).sub || {}
		},
		isWaitDay() {
			const td = this.today7.todays_decision
			const tb = String(this.canonicalTradeability() || td?.regime?.tradeability || "").toUpperCase()
			if (tb === "NO_TRADE" || td?.day_state === "NO_TRADE_DAY") return true
			if (td?.deploy_posture === "WAIT" || tb === "WAIT") return true
			return (td?.execution_ready_count || 0) < 1 && !td?.can_deploy_today
		},
		waitDayHasActionables() {
			const td = this.today7.todays_decision
			const deployable = td?.execution_ready_count || this.today7.no_setup_diagnosis?.deployable_count || 0
			const pilots = td?.pilot_count || 0
			const near = (this.today7.near_miss || []).length
			return deployable > 0 || pilots > 0 || near > 0
		},
		playbookUsesBriefFallback() {
			const da = this.decisionAuthority()
			if (da.source === "fallback_brief" || da.gates?.fallback_brief) return true
			const mode = String(this.rankedOpps.board_mode || "").toLowerCase()
			if (mode === "compressed_fallback") return true
			const src = String(this.rankedOpps.source || "").toLowerCase()
			if (src === "brief" || src.includes("brief") || src.includes("fallback") || src === "compressed_fallback")
				return true
			const warn = String(this.rankedOpps.warning || "").toLowerCase()
			return warn.includes("fallback") || warn.includes("brief") || warn.includes("compressed")
		},
		playbookIsCompressedFallback() {
			return String(this.rankedOpps.board_mode || "").toLowerCase() === "compressed_fallback"
		},
		playbookIsEmergencyBoard() {
			return String(this.rankedOpps.board_mode || "").toLowerCase() === "emergency"
		},
		playbookBoardModeLabel() {
			const ep = this.rankedOpps.board_posture?.effective_posture
			if (ep === "SELECTIVE_MONITOR") return "SELECTIVE · monitor only"
			if (ep === "WAIT") return "WAIT · monitor session"
			if (ep === "DEPLOY_OPEN") return "Deploy gate open"
			if (this.rankedOpps.board_mode_label) return this.rankedOpps.board_mode_label
			const m = String(this.rankedOpps.board_mode || "").toLowerCase()
			if (m === "emergency") return "Board unavailable"
			if (m === "compressed_fallback" || this.playbookUsesBriefFallback()) return "Fallback board"
			if (this.rankedOpps.cached || this.rankedOpps.stale || this.playbookSnapshotLabel()) return "Snapshot board"
			if (m === "full_live") return "Live board"
			if (this.playbookBoardWait() || this.playbookDeployableCount() < 1) return "Monitor board"
			return ""
		},
		playbookSnapshotLabel() {
			const ts = this.rankedOpps.snapshot_timestamp
			if (!ts) return ""
			const s = String(ts).slice(0, 19).replace("T", " ")
			return "Board snapshot · " + s + (this.rankedOpps.refreshing ? " · refreshing…" : "")
		},
		playbookBrokerOffline() {
			const ex = this.rankedOpps.bestAction?.execution_readiness || this.today7.execution_readiness || {}
			const st = this.ibkrStateFrom(ex)
			return st.level !== "ready" && !st.handoff
		},
		playbookDeployableCount() {
			const f = this.rankedOpps.filter_funnel || this.today7.filter_funnel || {}
			return this.playbookFunnelCounts(f, null).deploy
		},
		playbookBoardWait() {
			if (this.isWaitDay()) return true
			const bp = this.rankedOpps.board_posture
			if (bp && bp.effective_posture === "WAIT") return true
			const tb = String(this.rankedOpps.bestAction?.tradeability || this.today7.tradeability || "").toUpperCase()
			if (tb === "WAIT" || tb === "NO_TRADE") return true
			if (this.playbookDeployableCount() < 1) {
				const ba = this.rankedOpps.bestAction
				if (!ba?.best_trade_now?.execution_ready) return true
			}
			return false
		},
		playbookWatchQueueKeys() {
			return [
				"near_trigger",
				"early_setup",
				"needs_volume",
				"needs_thesis",
				"needs_timing",
				"needs_broker_only",
				"needs_data_refresh",
				"dead_remove",
			]
		},
		playbookWatchQueueLabel(key) {
			const m = {
				near_trigger: "Near trigger",
				early_setup: "Early setup",
				needs_volume: "Needs volume",
				needs_thesis: "Needs thesis",
				needs_timing: "Needs timing",
				needs_broker_only: "Needs broker",
				needs_data_refresh: "Needs data refresh",
				dead_remove: "Dead / remove",
			}
			return m[key] || key
		},
		playbookOperatorSectionEntries() {
			return [
				{ key: "deploy_candidates", label: "Deploy candidates" },
				{ key: "pilot_candidates", label: "Pilot candidates" },
				{ key: "watch_upgrades", label: "Watch upgrades" },
				{ key: "blocked_high_conviction", label: "Blocked high conviction" },
				{ key: "fastest_improving", label: "Fastest improving" },
				{ key: "sector_leaders", label: "Sector leaders" },
				{ key: "best_rr", label: "Best R:R" },
				{ key: "monitor_queue", label: "Monitor queue" },
				{ key: "event_sensitive", label: "Event sensitive" },
				{ key: "contradiction_heavy", label: "Contradiction heavy" },
			]
		},
		playbookHasTradeCards() {
			return (this.rankedOpps.rows || []).some((r) =>
				["TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"].includes(
					String(r.action || "").toUpperCase(),
				),
			)
		},
		playbookExecutionGateOverrideActive() {
			if (!this.playbookBoardWait() || !this.playbookHasTradeCards()) return false
			return (
				this.playbookUsesBriefFallback() || this.playbookBrokerOffline() || this.playbookDeployableCount() < 1
			)
		},
		playbookWaitDayIntro() {
			return "WAIT · 今日不可 Deploy。只有 tradeability、deploy-qualified setup、broker handoff 同 watch-qualified data 全部放行，先可解除。"
		},
		playbookWhatToMonitorLine() {
			if (!this.playbookBoardWait()) return ""
			const opts = {
				waitDay: true,
				topSymbol: this.playbookTopWatchSymbol(),
				nearMissCount: (this.rankedOpps.near_miss || this.today7.near_miss || []).length,
			}
			if (typeof CCHelpers !== "undefined" && CCHelpers.playbookWhatToMonitorLine)
				return CCHelpers.playbookWhatToMonitorLine(opts)
			const parts = []
			if (opts.topSymbol) parts.push(String(opts.topSymbol).toUpperCase() + " upgrade triggers")
			if (opts.nearMissCount)
				parts.push(opts.nearMissCount + " near-miss row" + (opts.nearMissCount === 1 ? "" : "s"))
			parts.push("deploy unlock checklist below")
			return "目前只可 Monitor · " + parts.join(" · ")
		},
		playbookTopComment() {
			if (!this.playbookBoardWait()) return ""
			const parts = ["排名只代表關注優先次序，唔代表 Deploy 權限。"]
			if (this.playbookBrokerOffline()) parts.push("IBKR offline · 暫無 handoff。")
			else if (this.playbookDeployableCount() < 1) parts.push("目前 0 個 deploy-qualified。")
			if (this.playbookUsesBriefFallback()) parts.push("Board 仍係 brief fallback · 尚未校準。")
			return parts.join(" ")
		},
		playbookRankingsDisclaimer() {
			if (this.playbookBoardWait()) return "呢度只係 Monitor ranking；WAIT 日 rank ≠ deploy permission。"
			return "Ranking 只代表相對優先次序，唔代表 deploy permission。"
		},
		playbookTopWatchSymbol() {
			const td = this.today7.todays_decision
			if (td?.best_watch?.ticker) return String(td.best_watch.ticker).toUpperCase()
			const ba = this.rankedOpps.bestAction?.best_watch_upgrade?.ticker
			if (ba) return String(ba).toUpperCase()
			const rows = this.rankedOpps.rows || []
			const first = rows.find((r) => ["WATCH", "PILOT"].includes(String(r.action || "").toUpperCase())) || rows[0]
			return first ? String(first.ticker || "").toUpperCase() : ""
		},
		playbookWatchCardFooter() {
			return "Ranked for monitoring, not deployment. WAIT holds until a setup becomes execution-ready and clears quality gates."
		},
		playbookBestActionDisplay() {
			if (
				this.playbookBoardWait() &&
				(this.playbookBrokerOffline() || this.playbookDeployableCount() < 1 || this.playbookUsesBriefFallback())
			) {
				return "WAIT — no deploy-qualified setup and no broker handoff. Monitor near-misses and unlock conditions first."
			}
			return this.rankedOpps.bestAction?.stance_one_liner || ""
		},
		playbookDecisionConfidenceDisplay() {
			const ba = this.rankedOpps.bestAction
			if (
				this.playbookBoardWait() &&
				(this.playbookUsesBriefFallback() ||
					ba?.data_freshness === "STALE" ||
					String(ba?.evidence_quality || "").toLowerCase() === "low")
			) {
				return "Fallback confidence — rank ≠ deploy permission"
			}
			return ba?.decision_confidence_label || ba?.evidence_label || ""
		},
		playbookNearMissMissing(nm) {
			const raw = nm.whats_missing || (Array.isArray(nm.gaps) ? nm.gaps.join(", ") : "") || ""
			if (raw && raw !== "At gate — confirm volume and R:R" && raw !== "At gate — review sizing")
				return "Missing: " + raw
			return "Missing: timing, confirmed volume, monitor support, and execution-ready status"
		},
		playbookNearMissHorizon(nm) {
			return nm.timing_bucket || "next 1–3 sessions if conditions improve"
		},
		playbookNearMissRows() {
			const ranked = this.rankedOpps.near_miss_rows || this.rankedOpps.near_miss || []
			if (ranked.length) return ranked
			if (this.playbookBoardWait() || this.isWaitDay()) return (this.today7.near_miss || []).slice(0, 3)
			return []
		},
		playbookNearMissUpgradeLine() {
			if (!this.playbookBoardWait() && !this.isWaitDay()) return ""
			const rows = this.playbookNearMissRows().slice(0, 3)
			if (!rows.length) {
				const diag = this.today7.no_setup_diagnosis
				if (diag?.primary_blocker) return "Near-miss monitor: " + diag.primary_blocker
				return ""
			}
			return rows
				.map((nm) => {
					const tk = nm.ticker || "—"
					const trig =
						nm.upgrade_trigger ||
						nm.whats_missing ||
						this.playbookNearMissMissing(nm).replace(/^Missing:\s*/, "")
					return tk + " · " + String(trig).slice(0, 72)
				})
				.join(" | ")
		},
		dashboardEventRiskLine() {
			const n = (this.today7.event_risks || []).length
			if (!n) return ""
			return n + " event risk" + (n === 1 ? "" : "s") + " — review before sizing"
		},
		eventRiskKey(r) {
			return this.eventRiskTicker(r) || this.eventRiskLabel(r) || String(r)
		},
		eventRiskTicker(r) {
			if (!r) return ""
			if (typeof r === "string") return r.split(/[:\s]/)[0].toUpperCase()
			return String(r.ticker || r.symbol || "").toUpperCase()
		},
		eventRiskLabel(r) {
			if (!r) return "—"
			if (typeof r === "string") return r
			return r.event || r.label || r.ticker || r.symbol || "—"
		},
		eventRiskTooltip(r) {
			const tk = this.eventRiskTicker(r)
			const lbl = this.eventRiskLabel(r)
			const impact = typeof r === "object" && r ? r.regime_impact || r.impact || "" : ""
			const parts = [lbl]
			if (impact) parts.push("Regime: " + impact)
			if (tk) parts.push("Open dossier for " + tk)
			return parts.join(" · ")
		},
		openEventRiskDossier(r) {
			const tk = this.eventRiskTicker(r)
			if (tk) {
				this.openDossier(tk)
				return
			}
			this.switchTab("dossier")
		},
		dashboardScoreReconciliation() {
			return this.today7.score_reconciliation || this.rankedOpps.score_reconciliation || null
		},
		dashboardScoreReconciliationActive() {
			const sr = this.dashboardScoreReconciliation()
			if (sr && sr.active) return true
			return this.playbookScoreReconciliationActive()
		},
		dashboardScoreReconciliationMessage() {
			const sr = this.dashboardScoreReconciliation()
			return (sr && sr.message) || "Score families disagree — do not size on rank alone"
		},
		dashboardScoreReconciliationDetail() {
			const sr = this.dashboardScoreReconciliation()
			if (!sr) return this.playbookScoreReconciliationDetail()
			const bits = []
			if ((sr.divergent_tickers || []).length) bits.push("Divergent: " + (sr.divergent_tickers || []).join(", "))
			if ((sr.contradictions || []).length) bits.push((sr.contradictions || []).slice(0, 2).join(" · "))
			return bits.join(" — ") || "Council fit vs scanner rank disagree on top names."
		},
		playbookScoreReconciliationActive() {
			const rows = (this.rankedOpps.rows || []).slice(0, 12)
			return rows.some((r) => this.rowScoreFamiliesDiverge(r))
		},
		playbookScoreReconciliationDetail() {
			const rows = (this.rankedOpps.rows || []).slice(0, 12).filter((r) => this.rowScoreFamiliesDiverge(r))
			return rows.length
				? "Divergent: " +
						rows
							.map((r) => r.ticker)
							.filter(Boolean)
							.join(", ")
				: ""
		},
		rowScoreFamiliesDiverge(r) {
			if (!r) return false
			const eq = r.evidence_quality || {}
			const council = Number(r.score || eq.validated_score || 0)
			let scanner = eq.raw_score
			if (scanner == null && r.score_card?.families?.board_investability)
				scanner = r.score_card.families.board_investability.raw_scanner
			if (scanner == null || !council) return false
			let sc = Number(scanner)
			if (sc > 20) sc = sc / 10
			return Math.abs(council - sc) >= 1.5 || String(r.conflict_level || "").toUpperCase() === "HIGH"
		},
		flowPlaybookCrossBadge(ticker) {
			if (this.flowOverlayDegraded()) return false
			const tk = String(ticker || "").toUpperCase()
			if (!tk) return false
			const d = this.flowPanel?.decision
			if (!d || d.degraded || d.freshness?.synthetic || d.mock_only) return false
			const pools = [
				d.actionable_top3,
				d.watch_for_confirm,
				d.live_flow,
				d.best_bullish_flow,
				d.best_bearish_flow,
			].filter(Boolean)
			for (const list of pools) {
				for (const c of list || []) {
					if (String(c.underlying || c.ticker || "").toUpperCase() === tk) return true
				}
			}
			return false
		},
		trackRecordGateLine() {
			if (this.today7.live_track_record || this.today7.evidence_badges?.ai?.badge === "live") return ""
			if (this.today7.ai_narrative || this.today7.ai_loading)
				return "NO TRACK RECORD — model output not live-track-recorded"
			if ((this.today7.top_ranked || []).some((r) => r.ml_confidence != null && !r.live_track_record))
				return "NO TRACK RECORD — model output not live-track-recorded"
			return ""
		},
		playbookCardDisclaimer() {
			if (!this.playbookBoardWait()) return ""
			if (this.playbookUsesBriefFallback() && this.playbookBrokerOffline()) {
				return "Card action reflects research ranking, not live execution permission. Board gate remains WAIT — brief fallback and broker offline."
			}
			return "Research TRADE, not live TRADE. Board gate remains WAIT."
		},
		playbookSymbolComment(r, idx) {
			if (!this.playbookBoardWait()) return ""
			const tk = String(r.ticker || "").toUpperCase()
			const topWatch = this.playbookTopWatchSymbol()
			const isTop = idx === 0 || (topWatch && tk === topWatch)
			if (!isTop) return ""
			const sym = tk || topWatch || "Top name"
			if (topWatch && tk === topWatch) {
				return (
					sym +
					" is the best watch on the board, not the best trade on the board. It ranks near the top on relative priority, but still lacks the clean R:R, thesis strength, and leadership profile needed for deployment."
				)
			}
			return (
				"Top watch, not top trade. " +
				sym +
				" leads a weak board, but still lacks the clean R:R, thesis strength, and leadership profile needed for deployment."
			)
		},
		playbookSymbolWhyNotFullTrade(r) {
			if (!this.playbookBoardWait()) return ""
			const tk = String(r.ticker || "").toUpperCase()
			const topWatch = this.playbookTopWatchSymbol()
			if (!topWatch || tk !== topWatch) return ""
			return "Why not full TRADE: timing, R:R, or execution readiness still incomplete — board gate remains WAIT."
		},
		playbookSymbolUpgrade(r) {
			const tk = String(r.ticker || "").toUpperCase()
			if (this.playbookBoardWait() && tk === this.playbookTopWatchSymbol() && !r.upgrade_trigger) {
				return "Decisive hold above entry zone with improving volume and restored watch-qualified ranking."
			}
			return r.upgrade_trigger || ""
		},
		playbookSymbolBreak(r) {
			const tk = String(r.ticker || "").toUpperCase()
			if (this.playbookBoardWait() && tk === this.playbookTopWatchSymbol()) {
				return "Loses follow-through or closes below stop/invalidation."
			}
			return ""
		},
		btLabPlainSummary() {
			const d = this.btLab.data || {}
			if (d.degraded || d.research_only)
				return "Backend still warming — no usable walk-forward evidence yet. This page is diagnostic only."
			const v = String(d.walk_forward?.verdict || "").toLowerCase()
			if (v === "insufficient_data" || v === "skipped")
				return "No usable walk-forward evidence yet. This page is diagnostic only."
			if (v === "unstable") return "Walk-forward is unstable — treat results as diagnostic, not deploy evidence."
			if (v === "stable_across_windows")
				return "Walk-forward looks consistent across windows — still backtest-only, not live validation."
			return "Backtest lab results are diagnostic only — not deployment authority."
		},
		btLabAuthorityBlock() {
			return "Backtest research only — not deployment authority."
		},
		btLabEvidenceLine() {
			const d = this.btLab.data || {}
			if (d.degraded || d.research_only) return "API warming up — placeholder shell, not a valid backtest."
			const v = String(d.walk_forward?.verdict || "").toLowerCase()
			if (v === "insufficient_data")
				return "Insufficient sample depth — too few trades or windows for reliable attribution."
			if (v === "unstable")
				return "Evidence quality is weak — performance inconsistent across windows with low trade count."
			if (v === "skipped") return "Walk-forward skipped — core backtest only, no cross-window stability check."
			if (this.btLabAttributionLowValue())
				return "Attribution has low informational value — insufficient trade count or incomplete replay coverage."
			if (v === "stable_across_windows")
				return "Moderate evidence — windows show positive returns, but backtest ≠ live track record."
			return "Historical simulation only — gross returns, no fees or slippage."
		},
		btLabActionLine() {
			const d = this.btLab.data || {}
			if (d.degraded || d.research_only) return "Retry Run lab when API health shows full mode."
			const v = String(d.walk_forward?.verdict || "").toLowerCase()
			if (v === "insufficient_data")
				return "Reduce trust in displayed metrics; try a longer period or wait for more trade history."
			if (v === "unstable")
				return "Do not use attractive segments to justify live capital — diagnose robustness only."
			if (v === "skipped")
				return "Enable walk-forward to compare stability across windows before trusting the backtest."
			if (v === "stable_across_windows")
				return "Use for hypothesis validation only — live validation required before sizing."
			return "Use this page to diagnose strategy behavior, not to authorize deployment."
		},
		btLabVerdictLabel() {
			const v = String(this.btLab.data?.walk_forward?.verdict || "").toLowerCase()
			if (v === "insufficient_data") return "Insufficient data"
			if (v === "unstable") return "Unstable"
			if (v === "stable_across_windows") return "Stable across windows"
			if (v === "skipped") return "Skipped"
			return v ? String(this.btLab.data.walk_forward.verdict).replace(/_/g, " ") : "Pending"
		},
		btLabWindowLabel(w) {
			const raw = String((w && w.label) || (w && w.window) || "").toLowerCase()
			if (raw === "recent") return "Recent window"
			if (raw === "1y") return "1-year window"
			if (raw === "2y") return "2-year window"
			if (!raw) return "Window pending"
			return raw.charAt(0).toUpperCase() + raw.slice(1).replace(/_/g, " ")
		},
		btLabTradeReviewHeading() {
			const strat = String(this.btLab.data?.trade_level_review?.strategy || "").trim()
			return strat ? "Trade-level review · " + strat : "Trade-level review · best strategy pending"
		},
		btLabMetricsPending() {
			const d = this.btLab.data || {}
			const review = d.trade_level_review || {}
			const tc = Number(review.trade_count || 0)
			if (d.degraded || d.research_only) return true
			const v = String(d.walk_forward?.verdict || "").toLowerCase()
			if (v === "insufficient_data" || v === "skipped") return true
			if (!tc) return true
			if (this.btLabAttributionLowValue()) return true
			return false
		},
		btLabMetricDisplay(label, val) {
			if (this.btLabMetricsPending()) return label + " · pending"
			if (val == null || val === "" || Number.isNaN(Number(val))) return label + " · unavailable"
			return label + " " + Number(val) + "%"
		},
		btLabTradeMetricsLine() {
			const r = this.btLab.data?.trade_level_review || {}
			return [
				this.btLabMetricDisplay("Win", r.win_rate),
				this.btLabMetricDisplay("avg win", r.avg_win_pct),
				this.btLabMetricDisplay("avg loss", r.avg_loss_pct),
			].join(" · ")
		},
		btLabWalkForwardUnstable() {
			const v = String(this.btLab.data?.walk_forward?.verdict || "").toLowerCase()
			return v === "unstable" || v === "insufficient_data"
		},
		btLabAttributionLowValue() {
			const ranked = this.btLab.data?.attribution?.ranked || []
			const review = this.btLab.data?.trade_level_review || {}
			if (!ranked.length) return true
			const allZero = ranked.every(
				(s) => !(Number(s.return_pct) || Number(s.sharpe) || Number(s.total_trades) || Number(s.trades)),
			)
			const reviewEmpty = !(Number(review.trade_count) || (review.best_trades || []).length)
			return allZero || reviewEmpty
		},
		aiCommentaryWarranted() {
			const td = this.today7.todays_decision
			const dm = this.today7.decision_model
			if ((td?.risk_blockers || []).length) return true
			if ((td?.why_not_aggressive || []).length >= 2) return true
			if (dm && dm.macro_regime === "Hostile" && dm.opportunity_quality !== "Weak") return true
			if ((this.today7.event_risks || []).length >= 2) return true
			if (this.today7.overlap_warning && this.today7.overlap_warning.level === "high") return true
			return false
		},
		aiSetupHintFromStatus(st) {
			if (st?.configured) return ""
			return "Configure any one LLM provider: OPENAI_API_KEY, NVIDIA_API_KEY, OPENCLAW_API_KEY, or LOCAL_LLM_URL (Docker Model Runner). Without a key, Generate still returns a rule-based narrative."
		},
		async fetchAIStatus() {
			try {
				const r = await this.ccFetch("/api/ai/status", { retries: 1, backoff: 400 })
				if (!r || !r.ok) return
				const d = await r.json()
				this.today7.ai_configured = d.configured === true
				if (!this.today7.ai_provider) this.today7.ai_provider = d.configured ? "ready" : "none"
				if (!this.today7.ai_setup_hint) this.today7.ai_setup_hint = this.aiSetupHintFromStatus(d)
			} catch (e) {
				console.warn("fetchAIStatus", e)
			}
		},
		buildDecisionHubFromToday(d) {
			if (!d) return
			const regime = d.market_regime || {}
			const top5 = d.top_5 || []
			const best_action = d.best_action || {}
			const tradeability = regime.tradeability || "WAIT"
			const should_trade = regime.should_trade !== false
			let deploy = "WAIT"
			const td = d.todays_decision
			if (tradeability === "NO_TRADE" || td?.day_state === "NO_TRADE_DAY") deploy = "REDUCE"
			else if (td?.can_deploy_today) deploy = "DEPLOY"
			else if (td?.day_state === "PILOT_WATCH_DAY") deploy = "WATCH"
			else if (!should_trade) deploy = "REDUCE"
			const best_idea = top5[0]
				? { ticker: top5[0].ticker, action: top5[0].action, score: top5[0].score }
				: best_action.best_trade_now
					? { ticker: best_action.best_trade_now.ticker, action: best_action.best_trade_now.action }
					: null
			const avoid_now = (d.avoid || [])
				.slice(0, 5)
				.map((a) =>
					typeof a === "string"
						? { ticker: "—", reason: a, category: "regime" }
						: { ticker: a.ticker || "—", reason: a.reason || "", category: a.category || "filter" },
				)
			let best_rr = null
			;(top5 || []).forEach((t) => {
				const rr = this.parseRR(t.risk_reward || 0)
				if (rr > 0 && (!best_rr || rr > best_rr.risk_reward)) best_rr = { ticker: t.ticker, risk_reward: rr }
			})
			const stock_mon = (d.near_miss || [])
				.slice(0, 3)
				.map((nm) => ({
					class: "stock",
					rule: "Upgrade watch " + (nm.ticker || ""),
					detail: nm.upgrade_trigger || "",
				}))
			const market_mon = []
			if (regime.vix != null)
				market_mon.push({ class: "market", rule: "VIX " + regime.vix, detail: "Reduce size if VIX >25" })
			if (regime.breadth != null)
				market_mon.push({
					class: "market",
					rule: "Breadth " + regime.breadth + "%",
					detail: "Broad deploy needs breadth >50%",
				})
			const ex = d.execution_readiness || best_action.execution_readiness || {}
			const execution_mon = [
				{
					class: "execution",
					rule: "Gateway",
					detail: ex.gateway_reachable ? "Up — connect session" : "Down — paper signals only",
				},
				{
					class: "execution",
					rule: "Broker login",
					detail: ex.broker_connected
						? (ex.paper_or_live || "paper").toUpperCase() + " connected"
						: "Not logged in",
				},
				{
					class: "execution",
					rule: "Position sync",
					detail: ex.portfolio_source || (ex.portfolio_synced ? "IBKR" : "Manual"),
				},
				{
					class: "execution",
					rule: "Bracket readiness",
					detail: ex.bracket_order_ready ? "Ready" : "Draft in IBKR tab",
				},
				{ class: "execution", rule: "Order handoff", detail: ex.readiness_label || "Broker offline" },
			]
			if (ex.last_heartbeat)
				execution_mon.push({ class: "execution", rule: "Heartbeat", detail: ex.last_heartbeat })
			this.decisionHub = {
				warming: false,
				_from_today: true,
				decision_strip: {
					best_idea_now: best_idea,
					best_risk_reward_now: best_rr,
					avoid_now,
					market_posture_now: { tradeability, should_trade, deploy_posture: deploy },
					deploy_reduce_wait: deploy,
					stance_one_liner: best_action.stance_one_liner || "",
				},
				monitoring: {
					stock: stock_mon,
					portfolio: [
						{ class: "portfolio", rule: "Position size vs 1R stop", detail: "Resize if stop widens >15%" },
					],
					market: market_mon,
					smart_money: [],
					execution: execution_mon,
					posture: deploy,
				},
			}
		},
		async fetchCcHeader() {
			return this.fetchCcStatus()
		},
		async fetchCcStatus() {
			try {
				const tabQ = this.tab ? "?tab=" + encodeURIComponent(this.tab) : ""
				const r = await fetch("/api/ops/cc-header" + tabQ, {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (r.ok) {
					const h = await r.json()
					const eng = h.engine || {}
					this.ccHeader = {
						decision_authority: h.decision_authority || null,
						cc_state: h.cc_state || null,
						system_state: h.system_state || null,
						page_capability: h.page_capability || null,
						page_authority_mode: h.page_authority_mode || "active",
						portfolio_context: h.portfolio_context || null,
						header_summary: h.header_summary || null,
					}
					this.cc_status.mode = h.display_mode || "PAPER"
					if (h.display_mode === "LOADING")
						this.healthData = {
							...(this.healthData || {}),
							mode: "loading",
							uptime_seconds: this.healthData?.uptime_seconds || 0,
						}
					if (h.degraded_banner) this.instantDegradedBanner = h.degraded_banner
					this.cc_status.breaker = !!eng.circuit_breaker
					this.cc_status.breaker_reason = eng.circuit_breaker_reason || ""
					this.freshness = h.freshness || null
					this.brief_status = h.brief_status || null
					this.risk_alerts = h.risk_alerts || null
					const ib = h.ibkr || {}
					this.cc_status.ibkr_connected = !!(ib.session_usable || ib.connected)
					this.cc_status.ibkr_mode = (ib.mode || "paper").toLowerCase()
					this.cc_status.ibkr_gateway = !!ib.gateway_reachable
					this.cc_status.ibkr_monitoring = !!(
						ib.monitoring_only ||
						(ib.health && ib.health.handoff_status === "monitoring_only")
					)
					this.cc_status.ibkr_health_label =
						ib.health_label ||
						(ib.diagnosis && ib.diagnosis.label) ||
						(ib.health && ib.health.summary_label) ||
						""
					if (ib.diagnosis) this.ibkr.diagnosis = ib.diagnosis
					if (typeof ib.docker === "boolean") this.ibkr.docker = !!ib.docker
					this.ibkr.host =
						window.CCHelpers && CCHelpers.ibkrSyncHostFromStatus
							? CCHelpers.ibkrSyncHostFromStatus(ib.host || this.ibkr.host, !!ib.docker)
							: ib.host || this.ibkr.host
					this.ibkr.gateway_reachable = !!ib.gateway_reachable
					this.ibkr.api_port_open = !!ib.api_port_open
					this.ops.components = h.components || {}
					this.providers = h.providers || this.providers
					this.live = !!(this.ops.components.market_data || h.providers?.yfinance)
					this.trust = { mode: h.trust_mode || "PAPER", source: "cc-header", as_of: h.as_of }
					this.cc_status.last_fetch = Date.now()
					return
				}
			} catch (e) {
				/* fall through to legacy polls */
			}
			try {
				const r = await fetch("/api/ops/status")
				if (!r.ok) return
				const d = await r.json()
				this.opsDetail = d
				this.ops = { ...(d.engine || {}), components: d.components || {} }
				const eng = d.engine || {}
				const trustMode = d.trust && d.trust.mode ? String(d.trust.mode).toUpperCase() : "PAPER"
				this.cc_status.mode = eng.dry_run === false ? "LIVE" : eng.running ? "PAPER" : trustMode
				this.cc_status.breaker = !!eng.circuit_breaker
				this.cc_status.breaker_reason = eng.circuit_breaker_reason || ""
				this.cc_status.uptime_s = d.uptime_seconds || 0
				this.live = !!(this.ops.components?.market_data || eng.running === true)
				if (d.trust) this.trust = d.trust
			} catch (e) {
				this.cc_status.mode = "PAPER"
				this.live = false
			}
			try {
				const r2 = await fetch("/api/ibkr/status")
				if (r2.ok) {
					const d2 = await r2.json()
					this.ibkrApplyStatusPayload(d2)
					this.cc_status.ibkr_connected = !!(d2.session_usable || d2.connected)
					this.cc_status.ibkr_mode = (d2.mode || "paper").toLowerCase()
					this.cc_status.ibkr_gateway = !!d2.gateway_reachable
					this.cc_status.ibkr_monitoring = !!d2.monitoring_only
					this.cc_status.ibkr_health_label = d2.health_label || (d2.health && d2.health.summary_label) || ""
				}
			} catch (e) {}
			this.cc_status.last_fetch = Date.now()
		},
		tick() {
			this.clock = new Date().toLocaleTimeString("en-US", {
				hour: "2-digit",
				minute: "2-digit",
				second: "2-digit",
			})
		},
		toggleStar(ticker) {
			this.ccStarred[ticker] = !this.ccStarred[ticker]
			localStorage.setItem("ccStarred", JSON.stringify(this.ccStarred))
		},
		toggleLove(ticker) {
			this.ccLoved[ticker] = !this.ccLoved[ticker]
			localStorage.setItem("ccLoved", JSON.stringify(this.ccLoved))
		},
		toggleWatchlist(ticker) {
			this.ccWatchlist[ticker] = !this.ccWatchlist[ticker]
			localStorage.setItem("ccWatchlist", JSON.stringify(this.ccWatchlist))
		},
		contextDecisionBar() {
			if (this.tab === "guide") return null
			if (this.tab === "portfolio" && this.pfDecision && this.pfDecision.decision_bar)
				return this.pfDecision.decision_bar
			if (this.tab === "funds" && this.fundMonitor.console && this.fundMonitor.console.decision_bar)
				return this.fundMonitor.console.decision_bar
			if (this.tab === "dossier" && this.dos.intel && this.dos.intel.decision_bar)
				return this.dos.intel.decision_bar
			if ((this.tab === "today" || this.tab === "signals") && this.decisionHub && this.decisionHub.decision_bar)
				return this.decisionHub.decision_bar
			return null
		},
		normalizedContextDecisionBar() {
			const raw = this.contextDecisionBar()
			if (!raw) return null
			const mode = this.pageSurface()
			const chip = this.normalizedAuthorityChipForTab(this.tab, {
				badge: raw.verdict,
				authority: "monitor_only",
				short: raw.next_action,
				authority_label: "",
			})
			const deployVerdicts = ["DEPLOY", "TRADE", "ALLOCATE", "BUY", "SCALE", "PILOT"]
			const rawVerdict = String(raw.verdict || "").toUpperCase()
			let verdict = raw.verdict
			let nextAction = raw.next_action
			const blockedChip = ["BLOCKED", "MONITOR ONLY", "RESEARCH ONLY", "CONFIRM ONLY", "ANALYSIS ONLY"].includes(
				String(chip.badge || "").toUpperCase(),
			)
			const researchSurface = !["dashboard_core", "playbook_core", "ibkr_execution"].includes(mode)
			if (
				blockedChip ||
				researchSurface ||
				this.pageAuthorityIsDegraded() ||
				this.isWaitDay() ||
				this.playbookBoardWait()
			) {
				if (deployVerdicts.includes(rawVerdict) || rawVerdict === "HANDOFF READY") {
					verdict = chip.badge || "MONITOR ONLY"
					nextAction = chip.short || nextAction
				}
			}
			if (researchSurface && deployVerdicts.includes(String(verdict || "").toUpperCase())) {
				verdict = chip.badge || "RESEARCH ONLY"
				nextAction = chip.short || "只可研究比較 · not executable here"
			}
			return { ...raw, verdict, next_action: nextAction }
		},
		fmtDisplay(v, def = "—") {
			if (v === true || v === "true") return "Yes"
			if (v === false || v === "false") return "No"
			if (v == null || v === "") return def
			if (typeof v === "object") return this.formatEvidence(v)
			return this.sanitizeVisibleText(String(v)) || def
		},
		fundRegimeDisplay() {
			const c = this.fundMonitor.console || {}
			const d = this.fundMonitor.data || {}
			const label = c.regime_display || d.regime_display || c.regime || d.regime
			if (label && String(label).toUpperCase() !== "UNKNOWN") return label
			const tr = this.today7.regime?.trend
			const tb = this.today7.tradeability || ""
			if (tr) return tr + (tb ? " · " + tb : "")
			return label || "—"
		},
		fundRegimeNote() {
			const c = this.fundMonitor.console || {}
			if (c.regime_stale_note) return c.regime_stale_note
			if (c.regime_note) return c.regime_note
			if (c.using_today_fallback && c.today_regime_label) return "Using Today regime: " + c.today_regime_label
			const label = (c.regime_display || "").toUpperCase()
			if (label === "UNKNOWN" && this.today7.regime?.trend)
				return "Local sleeve regime unresolved — fallback to Today regime"
			return ""
		},
		fundPayloadDegraded() {
			const d = this.fundMonitor.data || {}
			return !!(d.degraded || d.research_only || d.metrics_pending)
		},
		fundCardMetricsPending(card) {
			if (!card) return this.fundPayloadDegraded()
			return !!(card.metrics_pending || this.fundPayloadDegraded())
		},
		fundBenchmarkLine() {
			const d = this.fundMonitor.data
			const bm = this.fundMonitor.benchmark || d?.benchmark || "SPY"
			if (!d) return "Loading…"
			if (this.fundPayloadDegraded() || d.benchmark_return_pct == null)
				return "Benchmark " + bm + " — unavailable or pending"
			return "Benchmark " + bm + " (" + d.benchmark_return_pct + "%)"
		},
		fundWhyNotMoreLine(items) {
			const list = Array.isArray(items) ? items.filter(Boolean) : []
			if (!list.length) return "—"
			return list.join(" · ")
		},
		fundFitDisplay(card) {
			const rf = card?.regime_fit
			if (rf === "warming" || String(rf || "").toLowerCase() === "fit warming") return "Warming"
			if (this.fundCardMetricsPending(card) && (rf == null || rf === "" || rf === 0)) return "Metrics pending"
			if (rf == null || rf === "") return "—"
			return String(rf).includes("%") ? String(rf) : rf + "%"
		},
		fundFitDecomposedLabel(card) {
			const d = card?.regime_fit_decomposed
			if (!d) return "—"
			const c = d.composite
			if (c === "warming" || String(c || "").toLowerCase() === "fit warming") return "Fit: warming"
			if (typeof c === "number" || /^\d+$/.test(String(c))) return "Fit " + c + "%"
			const s = String(c || "")
			return s.toLowerCase().startsWith("fit") ? s : "Fit " + s
		},
		fundAllocationMaxCapital() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const strip = this.fundMonitor.console?.allocator_truth_strip || {}
			return inv.max_capital_allowed || strip.max_capital_allowed || "—"
		},
		fundExecutionReadyBool() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const strip = this.fundMonitor.console?.allocator_truth_strip || {}
			if (typeof inv.execution_ready === "boolean") return inv.execution_ready
			if (typeof strip.execution_ready === "boolean") return strip.execution_ready
			const lbl = String(inv.execution_ready || strip.execution_ready_label || "").toLowerCase()
			return lbl === "yes" || lbl.startsWith("ready")
		},
		fundExecutionReadyLabel() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const strip = this.fundMonitor.console?.allocator_truth_strip || {}
			const raw = inv.execution_ready ?? strip.execution_ready_label ?? strip.execution_ready
			if (raw === true) return "Yes"
			if (raw === false) return "No"
			const s = String(raw || "").trim()
			if (!s) return "No"
			if (/^yes$/i.test(s)) return "Yes"
			if (/^no$/i.test(s)) return "No"
			return s
		},
		fundAllocationExecutionState() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const ex = this.fundMonitor.console?.execution_readiness || {}
			return inv.execution_state_label || ex.execution_state_label || ex.readiness_label || ""
		},
		fundAllocationStatusNote() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const trust = this.fundMonitor.data?.trust || {}
			if (trust.reason) return trust.reason
			if (inv.regime_stale_note) return inv.regime_stale_note
			if (this.fundMonitor.error) return this.fundMonitor.error
			return ""
		},
		fundPrimarySummary() {
			const inv = this.fundMonitor.console?.investable_now || {}
			const strip = this.fundMonitor.console?.allocator_truth_strip || {}
			const fetchFailed = !!(this.fundMonitor.error && !this.fundMonitor.data)
			const canAllocate =
				Number(strip.live_eligible_count || 0) > 0 &&
				this.fundExecutionReadyBool() &&
				!this.fundPayloadDegraded()
			const strongestEligible = inv.strongest_eligible?.label || ""
			const strongestResearch = inv.strongest_research?.label || ""
			const strongestSleeve =
				strongestEligible || (strongestResearch ? strongestResearch + " · research-only" : "—")
			const whyBlocked = canAllocate
				? "Board / execution 已對齊，可按 band 分配"
				: fetchFailed
					? this.pageOperatorSentence().blocker || "fund API fetch failed"
					: this.fundWhyNotMoreLine(inv.why_not_more || strip.why_not_more) ||
						inv.truth_headline ||
						this.fundAllocationStatusNote() ||
						"仍未有 live-validated sleeve"
			const executionMode = canAllocate
				? "可執行 · Executable"
				: this.fundExecutionReadyBool()
					? "紙上觀察 · Paper only"
					: "研究模式 · Research only"
			const nextAction = canAllocate
				? "只複核 " +
					(strongestEligible || strongestResearch || "當前 sleeve") +
					"，再按 " +
					(this.fundAllocationMaxCapital() || "band") +
					" 控制資金。"
				: fetchFailed
					? this.pageOperatorSentence().next_action || "index/core posture only — no sleeve allocation today"
					: "先修 regime / execution blockers，唔好把 backtest sleeves 當 live capital。"
			return {
				canAllocate,
				allocateLabel: canAllocate ? "可分配 · Allocate" : "不可分配 · Blocked",
				executionMode,
				strongestSleeve,
				maxCapital: this.fundAllocationMaxCapital() || "—",
				whyBlocked,
				nextAction,
				fetchFailed,
			}
		},
		fundsIndexPostureLine() {
			const idx = this.fundMonitor.console?.index_fund_posture || this.today7?.index_fund_posture
			if (!idx || typeof idx !== "object") return ""
			return String(idx.headline || idx.valuation_summary || idx.banner || "").slice(0, 160)
		},
		fundsFetchFailedShell() {
			return !!(this.fundMonitor.error && !this.fundMonitor.data && !this.fundMonitor.loading)
		},
		discoveryHasApiCachedLeaders() {
			const d = this.scannerHub.data || {}
			return Array.isArray(d.cached_leaders) && d.cached_leaders.length > 0
		},
		discoveryCachedLeadersBannerVisible() {
			if (this.discoveryHasApiCachedLeaders()) return true
			const hub = String(this.scannerHub.data?.hub_status || "").toLowerCase()
			return hub === "degraded" && this.discoveryCachedLeadersRows().length > 0
		},
		discoveryCachedLeadersRows() {
			const d = this.scannerHub.data || {}
			const out = []
			const seen = new Set()
			const add = (row, source) => {
				const t = String((row && row.ticker) || row || "").toUpperCase()
				if (!t || t.length > 8 || seen.has(t)) return
				seen.add(t)
				out.push(
					typeof row === "object" && row !== null
						? { ...row, ticker: t, source: source || row.source || "cache" }
						: { ticker: t, source: source || "cache" },
				)
			}
			;(d.cached_leaders || []).slice(0, 8).forEach((r) => add(r, "brief-cache"))
			;(d.merged_top_names || []).slice(0, 8).forEach((r) => add(r, "merged"))
			const intent = d.decision_intent?.LEADERS || {}
			;(intent.top_hits || intent.sample || intent.hits || []).slice(0, 8).forEach((r) => add(r, "leaders"))
			if (!out.length && (this.scannerHub.error || this.scannerDiscoveryHasFallbackRows())) {
				;(this.rankedOpps.rows || [])
					.filter((r) => !["AVOID", "NO_TRADE", "BLOCKED"].includes(String(r.action || "").toUpperCase()))
					.slice(0, 6)
					.forEach((r) => add(r, "playbook-bridge"))
				;(this.today7.top_ranked || []).slice(0, 4).forEach((r) => add(r, "dashboard-bridge"))
			}
			return out.slice(0, 8)
		},
		discoveryCachedIntentRows(intent) {
			const d = this.scannerHub.data || {}
			const intentObj = d.decision_intent?.[intent] || {}
			const pool = intentObj.top_hits || intentObj.sample || intentObj.hits || []
			const reject = new Set(["AVOID", "NO_TRADE", "BLOCKED"])
			const out = []
			const seen = new Set()
			const add = (row, source) => {
				const t = String((row && row.ticker) || row || "").toUpperCase()
				if (!t || t.length > 8 || seen.has(t)) return
				if (row && reject.has(String(row.action || "").toUpperCase())) return
				seen.add(t)
				out.push(
					typeof row === "object" && row !== null
						? { ...row, ticker: t, source: source || intent }
						: { ticker: t, source: source || intent },
				)
			}
			pool.slice(0, 8).forEach((r) => add(r, intent.toLowerCase()))
			if (!out.length && (this.scannerHub.error || this.scannerDiscoveryHasFallbackRows())) {
				;(this.rankedOpps.rows || [])
					.filter((r) => {
						const a = String(r.action || "").toUpperCase()
						return (
							!reject.has(a) &&
							(intent !== "BREAKOUTS" || a === "TRADE" || r.ladder_bucket === "watch_upgrade")
						)
					})
					.slice(0, 6)
					.forEach((r) => add(r, "playbook-bridge"))
			}
			return out.slice(0, 8)
		},
		discoveryShowCachedBreakouts() {
			return (
				(this.scannerHub.error || this.scannerDiscoveryHasFallbackRows()) &&
				this.discoveryCachedIntentRows("BREAKOUTS").length > 0
			)
		},
		discoveryShowCachedPullbacks() {
			return (
				(this.scannerHub.error || this.scannerDiscoveryHasFallbackRows()) &&
				this.discoveryCachedIntentRows("PULLBACKS").length > 0
			)
		},
		discoveryShowCachedLeaders() {
			return (
				(this.discoveryCachedLeadersBannerVisible() ||
					this.scannerHub.error ||
					this.scannerDiscoveryHasFallbackRows() ||
					(this.scannerHub.loading === false && !this.scannerHub.data)) &&
				this.discoveryCachedLeadersRows().length > 0
			)
		},
		discoveryPageStateVisible() {
			return !!(this.scannerHub.error && !this.globalSystemStripVisible())
		},
		fundMetricPct(val, card, pendingLabel) {
			if (this.fundCardMetricsPending(card) && (val == null || val === 0))
				return pendingLabel || "Metrics pending"
			if (val == null) return "—"
			return val + "%"
		},
		fundMetricTone(val, card) {
			if (this.fundCardMetricsPending(card) && (val == null || val === 0)) return ""
			if (val == null) return ""
			return (val || 0) >= 0 ? "text-green-400" : "text-red-400"
		},
		fundReturnDisplay(card) {
			if (this.fundCardMetricsPending(card) && (card.fund_return_pct == null || card.fund_return_pct === 0))
				return "Backtest evidence unavailable"
			return this.fundMetricPct(card.fund_return_pct, card, "Metrics pending")
		},
		fundAlphaDisplay(card) {
			if (this.fundCardMetricsPending(card) && (card.excess_return_pct == null || card.excess_return_pct === 0))
				return "Metrics pending"
			if (card.excess_return_pct == null) return "—"
			const v = card.excess_return_pct
			return (v >= 0 ? "+" : "") + v + "%"
		},
		fundDrawdownDisplay(card) {
			if (this.fundCardMetricsPending(card) && (card.max_drawdown_pct == null || card.max_drawdown_pct === 0))
				return "Metrics pending"
			if (card.max_drawdown_pct == null) return "—"
			return card.max_drawdown_pct + "%"
		},
		fundEvidenceWindowLine(card) {
			const win = card.evidence_quality?.sample_window || "1y"
			const live = card.evidence_quality?.live_trades_count ?? 0
			let bm = "BM pending"
			if (!this.fundCardMetricsPending(card) && card.benchmark_return_pct != null)
				bm = "BM " + card.benchmark_return_pct + "%"
			else if (this.fundPayloadDegraded()) bm = "BM unavailable or pending"
			return "Window: " + win + " · " + bm + " · live trades: " + live
		},
		verdictPillClass(v) {
			const m = {
				BUY: "pg",
				DEPLOY: "pg",
				ALLOCATE: "pg",
				TRADE: "pg",
				SCALE: "pg",
				PILOT: "pb",
				HOLD: "pw",
				WAIT: "pa",
				WATCH: "pa",
				REDUCE: "pr",
				AVOID: "pr",
				REBALANCE: "pa",
				PAUSE: "pr",
				"RESEARCH ONLY": "pa",
				"ANALYSIS ONLY": "pa",
				"HOLD CASH": "pw",
				"MONITOR ONLY": "pa",
				"CONFIRM ONLY": "pa",
				BLOCKED: "pr",
			}
			return m[(v || "").toUpperCase()] || "pw"
		},
		async fetchAosMonitors() {
			this.aosMonitors.loading = true
			try {
				const [r1, r2] = await Promise.all([
					fetch("/api/v7/monitors", { headers: { "X-API-Key": window._apiKey || "dev-secret-local" } }),
					fetch("/api/v7/monitors/evaluate", {
						headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
					}),
				])
				if (r1.ok) {
					const d = await r1.json()
					this.aosMonitors.rules = d.monitors || []
				}
				if (r2.ok) {
					const d = await r2.json()
					this.aosMonitors.alerts = d.alerts || []
				}
			} catch (e) {
			} finally {
				this.aosMonitors.loading = false
			}
		},
		switchTab(t) {
			this.tab = ccNormalizeTab(t, "today")
			this.ccHeader.header_summary = null
			this.fetchCcStatus()
			const tSafe = this.tab
			if (tSafe === "today") {
				this.fetchToday7()
				this.fetchMarketStrip()
				this.fetchLeadersDashboard()
			}
			if (tSafe === "signals") {
				this.hydrateRankedFromCache()
				this.fetchSignals()
				this.fetchRanked()
				if (!this._signalsPoll) {
					this._signalsPoll = setInterval(() => {
						if (this.tab === "signals") this.fetchSignals()
					}, 60000)
				}
			}
			if (tSafe === "scanners") {
				this.hydrateScannersFromCache()
				this.fetchScanners()
			}
			if (tSafe === "portfolio") {
				this.fetchPortfolio()
				this.fetchDesk()
			}
			if (tSafe === "dossier") {
				if (this.dos.ticker) {
					this.fetchDossier()
				} else {
					this.dos.status = "idle_no_query"
					this.dos.error = ""
					this.dos.loading = false
				}
			}
			if (tSafe === "leaders") {
				this.fetchLeadersHub()
			}
			if (tSafe === "funds") {
				this.fetchFunds()
				this.fetchLeaders()
			}
			if (tSafe === "flow") {
				if (!this.today7.regime) this.fetchToday7()
				this.fetchFlow()
			}
			if (tSafe === "agent") {
				if (!this.today7?.regime) this.fetchToday7()
				this.fetchVibeAgent()
			}
			if (tSafe === "strategy-lab") {
				if (!this.today7?.regime) this.fetchToday7()
				this.fetchStrategyLabShell()
			}
			if (tSafe === "shadow") {
				this.fetchShadowShell()
			}
			if (tSafe === "reports") {
				this.fetchReportsLib()
			}
			if (tSafe === "rs") {
				this.fetchRs()
			}
			if (tSafe === "notrade") {
				this.fetchRejections()
			}
			if (tSafe === "command") {
				this.fetchCommandBoard()
			}
			if (tSafe === "ops") {
				this.fetchCcStatus()
				this.fetchOpsRuntime()
				this.fetchOpsConsole()
				this.fetchChangelog()
				this.fetchErrorLog()
				this.fetchNotifyLog()
			}
			if (tSafe === "ibkr") {
				this.ibkrRefreshAll()
			}
			if (tSafe === "btlab" && !this.btLab.data && !this.btLab.loading) {
				/* user clicks Run lab */
			}
			if (this.uiExpandAll) {
				this.$nextTick(() => this.applyUiExpandAll())
			}
		},
		uiExpandAllActive() {
			return !!this.uiExpandAll
		},
		uiExpandAllLabel() {
			return this.uiExpandAll ? "Collapse all" : "Expand all"
		},
		async copyBdrSummary() {
			const text = String((this.today7.bdr_summary && this.today7.bdr_summary.text) || "")
			if (!text) return
			try {
				if (navigator.clipboard && navigator.clipboard.writeText) {
					await navigator.clipboard.writeText(text)
					return
				}
			} catch (e) {}
			try {
				const ta = document.createElement("textarea")
				ta.value = text
				ta.setAttribute("readonly", "")
				ta.style.position = "fixed"
				ta.style.left = "-9999px"
				document.body.appendChild(ta)
				ta.select()
				document.execCommand("copy")
				document.body.removeChild(ta)
			} catch (e) {
				console.warn("copyBdrSummary failed", e)
			}
		},
		uiExpandAllFabLabel() {
			return this.uiExpandAll ? "收合" : "一鍵展開"
		},
		uiExpandAllHeaderLabel() {
			return this.uiExpandAll ? "收合 · Collapse all" : "一鍵展開 · Expand all"
		},
		ccDetailsOpen(fallback) {
			return this.uiExpandAll || !!fallback
		},
		toggleUiExpandAll() {
			this.uiExpandAll = !this.uiExpandAll
			this.applyUiExpandAll()
		},
		applyUiExpandAll() {
			const on = !!this.uiExpandAll
			if (this.today7) {
				this.today7.avoid_collapsed = !on
				this.today7.ai_commentary_open = on
			}
			this.rankedOpps.avoid_collapsed = !on
			this.rankedOpps.operator_sections_open = on
			this.rankedOpps.compact_rows = on ? false : this.isWaitDay() ? null : false
			this.scannerHub.expanded = on
			this.rsPanel.expanded = on
			this.ledgerView.expanded = on
			if (on) {
				const clusters = this.rejectionsPanel?.data?.clusters || []
				clusters.forEach((cl) => {
					if (cl?.key) this.rejectionsClusterExpanded[cl.key] = true
				})
				if (this.pfDecision) this.pfDecision.sleeve_research_collapsed = false
			} else {
				this.rejectionsClusterExpanded = {}
				if (this.isWaitDay()) {
					this.today7.avoid_collapsed = true
					this.today7.ai_commentary_open = false
					this.rankedOpps.avoid_collapsed = true
					this.rankedOpps.compact_rows = null
				}
				if (this.pfDecision) this.pfDecision.sleeve_research_collapsed = true
			}
			this.$nextTick(() => this.syncDetailsExpandAll(on))
		},
		syncDetailsExpandAll(open) {
			requestAnimationFrame(() => {
				document.querySelectorAll("details").forEach((el) => {
					if (open) {
						if (el.offsetParent !== null) el.open = true
						return
					}
					if (el.hasAttribute("data-cc-default-open")) return
					el.open = false
				})
			})
		},

		cmdActionColor(action) {
			return (
				{
					TRADE: "var(--green)",
					WATCH: "var(--amber)",
					WAIT: "var(--t3)",
					NO_TRADE: "var(--red)",
					REJECT: "var(--red)",
				}[action] || "var(--t3)"
			)
		},
		cmdConfColor(v) {
			return v >= 70 ? "var(--green)" : v >= 50 ? "var(--amber)" : "var(--red)"
		},

		acInput(val, target) {
			this.ac.target = target
			if (this.ac.timer) clearTimeout(this.ac.timer)
			if (!val || val.length < 1) {
				this.ac.results = []
				this.ac.show = false
				return
			}
			this.ac.timer = setTimeout(async () => {
				try {
					const r = await fetch("/api/tickers?q=" + encodeURIComponent(val))
					if (r.ok) {
						const d = await r.json()
						this.ac.results = d.results || []
						this.ac.show = this.ac.results.length > 0
						this.ac.selIdx = -1
					}
				} catch (e) {
					this.ac.show = false
				}
			}, 150)
		},
		acSelect(item) {
			const t = this.ac.target
			if (t === "dos") this.dos.ticker = item.s
			// 'opt','bt','tt' targets removed — dead routes (sprint-dead-route-purge)
			this.ac.show = false
			this.ac.results = []
			this.ac.selIdx = -1
			if (t === "dos" && this.dos.ticker) this.fetchDossier()
		},
		acKey(e) {
			if (!this.ac.show) return
			if (e.key === "ArrowDown") {
				e.preventDefault()
				this.ac.selIdx = Math.min(this.ac.selIdx + 1, this.ac.results.length - 1)
			} else if (e.key === "ArrowUp") {
				e.preventDefault()
				this.ac.selIdx = Math.max(this.ac.selIdx - 1, 0)
			} else if (e.key === "Enter" && this.ac.selIdx >= 0) {
				e.preventDefault()
				this.acSelect(this.ac.results[this.ac.selIdx])
			} else if (e.key === "Escape") {
				this.ac.show = false
			}
		},
		_clearRetry() {
			if (this._retryTimer) {
				clearTimeout(this._retryTimer)
				this._retryTimer = null
			}
		},
		dosEquity() {
			const s = this.pf && this.pf.summary
			return (s && (s.account_equity || s.equity || s.total_value)) || 100000
		},
		stratSpark(curve) {
			// Render cumulative R curve to a 40×14 SVG path.
			if (!curve || curve.length < 2) return ""
			const w = 40,
				h = 14,
				pad = 1
			const lo = Math.min(...curve),
				hi = Math.max(...curve)
			const range = Math.max(0.01, hi - lo)
			const step = (w - 2 * pad) / (curve.length - 1)
			const pts = curve.map((v, i) => {
				const x = pad + i * step
				const y = h - pad - ((v - lo) / range) * (h - 2 * pad)
				return (i === 0 ? "M" : "L") + x.toFixed(1) + "," + y.toFixed(1)
			})
			return pts.join(" ")
		},
		pfRisk() {
			const positions = (this.pf && this.pf.positions) || []
			const summary = this.pf && this.pf.summary
			const equity = (summary && (summary.total_value || summary.account_equity)) || 100000
			const serverHeat = this.pfDecision && this.pfDecision.portfolio_heat
			let heatDollars = 0,
				topVal = 0,
				topTicker = "",
				withStop = 0,
				withoutStop = 0
			let posVolWeighted = 0
			let hasRealVol = false
			let localBreached = 0
			for (const p of positions) {
				const px = p.current_price || p.last_price || p.entry_price || 0
				const stop = Number(p.stop_price || p.current_stop || p.initial_stop || p.stop || 0)
				const sh = p.shares || p.quantity || 0
				const stopOk = !!(p.stop_defined || stop > 0)
				const breached = p.risk_status === "STOP BREACHED" || (stop > 0 && px > 0 && px <= stop)
				if (breached) {
					localBreached++
					continue
				}
				if (px && stopOk && stop > 0 && sh) {
					heatDollars += Math.max(0, (px - stop) * sh)
					withStop++
				} else if (sh > 0) {
					withoutStop++
				}
				const val = px * sh || p.market_value || 0
				if (val > topVal) {
					topVal = val
					topTicker = p.ticker || p.symbol || ""
				}
				const sigma = p.daily_vol || p.atr_pct || null
				if (sigma != null) {
					hasRealVol = true
				}
				const w = equity > 0 ? val / equity : 0
				posVolWeighted += w * (sigma != null ? sigma : 0.02)
			}
			if (serverHeat && typeof serverHeat.with_stop === "number") {
				withStop = serverHeat.with_stop
				withoutStop = serverHeat.without_stop || 0
				if (serverHeat.heat_dollars != null) heatDollars = serverHeat.heat_dollars
			}
			const breachCount = (serverHeat && serverHeat.stop_breached_count) || localBreached
			const stopBreached = breachCount > 0
			const postBreachR = serverHeat && serverHeat.post_breach_open_r
			const heatPct = equity > 0 ? (heatDollars / equity) * 100 : 0
			const heatR = heatDollars / Math.max(1, equity * 0.01)
			let heatAvailable = !stopBreached && withStop > 0 && withoutStop < positions.length
			if (serverHeat && serverHeat.heat_available === false) heatAvailable = false
			if (serverHeat && serverHeat.heat_available === true && !stopBreached) heatAvailable = true
			const heatQuality = serverHeat && serverHeat.heat_quality
			const stopCoverage = positions.length > 0 ? (withStop / positions.length) * 100 : 0
			let heatQualityLabel = "No open positions"
			if (withoutStop && withStop) heatQualityLabel = "Risk model partial until stop is added"
			else if (withoutStop && positions.length) heatQualityLabel = "Heat unavailable — stop not set"
			else if (withStop) heatQualityLabel = "Measured — all stops defined"
			if (serverHeat && serverHeat.heat_quality_label) heatQualityLabel = serverHeat.heat_quality_label
			let heatDisplay = "—"
			if (!positions.length) heatDisplay = "—"
			else if (stopBreached) {
				heatDisplay =
					"POST-BREACH" + (postBreachR != null ? " · " + Number(postBreachR).toFixed(2) + "R open" : "")
			} else if (withoutStop === positions.length) heatDisplay = "UNAVAILABLE"
			else if (withStop > 0 && withoutStop > 0) heatDisplay = "PARTIAL · " + withStop + "/" + positions.length
			else if (!heatAvailable) heatDisplay = "UNAVAILABLE"
			else heatDisplay = heatPct.toFixed(2) + "% · " + heatR.toFixed(2) + "R"
			const stopAnchorLabel = withStop + "/" + positions.length + " valid stop anchors"
			let var95,
				var95Pct,
				var95Quality,
				var95Tier = null,
				var95Sample = null,
				var95Warning = null
			const hv = this.histVar && this.histVar.data
			if (hv && hv.method === "historical_sim" && hv.var_95_dollar != null) {
				var95 = Math.round(Math.abs(hv.var_95_dollar))
				var95Pct = Math.abs(hv.var_95_pct || 0)
				var95Quality = "historical"
				var95Tier = hv.tier || "HISTSIM"
				var95Sample = hv.sample_size
				var95Warning = hv.warning || null
			} else {
				const portfolioVol = positions.length > 0 ? posVolWeighted : 0.02
				var95 = Math.round(equity * portfolioVol * 1.65)
				var95Pct = (var95 / equity) * 100
				var95Quality = hasRealVol ? "position-vol" : "estimate"
			}
			const topPct = equity > 0 ? (topVal / equity) * 100 : 0
			const heatColor = stopBreached
				? "red"
				: heatAvailable && heatPct >= 6
					? "red"
					: heatAvailable && heatPct >= 4
						? "amber"
						: heatDisplay.startsWith("PARTIAL") || heatDisplay === "UNAVAILABLE"
							? "amber"
							: "green"
			const heatPctClass = stopBreached
				? "text-red-400"
				: heatDisplay.startsWith("PARTIAL") || heatDisplay === "UNAVAILABLE" || !heatAvailable
					? "text-amber-300"
					: heatPct >= 6
						? "text-red-400"
						: heatPct >= 4
							? "text-amber-300"
							: "text-green-400"
			let partialRiskMsg = ""
			if (stopBreached && serverHeat && serverHeat.post_breach_note) partialRiskMsg = serverHeat.post_breach_note
			else if (stopBreached && serverHeat && serverHeat.heat_warning) partialRiskMsg = serverHeat.heat_warning
			else if (withoutStop > 0 && withStop > 0)
				partialRiskMsg =
					"Risk model partial until stop is added on " +
					withoutStop +
					" position(s). Heat excludes undefined risk."
			else if (withoutStop > 0 && withStop === 0)
				partialRiskMsg = "Heat unavailable — stop not set. Risk model partial until stop is added."
			return {
				equity,
				heatDollars,
				heatPct,
				heatR,
				count: positions.length,
				withStop,
				withoutStop,
				stopCoverage,
				heatAvailable,
				stopBreached,
				breachCount,
				heatQualityLabel,
				heatDisplay,
				stopAnchorLabel,
				topPct,
				topTicker,
				var95,
				var95Pct,
				var95Quality,
				var95Tier,
				var95Sample,
				var95Warning,
				heatColor,
				heatPctClass,
				partialRiskMsg,
			}
		},
		pfBenchmarkStatsOk() {
			const bi = this.pfDecision && this.pfDecision.benchmark_intel
			if (bi && bi.stats_reliable === true) return true
			const eq = this.pfEquity
			if (eq && eq.stats_reliable === true) return true
			const cd = this.pfDecision && this.pfDecision.curve_diagnostics
			return !!(cd && cd.stats_reliable === true)
		},
		pfDemoteResearch() {
			const cre = this.pfDecision && this.pfDecision.critical_risk_event
			return !!(cre && cre.active)
		},
		pfPosRisk(pos) {
			const px = pos.current_price || pos.entry_price || pos.avg_cost || 0
			const entry = pos.entry_price || pos.avg_cost || 0
			const stop = Number(pos.stop_price || pos.current_stop || pos.initial_stop || pos.stop || 0)
			const stopDefined = !!(pos.stop_defined || stop > 0)
			const risk = stopDefined && entry ? Math.abs(entry - stop) : entry * 0.05
			const t1 = pos.target_1r || (stopDefined && entry ? entry + risk : null)
			const t2 = pos.target_2r || (stopDefined && entry ? entry + 2 * risk : null)
			const unrealR =
				stopDefined && pos.unrealized_r != null
					? pos.unrealized_r
					: stopDefined && px && entry
						? (px - entry) / risk
						: null
			const distPct =
				pos.distance_to_stop_pct != null
					? pos.distance_to_stop_pct
					: stopDefined && px
						? ((px - stop) / px) * 100
						: null
			const distUsd = pos.distance_to_stop_usd
			const alloc = ((this.pfDecision && this.pfDecision.allocation_monitor) || []).find(
				(r) => (r.asset || "").toUpperCase() === (pos.ticker || "").toUpperCase(),
			)
			const allocAction = alloc ? alloc.action_required : null
			const driftPct = alloc ? Number(alloc.drift_pct || 0) : null
			let nextAction = allocAction || pos.next_action || (stopDefined ? "MONITOR" : "SET STOP")
			if (allocAction && String(allocAction).includes("TRIM")) nextAction = "TRIM · overweight vs policy cap"
			else if (allocAction === "ADD") nextAction = "ADD · underweight vs target"
			else if (allocAction === "HOLD") nextAction = "HOLD · at target"
			const riskStatus = stopDefined ? pos.risk_status || "IN TRADE" : "—"
			return {
				stopDefined,
				anchorBadge: "NO STOP PLAN",
				initStopLabel: stopDefined ? "$" + stop.toFixed(2) : "—",
				currStopLabel: stopDefined ? "$" + stop.toFixed(2) : "—",
				t1Label: t1 ? "$" + Number(t1).toFixed(2) : "—",
				t2Label: t2 ? "$" + Number(t2).toFixed(2) : "—",
				unrealR,
				unrealRLabel: unrealR != null ? unrealR.toFixed(2) + "R open" : "—",
				distStopLabel:
					distPct != null
						? distPct.toFixed(1) + "% / $" + (distUsd != null ? Math.abs(distUsd).toFixed(0) : "?")
						: "—",
				riskStatus,
				riskStatusClass: stopDefined
					? riskStatus.includes("BREACH")
						? "text-red-400"
						: riskStatus.includes("UNDEF") || riskStatus.includes("MISSING")
							? "text-amber-300"
							: "text-green-400"
					: "text-red-400",
				nextAction,
				driftPct,
				nextActionClass:
					nextAction.includes("EXIT") || nextAction.includes("SET") || nextAction.includes("NO STOP")
						? "pr"
						: nextAction.includes("TRIM") || nextAction.includes("TRAIL")
							? "pa"
							: nextAction.includes("ADD")
								? "pg"
								: "pw",
			}
		},
		pfSortedPositions() {
			const positions = (this.pf && this.pf.positions) || []
			const monitor = (this.pfDecision && this.pfDecision.allocation_monitor) || []
			const rank = { TRIM: 0, ADD: 1, HOLD: 2 }
			const pri = { high: 0, medium: 1, low: 2 }
			const byTicker = Object.fromEntries(monitor.map((r) => [(r.asset || "").toUpperCase(), r]))
			return [...positions].sort((a, b) => {
				const ra = byTicker[(a.ticker || "").toUpperCase()] || {}
				const rb = byTicker[(b.ticker || "").toUpperCase()] || {}
				const pa = rank[ra.action_required] ?? 9
				const pb = rank[rb.action_required] ?? 9
				if (pa !== pb) return pa - pb
				const pria = pri[ra.priority] ?? 9
				const prib = pri[rb.priority] ?? 9
				if (pria !== prib) return pria - prib
				return Math.abs(Number(rb.drift_pct || 0)) - Math.abs(Number(ra.drift_pct || 0))
			})
		},
		pfBrokerSource() {
			const link = this.pfDecision && this.pfDecision.ibkr_linkage
			let pill = link
				? link.source_pill
				: this.pf.source === "ibkr"
					? this.cc_status.ibkr_mode === "live"
						? "IBKR LIVE"
						: "IBKR PAPER"
					: "MANUAL"
			if ((!link || pill === "MANUAL") && this.cc_status && this.cc_status.ibkr_connected) {
				pill = this.cc_status.ibkr_mode === "live" ? "IBKR LIVE" : "IBKR PAPER"
			}
			const pillClass =
				pill.includes("LIVE") || pill.includes("PAPER") || pill === "MIXED"
					? "color:var(--green)"
					: pill === "MANUAL"
						? "color:var(--blue)"
						: "color:var(--amber)"
			return { pill, pillClass }
		},
		pfPrioritySummary() {
			const link = this.pfDecision?.ibkr_linkage || {}
			const risk = this.pfRisk()
			const action = this.pfDecision?.portfolio_action_now || {}
			const truth = link.broker_truth ? "Broker truth 已確認" : "Broker truth 未確認"
			const sync = (link.sync_quality || "—").replace(/_/g, " ")
			let riskLine = "Risk contained"
			if (risk.stopBreached) riskLine = "Stop breached — act before new adds"
			else if ((risk.topPct || 0) >= 12) riskLine = "Single-name concentration elevated"
			else if ((this.pfDecision?.risk_state?.sector_pct || 0) >= 25) riskLine = "Sector concentration elevated"
			else if (!risk.heatAvailable) riskLine = "Heat model partial — define stops first"
			let posture = "Normal risk posture"
			let allocateNow = true
			let allocateReason = "Can review adds within policy limits"
			if (!link.broker_truth) {
				posture = "Sync-first posture"
				allocateNow = false
				allocateReason = "Broker truth 未確認前，先對齊 local vs broker。"
			} else if (risk.stopBreached) {
				posture = "Protect capital"
				allocateNow = false
				allocateReason = "有 stop breach，先處理風險，再談新增 allocation。"
			} else if ((risk.topPct || 0) >= 12 || (this.pfDecision?.risk_state?.sector_pct || 0) >= 25) {
				posture = "Concentration capped"
				allocateNow = false
				allocateReason = "集中度過高，先 trim / rebalance。"
			} else if (!risk.heatAvailable) {
				posture = "Partial risk model"
				allocateNow = false
				allocateReason = "Heat / stop 覆蓋未齊，先補風控錨點。"
			}
			const next = action.best_action || action.decision || link.local_model_note || "Review portfolio state"
			return {
				truth,
				sync,
				riskLine,
				next,
				posture,
				allocateNow,
				allocateLabel: allocateNow ? "可加倉 · Can allocate" : "先停新增 · Hold adds",
				allocateReason,
			}
		},
		todayFocusAuthorityChip() {
			return this.normalizedAuthorityChipForTab("today", {
				badge: String(this.today7.todays_decision?.deploy_posture || "").toUpperCase(),
				authority: "monitor_only",
			})
		},
		dosVerdict() {
			const d = this.dos && this.dos.data
			if (!d) return { label: "—", pill: "pw", color: "border", conf: null, reason: "" }
			const raw = (d.confidence || d.signal?.confidence)?.final
			const conf = raw != null && raw !== "" ? Number(raw) : null
			const tradeOK = d.regime ? d.regime.should_trade !== false : true
			const conflict = (d.conflict || d.signal?.conflict)?.conflict_level || "LOW"
			const sect = d.sector || d.signal?.sector || {}
			const leader = sect.leader_status === "LEADER"
			if (!tradeOK)
				return {
					label: "NO TRADE",
					pill: "pr",
					color: "red",
					conf,
					reason: "Regime gate is OFF — VIX/breadth unfavorable. Sit out.",
				}
			if (conflict === "HIGH")
				return {
					label: "AVOID",
					pill: "pr",
					color: "red",
					conf,
					reason: "High signal conflict — wait for confirmation.",
				}
			if (conf != null && conf >= 0.7 && conflict === "LOW" && leader)
				return {
					label: "TRADE",
					pill: "pg",
					color: "green",
					conf,
					reason: "High conviction · low conflict · sector leader. Size at 1R.",
				}
			if (conf != null && conf >= 0.55 && conflict !== "HIGH")
				return {
					label: "WATCH",
					pill: "pa",
					color: "amber",
					conf,
					reason: "Setup forming — monitor for trigger; do not chase.",
				}
			return {
				label: "PASS",
				pill: "pw",
				color: "border",
				conf,
				reason: "Insufficient conviction. Look elsewhere.",
			}
		},
		dosUnified() {
			const u = this.dos?.intel?.unified_decision
			const tp = this.dos?.data?.trade_plan || {}
			const rrDisplay = (src) => {
				if (src == null || src === "") return null
				const n = this.parseRR(src)
				return n > 0 ? n.toFixed(1) : String(src)
			}
			if (u) {
				const rr = u.rr_ratio_display || rrDisplay(u.rr_ratio) || rrDisplay(tp.rr_ratio_label) || "—"
				const conf =
					u.confidence_available === false
						? null
						: u.confidence != null
							? u.confidence
							: this.dosVerdict().conf || null
				return { ...u, confidence: conf, rr_ratio_display: rr }
			}
			const v = this.dosVerdict()
			const rr = rrDisplay(tp.rr_ratio) || tp.rr_ratio_label || "—"
			const conf = v.conf || null
			return {
				label: v.label,
				pill: v.pill,
				color: v.color,
				confidence: conf,
				confidence_available: conf != null && conf > 0,
				confidence_label: conf != null && conf > 0 ? null : "Pending calibration",
				reason: v.reason,
				entry_zone: tp.entry_zone,
				stop: tp.stop,
				target_1r: tp.target_1r,
				target_2r: tp.target_2r,
				rr_ratio: tp.rr_ratio,
				rr_ratio_display: rr,
				invalidation: tp.invalidation,
			}
		},
		dosFormatConfidence(u) {
			return this.dosFormatDecisionConfidence(u)
		},
		dosConfidenceMetrics() {
			const intel = this.dos?.intel
			const u = this.dosUnified()
			return (
				intel?.confidence_metrics || {
					decision_confidence_pct: u.confidence_pct,
					decision_confidence_label: u.decision_confidence_label || u.confidence_label,
					decision_confidence_available: u.decision_confidence_available ?? u.confidence_available,
					decision_confidence_source: u.decision_confidence_source || u.confidence_source,
					thesis_quality: u.thesis_quality,
					thesis_quality_display: u.thesis_quality_display,
					thesis_quality_label: u.thesis_quality_label,
				}
			)
		},
		dosFormatDecisionConfidence(u) {
			const m = this.dosConfidenceMetrics()
			const src = u || this.dosUnified()
			const pct = m.decision_confidence_pct ?? src.confidence_pct
			if (m.decision_confidence_available === false || pct == null || pct <= 0) {
				return (
					"Decision confidence · " +
					(m.decision_confidence_label || src.confidence_label || "Pending calibration")
				)
			}
			const proxy =
				m.decision_confidence_source === "confluence" || src.confidence_source === "confluence"
					? " (proxy)"
					: ""
			const lbl = m.decision_confidence_label || ""
			return "Decision confidence · " + pct + "%" + proxy + (lbl ? " · " + lbl : "")
		},
		dosFormatThesisQuality() {
			const m = this.dosConfidenceMetrics()
			let s = ""
			if (m.thesis_quality_display) s = "Thesis quality · " + m.thesis_quality_display
			else if (m.thesis_quality != null) s = "Thesis quality · " + m.thesis_quality + "/100"
			if (m.net_edge_display) return (s ? s + " · " : "") + m.net_edge_display
			return s
		},
		dosSizeExplanation() {
			if (this.dossierSizingBlocked()) {
				const r = this.dossierSizingBlockedReason()
				if (window.CCHelpers && CCHelpers.dossierSizingExplanation)
					return CCHelpers.dossierSizingExplanation(true, r)
				if (r === "confirm_only") return "No sizing guidance in confirm-only mode"
				if (r === "failed" || r === "partial") return "Sizing blocked until live dossier loads"
				if (r === "rr_unavailable") return "Size unavailable — R:R not confirmed"
				return "Size unavailable"
			}
			return this.dos?.intel?.size_info?.size_explanation || ""
		},
		dosTradePlanLevelsBlank() {
			const u = this.dosUnified()
			const tp = this.dos?.data?.trade_plan || {}
			const ez = tp.entry_zone || u.entry_zone
			const hasEntry = ez && ez.length >= 2 && ez[0] != null && ez[1] != null
			const stop = tp.stop || u.stop
			const t1 = tp.target_1r || u.target_1r
			const t2 = tp.target_2r || u.target_2r
			return !hasEntry && !stop && !t1 && !t2
		},
		dosTradePlanNoteValue() {
			const tp = this.dos?.data?.trade_plan || {}
			const opts = {
				note: tp.note,
				setup_type: tp.setup_type,
				research_only: this.dossierResearchOnly(),
				levels_blank: this.dosTradePlanLevelsBlank(),
			}
			if (window.CCHelpers && CCHelpers.dossierTradePlanNote) return CCHelpers.dossierTradePlanNote(opts)
			if (opts.research_only && opts.levels_blank) return "Live structure unavailable — confirm-only dossier"
			if (opts.levels_blank) return "Live structure unavailable"
			const note = String(tp.note || tp.setup_type || "").trim()
			return note || "Structure-based plan"
		},
		dosTradePlanRows() {
			const tp = this.dos?.data?.trade_plan || {}
			const u = this.dosUnified()
			const ez = tp.entry_zone || u.entry_zone
			const fmt = (v) => (v != null && v !== "" ? "$" + v : "—")
			const rows = [
				{ label: "Entry zone", value: ez && ez.length >= 2 ? "$" + ez[0] + "–$" + ez[1] : "—" },
				{ label: "Stop", value: fmt(tp.stop || u.stop) },
				{
					label: "T1 / T2",
					value:
						tp.target_1r || u.target_1r
							? "$" + (tp.target_1r || u.target_1r) + " / $" + (tp.target_2r || u.target_2r)
							: "—",
				},
				{ label: "R:R", value: u.rr_ratio_display || tp.rr_ratio_label || "—" },
				{ label: "Invalidation", value: String(tp.invalidation || u.invalidation || "—") },
				{ label: "Note", value: this.dosTradePlanNoteValue() },
			]
			return rows
		},
		dosSizeShares() {
			if (this.dossierSizingBlocked()) return 0
			const backend = this.dos?.intel?.size_info?.shares
			if (backend != null && backend > 0) return backend
			const d = this.dos?.data
			if (!d?.price) return 0
			const u = this.dosUnified()
			const stop = u.stop
			const ez = u.entry_zone
			let risk = 0
			if (ez && ez.length >= 2 && stop != null) {
				const mid = (Number(ez[0]) + Number(ez[1])) / 2
				risk = Math.abs(mid - Number(stop))
			}
			if (!risk && d.technicals?.atr) risk = 1.5 * d.technicals.atr
			if (!risk) return 0
			return Math.max(0, Math.floor((this.dosEquity() * 0.01) / risk))
		},
		dosSetTab(t) {
			this.dos.subTab = t
			if (t === "technicals")
				this.$nextTick(() => {
					this.renderDossierChart()
					this.renderBenchChart()
				})
			if (t === "options" && !this.dos.optionsData) this.fetchDosOptions()
			if (t === "peers" && !this.dosPeersRows().length && !this.dos.peersLoading) this.fetchDosPeers()
			if (t === "workstation" && this.dos.ticker && !this.dosWorkstation.data) this.fetchQuoteWorkstation()
		},
		dosFundamentals() {
			const p9 = this.dos?.data?._p9?.fundamentals || this.dos?.intel?.p9?.fundamentals
			if (p9) return p9
			const fb = this.dos?.intel?.fundamentals_block
			if (fb?.raw) return fb.raw
			if (fb?.has_data) return fb
			return null
		},
		dosHasLoadedData() {
			const d = this.dos?.data
			if (d && (d.symbol || d.price)) return true
			const intel = this.dos?.intel
			return !!(
				intel &&
				((intel.dossier && (intel.dossier.symbol || intel.dossier.price)) ||
					intel.unified_decision ||
					intel.narrative)
			)
		},
		dosPeersRows() {
			const p = this.dos?.peers
			const rows = p && (p.table || p.rankings || p.peers)
			if (Array.isArray(rows) && rows.length) return rows
			const block = this.dos?.intel?.peers_block?.rows
			return Array.isArray(block) ? block : []
		},
		async fetchDosPeers() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk || this.dos.peersLoading) return
			this.dos.peersLoading = true
			try {
				const r = await this.ccFetch("/api/dossier/" + encodeURIComponent(tk) + "/peers", {
					retries: 2,
					backoff: 600,
					timeoutMs: 20000,
				})
				if (r && r.ok) this.dos.peers = await r.json()
			} catch (e) {
				console.warn("peers", e)
			} finally {
				this.dos.peersLoading = false
			}
		},
		async fetchDosOptions() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk) return
			this.dos.optionsLoading = true
			try {
				const r = await fetch("/api/live/options/" + encodeURIComponent(tk))
				this.dos.optionsData = r.ok ? await r.json() : null
			} catch (e) {
				console.warn("options", e)
				this.dos.optionsData = null
			} finally {
				this.dos.optionsLoading = false
			}
		},
		flowIbkrDraft(c) {
			const tk = ((c && c.underlying) || "").toUpperCase()
			if (!tk) return
			const cp = (c.call_put || c.options_detail?.call_put || "C").toString().toUpperCase()
			const isPut = cp === "P" || cp === "PUT"
			this.dos.ticker = tk
			this.ibkr.orderForm = {
				...this.ibkr.orderForm,
				symbol: tk,
				secType: "STK",
				action: isPut ? "SELL" : "BUY",
				qty: this.dosSizeShares() || 1,
				orderType: "MKT",
				limitPrice: "",
				useBracket: false,
			}
			alert("Flow → IBKR: paper order draft loaded — review in IBKR tab.")
			this.switchTab("ibkr")
		},
		opsSectionActive(key) {
			const s = this.opsConsole && this.opsConsole.data && this.opsConsole.data.section_states
			return s && s[key] && s[key].state === "active"
		},
		opsSectionShowAdvanced() {
			const s = this.opsConsole && this.opsConsole.data && this.opsConsole.data.section_states
			if (!s) return !!(this.selfLearn.status || this.risk.summary || this.exec.metrics)
			return Object.values(s).some((v) => v && v.state === "active")
		},
		opsAdvancedCollapsedCopy() {
			const H = window.CCHelpers || {}
			const d = this.opsConsole && this.opsConsole.data && this.opsConsole.data.diagnostics
			const note =
				(d && d.collapsed_diagnostics_note) ||
				"Engine off or insufficient trade sample — Ops experimental panels below (self-learning, Thompson sizing, execution metrics) need runtime evidence before they affect capital. Dossier research loads from market data independently."
			return H.localizeOpsAdvancedDiagnosticsCopy ? H.localizeOpsAdvancedDiagnosticsCopy(note) : note
		},
		opsAdvancedDiagnosticsTitle() {
			const H = window.CCHelpers || {}
			return H.opsAdvancedDiagnosticsTitle ? H.opsAdvancedDiagnosticsTitle() : "進階診斷 · Advanced diagnostics"
		},
		opsAdvancedDiagnosticsCollapsedTitle() {
			const H = window.CCHelpers || {}
			return H.opsAdvancedDiagnosticsCollapsedTitle
				? H.opsAdvancedDiagnosticsCollapsedTitle()
				: "進階診斷（收合） · Advanced diagnostics (collapsed)"
		},
		opsAdvancedSectionKey(key) {
			const H = window.CCHelpers || {}
			return H.localizeOpsAdvancedSectionKey
				? H.localizeOpsAdvancedSectionKey(key)
				: String(key || "").replace(/_/g, " ")
		},
		opsAdvancedSectionStatus(section) {
			const H = window.CCHelpers || {}
			const label = (section && section.label) || ""
			return H.localizeOpsAdvancedSectionLabel ? H.localizeOpsAdvancedSectionLabel(label) : label
		},
		opsSectionInactiveMsg(key) {
			const H = window.CCHelpers || {}
			const s = this.opsConsole && this.opsConsole.data && this.opsConsole.data.section_states
			if (s && s[key]) {
				const label = H.localizeOpsAdvancedSectionLabel
					? H.localizeOpsAdvancedSectionLabel(s[key].label || "inactive")
					: s[key].label || "inactive"
				const detail = H.localizeOpsAdvancedSectionDetail
					? H.localizeOpsAdvancedSectionDetail(s[key].detail || "")
					: s[key].detail || ""
				return label + ": " + detail
			}
			const fallback = "Start engine or refresh ops console for evidence."
			return H.localizeOpsAdvancedSectionDetail ? H.localizeOpsAdvancedSectionDetail(fallback) : fallback
		},
		opsShowHttp500Banner() {
			return this.opsRuntime.http_status === 500
		},
		opsHttp500BannerText() {
			const H = this._opsH()
			return H.opsHttp500BannerText
				? H.opsHttp500BannerText()
				: "OPS UNAVAILABLE — runtime status endpoint failed (HTTP 500)."
		},
		opsPaperLiveBoundaryTitle() {
			const H = this._opsH()
			return H.opsPaperLiveBoundaryTitle ? H.opsPaperLiveBoundaryTitle() : "Paper / live boundary"
		},
		opsLastSuccessfulTimesTitle() {
			const H = this._opsH()
			return H.opsLastSuccessfulTimesTitle ? H.opsLastSuccessfulTimesTitle() : "Last successful times"
		},
		opsOperationalEventsTitle() {
			const H = this._opsH()
			return H.opsOperationalEventsTitle ? H.opsOperationalEventsTitle() : "Operational events"
		},
		opsWhyNoSignalsTitle() {
			const H = this._opsH()
			return H.opsWhyNoSignalsTitle ? H.opsWhyNoSignalsTitle() : "Why no signals today?"
		},
		opsFailedFreshnessHint() {
			const H = this._opsH()
			return H.opsFailedFreshnessHint
				? H.opsFailedFreshnessHint()
				: "failed_freshness = scanner cache warming, not 7 separate failures."
		},
		opsWhyNoSignalsGateLabel(gate) {
			const H = this._opsH()
			return H.localizeOpsWhyNoSignalsGate ? H.localizeOpsWhyNoSignalsGate(gate) : String(gate || "")
		},
		opsSignalZeroReasonLabel(r) {
			const H = this._opsH()
			const t = (r && r.label) || ""
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsPhase9EnginesTitle() {
			const H = this._opsH()
			return H.opsPhase9EnginesTitle ? H.opsPhase9EnginesTitle() : "Phase 9 Engines"
		},
		opsPhase9LoadFailed() {
			const H = this._opsH()
			return H.opsPhase9LoadFailed
				? H.opsPhase9LoadFailed()
				: "Phase 9 engines failed to load — check server logs"
		},
		opsPhase9StatusLabel(loaded) {
			const H = this._opsH()
			const t = loaded ? "LOADED" : "OFFLINE"
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsPhase9ComponentActive() {
			const H = this._opsH()
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText("Active") : "Active"
		},
		opsCacheStatisticsTitle() {
			const H = this._opsH()
			return H.opsCacheStatisticsTitle ? H.opsCacheStatisticsTitle() : "Cache Statistics"
		},
		opsCacheStatKeyLabel(k) {
			const H = this._opsH()
			return H.localizeOpsDictKey ? H.localizeOpsDictKey(k) : String(k || "").replace(/_/g, " ")
		},
		opsSelfLearningEngineTitle() {
			const H = this._opsH()
			return H.opsSelfLearningEngineTitle ? H.opsSelfLearningEngineTitle() : "Self-Learning Engine"
		},
		opsSelfLearnLabel(key) {
			const H = this._opsH()
			return H.opsSelfLearnLabel ? H.opsSelfLearnLabel(key) : key
		},
		opsWhatThisMeansTitle() {
			const H = this._opsH()
			return H.opsWhatThisMeansTitle ? H.opsWhatThisMeansTitle() : "What this means"
		},
		opsBoardStateCachedNote() {
			const H = this._opsH()
			return H.opsBoardStateCachedNote
				? H.opsBoardStateCachedNote()
				: "Board state elsewhere may be cached, fallback, or precomputed — not proof the engine ran this session."
		},
		opsEngineStoppedHelpCopy() {
			const H = this._opsH()
			return H.opsEngineStoppedHelpCopy
				? H.opsEngineStoppedHelpCopy()
				: "Start the trading loop for cycles, cache, and runtime evidence. Or set CC_AUTO_START_ENGINE=1 in Docker/env to start on boot."
		},
		opsStartEngineLabel() {
			const H = this._opsH()
			return H.opsStartEngineLabel ? H.opsStartEngineLabel(!!this.ops.engineStarting) : "▶ Start engine"
		},
		opsViewErrorLogLabel() {
			const H = this._opsH()
			return H.opsViewErrorLogLabel ? H.opsViewErrorLogLabel() : "View Error Log"
		},
		opsRecoveryRunbookTitle() {
			const H = this._opsH()
			return H.opsRecoveryRunbookTitle ? H.opsRecoveryRunbookTitle() : "恢復手冊 · Recovery runbook"
		},
		opsBlocksCapitalTitle() {
			const H = this._opsH()
			return H.opsBlocksCapitalTitle ? H.opsBlocksCapitalTitle() : "阻擋資金 · Blocks capital"
		},
		opsSafeDegradedTitle() {
			const H = this._opsH()
			return H.opsSafeDegradedTitle ? H.opsSafeDegradedTitle() : "降級模式可安全操作 · Safe in degraded mode"
		},
		opsNoHardBlocksCopy() {
			const H = this._opsH()
			return H.opsNoHardBlocksCopy ? H.opsNoHardBlocksCopy() : "No hard blocks flagged from Ops snapshot"
		},
		opsPlatformUpdatesTitle() {
			const H = this._opsH()
			return H.opsPlatformUpdatesTitle ? H.opsPlatformUpdatesTitle() : "平台更新 · Platform updates"
		},
		opsSessionErrorLogTitle() {
			const H = this._opsH()
			return H.opsSessionErrorLogTitle ? H.opsSessionErrorLogTitle() : "Session 錯誤日誌 · Session error log"
		},
		opsSeeRecoveryRunbookHint() {
			const H = this._opsH()
			const retry = (this.opsRecoveryGuide().retry || [])[0] || "wait for /health mode=full"
			const prefix = H.opsSeeRecoveryRunbookPrefix
				? H.opsSeeRecoveryRunbookPrefix()
				: "見上方恢復手冊 · See Recovery runbook above"
			const hint = H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(retry) : retry
			return prefix + " — " + hint
		},
		opsBootTimeLine() {
			const H = this._opsH()
			return H.opsBootTimeLine ? H.opsBootTimeLine(this.opsConsole.data?.startup_time) : ""
		},
		opsLastCycleLine() {
			const H = this._opsH()
			return H.opsLastCycleLine
				? H.opsLastCycleLine(this.opsConsole.data?.last_times?.last_successful_engine_cycle)
				: ""
		},
		opsIbkrSessionInactiveTitle() {
			const H = this._opsH()
			return H.opsIbkrSessionInactiveTitle ? H.opsIbkrSessionInactiveTitle() : "IBKR session not active"
		},
		opsIbkrSessionNote() {
			const H = this._opsH()
			const reachable = !!this.opsConsole.data?.ibkr?.gateway_reachable
			return reachable
				? H.opsIbkrGatewayReachableNote
					? H.opsIbkrGatewayReachableNote()
					: "Gateway signals present — confirm login on IBKR tab."
				: H.opsIbkrNoSessionNote
					? H.opsIbkrNoSessionNote()
					: "No IB API session yet. Start IB Gateway/TWS, then Connect. Raw TCP probes are disabled (CC_SKIP_IB_INSYNC avoids log spam). "
		},
		opsOpenIbkrConnectLabel() {
			const H = this._opsH()
			return H.opsOpenIbkrConnectLabel ? H.opsOpenIbkrConnectLabel() : "Open IBKR tab → Connect"
		},
		opsCriticalGapsLine() {
			const H = this._opsH()
			const flags = this.opsCriticalFlags().map((f) => (H.opsCriticalFlagText ? H.opsCriticalFlagText(f) : f))
			const prefix = H.opsCriticalGapsPrefix ? H.opsCriticalGapsPrefix() : "Runtime gaps"
			return prefix + ": " + flags.join(" · ")
		},
		opsNoCycleSessionWarning() {
			const H = this._opsH()
			return H.opsNoCycleSessionWarning
				? H.opsNoCycleSessionWarning()
				: "No engine cycle executed this session — uptime and latency below reflect API boot only, not trading loop activity."
		},
		opsNoCacheWarning() {
			const H = this._opsH()
			return H.opsNoCacheWarning
				? H.opsNoCacheWarning()
				: "Recommendation cache empty — Today/Signals boards may show stale or precomputed output."
		},
		opsTradesTodayPill() {
			const H = this._opsH()
			return H.opsTradesTodayPill
				? H.opsTradesTodayPill(this.ops.trades_today || 0)
				: "Trades today: " + (this.ops.trades_today || 0)
		},
		opsRunCycleLabel() {
			const H = this._opsH()
			return H.opsRunCycleLabel ? H.opsRunCycleLabel() : "▶ Run Cycle"
		},
		opsSelfLearnEnabledLabel(enabled) {
			const H = this._opsH()
			return H.opsSelfLearnEnabledLabel ? H.opsSelfLearnEnabledLabel(!!enabled) : enabled ? "YES" : "DISABLED"
		},
		opsEngineStoppedBannerText() {
			const H = this._opsH()
			const t = this.opsEngineStoppedBanner() || ""
			return t ? (H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t) : ""
		},
		opsWhyNoSignalsCell(w) {
			const H = this._opsH()
			return H.opsWhyNoSignalsCell ? H.opsWhyNoSignalsCell(w) : (w?.count ?? w?.note ?? "")
		},
		opsPageIntro() {
			const H = this._opsH()
			const d = this.opsConsole.data && this.opsConsole.data.diagnostics
			let intro =
				(d && d.page_intro) || "Treat this page as a diagnostics surface until fresh runtime evidence exists."
			intro = H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(intro) : intro
			if (this.opsShowHttp500Banner()) {
				intro = intro.replace(/\.$/, "")
				const suffix = H.opsHttp500IntroSuffix
					? H.opsHttp500IntroSuffix()
					: "The runtime status path is failing with HTTP 500."
				if (intro.indexOf("HTTP 500") < 0 && intro.indexOf(suffix) < 0) {
					intro += " " + suffix
				}
				if (!/\.$/.test(intro)) intro += "."
			}
			return intro
		},
		opsEngineStoppedBanner() {
			const d = this.opsConsole.data && this.opsConsole.data.diagnostics
			return (d && d.engine_stopped_banner) || null
		},
		opsSignalsTodayNote() {
			const H = this._opsH()
			const d = this.opsConsole.data && this.opsConsole.data.diagnostics
			const t = (d && d.signals_today_note) || "Signals today: " + (this.ops.signals_today || 0)
			return H.localizeOpsRuntimeText ? H.localizeOpsRuntimeText(t) : t
		},
		opsCriticalFlags() {
			const d = (this.opsConsole.data && this.opsConsole.data.diagnostics) || {}
			const flags = []
			if (this.opsShowHttp500Banner()) flags.push("runtime HTTP 500")
			if (d.engine_stopped) flags.push("engine stopped")
			if (d.no_cycles) flags.push("0 cycles")
			if (d.no_cache) flags.push("no cache")
			return flags
		},
		async fetchOpsRuntime() {
			this.opsRuntime.loading = true
			try {
				const r = await fetch("/api/ops/status")
				this.opsRuntime.http_status = r.status
				this.opsRuntime.ok = r.ok
				if (r.ok) {
					this.opsRuntime.data = await r.json()
					this.opsRuntime.error = ""
					this.opsDetail = { ...this.opsDetail, ...this.opsRuntime.data }
					if (this.opsRuntime.data.engine) {
						this.ops = {
							...this.ops,
							...this.opsRuntime.data.engine,
							components: this.ops.components || this.opsRuntime.data.components || {},
						}
					}
				} else {
					this.opsRuntime.data = null
					this.opsRuntime.error = "HTTP " + r.status
					if (r.status >= 500) this.fetchErrorLog()
				}
			} catch (e) {
				this.opsRuntime.ok = false
				this.opsRuntime.error = e.message || "runtime status failed"
			} finally {
				this.opsRuntime.loading = false
			}
		},
		changelogFallback() {
			return [
				{
					date: new Date().toISOString().slice(0, 10),
					title: this._uiText("CC platform"),
					summary: this._uiText("Built-in fallback — edit data/changelog.json for release notes."),
					surfaces: ["Ops"],
				},
			]
		},
		async fetchChangelog() {
			if (!this.changelogPanel)
				this.changelogPanel = {
					loading: false,
					loaded: false,
					error: "",
					timeout: false,
					version: "",
					product: "CC",
					entries: [],
				}
			if (this.changelogPanel.loading) return
			this.changelogPanel.loading = true
			this.changelogPanel.error = ""
			this.surfaceFetchHints.ops_updates = { loading: true, error: "", fallback: false, timed_out: false }
			try {
				const ctrl = new AbortController()
				const timer = setTimeout(() => ctrl.abort(), 8000)
				const r = await fetch("/api/ops/changelog", { signal: ctrl.signal })
				clearTimeout(timer)
				if (!r.ok) throw new Error("HTTP " + r.status)
				const d = await r.json()
				this.changelogPanel.version = d.version || ""
				this.changelogPanel.product = d.product || "CC"
				this.changelogPanel.entries = Array.isArray(d.entries) ? d.entries : []
				this.changelogPanel.loaded = true
				this.changelogPanel.timeout = false
				this.surfaceFetchHints.ops_updates = { loading: false, error: "", fallback: false, timed_out: false }
			} catch (e) {
				const timedOut = e && e.name === "AbortError"
				this.changelogPanel.timeout = timedOut
				this.changelogPanel.error = timedOut ? "timeout" : e.message || "changelog failed"
				if (!this.changelogPanel.entries.length) {
					this.changelogPanel.entries = this.changelogFallback()
				}
				const state = this.opsInferDegradedState({
					error: this.changelogPanel.error,
					fallback: !!this.changelogPanel.entries.length,
					timed_out: timedOut,
				})
				this.surfaceFetchHints.ops_updates = {
					loading: false,
					error: this.opsDegradedLine(state, this.changelogPanel.error),
					fallback: state === "fallback",
					timed_out: timedOut,
				}
			} finally {
				this.changelogPanel.loading = false
			}
		},
		async sendDiscordTestPing() {
			try {
				const r = await fetch("/api/v7/notify/test?message=" + encodeURIComponent("CC real-life notice test"), {
					method: "POST",
				})
				const d = await r.json()
				const mode = d.config?.mode || "—"
				alert(
					d.pushed_to_discord
						? `✓ Sent to Discord (${mode})`
						: `⚠ Not sent (${mode}) — check bot token, webhook, or channel name`,
				)
				this.fetchNotifyLog()
			} catch (e) {
				alert("Test failed: " + e.message)
			}
		},
		async resolveDiscordChannel() {
			try {
				const r = await fetch("/api/v7/notify/resolve-channel")
				const d = await r.json()
				alert(d.ok ? `✓ Channel resolved: ${d.channel_id}` : d.hint || "Resolve failed")
				this.fetchNotifyLog()
			} catch (e) {
				alert("Resolve failed: " + e.message)
			}
		},
		async fetchNotifyLog() {
			this.notifyLog.loading = true
			try {
				const [statusR, logR] = await Promise.allSettled([
					fetch("/api/v7/notify/status"),
					fetch("/api/v7/notify/log?limit=20"),
				])
				if (statusR.status === "fulfilled" && statusR.value.ok) {
					const st = await statusR.value.json()
					this.notifyLog.discord_configured = !!st.discord_configured
					this.notifyLog.discord_status = st
				}
				if (logR.status === "fulfilled" && logR.value.ok) {
					const lg = await logR.value.json()
					this.notifyLog.events = lg.events || []
				}
				this.notifyLog.loaded = true
			} catch (e) {
				console.warn("notify log fetch failed", e)
			} finally {
				this.notifyLog.loading = false
			}
		},
		async opsStartEngine() {
			if (this.ops.engineStarting || this.ops.running) return
			this.ops.engineStarting = true
			try {
				const r = await fetch("/api/ops/engine/start", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				const d = await r.json().catch(() => ({}))
				if (!r.ok) throw new Error(d.detail || d.error || "HTTP " + r.status)
				await this.fetchOpsRuntime()
				await this.fetchOpsConsole()
			} catch (e) {
				alert("Engine start failed: " + (e.message || e))
				this.fetchErrorLog()
			} finally {
				this.ops.engineStarting = false
			}
		},
		async fetchErrorLog() {
			this.errorLog.loading = true
			this.errorLog.error = ""
			this.surfaceFetchHints.ops_error_log = { loading: true, error: "", unavailable: false }
			try {
				const sev = encodeURIComponent(this.errorLog.filter || "all")
				const r = await fetch("/api/ops/error-log?severity=" + sev + "&limit=80")
				if (!r.ok) throw new Error("HTTP " + r.status)
				const d = await r.json()
				this.errorLog.entries = d.entries || []
				this.errorLog.total = d.total_buffered || this.errorLog.entries.length
				this.surfaceFetchHints.ops_error_log = { loading: false, error: "", unavailable: false }
			} catch (e) {
				const msg = e.message || "error log failed"
				this.errorLog.error = msg
				this.errorLog.entries = []
				const state = this.opsInferDegradedState({ error: msg })
				this.surfaceFetchHints.ops_error_log = {
					loading: false,
					error: this.opsDegradedLine(state, msg),
					unavailable: true,
				}
			} finally {
				this.errorLog.loading = false
			}
		},

		async fetchDesk() {
			try {
				const [p, m] = await Promise.all([
					fetch("/api/desk/portfolio")
						.then((r) => (r.ok ? r.json() : null))
						.catch(() => null),
					fetch("/api/desk/monitor")
						.then((r) => (r.ok ? r.json() : null))
						.catch(() => null),
				])
				if (p) this.desk.portfolio = p
				if (m) this.desk.monitor = m
			} catch (e) {
				console.warn("desk fetch:", e)
			}
		},
		deskSeriesPts(series) {
			return (series || []).map((x) => (typeof x === "number" ? x : (x.equity ?? x.value ?? 0)))
		},
		deskSparkSvg(primary, overlay, w, h) {
			const ptsA = this.deskSeriesPts(primary)
			const ptsB = this.deskSeriesPts(overlay)
			if (!ptsA.length && !ptsB.length)
				return '<div style="text-align:center;font-size:10px;color:var(--t3);padding:12px">no curve data</div>'
			const pad = 4,
				combined = ptsA.length ? ptsA : ptsB
			const min = Math.min(...combined, ...ptsB)
			const max = Math.max(...combined, ...ptsB)
			const rng = max - min || 1
			const mkPath = (pts, color, dash) => {
				if (!pts.length) return ""
				const sx = (w - pad * 2) / Math.max(pts.length - 1, 1)
				const d = pts
					.map((v, i) => {
						const x = pad + i * sx
						const y = pad + (h - pad * 2) * (1 - (v - min) / rng)
						return (i ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1)
					})
					.join(" ")
				return (
					'<path d="' +
					d +
					'" fill="none" stroke="' +
					color +
					'" stroke-width="1.5"' +
					(dash ? ' stroke-dasharray="4 3"' : "") +
					"/>"
				)
			}
			return (
				'<svg width="' +
				w +
				'" height="' +
				h +
				'" viewBox="0 0 ' +
				w +
				" " +
				h +
				'">' +
				mkPath(ptsA, "#00d4aa", false) +
				mkPath(ptsB, "#58a6ff", true) +
				"</svg>"
			)
		},
		leaderQualityClass(q) {
			return { verified: "pg", delayed: "pa", derived: "pb", inferred: "pp", speculative: "pr" }[q] || "pw"
		},
		async fetchLeadersDashboard() {
			try {
				const r = await fetch("/api/leaders/dashboard")
				if (r.ok) this.leadersDash = await r.json()
			} catch (e) {
				console.warn("leaders dash", e)
			}
		},
		async fetchLeadersHub() {
			this.leadersHub.loading = true
			try {
				let u = "/api/leaders?"
				if (this.leadersFilter.category)
					u += "category=" + encodeURIComponent(this.leadersFilter.category) + "&"
				if (this.leadersFilter.quality)
					u += "source_quality=" + encodeURIComponent(this.leadersFilter.quality) + "&"
				if (this.leadersFilter.search) u += "search=" + encodeURIComponent(this.leadersFilter.search) + "&"
				const r = await fetch(u)
				if (r.ok) {
					const d = await r.json()
					this.leadersHub.leaders = d.leaders || []
				}
			} catch (e) {
				console.warn("leaders hub", e)
			} finally {
				this.leadersHub.loading = false
			}
		},
		async openLeaderDetail(id) {
			try {
				const r = await fetch("/api/leaders/" + encodeURIComponent(id))
				if (r.ok) this.leadersDetail = await r.json()
			} catch (e) {
				console.warn("leader detail", e)
			}
		},
		async fetchLeadersConsensus() {
			try {
				const u =
					"/api/consensus?min_overlap=2&verified_only=" + (this.leadersConsensusVerified ? "true" : "false")
				const r = await fetch(u)
				if (r.ok) this.leadersConsensus = await r.json()
			} catch (e) {
				console.warn("consensus", e)
			}
		},
		async openConsensusTicker(t) {
			try {
				const r = await fetch("/api/consensus/ticker/" + encodeURIComponent(t))
				if (r.ok) {
					const d = await r.json()
					alert(t + ": consensus " + JSON.stringify(d.consensus || {}, null, 0).slice(0, 200))
				}
			} catch (e) {}
		},
		async fetchLeadersFlow() {
			try {
				const r = await fetch("/api/flow/tracked")
				if (r.ok) this.leadersFlow = await r.json()
			} catch (e) {
				console.warn("flow", e)
			}
		},
		async fetchLeadersBaskets() {
			try {
				const r = await fetch("/api/baskets")
				if (r.ok) this.leadersBaskets = await r.json()
			} catch (e) {
				console.warn("baskets", e)
			}
		},
		async fetchLeadersAlerts() {
			try {
				const r = await fetch("/api/alerts/leaders?unseen_only=false")
				if (r.ok) this.leadersAlerts = await r.json()
			} catch (e) {
				console.warn("alerts", e)
			}
		},

		async fetchLeaders() {
			this.leadersPanel.loading = true
			this.leadersPanel.error = ""
			try {
				const r = await this.ccFetch("/api/v7/leaders-tracker?limit=12", { retries: 2, backoff: 500 })
				if (!r || !r.ok) throw new Error("HTTP " + (r ? r.status : "fail"))
				this.leadersPanel.data = await r.json()
			} catch (e) {
				this.leadersPanel.error = e.message || "leaders failed"
				this.leadersPanel.data = null
			} finally {
				this.leadersPanel.loading = false
			}
		},
		dosIbkrPaperDraft() {
			if (this.dossierSizingBlocked()) {
				alert("Sizing blocked — wait for decision-grade dossier before IBKR handoff.")
				return
			}
			const tk = (this.dos.ticker || this.dos.data?.symbol || "").toUpperCase()
			const u = this.dosUnified()
			const qty = this.dosSizeShares() || 1
			this.ibkr.orderForm = {
				...this.ibkr.orderForm,
				symbol: tk,
				secType: "STK",
				action: "BUY",
				qty,
				orderType: "LMT",
				limitPrice: String(this.dos.data?.price || ""),
				useBracket: true,
				stopPrice: String(u.stop || ""),
				targetPrice: String(u.target_1r || ""),
			}
			this.ibkr.workingBracket = {
				symbol: tk,
				quantity: qty,
				entry_price: this.dos.data?.price,
				stop_price: u.stop,
				take_profit: u.target_1r,
				draft: true,
			}
			alert("Paper bracket draft loaded in IBKR tab — review before submit.")
			this.switchTab("ibkr")
		},
		dosIbkrSetAlert() {
			if (this.dossierSizingBlocked()) {
				alert("Sizing blocked — wait for decision-grade dossier before IBKR handoff.")
				return
			}
			const tk = (this.dos.ticker || this.dos.data?.symbol || "").toUpperCase()
			const u = this.dosUnified()
			const stop = u.stop
			if (!stop) {
				alert("No stop level in trade plan — set structure first.")
				return
			}
			this.ibkr.orderForm = {
				...this.ibkr.orderForm,
				symbol: tk,
				secType: "STK",
				action: "SELL",
				qty: this.dosSizeShares() || 1,
				orderType: "STP",
				limitPrice: "",
				stopPrice: String(stop),
				useBracket: false,
			}
			alert("Stop alert draft: STP SELL @ $" + stop + " — open IBKR tab to connect and submit.")
			this.switchTab("ibkr")
		},
		async fetchSignals() {
			try {
				const r = await fetch("/api/recommendations")
				if (!r.ok) throw 0
				const d = await r.json()
				this.sig.mode = d.mode || "—"
				this.sig.source = d.source || ""
				this.sig.as_of = d.as_of || ""
				this.sig.recs = d.recommendations || []
				this.sig.strategy_scores = d.strategy_scores || {}
				this.sig.no_trade_reason = d.no_trade_reason || null
				this.sig.scan_meta = d.scan_meta || null
				this.sig.data_freshness = d.data_freshness || null
			} catch (e) {
				this.sig.mode = "OFFLINE"
				this.sig.source = "error"
				this.sig.no_trade_reason = "⚠ Failed to connect to the scanner. Check if the server is running."
			}
		},
		async fetchPortfolio() {
			this.pf.loading = true
			try {
				const r = await fetch("/api/portfolio/monitor")
				if (!r.ok) throw 0
				const d = await r.json()
				this.pf.positions = this.mergeLocalPortfolioHoldings(d.positions || [])
				this.pf.alerts = d.alerts || []
				this.pf.summary = d.summary || null
				this.pf.source = "manual"
				// ── IBKR auto-sync: when broker is connected, broker positions become canonical ──
				// Manual entries are kept as overlay (e.g. for stop/target metadata) but counts/equity reflect IBKR
				try {
					if (this.cc_status && this.cc_status.ibkr_connected) {
						const r2 = await fetch("/api/ibkr/positions")
						if (r2.ok) {
							const d2 = await r2.json()
							const brokerPositions = (d2.positions || []).map((p) => {
								const sym = (p.symbol || p.ticker || "").toUpperCase()
								const manual =
									(this.pf.positions || []).find(
										(m) => (m.ticker || m.symbol || "").toUpperCase() === sym,
									) || {}
								const stop = Number(
									manual.stop_price || manual.initial_stop || manual.current_stop || 0,
								)
								return {
									ticker: sym,
									shares: p.position || p.quantity || 0,
									entry_price: manual.entry_price || p.avg_cost || p.average_cost || 0,
									current_price: p.market_price || p.last_price || 0,
									market_value: p.market_value || 0,
									unrealized_pnl: p.unrealized_pnl || 0,
									stop_price: stop,
									target_1r: manual.target_1r || 0,
									target_2r: manual.target_2r || 0,
									stop_defined: !!(manual.stop_defined || stop > 0),
									notes: manual.notes || "",
									source: "broker",
								}
							})
							if (brokerPositions.length > 0) {
								this.pf.positions = brokerPositions
								this.pf.source = "ibkr"
								// Recompute summary from broker truth
								const totalVal = brokerPositions.reduce((s, p) => s + (p.market_value || 0), 0)
								this.pf.summary = {
									...this.pf.summary,
									total_positions: brokerPositions.length,
									total_value: totalVal,
									source: "ibkr",
								}
							}
						}
					}
				} catch (e) {
					console.warn("IBKR sync skipped:", e)
				}
				// Enrich with trade advice in background (deferred — keeps initial portfolio load fast)
				if (this.pf.positions.length > 0) {
					const positions = this.pf.positions.filter((p) => p.entry_price && p.ticker)
					setTimeout(async () => {
						const enrichTasks = positions.map((p) =>
							this.ccFetch("/api/dossier/" + p.ticker + "/trade-advice?buy_price=" + p.entry_price, {
								retries: 2,
								backoff: 400,
							})
								.then((r) => (r && r.ok ? r.json() : null))
								.catch(() => null),
						)
						const results = await Promise.allSettled(enrichTasks)
						const posWithEntry = this.pf.positions.filter((p) => p.entry_price && p.ticker)
						results.forEach((r, i) => {
							if (r.status === "fulfilled" && r.value) {
								posWithEntry[i]._action = r.value.action
								posWithEntry[i]._alpha_spy =
									r.value.pnl_pct != null
										? Math.round(
												(r.value.pnl_pct - (this.today7.regime?.spy_change_pct || 0)) * 100,
											) / 100
										: null
							}
						})
					}, 4000)
				}
				try {
					const now = Date.now()
					if ((this.pf.positions || []).length > 0 && now - (this.histVar.last_run || 0) > 300000) {
						this.fetchHistVar()
					}
				} catch (_) {}
			} catch (e) {
				console.warn("Portfolio fetch error:", e)
				const local = this.hydratePortfolioFromLocal()
				if (local && local.holdings && local.holdings.length) {
					this.pf.positions = local.holdings
					this.pf.source = "manual"
					const totalVal = local.holdings.reduce(
						(s, p) => s + (p.market_value || p.entry_price * p.shares || 0),
						0,
					)
					const totalCost = local.holdings.reduce(
						(s, p) => s + (p.cost_basis || p.entry_price * p.shares || 0),
						0,
					)
					this.pf.summary = {
						total_positions: local.holdings.length,
						total_value: Math.round(totalVal * 100) / 100,
						total_cost: Math.round(totalCost * 100) / 100,
						total_pnl: Math.round((totalVal - totalCost) * 100) / 100,
						total_pnl_pct: totalCost ? Math.round((totalVal / totalCost - 1) * 10000) / 100 : 0,
					}
				}
			} finally {
				this.pf.loading = false
			}
			this.fetchPortfolioDecision()
		},
		async fetchPortfolioDecision() {
			this.pfDecisionLoading = true
			try {
				const r = await this.ccFetch("/api/v7/portfolio-decision", { retries: 3, backoff: 500 })
				if (r && r.ok) this.pfDecision = await r.json()
				try {
					const ddPct =
						(this.pfDecision &&
							this.pfDecision.curve_diagnostics &&
							this.pfDecision.curve_diagnostics.max_drawdown_pct) ||
						8.5
					const qs = await this.ccFetchJson(
						"/api/v7/quant/drawdown-sizing?current_dd_pct=" +
							encodeURIComponent(ddPct) +
							"&research_only=" +
							(this.authorityDegradedBanner() || this.todayUsesBriefFallback() ? "true" : "false"),
						{ tab: "portfolio", retries: 1, backoff: 400 },
					)
					if (qs.ok) this.pfQuantSizing = qs.data
				} catch (e) {
					console.warn("quant drawdown-sizing", e)
				}
			} catch (e) {
				console.warn("portfolio-decision", e)
			} finally {
				this.pfDecisionLoading = false
			}
		},
		async fetchPortfolioEquity() {
			this.pfEquityLoading = true
			try {
				const r = await this.ccFetch("/api/v7/portfolio-equity?period=6mo&benchmark=SPY", {
					retries: 2,
					backoff: 500,
				})
				if (r && r.ok) this.pfEquity = await r.json()
			} catch (e) {
				console.warn("portfolio-equity", e)
			} finally {
				this.pfEquityLoading = false
			}
		},
		async runRebalanceSim(policy, targetsStr) {
			let u = "/api/v7/rebalance-sim?policy=" + encodeURIComponent(policy || "equal_weight")
			if (targetsStr) u += "&targets=" + encodeURIComponent(targetsStr)
			try {
				const r = await this.ccFetch(u, { method: "POST", retries: 2, backoff: 400 })
				if (r && r.ok) {
					const sim = await r.json()
					if (this.pfDecision) this.pfDecision = { ...this.pfDecision, rebalance_sim: sim }
				}
			} catch (e) {
				console.warn("rebalance-sim", e)
			}
		},
		async fetchScenarioList() {
			try {
				const r = await fetch("/api/scenarios")
				if (r.ok) {
					const d = await r.json()
					this.pfScenario.list = d.scenarios || []
				}
			} catch (e) {
				console.warn("scenarios list", e)
			}
		},
		async runScenarioShock(key) {
			if (!key) return
			this.pfScenario.loading = true
			this.pfScenario.selected = key
			this.pfScenario.result = null
			try {
				const r = await this.ccFetch("/api/v7/scenario-shock?scenario_key=" + encodeURIComponent(key), {
					method: "POST",
					retries: 2,
					backoff: 600,
				})
				if (r && r.ok) this.pfScenario.result = await r.json()
			} catch (e) {
				console.warn("scenario-shock", e)
			} finally {
				this.pfScenario.loading = false
			}
		},
		async fetchBacktestLab() {
			if (!this.btLab.ticker) return
			this.btLab.loading = true
			this.btLab.error = ""
			this.btLab.data = null
			try {
				const u =
					"/api/v7/backtest-lab?ticker=" +
					encodeURIComponent(this.btLab.ticker) +
					"&strategy=" +
					encodeURIComponent(this.btLab.strategy) +
					"&period=" +
					encodeURIComponent(this.btLab.period) +
					"&walk_forward=" +
					(this.btLab.walkForward ? "true" : "false")
				const res = await this.ccFetchJson(u, { tab: "btlab", retries: 2, backoff: 800 })
				if (!res.ok) {
					this.btLab.error = this.surfaceFetchErrorLine(res.error, "btlab")
					return
				}
				this.btLab.data = res.data
				if (res.data && (res.data.degraded || res.data.research_only)) {
					this.surfaceFetchHints.btlab = { loading: false, stale: true, fallback: true, error: "" }
				}
				this.bt.result = this.btLab.data.core_backtest || null
				try {
					const qc = await this.ccFetchJson(
						"/api/v7/quant/strategy-health?ticker=" + encodeURIComponent(this.btLab.ticker),
						{ tab: "btlab", retries: 1, backoff: 400 },
					)
					if (qc.ok) this.btLab.quantCurve = qc.data
				} catch (e) {
					console.warn("quant strategy-health", e)
				}
				this.$nextTick(() => this.renderBtlabChart())
			} catch (e) {
				this.btLab.error = this.surfaceFetchErrorLine(e.message || String(e), "btlab")
				console.warn("backtest-lab", e)
			} finally {
				this.btLab.loading = false
			}
		},
		renderBtlabChart() {
			const ec = this.btLab.data && this.btLab.data.core_backtest && this.btLab.data.core_backtest.equity_chart
			if (!ec || !ec.bh || !ec.bh.length) return
			const el = document.getElementById("btlab-equity-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 220,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				if (ec.strategy && ec.strategy.length) {
					const sl = chart.addLineSeries({
						color: "#00d4aa",
						lineWidth: 2,
						priceLineVisible: false,
						lastValueVisible: true,
						title: "Strategy",
					})
					sl.setData(ec.strategy)
					if (ec.signals && ec.signals.length) sl.setMarkers(ec.signals)
				}
				const bl = chart.addLineSeries({
					color: "#fbbf24",
					lineWidth: 1,
					priceLineVisible: false,
					lastValueVisible: true,
					title: "Buy&Hold",
					lineStyle: 2,
				})
				bl.setData(ec.bh)
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
			} catch (e) {
				console.warn("btlab chart", e)
			}
		},
		async fetchQuoteWorkstation() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk) return
			this.dosWorkstation.loading = true
			try {
				const r = await this.ccFetch("/api/v7/quote-workstation/" + encodeURIComponent(tk), {
					retries: 2,
					backoff: 600,
				})
				if (r && r.ok) this.dosWorkstation.data = await r.json()
			} catch (e) {
				console.warn("quote-workstation", e)
			} finally {
				this.dosWorkstation.loading = false
			}
		},
		async fetchCatalystCalendar() {
			this.platformExtras.loading = true
			try {
				const r = await this.ccFetch("/api/v7/catalyst-calendar", { retries: 2, backoff: 500 })
				if (r && r.ok) this.platformExtras.catalyst = await r.json()
			} catch (e) {
				console.warn("catalyst-calendar", e)
			} finally {
				this.platformExtras.loading = false
			}
		},
		async runPmMemo(scope) {
			const u =
				"/api/v7/pm-memo?scope=" +
				encodeURIComponent(scope) +
				(scope === "ticker" && this.dos.ticker ? "&ticker=" + encodeURIComponent(this.dos.ticker) : "")
			try {
				const r = await this.ccFetch(u, { retries: 2, backoff: 500 })
				if (!r || !r.ok) return
				this.platformExtras.pmMemo = await r.json()
				alert(this.platformExtras.pmMemo.one_liner || "Memo ready — see console")
				console.log(this.platformExtras.pmMemo.markdown)
			} catch (e) {
				console.warn("pm-memo", e)
			}
		},
		async fetchLedgerView(force = false) {
			if (this.ledgerView.loading) return
			if (this.ledgerView.loaded && !force) return
			this.ledgerView.loading = true
			try {
				const qs = new URLSearchParams({ limit: "200" })
				if (this.ledgerView.filterStrategy) qs.set("strategy", this.ledgerView.filterStrategy)
				if (this.ledgerView.filterDirection) qs.set("direction", this.ledgerView.filterDirection)
				if (this.ledgerView.filterTicker) qs.set("ticker", this.ledgerView.filterTicker)
				const [r1, r2] = await Promise.all([
					fetch("/api/ledger/list?" + qs.toString()),
					fetch("/api/ledger/stats"),
				])
				if (r1.ok) {
					const d = await r1.json()
					this.ledgerView.rows = d.rows || []
				}
				if (r2.ok) {
					const raw = await r2.json()
					const s = raw.summary || {}
					const aggOk =
						raw.aggregate_metrics_available !== false &&
						raw.data_quality?.aggregate_metrics_available !== false &&
						!raw.data_quality?.partially_hydrated
					this.ledgerView.stats = {
						count: raw.count || s.count || 0,
						wins: s.wins ?? raw.wins ?? 0,
						losses: s.losses ?? raw.losses ?? 0,
						total_pnl_pct: s.total_pnl_pct ?? raw.total_pnl_pct ?? null,
						win_rate_pct: s.win_rate_pct ?? raw.win_rate_pct ?? 0,
						profit_factor: s.profit_factor ?? raw.profit_factor ?? null,
						avg_r_multiple: s.avg_r_multiple ?? raw.avg_r_multiple ?? null,
						expectancy_pct: s.expectancy_pct ?? raw.expectancy_pct ?? null,
						avg_win_pct: s.avg_win_pct ?? raw.avg_win_pct ?? 0,
						avg_loss_pct: s.avg_loss_pct ?? raw.avg_loss_pct ?? 0,
						by_strategy: raw.by_strategy || {},
						data_quality: raw.data_quality || {},
						aggregate_metrics_available: aggOk,
						summary: s,
					}
				}
				this.ledgerView.loaded = true
			} catch (_) {
				this.ledgerView.rows = []
				this.ledgerView.stats = null
			} finally {
				this.ledgerView.loading = false
			}
		},
		async seedDemoPortfolio() {
			if (
				!window.confirm(
					"Seed 3 demo positions (AAPL 100sh, MSFT 50sh, NVDA 30sh)?\n\nThis overwrites any existing manual portfolio.",
				)
			)
				return
			this.pf.loading = true
			try {
				const r = await fetch("/api/portfolio/seed-demo", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) throw new Error("HTTP " + r.status)
				const d = await r.json()
				await this.fetchPortfolio()
				await this.fetchPortfolioDecision()
				await this.fetchPortfolioEquity()
				this.histVar.last_run = 0
				await this.fetchHistVar()
				alert("✅ Seeded " + d.seeded + " positions.\n\n" + d.next)
			} catch (e) {
				alert("Seed failed: " + e.message)
			} finally {
				this.pf.loading = false
			}
		},
		async fetchHistVar() {
			// Real historical-sim VaR — pulls 1y daily returns per position from /api/portfolio/var-historical
			if (this.histVar.loading) return
			const positions = (this.pf && this.pf.positions) || []
			if (positions.length === 0) {
				this.histVar.data = null
				return
			}
			const equity = this.pfRisk().equity || 100000
			this.histVar.loading = true
			this.histVar.err = ""
			try {
				const body = {
					positions: positions
						.map((p) => ({
							ticker: p.ticker || p.symbol,
							market_value:
								p.market_value ||
								(p.current_price || p.entry_price || 0) * (p.shares || p.quantity || 0),
						}))
						.filter((p) => p.ticker && p.market_value > 0),
					equity: equity,
					lookback_period: "1y",
				}
				const r = await fetch("/api/portfolio/var-historical", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(body),
				})
				if (!r.ok) throw new Error("HTTP " + r.status)
				const d = await r.json()
				this.histVar.data = d
				this.histVar.last_run = Date.now()
			} catch (e) {
				this.histVar.err = String(e)
				console.warn("histVar fetch error:", e)
			} finally {
				this.histVar.loading = false
			}
		},
		resetAddPositionForm() {
			this.pf.showAdd = false
			this.pf.showAdvanced = false
			this.pf.addTicker = ""
			this.pf.addShares = 0
			this.pf.addEntry = 0
			this.pf.addStop = 0
			this.pf.addT1r = 0
			this.pf.addT2r = 0
			this.pf.addNotes = ""
			this.pf.addSleeve = ""
			this.pf.addSector = ""
			this.pf.addError = ""
			this.pf.addSuccess = ""
		},
		async addPosition() {
			const ticker = (this.pf.addTicker || "").toUpperCase().trim()
			const shares = Number(this.pf.addShares)
			const entry = Number(this.pf.addEntry)
			this.pf.addError = ""
			this.pf.addSuccess = ""
			if (!ticker) {
				this.pf.addError = "Ticker is required"
				return
			}
			if (!shares || shares <= 0) {
				this.pf.addError = "Shares must be greater than 0"
				return
			}
			if (!entry || entry <= 0) {
				this.pf.addError = "Entry price must be greater than 0"
				return
			}
			if (this.pf.corrPreview && this.pf.corrPreview.blocked) {
				this.pf.addError = "Correlation guard blocked: " + this.pf.corrPreview.message
				return
			}
			const body = {
				ticker,
				shares,
				entry_price: entry,
				notes: this.pf.addNotes || "",
			}
			if (this.pf.showAdvanced) {
				if (this.pf.addStop > 0) body.stop_price = this.pf.addStop
				if (this.pf.addT1r > 0) body.target_1r = this.pf.addT1r
				if (this.pf.addT2r > 0) body.target_2r = this.pf.addT2r
				if (this.pf.addSleeve) body.sleeve = this.pf.addSleeve
				if (this.pf.addSector) body.sector = this.pf.addSector
			}
			const finishAdd = (d, pos) => {
				const msg =
					(d && d.message) ||
					(d && d.broker_sync === "unavailable"
						? "Saved locally · Broker sync unavailable"
						: "Position saved")
				this.pf.addSuccess = msg
				this.resetAddPositionForm()
				if (pos && pos.quote_pending) {
					this.pf.alerts = [
						{
							ticker: pos.ticker,
							type: "QUOTE_PENDING",
							severity: "warning",
							msg: "⏳ " + pos.ticker + " 已保存 · 報價待回補，暫以 entry price 顯示",
						},
						...(this.pf.alerts || []),
					]
				}
			}
			try {
				const r = await this.ccFetch("/api/portfolio/position", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(body),
					retries: 2,
					backoff: 400,
				})
				if (r && r.ok) {
					const d = await r.json()
					await this.fetchPortfolio()
					finishAdd(d, d.position)
					return
				}
				if (r && (r.status === 503 || r.status >= 500)) {
					const pos = this.applyLocalPortfolioAdd(body)
					finishAdd({ message: "Saved locally · Broker sync unavailable", broker_sync: "unavailable" }, pos)
					return
				}
				const err = r ? await r.json().catch(() => ({})) : {}
				this.pf.addError = err.detail || "Failed to add position (HTTP " + (r ? r.status : "fail") + ")"
			} catch (e) {
				const pos = this.applyLocalPortfolioAdd(body)
				if (pos) {
					finishAdd({ message: "Saved locally · Broker sync unavailable", broker_sync: "unavailable" }, pos)
					return
				}
				this.pf.addError = "Network error — could not add position"
				console.warn("Add position error:", e)
			}
		},
		// ── Correlation guard: warn (>0.6) / block (>0.7) when adding correlated names ──
		// Uses per-ticker history vs each existing position; fallbacks to sector overlap if API unavailable
		async checkCorrelation() {
			const t = (this.pf.addTicker || "").toUpperCase().trim()
			if (!t) {
				this.pf.corrPreview = null
				return
			}
			const existing = (this.pf.positions || [])
				.map((p) => (p.ticker || p.symbol || "").toUpperCase())
				.filter((x) => x && x !== t)
			if (existing.length === 0) {
				this.pf.corrPreview = { blocked: false, warn: false, message: "First position — no correlation risk" }
				return
			}
			try {
				// Pull rolling 60d closes for new ticker and existing — compute pairwise ρ
				const period = "3mo"
				const fetchSpark = async (sym) => {
					const r = await fetch("/api/live/spark/" + sym + "?days=60")
					if (!r.ok) return null
					const d = await r.json()
					return d.prices || null
				}
				const newPrices = await fetchSpark(t)
				if (!newPrices || newPrices.length < 20) {
					this.pf.corrPreview = {
						blocked: false,
						warn: true,
						message: "Insufficient price history for " + t + " — proceed with caution",
					}
					return
				}
				const newRet = newPrices.slice(1).map((p, i) => p / newPrices[i] - 1)
				const corrs = []
				for (const sym of existing) {
					const p = await fetchSpark(sym)
					if (!p || p.length < 20) continue
					const r = p.slice(1).map((px, i) => px / p[i] - 1)
					const n = Math.min(newRet.length, r.length)
					const a = newRet.slice(-n),
						b = r.slice(-n)
					const ma = a.reduce((s, x) => s + x, 0) / n,
						mb = b.reduce((s, x) => s + x, 0) / n
					let num = 0,
						da = 0,
						db = 0
					for (let i = 0; i < n; i++) {
						const xa = a[i] - ma,
							xb = b[i] - mb
						num += xa * xb
						da += xa * xa
						db += xb * xb
					}
					const rho = da > 0 && db > 0 ? num / Math.sqrt(da * db) : 0
					corrs.push({ sym, rho: Math.round(rho * 100) / 100 })
				}
				if (corrs.length === 0) {
					this.pf.corrPreview = { blocked: false, warn: true, message: "No correlation data available" }
					return
				}
				corrs.sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho))
				const top = corrs[0]
				if (Math.abs(top.rho) >= 0.7) {
					this.pf.corrPreview = {
						blocked: true,
						warn: false,
						corrs,
						message: "ρ=" + top.rho + " vs " + top.sym + " (>0.7 cap). Concentration risk — block.",
					}
				} else if (Math.abs(top.rho) >= 0.5) {
					this.pf.corrPreview = {
						blocked: false,
						warn: true,
						corrs,
						message:
							"ρ=" +
							top.rho +
							" vs " +
							top.sym +
							" — moderate correlation. Reduce size or pick a less-correlated name.",
					}
				} else {
					this.pf.corrPreview = {
						blocked: false,
						warn: false,
						corrs,
						message: "Max ρ=" + top.rho + " vs " + top.sym + " — diversifying",
					}
				}
			} catch (e) {
				console.warn("Correlation check failed:", e)
				this.pf.corrPreview = {
					blocked: false,
					warn: true,
					message: "Correlation check failed — proceed with caution",
				}
			}
		},
		async removePosition(ticker) {
			if (!confirm("Remove " + ticker + " from portfolio?")) return
			try {
				await fetch("/api/portfolio/position/" + ticker, { method: "DELETE" })
				await this.fetchPortfolio()
			} catch (e) {
				console.warn(e)
			}
		},
		async confirmBuy() {
			if (!this.dos.data || !this.dos.ticker) return
			const tp = this.dos.data.trade_plan
			if (!tp) return
			const entry = this.dos.data.price || tp.entry_zone[0]
			const shares = prompt("How many shares to track for " + this.dos.ticker + "?", "100")
			if (!shares) return
			try {
				const r = await fetch("/api/portfolio/position", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						ticker: this.dos.ticker,
						shares: parseFloat(shares),
						entry_price: entry,
						stop_price: tp.stop,
						target_1r: tp.target_1r,
						target_2r: tp.target_2r,
						notes: "From dossier trade plan",
					}),
				})
				if (r.ok) {
					alert("✅ " + this.dos.ticker + " added to portfolio! Check Portfolio tab.")
					this.tab = "portfolio"
					await this.fetchPortfolio()
				}
			} catch (e) {
				console.warn(e)
			}
		},
		async runFactory() {
			this.factory.loading = true
			this.factory.result = null
			this.factory.showDetail = false
			try {
				const r = await fetch(
					"/api/strategy-factory/generate?ticker=" +
						encodeURIComponent(this.factory.ticker) +
						"&period=" +
						this.factory.period +
						"&mode=" +
						this.factory.mode,
					{ method: "POST" },
				)
				if (!r.ok) throw new Error("Factory failed")
				this.factory.result = await r.json()
			} catch (e) {
				console.warn("Factory error:", e)
				alert("Strategy Factory error: " + e.message)
			} finally {
				this.factory.loading = false
			}
		},
		viewFactoryDetail(rank) {
			if (!this.factory.result) return
			const all = this.factory.result.best_strategy ? [this.factory.result.best_strategy] : []
			// Find in library or reconstruct from ranking
			const lib = this._factoryLib || []
			const found = lib.find((s) => s.rank === rank)
			if (found) {
				this.factory.detail = found
				this.factory.showDetail = true
				return
			}
			// Fetch full library
			fetch("/api/strategy-factory/library")
				.then((r) => r.json())
				.then((d) => {
					this._factoryLib = d.strategies || []
					const s = this._factoryLib.find((x) => x.rank === rank)
					if (s) {
						this.factory.detail = s
						this.factory.showDetail = true
					}
				})
				.catch((e) => console.warn(e))
		},
		async deployFactory(id) {
			try {
				const r = await fetch("/api/strategy-factory/deploy/" + id, { method: "POST" })
				if (r.ok) {
					alert("🚀 Strategy deployed to paper trading monitor!")
				}
			} catch (e) {
				console.warn(e)
			}
		},
		_dosCacheKey(t) {
			return "cc_dos_cache_v2_" + (t || "").toUpperCase()
		},
		_normalizeStockIntel(intel) {
			if (!intel || typeof intel !== "object") return null
			const emptyP9 = { fundamentals: null, earnings: null, structure: null }
			const isEnvelope = !!(
				intel.dossier ||
				intel.unified_decision ||
				intel.narrative ||
				intel.load_phase ||
				intel.decision_stack
			)
			let dossier = null
			if (intel.dossier && typeof intel.dossier === "object") {
				dossier = { ...intel.dossier }
			} else if (intel.symbol || intel.price) {
				dossier = { ...intel }
			} else if (this.dos?.data && (this.dos.data.symbol || this.dos.data.price)) {
				dossier = { ...this.dos.data }
			} else {
				dossier = {}
			}
			const p9 = intel.p9 || dossier._p9 || null
			dossier._p9 = p9 ? { ...emptyP9, ...p9 } : { ...emptyP9, ...(dossier._p9 || {}) }
			const envelope = isEnvelope
				? { ...intel, dossier }
				: { ...intel, dossier, load_phase: intel.load_phase || "full" }
			envelope.dossier = dossier
			return envelope
		},
		dosSaveCache(t, intel) {
			if (!t || !intel) return
			const norm = this._normalizeStockIntel(intel) || intel
			try {
				localStorage.setItem(this._dosCacheKey(t), JSON.stringify({ ts: Date.now(), intel: norm }))
			} catch (_) {}
		},
		dosLoadCache(t) {
			if (!t) return null
			const tk = (t || "").toUpperCase()
			try {
				for (const prefix of ["cc_dos_cache_v2_", "cc_dos_cache_"]) {
					const raw = localStorage.getItem(prefix + tk)
					if (!raw) continue
					const parsed = JSON.parse(raw)
					if (!parsed?.intel) continue
					const norm = this._normalizeStockIntel(parsed.intel)
					if (norm && (norm.dossier?.symbol || norm.dossier?.price)) return { ts: parsed.ts, intel: norm }
				}
			} catch (_) {}
			return null
		},
		dosHasCached() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			return !!(tk && this.dosLoadCache(tk) && this.dosLoadCache(tk).intel)
		},
		dosTrustSource() {
			if (this.dos.status === "idle_no_query") return "Source: —"
			if (this.dos.data && this.dos.data.trust) return "Source: " + this.dos.data.trust.source
			if (this.dos.loading || this.dos.status === "loading_core") return "Source: market_data_service (loading)"
			return "Source: market_data_service"
		},
		dosTrustAsOf() {
			if (this.dos.status === "idle_no_query") return "Select a symbol to research"
			if (this.dos.status === "loading_core") return "Loading core dossier…"
			if (this.dos.status === "failed") return "Awaiting research — not decision-grade"
			if (this.dos.status === "partial_loaded" && (this.dos.partialNotice || this.dos.error))
				return this.dos.partialNotice || "Partial load — see notice below"
			if (this.dos.status === "stale_fallback" && this.dos.staleAt)
				return "Cached: " + new Date(this.dos.staleAt).toISOString().slice(0, 19)
			if (this.dos.data && this.dos.data.trust && this.dos.data.trust.as_of)
				return "As-of: " + this.dos.data.trust.as_of.slice(0, 19)
			if (this.dos.intel && this.dos.intel.as_of) return "As-of: " + this.dos.intel.as_of.slice(0, 19)
			if (this.dos.status === "loading_enrichments") return "Loading enrichments…"
			if (this.dos.status === "partial_loaded") return "Core loaded — enrichments optional"
			if (this.dos.status === "loaded") return "Research ready"
			return ""
		},
		_applyDossierIntel(intel, meta = {}) {
			if (!intel) return
			const envelope = this._normalizeStockIntel(intel)
			if (!envelope) return
			this.dos.intel = envelope
			this.dos.dossier_freshness = envelope.dossier_freshness || null
			this.dos.missing_modules = envelope.missing_modules || []
			this.dos.cc_state = envelope.cc_state || null
			this.dos.data = { ...envelope.dossier }
			this.dos.data._p9 = envelope.dossier._p9 || { fundamentals: null, earnings: null, structure: null }
			this.dos.conviction = envelope.conviction || null
			this.dos.peers = envelope.peers || this.dos.peers || null
			this.dos.peersLoading = false
			if (envelope.options) this.dos.optionsData = envelope.options
			if (meta.stale) {
				this.dos.status = "stale_fallback"
				this.dos.staleAt = meta.cachedAt || Date.now()
				this.dos.error = ""
			} else if (envelope.load_phase === "core" || envelope.partial) {
				this.dos.status =
					envelope.load_phase === "core"
						? "partial_loaded"
						: this.dos.loadingEnrich
							? "loading_enrichments"
							: "partial_loaded"
			} else {
				this.dos.status = "loaded"
				this.dos.staleAt = null
			}
			this.dos.chartPeriod = this.dos.chartPeriod || "6mo"
			if (this.dos.subTab === "technicals")
				this.$nextTick(() => {
					this.renderDossierChart()
					this.renderBenchChart()
				})
			if (this.dos.subTab === "options" && !this.dos.optionsData) this.fetchDosOptions()
			if (this.dos.subTab === "peers" && !this.dosPeersRows().length) this.fetchDosPeers()
		},
		_mergeDossierEnrichments(enrich) {
			if (!enrich || !this.dos.intel) return
			const base = this._normalizeStockIntel(this.dos.intel) || this.dos.intel
			const dossier = { ...(base.dossier || this.dos.data || {}) }
			if (enrich.p9) dossier._p9 = { fundamentals: null, earnings: null, structure: null, ...enrich.p9 }
			const merged = {
				...base,
				...enrich,
				load_phase: "full",
				dossier,
				module_errors: { ...(base.module_errors || {}), ...(enrich.module_errors || {}) },
			}
			this._applyDossierIntel(merged)
			this.dosSaveCache((this.dos.ticker || "").trim().toUpperCase(), merged)
		},
		async _refreshDossierFullSilent(tk, reqId) {
			try {
				const r = await this.ccFetch("/api/v7/stock-intel/" + encodeURIComponent(tk), {
					retries: 1,
					backoff: 800,
					timeoutMs: 60000,
				})
				if (reqId !== this.dos._reqId || !r || !r.ok) return
				const intel = await r.json()
				if (reqId !== this.dos._reqId) return
				this._applyDossierIntel(intel)
				this.dosSaveCache(tk, intel)
				const degraded = this._dossierIntelDegraded(intel)
				const notice = this._dossierPartialNoticeFromIntel(intel)
				if (intel.module_errors && Object.keys(intel.module_errors).length && !degraded) {
					const first = Object.entries(intel.module_errors)[0]
					this.dos.failedModule = first[0]
					this.dos.error = "Partial load: " + first[1]
					this.dos.partialNotice = ""
					this.dos.status = "partial_loaded"
				} else if (degraded || intel.partial || intel.load_phase === "core") {
					this.dos.error = ""
					this.dos.partialNotice = notice
					this.dos.failedModule = intel.module_errors?.dossier ? "dossier" : ""
					this.dos.status = "partial_loaded"
				} else {
					this.dos.error = ""
					this.dos.partialNotice = ""
					this.dos.failedModule = ""
					this.dos.status = "loaded"
				}
			} catch (_) {}
		},
		async fetchDossierEnrichments() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk || !this.dos.intel) return
			const reqId = this.dos._reqId
			this.dos.loadingEnrich = true
			this.dos.status = "loading_enrichments"
			this._syncDossierFetchHints()
			try {
				const r = await this.ccFetch("/api/v7/stock-intel/" + encodeURIComponent(tk) + "?enrichments=true", {
					retries: 2,
					backoff: 800,
					timeoutMs: 45000,
				})
				if (reqId !== this.dos._reqId) return
				if (!r || !r.ok) {
					const e = r ? await r.json().catch(() => ({})) : {}
					throw new Error(this.formatReplayError(e.detail || e.error || "Enrichments unavailable"))
				}
				const enrich = await r.json()
				if (reqId !== this.dos._reqId) return
				this._mergeDossierEnrichments(enrich)
				await this._refreshDossierFullSilent(tk, reqId)
			} catch (e) {
				if (reqId !== this.dos._reqId) return
				const detail = this.formatReplayError(e.message || String(e))
				this.dos.fetchDetail = detail
				if (this.dos.data) {
					this.dos.error = ""
					this.dos.partialNotice = "Enrichments unavailable — " + detail
					this.dos.failedModule = "enrichments"
					this.dos.status = "partial_loaded"
				} else {
					this.dos.partialNotice = ""
					this.dos.error = "即時研究暫不可用"
					this.dos.status = "failed"
				}
			} finally {
				if (reqId === this.dos._reqId) {
					this.dos.loadingEnrich = false
					this._syncDossierFetchHints()
				}
			}
		},
		async fetchOpportunityIntel() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk) {
				this.dos.oppIntel = null
				return
			}
			const reqId = this.dos._reqId
			this.dos.oppIntelLoading = true
			try {
				const key = window._apiKey || "dev-secret-local"
				const hdr = { headers: { "X-API-Key": key } }
				const base = "/api/v7/intelligence/"
				const q = "?ticker=" + encodeURIComponent(tk)
				const [insR, instR] = await Promise.all([
					this.ccFetch(base + "insider" + q, { retries: 1, backoff: 400, ...hdr }),
					this.ccFetch(base + "institutional" + q, { retries: 1, backoff: 400, ...hdr }),
				])
				if (reqId !== this.dos._reqId) return
				const insider = insR && insR.ok ? await insR.json() : null
				const institutional = instR && instR.ok ? await instR.json() : null
				if (reqId !== this.dos._reqId) return
				this.captureInstantDegradedBanner(insider || institutional || {})
				this.dos.oppIntel = { insider, institutional }
			} catch (_) {
				if (reqId === this.dos._reqId) this.dos.oppIntel = null
			} finally {
				if (reqId === this.dos._reqId) this.dos.oppIntelLoading = false
			}
		},
		async fetchDossier(opts = {}) {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk) {
				this.dos.status = "idle_no_query"
				this.dos.error = ""
				this.dos.loading = false
				return
			}
			if (opts.useCached) {
				const cached = this.dosLoadCache(tk)
				if (cached && cached.intel) {
					this._applyDossierIntel(cached.intel, { stale: true, cachedAt: cached.ts })
					this.dos.error = ""
					this.dos.partialNotice = ""
					this.dos.failedModule = ""
					return
				}
			}
			if (this.dos._abort) {
				try {
					this.dos._abort.abort()
				} catch (_) {}
			}
			const abort = new AbortController()
			this.dos._abort = abort
			const reqId = (this.dos._reqId || 0) + 1
			this.dos._reqId = reqId
			this.dos.loading = true
			this.dos.error = ""
			this.dos.partialNotice = ""
			this.dos.fetchDetail = ""
			this.dos.failedModule = ""
			this.dos.staleAt = null
			this.dos.status = "loading_core"
			this.dos.subTab = this.dos.subTab || "decision"
			this._syncDossierFetchHints()
			const coreOnly = !!opts.coreOnly
			try {
				const url = "/api/v7/stock-intel/" + encodeURIComponent(tk) + "?lite=true"
				const r = await this.ccFetch(url, {
					retries: 2,
					backoff: 800,
					timeoutMs: 15000,
					init: { signal: abort.signal },
				})
				if (reqId !== this.dos._reqId || abort.signal.aborted) return
				if (!r || !r.ok) {
					const e = r ? await r.json().catch(() => ({})) : {}
					const detail = e.detail || e.error || "Stock intel unavailable"
					const modMatch = String(detail).match(/^(dossier(?:_\w+)?|conviction|peers|options)/i)
					this.dos.failedModule = modMatch ? modMatch[1] : "dossier"
					throw new Error(this.formatReplayError(detail))
				}
				const intel = await r.json()
				if (reqId !== this.dos._reqId) return
				this._applyDossierIntel(intel)
				this.dosSaveCache(tk, intel)
				this.fetchOpportunityIntel()
				const degraded = this._dossierIntelDegraded(intel)
				const modErr = intel.module_errors || {}
				const notice = this._dossierPartialNoticeFromIntel(intel)
				if (modErr.dossier && !degraded) {
					this.dos.failedModule = "dossier"
					this.dos.fetchDetail = modErr.dossier
					this.dos.error = "Core partial: " + modErr.dossier
					this.dos.partialNotice = ""
				} else if (degraded || intel.partial || intel.load_phase === "core") {
					this.dos.error = ""
					this.dos.partialNotice = notice
					this.dos.fetchDetail = notice
					this.dos.failedModule = modErr.dossier ? "dossier" : ""
				} else {
					this.dos.error = ""
					this.dos.partialNotice = ""
					this.dos.failedModule = ""
					this.dos.fetchDetail = ""
				}
				if (coreOnly) {
					this.dos.status =
						degraded || intel.load_phase === "core" || intel.partial ? "partial_loaded" : "loaded"
					this._syncDossierFetchHints()
					return
				}
				this.fetchDossierEnrichments()
			} catch (e) {
				if (reqId !== this.dos._reqId || abort.signal.aborted) return
				const detail = this.formatReplayError(e.message || String(e))
				this.dos.fetchDetail = detail
				const cached = this.dosLoadCache(tk)
				if (cached && cached.intel) {
					this._applyDossierIntel(cached.intel, { stale: true, cachedAt: cached.ts })
					this.dos.error = "Cached dossier shown"
					this.dos.status = "stale_fallback"
				} else {
					this.dos.data = null
					this.dos.intel = null
					this.dos.error = "即時研究暫不可用"
					this.dos.status = "failed"
				}
			} finally {
				if (reqId === this.dos._reqId) {
					this.dos.loading = false
					this._syncDossierFetchHints()
				}
			}
		},
		async renderDossierChart() {
			if (!this.dos.data || !this.dos.ticker) return
			const el = document.getElementById("dossier-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				const sig = this.dos.showSignals ? "&signals=true" : ""
				const r = await fetch(
					"/api/live/chart/" +
						encodeURIComponent(this.dos.ticker) +
						"?period=" +
						(this.dos.chartPeriod || "6mo") +
						sig,
				)
				if (!r.ok) return
				const d = await r.json()
				if (!d.candles || !d.candles.length) return
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 260,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				const cs = chart.addCandlestickSeries({
					upColor: "#00d4aa",
					downColor: "#ff5c5c",
					borderUpColor: "#00d4aa",
					borderDownColor: "#ff5c5c",
					wickUpColor: "#00d4aa",
					wickDownColor: "#ff5c5c",
				})
				cs.setData(d.candles)
				if (d.sma20 && d.sma20.length) {
					const s20 = chart.addLineSeries({
						color: "#58a6ff",
						lineWidth: 1,
						priceLineVisible: false,
						lastValueVisible: false,
					})
					s20.setData(d.sma20)
				}
				if (d.sma50 && d.sma50.length) {
					const s50 = chart.addLineSeries({
						color: "#fbbf24",
						lineWidth: 1,
						priceLineVisible: false,
						lastValueVisible: false,
					})
					s50.setData(d.sma50)
				}
				// Pattern signal markers
				this.dos.chartSignals = d.signals || []
				if (this.dos.showSignals && d.signals && d.signals.length) {
					cs.setMarkers(
						d.signals.map((s) => ({
							time: s.time,
							position: s.position,
							color: s.color,
							shape: s.shape,
							text: s.text,
						})),
					)
				}
				// S/R lines from structure
				const st = this.dos.data._p9 && this.dos.data._p9.structure
				if (st) {
					if (st.nearest_support) {
						cs.createPriceLine({
							price: st.nearest_support,
							color: "#00d4aa",
							lineWidth: 1,
							lineStyle: 2,
							axisLabelVisible: true,
							title: "S",
						})
					}
					if (st.nearest_resistance) {
						cs.createPriceLine({
							price: st.nearest_resistance,
							color: "#ff5c5c",
							lineWidth: 1,
							lineStyle: 2,
							axisLabelVisible: true,
							title: "R",
						})
					}
				}
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
				this._dossierChart = chart
			} catch (e) {
				console.warn("Chart error:", e)
			}
			// Also render benchmark chart
			this.renderBenchChart()
		},
		async renderBenchChart() {
			if (!this.dos.ticker) return
			const el = document.getElementById("bench-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				const r = await fetch(
					"/api/live/perf-vs-spy/" +
						encodeURIComponent(this.dos.ticker) +
						"?period=" +
						(this.dos.benchPeriod || "1y"),
				)
				if (!r.ok) return
				const d = await r.json()
				if (d.error || !d.equity_stock || !d.equity_stock.length) return
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 200,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				// Stock line (green)
				const sl = chart.addLineSeries({
					color: "#00d4aa",
					lineWidth: 2,
					priceLineVisible: false,
					lastValueVisible: true,
					title: this.dos.ticker,
				})
				sl.setData(d.equity_stock)
				// SPY line (amber dashed)
				const bl = chart.addLineSeries({
					color: "#fbbf24",
					lineWidth: 2,
					priceLineVisible: false,
					lastValueVisible: true,
					title: "SPY",
					lineStyle: 2,
				})
				bl.setData(d.equity_spy)
				// Base line at 100
				sl.createPriceLine({
					price: 100,
					color: "#484f58",
					lineWidth: 1,
					lineStyle: 1,
					axisLabelVisible: false,
					title: "",
				})
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
				// Store period breakdown data
				this.dos.benchSummary = d.summary || null
				this.dos.benchMonthly = d.monthly || null
				this.dos.benchQuarterly = d.quarterly || null
				this.dos.benchYearly = d.yearly || null
				// Legacy compat
				if (d.summary) {
					this.dos.benchStats = {
						stockReturn: d.summary.total_return.stock,
						spyReturn: d.summary.total_return.spy,
						alpha: d.summary.total_return.alpha,
					}
				}
			} catch (e) {
				console.warn("Bench chart error:", e)
			}
		},
		renderBTEquityChart() {
			const ec = this.bt.result && this.bt.result.equity_chart
			if (!ec || !ec.bh || !ec.bh.length) return
			const el = document.getElementById("bt-equity-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 220,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				// Strategy line (green)
				if (ec.strategy && ec.strategy.length) {
					const sl = chart.addLineSeries({
						color: "#00d4aa",
						lineWidth: 2,
						priceLineVisible: false,
						lastValueVisible: true,
						title: "Strategy",
					})
					sl.setData(ec.strategy)
					// Signal markers
					if (ec.signals && ec.signals.length) {
						sl.setMarkers(ec.signals)
					}
				}
				// Buy-hold line (amber dashed)
				const bl = chart.addLineSeries({
					color: "#fbbf24",
					lineWidth: 1,
					priceLineVisible: false,
					lastValueVisible: true,
					title: "Buy&Hold",
					lineStyle: 2,
				})
				bl.setData(ec.bh)
				// Base 100 line
				bl.createPriceLine({
					price: 100,
					color: "#484f58",
					lineWidth: 1,
					lineStyle: 1,
					axisLabelVisible: false,
					title: "",
				})
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
			} catch (e) {
				console.warn("BT equity chart error:", e)
			}
		},
		renderBenchBTChart() {
			const ec = this.benchBT.data && this.benchBT.data.equity_curve
			if (!ec || !ec.strategy || !ec.strategy.length) return
			const el = document.getElementById("bench-bt-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 160,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				// Build time-series from arrays + dates
				const dates = ec.dates || []
				const stratVals = ec.strategy || []
				const benchVals = ec.benchmark || []
				const toData = (vals) =>
					vals
						.map((v, i) => {
							const d = dates[i] || ""
							const parts = d.split("-")
							const ts = parts.length === 3 ? Date.UTC(+parts[0], +parts[1] - 1, +parts[2]) / 1000 : i
							return { time: ts, value: v * 100 }
						})
						.filter((d) => d.value > 0)
				const sd = toData(stratVals)
				const bd = toData(benchVals)
				if (sd.length) {
					const sl = chart.addLineSeries({
						color: "#00d4aa",
						lineWidth: 2,
						priceLineVisible: false,
						lastValueVisible: true,
						title: "RS Top-5",
					})
					sl.setData(sd)
				}
				if (bd.length) {
					const bl = chart.addLineSeries({
						color: "#fbbf24",
						lineWidth: 1,
						priceLineVisible: false,
						lastValueVisible: true,
						title: this.benchBT.benchmark,
						lineStyle: 2,
					})
					bl.setData(bd)
				}
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
			} catch (e) {
				console.warn("Bench BT chart error:", e)
			}
		},
		async loadSparklines(items) {
			// Load sparkline data for an array of {ticker} objects, sets _spark property
			const tickers = [...new Set(items.filter((o) => o.ticker).map((o) => o.ticker))].slice(0, 15)
			const results = await Promise.allSettled(
				tickers.map((t) =>
					fetch("/api/live/spark/" + encodeURIComponent(t) + "?days=20").then((r) =>
						r.ok ? r.json() : null,
					),
				),
			)
			const map = {}
			results.forEach((r, i) => {
				if (r.status === "fulfilled" && r.value && r.value.prices && r.value.prices.length >= 3)
					map[tickers[i]] = r.value.prices
			})
			items.forEach((o) => {
				if (o.ticker && map[o.ticker]) {
					const p = map[o.ticker]
					const mn = Math.min(...p),
						mx = Math.max(...p)
					const rng = mx - mn || 1
					o._spark = p.map((v) => Math.round(((v - mn) / rng) * 16) + 1)
				}
			})
		},
		async renderTTChart() {
			if (!this.tt.result || !this.tt.result.ticker) return
			const el = document.getElementById("tt-chart")
			if (!el || typeof LightweightCharts === "undefined") return
			el.innerHTML = ""
			try {
				// Fetch 1y chart data centered around the target date
				const r = await fetch("/api/live/chart/" + encodeURIComponent(this.tt.result.ticker) + "?period=1y")
				if (!r.ok) return
				const d = await r.json()
				if (!d.candles || !d.candles.length) return
				const chart = LightweightCharts.createChart(el, {
					width: el.clientWidth,
					height: 200,
					layout: { background: { color: "#161b22" }, textColor: "#8b949e", fontSize: 10 },
					grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
					crosshair: { mode: 0 },
					rightPriceScale: { borderColor: "#21262d" },
					timeScale: { borderColor: "#21262d", timeVisible: false },
				})
				const cs = chart.addCandlestickSeries({
					upColor: "#00d4aa",
					downColor: "#ff5c5c",
					borderUpColor: "#00d4aa",
					borderDownColor: "#ff5c5c",
					wickUpColor: "#00d4aa",
					wickDownColor: "#ff5c5c",
				})
				cs.setData(d.candles)
				// Mark the entry date
				const targetDate = this.tt.result.target_date
				if (targetDate) {
					const parts = targetDate.split("-")
					if (parts.length === 3) {
						const targetTs = Date.UTC(+parts[0], +parts[1] - 1, +parts[2]) / 1000
						// Find nearest candle
						let nearestIdx = 0,
							minDiff = Infinity
						d.candles.forEach((c, i) => {
							const df = Math.abs(c.time - targetTs)
							if (df < minDiff) {
								minDiff = df
								nearestIdx = i
							}
						})
						const entryCandle = d.candles[nearestIdx]
						if (entryCandle) {
							cs.setMarkers([
								{
									time: entryCandle.time,
									position: "belowBar",
									color: "#00d4aa",
									shape: "arrowUp",
									text: "ENTRY $" + this.tt.result.price,
								},
							])
							cs.createPriceLine({
								price: this.tt.result.price,
								color: "#58a6ff",
								lineWidth: 1,
								lineStyle: 2,
								axisLabelVisible: true,
								title: "Entry",
							})
						}
					}
				}
				// SMA overlays
				if (d.sma20 && d.sma20.length) {
					const s20 = chart.addLineSeries({
						color: "#58a6ff",
						lineWidth: 1,
						priceLineVisible: false,
						lastValueVisible: false,
					})
					s20.setData(d.sma20)
				}
				if (d.sma50 && d.sma50.length) {
					const s50 = chart.addLineSeries({
						color: "#fbbf24",
						lineWidth: 1,
						priceLineVisible: false,
						lastValueVisible: false,
					})
					s50.setData(d.sma50)
				}
				chart.timeScale().fitContent()
				new ResizeObserver(() => {
					chart.applyOptions({ width: el.clientWidth })
				}).observe(el)
			} catch (e) {
				console.warn("TT chart error:", e)
			}
		},
		openDossier(ticker, meta) {
			if (!ticker) return
			const tk = String(ticker).toUpperCase().trim()
			const from = this.tab
			const ctx = { from, ts: Date.now() }
			if (meta && typeof meta === "object") {
				Object.entries(meta).forEach(([k, v]) => {
					if (v != null && v !== "") ctx[k] = v
				})
			}
			if (from === "signals") {
				const rows = this.playbookDisplayRows() || []
				const idx = rows.findIndex((r) => String(r.ticker || "").toUpperCase() === tk)
				if (idx >= 0) {
					ctx.playbook_rank = idx + 1
					ctx.playbook_label = this.cardActionDisplay(rows[idx])
				}
			}
			if (from === "scanners") {
				const hits = (this.scannerHub.data && this.scannerHub.data.hits) || []
				const h = hits.find((x) => String(x.ticker || "").toUpperCase() === tk)
				if (h) {
					ctx.scanner = h.signal_source || h.scanner || ""
					ctx.discovery_reason = h.why_surfaced || h.headline || ""
				}
			}
			this.dos.open_context = ctx
			this.dos.ticker = tk
			this.switchTab("dossier")
		},
		playbookSetFocusTicker(ticker) {
			const t = String(ticker || "")
				.toUpperCase()
				.trim()
			this.playbookFocusTicker = t
		},
		playbookClearFocusTicker() {
			this.playbookFocusTicker = ""
		},
		async runBT() {
			if (!this.bt.ticker) return
			this.bt.loading = true
			this.bt.result = null
			try {
				const u =
					"/api/live/backtest?ticker=" +
					encodeURIComponent(this.bt.ticker) +
					"&strategy=" +
					this.bt.strategy +
					"&period=" +
					this.bt.period
				const r = await this.ccFetch(u, { method: "POST", retries: 2, backoff: 600 })
				if (!r || !r.ok) {
					let msg = "Failed"
					try {
						const e = await r.json()
						msg = e.detail || e.error || msg
					} catch (_x) {}
					throw new Error(msg)
				}
				const data = await r.json()
				if (data.degraded) {
					alert("API warming up — backtest shell only. Retry when health mode is full.")
				}
				this.bt.result = data
				this.$nextTick(() => this.renderBTEquityChart())
			} catch (e) {
				alert("Error: " + this.surfaceFetchErrorLine(e.message, "backtest"))
			} finally {
				this.bt.loading = false
			}
		},
		// ── 24/7 Fund Monitor (sprint89) ──────────────────────────────────────
		startFundMonitor() {
			// stop any existing timer first
			if (this.fundMonitor.autoRefreshTimer) {
				clearInterval(this.fundMonitor.autoRefreshTimer)
				this.fundMonitor.autoRefreshTimer = null
			}
			this.fetchFunds()
			// auto-refresh every 30 minutes (matches /fund-lab/live cache TTL)
			this.fundMonitor.autoRefreshTimer = setInterval(() => {
				if (this.tab === "funds") this.fetchFunds()
				else {
					clearInterval(this.fundMonitor.autoRefreshTimer)
					this.fundMonitor.autoRefreshTimer = null
				}
			}, 1800000)
		},
		async ibkrPing() {
			this.ibkr.pingResult = null
			this.ibkr.loading = true
			try {
				const r = await fetch("/api/ibkr/ping", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ host: this.ibkr.host || "127.0.0.1", mode: this.ibkr.mode }),
				})
				this.ibkr.pingResult = await r.json()
			} catch (e) {
				this.ibkr.pingResult = { reachable: false, message: "Probe failed: " + e.message }
			} finally {
				this.ibkr.loading = false
			}
		},
		async ibkrConnect() {
			this.ibkr.loading = true
			try {
				const r = await fetch("/api/ibkr/connect", {
					method: "POST",
					headers: { "Content-Type": "application/json", "X-API-Key": window._apiKey || "dev-secret-local" },
					body: JSON.stringify({ mode: this.ibkr.mode, host: this.ibkr.host || "127.0.0.1" }),
				})
				let d = {}
				try {
					d = await r.json()
				} catch (_x) {}
				if (d.diagnosis) this.ibkr.diagnosis = d.diagnosis
				if (!r.ok || d.ok === false) throw new Error(this.ibkrFormatConnectError(r.status, d))
				this.ibkr.connected = true
				await this.ibkrRefreshAll()
			} catch (e) {
				const msg = this.ibkrFormatConnectError(0, { message: e.message })
				const hint = (this.ibkr.diagnosis && this.ibkr.diagnosis.hint) || ""
				alert("IBKR connect: " + msg + (hint ? "\n\n" + hint : ""))
			} finally {
				this.ibkr.loading = false
			}
		},
		async ibkrDisconnect() {
			await fetch("/api/ibkr/disconnect", {
				method: "POST",
				headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
			}).catch(() => {})
			this.ibkr.connected = false
			this.ibkr.account = null
			this.ibkr.positions = []
			this.ibkr.openOrders = []
			this.ibkr.recentFills = []
			this.ibkr.readiness = null
			this.ibkr.diagnostics = null
		},
		async ibkrFetchAccount() {
			this.ibkr.loading = true
			try {
				const r = await fetch("/api/ibkr/account", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) throw new Error("status " + r.status)
				this.ibkr.account = await r.json()
			} catch (e) {
				console.warn("ibkr account failed", e)
			} finally {
				this.ibkr.loading = false
			}
		},
		async ibkrFetchPositions() {
			try {
				const r = await fetch("/api/ibkr/positions", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) throw new Error("status " + r.status)
				const d = await r.json()
				this.ibkr.positions = d.positions || []
				this.ibkr.lastSyncedAt = new Date().toLocaleTimeString()
			} catch (e) {
				console.warn("ibkr positions failed", e)
			}
		},
		async ibkrFetchOpenOrders() {
			try {
				const r = await fetch("/api/ibkr/open-orders", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				const d = await r.json()
				this.ibkr.openOrders = d.orders || []
			} catch (e) {
				console.warn("ibkr open orders failed", e)
			}
		},
		async ibkrFetchRecentFills() {
			try {
				const r = await fetch("/api/ibkr/recent-fills", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				const d = await r.json()
				this.ibkr.recentFills = d.fills || []
			} catch (e) {
				console.warn("ibkr fills failed", e)
			}
		},
		async ibkrFetchPortfolioCompare() {
			try {
				const r = await fetch("/api/portfolio/monitor")
				if (!r.ok) return
				const d = await r.json()
				const manual = (d.positions || []).length
				const broker = (this.ibkr.positions || []).length
				let note = ""
				if (manual > 0 && broker === 0 && this.ibkr.connected) {
					note = `Portfolio page has ${manual} position(s) but IBKR shows 0 — local book is research/manual until broker sync.`
				} else if (manual > broker && broker > 0) {
					note = `Portfolio=${manual} local rows vs IBKR=${broker} broker positions — reconcile stops/metadata on Portfolio tab.`
				} else if (this.ibkr.connected) {
					note =
						"When connected, IBKR positions are broker truth; Portfolio tab overlays stop/target research fields."
				}
				this.ibkr.portfolioCompare = { manual, broker, note }
			} catch (e) {
				console.warn("portfolio compare failed", e)
			}
		},
		async ibkrRefreshAll() {
			await this.ibkrFetchPortfolioCompare().catch(() => {})
			await this.ibkrFetchStatus()
			if (this.ibkr.connected) {
				await this.ibkrFetchAccount()
				await this.ibkrFetchPositions()
				await Promise.all([this.ibkrFetchOpenOrders(), this.ibkrFetchRecentFills()])
				await this.ibkrFetchPortfolioCompare().catch(() => {})
				await this.ibkrFetchStatus()
			}
		},
		ibkrOrderNotional() {
			const f = this.ibkr.orderForm
			const qty = Number(f.qty) || 0
			const px = Number(f.limitPrice) || Number(f.stopPrice) || Number(f.targetPrice) || 0
			const notional =
				px > 0 && qty > 0
					? "$" + (px * qty).toLocaleString(undefined, { maximumFractionDigits: 0 })
					: "MKT — price at fill"
			let risk = "—"
			if (f.useBracket && f.stopPrice && qty) {
				const entry = Number(f.limitPrice) || Number(f.targetPrice) || Number(f.stopPrice)
				const stop = Number(f.stopPrice)
				const per = f.action === "BUY" ? entry - stop : stop - entry
				if (per > 0) risk = "$" + (per * qty).toFixed(0) + " max (stop distance)"
			} else if (f.orderType === "STP" && f.stopPrice && qty) {
				risk = "Stop trigger @ $" + f.stopPrice + " (risk depends on fill)"
			}
			return { notional, risk }
		},
		ibkrBracketPreview() {
			const f = this.ibkr.orderForm
			const stop = Number(f.stopPrice) || 0,
				target = Number(f.targetPrice) || 0,
				entry = Number(f.limitPrice) || 0
			let riskReward = "Enter stop + target"
			if (stop && target) {
				const isBuy = f.action === "BUY"
				const ref = entry || (isBuy ? target : stop)
				const risk = isBuy ? ref - stop : stop - ref
				const reward = isBuy ? target - ref : ref - target
				if (risk > 0 && reward > 0)
					riskReward = `$${(risk * Number(f.qty || 0)).toFixed(0)} risk · $${(reward * Number(f.qty || 0)).toFixed(0)} reward · R:R ${(reward / risk).toFixed(2)}:1`
			}
			return {
				ocaNote:
					stop && target
						? "OCA group assigned on transmit (one child cancels the other)"
						: "Pending stop/target",
				riskReward,
				transmitNote: "Parent transmit=false until target child attached; final leg transmits all",
			}
		},
		ibkrPreviewOrder() {
			const f = this.ibkr.orderForm
			const sym = (f.symbol || "").toUpperCase()
			if (!sym) {
				this.ibkr.orderError = "Symbol required"
				return
			}
			this.ibkr.orderError = ""
			if (f.useBracket) {
				this.ibkr.orderPreview = `BRACKET PREVIEW (not transmitted)\n${f.action} ${f.qty}x ${sym}\nEntry: ${f.orderType === "LMT" && f.limitPrice ? "LMT $" + f.limitPrice : "MKT"}\nStop: $${f.stopPrice || "?"}\nTarget: $${f.targetPrice || "?"}\nTIF: ${f.tif || "DAY"}\n${this.ibkrBracketSummary()}\n${this.ibkrBracketPreview().transmitNote}`
			} else {
				const px =
					f.orderType === "LMT"
						? "LMT $" + (f.limitPrice || "?")
						: f.orderType === "STP"
							? "STP @ $" + (f.stopPrice || "?")
							: "MKT"
				this.ibkr.orderPreview = `ORDER PREVIEW (not transmitted)\n${f.action} ${f.qty}x ${sym} ${px}\nTIF: ${f.tif || "DAY"}\nNotional: ${this.ibkrOrderNotional().notional}\nEst. risk: ${this.ibkrOrderNotional().risk}`
			}
		},
		async ibkrPlaceOrder() {
			// SAFETY: block when circuit breaker tripped
			if (this.cc_status && this.cc_status.breaker) {
				this.ibkr.orderError =
					"⛔ Circuit breaker is TRIPPED (" +
					(this.cc_status.breaker_reason || "unknown") +
					"). Reset before trading."
				return
			}
			// SAFETY: hard confirm on LIVE mode
			const f = this.ibkr.orderForm
			const sym = (f.symbol || "").toUpperCase()
			if (!sym) {
				this.ibkr.orderError = "Symbol required"
				return
			}
			if (f.orderType === "STP" && !f.stopPrice) {
				this.ibkr.orderError = "Stop trigger price required for STP orders"
				return
			}
			if (f.orderType === "LMT" && !f.limitPrice) {
				this.ibkr.orderError = "Limit price required for LMT orders"
				return
			}
			const px =
				f.orderType === "MKT"
					? "MKT"
					: f.orderType === "LMT"
						? "LMT @ $" + (f.limitPrice || "?")
						: "STP @ $" + (f.stopPrice || "?")
			const summary = f.action + " " + f.qty + " " + sym + " " + px + " TIF " + (f.tif || "DAY")
			if (this.ibkr.mode === "live") {
				const typed = window.prompt(
					"⚠ LIVE ORDER\n\n" +
						summary +
						'\n\nThis will submit a REAL order to IBKR.\nType the ticker symbol "' +
						sym +
						'" to confirm:',
				)
				if (typed !== sym) {
					this.ibkr.orderError = "Cancelled — confirmation did not match."
					return
				}
			} else {
				if (!window.confirm("PAPER ORDER\n\n" + summary + "\n\nProceed?")) return
			}
			this.ibkr.loading = true
			this.ibkr.orderResult = null
			this.ibkr.orderError = ""
			this.ibkr.orderPreview = null
			try {
				const body = {
					symbol: sym,
					sec_type: f.secType,
					action: f.action,
					quantity: Number(f.qty),
					order_type: f.orderType,
					tif: f.tif || "DAY",
				}
				if (f.orderType === "LMT" && f.limitPrice) body.limit_price = Number(f.limitPrice)
				if (f.orderType === "STP" && f.stopPrice) body.stop_price = Number(f.stopPrice)
				const headers = {
					"Content-Type": "application/json",
					"X-API-Key": window._apiKey || "dev-secret-local",
				}
				if (this.ibkr.mode === "live") headers["X-Confirm-Live-Order"] = "CONFIRMED"
				const r = await fetch("/api/ibkr/order", { method: "POST", headers, body: JSON.stringify(body) })
				const d = await r.json()
				if (!r.ok) throw new Error(d.detail || "Order failed")
				this.ibkr.orderResult = d
				await this.ibkrRefreshAll()
			} catch (e) {
				this.ibkr.orderError = e.message
			} finally {
				this.ibkr.loading = false
			}
		},

		// ── BRACKET ORDER (parent + stop + target, OCA) ─────────────────────────
		ibkrBracketSummary() {
			const f = this.ibkr.orderForm
			const e = Number(f.limitPrice) || 0,
				s = Number(f.stopPrice) || 0,
				t = Number(f.targetPrice) || 0
			if (!s || !t) return "Enter stop and target to compute R:R"
			if (!e) return "Entry will be MKT — R:R will be calculated from fill price"
			const isBuy = f.action === "BUY"
			const risk = isBuy ? e - s : s - e
			const reward = isBuy ? t - e : e - t
			if (risk <= 0) return "⚠ Bad geometry: stop is on wrong side of entry"
			if (reward <= 0) return "⚠ Bad geometry: target is on wrong side of entry"
			const rr = (reward / risk).toFixed(2)
			const tier = rr >= 3 ? "🟢 TRADE-tier" : rr >= 2 ? "🟡 WATCH-tier" : "🔴 Below threshold"
			let kind = "STP"
			if (f.trail) {
				const tv = Number(f.trailValue) || 0
				kind = tv > 0 ? "TRAIL " + (f.trailKind === "percent" ? tv + "%" : "$" + tv) : "TRAIL (default)"
			}
			return `Risk $${risk.toFixed(2)}/sh · Reward $${reward.toFixed(2)}/sh · R:R ${rr}:1 · ${tier} · stop-kind: ${kind}`
		},
		ibkrAcceptSuggestedBracket() {
			const f = this.ibkr.orderForm
			if (f._suggestedStop) f.stopPrice = f._suggestedStop
			if (f._suggestedTarget) f.targetPrice = f._suggestedTarget
			f.useBracket = true
		},
		async ibkrPlaceBracket() {
			if (this.cc_status && this.cc_status.breaker) {
				this.ibkr.orderError =
					"⛔ Circuit breaker TRIPPED (" +
					(this.cc_status.breaker_reason || "unknown") +
					"). Reset before trading."
				return
			}
			const f = this.ibkr.orderForm
			const sym = (f.symbol || "").toUpperCase()
			const qty = Number(f.qty) || 0
			const stop = Number(f.stopPrice) || 0
			const target = Number(f.targetPrice) || 0
			const entry = f.limitPrice ? Number(f.limitPrice) : null
			if (!sym) {
				this.ibkr.orderError = "Symbol required"
				return
			}
			if (!qty || qty <= 0) {
				this.ibkr.orderError = "Quantity required"
				return
			}
			if (!stop || !target) {
				this.ibkr.orderError = "Bracket requires stop + target"
				return
			}
			// Geometry sanity
			if (f.action === "BUY") {
				if (entry !== null && !(stop < entry && entry < target)) {
					this.ibkr.orderError = "BUY bracket needs stop<entry<target"
					return
				}
				if (entry === null && !(stop < target)) {
					this.ibkr.orderError = "BUY bracket needs stop<target"
					return
				}
			} else {
				if (entry !== null && !(target < entry && entry < stop)) {
					this.ibkr.orderError = "SELL bracket needs target<entry<stop"
					return
				}
				if (entry === null && !(target < stop)) {
					this.ibkr.orderError = "SELL bracket needs target<stop"
					return
				}
			}
			const risk = f.action === "BUY" ? (entry || target) - stop : stop - (entry || target)
			const reward = f.action === "BUY" ? target - (entry || stop) : (entry || stop) - target
			const rr = risk > 0 ? (reward / risk).toFixed(2) : "?"
			// ── Pre-trade slippage gate (BLOCK on illiquid; WARN on costly) ──
			let slipVerdict = null,
				slipReasonsText = ""
			try {
				const refPx = entry || target || stop || 0
				if (refPx > 0) {
					const sr = await fetch("/api/slippage/check", {
						method: "POST",
						headers: {
							"Content-Type": "application/json",
							"X-API-Key": window._apiKey || "dev-secret-local",
						},
						body: JSON.stringify({ ticker: sym, size_shares: qty, current_price: refPx, side: f.action }),
					})
					if (sr.ok) {
						slipVerdict = await sr.json()
						slipReasonsText = (slipVerdict.reasons || []).join("\n  • ")
					}
				}
			} catch (_) {
				if (this.ibkr.mode === "live") {
					this.ibkr.orderError =
						"🛑 SLIPPAGE GATE UNAVAILABLE — live orders blocked until /api/slippage/check responds."
					this.ibkr.loading = false
					return
				}
			}
			if (slipVerdict && slipVerdict.verdict === "BLOCK") {
				this.ibkr.orderError =
					"🛑 SLIPPAGE BLOCK:\n  • " +
					slipReasonsText +
					"\n\n(Spread " +
					slipVerdict.spread_bps +
					"bps · ADV-participation " +
					slipVerdict.participation_pct +
					"%)"
				this.ibkr.loading = false
				return
			}
			const slipBanner = slipVerdict
				? slipVerdict.verdict === "WARN"
					? `\n\n⚠ SLIPPAGE WARN:\n  • ${slipReasonsText}\n  (Spread ${slipVerdict.spread_bps}bps · ADV-pct ${slipVerdict.participation_pct}% · Round-trip ${slipVerdict.estimate && slipVerdict.estimate.round_trip_bps}bps)`
					: `\n\n✓ Slippage gate: PASS (spread ${slipVerdict.spread_bps}bps · cost ${slipVerdict.estimate && slipVerdict.estimate.round_trip_bps}bps RT)`
				: ""
			const summary =
				`🎯 BRACKET ${f.action} ${qty}x ${sym}\nEntry: ${entry ? "$" + entry : "MKT"}\nStop: $${stop} (risk $${risk.toFixed(2)}/sh)\nTarget: $${target} (reward $${reward.toFixed(2)}/sh)\nR:R: ${rr}:1` +
				slipBanner
			if (this.ibkr.mode === "live") {
				const typed = window.prompt(
					"⚠ LIVE BRACKET ORDER\n\n" + summary + '\n\nReal money. Type "' + sym + '" to confirm:',
				)
				if (typed !== sym) {
					this.ibkr.orderError = "Cancelled — confirmation did not match."
					return
				}
			} else {
				if (!window.confirm("PAPER BRACKET\n\n" + summary + "\n\nProceed?")) return
			}
			this.ibkr.loading = true
			this.ibkr.orderResult = null
			this.ibkr.orderError = ""
			this.ibkr.orderPreview = null
			try {
				const body = {
					symbol: sym,
					sec_type: f.secType,
					action: f.action,
					quantity: qty,
					entry_price: entry,
					stop_price: stop,
					take_profit: target,
				}
				// Trail variant — replaces STP child with TRAIL
				if (f.trail) {
					body.trail = true
					const tv = Number(f.trailValue) || 0
					if (tv > 0) {
						if (f.trailKind === "percent") body.trail_percent = tv
						else body.trail_amount = tv
					}
				}
				const headers = {
					"Content-Type": "application/json",
					"X-API-Key": window._apiKey || "dev-secret-local",
				}
				if (this.ibkr.mode === "live") headers["X-Confirm-Live-Order"] = "CONFIRMED"
				const r = await fetch("/api/ibkr/bracket", { method: "POST", headers, body: JSON.stringify(body) })
				const d = await r.json()
				if (!r.ok) throw new Error(d.detail || "Bracket failed")
				// Surface as orderResult so existing success card renders it
				this.ibkr.orderResult = {
					order_id: d.parent_order_id,
					status: "BRACKET " + (d.parent_status || "Submitted"),
					filled: d.parent_filled || 0,
					avg_fill_price: d.parent_avg_fill || 0,
					warning:
						d.warning ||
						"Children: " +
							(d.stop_kind || "STP") +
							"#" +
							d.stop_order_id +
							" / TGT#" +
							d.target_order_id +
							" (OCA " +
							d.oca_group +
							")",
				}
				// Archive previous working bracket so back-to-back placements don't lose context
				if (this.ibkr.workingBracket) {
					this.ibkr.bracketArchive.unshift({ ...this.ibkr.workingBracket, archived_at: Date.now() })
					this.ibkr.bracketArchive = this.ibkr.bracketArchive.slice(0, 8) // cap at 8
				}
				// Stash full bracket detail for the WORKING BRACKET panel
				this.ibkr.workingBracket = {
					symbol: sym,
					parent_order_id: d.parent_order_id,
					stop_order_id: d.stop_order_id,
					target_order_id: d.target_order_id,
					oca_group: d.oca_group,
					stop_kind: d.stop_kind || "STP",
					stop_price: stop,
					take_profit: target,
					parent_status: d.parent_status || "Submitted",
					parent_filled: d.parent_filled || 0,
					parent_avg_fill: d.parent_avg_fill || 0,
					trail_amount: d.trail_amount,
					trail_percent: d.trail_percent,
					warning: d.warning || null,
					ts: Date.now(),
				}
				// Start auto-poll loop (5s) for live status of all 3 legs
				this.ibkrStartBracketPoll()
				await this.ibkrRefreshAll()
			} catch (e) {
				this.ibkr.orderError = e.message
			} finally {
				this.ibkr.loading = false
			}
		},

		// ── Bracket live polling + cancel ──────────────────────────────────────
		ibkrStartBracketPoll() {
			if (this._bracketPollTimer) {
				clearInterval(this._bracketPollTimer)
				this._bracketPollTimer = null
			}
			// Immediate refresh, then every 5s
			this.ibkrPollBracket()
			this._bracketPollTimer = setInterval(() => {
				if (!this.ibkr.workingBracket) {
					this.ibkrStopBracketPoll()
					return
				}
				this.ibkrPollBracket()
			}, 5000)
		},
		ibkrStopBracketPoll() {
			if (this._bracketPollTimer) {
				clearInterval(this._bracketPollTimer)
				this._bracketPollTimer = null
			}
		},
		async ibkrPollBracket() {
			const wb = this.ibkr.workingBracket
			if (!wb) return
			try {
				const r = await fetch("/api/ibkr/open-orders", {
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) return
				const d = await r.json()
				const byId = {}
				;(d.orders || []).forEach((o) => {
					byId[o.order_id] = o
				})
				const p = byId[wb.parent_order_id],
					s = byId[wb.stop_order_id],
					t = byId[wb.target_order_id]
				if (p) {
					wb.parent_status = p.status || wb.parent_status
					wb.parent_filled = p.filled || wb.parent_filled
					wb.parent_avg_fill = p.avg_fill_price || wb.parent_avg_fill
				}
				if (s) {
					wb.stop_status = s.status || ""
				}
				if (t) {
					wb.target_status = t.status || ""
				}
				wb.pollAge = Math.round((Date.now() - wb.ts) / 1000)
				// Auto-stop poll when all legs reached terminal state
				const term = (v) =>
					v &&
					["filled", "cancelled", "canceled", "inactive", "pendingcancel"].includes((v || "").toLowerCase())
				const allDone =
					term(wb.parent_status) &&
					(wb.parent_filled > 0 ? term(wb.stop_status) || term(wb.target_status) : term(wb.stop_status))
				if (allDone) {
					// Auto-log to closed_trades.jsonl when we have entry + exit price
					if (wb.parent_filled > 0 && !wb._ledgerLogged) {
						const stopFilled = (wb.stop_status || "").toLowerCase() === "filled"
						const tgtFilled = (wb.target_status || "").toLowerCase() === "filled"
						const exitPx = tgtFilled ? wb.take_profit : stopFilled ? wb.stop_price : 0
						if (exitPx > 0 && wb.parent_avg_fill > 0) {
							wb._ledgerLogged = true
							try {
								await fetch("/api/ledger/close-trade", {
									method: "POST",
									headers: {
										"Content-Type": "application/json",
										"X-API-Key": window._apiKey || "dev-secret-local",
									},
									body: JSON.stringify({
										ticker: wb.symbol,
										direction: "LONG",
										entry_price: wb.parent_avg_fill,
										exit_price: exitPx,
										shares: wb.parent_filled,
										stop_price: wb.stop_price,
										strategy_id: "ibkr_bracket",
										source: "ibkr_bracket_auto",
									}),
								})
								// Refresh strategy health so the new row appears
								this.fetchStrategyHealth()
							} catch (_) {
								/* silent */
							}
						}
					}
					this.ibkrStopBracketPoll()
				}
			} catch (e) {
				/* silent — keep last known state */
			}
		},
		async ibkrCancelBracket() {
			const wb = this.ibkr.workingBracket
			if (!wb) return
			if (
				!window.confirm(
					"Cancel bracket for " +
						wb.symbol +
						"?\n\nParent #" +
						wb.parent_order_id +
						" + stop + target will be cancelled at IB.",
				)
			)
				return
			try {
				const body = {
					parent_order_id: wb.parent_order_id,
					stop_order_id: wb.stop_order_id,
					target_order_id: wb.target_order_id,
				}
				const r = await fetch("/api/ibkr/cancel-bracket", {
					method: "POST",
					headers: { "Content-Type": "application/json", "X-API-Key": window._apiKey || "dev-secret-local" },
					body: JSON.stringify(body),
				})
				const d = await r.json()
				wb.cancelOk = !!d.ok
				wb.cancelMsg = d.ok
					? "✓ Cancel submitted for all 3 legs at " + new Date().toLocaleTimeString()
					: "Cancel partial: " + JSON.stringify(d.results || d.detail || d)
				// Re-poll to pick up PendingCancel/Cancelled status
				this.ibkrPollBracket()
			} catch (e) {
				wb.cancelOk = false
				wb.cancelMsg = "Cancel failed: " + e.message
			}
		},
		ibkrDismissBracket() {
			this.ibkrStopBracketPoll()
			if (this.ibkr.workingBracket) {
				this.ibkr.bracketArchive.unshift({ ...this.ibkr.workingBracket, archived_at: Date.now() })
				this.ibkr.bracketArchive = this.ibkr.bracketArchive.slice(0, 8)
			}
			this.ibkr.workingBracket = null
		},

		fundIcon(name) {
			return name === "FUND_ALPHA" ? "🚀" : name === "FUND_PENDA" ? "🛡" : name === "FUND_MACRO" ? "🌐" : "⚙️"
		},
		fundColor(name) {
			return name === "FUND_ALPHA"
				? "var(--green)"
				: name === "FUND_PENDA"
					? "var(--blue)"
					: name === "FUND_MACRO"
						? "var(--purple)"
						: "var(--orange)"
		},

		// ── Playbook → IBKR bracket helper ─────────────────────────────────────
		// Pre-fills the order ticket using the Playbook card's R-based size, then
		// switches to the IBKR tab. PM still has to confirm — no silent submission.
		sendPlaybookToIbkr(r) {
			if (!r || !r.ticker) {
				alert("Missing ticker")
				return
			}
			if (!this.cc_status || !this.cc_status.ibkr_connected) {
				alert("IBKR not connected. Open the IBKR pill to connect first.")
				return
			}
			const equity =
				(this.pf && this.pf.summary && (this.pf.summary.total_value || this.pf.summary.account_equity)) ||
				100000
			const entry = Number(r.entry_price) || 0
			const stop = Number(r.stop_price) || 0
			let qty = 0
			if (entry > 0 && stop > 0 && entry > stop) {
				// 1R = 1% of equity (matches the size pill in Playbook)
				const riskDollars = equity * 0.01
				const perShareRisk = entry - stop
				qty = Math.max(1, Math.floor(riskDollars / perShareRisk))
			}
			this.ibkr.orderForm.symbol = (r.ticker || "").toUpperCase()
			this.ibkr.orderForm.action = "BUY"
			this.ibkr.orderForm.secType = "STK"
			this.ibkr.orderForm.qty = qty || 1
			this.ibkr.orderForm.orderType = entry > 0 ? "LMT" : "MKT"
			if (entry > 0) this.ibkr.orderForm.limitPrice = entry
			// Stash bracket details for the IBKR view to surface (optional bracket builder UI to come)
			this.ibkr.orderForm._suggestedStop = stop || null
			this.ibkr.orderForm._suggestedTarget = Number(r.target_price) || null
			this.ibkr.orderForm._suggestedRR = r.risk_reward || null
			// Auto-enable bracket if both stop + target are available — close alpha→execution loop
			if (stop > 0 && Number(r.target_price) > 0) {
				this.ibkr.orderForm.stopPrice = stop
				this.ibkr.orderForm.targetPrice = Number(r.target_price)
				this.ibkr.orderForm.useBracket = true
			}
			this.tab = "ibkr"
		},

		// ── PM Strip (model funds mini-cards, refreshed lazily) ────────────────

		// ── Model Funds (productized fund cards) ──────────────────────────────

		// ── Trade Intelligence ────────────────────────────────────────────────

		async selectTradeIntelTrade(t) {
			if (!t) return
			this.tradeIntel.selectedTradeKey = (t.ticker || "") + "|" + (t.entry_time || "")
			await this.fetchSelectedTradeAIReview()
		},
		sortOpps() {
			const k = this.oppsSort
			this.opps.sort((a, b) =>
				k === "ticker"
					? (a.ticker || "").localeCompare(b.ticker || "")
					: (Number(b[k]) || 0) - (Number(a[k]) || 0),
			)
		},
		sleeveSparkPoints(curve) {
			if (!curve || curve.length < 2) return ""
			const mn = Math.min(...curve),
				mx = Math.max(...curve),
				rg = mx - mn || 1
			return curve.map((v, i) => `${i * 4},${18 - Math.round(((v - mn) / rg) * 16)}`).join(" ")
		},
		marketRoleFor(sym) {
			const raw = (sym || "").toUpperCase()
			const s = raw.replace(/^\^/, "")
			if (
				["SPY", "QQQ", "IWM", "DIA", "BTC-USD", "ETH-USD"].includes(raw) ||
				["SPY", "QQQ", "IWM", "DIA"].includes(s)
			)
				return "risk-on"
			if (s === "VIX" || raw === "^VIX") return "vol"
			if (["TLT", "TNX", "^TNX", "US10Y"].includes(raw) || ["TLT", "TNX"].includes(s)) return "rates"
			if (["GLD", "DXY", "UUP"].includes(raw) || ["GLD", "DXY", "UUP"].includes(s)) return "defensive"
			if (s.startsWith("XL")) return "sector"
			return "macro"
		},
		normalizeMarketItem(raw) {
			const r = raw && typeof raw === "object" ? raw : {}
			const sym = (r.symbol || "").toUpperCase()
			return {
				symbol: sym,
				name: r.name || sym || "—",
				price: Number(r.price) || 0,
				change_pct: Number(r.change_pct) || 0,
				change_5d: r.change_5d != null ? Number(r.change_5d) : null,
				change_20d: r.change_20d != null ? Number(r.change_20d) : null,
				role: this.marketRoleFor(sym),
				error: !!r.error,
			}
		},
		applyPulseToMarketStrip(pulse) {
			if (!pulse || typeof pulse !== "object") return
			const trust = this.today7.trust || {}
			const snap = pulse.as_of || pulse.timestamp || trust.as_of || null
			if (snap) this.marketStrip.snapshotAt = snap
			this.marketStrip.renderedAt = new Date().toISOString()
			const idx = (pulse.indices || []).filter(Boolean)
			if (idx.length) {
				this.indices = idx.map((i) => this.normalizeMarketItem(i))
				this.marketStrip.fromPulse = true
				if (!this.marketStrip.source) this.marketStrip.source = "today_pulse"
			}
			const leaders = pulse.sector_leaders || []
			const laggards = pulse.sector_laggards || []
			const seen = {}
			const merged = []
			;[...leaders, ...laggards].forEach((s) => {
				if (!s) return
				const n = this.normalizeMarketItem(s)
				const key = n.symbol || n.name
				if (!key || seen[key]) return
				seen[key] = true
				const k = (n.symbol || n.name || "").toUpperCase()
				n.leaderBadge = leaders.some((x) => (x.symbol || x.name || "").toUpperCase() === k)
				n.laggardBadge = laggards.some((x) => (x.symbol || x.name || "").toUpperCase() === k)
				merged.push(n)
			})
			merged.forEach((s, i) => {
				s.rank = i + 1
			})
			if (merged.length) {
				this.sectors = merged
				this.marketStrip.fromPulse = true
			}
		},
		_marketStripFromLive(d) {
			const want = ["SPY", "QQQ", "IWM", "^VIX", "VIX", "GLD", "TLT", "UUP", "DXY"]
			const pool = [...(d.indices || []), ...(d.macro || [])]
			const bySym = {}
			pool.forEach((item) => {
				const n = this.normalizeMarketItem(item)
				const key = (n.symbol || "").toUpperCase()
				if (!key) return
				bySym[key] = n
				if (key === "VIX") bySym["^VIX"] = n
			})
			const ordered = []
			want.forEach((w) => {
				const k = w.toUpperCase()
				const hit = bySym[k]
				if (hit && !ordered.some((x) => (x.symbol || "").toUpperCase() === (hit.symbol || "").toUpperCase()))
					ordered.push(hit)
			})
			pool.forEach((item) => {
				const n = this.normalizeMarketItem(item)
				const key = (n.symbol || "").toUpperCase()
				if (key && !ordered.some((x) => (x.symbol || "").toUpperCase() === key)) ordered.push(n)
			})
			this.indices = ordered.slice(0, 12)
			const secs = (d.sectors || []).map((s) => this.normalizeMarketItem(s))
			secs.sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0))
			const n = secs.length
			secs.forEach((s, i) => {
				s.rank = i + 1
				s.leaderBadge = i < 3
				s.laggardBadge = n > 3 && i >= n - 3
			})
			this.sectors = secs
			if (d.macro) this.macro = (d.macro || []).map((m) => this.normalizeMarketItem(m))
			if (d.regime) this.regime = d.regime
			if (d.trust) this.trust = d.trust
			this.marketStrip.source = (d.trust && d.trust.source) || "market_data_service"
			const snap = (d.trust && d.trust.as_of) || d.timestamp || null
			this.marketStrip.snapshotAt = snap
			this.marketStrip.lastOk = snap || new Date().toISOString()
			this.marketStrip.renderedAt = new Date().toISOString()
			this.marketStrip.fromPulse = false
			this.marketStrip.error = ""
		},
		async fetchMarketStrip() {
			if (this.marketStrip.loading) return
			this.marketStrip.loading = true
			try {
				const r = await this.ccFetch("/api/live/market", { retries: 3, backoff: 500 })
				if (!r || !r.ok) {
					const msg =
						r && r.status === 503
							? "API warming up — retry in a few seconds"
							: "Market data unavailable (HTTP " + (r ? r.status : "?") + ")"
					this.marketStrip.error = msg
					if (!this.indices.length) this.applyPulseToMarketStrip(this.today7.pulse)
					return
				}
				const d = await r.json()
				if (d && d.error) {
					this.marketStrip.error = String(d.error)
					if (!this.indices.length) this.applyPulseToMarketStrip(this.today7.pulse)
					return
				}
				this._marketStripFromLive(d || {})
			} catch (e) {
				console.warn("fetchMarketStrip failed", e)
				this.marketStrip.error = "Market strip fetch failed — check yfinance / API"
				if (!this.indices.length) this.applyPulseToMarketStrip(this.today7.pulse)
			} finally {
				this.marketStrip.loading = false
			}
		},
		async fetchToday7() {
			try {
				const r = await this.ccFetch("/api/v7/today", { retries: 2, backoff: 500, timeoutMs: 15000 })
				if (!r || !r.ok) throw new Error("HTTP " + (r ? r.status : "fail"))
				const d = await r.json()
				this.captureInstantDegradedBanner(d)
				if (d && d.error) throw new Error(String(d.error))
				if (!d || !d.market_regime) throw new Error("incomplete today payload")
				this.today7.regime = d.market_regime || null
				this.today7.decision_authority = d.decision_authority || null
				this.today7.top_ranked = d.top_5 || []
				this.today7.todays_decision = d.todays_decision || null
				this.today7.bdr_summary = d.bdr_summary || null
				if (this.bdrShouldAutoOpen()) this.bdrPanelOpen = true
				this.today7.feature_ic_status = d.feature_ic_status || null
				this.today7.ml_advisory = d.ml_advisory || null
				this.today7.best_action = d.best_action || null
				this.today7.overlap_warning = d.overlap_warning || null
				this.today7.near_miss = d.near_miss || []
				this.today7.score_reconciliation = d.score_reconciliation || null
				this.today7.no_setup_diagnosis = d.no_setup_diagnosis || null
				this.today7.quant_cluster_hints = d.quant_cluster_hints || []
				this.today7.unlock_deploy = d.unlock_deploy || null
				this.today7.regime_wait_explanation = d.regime_wait_explanation || []
				this.today7.monitor_triggers = d.monitor_triggers || []
				this.today7.sleeve_summary = d.sleeve_summary || null
				this.today7.execution_readiness = d.execution_readiness || d.best_action?.execution_readiness || null
				this.today7.evidence_badges = d.evidence_badges || null
				this.today7.cross_asset_confirmation = d.cross_asset_confirmation || null
				this.today7.index_regime_summary = d.index_regime_summary || null
				this.today7.regime_strip = d.regime_strip || null
				this.today7.regime_stack_summary = d.regime_stack_summary || null
				this.today7.allocator_stance = d.allocator_stance || null
				this.today7.ai_reason_codes = d.ai_reason_codes || []
				this.today7.filter_funnel = d.filter_funnel || null
				this.today7.decision_model = d.decision_model || null
				this.today7.decision_hierarchy = d.decision_hierarchy || null
				this.today7.passive_baseline = d.passive_baseline || null
				this.today7.complexity_challenge = d.complexity_challenge || null
				this.today7.restraint = d.restraint || null
				this.today7.surface_authority = d.surface_authority || null
				this.today7.crisis_regime = d.crisis_regime || null
				this.today7.naval_clarity = d.naval_clarity || null
				this.today7.buffett_clarity = d.buffett_clarity || null
				this.today7.index_fund_posture = d.index_fund_posture || null
				this.today7.principles_posture = d.principles_posture || null
				this.today7.avoid_grouped = d.avoid_grouped || null
				this.today7.bucket_quality = d.bucket_quality || []
				this.today7.avoid_list = (d.avoid_now || []).length
					? d.avoid_now || []
					: (d.avoid || []).map((a) =>
							typeof a === "string" ? { ticker: "—", reason: a, category: "regime" } : a,
						)
				this.today7.tradeability =
					(d.cc_state && d.cc_state.tradeability_state && d.cc_state.tradeability_state.tradeability) ||
					(d.decision_model && d.decision_model.honest_tradeability) ||
					(d.market_regime || {}).tradeability ||
					""
				this.today7.what_changed = d.what_changed || []
				this.today7.event_risks = d.event_risks || []
				this.today7.best_family = d.best_setup_family || null
				this.today7.pulse = d.market_pulse || null
				this.today7.narrative = d.narrative || ""
				this.today7.ai_narrative = d.ai_narrative || null
				this.today7.date = d.date || ""
				this.today7.trust = d.trust || {}
				this.today7.cc_state = d.cc_state || null
				this.today7.system_state = d.system_state || null
				this.today7.dashboard_monitors = d.dashboard_monitors || []
				this.today7.page_capability = d.page_capability || null
				if (!(this.today7.top_ranked || []).length && (d.degraded || d.instant_degraded)) {
					this.hydrateToday7FromCache()
					if (!(this.today7.top_ranked || []).length) {
						const bridged = this.playbookBridgeFromCaches()
						if (bridged.length) this.today7.top_ranked = bridged.slice(0, 5)
					}
				}
				if (this.isWaitDay() && !this.uiExpandAll) {
					this.today7.avoid_collapsed = true
					this.today7.ai_commentary_open = false
				}
				this.applyPulseToMarketStrip(this.today7.pulse)
				this.saveToday7ToCache(d)
				// DAY-OVER-DAY DIFF — tag NEW vs CARRYOVER vs MOVED
				try {
					const todayKey = d.date || new Date().toISOString().slice(0, 10)
					const prevRaw = localStorage.getItem("cc_yesterday_top")
					const prevDate = localStorage.getItem("cc_yesterday_date")
					const prev = prevRaw ? JSON.parse(prevRaw) : []
					const prevMap = {}
					prev.forEach((t, i) => {
						prevMap[t] = i + 1
					})
					;(this.today7.top_ranked || []).forEach((opp, i) => {
						const t = opp.ticker
						const newRank = i + 1
						if (!(t in prevMap)) {
							opp._diff = "NEW"
							opp._diffMove = null
						} else {
							const oldRank = prevMap[t]
							const move = oldRank - newRank
							opp._diff = move > 0 ? "UP" : move < 0 ? "DOWN" : "SAME"
							opp._diffMove = move
						}
					})
					// Stash today as "yesterday" if date changed (avoid stomping mid-day)
					if (prevDate !== todayKey) {
						localStorage.setItem(
							"cc_yesterday_top",
							JSON.stringify((this.today7.top_ranked || []).map((o) => o.ticker)),
						)
						localStorage.setItem("cc_yesterday_date", todayKey)
					}
				} catch (e) {
					console.warn("dod diff failed", e)
				}
				this.buildDecisionHubFromToday(d)
				if (this.today7.top_ranked.length) setTimeout(() => this.loadSparklines(this.today7.top_ranked), 200)
				if (!(this.pmStrip.funds || []).length) this.fetchFunds()
				try {
					const qa = await this.ccFetchJson("/api/v7/quant/sleeve-allocation", {
						tab: "today",
						retries: 1,
						backoff: 400,
					})
					if (qa.ok) this.today7.quant_alloc = qa.data
				} catch (e) {
					console.warn("quant sleeve-allocation", e)
				}
			} catch (e) {
				console.warn("v7/today fetch failed", e)
				this.today7.trust = {
					...(this.today7.trust || {}),
					stale: true,
					reason: String(e.message || e).slice(0, 140),
				}
				this.hydrateToday7FromCache()
				if (!(this.today7.top_ranked || []).length) {
					const bridged = this.playbookBridgeFromCaches()
					if (bridged.length) this.today7.top_ranked = bridged.slice(0, 5)
				}
				if (!this.playbookBoardHasContent()) this.fetchWarmupBriefBoard()
			}
		},
		hydrateToday7FromCache() {
			try {
				const raw = localStorage.getItem("cc_today7_snapshot")
				if (!raw) return
				const d = JSON.parse(raw)
				if (!d || !d.market_regime) return
				if ((this.today7.top_ranked || []).length && !this.today7.trust?.stale) return
				this.today7.regime = d.market_regime || null
				this.today7.decision_authority = d.decision_authority || null
				this.today7.top_ranked = d.top_5 || []
				this.today7.narrative = d.narrative || ""
				this.today7.pulse = d.market_pulse || null
				this.today7.filter_funnel = d.filter_funnel || null
				this.today7.date = d.date || ""
				this.today7.trust = { ...(d.trust || {}), stale: true, source: "local-cache" }
				this.applyPulseToMarketStrip(this.today7.pulse)
			} catch (err) {
				console.warn("today7 cache hydrate failed", err)
			}
		},
		saveToday7ToCache(d) {
			try {
				if (!d || !d.market_regime) return
				if (!(d.top_5 || []).length && (d.degraded || d.instant_degraded)) return
				localStorage.setItem(
					"cc_today7_snapshot",
					JSON.stringify({
						market_regime: d.market_regime,
						top_5: d.top_5 || [],
						decision_authority: d.decision_authority || null,
						market_pulse: d.market_pulse || null,
						filter_funnel: d.filter_funnel || null,
						narrative: d.narrative || "",
						date: d.date || "",
						trust: d.trust || {},
						saved_at: Date.now(),
					}),
				)
			} catch (e) {
				console.warn("today7 cache save failed", e)
			}
		},
		async fetchDecisionHub() {
			try {
				const r = await this.ccFetch("/api/v7/decision-hub", { retries: 3, backoff: 500 })
				if (!r || !r.ok) return
				const hub = await r.json()
				const local = this.decisionHub
				if (hub.warming && local?.decision_strip?.best_idea_now) {
					this.decisionHub = {
						...hub,
						decision_strip: local.decision_strip,
						monitoring: hub.monitoring || local.monitoring,
					}
				} else {
					this.decisionHub = hub
				}
			} catch (e) {
				console.warn("decision-hub", e)
			}
		},
		async fetchAINarrative() {
			if (this.today7.ai_loading) return
			this.today7.ai_commentary_open = true
			this.today7.ai_loading = true
			this.today7.ai_error = ""
			this.today7.ai_provider = "loading"
			try {
				const r = await this.ccFetch("/api/v7/today/ai-narrative", {
					retries: 2,
					backoff: 800,
					timeoutMs: 95000,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({
							regime_ctx: this.today7.regime,
							top_5: this.today7.top_ranked,
							market_pulse: this.today7.pulse,
							filter_funnel: this.today7.filter_funnel,
							narrative: this.today7.narrative,
						}),
					},
				})
				if (!r || !r.ok) {
					const st = r ? r.status : 0
					const warming = st === 503 || st === 502 || st === 0
					this.today7.ai_error = warming
						? this.surfaceWarmupLoadingLine("dashboard")
						: "Generation failed (HTTP " + (st || "no response") + ")."
					this.today7.ai_provider = warming ? "loading" : "error"
					return
				}
				const d = await r.json()
				this.today7.ai_provider = d.provider || "unknown"
				this.today7.ai_model = d.model || ""
				this.today7.ai_configured = d.configured === true
				if (d.setup_hint) this.today7.ai_setup_hint = d.setup_hint
				if (d.message && d.provider !== "stub") this.today7.ai_error = d.message
				if (d.ai_narrative) {
					this.today7.ai_narrative = d.ai_narrative
					this.today7.trust.ai_powered = d.configured === true && d.provider !== "stub"
					if (d.degraded || d.research_only || d.provider === "stub") {
						this.today7.ai_error = ""
					}
				} else {
					this.today7.ai_error = d.message || "AI commentary unavailable."
					if (!d.configured) this.today7.ai_provider = "none"
				}
			} catch (e) {
				console.warn("fetchAINarrative failed", e)
				const raw = String((e && e.message) || e || "")
				if (this.normalizeFetchError(raw)) {
					this.today7.ai_error = this.surfaceWarmupLoadingLine("dashboard")
					this.today7.ai_provider = "loading"
				} else if (/aborted|timeout/i.test(raw)) {
					this.today7.ai_error = "Narrative request timed out — retry after API warm-up."
					this.today7.ai_provider = "loading"
				} else {
					this.today7.ai_error = "Request failed: " + raw
					this.today7.ai_provider = "error"
				}
			} finally {
				this.today7.ai_loading = false
			}
		},
		async fetchRanked(opts = {}) {
			const hadRows = (this.rankedOpps.rows || []).length > 0
			if (!hadRows) this.hydrateRankedFromCache()
			const needsBoard = !(this.rankedOpps.rows || []).length
			this.rankedOpps.loading = needsBoard
			this.rankedOpps.refreshing = true
			try {
				if (needsBoard && !this.rankedOpps.actionFilter && !this.rankedOpps.sectorFilter) {
					await this.fetchWarmupBriefBoard()
					if (this.rankedOpps.rows.length) {
						this.rankedOpps.loading = false
					} else {
						try {
							const sr = await fetch("/api/v7/playbook/ranked/snapshot?limit=50", {
								signal: AbortSignal.timeout(5000),
							})
							if (sr.ok) this.applyRankedPayload(await sr.json(), { fromSnapshot: true })
						} catch (e) {
							console.warn("ranked snapshot hydrate failed", e)
						}
						if (this.rankedOpps.rows.length) this.rankedOpps.loading = false
					}
				}
				let u = "/api/v7/playbook/ranked?limit=50"
				if (this.rankedOpps.actionFilter) u += "&action=" + this.rankedOpps.actionFilter
				if (this.rankedOpps.sectorFilter) u += "&sector=" + this.rankedOpps.sectorFilter
				if (opts.refresh) u += "&refresh=true"
				const r = await fetch(u, { signal: AbortSignal.timeout(12000) })
				if (!r.ok) {
					if (r.status === 503) {
						try {
							const sr = await fetch("/api/v7/playbook/ranked/snapshot?limit=50", {
								signal: AbortSignal.timeout(5000),
							})
							if (sr.ok) {
								this.applyRankedPayload(await sr.json(), { fromSnapshot: true })
								return
							}
						} catch (e2) {
							console.warn("ranked snapshot fallback failed", e2)
						}
					}
					throw new Error("HTTP " + r.status)
				}
				this.applyRankedPayload(await r.json())
				this.rankedOpps.fetch_failed = false
				this.surfaceFetchHints.signals = {
					...(this.surfaceFetchHints.signals || {}),
					failed_fetch: false,
					error: "",
				}
				if (
					!this.rankedOpps.rows.length &&
					!this.rankedOpps.actionFilter &&
					!this.rankedOpps.sectorFilter &&
					!this.playbookIsEmergencyBoard()
				) {
					if (this.healthMode === "loading") await this.fetchWarmupBriefBoard()
					if (!this.rankedOpps.rows.length) {
						try {
							const sr = await fetch(
								"/api/v7/opportunity-scanner?regime=" + (this.regime.label || "BULL") + "&top_n=50",
							)
							if (sr.ok) {
								const sd = await sr.json()
								const cands = (sd.candidates || []).slice(0, 50)
								if (cands.length) {
									this.rankedOpps.rows = cands.map((c) => ({
										ticker: c.ticker || c.symbol,
										score: c.score || c.composite_score || 0,
										action: c.tag || c.action || "WATCH",
										sector_type: c.sector || "",
										entry_price: c.close || c.price,
										stop_price: c.stop_loss,
										target_price: c.activation || c.target,
										risk_reward: c.rr || 0,
										setup: c.strategy || c.engine || "scanner",
										grade: c.score >= 8 ? "A" : c.score >= 6 ? "B" : "C",
										thesis_conf: 0.6,
										timing_conf: 0.5,
										exec_conf: 0.5,
										data_conf: 0.7,
										why_now: c.tags ? c.tags.join(" · ") : c.reason || "",
									}))
									this.rankedOpps.source = "scanner"
									this.rankedOpps.board_mode = "compressed_fallback"
								}
							}
						} catch (e) {
							console.warn("scanner fallback failed", e)
						}
					}
				}
				if (this.rankedOpps.rows.length) this.loadSparklines(this.rankedOpps.rows)
				if ((this.rankedOpps.rows || []).length || (this.rankedOpps.near_miss || []).length)
					this.saveRankedToCache()
			} catch (e) {
				console.warn("ranked fetch failed", e)
				if (!this.playbookBoardHasContent()) {
					await this.fetchWarmupBriefBoard()
					this.rankedOpps.fetch_failed = !this.playbookBoardHasContent()
					if (this.rankedOpps.fetch_failed)
						this.surfaceFetchHints.signals = {
							...(this.surfaceFetchHints.signals || {}),
							failed_fetch: true,
							error: this.surfaceFetchStateMessage("failed_fetch"),
						}
				}
			} finally {
				this.rankedOpps.loading = false
				this.rankedOpps.refreshing = false
			}
		},
		applyRankedPayload(d, meta = {}) {
			if (!d || typeof d !== "object") return
			this.captureInstantDegradedBanner(d)
			if (d.degraded_banner) this.rankedOpps.degraded_banner = d.degraded_banner
			if (d.instant_degraded) this.rankedOpps.instant_degraded = true
			const incomingEmpty = !(d.opportunities || []).length && !(d.near_miss || []).length
			const incomingAllAvoid =
				!!(d.opportunities || []).length &&
				!(d.opportunities || []).some(
					(row) => !["AVOID", "NO_TRADE"].includes(String(row.action || "").toUpperCase()),
				)
			const hasLocal = (this.rankedOpps.rows || []).length || (this.rankedOpps.near_miss || []).length
			if (incomingEmpty && (d.degraded || d.instant_degraded) && !hasLocal && !meta.fromCache) {
				const bridged = this.playbookBridgeFromCaches()
				if (bridged.length) {
					d = {
						...d,
						opportunities: bridged,
						count: bridged.length,
						source: d.source || "brief-bridge",
						board_message:
							d.board_message || "API returned empty — showing brief/cache bridge (monitor only)",
					}
				}
			}
			const stillEmpty = !(d.opportunities || []).length && !(d.near_miss || []).length
			if ((stillEmpty || incomingAllAvoid) && !(d.near_miss || []).length && hasLocal && !meta.force) {
				this.rankedOpps.emergency = d.emergency || this.rankedOpps.emergency
				this.rankedOpps.warning =
					d.warning || this.rankedOpps.warning || "Live refresh returned empty — showing last-good board"
				this.rankedOpps.board_mode = d.board_mode || this.rankedOpps.board_mode
				this.rankedOpps.board_message = d.board_message || this.rankedOpps.board_message
				this.rankedOpps.board_explanation = d.board_explanation || this.rankedOpps.board_explanation
				if (d.rejection_clusters?.length) this.rankedOpps.rejection_clusters = d.rejection_clusters
				if (d.rejection_clusters_note) this.rankedOpps.rejection_clusters_note = d.rejection_clusters_note
				if (d.avoid_grouped?.total) this.rankedOpps.avoid_grouped = d.avoid_grouped
				if (d.filter_funnel) this.rankedOpps.filter_funnel = d.filter_funnel
				if (meta.fromSnapshot) this.rankedOpps.refreshing = !!d.refreshing
				return
			}
			this.rankedOpps.rows = d.opportunities || []
			this.rankedOpps.fetch_failed = false
			this.rankedOpps.decision_authority = d.decision_authority || null
			this.rankedOpps.bestAction = d.best_action || null
			this.rankedOpps.overlapWarning = d.overlap_warning || null
			this.rankedOpps.warning = d.warning || ""
			this.rankedOpps.avoid_grouped = d.avoid_grouped || null
			this.rankedOpps.bucket_quality = d.bucket_quality || []
			this.rankedOpps.filter_funnel = d.filter_funnel || null
			this.rankedOpps.source = d.source || "playbook"
			this.rankedOpps.board_mode = d.board_mode || ""
			this.rankedOpps.board_mode_label = d.board_mode_label || ""
			this.rankedOpps.board_message = d.board_message || ""
			this.rankedOpps.board_explanation = d.board_explanation || ""
			this.rankedOpps.snapshot_timestamp = d.snapshot_timestamp || ""
			this.rankedOpps.rejection_clusters = d.rejection_clusters || []
			this.rankedOpps.rejection_clusters_note = d.rejection_clusters_note || ""
			this.rankedOpps.unlock_deploy = d.unlock_deploy || null
			this.rankedOpps.emergency = d.emergency || null
			this.rankedOpps.near_miss =
				d.near_miss && d.near_miss.length ? d.near_miss : this.derivePlaybookNearMiss(d.opportunities || [])
			this.rankedOpps.restraint = d.restraint || null
			this.rankedOpps.surface_authority = d.surface_authority || null
			this.rankedOpps.degraded_banner = d.degraded_banner || ""
			this.rankedOpps.instant_degraded = !!d.instant_degraded
			this.rankedOpps.operator_board = d.operator_board || null
			this.rankedOpps.watch_queues = d.watch_queues || null
			this.rankedOpps.watch_intelligence_summary = d.watch_intelligence_summary || null
			this.rankedOpps.ai_vibe = d.ai_vibe || null
			this.rankedOpps.board_posture = d.board_posture || null
			this.rankedOpps.paper_automation = d.paper_automation || null
			this.rankedOpps.auto_execution = d.auto_execution || null
			this.rankedOpps.monitor_auto_actions = d.monitor_auto_actions || null
			this.rankedOpps.rank_buckets = d.rank_buckets || null
			this.rankedOpps.system_state = d.system_state || null
			this.rankedOpps.page_capability = d.page_capability || null
			if (this.rankedOpps.compact_rows === null && d.board_posture) this.rankedOpps.compact_rows = null
			this.captureInstantDegradedBanner(d)
			if (d.decision_authority) this.rankedOpps.decision_authority = d.decision_authority
			if (d.avoid_collapsed_default || this.isWaitDay() || this.playbookIsCompressedFallback()) {
				if (!this.uiExpandAll) this.rankedOpps.avoid_collapsed = true
			}
			if (meta.fromSnapshot && d.refreshing) this.rankedOpps.refreshing = true
			if (this.uiExpandAll) this.$nextTick(() => this.applyUiExpandAll())
		},
		hydrateRankedFromCache() {
			try {
				const raw = localStorage.getItem("cc_playbook_ranked_snapshot")
				if (!raw) return
				const parsed = JSON.parse(raw)
				if (!parsed || (!(parsed.opportunities || []).length && !(parsed.near_miss || []).length)) return
				this.applyRankedPayload(parsed, { fromCache: true })
			} catch (e) {
				console.warn("playbook cache hydrate failed", e)
			}
		},
		saveRankedToCache() {
			try {
				const payload = {
					opportunities: this.rankedOpps.rows,
					best_action: this.rankedOpps.bestAction,
					overlap_warning: this.rankedOpps.overlapWarning,
					warning: this.rankedOpps.warning,
					avoid_grouped: this.rankedOpps.avoid_grouped,
					bucket_quality: this.rankedOpps.bucket_quality,
					filter_funnel: this.rankedOpps.filter_funnel,
					source: this.rankedOpps.source,
					board_mode: this.rankedOpps.board_mode,
					board_mode_label: this.rankedOpps.board_mode_label,
					board_message: this.rankedOpps.board_message,
					board_explanation: this.rankedOpps.board_explanation,
					snapshot_timestamp: this.rankedOpps.snapshot_timestamp || new Date().toISOString(),
					rejection_clusters: this.rankedOpps.rejection_clusters,
					unlock_deploy: this.rankedOpps.unlock_deploy,
					near_miss: this.rankedOpps.near_miss,
					operator_board: this.rankedOpps.operator_board,
					watch_queues: this.rankedOpps.watch_queues,
					watch_intelligence_summary: this.rankedOpps.watch_intelligence_summary,
					ai_vibe: this.rankedOpps.ai_vibe,
					board_posture: this.rankedOpps.board_posture,
					paper_automation: this.rankedOpps.paper_automation,
					auto_execution: this.rankedOpps.auto_execution,
					monitor_auto_actions: this.rankedOpps.monitor_auto_actions,
					saved_at: Date.now(),
				}
				localStorage.setItem("cc_playbook_ranked_snapshot", JSON.stringify(payload))
			} catch (e) {
				console.warn("playbook cache save failed", e)
			}
		},
		_SCANNER_META_KEYS: [
			"count",
			"top_hits",
			"display_count",
			"urgent_count",
			"warning_count",
			"urgent",
			"warnings",
		],
		scannerHitCount(hits) {
			if (hits == null || hits === undefined) return 0
			if (Array.isArray(hits)) return hits.length
			if (typeof hits === "object") {
				const c = hits.count
				if (typeof c === "number" && !Number.isNaN(c)) return c
				if (typeof c === "string" && c !== "" && !Number.isNaN(Number(c))) return Number(c)
				if (Array.isArray(hits.top_hits)) return hits.top_hits.length
			}
			return 0
		},
		scannerHitList(hits) {
			if (!hits) return []
			if (Array.isArray(hits)) return hits
			if (typeof hits === "object" && Array.isArray(hits.top_hits)) return hits.top_hits
			return []
		},
		scannerHitsLabel(hits) {
			const n = Number(this.scannerHitCount(hits))
			const safe = Number.isFinite(n) ? n : 0
			const list = this.scannerHitList(hits)
			if (safe > 0) return safe + " hits"
			if (list.length > 0) return list.length + " top samples"
			return "0 hits"
		},
		scannerCategoryLabel(cat) {
			const m = {
				VALIDATION: "Confirmation",
				NO_TRADE: "Avoid Now",
				PATTERN: "Price / Pattern",
				FLOW: "Options Flow",
				RISK: "Risk Flags",
				SECTOR: "Sector",
				LEADERS: "Leaders",
				PULLBACKS: "Pullbacks",
				BREAKOUTS: "Breakouts",
			}
			return m[cat] || (cat || "").replace(/_/g, " ")
		},
		scannerCategoryEmptyWhy(cat) {
			const d = this.scannerHub.data
			const intent = d && d.decision_intent && d.decision_intent[cat]
			if (intent && intent.empty_why) return intent.empty_why
			const w = {
				FLOW: "No unusual volume or options-flow triggers in the scanned universe.",
				VALIDATION: "No confirmation / calibration patterns passed strict gates.",
				PATTERN: "No VCP, breakout, or pullback patterns met score thresholds.",
				SECTOR: "No sector rotation or leader/laggard signals fired.",
				RISK: "No risk warnings — or regime is permissive.",
				LEADERS: "No RS leaders mapped for this intent filter.",
				PULLBACKS: "No pullback setups in current tape.",
				BREAKOUTS: "No breakout pivots with confirming volume.",
				NO_TRADE: "No avoid-now composite triggers — see Rejections for pipeline blocks.",
			}
			return w[cat] || "No symbols passed this category threshold in the current run."
		},
		scannerIntentRow(intent) {
			const d = this.scannerHub.data
			return (
				(d && d.decision_intent && d.decision_intent[intent]) ||
				(d && d.category === intent
					? {
							probe_status: d.probe_status,
							count: d.count,
							regime_note: d.regime_note,
							empty_why: d.empty_why,
						}
					: null)
			)
		},
		scannerIntentProbeLabel(intent) {
			const row = this.scannerIntentRow(intent)
			const p = (row && row.probe_status) || "idle"
			if (p === "active") return "Active"
			if (p === "warming") return "Warming"
			return "Idle"
		},
		scannerHitDisplayLimit() {
			return this.scannerHub.expanded ? 25 : 10
		},
		scannerMergedDisplayLimit() {
			return this.scannerHub.expanded ? 40 : 20
		},
		scannerToggleExpanded() {
			this.scannerHub.expanded = !this.scannerHub.expanded
		},
		scannerHitsShownLabel(total) {
			const n = Number(total || 0)
			const lim = this.scannerHitDisplayLimit()
			return "顯示 " + Math.min(n, lim) + " / " + n + " · research only"
		},
		rsLeadersDisplayLimit() {
			return this.rsPanel.expanded ? 100 : 30
		},
		rsToggleExpanded() {
			this.rsPanel.expanded = !this.rsPanel.expanded
		},
		scannerIntentProbeClass(intent) {
			const row = this.scannerIntentRow(intent)
			const p = (row && row.probe_status) || "idle"
			if (p === "active") return "pg"
			if (p === "warming") return "pa"
			return "pw"
		},
		scannerPageGateLabel() {
			const tb =
				(this.today7 && this.today7.tradeability) ||
				(this.scannerHub.data &&
					this.scannerHub.data.diagnostics &&
					this.scannerHub.data.diagnostics.tradeability) ||
				""
			if (!tb) return ""
			return "Dashboard gate: " + String(tb).replace(/_/g, " ")
		},
		scannerPageGateClass() {
			const tb = String(
				(this.today7 && this.today7.tradeability) ||
					(this.scannerHub.data &&
						this.scannerHub.data.diagnostics &&
						this.scannerHub.data.diagnostics.tradeability) ||
					"",
			).toUpperCase()
			if (tb === "NO_TRADE") return "pr"
			if (tb === "WAIT" || tb === "SELECTIVE") return "pa"
			if (tb === "TRADE" || tb === "STRONG_TRADE") return "pg"
			return "pw"
		},
		scannerAllCategoryKeys() {
			const d = this.scannerHub.data
			if (!d) return []
			const core = ["PATTERN", "FLOW", "SECTOR", "RISK", "VALIDATION"]
			if (d.category_summary) return core
			return Object.keys(d.scanners || {}).filter((c) => !this._SCANNER_META_KEYS.includes(c))
		},
		scannerCategoryTopHits(catName) {
			const d = this.scannerHub.data
			const sum = d && d.category_summary && d.category_summary[catName]
			return sum && Array.isArray(sum.top_hits) ? sum.top_hits : []
		},
		scannerCategoryScannerEntries(catName) {
			const d = this.scannerHub.data
			const grp = (d && d.scanners && d.scanners[catName]) || {}
			return Object.entries(grp).filter(
				([n, p]) => !this._SCANNER_META_KEYS.includes(n) && this.scannerHitCount(p) > 0,
			)
		},
		scannerCategoryTotal(catName) {
			const d = this.scannerHub.data
			if (!d) return 0
			const sum = d.category_summary && d.category_summary[catName]
			let fromSummary = 0
			if (sum) fromSummary = Math.max(this.scannerHitCount(sum), this.scannerCategoryTopHits(catName).length)
			let fromGrouped = 0
			for (const [, p] of this.scannerCategoryScannerEntries(catName)) fromGrouped += this.scannerHitCount(p)
			return Math.max(fromSummary, fromGrouped, 0)
		},
		scannerCategoriesWithHits() {
			return this.scannerAllCategoryKeys().filter((c) => this.scannerCategoryTotal(c) > 0)
		},
		scannerCategoriesEmpty() {
			return this.scannerAllCategoryKeys().filter((c) => this.scannerCategoryTotal(c) === 0)
		},
		scannerUniverseLabel() {
			const d = this.scannerHub.data || {}
			const n = this.scannerHub.universe || d.universe_size || 0
			const lbl = d.universe_label || "universe"
			if (lbl === "watchlist") return n + " tickers (watchlist)"
			if (lbl === "broad_universe") return n + " tickers (broad universe)"
			if (lbl === "warming") return (n || 0) + " tickers (warming — no upstream signals yet)"
			if (lbl === "synthetic_default") return (n || "—") + " tickers (default pool)"
			return (n || "—") + " tickers"
		},
		scannerTotalHits() {
			const d = this.scannerHub.data
			if (!d) return "—"
			if (d.total_hits != null && !Number.isNaN(Number(d.total_hits))) return Number(d.total_hits)
			if (d.category_summary) {
				let s = 0
				for (const k of this.scannerAllCategoryKeys()) s += this.scannerCategoryTotal(k)
				return s || 0
			}
			if (d.scanners) {
				let s = 0
				for (const c of this.scannerAllCategoryKeys()) s += this.scannerCategoryTotal(c)
				return s || 0
			}
			if (d.hits) return (d.hits || []).length
			return "—"
		},
		scannerDiscoveryHitsLabel() {
			const hits = this.scannerTotalHits()
			if (hits === null || hits === undefined || hits === "—") return "—"
			const n = Number(hits)
			const safe = Number.isFinite(n) ? n : 0
			if (this.scannerDiscoveryHasFallbackRows()) return safe + " hits · fallback"
			return safe + " hits"
		},
		discoveryConfidenceLabel(row) {
			const r = row || {}
			if (
				String(r.score_display_mode || "") === "fallback_rank" ||
				this.scannerUsesBriefFallback() ||
				this.scannerDiscoveryHasFallbackRows()
			) {
				return "estimated confidence"
			}
			return "conf"
		},
		discoveryConfidenceLine(row) {
			const r = row || {}
			if (r.confidence == null || r.confidence === "") return ""
			const pct = Math.round(Number(r.confidence || 0) * 100)
			if (!Number.isFinite(pct) || pct <= 0) return ""
			return this.discoveryConfidenceLabel(r) + " " + pct + "%"
		},
		portfolioHasTicker(tk) {
			if (!tk) return false
			return (this.pf?.positions || []).some(
				(p) => (p.ticker || p.symbol || "").toUpperCase() === String(tk).toUpperCase(),
			)
		},
		scannerHubIsRenderable(d) {
			if (!d || typeof d !== "object" || d.error) return false
			if (d.decision_intent && Object.keys(d.decision_intent).length) return true
			if (d.discovery_verdict) return true
			if (d.scanners && Object.keys(d.scanners).length) return true
			if (d.hits !== undefined) return true
			return false
		},
		scannerDiscoveryEmpty() {
			if (this.scannerHub.loading) return false
			if (this.scannerHubIsRenderable(this.scannerHub.data)) return false
			return !this.scannerHub.data || !!this.scannerHub.error
		},
		hydrateScannersFromCache() {
			try {
				const raw = localStorage.getItem("cc_scanner_hub_snapshot")
				if (!raw) return
				const d = JSON.parse(raw)
				if (!this.scannerHubIsRenderable(d)) return
				if (this.scannerHub.data && !this.scannerHub.error) return
				this.scannerHub.data = d
				this.scannerHub.universe = d.universe_size || d.diagnostics?.symbols_scanned || 0
				if (d.diagnostics && !d.diagnostics.source) d.diagnostics.source = "local-cache"
				if (!this.scannerHub.error) this.scannerHub.error = ""
			} catch (e) {
				console.warn("scanner hub cache hydrate failed", e)
			}
		},
		saveScannersToCache(d) {
			try {
				if (!this.scannerHubIsRenderable(d)) return
				localStorage.setItem("cc_scanner_hub_snapshot", JSON.stringify({ ...d, saved_at: Date.now() }))
			} catch (e) {
				console.warn("scanner hub cache save failed", e)
			}
		},
		async fetchScanners(cat) {
			const tab = "scanners"
			this.scannerHub.loading = true
			this.scannerHub.category = cat || null
			this.scannerHub.error = ""
			this.surfaceFetchHints[tab] = { ...(this.surfaceFetchHints[tab] || {}), loading: true, error: "" }
			const _t0 = performance.now()
			try {
				let u = "/api/v7/playbook/scanners"
				if (cat) u += "?category=" + encodeURIComponent(cat)
				const r = await this.ccFetch(u, { retries: 3, backoff: 600 })
				if (!r || !r.ok) {
					if (r && r.status === 503) {
						const sr = await fetch(u)
						if (sr.ok) {
							const d = await sr.json()
							if (this.scannerHubIsRenderable(d)) {
								this.scannerHub.data = d
								this.scannerHub.error = ""
								this.saveScannersToCache(d)
								this.surfaceFetchHints[tab] = {
									loading: false,
									error: "",
									fallback: this.scannerUsesBriefFallback(),
									research_only: true,
								}
								return
							}
						}
					}
					throw new Error("HTTP " + (r ? r.status : "fail"))
				}
				const d = await r.json()
				if (!this.scannerHubIsRenderable(d)) throw new Error(d.error || "incomplete scanner payload")
				this.scannerHub.data = d
				if (d.diagnostics && !d.diagnostics.source) d.diagnostics.source = "playbook"
				let uni = d.universe_size || d.diagnostics?.symbols_scanned || d.universe || 0
				if (!uni && d.hits) uni = (d.hits || []).length
				this.scannerHub.universe = uni
				if (!cat) this.saveScannersToCache(d)
				this.surfaceFetchHints[tab] = {
					loading: false,
					error: "",
					fallback: this.scannerUsesBriefFallback(),
					research_only: true,
				}
			} catch (e) {
				console.warn("scanners fetch failed", e)
				if (!this.scannerHub.data) this.hydrateScannersFromCache()
				if (!this.scannerHub.data) this.scannerHub.data = null
				this.scannerHub.error = e.message || "fetch failed"
				const hasFallback = this.scannerDiscoveryHasFallbackRows()
				this.surfaceFetchHints[tab] = {
					loading: false,
					error: hasFallback ? "" : this.surfaceFetchStateMessage("failed_fetch"),
					failed_fetch: !hasFallback,
					failed_fetch_with_fallback: hasFallback,
					fallback: hasFallback || this.scannerUsesBriefFallback(),
					research_only: true,
				}
			} finally {
				this.scannerHub.duration_ms = Math.round(performance.now() - _t0)
				this.scannerHub.last_run = new Date().toISOString()
				this.scannerHub.loading = false
			}
		},

		tabAuthorityAlias(t) {
			return { signals: "playbook", scanners: "discovery", today: "today" }[t] || t
		},
		guideAuthorityStrip() {
			return this._uiText("GUIDE MODE · Reference only · Decision surfaces suspended")
		},
		guideStatusNote() {
			const mode = (this.cc_status && this.cc_status.mode) || "PAPER"
			return this._uiText("Mode · " + mode + " · Runtime not evaluated here")
		},
		tabAuthorityChip() {
			if (this.tab === "guide") {
				return {
					badge: "GUIDE MODE",
					short: "Reference only · Decision surfaces suspended",
					authority: "suspended",
					authority_label: "Guide mode — decision surfaces suspended; reference only",
				}
			}
			const strip = this.currentSurfaceAuthorityStrip()
			if (!strip || !(strip.surfaces || []).length) {
				return this.normalizedAuthorityChipForTab(this.tab, {
					badge: "—",
					short: "",
					authority: "research_only",
					authority_label: "",
				})
			}
			const key = this.tabAuthorityAlias(this.tab)
			const hit = strip.surfaces.find((s) => s.tab === key)
			if (hit) return this.normalizedAuthorityChipForTab(this.tab, hit)
			return this.normalizedAuthorityChipForTab(this.tab, strip.surfaces[0])
		},

		flowPanelCount() {
			const d = this.flowPanel && this.flowPanel.decision
			if (d && d.count_live) return String(d.count_live)
			const radar = (this.flowPanel && this.flowPanel.radar) || {}
			return String((radar.candidates || []).length || 0)
		},

		flowNotCalibrated() {
			const c = this.flowPanel?.decision?.calibration
			return !c || !c.available
		},
		flowShowConfirmationWarning() {
			const d = this.flowPanel?.decision
			if (!d) return false
			return !!(d.freshness?.synthetic || !(d.count_live || 0) || this.flowNotCalibrated())
		},
		flowResearchOnly() {
			return this.flowShowConfirmationWarning()
		},
		flowStatusAuthority() {
			return "Confirm only · Flow 唔提供 deploy 權限"
		},
		flowStatusSource() {
			const d = this.flowPanel?.decision
			if (d?.freshness?.synthetic || !(d?.count_live || 0)) return "Mock / synthetic flow samples"
			return (d?.freshness?.provider || "Live provider") + " flow"
		},
		flowStatusActionability() {
			return "Not standalone entry trigger"
		},
		flowOverlayDegraded() {
			return this.flowShowConfirmationWarning()
		},
		flowOverlayDegradedShort() {
			const d = this.flowPanel?.decision
			if (d?.freshness?.synthetic) return "Fallback only"
			if (!(d?.count_live || 0)) return "No live overlay"
			if (this.flowNotCalibrated()) return "Unavailable"
			return "Unavailable"
		},
		flowRegimeSupportLine() {
			const d = this.flowPanel?.decision
			if (d?.freshness?.synthetic) return "No live flow overlay"
			if (!(d?.count_live || 0)) return "Flow overlay unavailable"
			return "Flow overlay unavailable"
		},
		flowKpiLabel() {
			return "flow"
		},
		flowKpiSubLabel() {
			if (this.flowOverlayDegraded()) return "overlay"
			const n = Number(this.flowPanelCount()) || 0
			return n === 1 ? "signal" : "signals"
		},
		flowKpiValue() {
			if (this.flowOverlayDegraded()) return "—"
			return this.flowPanelCount()
		},
		aiCommentaryCtaLabel() {
			if (this.today7.ai_loading) return "Loading…"
			return this.today7.ai_narrative ? "Regenerate" : "Generate"
		},
		aiCommentaryEmptyLine() {
			if (this.today7.ai_provider === "stub")
				return "Rule-based summary only — configure an LLM for richer narrative; board authority unchanged."
			return "Generate a narrative briefing when the API is ready. Commentary is explanatory only — it does not change deploy permission."
		},
		flowKpiTitle() {
			if (this.flowOverlayDegraded()) return this.flowRegimeSupportLine() + " — confirmation overlay only"
			return "Live flow hits — confirmation overlay only"
		},
		flowOverlaySummaryLine() {
			if (!this.flowOverlayDegraded()) return ""
			const d = this.flowPanel?.decision
			if (d?.freshness?.synthetic || !(d?.count_live || 0)) {
				return "No live flow overlay — mock samples only. Use Playbook and Dossier for structure; flow cannot confirm entries."
			}
			return ""
		},
		flowStatusSummary() {
			const d = this.flowPanel?.decision
			if (this.flowOverlayDegraded()) {
				if (d?.freshness?.synthetic || !(d?.count_live || 0)) return ""
				return "Flow overlay unavailable — grades are heuristic until calibration completes."
			}
			return "Confirmation overlay only — use after Playbook and Dossier agree on a name. May add timing colour; cannot replace regime or execution validation."
		},
		flowRegimeContextHint() {
			if (this.flowNotCalibrated())
				return "Calibration pending — treat grades as heuristic until forward outcomes are logged."
			return "Regime context only — deploy authority stays with Playbook and Dossier."
		},
		flowShowMockPreviewSubtitle() {
			const d = this.flowPanel?.decision
			return !!(
				d &&
				(d.freshness?.synthetic || d.mock_only) &&
				(d.mock_flow || []).length &&
				!(d.count_live || 0)
			)
		},
		flowPmActionLabel(action) {
			const a = String(action || "").toUpperCase()
			if (a === "WATCH_FOR_STOCK_CONFIRM") return "待價格確認 · confirm"
			if (a === "NOT_ACTIONABLE") return "研究模式 · research"
			if (a === "BUYABLE_NOW" || a === "ACTIONABLE" || a === "PROMOTION_CANDIDATE")
				return "研究候選 · research candidate"
			if (a === "PILOT" || a === "PILOT_ENTRY") return "監察候選 · monitor"
			return action ? String(action).replace(/_/g, " ") : "—"
		},
		rsVisibleBuyabilityLabel(label) {
			const a = String(label || "").toUpperCase()
			if (["BUYABLE_NOW", "ACTIONABLE", "BUY", "TRADE", "PROMOTION_CANDIDATE"].includes(a))
				return "不可執行 · not executable"
			if (a.includes("PILOT")) return "送去 Playbook · compare"
			if (a.includes("WATCH")) return "只可監察 · monitor"
			return label ? String(label).replace(/_/g, " ") : "研究候選 · research"
		},
		flowWatchConfirmReason(c) {
			const r = String(c?.reason || c?.explanation || "").trim()
			if (r) return r
			return "Await price confirmation elsewhere"
		},
		flowMainComment() {
			const c = this.flowPanel?.decision?.calibration
			if (c?.available) return c.detail || "Calibration sample available — still confirmation-only vs Playbook."
			return "No calibrated forward-outcome history yet — grades are heuristic until the model logs enough closed outcomes."
		},
		flowLiveEmptyState() {
			if (this.flowShowMockPreviewSubtitle()) return "目前無 live research candidates。"
			return "目前無 live flow candidates。"
		},
		rsResearchActionLabel(row) {
			const a = String(row?.action_label || row?.buyability || "").toUpperCase()
			if (["BUYABLE_NOW", "ACTIONABLE", "BUY", "TRADE", "PROMOTION_CANDIDATE"].includes(a))
				return "研究候選 · research candidate"
			if (a.includes("PILOT")) return "監察候選 · monitor"
			if (a.includes("WATCH")) return "監察候選 · monitor"
			if (a) return a.replace(/_/g, " ")
			return "研究候選 · research"
		},
		flowCalibrationHeadline() {
			const c = this.flowPanel?.decision?.calibration
			if (c?.available) return c.label || "Calibration active"
			return c?.label || "Calibration status: insufficient evidence"
		},
		flowCalibrationDetail() {
			const c = this.flowPanel?.decision?.calibration
			if (c?.available) return c.label || ""
			return (
				c?.detail ||
				"The flow model has not yet logged enough closed trade outcomes to estimate hit-rate, follow-through quality, or sizing usefulness. Until this sample exists, all flow grades should be treated as heuristic research labels only."
			)
		},
		flowCardDisclaimerShort(c) {
			const tk = String(c?.underlying || "").toUpperCase()
			if (["QCOM", "NET", "AMAT"].includes(tk))
				return "Mock flow — confirm structure in Playbook / Dossier first."
			if (tk === "SOUN") return "Synthetic noise — watchlist colour only."
			if (tk === "AAPL") return "Mock flow — stock not confirmed by decision stack."
			return "Mock flow only — not deployable."
		},
		flowCardDisclaimerDetail(c) {
			const tk = String(c?.underlying || "").toUpperCase()
			if (tk === "QCOM")
				return "QCOM 可能見到偏高 options 活動，但未經 live provider 同 stock follow-through 確認前，只屬 research-only。先用 Playbook / Dossier 確認 sector leadership 同 structure。"
			if (tk === "NET")
				return "NET mock flow can look active on vol/OI, yet remains research preview only. Confirm trend and risk in Playbook / Dossier; do not size from synthetic flow alone."
			if (tk === "AMAT")
				return "AMAT mock prints are illustrative equipment-sector colour, not deployable edge. Wait for live flow and stock confirmation elsewhere before any sizing discussion."
			if (tk === "SOUN")
				return "SOUN 嘅 synthetic flow 雖然吸睛，但目前只屬 research-only。呢種 options profile 代表注意力，唔代表 deployable edge；未有 live flow 同 stock 結構確認前，只可當 watchlist colour。"
			if (tk === "AAPL")
				return "AAPL flow is interesting but not investable in its current form. The flow is mock / synthetic, and the stock itself is not fully confirmed by the broader decision stack. Use this as supporting context only, not as a reason to initiate or size a trade."
			return ""
		},

		async fetchFlow() {
			const tab = "flow"
			this.flowPanel.loading = true
			this.flowPanel.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/flow-decision?limit=50", { tab, retries: 3, backoff: 800 })
				if (!res.ok) {
					this.flowPanel.error = this.surfaceFetchErrorLine(res.error, tab)
					return
				}
				this.flowPanel.decision = res.data
				this.flowPanel.radar = { candidates: res.data.live_flow || [], trust: res.data.freshness || {} }
			} catch (e) {
				this.flowPanel.error = this.surfaceFetchErrorLine(e.message || "flow fetch failed", tab)
			} finally {
				this.flowPanel.loading = false
			}
		},

		researchAuthorityLabel() {
			return "研究 / 監察 only · Research / Monitoring only · 不提供部署權限"
		},
		agentModeLabel() {
			const m = String(this.vibeAgent?.status?.mode || "—")
			if (m === "running") return "Agent monitoring active"
			if (m === "degraded") return "Agent monitoring degraded"
			if (m === "paused") return "Agent monitoring paused"
			if (m === "offline") return "Agent monitoring offline"
			return m
		},
		agentAuthorityNoticeLines() {
			const n = this.vibeAgent?.status?.authority_notice || this.vibeAgent?.safety?.authority_notice || []
			return Array.isArray(n) ? n : []
		},
		agentActiveRules() {
			return (this.vibeAgent?.rules || []).filter((r) => String(r.status || "active") === "active")
		},
		agentTriggeredRules() {
			const ids = new Set((this.vibeAgent?.alerts || []).map((a) => a.ruleId))
			return (this.vibeAgent?.rules || []).filter((r) => ids.has(r.id))
		},
		agentMutedRules() {
			return (this.vibeAgent?.rules || []).filter((r) => String(r.status) === "muted")
		},
		agentExpiredRules() {
			const now = Date.now()
			return (this.vibeAgent?.rules || []).filter((r) => {
				const exp = r.expiry
				if (!exp) return false
				const t = Date.parse(String(exp).replace("Z", ""))
				return !isNaN(t) && t < now
			})
		},

		async fetchVibeAgent() {
			const tab = "agent"
			this.vibeAgent.loading = true
			this.vibeAgent.error = ""
			try {
				const paused = !!this.vibeAgent.paused
				const [st, bf, ru, al, jo, ev, ct] = await Promise.all([
					this.ccFetchJson("/api/v7/vibe-agent/status?paused=" + (paused ? "true" : "false"), {
						tab,
						retries: 2,
						backoff: 500,
					}),
					this.ccFetchJson("/api/v7/vibe-agent/overnight-brief", { tab, retries: 2, backoff: 500 }),
					this.ccFetchJson("/api/v7/vibe-agent/rules", { tab, retries: 2, backoff: 500 }),
					this.ccFetchJson("/api/v7/vibe-agent/alerts?limit=50", { tab, retries: 2, backoff: 500 }),
					this.ccFetchJson("/api/v7/vibe-agent/journal?limit=80", { tab, retries: 2, backoff: 500 }),
					this.ccFetchJson("/api/v7/vibe-agent/evaluate", { tab, retries: 2, backoff: 500 }),
					this.ccFetchJson("/api/v7/vibe-agent/contract", { tab, retries: 1, backoff: 300 }),
				])
				if (st.ok) this.vibeAgent.status = st.data
				if (bf.ok) {
					this.vibeAgent.brief = bf.data?.brief || null
					this.vibeAgent.page_capability = bf.data?.page_capability || null
				}
				if (ru.ok) this.vibeAgent.rules = ru.data?.rules || []
				if (al.ok) this.vibeAgent.alerts = al.data?.alerts || []
				if (jo.ok) this.vibeAgent.journal = jo.data?.journal || []
				if (ct.ok) this.vibeAgent.safety = ct.data
				if (ev.ok && Array.isArray(ev.data?.triggeredAlerts)) {
					const merged = [...(ev.data.triggeredAlerts || []), ...(ev.data.provisionalAlerts || [])]
					if (merged.length) {
						const seen = new Set(
							(this.vibeAgent.alerts || []).map((a) => a.id || a.ruleId + "-" + a.triggeredAt),
						)
						merged.forEach((a) => {
							const k = a.id || a.ruleId + "-" + a.triggeredAt
							if (!seen.has(k)) {
								this.vibeAgent.alerts.unshift(a)
								seen.add(k)
							}
						})
					}
				}
				if (!st.ok && !bf.ok)
					this.vibeAgent.error = this.surfaceFetchErrorLine(st.error || bf.error || "agent fetch failed", tab)
			} catch (e) {
				this.vibeAgent.error = this.surfaceFetchErrorLine(e.message || "agent fetch failed", tab)
			} finally {
				this.vibeAgent.loading = false
			}
		},

		async parseVibeIntentPreview() {
			const text = String(this.vibeAgent.intentText || "").trim()
			if (!text) return
			this.vibeAgent.loading = true
			this.vibeAgent.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/vibe-agent/intent/parse", {
					tab: "agent",
					retries: 1,
					backoff: 300,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ text }),
					},
				})
				if (!res.ok) {
					this.vibeAgent.error = res.error || "parse failed"
					return
				}
				this.vibeAgent.intentPlan = res.data?.plan || null
			} catch (e) {
				this.vibeAgent.error = e.message || "parse failed"
			} finally {
				this.vibeAgent.loading = false
			}
		},

		async saveVibeIntent() {
			const text = String(this.vibeAgent.intentText || "").trim()
			if (!text) return
			this.vibeAgent.loading = true
			this.vibeAgent.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/vibe-agent/intent", {
					tab: "agent",
					retries: 1,
					backoff: 300,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ text }),
					},
				})
				if (!res.ok) {
					this.vibeAgent.error = res.error || "save failed"
					return
				}
				this.vibeAgent.intentPlan = res.data?.plan || null
				this.vibeAgent.intentText = ""
				await this.fetchVibeAgent()
			} catch (e) {
				this.vibeAgent.error = e.message || "save failed"
			} finally {
				this.vibeAgent.loading = false
			}
		},

		async saveAgentWatchRule() {
			const d = this.vibeAgent.ruleDraft || {}
			const body = {
				name: String(d.name || "").trim() || "Custom watch rule",
				asset:
					String(d.asset || "")
						.trim()
						.toUpperCase() || "WATCHLIST",
				ruleType: String(d.ruleType || "price_zone_touch"),
				condition: String(d.condition || "").trim() || "User-defined monitor condition",
				dataRequired: ["market_data", "playbook_rank"],
				freshnessRequired: "FRESH",
				confirmationRequired: true,
				authorityEffect: "none",
				action: "alert_only",
				status: "active",
			}
			const days = parseInt(d.expiryDays, 10)
			if (!isNaN(days) && days > 0) {
				const exp = new Date(Date.now() + days * 86400000).toISOString()
				body.expiry = exp
			}
			this.vibeAgent.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/vibe-agent/rules", {
					tab: "agent",
					retries: 1,
					backoff: 300,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify(body),
					},
				})
				if (!res.ok) {
					this.vibeAgent.error = res.error || "rule save failed"
					return
				}
				this.vibeAgent.ruleDraft = {
					name: "",
					asset: "",
					ruleType: "price_zone_touch",
					condition: "",
					expiryDays: 14,
				}
				await this.fetchVibeAgent()
			} catch (e) {
				this.vibeAgent.error = e.message || "rule save failed"
			} finally {
				this.vibeAgent.loading = false
			}
		},

		async muteAgentRule(ruleId) {
			if (!ruleId) return
			try {
				await this.ccFetchJson("/api/v7/vibe-agent/rules/" + encodeURIComponent(ruleId), {
					tab: "agent",
					retries: 1,
					init: {
						method: "PATCH",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ status: "muted" }),
					},
				})
				await this.fetchVibeAgent()
			} catch (e) {}
		},

		async checkAgentGuardrail(actionType, context) {
			try {
				const res = await this.ccFetchJson("/api/v7/vibe-agent/guardrail", {
					tab: "agent",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ action_type: actionType, context: context || {} }),
					},
				})
				if (res.ok) this.vibeAgent.guardrail = res.data
			} catch (e) {}
		},

		async toggleAgentPaused() {
			this.vibeAgent.paused = !this.vibeAgent.paused
			await this.fetchVibeAgent()
		},

		async fetchStrategyLabShell() {
			const tab = "strategy-lab"
			this.strategyLab.loading = true
			this.strategyLab.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/research/contract?surface=strategy-lab", {
					tab,
					retries: 1,
				})
				if (res.ok) this.strategyLab.safety = res.data
			} catch (e) {
				this.strategyLab.error = e.message || "load failed"
			} finally {
				this.strategyLab.loading = false
			}
		},

		async parseStrategyDraft() {
			const prompt = String(this.strategyLab.prompt || "").trim()
			if (!prompt) return
			this.strategyLab.loading = true
			this.strategyLab.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/research/strategy/parse", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ prompt }),
					},
				})
				if (!res.ok) {
					this.strategyLab.error = res.error || "parse failed"
					return
				}
				this.strategyLab.draft = res.data?.draft || null
			} catch (e) {
				this.strategyLab.error = e.message || "parse failed"
			} finally {
				this.strategyLab.loading = false
			}
		},

		async saveStrategyDraft() {
			const prompt = String(this.strategyLab.prompt || "").trim()
			if (!prompt) return
			this.strategyLab.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/research/strategy", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ prompt }),
					},
				})
				if (!res.ok) {
					this.strategyLab.error = res.error
					return
				}
				this.strategyLab.draft = res.data?.draft || null
			} catch (e) {
				this.strategyLab.error = e.message
			} finally {
				this.strategyLab.loading = false
			}
		},

		async runStrategyValidation() {
			if (!this.strategyLab.draft?.id) {
				this.strategyLab.error = "Save draft first"
				return
			}
			this.strategyLab.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/research/validate", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ draft_id: this.strategyLab.draft.id }),
					},
				})
				if (!res.ok) {
					this.strategyLab.error = res.error
					return
				}
				this.strategyLab.validation = res.data?.validation || null
				this.strategyLab.page_capability = res.data?.page_capability || null
			} catch (e) {
				this.strategyLab.error = e.message
			} finally {
				this.strategyLab.loading = false
			}
		},

		async runResearchPipeline() {
			const prompt = String(this.strategyLab.prompt || "").trim()
			if (!prompt) return
			this.strategyLab.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/research/pipeline", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ prompt }),
					},
				})
				if (!res.ok) {
					this.strategyLab.error = res.error
					return
				}
				this.strategyLab.pipeline = res.data
				this.strategyLab.draft = res.data?.strategyDraft || this.strategyLab.draft
				this.strategyLab.validation = res.data?.validation || null
				this.strategyLab.committee = res.data?.committee || null
				this.strategyLab.page_capability = res.data?.page_capability || null
			} catch (e) {
				this.strategyLab.error = e.message
			} finally {
				this.strategyLab.loading = false
			}
		},

		async runCommitteeReview() {
			if (!this.strategyLab.draft) return
			this.strategyLab.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/research/committee/review", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ subject: this.strategyLab.draft }),
					},
				})
				if (res.ok) this.strategyLab.committee = res.data?.review || null
			} catch (e) {
			} finally {
				this.strategyLab.loading = false
			}
		},

		async exportStrategyPine() {
			if (!this.strategyLab.draft) return
			try {
				const res = await this.ccFetchJson("/api/v7/research/export/pine", {
					tab: "strategy-lab",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ draft: this.strategyLab.draft }),
					},
				})
				if (res.ok) this.strategyLab.pineExport = res.data?.pine || ""
			} catch (e) {}
		},

		async fetchShadowShell() {
			this.shadowAccount.loading = true
			try {
				const res = await this.ccFetchJson("/api/v7/research/shadow?limit=5", { tab: "shadow", retries: 1 })
				if (res.ok && res.data?.runs?.length) this.shadowAccount.result = res.data.runs[0]
			} catch (e) {
			} finally {
				this.shadowAccount.loading = false
			}
		},

		async analyzeShadowAccount() {
			let trades = []
			try {
				trades = JSON.parse(this.shadowAccount.tradesJson || "[]")
			} catch (e) {
				this.shadowAccount.error = "Invalid JSON"
				return
			}
			if (!Array.isArray(trades) || !trades.length) {
				this.shadowAccount.error = "trades array required"
				return
			}
			this.shadowAccount.loading = true
			this.shadowAccount.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/research/shadow/analyze", {
					tab: "shadow",
					retries: 1,
					init: {
						method: "POST",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify({ trades, source: "manual_journal" }),
					},
				})
				if (!res.ok) {
					this.shadowAccount.error = res.error
					return
				}
				this.shadowAccount.result = res.data?.shadow || null
				this.shadowAccount.page_capability = res.data?.page_capability || null
			} catch (e) {
				this.shadowAccount.error = e.message
			} finally {
				this.shadowAccount.loading = false
			}
		},

		async fetchReportsLib() {
			this.reportsLib.loading = true
			this.reportsLib.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/research/reports?limit=40", { tab: "reports", retries: 2 })
				if (!res.ok) {
					this.reportsLib.error = res.error
					return
				}
				this.reportsLib.reports = res.data?.reports || []
				this.reportsLib.page_capability = res.data?.page_capability || null
			} catch (e) {
				this.reportsLib.error = e.message
			} finally {
				this.reportsLib.loading = false
			}
		},

		async exportReport(reportId, fmt) {
			if (!reportId) return
			try {
				const r = await this.ccFetch(
					"/api/v7/research/reports/" + encodeURIComponent(reportId) + "/export?fmt=" + (fmt || "markdown"),
					{ tab: "reports", retries: 1 },
				)
				if (r && r.ok) this.reportsLib.exportText = await r.text()
			} catch (e) {}
		},

		async fetchOpsConsole() {
			this.opsConsole.loading = true
			this.opsConsole.error = ""
			try {
				const res = await this.ccFetchJson("/api/v7/ops-console", { tab: "ops", retries: 3, backoff: 600 })
				if (!res.ok) {
					this.opsConsole.error = this.surfaceFetchErrorLine(res.error, "ops")
					return
				}
				const d = res.data
				this.opsConsole.data = d
				const fromEvidence = {}
				;(d.component_evidence || []).forEach((c) => {
					if (c && c.name) fromEvidence[c.name] = !!c.ok
				})
				const mergedComponents = Object.keys(fromEvidence).length ? fromEvidence : d.components || {}
				if (d.engine) {
					this.ops = {
						...this.ops,
						...d.engine,
						components: Object.keys(mergedComponents).length ? mergedComponents : this.ops.components || {},
					}
				}
				this.opsDetail = {
					uptime: d.uptime,
					latency: d.latency,
					startup_time: d.startup_time,
					engine: d.engine,
					components: mergedComponents,
				}
			} catch (e) {
				this.opsConsole.error = this.surfaceFetchErrorLine(e.message || "ops console failed", "ops")
			} finally {
				this.opsConsole.loading = false
			}
		},

		async fetchFunds() {
			this.fundMonitor.loading = true
			this.fundMonitor.error = ""
			try {
				const res = await this.ccFetchJson(
					"/api/fund-lab/live?benchmark=" + (this.fundMonitor.benchmark || "SPY"),
					{ tab: "funds", retries: 3, backoff: 600 },
				)
				if (!res.ok) {
					this.fundMonitor.error = this.surfaceFetchErrorLine(res.error, "funds")
					this.fundMonitor.data = null
					return
				}
				this.fundMonitor.data = res.data
				if (res.data && (res.data.degraded || res.data.research_only)) {
					this.surfaceFetchHints.funds = { loading: false, stale: true, fallback: true, error: "" }
				}
				this.fundMonitor.console = this.fundMonitor.data?.console || this.fundMonitor.data
				this.fundMonitor.lastRefresh = new Date().toISOString()
				if (this.fundMonitor.data?.cards) {
					this.pmStrip.funds = this.fundMonitor.data.cards.slice(0, 3)
					this.pmStrip.lastFetch = Date.now()
					if (this.fundMonitor.data.cards.length) {
						const cards = this.fundMonitor.data.cards
						const ctrl =
							cards.find((c) => c.controls_capital) ||
							cards.find((c) => c.gate_status === "ACTIVE") ||
							cards[0]
						const strip = (c) => ({
							id: c.id,
							display_name: c.display_name,
							gate_status: c.gate_status,
							stance: c.stance,
							mode: c.mode,
							controls_capital: !!c.controls_capital,
							regime_fit: c.regime_fit,
							excess_return_pct: c.excess_return_pct,
							max_drawdown_pct: c.max_drawdown_pct,
							equity_curve_20: c.equity_curve_20 || [],
							evidence_badge: c.evidence_badge || "model_backtest",
						})
						this.today7.sleeve_summary = {
							stance:
								"Active: " +
								(ctrl?.display_name || "") +
								" · " +
								(ctrl?.stance || "NEUTRAL") +
								" · " +
								(ctrl?.gate_status || "—"),
							cards: cards.slice(0, 3).map(strip),
							active_today: ctrl ? strip(ctrl) : null,
							fund_manager: ctrl
								? {
										active_sleeve_id: ctrl.id,
										active_sleeve_name: ctrl.display_name,
										stance: ctrl.stance,
										mode: ctrl.mode,
										controls_capital: !!ctrl.controls_capital,
										regime_fit: ctrl.regime_fit,
									}
								: null,
						}
					}
				}
			} catch (e) {
				this.fundMonitor.error = this.surfaceFetchErrorLine(e.message || "fund fetch failed", "funds")
				this.fundMonitor.data = null
			} finally {
				this.fundMonitor.loading = false
			}
		},

		async fetchRs() {
			this.rsPanel.loading = true
			this.rsPanel.error = ""
			try {
				let u = "/api/v7/rs-decision?limit=80"
				if (this.rsPanel.sectorFilter) u += "&sector=" + encodeURIComponent(this.rsPanel.sectorFilter)
				const r = await this.ccFetch(u, { retries: 2, backoff: 1200 })
				if (!r || !r.ok) throw new Error("HTTP " + (r ? r.status : "timeout"))
				this.rsPanel.data = await r.json()
			} catch (e) {
				this.rsPanel.error = e.message || "RS fetch failed"
				this.rsPanel.data = null
			} finally {
				this.rsPanel.loading = false
			}
		},

		rejectionsRegimeLabel() {
			const r = this.rejectionsPanel.regime || this.today7?.regime || {}
			const trend = (r.trend || r.trend_regime || "SIDEWAYS").toString().toUpperCase()
			const tb = (r.tradeability || this.today7?.tradeability || "WAIT").toString().toUpperCase()
			return trend + " · " + tb
		},
		rejectionsPageIntro() {
			const r = this.rejectionsPanel.regime || this.today7?.regime || {}
			const trend = (r.trend || r.trend_regime || "SIDEWAYS").toString().toUpperCase()
			const tb = (r.tradeability || this.today7?.tradeability || "WAIT").toString().toUpperCase()
			return (
				"呢頁只答點解被擋住。當前 " +
				trend +
				" · " +
				tb +
				" 盤面下，未同時通過 leadership、timing、contradiction 同 board-quality gates 嘅名稱，預設都唔應得 capital。先睇 blocker clusters，再決定要監察咩改善。"
			)
		},
		rejectionsClusterCards() {
			const rows = this.rejectionsPanel.data?.no_trade_signals || []
			const groups = {}
			for (const sig of rows) {
				const key = String(sig.blocker_category || "blocked")
				if (!groups[key]) {
					groups[key] = {
						key,
						badge: this.rejectionsBlockerBadge(sig),
						headline: sig.primary_blocker || this.rejectionsFallbackPrimary(sig),
						count: 0,
						names: [],
						trigger: sig.upgrade_trigger || "等待主要 blocker 緩解",
					}
				}
				groups[key].count += 1
				if (sig.ticker && groups[key].names.length < 3) groups[key].names.push(sig.ticker)
				if (!groups[key].trigger && sig.upgrade_trigger) groups[key].trigger = sig.upgrade_trigger
			}
			return Object.values(groups)
				.sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
				.slice(0, 3)
				.map((g) => ({ ...g, names: (g.names || []).join(" / ") || "—" }))
		},
		rejectionsClusterGroups() {
			const rows = this.rejectionsPanel.data?.no_trade_signals || []
			const groups = {}
			for (const sig of rows) {
				const key = String(sig.blocker_category || "blocked")
				if (!groups[key]) {
					groups[key] = {
						key,
						badge: this.rejectionsBlockerBadge(sig),
						headline: sig.primary_blocker || this.rejectionsFallbackPrimary(sig),
						count: 0,
						names: [],
						trigger: sig.upgrade_trigger || "等待主要 blocker 緩解",
						rows: [],
					}
				}
				groups[key].count += 1
				if (sig.ticker && groups[key].names.length < 3) groups[key].names.push(sig.ticker)
				if (groups[key].rows.length < 12) groups[key].rows.push(sig)
				if (!groups[key].trigger && sig.upgrade_trigger) groups[key].trigger = sig.upgrade_trigger
			}
			return Object.values(groups)
				.sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
				.slice(0, 3)
				.map((g) => ({ ...g, names: (g.names || []).join(" / ") || "—" }))
		},
		rejectionsBlockerBadge(sig) {
			const m = {
				laggard: "Laggard",
				contradiction: "Contradiction",
				board_quality: "Board / regime",
				timing: "Timing",
				context: "Context",
			}
			return m[sig.blocker_category] || "Blocked"
		},
		rejectionsFallbackPrimary(sig) {
			const raw = String(sig.reason || "")
			if (raw.indexOf("Weak setup — monitor only") >= 0) {
				if ((sig.conflict || "").toLowerCase().indexOf("laggard") >= 0)
					return "Blocked — not leading enough for this regime (inferred from conflict)."
				if ((sig.conflict || "").indexOf("contradict") >= 0)
					return "Blocked — too many contradictions for deployment (inferred from conflict)."
				return "Blocked — below current capital standard (legacy mapper rationale)."
			}
			return raw || "Blocked — see dossier for gate detail."
		},
		rejectionsCardMeta(sig) {
			const parts = [sig.sector || "—", sig.stage || "—", sig.leader_status || ""]
			if (sig.timing_conf != null) parts.push("timing " + Math.round(sig.timing_conf * 100) + "%")
			if (sig.conflict) parts.push(sig.conflict)
			return parts.filter(Boolean).join(" · ")
		},
		rejectionsInferDegradedState() {
			const hints = this.surfaceFetchHints.notrade || {}
			return this.opsInferDegradedState({
				loading: !!(this.rejectionsPanel.loading || hints.loading) && !hints.failed_fetch,
				error: hints.error || "",
				fallback: !!hints.stale || !!this.rejectionsPanel.data?.degraded,
			})
		},
		rejectionsFetchFailed() {
			const hints = this.surfaceFetchHints.notrade || {}
			return !!hints.failed_fetch
		},
		rejectionsFetchBanner() {
			const hints = this.surfaceFetchHints.notrade || {}
			if (hints.loading || !hints.failed_fetch) return ""
			const state = this.rejectionsInferDegradedState()
			if (state === "ok" || state === "loading") return ""
			const raw = hints.error || ""
			if (state === "retry_recommended" || state === "unavailable" || state === "fallback") {
				return this.opsDegradedLine(state)
			}
			return this.surfaceFetchErrorLine(raw || "", "notrade")
		},
		rejectionsTrustStripStatus() {
			const hints = this.surfaceFetchHints.notrade || {}
			if (this.rejectionsPanel.data) return "Blocked: " + (this.rejectionsPanel.data.count || 0)
			if (hints.failed_fetch || hints.error) {
				return this.opsDegradedCopy(this.rejectionsInferDegradedState()).title
			}
			if (this.rejectionsPanel.loading || hints.loading) return this.opsDegradedCopy("loading").title + "…"
			return this.opsDegradedCopy("unavailable").title
		},
		rejectionsEmptyMessage() {
			if (this.rejectionsFetchFailed()) {
				return "Fresh rejection data unavailable; no blocked signals shown. No blocked signals available from the last readable batch."
			}
			return this.rejectionsEmptyState().detail
		},
		async fetchRejections() {
			const tab = "notrade"
			this.rejectionsPanel.loading = true
			this.rejectionsPanel.error = ""
			this.surfaceFetchHints[tab] = {
				...(this.surfaceFetchHints[tab] || {}),
				loading: true,
				error: "",
				failed_fetch: false,
			}
			try {
				const ntR = await this.ccFetchJson("/api/v7/playbook/no-trade", { retries: 3, backoff: 600, tab })
				if (!ntR.ok) {
					const msg = ntR.error || ""
					const degraded = this.opsInferDegradedState({ error: msg })
					this.rejectionsPanel.data = null
					this.surfaceFetchHints[tab] = {
						loading: false,
						error: this.opsDegradedLine(degraded),
						failed_fetch: true,
					}
					return
				}
				this.rejectionsPanel.data = ntR.data
				if (this.rejectionsPanel.data?.regime) {
					this.rejectionsPanel.regime = this.rejectionsPanel.data.regime
				}
				const degraded = !!(this.rejectionsPanel.data?.degraded || this.rejectionsPanel.data?.trust?.stale)
				const empty = !(this.rejectionsPanel.data?.no_trade_signals || []).length
				this.surfaceFetchHints[tab] = {
					loading: false,
					error: "",
					failed_fetch: false,
					stale: degraded,
					empty: !degraded && empty,
				}
				const todayR = await this.ccFetchJson("/api/v7/today", { retries: 2, backoff: 500, tab })
				if (todayR.ok && todayR.data) {
					const today = todayR.data
					if (!this.rejectionsPanel.regime && today.market_regime) {
						this.rejectionsPanel.regime = today.market_regime
					}
					this.rejectionsPanel.regimeReasons = today.no_trade_reasons || []
					if (!this.rejectionsPanel.regimeReasons.length && today.regime?.no_trade_reason) {
						this.rejectionsPanel.regimeReasons = [today.regime.no_trade_reason]
					}
					if (degraded && today.market_regime) {
						this.rejectionsPanel.regime = {
							...(this.rejectionsPanel.regime || {}),
							trend: today.market_regime.trend || today.market_regime.trend_regime || "SIDEWAYS",
							tradeability: today.market_regime.tradeability || "WAIT",
						}
					}
				}
			} catch (e) {
				const msg = String((e && e.message) || e || "")
				const degraded = this.opsInferDegradedState({ error: msg })
				this.rejectionsPanel.data = null
				this.surfaceFetchHints[tab] = {
					loading: false,
					error: this.opsDegradedLine(degraded),
					failed_fetch: true,
				}
			} finally {
				this.rejectionsPanel.loading = false
			}
		},

		async fetchConviction() {
			const tk = (this.dos.ticker || "").trim().toUpperCase()
			if (!tk) {
				this.dos.conviction = null
				return
			}
			this.dos.convictionLoading = true
			try {
				const r = await fetch("/api/v1/conviction/" + encodeURIComponent(tk))
				if (!r.ok) throw new Error("HTTP " + r.status)
				this.dos.conviction = await r.json()
			} catch (e) {
				console.warn("conviction fetch failed", e)
				this.dos.conviction = null
			} finally {
				this.dos.convictionLoading = false
			}
		},

		_mapSignalCardToDecision(card) {
			const cb = card.confidence_breakdown || {}
			const pct = (v) => Math.round(Math.max(0, Math.min(100, Number(v || 0) * 100)))
			return {
				ticker: card.ticker,
				action: card.action || "WAIT",
				conviction_tier: card.grade || "WATCH",
				sector: card.sector_bucket || "—",
				sector_stage: "—",
				macro_regime: card.technicals?.regime || "—",
				rs_state: card.technicals?.above_50sma ? "CONFIRMED_LEADER" : "EMERGING",
				leadership: card.direction || "—",
				synthetic: false,
				thesis_confidence: pct(cb.thesis),
				timing_confidence: pct(cb.timing),
				execution_confidence: pct(cb.execution),
				data_confidence: pct(cb.data),
				final_confidence: pct(card.score ? card.score / 100 : card.committee_confidence),
				entry_zone: card.entry_price ? "$" + Number(card.entry_price).toFixed(2) : "—",
				invalidation: card.stop_price ? "$" + Number(card.stop_price).toFixed(2) : "—",
				rr_ratio: card.risk_reward || "—",
				strategy_style: card.strategy || "—",
				setup_type: card.strategy || "—",
				rs_composite: card.score || 0,
				portfolio_fit: card.regime_allows_trading ? "ALLOWED" : "BLOCKED",
				portfolio_gate_reason: card.action_reason || "",
				why_now: card.explanation?.why_now || card.action_reason || "—",
				why_not_stronger: card.explanation?.why_not || "—",
				contradictions: card.explanation?.contradictions || [],
				peer_comparison: [],
				sector_type: card.sector_bucket || "",
			}
		},

		async fetchCommandBoard() {
			this.cmd.loading = true
			this.cmd.error = ""
			try {
				const r = await fetch("/api/watchlist?limit=60")
				if (!r.ok) throw new Error("HTTP " + r.status)
				const d = await r.json()
				this.cmd.watchlistRows = (d.board || []).map((row) => ({
					ticker: row.ticker,
					action: row.action,
					confidence: Math.round(Number(row.conviction || 0)),
					rs_state: row.rs_score != null ? "RS " + row.rs_score : "—",
					sector: row.setup || "",
				}))
				if (this.cmd.watchlistRows.length && !this.cmd.activeTicker) {
					await this.fetchDecision(this.cmd.watchlistRows[0].ticker)
				}
			} catch (e) {
				this.cmd.error = e.message || "board fetch failed"
			} finally {
				this.cmd.loading = false
			}
		},

		async fetchDecision(ticker) {
			const tk = (ticker || "").trim().toUpperCase()
			if (!tk) return
			this.cmd.activeTicker = tk
			this.cmd.loading = true
			this.cmd.error = ""
			this.cmd.agentError = ""
			try {
				const r = await fetch("/api/v7/signal-card/" + encodeURIComponent(tk))
				if (!r.ok) {
					const e = await r.json().catch(() => ({}))
					throw new Error(e.detail || "HTTP " + r.status)
				}
				const card = await r.json()
				this.cmd.decision = this._mapSignalCardToDecision(card)
				this.cmd.agent = {
					regime_gate: card.regime_allows_trading ? "PASS" : "BLOCK",
					conviction_tier: card.grade,
					rr_multiple: card.risk_reward,
					summary: card.action_reason,
					council: card.expert_council,
					journal: { persisted: false },
					agents: { critic: { notes: [] } },
				}
				try {
					const jr = await fetch("/api/v6/decision-journal?ticker=" + encodeURIComponent(tk))
					if (jr.ok) {
						const jd = await jr.json()
						this.cmd.agentJournal = Array.isArray(jd) ? jd : jd.entries || []
					}
				} catch (e) {}
			} catch (e) {
				this.cmd.error = e.message
				this.cmd.decision = null
			} finally {
				this.cmd.loading = false
			}
		},

		async ibkrFetchStatus(opts) {
			const scroll = !!(opts && opts.scrollToSession)
			this.ibkr.statusLoading = true
			try {
				await this.ibkrFetchPortfolioCompare().catch(() => {})
				const f = this.ibkr.orderForm || {}
				const qs = new URLSearchParams({
					manual_positions: String(this.ibkr.portfolioCompare.manual || 0),
					broker_positions: String((this.ibkr.positions || []).length),
					bracket_enabled: String(!!f.useBracket),
				})
				if (f.stopPrice) qs.set("bracket_stop", String(f.stopPrice))
				if (f.targetPrice) qs.set("bracket_target", String(f.targetPrice))
				const r = await fetch("/api/ibkr/status?" + qs.toString())
				if (!r.ok) {
					let errBody = {}
					try {
						errBody = await r.json()
					} catch (_x) {
						const txt = await r.text().catch(() => "")
						try {
							errBody = JSON.parse(txt)
						} catch (_y) {
							errBody = { error: txt }
						}
					}
					if (errBody.diagnosis) {
						this.ibkrApplyStatusPayload({
							connected: false,
							session_usable: false,
							mode: this.ibkr.mode,
							host: this.ibkr.host,
							diagnosis: errBody.diagnosis,
							gateway_reachable: !!errBody.diagnosis.gateway_reachable,
							api_port_open: !!errBody.diagnosis.api_port_open,
							health_label: errBody.diagnosis.label,
						})
					}
					this.ibkrApplyStatusFetchFailure(r.status, errBody.detail || errBody.error || errBody.message || "")
					return
				}
				const d = await r.json()
				this.ibkrApplyStatusPayload(d)
			} catch (e) {
				console.warn("ibkr status", e)
				this.ibkrApplyStatusFetchFailure(0, e && e.message ? e.message : String(e))
			} finally {
				this.ibkr.statusLoading = false
				if (scroll) this.$nextTick(() => this.ibkrScrollSessionIntoView())
			}
		},

		async triggerSelfLearn() {
			this.selfLearn.triggering = true
			this.selfLearn.lastResult = ""
			try {
				const r = await fetch("/api/v7/self-learn/trigger", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				const d = await r.json()
				this.selfLearn.lastResult = `Cycle: ${d.trades_analysed || 0} trades, ${d.adjustments_applied || 0} adjustments. Status: ${d.status}`
				await this.fetchSelfLearnStatus()
			} catch (e) {
				this.selfLearn.lastResult = "Error: " + e.message
			} finally {
				this.selfLearn.triggering = false
			}
		},
		async evaluateAB(param) {
			try {
				const r = await fetch(`/api/v7/self-learn/ab-evaluate?param=${encodeURIComponent(param)}`, {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				const d = await r.json()
				alert(`A/B ${param}: promoted=${d.promoted} — ${d.reason}`)
				await this.fetchABStatus()
			} catch (e) {
				console.warn("ab-evaluate failed", e)
			}
		},
		_handleAutoScheduleError(err) {
			const msg = String((err && err.message) || err || "unknown error")
			console.warn("auto-schedule failed", err)
			alert("Auto-schedule failed: " + msg)
		},
		async autoScheduleExperiments() {
			try {
				const r = await fetch("/api/v7/self-learn/auto-schedule-experiments", {
					method: "POST",
					headers: { "X-API-Key": window._apiKey || "dev-secret-local" },
				})
				if (!r.ok) {
					throw new Error("status " + r.status)
				}
				const d = await r.json()
				this.selfLearn.lastAutoSchedule = d
				await this.fetchABStatus()
				alert("Auto-schedule: " + (d.total_proposed || 0) + " experiment(s) proposed.")
			} catch (e) {
				this._handleAutoScheduleError(e)
			}
		},
	}
}
