/**
 * CC · Clarity Console — Phase 1 Alpine companion helpers.
 * Loaded before Alpine in index.html; mirrors fetch_surface_state.py copy.
 */
;(function (global) {
	"use strict"

	var CC_TOP_MONITOR_COUNT = 10

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
		dossier_research: "Live dossier fetch still loading — retry when core panels populate.",
		backtest_research:
			"Backtest API still loading — retry Run lab in a few seconds (research-only shell may appear meanwhile).",
		funds_research: "Fund Research Lab still loading — sleeve cards refresh when the API is ready.",
		rejections_diagnostic: "Rejection audit still loading — brief shell may show until the pipeline is ready.",
		flow_supporting: "Flow API still loading — mock/research shell may appear until live provider connects.",
		ops_diagnostic: "Ops API still loading — refresh Ops panels in a few seconds.",
		ibkr_execution:
			"IBKR API still loading — status may show LOGIN from port probe; Connect when /health mode=full.",
		"": "API still loading — retry in a few seconds.",
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
			return "OFFLINE — API unreachable · instant snapshot may be stale"
		}
		if (mode === "loading") {
			return "WARMING — backend importing modules · brief/monitor queue only until full"
		}
		if (o.instantDegraded || o.fetchFailed) {
			return "DEGRADED — instant snapshot · council/scanner may disagree until live ranked loads"
		}
		if (mode === "full") {
			return "LIVE — health mode full · ranked payloads authoritative when fetch badges clear"
		}
		return "LOADING — probing /health before treating board as live"
	}

	function warmupUpgradeQueue(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		if (mode !== "loading" && !o.briefFallback) return ""
		var parts = ["live ranked playbook", "today council reconciliation", "dossier enrichment"]
		if (o.nearMiss || o.briefFallback) {
			parts.unshift("monitor queue (brief near-miss + top watch)")
		}
		return "When API ready: " + parts.join(" · ")
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
		return (
			"Cold start: port 8000 instant shell may proxy to :8001 — " +
			"wait for /health mode=full; restart once if loading exceeds ~2 min"
		)
	}

	function instantDegradedBannerHint(healthData) {
		var h = healthData || {}
		if (String(h.mode || "").toLowerCase() === "loading") {
			var up = Math.round(Number(h.uptime_seconds) || 0)
			return (
				"Wait for /health mode=full before sizing or IBKR handoff · uptime " +
				up +
				"s · data contract + warmup strip stay authoritative if you dismiss"
			)
		}
		return "Refresh when fetch badges clear · page gates still apply on WAIT days"
	}

	function todayMissionMonitorsLabel(monitors, nearMissCount, watchQualified) {
		var n = (monitors || []).length
		var nm = Number(nearMissCount) || 0
		var wq = Number(watchQualified)
		if (!n && !nm) return bilingualLine("監察清單", "Monitors")
		var prefix =
			n && (isNaN(wq) || wq === 0)
				? bilingualLine("備援監察", "Fallback monitors")
				: bilingualLine("監察清單", "Monitors")
		var base = n ? prefix + " (" + n + ")" : prefix
		return nm ? base + " · " + nm + " " + bilingualLine("筆近失", "near-miss") : base
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
			var line = label + (detail && detail.length <= 72 ? " — " + detail : " — monitor only, not deploy")
			if (line && lines.indexOf(line) < 0) lines.push(line)
		}
		return lines
	}

	function todayBoardHeroSynthesisLine(opts) {
		// Compressed hierarchy: synthesis belongs in Why not deploy, not first-screen chrome.
		return ""
	}

	function todayExecutionReadinessDiagnostic(er) {
		var e = er || {}
		var sub = e.sub_status || {}
		var gaps = []
		if (sub.broker_transport !== "up") gaps.push("transport down")
		if (sub.session_auth !== "active") gaps.push("session inactive")
		if (sub.engine !== "on") gaps.push("engine off")
		if (sub.handoff_readiness !== "ready") gaps.push("handoff blocked")
		if (sub.bracket_readiness !== "ready") {
			gaps.push("bracket draft")
		} else if (sub.broker_transport !== "up" || sub.handoff_readiness !== "ready") {
			gaps.push("bracket template only")
		}
		if (e.circuit_breaker) gaps.push("breaker on")
		if (!gaps.length && e.trade_handoff_ready) return ""
		var reasons = (e.degraded_reasons || []).slice(0, 2)
		var base =
			"Exec diagnostic: " + (gaps.length ? gaps.join(" · ") : String(e.readiness_label || "path incomplete"))
		if (reasons.length) base += " — " + reasons.join("; ")
		return base + " (not deploy authority)"
	}

	function playbookStrategyDecayLine(row) {
		var r = row || {}
		return String(r.strategy_decay_line || "").trim()
	}

	function todayMissionMonitorsColumnHint(opts) {
		var o = opts || {}
		var wq = Number(o.watchQualified)
		var mc = Number(o.monitorCount) || 0
		var au = Number(o.avoidEntryCount) || 0
		if (!isNaN(wq) && wq > 0) {
			return (
				wq +
				" watch-qualified on funnel · upgrade-watch = track for deploy unlock · avoid-entry = no new risk today"
			)
		}
		if (mc > 0 || au > 0) {
			return "Upgrade watch = monitor for deploy unlock later · Avoid entry = on board but not for new entries today"
		}
		if (o.waitDay) {
			return "Upgrade watch only — attention queue, not deploy permission"
		}
		return "Ranking for attention — not handoff permission"
	}

	function todayMissionWaitSubtitle(opts) {
		// Authority strip owns deploy posture on WAIT days — avoid repeating here.
		return ""
	}

	function dashboardBlockerTreeLegend(opts) {
		var o = opts || {}
		var deployN = Number(o.deployQualified) || 0
		if (deployN > 0) {
			return "Subsystem layer checks — all must pass together for deploy authority."
		}
		return (
			"Subsystem layer checks — OK/BLOCK per layer. " +
			"No name cleared the full deploy stack today; individual layers can still pass."
		)
	}

	function executionBracketStatusLabel(sub) {
		var s = sub || {}
		var br = String(s.bracket_readiness || "draft").toLowerCase()
		var transport = String(s.broker_transport || "").toLowerCase()
		var handoff = String(s.handoff_readiness || "").toLowerCase()
		if (br === "ready" && (transport !== "up" || handoff !== "ready")) return "TEMPLATE"
		if (br === "ready") return "READY"
		return "DRAFT"
	}

	function executionBracketStatusTitle(sub) {
		var label = executionBracketStatusLabel(sub)
		if (label === "TEMPLATE") {
			return "Local bracket template staged — not live broker submission while transport/handoff blocked"
		}
		if (label === "READY") return "Bracket aligned for handoff when broker path is live"
		return "Bracket draft — sizing template not finalized"
	}

	function todayMissionSystemBlockers(opts) {
		var o = opts || {}
		var truth = o.systemTruth || o.system_truth
		if (truth && ((truth.reason_codes || []).length || truth.primary_blocker)) {
			return systemTruthMissionBlockers(truth).map(localizeMissionBlocker)
		}
		var out = []
		if (!o.ibkrReady) {
			var ib = String(o.ibkrShort || "OFFLINE")
				.trim()
				.toUpperCase()
			out.push(ib.indexOf("IBKR") === 0 ? ib : "IBKR " + ib)
		}
		var eng = resolveEngineState(truth, o)
		if (eng === "conflict") out.push("RUNTIME CONFLICT")
		else if (eng === "off") out.push("ENGINE OFF")
		else if (eng === "unknown") out.push("ENGINE UNKNOWN")
		if (o.breaker) {
			out.push("EXEC BLOCKED — risk breaker")
		}
		var fb = String(o.fetchBadge || "").toUpperCase()
		if (fb === "FETCH FAILED") {
			out.push("FETCH FAILED — not decision-grade")
		}
		var expired = briefExpiredOperatorLine(truth || {})
		if (expired && out.indexOf(expired) < 0) out.push(expired)
		return out.map(localizeMissionBlocker)
	}

	function systemTruthMissionBlockers(truth) {
		var t = truth || {}
		var codes = t.reason_codes || []
		var eng = resolveEngineState(t, {})
		var labels = {
			FALLBACK_BRIEF: "FALLBACK / BRIEF ONLY",
			BRIEF_EXPIRED: "BRIEF EXPIRED — not used for ranking",
			BRIEF_STALE: "BRIEF STALE",
			DATA_STALE: "Market: Stale",
			DATA_UNAVAILABLE: "MARKET DATA UNAVAILABLE",
			BOARD_STALE: "BOARD STALE",
			NO_VALID_BOARD: "NO VALID BOARD",
			DATA_DEGRADED: "DATA DEGRADED",
			ENGINE_OFF: "ENGINE OFF",
			ENGINE_CONFLICT: "RUNTIME CONFLICT",
			IBKR_OFFLINE: "IBKR OFFLINE",
			BROKER_OFFLINE: "IBKR OFFLINE",
			EXEC_BLOCKED: "EXEC BLOCKED — risk breaker",
			BOARD_WAIT: "BOARD WAIT — no deploy",
			BOARD_RESEARCH: "RESEARCH ONLY — board gate",
			BOARD_SUSPENDED: "AUTHORITY SUSPENDED",
			REGIME_WAIT: "REGIME WAIT",
			REGIME_NO_TRADE: "REGIME NO TRADE",
			NO_DEPLOY_QUALIFIED: "0 deploy-qualified — gates not met",
		}
		var out = []
		if (eng === "conflict" && out.indexOf("RUNTIME CONFLICT") < 0) {
			out.push("RUNTIME CONFLICT")
		}
		for (var i = 0; i < codes.length && out.length < 6; i++) {
			var code = String(codes[i] || "")
			if (code === "ENGINE_OFF" && (eng === "on" || eng === "conflict" || eng === "unknown")) continue
			if (code === "ENGINE_OFF" && eng === "conflict") continue
			if (code === "FALLBACK_BRIEF" && String(t.brief_freshness || "").toLowerCase() === "expired") continue
			var label = labels[code] || code.replace(/_/g, " ")
			if (out.indexOf(label) < 0) out.push(label)
		}
		return out
	}

	/** Canonical scoped freshness strip — matches system_truth.typed_freshness_display. */
	function systemTruthLine(truth) {
		var t = truth || {}
		if (t.typed_freshness_display) return String(t.typed_freshness_display)
		if (t.truth_strip) return String(t.truth_strip)
		return scopedFreshnessStrip(t)
	}

	function globalTruthStrip(truth) {
		var t = truth || {}
		var vm = shellTruthViewModel({ system_truth: t }, {})
		return localizeScopedFreshnessStrip(safeRenderText(vm.scopedStrip, { truth: t, blocked: vm.deployBlocked }))
	}

	function researchSurfaceBlock(truth, surface, extra) {
		var t = truth || {}
		var o = extra || {}
		var surf = String(surface || "research").toLowerCase()
		if (surf === "strategy") {
			var lab = strategyLabPageState({ system_truth: t, strategy_lab_page: t.strategy_lab_page })
			return {
				surface: surf,
				now: lab.now || "RESEARCH ONLY · Offline draft sandbox",
				blocker: lab.blocked || "deploy authority blocked · no deploy authority",
				next: lab.next || "repair live data — then run validation",
				research_only: true,
				why: lab.why || "",
				allowed: lab.allowed || "",
				validation_status: lab.validation_status || {},
				mode: lab.mode || "offline_draft_only",
			}
		}
		var posture = primaryOperatorState(t)
		var blocker = String(o.blocker || t.primary_blocker || "deploy authority blocked")
		if (!t.deploy_authority && blocker.toLowerCase().indexOf("deploy") < 0) {
			blocker = blocker + " · no deploy authority"
		}
		var nextMap = {
			discovery: "promote names to Playbook — scan evidence only",
			flow: "confirm in Playbook / Dossier — flow is supporting only",
			funds: "review sleeve research — not live allocation",
			strategy: "calibrate when closed-trade evidence exists",
			agent: "use Dashboard + Playbook for deploy gates",
			shadow: "shadow challengers — no capital impact until promoted",
		}
		var surf = String(surface || "research").toLowerCase()
		return {
			surface: surf,
			now: posture.primary || "MONITOR ONLY",
			blocker: blocker,
			next: o.next || nextMap[surf] || "monitor only",
			research_only: !t.deploy_authority,
		}
	}

	function strategyLabPageState(payload) {
		var p = payload || {}
		if (p.strategy_lab_page && typeof p.strategy_lab_page === "object") {
			return p.strategy_lab_page
		}
		var truth = p.system_truth || p.systemTruth || p || {}
		if (truth.strategy_lab_page && typeof truth.strategy_lab_page === "object") {
			return truth.strategy_lab_page
		}
		var mode = "offline_draft_only"
		var briefAge = Number(truth.brief_age_days || 0)
		var briefExpired = briefAge > 2 || String(truth.brief_freshness || "").toLowerCase() === "expired"
		var dataStale =
			["stale", "unavailable", "fallback", "expired"].indexOf(
				String(truth.market_data_freshness || "").toLowerCase(),
			) >= 0
		var boardStale =
			["stale", "fallback", "unavailable"].indexOf(String(truth.ranked_board_freshness || "").toLowerCase()) >= 0
		var brokerOffline = ["offline", "blocked"].indexOf(String(truth.broker_freshness || "").toLowerCase()) >= 0
		if (!(briefExpired || dataStale || boardStale || brokerOffline)) {
			mode = "validation_ready"
		}
		var blocked = ""
		if (briefExpired) blocked = "Brief expired " + briefAge + "d — excluded from strategy context"
		else if (boardStale) blocked = "Board stale — validation and Playbook promotion blocked"
		else if (dataStale) blocked = "Market data stale — refresh context before validation"
		else if (brokerOffline) blocked = "Broker offline — no deploy, sizing, or handoff"
		return {
			now: "RESEARCH ONLY · Offline draft sandbox",
			why: briefExpired
				? "Brief expired " + briefAge + "d — excluded"
				: dataStale
					? "market data stale"
					: boardStale
						? "board stale"
						: "research context only",
			allowed: "generate offline draft · save draft · refresh context",
			blocked: blocked,
			next: "repair live data / refresh board — then run validation",
			mode: mode,
			primary: "RESEARCH ONLY",
			brief_line: briefExpired
				? "Expired " + briefAge + "d — excluded from strategy context"
				: "Included in strategy context",
			validation_status: strategyLabValidationStatus(truth),
			actions: {},
		}
	}

	function strategyLabActionEnabled(action, mode, payload) {
		var p = payload || {}
		var page = strategyLabPageState(p)
		var actions = page.actions || {}
		var key = String(action || "")
		if (actions[key]) return !!actions[key].enabled
		var m = String(mode || page.mode || "offline_draft_only")
		if (m === "offline_draft_only") {
			return ["generate_draft", "save_draft", "refresh_context", "backtest_lab"].indexOf(key) >= 0
		}
		if (key === "export_pine" || key === "send_playbook") return m === "validated_research"
		return m !== "offline_draft_only"
	}

	function strategyLabActionReason(action, payload) {
		var page = strategyLabPageState(payload || {})
		var actions = page.actions || {}
		var key = String(action || "")
		if (actions[key] && actions[key].reason) return String(actions[key].reason)
		if (!strategyLabActionEnabled(key, page.mode, payload)) {
			return "Offline draft only — action blocked until validation context recovers"
		}
		return ""
	}

	function strategyLabValidationStatus(truth) {
		var t = truth || {}
		var bundle = t.strategy_lab_validation || t.strategy_validation || {}
		var briefAge = Number(t.brief_age_days || 0)
		var briefExpired = briefAge > 2 || String(t.brief_freshness || "").toLowerCase() === "expired"
		var marketFresh = String(t.market_data_freshness || "").toLowerCase() === "fresh"
		var boardFresh = String(t.ranked_board_freshness || "").toLowerCase() === "fresh"
		var brokerOk = ["offline", "blocked"].indexOf(String(t.broker_freshness || "").toLowerCase()) < 0
		function gate(passed, label) {
			return { passed: !!passed, label: label }
		}
		function flag(keys) {
			for (var i = 0; i < keys.length; i++) {
				if (bundle[keys[i]] === true) return true
			}
			return false
		}
		var tier = String(t.deploy_authority_tier || t.deployAuthority || "").toLowerCase()
		var deployAllowed = tier === "allowed" && t.deploy_authority === true
		return {
			live_data: gate(marketFresh, marketFresh ? "Fresh" : "Stale — refresh before validation"),
			brief: gate(
				!briefExpired,
				briefExpired
					? "Expired " + briefAge + "d — excluded from strategy context"
					: "Fresh — included in strategy context",
			),
			board: gate(boardFresh, boardFresh ? "Fresh" : "Stale — promotion blocked"),
			broker: gate(brokerOk, brokerOk ? "Ready" : "Offline — no handoff"),
			backtest: gate(
				flag(["backtest", "backtest_passed"]),
				flag(["backtest", "backtest_passed"]) ? "Passed" : "Pending",
			),
			walk_forward: gate(
				flag(["walk_forward", "walk_forward_passed"]),
				flag(["walk_forward", "walk_forward_passed"]) ? "Passed" : "Pending",
			),
			costs: gate(flag(["costs", "costs_passed"]), flag(["costs", "costs_passed"]) ? "Passed" : "Pending"),
			calibration: gate(
				flag(["calibration", "calibration_passed"]),
				flag(["calibration", "calibration_passed"]) ? "Ready" : "Provisional",
			),
			authority: {
				deploy: deployAllowed,
				sizing: deployAllowed,
				handoff: deployAllowed && brokerOk,
				label: deployAllowed
					? "deploy path open on qualified names"
					: "research only — no deploy, sizing, or handoff",
			},
		}
	}

	function strategyLabValidationSummary(payload) {
		var page = strategyLabPageState(payload || {})
		var vs = page.validation_status || strategyLabValidationStatus(payload && payload.system_truth)
		var parts = []
		;["live_data", "brief", "board", "broker", "backtest", "walk_forward", "costs", "calibration"].forEach(
			function (k) {
				var row = vs[k] || {}
				if (row.label) parts.push(k.replace("_", " ") + ": " + row.label)
			},
		)
		return parts.join(" · ")
	}

	/** Getting-started copy for research surfaces — Agent / Strategy Lab / Shadow. */
	function researchGettingStarted(surface, ctx) {
		var o = ctx || {}
		var surf = String(surface || "").toLowerCase()
		var watchN = Number(o.watchCandidates) || 0
		var boardStale = !!o.boardStale
		var brokerOffline = !!o.brokerOffline
		var systemBlocker = ""
		if (boardStale) {
			systemBlocker = "盤面資料過舊 — 請先刷新 Playbook · Board data stale — refresh Playbook first"
		} else if (brokerOffline && surf === "shadow") {
			systemBlocker = "目前 IBKR 離線 — 可先用 CSV 匯入 · IBKR offline — use CSV import first"
		}
		if (surf === "agent") {
			return {
				surface: "agent",
				title: "如何開始 · Getting started",
				badge: "Agent 盯盤 · 僅監察 · Monitor only",
				now: "用一句話建立監察規則 — 不會下單或調倉 · Describe a watch condition — no orders or sizing",
				copy: "輸入一句話描述你想監察的條件。Agent 只建立監察規則，不會下單或調倉。",
				placeholder: "例如：當 KO 跌破 20 日線時提醒我…",
				examples: [
					{ text: "當 KO 跌破 20 日線時提醒我", hint: "price alert" },
					{ text: "監察 XLP 成交量異常", hint: "volume watch" },
					{ text: "每日開盤前摘要 Watch 名單", hint: "watch list digest" },
					{ text: "當 VIX > 25 時降低關注度", hint: "calm-down guardrail" },
				],
				blocker: systemBlocker,
				next: watchN > 0 ? "從 Playbook Watch 名單建立第一條規則" : "先刷新 Playbook，再建立監察規則",
				nextButton: watchN > 0 ? "從 Playbook Watch 名單建立規則" : "先刷新 Playbook",
				watchCandidates: watchN,
			}
		}
		if (surf === "strategy") {
			return {
				surface: "strategy",
				title: "如何開始 · Getting started",
				badge: "策略實驗室 · Strategy Lab",
				now: "研究策略假設，不具部署權限 · Research strategy hypotheses — no deploy authority",
				copy: "策略實驗室用於研究假設，不具部署權限。",
				placeholder: "輸入策略 ID 或從下方範例選擇…",
				steps: [
					"選擇或輸入策略名稱（例：defensive_pullback）",
					"產生研究草稿",
					"驗證後轉為 Watch 規則",
					"到 Playbook 審閱候選",
				],
				examples: ["defensive_pullback", "rs_leader", "squeeze_breakout"],
				blocker: systemBlocker,
				next: "輸入策略 ID，點擊「產生研究草稿」開始",
				nextButton: "產生研究草稿",
			}
		}
		if (surf === "shadow") {
			return {
				surface: "shadow",
				title: "如何開始 · Getting started",
				badge: "影子帳戶 · Shadow account",
				now: "匯入交易紀錄以診斷行為 · Import trades to diagnose behavior — research only",
				copy: "影子帳戶用於行為診斷，需先匯入交易紀錄。",
				steps: ["匯入 CSV 交易紀錄，或", "連接 IBKR 歷史成交（當 broker 就緒時）"],
				outcomes: "勝率、持倉時間、過早平倉等（研究用）",
				csvColumns: "ticker,direction,entry_price,exit_price,entry_time,exit_time,strategy_id",
				csvExample: "AAPL,LONG,180.50,185.20,2025-01-15,2025-01-22,defensive_pullback",
				blocker: systemBlocker,
				next: "匯入第一筆交易紀錄，或連接 IBKR 後同步歷史成交",
				nextButton: "匯入交易紀錄",
				formatButton: "查看匯入格式說明",
			}
		}
		return {
			surface: surf,
			title: "如何開始 · Getting started",
			badge: "Research only",
			now: "Monitor only — no deploy authority",
			copy: "",
			blocker: systemBlocker,
			next: "Refresh when API badges clear",
			nextButton: "Refresh",
			examples: [],
			steps: [],
		}
	}

	function excludeExpiredBriefFromAgent(truth) {
		var t = truth || {}
		var age = Number(t.brief_age_days)
		if (!isNaN(age) && age > 2) return true
		return String(t.brief_freshness || "").toLowerCase() === "expired"
	}

	function agentBriefLabel(truth) {
		var t = truth || {}
		if (excludeExpiredBriefFromAgent(t)) {
			var age = Number(t.brief_age_days) || 0
			return "Brief: Expired " + age + "d — excluded from Agent brief and rule suggestions"
		}
		var bf = String(t.brief_freshness || "fresh").toLowerCase()
		if (bf === "stale") return "Brief: Stale — provisional rule status only"
		if (bf === "fresh") return "Brief: Fresh"
		if (bf === "fallback") return "Brief: Fallback board — monitor context only, not deploy"
		return "Brief: " + (bf.charAt(0).toUpperCase() + bf.slice(1))
	}

	function agentMaxOneBlockerLine(truth) {
		var t = Object.assign({}, truth || {}, { agent_blocker_compact: true })
		if (typeof systemTruthMissionBlockers === "function") {
			var blk = systemTruthMissionBlockers(t)
			if (blk && blk.length) return String(blk[0])
		}
		return String(t.primary_blocker || "").trim()
	}

	function agentSuggestedRules(candidates, truth) {
		var t = truth || {}
		if (excludeExpiredBriefFromAgent(t)) {
			return { rules: [], reason: agentBriefLabel(t) }
		}
		var list = candidates || []
		var scoped = (t.scoped_freshness || {}).agent_rules || t.agentRulesFreshness || "fresh"
		var provisional = String(scoped).toLowerCase() !== "fresh"
		var status = provisional ? "provisional" : "draft"
		var blocked = { AVOID: 1, NO_TRADE: 1, BLOCKED: 1, EXIT: 1, REDUCE: 1, PASS: 1 }
		var out = []
		var seen = {}
		for (var i = 0; i < list.length && out.length < 3; i++) {
			var c = list[i] || {}
			var ticker = String(c.ticker || c.symbol || c || "")
				.toUpperCase()
				.replace(/[^A-Z0-9.]/g, "")
			if (!ticker || seen[ticker]) continue
			var act = String(c.action || c.effective_action || "WATCH").toUpperCase()
			if (blocked[act]) continue
			seen[ticker] = true
			out.push({
				trigger: "Alert when " + ticker + " needs attention — monitor only",
				ticker: ticker,
				expiry: "session",
				source: String(c.source || "playbook_watch"),
				authority_effect: "none",
				rule_status: status,
			})
		}
		var reason = ""
		if (!out.length) {
			reason = "No fresh watch or near-miss on Playbook — no safe rule candidates"
		}
		return { rules: out, reason: reason }
	}

	function agentPageState(payload) {
		var p = payload || {}
		if (p.agent_page_state) return p.agent_page_state
		var truth = p.system_truth || p.truth || {}
		var mode = "active_monitor"
		var tier = String(truth.deploy_authority_tier || truth.deployAuthority || "").toLowerCase()
		if (!tier) tier = truth.deploy_authority === true ? "allowed" : "blocked"
		if (tier !== "allowed" || !truth.deploy_authority || excludeExpiredBriefFromAgent(truth)) {
			mode = "degraded_monitor"
		}
		var posture = primaryOperatorState(truth)
		var now =
			mode === "degraded_monitor"
				? "MONITOR ONLY · Agent degraded"
				: posture.primary === "MONITOR ONLY"
					? posture.now || "MONITOR ONLY · Active monitor copilot"
					: "MONITOR ONLY · Active monitor copilot"
		var suggested = agentSuggestedRules(p.watch_candidates || [], truth)
		var rules = p.rules || []
		var blockedLine = "no sizing, no handoff, no pilot entry"
		if (tier === "paper_only") blockedLine = "no live handoff while broker offline"
		else if (tier === "pilot_only") blockedLine = "no full-size deploy until execution-ready"
		else if (tier === "allowed" && truth.deploy_authority) blockedLine = ""
		var degradedNote = ""
		if (mode === "degraded_monitor") {
			var parts = []
			var blk = agentMaxOneBlockerLine(truth)
			if (blk) parts.push(blk)
			if (excludeExpiredBriefFromAgent(truth)) parts.push(agentBriefLabel(truth))
			if (tier !== "allowed") parts.push("Deploy authority blocked — sizing and handoff disabled")
			degradedNote =
				"Degraded Status Note: " + (parts.length ? parts.join(" · ") : "System degraded — monitor-only copilot")
		}
		return {
			now: now,
			why: agentMaxOneBlockerLine(truth) || "monitor only — no deploy authority",
			allowed:
				tier === "allowed" && truth.deploy_authority
					? "deploy selectively on qualified names"
					: "monitor candidates, create watch rules",
			blocked: blockedLine || "no sizing, no handoff, no pilot entry",
			rules: rules,
			rules_count: rules.length,
			suggested_rules: suggested.rules,
			suggested_rules_reason: suggested.reason,
			next:
				mode === "degraded_monitor"
					? "repair blockers on Dashboard — Agent stays monitor-only"
					: suggested.rules.length
						? "review suggested watch rules — alert only, no deploy"
						: "describe a monitor condition or seed rules from Playbook Watch",
			mode: mode,
			brief_label: agentBriefLabel(truth),
			degraded_status_note: degradedNote,
			agent_can_deploy: false,
			agent_can_size: false,
			agent_can_handoff: false,
			authority_guardrail_label: "Test authority guardrail",
		}
	}

	function portfolioRiskPageState(payload) {
		var p = payload || {}
		if (p.portfolio_mode && p.portfolio_operator_block) {
			return {
				mode: p.portfolio_mode.mode || "unavailable",
				portfolio_mode: p.portfolio_mode,
				operator_block: p.portfolio_operator_block,
				capital_action_queue_enabled: !!p.portfolio_mode.capital_action_queue_enabled,
				risk_review_only: !!p.portfolio_mode.risk_review_only,
			}
		}
		var pm = p.portfolio_mode || {}
		var block = p.portfolio_operator_block || {}
		return {
			mode: pm.mode || "unavailable",
			portfolio_mode: pm,
			operator_block: block,
			capital_action_queue_enabled: !!pm.capital_action_queue_enabled,
			risk_review_only: !!pm.risk_review_only,
		}
	}

	function portfolioOperatorBlock(payload) {
		var page = portfolioRiskPageState(payload)
		var block = page.operator_block || {}
		if (block.now) return block
		var pm = page.portfolio_mode || {}
		return {
			now: pm.risk_review_only ? "Risk review only" : "MONITOR ONLY",
			why: (pm.blockers || []).join(" · ") || "broker truth unavailable",
			allowed: "risk review, stop coverage, concentration diagnostics",
			blocked: "no sizing · no handoff · no deploy from portfolio capacity",
			validation: "",
			next: pm.broker_truth ? "review risk cockpit" : "repair IBKR / reconcile local book",
			details_collapsed: true,
			portfolio_mode: pm.mode || "unavailable",
			risk_capacity_authority: pm.risk_capacity_authority || "none",
			capital_action_queue_enabled: !!pm.capital_action_queue_enabled,
		}
	}

	function portfolioCapitalActionsEnabled(payload) {
		var page = portfolioRiskPageState(payload)
		return !!page.capital_action_queue_enabled && !page.risk_review_only
	}

	function portfolioRiskViewModel(today7, portfolio) {
		var t7 = today7 || {}
		var pf = portfolio || {}
		var decision = pf.pfDecision || pf.decision || pf
		var pm = decision.portfolio_mode || {}
		var vm = decision.portfolio_risk_view_model || {}
		var link = decision.ibkr_linkage || {}
		var cre = decision.critical_risk_event || {}
		var positions = pf.positions || pf.holdings || []
		var reviewOnly = !!(pm.risk_review_only || vm.risk_review_only || !pm.capital_action_queue_enabled)
		var capitalEnabled = !!(vm.capital_action_enabled != null
			? vm.capital_action_enabled
			: pm.capital_action_queue_enabled && !pm.risk_review_only)
		var brokerTruth = !!(pm.broker_truth || link.broker_truth || vm.broker_truth)
		var brokerOffline = !(pm.broker_connected || link.broker_connected)
		var showCritical = !!(vm.show_critical_risk_event != null ? vm.show_critical_risk_event : cre.active)
		var brokerBanner =
			vm.broker_truth_banner ||
			(showCritical
				? null
				: reviewOnly || !brokerTruth || brokerOffline
					? "Broker truth unavailable · Risk review only until sync"
					: null)
		return {
			mode: vm.mode || pm.mode || "unavailable",
			riskCapacityAuthority:
				vm.risk_capacity_authority || (reviewOnly ? "none" : pm.risk_capacity_authority || "none"),
			capitalActionEnabled: capitalEnabled,
			sleeveAuthority: vm.sleeve_authority || (reviewOnly ? "research_only" : "live"),
			liveAllocationEligibility:
				(vm.live_allocation_eligibility_pct != null
					? vm.live_allocation_eligibility_pct
					: reviewOnly
						? 0
						: 100) + "%",
			showSleeveResearchDefault: !!(vm.show_sleeve_research_default != null
				? vm.show_sleeve_research_default
				: !reviewOnly && capitalEnabled),
			showDemoToolsDefault: !!(vm.show_demo_tools_default != null ? vm.show_demo_tools_default : false),
			showHistoricalJournalDefault: !!(vm.show_historical_journal_default != null
				? vm.show_historical_journal_default
				: false),
			defaultDetailsCollapsed: !!(vm.default_details_collapsed != null
				? vm.default_details_collapsed
				: reviewOnly || !capitalEnabled),
			showCriticalRiskEvent: showCritical,
			brokerTruthBannerActive: !!(vm.broker_truth_banner_active != null
				? vm.broker_truth_banner_active
				: brokerBanner && !showCritical),
			brokerTruthBanner: brokerBanner,
			historicalJournalNote: vm.historical_journal_note || "Learning only · not broker truth",
			bookScopeLabel: vm.book_scope_label || (pm.book_label ? "Book · " + pm.book_label : "Book · Unavailable"),
			brokerScopeLabel: vm.broker_scope_label || (brokerTruth ? "Broker · Synced" : "Broker · Offline"),
			scopedTruthStrip:
				vm.scoped_truth_strip ||
				(pm.book_label || "Portfolio") + " · " + (brokerTruth ? "Broker synced" : "Broker offline"),
			collapseAllocationBands: !!(vm.collapse_allocation_bands != null
				? vm.collapse_allocation_bands
				: reviewOnly || !brokerTruth || !positions.length),
			collapseOperatingDiscipline: !!(vm.collapse_operating_discipline != null
				? vm.collapse_operating_discipline
				: reviewOnly),
			manualAddLabel: vm.manual_add_label || "Add manual placeholder",
			riskReviewOnly: reviewOnly,
			operatorBlock: portfolioOperatorBlock(decision),
		}
	}

	function operatorBlock(truth, page, operatorBlocks) {
		var t = truth || {}
		var p = String(page || "dashboard").toLowerCase()
		var blocks = operatorBlocks || t.operator_blocks || {}
		if (blocks[p] && typeof blocks[p] === "object") return localizeOperatorBlock(blocks[p])
		if (p === "dashboard" && t.operator_block && typeof t.operator_block === "object")
			return localizeOperatorBlock(t.operator_block)
		var posture = primaryOperatorState(t)
		var tier = String(t.deploy_authority_tier || t.deployAuthority || "").toLowerCase()
		if (!tier) tier = t.deploy_authority === true ? "allowed" : "blocked"
		var deploy = tier === "allowed" && !!t.deploy_authority
		var why = String(t.primary_blocker || "No edge today — preserve capital")
		var allowed = deploy ? "deploy selectively on qualified names" : "monitor candidates, create watch rules"
		if (!deploy) {
			var codes = t.reason_copy || []
			if (codes.length) why = codes.slice(0, 3).join(" + ")
		}
		var repair = (t.repair_priority || [])[0] || ""
		var pilotOk = pilotSizingAllowed(t)
		var next = repair
			? "Repair: " + String(repair).replace(/_/g, " ")
			: deploy
				? "Review deploy-qualified on Playbook"
				: tier === "paper_only"
					? "review paper simulation drafts on Playbook — no live handoff"
					: tier === "pilot_only"
						? pilotOk
							? "review Pilot bucket on Playbook — half size when broker ready"
							: "review Pilot bucket on Playbook — monitor only until broker ready"
						: "monitor only — patience is the active decision"
		var watchN = Number(t.watch_qualified_count || t.setup_qualified_count) || 0
		var tradeN = Number(t.trade_qualified_count) || 0
		var execN = Number(t.execution_qualified_count) || 0
		var deployN = deploy ? Number(t.deploy_qualified_count) || 0 : 0
		var paperN = Number(t.paper_qualified_count) || 0
		var pilotN = Number(t.pilot_eligible_count) || 0
		var validLine = t.qualification_counts_line || ""
		if (!validLine) {
			if (tier === "paper_only" && paperN > 0) {
				validLine =
					"Setup-qualified: " +
					watchN +
					" · Trade-qualified: " +
					tradeN +
					" · Execution-qualified: " +
					execN +
					" · Paper-qualified: " +
					paperN
			} else if (tier === "pilot_only" && pilotN > 0) {
				validLine =
					"Setup-qualified: " +
					watchN +
					" · Trade-qualified: " +
					tradeN +
					" · Pilot: " +
					pilotN +
					" · Execution-qualified: " +
					execN
			} else {
				validLine =
					"Setup-qualified: " +
					watchN +
					" · Trade-qualified: " +
					tradeN +
					" · Execution-qualified: " +
					execN +
					" · Deploy-qualified: " +
					deployN
			}
		}
		return localizeOperatorBlock({
			page: p,
			now: posture.now || posture.primary || "",
			primary: posture.primary || "MONITOR ONLY",
			secondary: posture.secondary || "",
			why: why,
			allowed:
				tier === "paper_only"
					? "paper simulation drafts — no live IBKR handoff"
					: tier === "pilot_only"
						? pilotOk
							? "pilot probe on B+ setups — half size when broker ready"
							: "pilot review only — PILOT/WATCH labels are review-only"
						: deploy
							? "deploy selectively on qualified names"
							: "monitor candidates, create watch rules",
			blocked:
				tier === "paper_only"
					? "no live handoff while broker offline"
					: tier === "pilot_only"
						? "no full-size deploy until execution-ready"
						: deploy
							? ""
							: "no sizing, no handoff, no pilot entry",
			valid_candidates: validLine || "Watch " + watchN + " · Deploy " + deployN,
			next: next,
			truth_strip: globalTruthStrip(t),
			regime_state: String(t.regime_state || "WAIT").toUpperCase(),
			deploy_authority: deploy,
			deploy_authority_tier: tier,
			paper_deploy_available: tier === "paper_only",
			daily_use_zh: t.daily_use_zh || "",
			repair_priority: (t.repair_priority || []).slice(0, 5),
		})
	}

	function deployAuthorityTier(truth) {
		var t = truth || {}
		var tier = String(t.deploy_authority_tier || t.deployAuthority || "").toLowerCase()
		if (tier !== "allowed" && tier !== "paper_only" && tier !== "pilot_only" && tier !== "blocked") {
			tier = t.deploy_authority === true ? "allowed" : "blocked"
		}
		if (tier === "allowed" && t.deploy_authority === false) tier = "blocked"
		var broker = String(t.broker_freshness || "").toLowerCase()
		if (tier === "allowed" && (broker === "offline" || broker === "blocked" || broker === "stale")) {
			tier = "blocked"
		}
		var boardGate = String(t.board_gate || "").toLowerCase()
		if (tier === "allowed" && (boardGate === "wait" || boardGate === "closed")) tier = "blocked"
		var brief = String(t.brief_freshness || "").toLowerCase()
		var briefAge = Number(t.brief_age_days)
		if (
			tier === "allowed" &&
			(t.brief_expired === true || brief === "expired" || (!isNaN(briefAge) && briefAge > 2))
		) {
			tier = "blocked"
		}
		if (tier === "allowed" && t.gates_active === true) tier = "blocked"
		if (tier === "allowed" && t.allows_trade_labels === false) tier = "blocked"
		return tier
	}

	function resolveEngineState(truth, ops) {
		var t = truth || {}
		var o = ops || {}
		var er = t.execution_readiness || {}
		var sub = er.sub_status || {}
		var signals = []
		if (er.engine_running === true || sub.engine === "on") signals.push("on")
		else if (er.engine_running === false || sub.engine === "off") signals.push("off")
		if (o.engineRunning === true || o.running === true) signals.push("on")
		else if (o.engineRunning === false || o.running === false) signals.push("off")
		if (t.engine_state) {
			var canon = String(t.engine_state).toLowerCase()
			if (canon === "on" || canon === "off" || canon === "conflict") signals.push(canon)
		}
		if (!signals.length) return "unknown"
		if (signals.indexOf("on") >= 0 && signals.indexOf("off") >= 0) return "conflict"
		var state = signals[0]
		var codes = (truth && truth.reason_codes) || []
		if (state === "on" && codes.indexOf("ENGINE_OFF") >= 0 && (o.running === true || o.engineRunning === true)) {
			return "conflict"
		}
		var er2 = (truth && truth.execution_readiness) || {}
		if (state === "on" && er2.engine_running === false && (o.running === true || o.engineRunning === true)) {
			return "conflict"
		}
		return state
	}

	function runtimeEngineHeaderLabel(opts) {
		var o = opts || {}
		if (o.breaker) return "BREAKER"
		var eng = resolveEngineState(o.truth || o.systemTruth, o.ops || o)
		if (eng === "conflict") return "Runtime: Conflict"
		return "Runtime: " + formatEngineState(eng)
	}

	function engineStateHeaderLabel(opts) {
		return runtimeEngineHeaderLabel(opts)
	}

	function primaryOperatorState(truth) {
		var t = truth || {}
		var regime = String(t.regime_state || "WAIT").toUpperCase()
		var tier = deployAuthorityTier(t)
		if (tier === "allowed") {
			if (regime === "NO_TRADE") {
				return { primary: "MONITOR ONLY", secondary: "NO_TRADE", now: "MONITOR ONLY · Regime closed" }
			}
			return { primary: regime, secondary: "", now: t.operator_tier_now || regime }
		}
		if (tier === "paper_only") {
			return {
				primary: "PAPER DEPLOY",
				secondary: regime !== "NO_TRADE" && regime !== "WAIT" ? regime : "",
				now: t.operator_tier_now || "Paper deploy available · IBKR offline",
			}
		}
		if (tier === "pilot_only") {
			return {
				primary: "PILOT",
				secondary: regime !== "NO_TRADE" && regime !== "WAIT" ? regime : "",
				now: t.operator_tier_now || "Pilot probe allowed — half size when broker ready",
			}
		}
		if (regime === "NO_TRADE") {
			return { primary: "MONITOR ONLY", secondary: "NO_TRADE", now: "MONITOR ONLY · Regime closed" }
		}
		return {
			primary: "MONITOR ONLY",
			secondary: regime !== "NO_TRADE" && regime !== "WAIT" ? regime : "",
			now: t.operator_tier_now || "MONITOR ONLY · Deploy blocked",
		}
	}

	function todayPrimaryStateLine(truth) {
		var posture = primaryOperatorState(truth || {})
		return posture.primary || "MONITOR ONLY"
	}

	function runtimePrimaryStateLine(truth) {
		return todayPrimaryStateLine(truth)
	}

	function primaryOperatorStateLine(truth) {
		return runtimePrimaryStateLine(truth)
	}

	function runtimeSecondaryRegimeLine(truth, fallbackTb) {
		return regimeSecondaryLine(truth, fallbackTb)
	}

	function regimeSecondaryLine(truth, fallbackTb) {
		var posture = primaryOperatorState(truth || {})
		if (posture.secondary) return posture.secondary
		var fb = String(fallbackTb || (truth && truth.regime_state) || "WAIT").toUpperCase()
		var primary = String(posture.primary || "").toUpperCase()
		if (fb && fb !== primary && fb !== "MONITOR ONLY") return fb
		return ""
	}

	function briefExpiredOperatorLine(truth) {
		var t = truth || {}
		var age = t.brief_age_days
		if (t.brief_expired === true || String(t.brief_freshness || "").toLowerCase() === "expired") {
			return age != null && !isNaN(Number(age)) && Number(age) > 0
				? "Brief expired " + Number(age) + "d"
				: "Brief expired"
		}
		if (age != null && !isNaN(Number(age)) && Number(age) > 2) {
			return "Brief expired " + Number(age) + "d"
		}
		return ""
	}

	function safeRenderText(text, context) {
		var ctx = context || {}
		var raw = String(text == null ? "" : text).trim()
		if (!raw) return ""
		var truth = ctx.truth || ctx.system_truth || {}
		var blocked =
			ctx.blocked === true ||
			ctx.deployAuthority === false ||
			truth.deploy_authority === false ||
			deployAuthorityTier(truth) === "blocked"
		var expiredLine = briefExpiredOperatorLine(truth)
		if (expiredLine) {
			raw = raw
				.replace(/brief[\s-]?fallback/gi, expiredLine)
				.replace(/fallback[\s-]?brief/gi, expiredLine)
				.replace(/FALLBACK\s*\/\s*BRIEF\sONLY/gi, expiredLine)
				.replace(/fallback mode/gi, expiredLine)
				.replace(/BRIEF ONLY/gi, expiredLine)
				.replace(/Sizing suspended in fallback mode/gi, "Sizing blocked — " + expiredLine)
		}
		if (blocked) {
			raw = removeSizingLanguageWhenBlocked(removeTradeLanguageWhenBlocked(raw, true), true)
		}
		raw = raw
			.replace(/Deploy gate open/gi, "Deploy authority: Blocked")
			.replace(/gates open/gi, "gates blocked")
			.replace(/BOARD POSTURE TRADE/gi, "BOARD POSTURE MONITOR ONLY")
			.replace(/Current:\s*TRADE/gi, "Current: MONITOR ONLY")
			.replace(/ENGINE\s+undefined/gi, "Runtime: Unknown")
			.replace(/Runtime:\s*undefined/gi, "Runtime: Unknown")
		return sanitizeOperatorDetail(raw)
	}

	function topMonitorLabels(today7) {
		var t = today7 || {}
		if (Array.isArray(t.top_monitor_labels) && t.top_monitor_labels.length) {
			return t.top_monitor_labels
		}
		if (t.top_monitor && t.top_monitor.label) return [t.top_monitor.label]
		return []
	}

	function cardDisplayReason(row, opts) {
		var o = opts || {}
		var truth = o.truth || {}
		var blocked = o.blocked === true || o.deployAuthority === false || (truth && truth.deploy_authority === false)
		var briefExpired =
			truth.brief_expired === true ||
			String(truth.brief_freshness || "").toLowerCase() === "expired" ||
			(truth.brief_age_days != null && Number(truth.brief_age_days) > 2)
		if (blocked) return sanitizeBlockedCandidateCopy(row, o)
		var raw = String(
			row.display_copy || row.summary || row.action_reason || row.why_now || row.action_rationale || "",
		)
		if (briefExpired || o.briefFallback) {
			var expiredLine = briefExpiredOperatorLine(truth)
			raw = raw.replace(/brief[\s-]?fallback/gi, expiredLine || "brief expired — excluded from ranking")
			if (!raw) raw = (expiredLine || "Brief expired") + " — reference plan only — monitor only"
		}
		return safeRenderText(raw, { truth: truth, blocked: blocked, deployAuthority: !blocked })
	}

	function briefFreshnessStripState(truth) {
		var t = truth || {}
		var brief = String(t.brief_freshness || "").toLowerCase()
		var age = t.brief_age_days
		if (brief === "expired" || t.brief_expired || (age != null && Number(age) > 2)) {
			return "expired"
		}
		if (age != null && Number(age) > 2) {
			return "expired"
		}
		return t.brief_freshness
	}

	function bilingualLine(zh, en) {
		if (zh && en) return zh + " · " + en
		return zh || en || ""
	}

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
		var expired = raw.match(/^Expired\s+(\d+d)$/i)
		if (expired) return bilingualLine("已失效 " + expired[1], raw)
		var zh = FRESHNESS_STATE_ZH[raw]
		return zh ? bilingualLine(zh, raw) : raw
	}

	function localizeScopedFreshnessStrip(line) {
		var raw = String(line || "").trim()
		if (!raw) return raw
		return raw
			.split(/\s*·\s*/)
			.map(function (part) {
				var m = part.match(/^([A-Za-z]+):\s*(.+)$/)
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
			var tail = raw.replace(/^IBKR\s*/i, "").trim()
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

	var OPERATOR_WHY_ZH = {
		"Regime gate closed — no new risk": "體制關閉 — 今日禁止新倉",
		"Board WAIT — monitor only, no deploy": "看板 WAIT — 僅監察，不可部署",
		"Board closed — preserve capital": "看板關閉 — 保留資金，不做新倉",
		"Market data unavailable — refresh before sizing": "缺少即時報價 — 刷新後再定倉",
		"Market data stale — rankings may not reflect live tape": "報價過期 — 排名可能非即時",
		"Ranked board stale — not execution-grade": "排名看板過期 — 不可作執行依據",
		"No valid ranked board — do nothing": "無有效看板 — 今日不做",
		"Brief expired — not used for ranking": "簡報過期 — 不用於排名",
		"Brief stale — confirm before using narrative": "簡報過期 — 敘述僅供參考",
		"Brief fallback — not execution-grade board": "簡報備援 — 非執行級看板",
		"Engine OFF — precomputed board only": "引擎關閉 — 僅用預算看板",
		"IBKR offline — no handoff": "IBKR 離線 — 不可交接",
		"Execution blocked — breaker or bracket": "執行阻斷 — 熔斷或 bracket 未就緒",
		"No deploy-qualified setups": "無通過部署門檻的標的",
		"No edge today — preserve capital": "今日無優勢 — 保留資金",
	}

	var OPERATOR_NEXT_ZH = {
		"repair IBKR / open Repair Console": "修復 IBKR 連線 — 開啟修復清單",
		"refresh board / regenerate brief": "刷新看板 — 重新產生簡報",
		"refresh board / wait for live ranked load": "刷新看板 — 等待 live 排名載入",
		"start engine on Ops": "至 Ops 啟動引擎",
		"review deploy-qualified on Playbook": "至 Playbook 複核可部署標的",
		"monitor only — patience is the active decision": "僅監察 — 耐心即是決策",
	}

	function localizeOperatorWhy(why) {
		var raw = String(why || "").trim()
		if (!raw) return raw
		return raw
			.split(/\s*\+\s*/)
			.map(function (part) {
				var p = String(part || "").trim()
				var zh = OPERATOR_WHY_ZH[p]
				return zh ? bilingualLine(zh, p) : p
			})
			.join(" · ")
	}

	function localizeOperatorNext(next) {
		var raw = String(next || "").trim()
		if (!raw) return raw
		if (raw.indexOf("Repair: ") === 0) {
			var task = raw.slice(8).replace(/_/g, " ")
			return bilingualLine("修復：" + task, raw)
		}
		var zh = OPERATOR_NEXT_ZH[raw]
		return zh ? bilingualLine(zh, raw) : raw
	}

	function localizeOperatorNow(now, secondary) {
		var raw = String(now || "").trim()
		if (raw === "MONITOR ONLY · Deploy blocked") {
			return "MONITOR ONLY · 僅監察 · 禁止部署"
		}
		if (raw === "MONITOR ONLY · Regime closed") {
			return "MONITOR ONLY · 僅監察 · 體制關閉"
		}
		if (raw === "SELECTIVE") {
			return "SELECTIVE · 選擇性（僅供觀察，不可部署）"
		}
		if (raw === "WAIT") {
			return "WAIT · 等待（僅監察）"
		}
		if (raw === "NO_TRADE") {
			return "NO_TRADE · 禁止交易"
		}
		if (secondary && raw.indexOf(secondary) >= 0 && raw.indexOf("MONITOR ONLY") >= 0) {
			return raw + " · 次級體制 " + secondary
		}
		return raw
	}

	function localizeOperatorAllowed(allowed) {
		var raw = String(allowed || "").trim()
		if (raw === "monitor candidates, create watch rules") {
			return bilingualLine("刷新看板、建立監察規則", raw)
		}
		if (raw === "deploy selectively on qualified names") {
			return bilingualLine("僅在合格標的上選擇性部署", raw)
		}
		return raw
	}

	function localizeOperatorBlocked(blocked) {
		var raw = String(blocked || "").trim()
		if (!raw) return raw
		if (raw === "no sizing, no handoff, no pilot entry") {
			return bilingualLine("不定倉、不交接券商、不可試探倉", raw)
		}
		return raw
	}

	function localizeValidCandidates(line) {
		var raw = String(line || "").trim()
		var m = raw.match(/^Watch\s+(\d+)\s*·\s*Deploy\s+(\d+)$/i)
		if (m) {
			return "監察 " + m[1] + " 筆 · 可部署 " + m[2] + " 筆 · Watch " + m[1] + " · Deploy " + m[2]
		}
		return raw
	}

	function localizeOperatorBlock(block) {
		var b = block || {}
		return {
			page: b.page,
			now: localizeOperatorNow(b.now, b.secondary),
			primary: b.primary,
			secondary: b.secondary,
			why: localizeOperatorWhy(b.why),
			allowed: localizeOperatorAllowed(b.allowed),
			blocked: localizeOperatorBlocked(b.blocked),
			valid_candidates: localizeValidCandidates(b.valid_candidates),
			next: localizeOperatorNext(b.next),
			truth_strip: b.truth_strip,
			regime_state: b.regime_state,
			deploy_authority: b.deploy_authority,
			repair_priority: b.repair_priority,
			blocker: b.blocker,
			agent_blocker_compact: b.agent_blocker_compact,
		}
	}

	function pilotSizingAllowed(truth, opts) {
		var t = truth || {}
		var o = opts || {}
		if (t.replay_mode || o.replayMode) return false
		if (t.deploy_authority === false) return false
		if (o.brokerReady === false) return false
		var broker = String(t.broker_freshness || "").toLowerCase()
		if (broker === "offline" || broker === "blocked") return false
		var brief = String(t.brief_freshness || "").toLowerCase()
		if (brief === "expired" || brief === "fallback" || brief === "stale") return false
		var market = String(t.market_data_freshness || "").toLowerCase()
		if (market === "stale" || market === "unavailable") return false
		var board = String(t.ranked_board_freshness || "").toLowerCase()
		if (board === "stale" || board === "fallback" || board === "unavailable") return false
		return true
	}

	function replayModeActive(asOf) {
		return !!String(asOf || "").trim()
	}

	function replayDeployBlocked(opts) {
		var o = opts || {}
		return (
			replayModeActive(o.replayAsOf) ||
			o.deployAuthority === false ||
			(o.truth && o.truth.deploy_authority === false)
		)
	}

	function replayBannerLine(opts) {
		var o = opts || {}
		if (!replayModeActive(o.replayAsOf)) return ""
		var line = "重播模式 · Replay: " + o.replayAsOf + " · 全頁歷史狀態（非即時）"
		if (o.replayNote) line += " · " + o.replayNote
		return line
	}

	function evidenceConflictPanel(panel) {
		var p = panel || {}
		if (p.collapsed) {
			return {
				title: "Evidence conflict",
				headline: p.headline || "No valid candidate — evidence panel collapsed",
				collapsed: true,
				for: [],
				against: p.against || [],
				missing: p.missing || ["No valid monitor candidates on board"],
				decision: p.decision || "Preserve capital",
			}
		}
		return {
			title: "Evidence conflict",
			headline: p.headline || "Evidence review",
			collapsed: false,
			for: p.for || [],
			against: p.against || [],
			missing: p.missing || [],
			decision: p.decision || "Preserve capital",
			upgrade_trigger: p.upgrade_trigger || "",
			invalidation: p.invalidation || "",
		}
	}

	function volatilityMonitorLabel(crisisRegime) {
		var c = crisisRegime || {}
		if (c.monitor_label) return String(c.monitor_label)
		var level = String(c.level || "").toLowerCase()
		if (level === "crisis") return "Crisis Monitor"
		return "Volatility Monitor"
	}

	function formatEngineState(state) {
		if (state == null || state === "" || String(state) === "undefined") return "Unknown"
		var s = String(state).toLowerCase()
		if (s === "conflict") return "Conflict"
		if (s === "on") return "On"
		if (s === "off") return "Off"
		if (s === "unknown") return "Unknown"
		return s.charAt(0).toUpperCase() + s.slice(1)
	}

	function runtimeFreshnessLabel(truth) {
		var t = truth || {}
		if (t.runtime_freshness) return String(t.runtime_freshness)
		var rs = String(t.runtime_state || "").toLowerCase()
		var eng = resolveEngineState(t, {})
		if (eng === "conflict") return "Conflict"
		if (rs === "warming" || rs === "loading") return "Warming"
		if (rs === "execution_blocked") return "Blocked"
		if (rs === "degraded") return "Degraded"
		if (rs === "unknown" || eng === "unknown") return "Unknown"
		if (rs === "engine_off" || eng === "off") return "Off"
		if (rs === "engine_on" || rs === "live" || eng === "on") return "Live"
		return rs ? rs.charAt(0).toUpperCase() + rs.slice(1) : "Unknown"
	}

	function _shellScopeFreshnessLabel(scope, state, briefAgeDays) {
		var s = String(state || "unknown").toLowerCase()
		if (scope === "Brief" && (s === "expired" || (briefAgeDays != null && Number(briefAgeDays) > 2))) {
			return briefAgeDays != null && !isNaN(Number(briefAgeDays)) && Number(briefAgeDays) > 0
				? "Expired " + Number(briefAgeDays) + "d"
				: "Expired"
		}
		if (scope === "Broker" && (s === "unavailable" || s === "offline")) return "Offline"
		if (s === "fresh") return "Fresh"
		if (s === "stale") return "Stale"
		if (s === "expired") return "Expired"
		if (s === "fallback") return "Fallback"
		if (s === "unavailable") return "Unavailable"
		return s.charAt(0).toUpperCase() + s.slice(1)
	}

	/** Canonical global shell truth — one view model for header/strips/blockers. */
	function shellTruthViewModel(today7, opts) {
		var t7 = today7 || {}
		var o = opts || {}
		var truth = t7.system_truth || {}
		var ops = o.ops || {}
		var briefAge =
			truth.brief_age_days != null
				? truth.brief_age_days
				: t7.brief_status && t7.brief_status.latest
					? t7.brief_status.latest.age_days
					: null
		var briefState = briefFreshnessStripState(truth)
		var eng = resolveEngineState(truth, ops)
		var posture = primaryOperatorState(truth)
		var tier = deployAuthorityTier(truth)
		var blocked = tier === "blocked" || truth.deploy_authority === false

		var marketLabel = "Market: " + _shellScopeFreshnessLabel("Market", truth.market_data_freshness)
		var boardLabel = "Board: " + _shellScopeFreshnessLabel("Board", truth.ranked_board_freshness)
		var briefLabel = "Brief: " + _shellScopeFreshnessLabel("Brief", briefState, briefAge)
		var brokerLabel = "Broker: " + _shellScopeFreshnessLabel("Broker", truth.broker_freshness)
		var runtimeLabel = "Runtime: " + (eng === "conflict" ? "Conflict" : runtimeFreshnessLabel(truth))
		var authorityLabel = "Authority: " + (truth.deploy_authority ? "Open" : "Blocked")

		var primaryLine = posture.primary || "MONITOR ONLY"
		var secondaryLine =
			posture.secondary ||
			regimeSecondaryLine(truth, t7.tradeability || (t7.regime && t7.regime.tradeability)) ||
			""
		if (blocked && primaryLine === "MONITOR ONLY" && !String(posture.now || "").includes("Deploy blocked")) {
			primaryLine = "MONITOR ONLY · Deploy blocked"
		} else if (posture.now) {
			primaryLine = posture.now
		}

		var blockers = systemTruthMissionBlockers(truth)
		if (!blockers.length && eng === "conflict") blockers = ["RUNTIME CONFLICT"]
		var blockerLine = blockers.slice(0, 3).join(" · ")
		var repairLine = executionRepairOneLiner(truth) || ""

		var scopedStrip = [marketLabel, boardLabel, briefLabel, brokerLabel, runtimeLabel, authorityLabel].join(" · ")
		if (truth.typed_freshness_display && eng !== "conflict") {
			scopedStrip = String(truth.typed_freshness_display)
		} else if (truth.truth_strip && eng !== "conflict") {
			scopedStrip = String(truth.truth_strip)
		}

		return {
			marketLabel: marketLabel,
			boardLabel: boardLabel,
			briefLabel: briefLabel,
			brokerLabel: brokerLabel,
			runtimeLabel: runtimeLabel,
			authorityLabel: authorityLabel,
			primaryLine: primaryLine,
			secondaryLine: secondaryLine,
			blockerLine: blockerLine,
			repairLine: repairLine,
			scopedStrip: scopedStrip,
			engineState: eng,
			engineHeaderLabel:
				o.breaker || (ops && ops.breaker) ? "BREAKER" : runtimeEngineHeaderLabel({ truth: truth, ops: ops }),
			deployBlocked: blocked,
			briefExpiredLine: briefExpiredOperatorLine(truth),
		}
	}

	function shellTruthScopedStrip(today7, opts) {
		var vm = shellTruthViewModel(today7, opts)
		return safeRenderText(vm.scopedStrip, {
			truth: (today7 && today7.system_truth) || {},
			blocked: vm.deployBlocked,
		})
	}

	function sanitizeBlockedCandidateCopy(row, opts) {
		var o = opts || {}
		var r = row || {}
		var blocked = o.blocked === true || o.deployAuthority === false
		var raw = String(r.display_copy || r.summary || r.action_reason || r.why_now || r.action_rationale || "")
		if (!blocked) return raw
		var ticker = String(r.ticker || "—").toUpperCase()
		var bucket = r.primary_bucket || r.lifecycle_bucket || "Watch"
		var reason = o.blocker || r.blocker || "no pilot entry — deploy authority blocked"
		var line = ticker + " · " + bucket + " candidate · State: monitor only · Blocked: " + reason
		return removeSizingLanguageWhenBlocked(removeTradeLanguageWhenBlocked(line, true), true)
	}

	function removeTradeLanguageWhenBlocked(text, blocked) {
		if (!blocked) return String(text || "")
		return String(text || "")
			.replace(/taking a Pilot entry/gi, "monitor only — pilot blocked")
			.replace(/taking a pilot entry/gi, "monitor only — pilot blocked")
			.replace(/pilot entry/gi, "monitor only")
			.replace(/half size max/gi, "PILOT/WATCH labels are review-only")
			.replace(/half size/gi, "PILOT/WATCH labels are review-only")
			.replace(/size at half risk/gi, "PILOT/WATCH labels are review-only")
			.replace(/handoff to IBKR/gi, "no handoff — blocked")
			.replace(/Deploy gate open/gi, "Deploy authority: Blocked")
			.replace(/\bentry\b/gi, "monitor")
			.replace(/\bsizing\b/gi, "no sizing")
	}

	function removeSizingLanguageWhenBlocked(text, blocked) {
		if (!blocked) return String(text || "")
		var out = removeTradeLanguageWhenBlocked(text, blocked)
		return out
			.replace(/full size/gi, "no sizing — blocked")
			.replace(/1R sizing/gi, "PILOT/WATCH labels are review-only")
			.replace(/standard 1R sizing/gi, "PILOT/WATCH labels are review-only")
	}

	function topWatchCandidateLabel(ticker) {
		return "Top watch candidate: " + String(ticker || "—").toUpperCase()
	}

	function closestUpgradeLabel(ticker) {
		return "Closest upgrade: " + String(ticker || "—").toUpperCase()
	}

	function topPromotionTriggerLabel(ticker, trigger) {
		var tk = String(ticker || "—").toUpperCase()
		var trig = String(trigger || "upgrade conditions").trim()
		return "Top promotion trigger: " + tk + " — " + trig
	}

	function sizingPillClass(sizing) {
		var a = String((sizing || {}).action || "").toLowerCase()
		if (a === "full") return "text-green-400"
		if (a === "half") return "text-amber-300"
		return "text-gray-400"
	}

	function sizingBandLabel(band) {
		var m = { high: "High confidence", medium: "Medium confidence", low: "Low confidence", very_low: "Wait" }
		return m[String(band || "").toLowerCase()] || ""
	}

	function sizingBlockedForDisplay(sizing) {
		var s = sizing || {}
		var a = String(s.action || "").toLowerCase()
		return a === "monitor_only" || ((Number(s.size_pct) || 0) <= 0 && a === "wait")
	}

	function sanitizeSizingForBlocked(sizing, blocked) {
		if (!blocked) return sizing || {}
		return {
			action: "monitor_only",
			size_pct: 0,
			size_label: "Wait · 僅監察",
			confidence_band: (sizing || {}).confidence_band || "low",
			rationale: "不可部署 · 僅監察，不定倉 · Deploy blocked — monitor only",
			sanitized: true,
		}
	}
	function executionRepairOneLiner(truth) {
		var t = truth || {}
		var broker = String(t.broker_freshness || "").toLowerCase()
		var execGate = String(t.execution_gate || "").toLowerCase()
		if (broker === "offline" || broker === "blocked" || execGate === "blocked") {
			var detail = broker === "offline" ? "broker offline" : "execution blocked"
			return "Execution blocked: " + detail + ". Open Repair Console."
		}
		return ""
	}

	function scopedFreshnessStrip(truth) {
		return shellTruthScopedStrip({ system_truth: truth || {} }, {})
	}

	function morningDecisionLine(today) {
		var t = today || {}
		var td = t.todays_decision || {}
		if (td.morning_decision_line) return String(td.morning_decision_line)
		var truth = t.system_truth || {}
		if (truth.morning_decision_line) return String(truth.morning_decision_line)
		return ""
	}

	function qualificationCountLine(levels, funnel) {
		var lv = levels || {}
		if (lv.count_line) return String(lv.count_line)
		var f = funnel || {}
		if (f.qualification_line) return String(f.qualification_line)
		return playbookQualificationFunnelLine(f)
	}

	function playbookQualificationFunnelLine(funnel, truth) {
		var f = funnel || {}
		var t = truth || {}
		var blocked = t.deploy_authority === false || deployAuthorityTier(t) === "blocked"
		if (!blocked && t.qualification_line) return String(t.qualification_line)
		if (!blocked && f.qualification_line) return String(f.qualification_line)
		return playbookQualificationLine(t, f)
	}

	function playbookQualificationLine(truth, funnel) {
		var t = truth || {}
		var blocked = t.deploy_authority === false || deployAuthorityTier(t) === "blocked"
		var pov = t.playbook_operator_view || {}
		if (!blocked && pov.qualification_line) return String(pov.qualification_line)
		var q = pov.qualification || {}
		var setup = Number(q.setup != null ? q.setup : t.setup_qualified_count || t.watch_qualified_count) || 0
		var trade = Number(q.trade != null ? q.trade : t.trade_qualified_count) || 0
		var execution = Number(q.execution != null ? q.execution : t.execution_qualified_count) || 0
		var deploy = Number(q.deploy != null ? q.deploy : t.deploy_qualified_count) || 0
		if (t.deploy_authority === false) deploy = 0
		var broker = String(t.broker_freshness || "").toLowerCase()
		if (broker === "offline" || broker === "blocked" || broker === "stale") {
			execution = 0
			deploy = 0
		}
		if (
			String(t.board_gate || "").toLowerCase() === "wait" ||
			String(t.board_gate || "").toLowerCase() === "closed"
		) {
			deploy = 0
		}
		var parts = []
		if (setup) parts.push(setup + " setup-qualified")
		if (trade && t.deploy_authority !== false) parts.push(trade + " trade-qualified")
		if (execution && t.deploy_authority !== false && execution !== deploy) {
			parts.push(execution + " execution-qualified")
		}
		parts.push(deploy + " deploy-qualified")
		var line = parts.join(" · ")
		if (/deploy gate open|gates open/i.test(line)) return parts[parts.length - 1] || "0 deploy-qualified"
		return line
	}

	var _PLAYBOOK_AVOID = { AVOID: 1, NO_TRADE: 1, PASS: 1, EXIT: 1, REDUCE: 1, BLOCKED: 1 }
	var _PLAYBOOK_TRADE = {
		TRADE: 1,
		BUY: 1,
		BUY_ON_DIP: 1,
		STRONG_TRADE: 1,
		TRADE_NOW: 1,
	}
	var _PLAYBOOK_PILOT = { PILOT: 1 }
	var _PLAYBOOK_WATCH = { WATCH: 1, WAIT: 1, WATCH_TRIGGER: 1 }

	function assignPlaybookPrimaryBucket(row, deployAuth, nmSet, regimeState) {
		var act = String((row && (row.effective_action || row.action)) || "WATCH").toUpperCase()
		var ticker = String((row && row.ticker) || "").toUpperCase()
		if (_PLAYBOOK_AVOID[act]) return "Rejected"
		if (deployAuth && row && row.execution_ready && _PLAYBOOK_TRADE[act]) return "Deploy"
		if (_PLAYBOOK_PILOT[act]) return "Pilot"
		if ((nmSet && nmSet[ticker]) || (row && (row.whats_missing || row.near_miss))) return "Near-miss"
		if (_PLAYBOOK_WATCH[act] || _PLAYBOOK_TRADE[act]) return "Watch"
		var score = Number((row && row.score) || 0) || 0
		if (score >= 6) return "Near-miss"
		return "Rejected"
	}

	function secondaryPlaybookTags(row, deployAuth) {
		var tags = []
		var explicit = (row && (row.playbook_tags || row.secondary_tags)) || []
		if (explicit && explicit.length) {
			explicit.forEach(function (t) {
				if (t) tags.push(String(t))
			})
		}
		if (row && (row.fastest_improving || row.improvement_rank === 1)) tags.push("fastest_improving")
		if (row && (row.rr_improving || row.risk_reward_improving)) tags.push("rr_improving")
		if (row && (row.sector_leader || String(row.leader || "").toUpperCase() === "SECTOR_LEADER")) {
			tags.push("sector_leader")
		}
		var act = String((row && (row.effective_action || row.action)) || "").toUpperCase()
		if (!deployAuth && _PLAYBOOK_TRADE[act] && Number((row && row.score) || 0) >= 7) {
			tags.push("high_conviction_blocked")
		}
		var seen = {}
		var out = []
		tags.forEach(function (tag) {
			var key = String(tag || "")
				.trim()
				.toLowerCase()
			if (key && !seen[key]) {
				seen[key] = true
				out.push(key)
			}
		})
		return out
	}

	function buildPlaybookBuckets(rows, nearMiss, deployAuth, regimeState) {
		var nmSet = {}
		;(nearMiss || []).forEach(function (r) {
			var t = String((r && r.ticker) || "").toUpperCase()
			if (t) nmSet[t] = true
		})
		var merged = (rows || []).slice()
		var seen = {}
		merged.forEach(function (r) {
			seen[String((r && r.ticker) || "").toUpperCase()] = true
		})
		;(nearMiss || []).forEach(function (row) {
			var t = String((row && row.ticker) || "").toUpperCase()
			if (t && !seen[t]) {
				merged.push(Object.assign({}, row, { near_miss: true }))
				seen[t] = true
			}
		})
		var prio = { Deploy: 0, Pilot: 1, Watch: 2, "Near-miss": 3, Rejected: 4 }
		var winner = {}
		merged.forEach(function (row) {
			var bucket = assignPlaybookPrimaryBucket(row, deployAuth, nmSet, regimeState)
			var ticker = String((row && row.ticker) || "").toUpperCase()
			if (!ticker) return
			var p = prio[bucket]
			var prev = winner[ticker]
			if (!prev || p < prev.prio) {
				winner[ticker] = {
					prio: p,
					row: row,
					bucket: bucket,
				}
			}
		})
		var buckets = {
			deploy: [],
			pilot: [],
			watch: [],
			near_miss: [],
			rejected_count: 0,
		}
		Object.keys(winner).forEach(function (ticker) {
			var w = winner[ticker]
			var key = w.bucket === "Near-miss" ? "near_miss" : String(w.bucket || "Rejected").toLowerCase()
			if (key === "rejected") {
				buckets.rejected_count += 1
				return
			}
			if (!buckets[key]) return
			buckets[key].push(
				Object.assign({}, w.row, {
					primary_bucket: w.bucket,
					playbook_tags: secondaryPlaybookTags(w.row, deployAuth),
				}),
			)
		})
		return buckets
	}

	function playbookBucketsPopulated(buckets) {
		var b = buckets || {}
		return (
			(b.deploy && b.deploy.length) ||
			(b.pilot && b.pilot.length) ||
			(b.watch && b.watch.length) ||
			(b.near_miss && b.near_miss.length) ||
			Number(b.rejected_count || 0) > 0
		)
	}

	/** Canonical Playbook authority view — system_truth + buckets + scoped qualification. */
	function playbookAuthorityViewModel(today7, opts) {
		var t7 = today7 || {}
		var o = opts || {}
		var ranked = o.rankedOpps || {}
		var truth = t7.system_truth || {}
		var pov = ranked.playbook_operator_view || t7.playbook_operator_view || truth.playbook_operator_view || {}
		var funnel = ranked.filter_funnel || t7.filter_funnel || {}
		var rows = ranked.rows || o.ranked_rows || []
		var nearMiss = ranked.near_miss || t7.near_miss || []
		var tier = deployAuthorityTier(truth)
		var authority = String(pov.authority || "").toUpperCase()
		if (!authority) {
			if (tier === "allowed" && truth.deploy_authority) authority = "ALLOWED"
			else if (tier === "paper_only") authority = "PAPER_ONLY"
			else if (tier === "pilot_only") authority = "PILOT"
			else authority = "BLOCKED"
		}
		var blocked =
			authority === "BLOCKED" ||
			(truth.deploy_authority === false && tier !== "paper_only" && tier !== "pilot_only")
		var deployGateOpen = !blocked && truth.deploy_authority === true
		var postureState = primaryOperatorState(truth)
		var boardPosture = blocked ? "MONITOR ONLY" : String(postureState.primary || "MONITOR ONLY")
		var secondaryPosture = blocked ? String(postureState.secondary || truth.regime_state || "").toUpperCase() : ""
		if (blocked && (boardPosture === "TRADE" || boardPosture === "SELECTIVE" || boardPosture === "STRONG_TRADE")) {
			boardPosture = "MONITOR ONLY"
		}
		var deployAuth = deployGateOpen
		var buckets = pov.buckets || {}
		if (!playbookBucketsPopulated(buckets) && (rows.length || nearMiss.length)) {
			buckets = buildPlaybookBuckets(
				rows,
				nearMiss,
				deployAuth,
				String(truth.regime_state || "WAIT").toUpperCase(),
			)
		}
		var watchCount = (buckets.watch || []).length
		var nearCount = (buckets.near_miss || []).length
		var noMonitors = watchCount === 0 && nearCount === 0
		var qual = pov.qualification || {}
		var setupQualified =
			Number(qual.setup != null ? qual.setup : truth.setup_qualified_count || truth.watch_qualified_count) || 0
		var deployQualified = deployGateOpen
			? Number(qual.deploy != null ? qual.deploy : truth.deploy_qualified_count) || 0
			: 0
		var qualificationLine = playbookQualificationLine(truth, funnel)
		var bestAction = pov.best_action || ""
		if (!bestAction && blocked) {
			bestAction = noMonitors ? "do nothing — preserve capital" : "monitor only — patience is the active decision"
		}
		var next = pov.next || []
		if (!next.length && noMonitors) {
			next = ["No valid monitor candidates — refresh board or wait for setup"]
		}
		var eng = resolveEngineState(truth, o.ops || {})
		return {
			authority: authority,
			blocked: blocked,
			posture: boardPosture,
			boardPosture: boardPosture,
			secondaryPosture: secondaryPosture,
			deployGateOpen: deployGateOpen,
			deployQualified: deployQualified,
			setupQualified: setupQualified,
			truth_strip: safeRenderText(pov.truth_strip || truth.truth_strip || globalTruthStrip(truth), {
				truth: truth,
				blocked: blocked,
			}),
			qualification_line: qualificationLine,
			best_action: safeRenderText(bestAction, { truth: truth, blocked: blocked }),
			next: next,
			no_valid_monitors: noMonitors,
			simulation_drafts_collapsed: blocked || !!pov.simulation_drafts_collapsed,
			buckets: buckets,
			engineState: eng,
			engineLabel: eng === "conflict" ? "Conflict" : formatEngineState(eng),
		}
	}

	function playbookAuthorityView(payload) {
		var p = payload || {}
		var today7 = {
			system_truth: p.system_truth || (p.today7 && p.today7.system_truth) || {},
			playbook_operator_view: p.playbook_operator_view,
			filter_funnel: p.filter_funnel,
			near_miss: p.near_miss,
		}
		return playbookAuthorityViewModel(today7, {
			rankedOpps: {
				rows: p.ranked_rows || [],
				near_miss: p.near_miss || [],
				filter_funnel: p.filter_funnel,
				playbook_operator_view: p.playbook_operator_view,
			},
			ops: p.ops || {},
		})
	}

	function playbookNoEdgeLine(rows) {
		var list = rows || []
		var counts = { Deploy: 0, Pilot: 0, Watch: 0, "Near-miss": 0, Rejected: 0 }
		list.forEach(function (r) {
			var b = String(r.primary_bucket || r.lifecycle_bucket || "").trim()
			if (!b) return
			var key = b.charAt(0).toUpperCase() + b.slice(1).toLowerCase()
			if (key === "Near_miss" || key === "Near-miss") key = "Near-miss"
			if (counts[key] != null) counts[key] += 1
		})
		return (
			"NO EDGE TODAY · " +
			(counts.Deploy || 0) +
			" Deploy · " +
			(counts.Pilot || 0) +
			" Pilot · " +
			(counts.Watch || 0) +
			" Watch · " +
			(counts["Near-miss"] || 0) +
			" Near-miss · Rejected hidden · Best action: do nothing"
		)
	}

	function todayMissionBlockersTitle(opts) {
		var o = opts || {}
		if (o.waitDay && o.hasSystem) {
			return bilingualLine("系統阻斷 · 門檻標記", "System blockers · gate flags")
		}
		if (o.waitDay) {
			return bilingualLine("門檻標記", "Gate flags")
		}
		return o.hasSystem ? bilingualLine("系統阻斷", "System blockers") : bilingualLine("阻斷項", "Blockers")
	}

	function todayMissionEmptyBlockersCopy(opts) {
		var o = opts || {}
		if ((o.systemBlockers || []).length && !(o.cardGates || []).length) {
			return bilingualLine("無卡片級門檻標記", "No card-level gate flags")
		}
		return bilingualLine("無標記", "None flagged")
	}

	/** Playbook WAIT-day monitor guidance — operator-facing, no deploy authority. */
	function playbookWhatToMonitorLine(opts) {
		var o = opts || {}
		if (!o.waitDay) return ""
		var parts = []
		if (o.topSymbol) {
			parts.push(String(o.topSymbol).toUpperCase() + " 升級條件")
		}
		var nm = Number(o.nearMissCount) || 0
		if (nm > 0) {
			parts.push(nm + " 筆監察候選")
		}
		parts.push("複核路徑見下方清單")
		var body = parts.length ? parts.join(" · ") : "監察排名 · gate context"
		return "MONITOR ONLY · 僅監察 — " + body + " · 本頁不可下單、不可部署"
	}

	var AUTHORITY_COPY = {
		no_trade_authority: "本頁不可下單 · No trade authority here",
		monitor_item: "監察候選（不可部署）· monitor item",
		research_item: "研究候選（僅供觀察）· research item",
		upgrade_condition: "升級條件 · upgrade condition",
		review_path: "複核路徑 · review path",
		scan_evidence: "掃描證據 · scan evidence",
		playbook_review: "送 Playbook 複核 · Playbook review path",
	}

	function authorityNoTradeLine() {
		return AUTHORITY_COPY.no_trade_authority
	}

	function authorityBlockedNowLine(opts) {
		var o = opts || {}
		var state = String(o.effectiveState || o.boardState || "WAIT").toUpperCase()
		if (state === "NO_TRADE") {
			return "今日禁止新倉 · No new risk today"
		}
		if (o.confirmOnly) {
			return "僅結構複核 · Confirm-only — structure review only"
		}
		if (o.degraded || o.researchOnly) {
			return "研究面已降級 · Degraded research surface"
		}
		return "今日狀態：禁止部署 · No deploy today"
	}

	function authorityBlockedBlockerLine(opts) {
		var o = opts || {}
		var parts = []
		if (o.primaryBlocker) parts.push(localizeOperatorWhy(String(o.primaryBlocker)))
		if (o.brokerOffline) parts.push("IBKR 未就緒 · broker offline")
		if (o.deployQualified === 0 && o.deployQualified != null) {
			parts.push("0 筆通過部署門檻 · 0 deploy-qualified")
		}
		if (o.briefExpired || (o.briefAgeDays != null && Number(o.briefAgeDays) > 2)) {
			parts.push(
				"晨報已失效 " +
					(o.briefAgeDays != null ? o.briefAgeDays + "d" : "") +
					" · Brief expired — excluded from ranking",
			)
		} else if (o.briefFallback) {
			parts.push("簡報備援樣本 · brief sample only")
		}
		if (o.execBlocked) parts.push("執行已阻斷 · exec blocked")
		if (o.gatedRegime && o.regimeState && o.regimeState !== o.effectiveState) {
			parts.push(
				"體制 " + String(o.regimeState) + " 已閘為 " + String(o.effectiveState || "WAIT") + " · regime gated",
			)
		}
		if (!parts.length) {
			parts.push("升級條件未滿足 · upgrade conditions not met")
		}
		return parts.join(" · ")
	}

	function authorityBlockedNextLine(opts) {
		var o = opts || {}
		if (o.surface === "discovery") {
			return AUTHORITY_COPY.playbook_review
		}
		if (o.surface === "dossier" && o.confirmOnly) {
			return "先載入 live 檔案，再回 Dashboard 複核 · Load live dossier, then review on Dashboard"
		}
		if (o.surface === "ibkr") {
			return "依 IBKR 修復清單逐步連線 · Follow IBKR repair checklist"
		}
		if (o.brokerOffline) {
			return "開啟 IBKR 分頁完成連線 · Open IBKR tab — connect before handoff"
		}
		if (o.topSymbol) {
			return (
				"追蹤 " +
				String(o.topSymbol).toUpperCase() +
				" 升級條件 · Track upgrade conditions for " +
				String(o.topSymbol).toUpperCase()
			)
		}
		return "查看監察排名與升級條件 · Review monitor ranking and upgrade checklist"
	}

	function discoveryResearchHeaderNote(regimeLine, opts) {
		var o = opts || {}
		var regime = String(regimeLine || "—").trim()
		if (o.fallback) {
			return (
				"掃描證據（備援樣本）· fallback scan evidence — " +
				AUTHORITY_COPY.no_trade_authority +
				" · 體制 " +
				regime
			)
		}
		return (
			"掃描證據 · scan evidence — " +
			AUTHORITY_COPY.research_item +
			" · " +
			AUTHORITY_COPY.playbook_review +
			" · 體制 " +
			regime +
			" — WAIT/NO_TRADE 日零命中屬正常"
		)
	}

	function discoveryResearchActionLabel(row) {
		var r = row || {}
		var act = String(r.action || "WATCH").toUpperCase()
		if (["AVOID", "NO_TRADE", "BLOCKED"].indexOf(act) >= 0) {
			return "迴避參考 · avoid context"
		}
		if (["TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE"].indexOf(act) >= 0) {
			return AUTHORITY_COPY.research_item
		}
		return AUTHORITY_COPY.monitor_item
	}

	function discoveryResearchCue(row) {
		var r = row || {}
		var cue = String(r.next_action || "").trim()
		if (!cue) return AUTHORITY_COPY.playbook_review
		if (/buy|enter|deploy|trade now|pilot|actionable|candidate/i.test(cue)) {
			return AUTHORITY_COPY.playbook_review
		}
		return cue
	}

	function discoveryVerdictSpeculativeLabel() {
		return "頂部研究候選（非交易指令）· top research item"
	}

	function discoveryVerdictConfirmedLabel(opts) {
		var o = opts || {}
		if (o.fallback) return "備援監察樣本 · fallback monitor sample"
		if (o.briefFallback) return "簡報備援樣本 · brief sample only"
		return "多掃描器重合 · multi-scanner overlap"
	}

	function discoveryScannerRunLabel(diagnostics) {
		var d = diagnostics || {}
		var freshness = String(d.data_freshness || d.scanner_run_freshness || "unknown").toLowerCase()
		var hub = String(d.hub_status || "").toLowerCase()
		if (hub === "warming" || hub === "degraded") {
			return "Scanner run: " + hub.charAt(0).toUpperCase() + hub.slice(1)
		}
		if (freshness === "live") return "Scanner run: Live"
		if (freshness === "stale") return "Scanner run: Stale"
		if (freshness === "warming") return "Scanner run: Warming"
		return "Scanner run: " + (freshness.charAt(0).toUpperCase() + freshness.slice(1))
	}

	function discoveryStatusLine(truth, diagnostics) {
		var t = truth || {}
		var panel = (diagnostics && diagnostics.discovery_panel) || {}
		if (panel.status_line) return String(panel.status_line)
		var parts = [discoveryScannerRunLabel(diagnostics)]
		var board = String(t.ranked_board_freshness || "").toLowerCase()
		var boardGate = String(t.board_gate || "").toLowerCase()
		if (boardGate === "wait") parts.push("Board WAIT")
		else if (board === "stale" || board === "fallback" || board === "unavailable") {
			parts.push("Board " + (board.charAt(0).toUpperCase() + board.slice(1)))
		} else if (board === "fresh") parts.push("Board Fresh")
		var age = t.brief_age_days
		var brief = String(t.brief_freshness || "").toLowerCase()
		if (brief === "expired" || t.brief_expired || (age != null && Number(age) > 2)) {
			parts.push(age != null && Number(age) > 2 ? "Brief Expired " + Number(age) + "d" : "Brief Expired")
		}
		var broker = String(t.broker_freshness || "").toLowerCase()
		if (broker) {
			parts.push(
				broker === "offline" || broker === "blocked"
					? "Broker Offline"
					: "Broker " + broker.charAt(0).toUpperCase() + broker.slice(1),
			)
		}
		if (!t.deploy_authority) parts.push("Deploy authority: None")
		return parts.join(" · ")
	}

	function discoveryRowFreshnessLabel(hit, truth) {
		var h = hit || {}
		if (h.scanner_run_freshness) return "Scanner run: " + String(h.scanner_run_freshness)
		if (h.freshness_scope) return String(h.freshness_scope)
		var t = truth || {}
		return discoveryScannerRunLabel({ data_freshness: h.freshness || "live" })
	}

	function discoveryFunnelView(payload, truth) {
		var p = payload || {}
		var funnel = p.discovery_operator_view || {}
		var verdict = funnel.verdict || p.discovery_verdict || {}
		var panel = funnel.panel || verdict || {}
		var counts = funnel.funnel_counts || {}
		var t = truth || p.system_truth || {}
		var diagnostics = p.diagnostics || {}
		var strict = Number(funnel.strict_passed_count || verdict.strict_passed_count || counts.regime || 0)
		var now =
			panel.now ||
			verdict.now ||
			(strict === 0
				? "Research-only · deploy blocked"
				: verdict.default_sentence || funnel.empty_message || "No validated research candidates")
		var why =
			panel.why ||
			verdict.why ||
			(verdict.best_family != null
				? "Best family: " + String(verdict.best_family).replace(/_/g, " ")
				: "Scan evidence only — not deploy authority")
		var funnelLine =
			panel.funnel_line ||
			verdict.funnel_line ||
			"Raw " +
				(counts.raw || 0) +
				" / hits " +
				(counts.raw || 0) +
				" / strict " +
				strict +
				" / shortlist " +
				(counts.shortlist || 0) +
				" / deploy " +
				(strict > 0 && panel.mode === "usable" ? counts.shortlist || 0 : 0)
		var bestAction =
			panel.best_action ||
			verdict.best_action ||
			verdict.next_action ||
			(strict === 0 ? "No new research candidates. Refresh Dashboard + Playbook." : "Send to Playbook Review")
		return {
			mode: funnel.mode || verdict.mode || panel.mode || "research_only",
			now: now,
			why: why,
			funnel: counts,
			funnel_line: funnelLine,
			status_line: panel.status_line || verdict.status_line || discoveryStatusLine(t, diagnostics),
			subtitle:
				panel.subtitle ||
				verdict.subtitle ||
				"Research funnel only. Names go to Playbook review only after strict filters pass.",
			brief_expired_note: panel.brief_expired_note || verdict.brief_expired_note || "",
			best_action: bestAction,
			shortlist: (funnel.review_shortlist || []).slice(0, 10),
			hide_raw_hits: !!(funnel.hide_raw_hits || verdict.hide_raw_hits),
			strict_passed_count: strict,
			raw_hits: funnel.raw_hits || [],
		}
	}

	function discoveryRowLabels(mode) {
		var research = String(mode || "research_only") === "research_only"
		return {
			action: research ? "research hit" : "review",
			monitor: "Create monitor rule",
			dossier: "Review Dossier",
			playbook: "Send to Playbook Review",
			watch_disabled: "shortlist only",
		}
	}

	function discoveryScoreDisplay(score) {
		var n = Number(score)
		if (!Number.isFinite(n) || n < 0 || n > 10) {
			return "Signal quality: Low · Excluded"
		}
		if (n >= 7.5) return "Signal quality: High"
		if (n >= 6) return "Signal quality: Medium"
		return "Signal quality: Low"
	}

	function discoveryConfidenceDisplay(conf, calibration) {
		var sample =
			calibration && calibration.sample_size != null ? Number(calibration.sample_size) : Number(calibration)
		var hasCal = Number.isFinite(sample) && sample >= 30
		if (!hasCal) return "Confidence: heuristic · Calibration: insufficient"
		var val = Number(conf)
		if (!Number.isFinite(val) || val <= 0) {
			return "Confidence: heuristic · Calibration: insufficient"
		}
		var pct = val <= 1 ? Math.round(val * 100) : Math.round(val)
		return "Confidence: " + pct + "% · Calibration: sufficient"
	}

	var DOSSIER_MISSING_ZH = {
		quote: "即時報價",
		technicals: "技術面模組",
		peers: "同業比較",
		options: "期權鏈",
		catalysts: "催化劑",
		risk: "風險模組",
		"Playbook deploy permission": "Playbook 部署權限",
	}

	var DOSSIER_ACTION_ZH = {
		retry: "重試即時擷取",
		"load core": "載入核心模組",
		"open Playbook": "開啟 Playbook 複核",
		"no trade plan": "不可建立交易計劃",
		"no paper draft": "不可紙上模擬",
		"no sizing": "不可定倉",
		"no handoff": "不可交接 IBKR",
		"retry live fetch": "重試即時擷取",
		"review structure and open Playbook when deploy-qualified": "複核結構，合格後再開 Playbook",
	}

	function dossierMissingDataLabels(missing) {
		return (missing || []).map(function (item) {
			var key = String(item || "").trim()
			return DOSSIER_MISSING_ZH[key] || key
		})
	}

	function localizeDossierActions(items) {
		return (items || []).map(function (item) {
			var key = String(item || "").trim()
			var zh = DOSSIER_ACTION_ZH[key]
			return zh ? bilingualLine(zh, key) : key
		})
	}

	function localizeDossierWhy(why) {
		var raw = String(why || "").trim()
		if (!raw) return raw
		return raw
			.split(/\s*·\s*/)
			.map(function (part) {
				var p = String(part || "").trim()
				if (p === "live quote unavailable") {
					return bilingualLine("等待即時報價 — 請按「重試」或先開啟 Playbook", p)
				}
				if (p === "no brief row") return bilingualLine("缺少簡報列", p)
				if (p === "backend loading") return bilingualLine("後端載入中", p)
				if (p === "instant-degraded") return bilingualLine("即時面已降級", p)
				if (p === "Live dossier incomplete") {
					return bilingualLine("live 檔案不完整 — 僅供結構確認", p)
				}
				return p
			})
			.join(" · ")
	}

	function localizeDossierNow(now, mode, sym, label) {
		var raw = String(now || "").trim()
		if (raw.indexOf("Structure unavailable") >= 0) {
			return sym ? sym + " · 結構不可用 · Structure unavailable" : "結構不可用 · Structure unavailable"
		}
		if (raw.indexOf("Loading") >= 0) {
			return sym ? sym + " · 載入中 · Loading" : "載入中 · Loading dossier"
		}
		if (mode === "structure_review_only" || raw.indexOf("CONFIRM ONLY") >= 0) {
			return sym ? sym + " · Confirm-only · 僅結構確認" : "Confirm-only · 僅結構確認"
		}
		return raw
	}

	function localizeDossierOperatorBlock(block, mode) {
		var b = block || {}
		var sym = String(b.ticker || "").toUpperCase()
		return {
			now: localizeDossierNow(b.now, mode, sym, b.unified_label),
			why: localizeDossierWhy(b.why),
			allowed: localizeDossierActions(b.allowed),
			blocked: localizeDossierActions(b.blocked),
			missing_data: dossierMissingDataLabels(b.missing_data),
			next: localizeOperatorNext(b.next || "retry live fetch"),
		}
	}

	function dossierConfirmOnlyFourBlocks(opts) {
		var o = opts || {}
		var exists = []
		if (o.symbol) exists.push(String(o.symbol).toUpperCase() + " 研究檔已載入")
		if (o.hasIntel) exists.push("核心研究模組")
		if (o.hasQuote) exists.push("報價快照")
		if (o.pageSummary) exists.push("頁面摘要")
		var missing = []
		if (!o.hasQuote) missing.push("即時報價")
		if (o.partial) missing.push("部分模組")
		if (o.pending) missing.push("待校準信心度")
		if (o.rrUnavailable) missing.push("R:R 未確認")
		if (!missing.length && o.confirmOnly) missing.push("需 live fetch 才可複核")
		var blockers = []
		if (o.confirmOnly) blockers.push("Confirm-only · 僅結構確認，不可下單")
		if (o.boardWait) blockers.push("Dashboard WAIT · 無部署權限")
		if (o.brokerOffline) blockers.push("IBKR 未就緒 · 不可交接")
		if (o.failedFetch) blockers.push("擷取失敗 · 僅快取研究")
		if (!blockers.length) blockers.push("研究面 · 非交易觸發")
		var safe = []
		safe.push("閱讀研究檔與升級條件")
		safe.push("回 Dashboard 確認體制")
		if (o.hasCached) safe.push("可用快取檔（仍為 confirm-only）")
		safe.push(AUTHORITY_COPY.playbook_review)
		return {
			exists: exists.length ? exists.join(" · ") : "—",
			missing: missing.length ? missing.join(" · ") : "—",
			blocker: blockers.join(" · "),
			safe: safe.join(" · "),
		}
	}

	function ibkrRepairChecklistSteps() {
		return [
			{ key: "ibapi", label: "安裝 ibapi · Install ibapi", detail: "pip install ibapi in API venv" },
			{
				key: "tws",
				label: "開啟 TWS/Gateway · Open TWS/Gateway",
				detail: "Log in — paper 7497 / live 4001",
			},
			{
				key: "socket",
				label: "啟用 API socket · Enable API socket",
				detail: "TWS → API → Enable ActiveX and Socket Clients",
			},
			{
				key: "host",
				label: "驗證 host/port · Verify host/port",
				detail: "127.0.0.1 or host.docker.internal",
			},
			{ key: "connect", label: "連線 · Connect", detail: "IBKR tab → Connect when port open" },
			{
				key: "verify",
				label: "驗證帳戶/持倉/訂單 · Verify account/positions/orders",
				detail: "Refresh account + positions after connect",
			},
			{
				key: "bracket",
				label: "Bracket/交接就緒 · Bracket handoff ready",
				detail: "Readiness critical rows all READY",
			},
		]
	}

	function ibkrBuildRepairChecklistState(ibkr) {
		var ib = ibkr || {}
		var health = ib.health || {}
		var diag = ib.diagnostics || {}
		var read = ib.readiness || {}
		var crit = {}
		var rows = read.critical_rows || []
		for (var i = 0; i < rows.length; i++) {
			if (rows[i] && rows[i].key) crit[rows[i].key] = rows[i].state
		}
		var hasIbapi = ib.ibapi_available !== false && diag.ibapi_available !== false
		if (ib.ibapi_available === false || diag.ibapi_available === false) hasIbapi = false
		else if (ib.ibapi_available === true || diag.ibapi_available === true) hasIbapi = true
		var gw = !!(ib.gateway_reachable || diag.gateway_reachable || ib.gw)
		var apiPortOpen = !!(ib.api_port_open || diag.api_port_open)
		var connected = !!(ib.connected || ib.session_usable)
		var accountLoaded =
			!!ib.account_loaded ||
			crit.account === "ready" ||
			health.account_status === "ok" ||
			!!(ib.account && (ib.account.account || ib.account.net_liquidation != null))
		var positionsLoaded =
			crit.positions === "ready" || (Array.isArray(ib.positions) && ib.positions.length > 0 && connected)
		var bracketReady =
			!!read.full_handoff_ready || read.bracket_status === "ready" || health.handoff_status === "ready"
		return {
			hasIbapi: hasIbapi,
			gw: gw,
			apiPortOpen: apiPortOpen,
			hostConfigured: !!(ib.host || diag.host),
			connected: connected,
			accountLoaded: accountLoaded,
			positionsLoaded: positionsLoaded,
			bracketReady: bracketReady,
			sessionStatus: String(health.session_status || diag.session_status || ""),
		}
	}

	function ibkrRepairChecklistState(stepKey, ibkrState) {
		var st = ibkrState || {}
		var key = String(stepKey || "")
		if (key === "ibapi") {
			return st.hasIbapi === false ? "pending" : st.hasIbapi ? "done" : "unknown"
		}
		if (key === "tws") return st.gw || st.apiPortOpen ? "done" : "pending"
		if (key === "socket") {
			if (st.apiPortOpen) return "done"
			if (st.gw || st.sessionStatus === "connected") return "pending"
			return "pending"
		}
		if (key === "host") return st.hostConfigured ? "done" : "pending"
		if (key === "connect") return st.connected ? "done" : st.gw || st.apiPortOpen ? "pending" : "pending"
		if (key === "verify") {
			if (st.accountLoaded && st.positionsLoaded) return "done"
			if (st.accountLoaded || st.connected) return "pending"
			return "pending"
		}
		if (key === "bracket") {
			return st.bracketReady ? "done" : st.connected ? "pending" : "pending"
		}
		return "unknown"
	}

	function signalFamilyHealthLine(payload) {
		var p = payload || {}
		var sample = Number(p.sample_size != null ? p.sample_size : p.total_trades)
		var hit = p.hit_rate != null ? p.hit_rate : p.win_rate
		if (!isFinite(sample) || sample < 1) {
			return "Uncalibrated · heuristic only"
		}
		var hitPct =
			hit != null && isFinite(Number(hit)) ? (Number(hit) * (Number(hit) <= 1 ? 100 : 1)).toFixed(0) + "%" : "—"
		return "n=" + sample + " · hit " + hitPct + " (read-only scaffold)"
	}

	/** PM strip / trust strip chip tiers — primary authority first, context second. */
	function partitionHeaderChips(chips, opts) {
		var o = opts || {}
		var primary = []
		var secondary = []
		var infra = []
		var blockedAuthority =
			!!o.authorityChip && /^(MONITOR ONLY|INSTANT DEGRADED|AUTHORITY BLOCKED)$/i.test(String(o.authorityChip))
		if (o.authorityChip) {
			primary.push({ label: o.authorityChip, class: "authority", tier: "primary" })
		}
		if (o.tradeability) {
			var tb = String(o.tradeability)
			if (blockedAuthority) {
				secondary.push({ label: tb, class: "tradeability", tier: "secondary" })
			} else {
				primary.push({ label: tb, class: "tradeability", tier: "primary" })
			}
		}
		if (o.fetchBadge) {
			infra.push({ label: String(o.fetchBadge), class: "fetch", tier: "infra" })
		}
		if (o.ibkrChip) {
			infra.push({ label: String(o.ibkrChip), class: "ibkr", tier: "infra" })
		}
		if (o.typedFreshnessChip) {
			primary.push({ label: String(o.typedFreshnessChip), class: "freshness", tier: "primary" })
		} else if (o.freshnessChip) {
			secondary.push({ label: String(o.freshnessChip), class: "freshness", tier: "secondary" })
		}
		if (o.dataChip && !o.typedFreshnessChip) {
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
		return { primary: primary, secondary: secondary, infra: infra }
	}

	/** One-time recovery hint after route abort — research shell only, no authority. */
	function routeAbortRecoveryHint(surface) {
		var s = String(surface || "").toLowerCase()
		if (s === "dossier" || s === "dossier_research") {
			return "Route failed — retry Load core only; CONFIRM ONLY until live dossier returns"
		}
		if (s === "discovery" || s === "scanners") {
			return "Scanner route failed — retry Run Scanners; fallback funnel is not deploy authority"
		}
		return "Fetch failed — retry when badges clear; monitor queue and Guide remain safe"
	}

	/** Market strip stale — refresh before sizing (copy-only). */
	function staleRefreshRecoveryLine() {
		return "Market snapshot stale — refresh market data before using levels for sizing"
	}

	/** Engine off — no new cycle authority (copy-only). */
	function engineOffRecoveryLine() {
		return "Engine OFF — start engine in Ops or set CC_AUTO_START_ENGINE=1; board may be precomputed only"
	}

	/** IBKR recovery copy — aligned with ibkr_diagnosis short codes (not deploy gate). */
	function ibkrLoginToReadyHint(state) {
		var st = state || {}
		var short = String(st.short || "").toUpperCase()
		var hint = String(st.hint || "").trim()
		if (short === "OFFLINE" || short === "NO IBAPI" || short === "API OFF" || st.level === "offline") {
			return hint || "IBKR OFFLINE — start Gateway/TWS and confirm API port; Connect on IBKR tab when reachable"
		}
		if (short === "BLOCKED") {
			return "IBKR BLOCKED — circuit breaker active; clear risk gate before handoff"
		}
		if (short === "READY" || st.handoff || st.level === "ready") {
			return hint || "IBKR READY — handoff path verified; confirm bracket alignment before transmit"
		}
		if (short === "LOGIN" || short === "HANDSHAKE" || (st.gw && !st.connected)) {
			return hint || "IBKR LOGIN — connect session on IBKR tab; READY required before handoff (bracket aligned)"
		}
		if (short === "MONITOR" || short === "PARTIAL" || st.level === "partial") {
			return hint || "IBKR partial — session up; confirm bracket and portfolio sync before handoff"
		}
		return hint || "IBKR OFFLINE — start Gateway/TWS; Connect on IBKR tab when API port is reachable"
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
			return ""
		}
		if (!o.ibkrReady) {
			return "Blocked: IBKR handoff · Safe: dossier core-only · monitor queue"
		}
		if (!o.engineRunning) {
			return "Blocked: new cycle sizing · Safe: Guide · monitors until runtime live"
		}
		return ""
	}

	/** Staging soak anchors — mirrors fetch_surface_state.soak_confirmation_signals(). */
	function sanitizeOperatorDetail(detail) {
		var s = String(detail || "").trim()
		if (!s) return ""
		if (s.length > 120) s = s.slice(0, 117) + "..."
		if (/traceback|exception|error:|file "|\.py"|line \d+/i.test(s)) {
			return "See Ops diagnostics"
		}
		return s
	}

	function soakConfirmationSelectors() {
		return {
			instantDegraded: '[data-cc="instant-degraded-banner"]',
			warmupStrip: '[data-cc="warmup-context-strip"]',
			deployStrip: '[data-cc="deploy-status-strip"]',
			missionPanel: '[data-cc="today-mission-panel"]',
			playbookSurface: '[data-cc="playbook-surface"]',
			playbookAuthorityStrip: '[data-cc="playbook-authority-strip"]',
			discoverySurface: '[data-cc="discovery-surface"]',
			dossierConfirmOnlyBlocks: '[data-cc="dossier-confirm-only-blocks"]',
			ibkrRepairChecklist: '[data-cc="ibkr-repair-checklist"]',
			playbookCostRankPill: '[data-cc="playbook-cost-rank-pill"]',
			playbookStrategyDecayLine: '[data-cc="playbook-strategy-decay-line"]',
			execAnalyticsSample: '[data-cc="exec-analytics-sample"]',
			execAnalyticsConsole: '[data-cc="exec-analytics-console"]',
			trackerWaveStrip: '[data-cc="tracker-wave-strip"]',
			ccOsConsole: '[data-cc="cc-os-console"]',
			ccOsRegimeStrip: '[data-cc="cc-os-regime-strip"]',
			ccOsPipelineStrip: '[data-cc="cc-os-pipeline-strip"]',
			ccOsPortfolioStrip: '[data-cc="cc-os-portfolio-strip"]',
			ccOsCurveStrip: '[data-cc="cc-os-curve-strip"]',
			ccOsEventStrip: '[data-cc="cc-os-event-strip"]',
			playbookOpportunityQualityPill: '[data-cc="playbook-opportunity-quality-pill"]',
			researchStalenessAlert: '[data-cc="research-staleness-alert"]',
			monitorUpgradeAlerts: '[data-cc="monitor-upgrade-alerts"]',
			dailyOperatorBriefing: '[data-cc="daily-operator-briefing"]',
			regimeStackStrip: '[data-cc="regime-stack-strip"]',
			aiReasonCodes: '[data-cc="ai-reason-codes"]',
			marketStale: '[data-cc="market-strip-stale"]',
			opsRunbook: '[data-cc="ops-recovery-runbook"]',
			exportReviewPdf: '[data-cc="export-review-pdf"]',
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

	var DOSSIER_CONFIRM_ONLY_SIZING = "Confirm-only 不定倉 · No sizing guidance in confirm-only mode"

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
		if (r === "failed" || r === "partial") return "Sizing blocked until live dossier loads"
		if (r === "rr_unavailable") return "Size unavailable — R:R not confirmed"
		return "Size unavailable"
	}

	function dossierTradePlanNote(opts) {
		var o = opts || {}
		var note = String(o.note || o.setup_type || "").trim()
		var researchOnly = !!o.research_only
		var levelsBlank = !!o.levels_blank
		if (researchOnly && levelsBlank) {
			return "Live structure unavailable — structure review only"
		}
		if (levelsBlank) return "Live structure unavailable"
		if (note) return note
		return "Structure-based reference"
	}

	var DOSSIER_CONFIRM_ONLY_STRIP = "Confirm-only · 僅結構確認：無入場價、無止損、無倉位 · no sizing · no handoff"
	var DOSSIER_PAPER_DRAFT_DISABLED =
		"Paper draft disabled · 紙上模擬已關閉 — 需 live Dossier + Playbook 確認後才可模擬"
	var DOSSIER_MONITOR_RULE_BUTTON = "Create monitor rule · 建立監察規則"
	var DOSSIER_MONITOR_RULE_HINT = "Alert only · 僅提醒 — 不定倉、不交接券商 · no sizing · no handoff"
	var DOSSIER_LAGGED_CONTEXT_NOTE =
		"Lagged / illustrative context · 滯後參考，不用於結構確認 · not used for confirmation"
	var DOSSIER_STRUCTURE_SNAPSHOT_TITLE = "Structure snapshot · 結構快照"

	var DOSSIER_STRUCTURE_LABELS = {
		entry: ["Reference level · 參考價位", "Entry zone"],
		stop: ["Risk reference · 風險參考", "Stop"],
		target: ["Upside references · 上行參考", "T1 / T2"],
		rr: ["R:R", "R:R"],
		size: ["Sizing", "Size @1%"],
	}

	function resolveDossierMode(opts) {
		var o = opts || {}
		if (o.mode_key) return String(o.mode_key)
		if (o.failed_fetch && !o.has_quote) return "unavailable"
		if (o.load_phase === "core" || o.loading) return "loading"
		var label = String(o.unified_label || "").toUpperCase()
		var confirmLabels = ["CONFIRM ONLY", "RESEARCH ONLY", "REFERENCE ONLY", "WATCH ONLY", "PASS"]
		var confirmOnly =
			confirmLabels.indexOf(label) >= 0 ||
			!!o.research_only ||
			!!o.instant_degraded ||
			!!o.brief_backed ||
			!!o.pending_calibration ||
			!!o.rr_unavailable ||
			!o.has_quote
		if (!o.has_quote && (o.instant_degraded || !o.brief_backed || o.partial)) {
			return "unavailable"
		}
		if (confirmOnly) return "structure_review_only"
		if (o.partial) return "loading"
		return "usable"
	}

	function dossierRecoveryMode(mode) {
		var m = String(mode || "")
		return m === "structure_review_only" || m === "loading" || m === "unavailable"
	}

	function dossierUsableMode(mode) {
		return String(mode || "") === "usable"
	}

	function dossierOperatorBlock(mode, payload) {
		var p = payload || {}
		var block = p.dossier_operator_block
		if (block && block.now) return localizeDossierOperatorBlock(block, mode)
		var dm = p.dossier_mode || {}
		if (dm.dossier_operator_block && dm.dossier_operator_block.now) {
			return localizeDossierOperatorBlock(dm.dossier_operator_block, mode)
		}
		var sym = String(p.ticker || p.symbol || "").toUpperCase()
		var m = String(mode || resolveDossierMode(p))
		var now =
			m === "unavailable"
				? sym
					? sym + " · Structure unavailable"
					: "Structure unavailable"
				: m === "loading"
					? sym
						? sym + " · Loading"
						: "Loading dossier"
					: sym
						? sym + " · " + String(p.unified_label || "CONFIRM ONLY")
						: "CONFIRM ONLY"
		var why = []
		if (!p.has_quote) why.push("live quote unavailable")
		if (!p.brief_backed) why.push("no brief row")
		if (m === "loading") why.push("backend loading")
		var block = {
			now: now,
			why: why.length ? why.join(" · ") : "Live dossier incomplete",
			allowed: ["retry", "load core", "open Playbook"],
			blocked: ["no trade plan", "no paper draft", "no sizing", "no handoff"],
			missing_data: dm.missing_data || [],
			next: "retry live fetch",
		}
		return localizeDossierOperatorBlock(block, m)
	}

	function dossierTradePlanVisible(opts) {
		var o = opts || {}
		return resolveDossierMode(o) === "usable" && !!o.playbook_watch_plus && !o.deploy_blocked && !!o.broker_online
	}

	function dossierEvidenceStatus(payload) {
		var p = payload || {}
		var es = p.evidence_status
		if (es && es.show != null) return es
		var dm = p.dossier_mode || {}
		if (dm.evidence_status) return dm.evidence_status
		var mode = resolveDossierMode(p)
		var review = dossierRecoveryMode(mode)
		return {
			show: review || !p.has_quote || !p.has_narrative,
			headline: !p.has_quote ? "Structure unavailable" : "Evidence incomplete",
			evidence_quality: review ? "Low" : "—",
			calibration: review ? "Pending" : "—",
			use_allowed: review ? "structure review only" : "live confirmation",
			reason: "Live modules missing — no deploy authority",
			modules_missing: review || !p.has_narrative,
		}
	}

	function dossierStructureReviewOnly(mode) {
		return String(mode || "") === "structure_review_only"
	}

	function dossierConfirmOnlyStrip() {
		return DOSSIER_CONFIRM_ONLY_STRIP
	}

	function dossierStructureSnapshotTitle() {
		return DOSSIER_STRUCTURE_SNAPSHOT_TITLE
	}

	function dossierStructureLevelLabel(field, mode) {
		var review = dossierStructureReviewOnly(mode)
		var pair = DOSSIER_STRUCTURE_LABELS[field] || [field, field]
		return review ? pair[0] : pair[1]
	}

	function dossierPaperDraftDisabledCopy() {
		return DOSSIER_PAPER_DRAFT_DISABLED
	}

	function dossierMonitorRuleButton() {
		return DOSSIER_MONITOR_RULE_BUTTON
	}

	function dossierMonitorRuleHint() {
		return DOSSIER_MONITOR_RULE_HINT
	}

	function dossierLaggedContextNote() {
		return DOSSIER_LAGGED_CONTEXT_NOTE
	}

	function dossierPaperDraftVisible(opts) {
		var o = opts || {}
		var mode = resolveDossierMode(o)
		if (o.paper_deploy_available && mode !== "unavailable") return true
		return mode === "usable" && !!o.playbook_watch_plus && !o.deploy_blocked && !!o.broker_online
	}

	function dossierStructureSnapshotRows(opts) {
		var o = opts || {}
		var mode = resolveDossierMode(o)
		var review = dossierStructureReviewOnly(mode)
		var ez = o.entry_zone
		var fmt = function (v) {
			return v != null && v !== "" ? "$" + v : "—"
		}
		var entry = ez && ez.length >= 2 ? "$" + ez[0] + "–$" + ez[1] : "—"
		var rows = [
			{ label: dossierStructureLevelLabel("entry", mode), value: entry },
			{ label: dossierStructureLevelLabel("stop", mode), value: fmt(o.stop) },
			{
				label: dossierStructureLevelLabel("target", mode),
				value: o.target_1r ? "$" + o.target_1r + " / $" + o.target_2r : "—",
			},
		]
		if (!review || o.live_validated) {
			rows.push({
				label: dossierStructureLevelLabel("rr", mode),
				value: String(o.rr_display || "—"),
			})
		}
		if (review) {
			if (o.source) rows.push({ label: "Source", value: String(o.source) })
			if (o.freshness) rows.push({ label: "Freshness", value: String(o.freshness) })
			rows.push({ label: "Use", value: "Use: structure review only" })
		}
		return rows
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

	function execAnalyticsConsoleLine(analytics) {
		var a = analytics || {}
		var n = a.orders_sampled != null ? a.orders_sampled : 0
		var sample = String(a.sample_state || "").trim()
		var slip = a.slippage && a.slippage.median_bps != null ? a.slippage.median_bps + " bps slip" : ""
		var fill = a.fill_quality && a.fill_quality.status ? a.fill_quality.status : ""
		if (a.degraded || sample === "insufficient_sample" || sample === "stub_sample") {
			return (
				"Execution console: " +
				(n ? "n=" + n + " " : "") +
				(sample === "stub_sample" ? "MOCK/DEGRADED stub" : "insufficient sample") +
				" — ops context only"
			)
		}
		if (sample === "live_sample") {
			return (
				"Execution console: live n=" +
				n +
				(slip ? " · " + slip : "") +
				(fill ? " · " + fill : "") +
				" — not broker-ready claim"
			)
		}
		return execAnalyticsSample(a)
	}

	function trackerWaveStripLine(wave) {
		var w = wave || {}
		var tier1 = w.tier1 || w
		var line = String(tier1.strip_line || "").trim()
		if (!line) line = "Tracker wave — monitor support"
		if (w.degraded || tier1.degraded) line = "MOCK/DEGRADED · " + line
		return line + " — not deploy authority"
	}

	function opportunityQualityPill(row) {
		var q = (row || {}).opportunity_quality || {}
		var score = q.quality_score != null ? q.quality_score : row.quality_score
		if (score == null) return ""
		var flags = q.quality_flags || []
		var suffix = flags.length ? " · " + flags.join(",") : ""
		return "Q" + score + suffix + " — rank hint only"
	}

	function opportunityQualityPillClass(row) {
		var q = (row || {}).opportunity_quality || {}
		var flags = q.quality_flags || []
		if (flags.indexOf("event_blocker") >= 0 || flags.indexOf("false_breakout") >= 0) return "pr"
		if (flags.indexOf("cost_drag") >= 0 || flags.indexOf("stale_setup") >= 0) return "pa"
		var score = q.quality_score != null ? q.quality_score : row.quality_score
		if (score != null && score >= 7) return "pg"
		return "pw"
	}

	function ccOsCurveLine(curve) {
		var c = curve || {}
		var line = String(c.strip_line || "").trim()
		if (c.live_strategy_health) line = "Live ledger · " + line
		if (c.degraded && line.indexOf("MOCK") < 0) line = "MOCK/DEGRADED · " + line
		return line || "Curve governance — research only"
	}

	function ccOsEventLine(eventIntel) {
		var e = eventIntel || {}
		var line = String(e.strip_line || "").trim()
		return (line || "Event intel — downgrade/context only") + " — not deploy"
	}

	function ccOsOperatorStrip(os, wave) {
		var o = os || {}
		var line = String(o.operator_strip || "").trim()
		if (!line && wave && wave.tier1) {
			line = String(wave.tier1.strip_line || wave.strip_line || "").trim()
		}
		if (!line) return "CC OS idle — monitor support only"
		if (o.degraded && line.indexOf("MOCK") < 0) line = "MOCK/DEGRADED · " + line
		return line
	}

	function ccOsRegimeLine(regime) {
		var r = regime || {}
		var line = String(r.strip_line || "").trim()
		return line || "Regime stack unavailable — filter only"
	}

	function ccOsPipelineLine(pipeline) {
		var p = pipeline || {}
		return String(p.label || "Pipeline unknown") + " — not deploy authority"
	}

	function ccOsCapitalLine(capital, sizing) {
		var c = capital || {}
		if (c.strip_line) return String(c.strip_line)
		return drawdownSizingLine(sizing)
	}

	function ccOsExecutionLine(execMod, analytics) {
		var e = execMod || {}
		if (e.strip_line) return String(e.strip_line)
		return execAnalyticsConsoleLine(analytics)
	}

	function ccOsPortfolioLine(portfolio) {
		var p = portfolio || {}
		return String(p.strip_line || "Portfolio intel unavailable") + ""
	}

	function dailyBriefingLine(briefing) {
		var b = briefing || {}
		var one = String(b.one_liner || "").trim()
		if (!one && b.sections && b.sections[1] && b.sections[1].lines && b.sections[1].lines[0]) {
			one = b.sections[1].lines[0]
		}
		if (!one) return "Daily briefing — triage only, not board decision"
		if (b.degraded && one.indexOf("MOCK") < 0) one = one + " — degraded"
		return "Briefing: " + one + " — operator workflow support"
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
			return bilingualLine(
				"現可：查看監察清單、Guide 檢查表、Dossier 核心模組 — 等 /health mode=full 後才可定倉或交接 IBKR",
				"Safe now: monitor queue, Guide checklist, dossier core-only — wait for backend import + /health mode=full before sizing or IBKR handoff",
			)
		}
		if (o.fetchFailed || o.instantDegraded) {
			return bilingualLine(
				"現可：Guide、監察、Dossier 核心 — 等 fetch 徽章恢復；備援不可部署",
				"Safe now: Guide, monitors, dossier core-only — retry when fetch badges clear; no deploy from fallback",
			)
		}
		if (o.waitDay) {
			return bilingualLine(
				"現可：升級監察清單 · Discovery · Playbook 排名",
				"Safe now: upgrade-watch queue · Discovery · Playbook ranking",
			)
		}
		return ""
	}

	function tradeabilityGuidanceLine(opts) {
		var o = opts || {}
		if (o.blocked) {
			return bilingualLine(
				"禁止部署 — PILOT/WATCH 標籤僅供審閱",
				"PILOT/WATCH labels are review-only — deploy blocked.",
			)
		}
		var tb = String(o.tradeability || "WAIT").toUpperCase()
		if (tb === "STRONG_TRADE") {
			return bilingualLine(
				"多筆可執行 — 僅 A 級且 bracket 就緒才可滿倉",
				"Multiple execution-ready names — full size only on A-grade with brackets.",
			)
		}
		if (tb === "TRADE") {
			return bilingualLine(
				"至少一筆可執行 — 標準 1R 定倉",
				"At least one execution-ready setup — standard 1R sizing.",
			)
		}
		if (tb === "SELECTIVE") {
			if (o.pilotBlocked) {
				return bilingualLine(
					"候選審閱：選擇性（僅供觀察，不可部署）— 門檻未清前不可試單",
					"SELECTIVE review only — monitor candidates; no pilot sizing until gates clear.",
				)
			}
			return bilingualLine(
				"僅試單或單一標的 — 半倉，必須設止損",
				"Pilot or single-name only — half size, stop required.",
			)
		}
		if (tb === "WAIT") {
			return bilingualLine(
				"無部署級看板 — 耐心即是決策",
				"No deploy-grade board — patience is the active decision.",
			)
		}
		return bilingualLine("風險關閉 — 禁止新倉", "Risk-off — no new entries.")
	}

	function dashboardWaitTopComment(opts) {
		var o = opts || {}
		if (o.compact) {
			return o.brokerOffline
				? "WAIT · 僅監察，勿強行部署；IBKR 離線 · monitor, don't force"
				: "WAIT · 僅監察，勿強行部署 · monitor, don't force"
		}
		var s =
			"WAIT · 今日不可滿倉部署。看板有監察級標的，但尚未通過 thesis + 時機 + R:R + 執行全堆疊。" +
			"今日任務是監察，不是強行入場。"
		if (o.brokerOffline) {
			s += " IBKR 離線，執行不可用，無標的取得部署權限。"
		} else {
			s += " 尚無標的取得部署權限。"
		}
		return s
	}

	function playbookCardGateLine(status, detail) {
		var su = String(status || "WATCH")
			.toUpperCase()
			.replace(/[^A-Z0-9]+/g, " ")
			.trim()
		var d = String(detail || "").trim()
		if (!d) {
			if (su === "BLOCKED") return bilingualLine("禁止部署 — 門檻未齊", "Deploy blocked — gates incomplete")
			if (su === "AVOID" || su === "NO TRADE") return bilingualLine("避免 — 不可部署", "Avoid — not deploy-ready")
			return String(status || "WATCH").replace(/_/g, " ") + " — " + bilingualLine("僅監察", "monitor only")
		}
		d = d.replace(/^(AVOID|BLOCKED|WATCH|NO_TRADE|PILOT|FALLBACK WATCH)\s*[·\-\—:\u2014]\s*/i, "").trim()
		if (su === "BLOCKED") return bilingualLine("禁止部署 — " + d, "Deploy blocked — " + d)
		if (su === "AVOID" || su === "NO TRADE") return bilingualLine("避免 — " + d, "Avoid — " + d)
		return String(status || "WATCH").replace(/_/g, " ") + " — " + d
	}

	var HEADER_SURFACE_ZH = {
		"Monitor only": "僅監察",
		"Deploy blocked": "禁止部署",
		"Research only": "僅研究",
		Loading: "載入中",
		"Degraded board": "看板已降級",
		"Fallback board": "備援看板",
	}

	function localizeHeaderLine(line) {
		var raw = String(line || "").trim()
		if (!raw) return raw
		var zh = HEADER_SURFACE_ZH[raw]
		return zh ? bilingualLine(zh, raw) : raw
	}

	function localizeHeaderSurface(copy) {
		var c = copy || {}
		return {
			surface_mode: c.surface_mode,
			badge: c.badge,
			title: localizeHeaderLine(c.title),
			subtitle: localizeHeaderLine(c.subtitle),
			explanation: localizeHeaderLine(c.explanation),
			next_action: localizeHeaderLine(c.next_action),
			fetch_state: c.fetch_state,
			show_decision_chips: c.show_decision_chips,
			show_regime_strip: c.show_regime_strip,
			chips: c.chips,
			authority_badge: c.authority_badge,
		}
	}

	var FETCH_STATE_ZH = {
		"API still loading": "API 載入中",
		failed_fetch: "擷取失敗",
		stale: "資料過期",
		loading: "載入中",
	}

	function localizeFetchStateCopy(copy) {
		var c = copy || {}
		var out = {}
		for (var k in c) out[k] = c[k]
		var exp = String(c.explanation || "").trim()
		if (!exp) return out
		for (var key in FETCH_STATE_ZH) {
			if (exp.indexOf(key) >= 0) {
				out.explanation = bilingualLine(FETCH_STATE_ZH[key], exp)
				return out
			}
		}
		return out
	}

	function exportAllLabel(busy) {
		return busy ? bilingualLine("匯出中…", "Exporting…") : bilingualLine("一鍵匯出全介面", "Export All Pages")
	}

	function operatorBlockChromeLabel(key) {
		var labels = {
			now: bilingualLine("現在", "Now"),
			why: bilingualLine("原因", "Why"),
			allowed: bilingualLine("允許", "Allowed"),
			blocked: bilingualLine("禁止", "Blocked"),
			valid: bilingualLine("有效候選", "Valid"),
			next: bilingualLine("下一步", "Next"),
		}
		return labels[String(key || "").toLowerCase()] || String(key || "")
	}

	function dashboardLoadingHeadline() {
		return bilingualLine("載入看板中", "Loading dashboard…")
	}

	function dashboardLoadingHint() {
		return bilingualLine("快取快照會先顯示", "cached snapshot shown when available")
	}

	function surfaceEmptyStateCopy(kind) {
		return { headline: "", detail: "", badge: kind || "", cta: "" }
	}

	var WORKSTATION_PANEL_TITLES = {
		quote: "Quote",
		chart: "Chart",
		performance: "Performance vs SPY",
		options: "Options chain",
		intel: "Intel overlay",
		regime: "Regime context",
	}

	function workstationPanelKey(key) {
		return String(key || "")
			.replace(/^\d+_/, "")
			.replace(/_/g, " ")
	}

	function workstationPanelTitle(key) {
		var k = workstationPanelKey(key)
		return WORKSTATION_PANEL_TITLES[k] || k
	}

	function workstationPanelStateLabel(panel) {
		var p = panel || {}
		if (p.error || p.partial) return "partial"
		if (p.quote_pending || p.quote_unavailable) return "unavailable"
		var has =
			p.quote ||
			p.price != null ||
			p.last != null ||
			p.decision_bar ||
			p.unified_decision ||
			p.label ||
			p.summary ||
			p.calls ||
			p.puts ||
			(p.candles && p.candles.length)
		if (!has) return "unavailable"
		return "loaded"
	}

	function workstationPanelNextAction(panel, key) {
		var k = workstationPanelKey(key)
		if (k === "chart") return "Retry live chart when API recovers — or use dossier chart tab."
		if (k === "options") return "Options panel unavailable — no live chain loaded."
		if (k === "intel") return "Intel module partial — lagged context only."
		if (k === "performance") return "Performance loaded from cached source — confirm freshness."
		if (k === "quote") return "Quote unavailable — retry Load workstation."
		if (k === "regime") return "Regime context partial — board gate stays on Dashboard."
		return "Retry Load workstation or continue with core dossier."
	}

	function workstationPanelErrorLine(panel, key) {
		var p = panel || {}
		var title = workstationPanelTitle(key)
		var msg = String(p.error || "").trim()
		var lower = msg.toLowerCase()
		if (lower.indexOf("unexpected keyword argument") >= 0) {
			return title + " unavailable — retry live chart when API recovers"
		}
		if (lower.indexOf("nonetype") >= 0 && lower.indexOf("has no attribute") >= 0) {
			return title + " unavailable — upstream data not loaded yet"
		}
		if (lower.indexOf("timeout") >= 0 || lower.indexOf("timed out") >= 0) {
			return title + " timed out — retry Load workstation"
		}
		if (lower.indexOf("connection") >= 0 || lower.indexOf("unreachable") >= 0) {
			return title + " unavailable — market data path offline"
		}
		if (msg && lower.indexOf("unavailable") < 0) {
			return title + " unavailable — partial load"
		}
		return msg || title + " unavailable — partial load"
	}

	function workstationPanelEmptyCopy(key) {
		return workstationPanelTitle(key) + " unavailable — no data loaded yet"
	}

	function escapeExportHtml(text) {
		return String(text || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
	}

	function truncateExportText(text, maxLen) {
		var s = String(text || "").trim()
		if (!s) return ""
		var n = Number(maxLen) || 160
		if (s.length <= n) return s
		return s.slice(0, Math.max(0, n - 3)) + "..."
	}

	function exportIssuesList(items) {
		var rows = Array.isArray(items) ? items : []
		if (!rows.length) {
			return '<div class="cc-export-muted">None flagged</div>'
		}
		return (
			"<ul>" +
			rows
				.map(function (item) {
					return "<li>" + escapeExportHtml(truncateExportText(item, 200)) + "</li>"
				})
				.join("") +
			"</ul>"
		)
	}

	function exportErrorLogRows(entries, limit) {
		var list = Array.isArray(entries) ? entries : []
		var max = Number(limit) || 12
		if (!list.length) {
			return '<div class="cc-export-muted">No session errors logged</div>'
		}
		return (
			"<table><thead><tr><th>Severity</th><th>Source</th><th>Message</th><th>Time</th></tr></thead><tbody>" +
			list
				.slice(0, max)
				.map(function (row) {
					var r = row || {}
					return (
						"<tr><td>" +
						escapeExportHtml(r.severity || "—") +
						"</td><td>" +
						escapeExportHtml(truncateExportText(r.source || r.category || "—", 40)) +
						"</td><td>" +
						escapeExportHtml(sanitizeOperatorDetail(r.message || r.detail || r.summary || "—")) +
						'</td><td class="mono">' +
						escapeExportHtml(truncateExportText(r.timestamp || r.ts || r.time || "—", 24)) +
						"</td></tr>"
					)
				})
				.join("") +
			"</tbody></table>"
		)
	}

	function exportProbeRows(rows) {
		var list = Array.isArray(rows) ? rows : []
		var flagged = list.filter(function (row) {
			var r = row || {}
			var probe = String(r.probe || r.label || "").toUpperCase()
			var runtime = String(r.runtime || r.runtime_evidence || r.evidence || "").toUpperCase()
			return probe.indexOf("FAIL") >= 0 || runtime.indexOf("FAIL") >= 0 || runtime.indexOf("UNAVAILABLE") >= 0
		})
		var show = flagged.length ? flagged : list
		if (!show.length) {
			return '<div class="cc-export-muted">No probe/runtime rows available</div>'
		}
		return (
			"<table><thead><tr><th>Component</th><th>Probe</th><th>Runtime</th></tr></thead><tbody>" +
			show
				.slice(0, 8)
				.map(function (row) {
					var r = row || {}
					return (
						"<tr><td>" +
						escapeExportHtml(String(r.name || "—").replace(/_/g, " ")) +
						"</td><td>" +
						escapeExportHtml(r.probe || r.label || "—") +
						"</td><td>" +
						escapeExportHtml(
							truncateExportText(r.runtime || r.runtime_evidence || r.evidence || "—", 120),
						) +
						"</td></tr>"
					)
				})
				.join("") +
			"</tbody></table>"
		)
	}

	/** Page 1 — issues, disconnects, error log summary (no secrets). */
	function buildExportIssuesPage(snapshot) {
		var s = snapshot || {}
		var truth = s.system_truth || s.systemTruth || {}
		var blockers =
			(truth.reason_codes || []).length && typeof systemTruthMissionBlockers === "function"
				? systemTruthMissionBlockers(truth)
				: s.system_blockers || []
		var truthLine =
			typeof systemTruthLine === "function" && Object.keys(truth).length
				? systemTruthLine(truth)
				: String(s.system_truth_line || "")
		var qual =
			s.qualification ||
			(truth.setup_qualified_count != null || truth.deploy_qualified_count != null
				? {
						setup: Number(truth.setup_qualified_count) || 0,
						deploy: Number(truth.deploy_qualified_count) || 0,
						line:
							typeof qualificationCountLine === "function"
								? qualificationCountLine(truth.qualification_levels, s.filter_funnel)
								: "",
					}
				: null)
		var funnel = s.filter_funnel || {}
		var setupCount = qual ? qual.setup : Number(funnel.watch_qualified_setups || funnel.setup_qualified_setups) || 0
		var deployCount = qual
			? qual.deploy
			: Number(funnel.deploy_qualified_setups || funnel.execution_ready_setups) ||
				Number(truth.deploy_qualified_count) ||
				0
		var qualLine =
			(qual && qual.line) ||
			(typeof qualificationCountLine === "function"
				? qualificationCountLine(null, funnel)
				: setupCount + " setup-qualified · " + deployCount + " deploy-qualified")
		var header = s.cc_header || {}
		var disconnects = s.disconnects || {}
		var generated = s.generated_at || new Date().toISOString()

		return (
			'<section class="cc-export-page cc-export-issues" data-cc-export="issues">' +
			"<h1>CC · Issues / errors / disconnect summary</h1>" +
			'<p class="cc-export-meta mono">Generated ' +
			escapeExportHtml(generated) +
			" · review export · not trade authority</p>" +
			"<h2>SystemTruth</h2>" +
			(truthLine ? '<p class="cc-export-lead">' + escapeExportHtml(truthLine) + "</p>" : "") +
			exportIssuesList(blockers) +
			"<h2>cc-header status</h2>" +
			"<table><tbody>" +
			"<tr><th>Freshness</th><td>" +
			escapeExportHtml(header.freshness || s.data_tier || "—") +
			"</td></tr>" +
			"<tr><th>Engine</th><td>" +
			escapeExportHtml(header.engine || (s.engine_running ? "ON" : "OFF")) +
			"</td></tr>" +
			"<tr><th>IBKR</th><td>" +
			escapeExportHtml(header.ibkr || s.ibkr_label || "—") +
			"</td></tr>" +
			"<tr><th>Breaker</th><td>" +
			escapeExportHtml(header.breaker || (s.breaker ? "TRIPPED" : "clear")) +
			"</td></tr>" +
			"<tr><th>API mode</th><td>" +
			escapeExportHtml(header.mode || s.cc_mode || "—") +
			"</td></tr>" +
			"</tbody></table>" +
			"<h2>Disconnect / degraded states</h2>" +
			"<table><tbody>" +
			"<tr><th>IBKR gateway</th><td>" +
			escapeExportHtml(
				disconnects.ibkr_gateway != null ? (disconnects.ibkr_gateway ? "reachable" : "offline") : "—",
			) +
			"</td></tr>" +
			"<tr><th>API health mode</th><td>" +
			escapeExportHtml(disconnects.health_mode || "—") +
			"</td></tr>" +
			"<tr><th>instant_degraded</th><td>" +
			escapeExportHtml(disconnects.instant_degraded ? "yes" : "no") +
			"</td></tr>" +
			"<tr><th>brief-fallback</th><td>" +
			escapeExportHtml(disconnects.brief_fallback ? "yes" : "no") +
			"</td></tr>" +
			"</tbody></table>" +
			"<h2>Error log summary</h2>" +
			'<p class="cc-export-muted">' +
			escapeExportHtml(
				String(s.error_log_total || 0) +
					" buffered · showing last " +
					String((s.error_log || []).length) +
					" entries",
			) +
			"</p>" +
			exportErrorLogRows(s.error_log, s.error_log_limit) +
			"<h2>Ops probe vs runtime (FAIL / UNAVAILABLE)</h2>" +
			exportProbeRows(s.probe_rows) +
			"<h2>Deploy authority &amp; qualification</h2>" +
			"<table><tbody>" +
			"<tr><th>Deploy authority</th><td>" +
			escapeExportHtml(
				truth.deploy_authority === true || s.deploy_authority === true ? "open" : "blocked / monitor only",
			) +
			"</td></tr>" +
			"<tr><th>Setup-qualified</th><td>" +
			escapeExportHtml(String(setupCount)) +
			"</td></tr>" +
			"<tr><th>Deploy-qualified</th><td>" +
			escapeExportHtml(String(deployCount)) +
			"</td></tr>" +
			"<tr><th>Summary</th><td>" +
			escapeExportHtml(qualLine) +
			"</td></tr>" +
			"</tbody></table>" +
			'<footer class="cc-export-footer">Not trade authority — operator review snapshot only. No secrets included.</footer>' +
			"</section>"
		)
	}

	function discoveryExportSummaryBlock(scanner) {
		var hub = scanner || {}
		var data = hub.data || {}
		var verdict = data.discovery_verdict || {}
		var lines = []
		if (verdict.best_scanner_today) {
			lines.push(
				"Best scanner: " +
					String(verdict.best_scanner_today).replace(/_/g, " ") +
					" (" +
					(verdict.best_scanner_hits || 0) +
					" hits)",
			)
		}
		if (verdict.best_confirmed_name && verdict.best_confirmed_name.ticker) {
			lines.push("Best confirmed: " + verdict.best_confirmed_name.ticker)
		}
		if (verdict.discovery_breadth) lines.push("Breadth: " + verdict.discovery_breadth)
		if (data.category_summary) {
			var cats = Object.keys(data.category_summary).slice(0, 8)
			cats.forEach(function (cat) {
				var c = data.category_summary[cat] || {}
				var hits = c.hits != null ? c.hits : c.count
				if (hits != null) lines.push(cat.replace(/_/g, " ") + ": " + hits + " hits")
			})
		}
		if (hub.error) lines.push("Load error: " + sanitizeOperatorDetail(hub.error))
		if (!lines.length) lines.push("Discovery not loaded — open Discovery tab before export for funnel summary.")
		return exportIssuesList(lines)
	}

	function fundsExportSummaryBlock(funds) {
		var f = funds || {}
		var console = f.console || {}
		var lines = []
		if (console.research_lab_title || console.title) {
			lines.push(String(console.research_lab_title || console.title))
		}
		var fs = console.funds_first_screen || {}
		if (fs.guardrail) lines.push("Guardrail: " + fs.guardrail)
		if (fs.now) lines.push("NOW: " + fs.now)
		if (fs.why) lines.push("WHY: " + fs.why)
		if (fs.core_index_posture) lines.push("Core index posture: " + fs.core_index_posture)
		if (fs.live_allocation_label) lines.push("Live allocation: " + fs.live_allocation_label)
		if (fs.best_research_sleeve && fs.best_research_sleeve.headline) {
			lines.push("Best research sleeve: " + fs.best_research_sleeve.headline)
		}
		if (f.error) lines.push("Load error: " + sanitizeOperatorDetail(f.error))
		if (!lines.length) {
			lines.push("Funds not loaded — open Funds tab before export for sleeve summary.")
		}
		return exportIssuesList(lines)
	}

	function agentExportSummaryBlock(agent) {
		var a = agent || {}
		var lines = []
		if (a.summary) lines.push(String(a.summary))
		if (a.regime_gate) lines.push("Regime gate: " + a.regime_gate)
		if (a.conviction_tier) lines.push("Conviction tier: " + a.conviction_tier)
		if (a.rr_multiple != null) lines.push("R:R " + Number(a.rr_multiple).toFixed(2) + "R")
		if (a.blocker) lines.push("Blocker: " + a.blocker)
		if (a.council && a.council.dominant_risk) lines.push("Dominant risk: " + a.council.dominant_risk)
		if (a.error) lines.push("Error: " + sanitizeOperatorDetail(a.error))
		if (!lines.length) {
			lines.push("Agent council not loaded — open Agent tab before export.")
		}
		return exportIssuesList(lines)
	}

	function dossierExportBlock(dossier) {
		var d = dossier || {}
		if (!d.ticker) {
			return '<div class="cc-export-muted">No dossier ticker loaded — structure: quote · regime · confirm-only blocks · sizing template.</div>'
		}
		var blocks =
			typeof dossierConfirmOnlyFourBlocks === "function"
				? dossierConfirmOnlyFourBlocks(d.intel || d.data || {})
				: null
		var html =
			"<p><strong>" +
			escapeExportHtml(String(d.ticker).toUpperCase()) +
			"</strong> · " +
			escapeExportHtml(d.status || "loaded") +
			"</p>"
		if (blocks && typeof blocks === "object") {
			var sections = [
				["What exists", blocks.exists],
				["What's missing", blocks.missing],
				["Blocker", blocks.blocker],
				["Safe actions", blocks.safe],
			]
			html += sections
				.map(function (pair) {
					return (
						"<div><strong>" +
						escapeExportHtml(pair[0]) +
						"</strong><div>" +
						escapeExportHtml(truncateExportText(pair[1] || "—", 240)) +
						"</div></div>"
					)
				})
				.join("")
		} else {
			html +=
				'<div class="cc-export-muted">' +
				escapeExportHtml(
					truncateExportText(
						d.summary || d.note || "Dossier condensed — open tab for full workstation.",
						320,
					),
				) +
				"</div>"
		}
		return html
	}

	/** All CC surfaces snapshot for external review (condensed). */
	function buildExportAllSurfacesPage(snapshot) {
		var s = snapshot || {}
		var today = s.today || {}
		var playbook = s.playbook || {}
		var portfolio = s.portfolio || {}
		var ops = s.ops || {}
		var ibkr = s.ibkr || {}
		var guide = s.guide || {}

		return (
			'<section class="cc-export-page cc-export-surfaces" data-cc-export="surfaces">' +
			"<h1>CC · All surfaces snapshot</h1>" +
			"<h2>Today / Dashboard</h2>" +
			"<p>" +
			escapeExportHtml(
				truncateExportText(
					today.morning_decision ||
						today.board_message ||
						today.tradeability ||
						"Dashboard snapshot unavailable",
					400,
				),
			) +
			"</p>" +
			exportIssuesList(today.top_ranked || today.monitors || []) +
			"<h2>Playbook</h2>" +
			"<p>" +
			escapeExportHtml(playbook.funnel_label || playbook.board_message || "Playbook not loaded") +
			"</p>" +
			exportIssuesList(
				(playbook.rows || []).slice(0, 12).map(function (row) {
					var r = row || {}
					return (
						String(r.ticker || "—") +
						" · " +
						String(r.action || r.verdict || r.signal || "—") +
						(r.score != null ? " · score " + r.score : "")
					)
				}),
			) +
			"<h2>Discovery</h2>" +
			discoveryExportSummaryBlock(s.discovery) +
			"<h2>Dossier</h2>" +
			dossierExportBlock(s.dossier) +
			"<h2>Portfolio</h2>" +
			"<p>" +
			escapeExportHtml(
				portfolio.summary ||
					((portfolio.positions || []).length
						? (portfolio.positions || []).length + " positions"
						: "No portfolio positions loaded"),
			) +
			"</p>" +
			"<h2>Funds</h2>" +
			fundsExportSummaryBlock(s.funds) +
			"<h2>Agent</h2>" +
			agentExportSummaryBlock(s.agent) +
			"<h2>Ops</h2>" +
			"<p>" +
			escapeExportHtml(ops.verdict || ops.intro || "Ops console snapshot") +
			"</p>" +
			exportIssuesList(ops.blockers || []) +
			"<h2>IBKR</h2>" +
			"<p>" +
			escapeExportHtml(ibkr.label || ibkr.status || "IBKR not connected") +
			"</p>" +
			"<h2>Guide (condensed)</h2>" +
			"<p>" +
			escapeExportHtml(
				guide.workflow ||
					"Core workflow: Dashboard → Playbook → Discovery → Dossier → Portfolio / IBKR. Monitor-only when degraded.",
			) +
			"</p>" +
			'<footer class="cc-export-footer">End of CC review export · not trade authority</footer>' +
			"</section>"
		)
	}

	function buildExportReviewHtml(snapshot) {
		return buildExportIssuesPage(snapshot) + buildExportAllSurfacesPage(snapshot)
	}

	function exportReviewPdfDateSlug(snapshot) {
		var raw = (snapshot && snapshot.generated_at) || new Date().toISOString()
		var d = new Date(raw)
		if (isNaN(d.getTime())) d = new Date()
		var y = d.getUTCFullYear()
		var m = String(d.getUTCMonth() + 1)
		var day = String(d.getUTCDate())
		if (m.length < 2) m = "0" + m
		if (day.length < 2) day = "0" + day
		return y + "-" + m + "-" + day
	}

	/** Populate #cc-export-print-root and download PDF via html2pdf (no print dialog). */
	function exportReviewPdf(snapshot, opts) {
		var o = opts || {}
		if (typeof document === "undefined") {
			return Promise.resolve({ ok: false, error: "document unavailable" })
		}
		var root = o.rootEl || document.getElementById("cc-export-print-root")
		if (!root) {
			return Promise.resolve({ ok: false, error: "missing #cc-export-print-root" })
		}
		if (typeof html2pdf === "undefined") {
			return Promise.resolve({ ok: false, error: "html2pdf unavailable" })
		}
		var filename = "cc-review-" + exportReviewPdfDateSlug(snapshot) + ".pdf"
		root.innerHTML = buildExportReviewHtml(snapshot || {})
		var prevDisplay = root.style.display
		var prevPosition = root.style.position
		var prevLeft = root.style.left
		var prevTop = root.style.top
		var prevWidth = root.style.width
		root.style.display = "block"
		root.style.position = "absolute"
		root.style.left = "-9999px"
		root.style.top = "0"
		root.style.width = "210mm"
		var pdfOpts = {
			margin: [10, 10, 10, 10],
			filename: filename,
			image: { type: "jpeg", quality: 0.95 },
			html2canvas: { scale: 2, useCORS: true, logging: false },
			jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
			pagebreak: { mode: ["css", "legacy"], before: ".cc-export-page", avoid: ".cc-export-footer" },
		}
		var restoreRoot = function () {
			root.style.display = prevDisplay
			root.style.position = prevPosition
			root.style.left = prevLeft
			root.style.top = prevTop
			root.style.width = prevWidth
		}
		var delayMs = o.delayMs != null ? o.delayMs : 80
		return new Promise(function (resolve) {
			window.setTimeout(function () {
				html2pdf()
					.set(pdfOpts)
					.from(root)
					.save()
					.then(function () {
						restoreRoot()
						resolve({ ok: true, filename: filename })
					})
					.catch(function (err) {
						restoreRoot()
						resolve({ ok: false, error: String((err && err.message) || err || "pdf export failed") })
					})
			}, delayMs)
		})
	}

	global.CCHelpers = {
		CC_TOP_MONITOR_COUNT: CC_TOP_MONITOR_COUNT,
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
		dashboardBlockerTreeLegend: dashboardBlockerTreeLegend,
		executionBracketStatusLabel: executionBracketStatusLabel,
		executionBracketStatusTitle: executionBracketStatusTitle,
		todayExecutionReadinessDiagnostic: todayExecutionReadinessDiagnostic,
		playbookStrategyDecayLine: playbookStrategyDecayLine,
		todayMissionMonitorsColumnHint: todayMissionMonitorsColumnHint,
		playbookWhatToMonitorLine: playbookWhatToMonitorLine,
		todayMissionWaitSubtitle: todayMissionWaitSubtitle,
		todayMissionSystemBlockers: todayMissionSystemBlockers,
		systemTruthLine: systemTruthLine,
		globalTruthStrip: globalTruthStrip,
		operatorBlock: operatorBlock,
		scopedFreshnessStrip: scopedFreshnessStrip,
		scopedFreshnessStripLocalized: scopedFreshnessStripLocalized,
		localizeScopedFreshnessStrip: localizeScopedFreshnessStrip,
		localizeMissionBlocker: localizeMissionBlocker,
		localizeMissionBlockerList: localizeMissionBlockerList,
		systemTruthMissionBlockers: systemTruthMissionBlockers,
		systemTruthMissionBlockersLocalized: systemTruthMissionBlockersLocalized,
		playbookCardGateLine: playbookCardGateLine,
		localizeHeaderSurface: localizeHeaderSurface,
		localizeFetchStateCopy: localizeFetchStateCopy,
		exportAllLabel: exportAllLabel,
		operatorBlockChromeLabel: operatorBlockChromeLabel,
		dashboardLoadingHeadline: dashboardLoadingHeadline,
		dashboardLoadingHint: dashboardLoadingHint,
		surfaceEmptyStateCopy: surfaceEmptyStateCopy,
		morningDecisionLine: morningDecisionLine,
		qualificationCountLine: qualificationCountLine,
		playbookQualificationFunnelLine: playbookQualificationFunnelLine,
		playbookQualificationLine: playbookQualificationLine,
		playbookAuthorityViewModel: playbookAuthorityViewModel,
		playbookAuthorityView: playbookAuthorityView,
		buildPlaybookBuckets: buildPlaybookBuckets,
		playbookNoEdgeLine: playbookNoEdgeLine,
		todayMissionBlockersTitle: todayMissionBlockersTitle,
		todayMissionEmptyBlockersCopy: todayMissionEmptyBlockersCopy,
		playbookWhatToMonitorLine: playbookWhatToMonitorLine,
		partitionHeaderChips: partitionHeaderChips,
		operatorLoadingSafeLine: operatorLoadingSafeLine,
		tradeabilityGuidanceLine: tradeabilityGuidanceLine,
		dashboardWaitTopComment: dashboardWaitTopComment,
		dossierMissingDataLabels: dossierMissingDataLabels,
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
		resolveDossierMode: resolveDossierMode,
		dossierRecoveryMode: dossierRecoveryMode,
		dossierUsableMode: dossierUsableMode,
		dossierOperatorBlock: dossierOperatorBlock,
		dossierTradePlanVisible: dossierTradePlanVisible,
		dossierEvidenceStatus: dossierEvidenceStatus,
		dossierStructureReviewOnly: dossierStructureReviewOnly,
		dossierConfirmOnlyStrip: dossierConfirmOnlyStrip,
		dossierStructureSnapshotTitle: dossierStructureSnapshotTitle,
		dossierStructureLevelLabel: dossierStructureLevelLabel,
		dossierPaperDraftDisabledCopy: dossierPaperDraftDisabledCopy,
		dossierMonitorRuleButton: dossierMonitorRuleButton,
		dossierMonitorRuleHint: dossierMonitorRuleHint,
		dossierLaggedContextNote: dossierLaggedContextNote,
		dossierPaperDraftVisible: dossierPaperDraftVisible,
		dossierStructureSnapshotRows: dossierStructureSnapshotRows,
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
		execAnalyticsConsoleLine: execAnalyticsConsoleLine,
		trackerWaveStripLine: trackerWaveStripLine,
		ccOsOperatorStrip: ccOsOperatorStrip,
		ccOsRegimeLine: ccOsRegimeLine,
		ccOsPipelineLine: ccOsPipelineLine,
		ccOsCapitalLine: ccOsCapitalLine,
		ccOsExecutionLine: ccOsExecutionLine,
		ccOsPortfolioLine: ccOsPortfolioLine,
		ccOsCurveLine: ccOsCurveLine,
		ccOsEventLine: ccOsEventLine,
		opportunityQualityPill: opportunityQualityPill,
		opportunityQualityPillClass: opportunityQualityPillClass,
		sanitizeOperatorDetail: sanitizeOperatorDetail,
		sizingPillClass: sizingPillClass,
		sizingBandLabel: sizingBandLabel,
		sizingBlockedForDisplay: sizingBlockedForDisplay,
		sanitizeSizingForBlocked: sanitizeSizingForBlocked,
		dailyBriefingLine: dailyBriefingLine,
		regimeStackStripLine: regimeStackStripLine,
		allocatorStanceHint: allocatorStanceHint,
		workstationPanelTitle: workstationPanelTitle,
		workstationPanelStateLabel: workstationPanelStateLabel,
		workstationPanelNextAction: workstationPanelNextAction,
		workstationPanelErrorLine: workstationPanelErrorLine,
		workstationPanelEmptyCopy: workstationPanelEmptyCopy,
		aiContradictionDossierLine: aiContradictionDossierLine,
		AUTHORITY_COPY: AUTHORITY_COPY,
		authorityNoTradeLine: authorityNoTradeLine,
		authorityBlockedNowLine: authorityBlockedNowLine,
		authorityBlockedBlockerLine: authorityBlockedBlockerLine,
		authorityBlockedNextLine: authorityBlockedNextLine,
		discoveryResearchHeaderNote: discoveryResearchHeaderNote,
		discoveryResearchActionLabel: discoveryResearchActionLabel,
		discoveryResearchCue: discoveryResearchCue,
		discoveryVerdictSpeculativeLabel: discoveryVerdictSpeculativeLabel,
		discoveryVerdictConfirmedLabel: discoveryVerdictConfirmedLabel,
		discoveryFunnelView: discoveryFunnelView,
		discoveryStatusLine: discoveryStatusLine,
		discoveryScannerRunLabel: discoveryScannerRunLabel,
		discoveryRowFreshnessLabel: discoveryRowFreshnessLabel,
		runtimeEngineHeaderLabel: runtimeEngineHeaderLabel,
		discoveryRowLabels: discoveryRowLabels,
		discoveryScoreDisplay: discoveryScoreDisplay,
		discoveryConfidenceDisplay: discoveryConfidenceDisplay,
		dossierConfirmOnlyFourBlocks: dossierConfirmOnlyFourBlocks,
		ibkrRepairChecklistSteps: ibkrRepairChecklistSteps,
		ibkrBuildRepairChecklistState: ibkrBuildRepairChecklistState,
		ibkrRepairChecklistState: ibkrRepairChecklistState,
		signalFamilyHealthLine: signalFamilyHealthLine,
		formatEngineState: formatEngineState,
		resolveEngineState: resolveEngineState,
		engineStateHeaderLabel: engineStateHeaderLabel,
		primaryOperatorState: primaryOperatorState,
		todayPrimaryStateLine: todayPrimaryStateLine,
		runtimePrimaryStateLine: runtimePrimaryStateLine,
		primaryOperatorStateLine: primaryOperatorStateLine,
		regimeSecondaryLine: regimeSecondaryLine,
		runtimeSecondaryRegimeLine: runtimeSecondaryRegimeLine,
		deployAuthorityTier: deployAuthorityTier,
		briefExpiredOperatorLine: briefExpiredOperatorLine,
		safeRenderText: safeRenderText,
		topMonitorLabels: topMonitorLabels,
		cardDisplayReason: cardDisplayReason,
		briefFreshnessStripState: briefFreshnessStripState,
		pilotSizingAllowed: pilotSizingAllowed,
		replayModeActive: replayModeActive,
		replayDeployBlocked: replayDeployBlocked,
		replayBannerLine: replayBannerLine,
		evidenceConflictPanel: evidenceConflictPanel,
		volatilityMonitorLabel: volatilityMonitorLabel,
		runtimeFreshnessLabel: runtimeFreshnessLabel,
		shellTruthViewModel: shellTruthViewModel,
		shellTruthScopedStrip: shellTruthScopedStrip,
		sanitizeBlockedCandidateCopy: sanitizeBlockedCandidateCopy,
		removeTradeLanguageWhenBlocked: removeTradeLanguageWhenBlocked,
		removeSizingLanguageWhenBlocked: removeSizingLanguageWhenBlocked,
		topWatchCandidateLabel: topWatchCandidateLabel,
		closestUpgradeLabel: closestUpgradeLabel,
		topPromotionTriggerLabel: topPromotionTriggerLabel,
		executionRepairOneLiner: executionRepairOneLiner,
		researchSurfaceBlock: researchSurfaceBlock,
		researchGettingStarted: researchGettingStarted,
		excludeExpiredBriefFromAgent: excludeExpiredBriefFromAgent,
		agentBriefLabel: agentBriefLabel,
		agentMaxOneBlockerLine: agentMaxOneBlockerLine,
		agentSuggestedRules: agentSuggestedRules,
		agentPageState: agentPageState,
		portfolioRiskPageState: portfolioRiskPageState,
		portfolioOperatorBlock: portfolioOperatorBlock,
		portfolioCapitalActionsEnabled: portfolioCapitalActionsEnabled,
		portfolioRiskViewModel: portfolioRiskViewModel,
		strategyLabPageState: strategyLabPageState,
		strategyLabActionEnabled: strategyLabActionEnabled,
		strategyLabActionReason: strategyLabActionReason,
		strategyLabValidationStatus: strategyLabValidationStatus,
		strategyLabValidationSummary: strategyLabValidationSummary,
		buildExportIssuesPage: buildExportIssuesPage,
		buildExportAllSurfacesPage: buildExportAllSurfacesPage,
		buildExportReviewHtml: buildExportReviewHtml,
		exportReviewPdfDateSlug: exportReviewPdfDateSlug,
		exportReviewPdf: exportReviewPdf,
	}
})(typeof window !== "undefined" ? window : globalThis)
