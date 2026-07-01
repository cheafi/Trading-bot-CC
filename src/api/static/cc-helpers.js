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
		if (!n && !nm) return "Monitors"
		var prefix = n && (isNaN(wq) || wq === 0) ? "Fallback monitors" : "Monitors"
		var base = n ? prefix + " (" + n + ")" : prefix
		return nm ? base + " · " + nm + " near-miss" : base
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
		if (truth && (truth.reason_codes || []).length) {
			return systemTruthMissionBlockers(truth)
		}
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
			out.push("EXEC BLOCKED — risk breaker")
		}
		var tier = String(o.dataTier || "").toUpperCase()
		if (tier === "STALE" || tier === "CRITICAL") {
			out.push("DATA " + tier)
		}
		var fb = String(o.fetchBadge || "").toUpperCase()
		if (fb === "FALLBACK") {
			out.push("FALLBACK / BRIEF ONLY")
		} else if (fb === "FETCH FAILED") {
			out.push("FETCH FAILED — not decision-grade")
		}
		if (o.briefFallback || o.instantDegraded) {
			var hasFb = out.some(function (x) {
				return x.indexOf("FALLBACK") >= 0 || x.indexOf("BRIEF") >= 0
			})
			if (!hasFb) {
				out.push("FALLBACK / BRIEF ONLY")
			}
		}
		return out
	}

	function systemTruthMissionBlockers(truth) {
		var t = truth || {}
		var codes = t.reason_codes || []
		var labels = {
			FALLBACK_BRIEF: "FALLBACK / BRIEF ONLY",
			BRIEF_EXPIRED: "BRIEF EXPIRED — not used for ranking",
			BRIEF_STALE: "BRIEF STALE",
			DATA_STALE: "MARKET DATA STALE",
			DATA_UNAVAILABLE: "MARKET DATA UNAVAILABLE",
			BOARD_STALE: "BOARD STALE",
			NO_VALID_BOARD: "NO VALID BOARD",
			DATA_DEGRADED: "DATA DEGRADED",
			ENGINE_OFF: "ENGINE OFF",
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
		for (var i = 0; i < codes.length && out.length < 6; i++) {
			var code = String(codes[i] || "")
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
		if (t.truth_strip) return String(t.truth_strip)
		if (typeof scopedFreshnessStrip === "function") return scopedFreshnessStrip(t)
		return "Monitor only — see scoped truth strip"
	}

	function operatorBlock(truth, page, operatorBlocks) {
		var t = truth || {}
		var p = String(page || "dashboard").toLowerCase()
		var blocks = operatorBlocks || t.operator_blocks || {}
		if (blocks[p] && typeof blocks[p] === "object") return blocks[p]
		if (p === "dashboard" && t.operator_block && typeof t.operator_block === "object")
			return t.operator_block
		var regime = String(t.regime_state || "WAIT").toUpperCase()
		var deploy = !!t.deploy_authority
		var why = String(t.primary_blocker || "No edge today — preserve capital")
		var allowed = deploy ? "deploy selectively" : "monitor only"
		if (regime === "NO_TRADE") allowed = "monitor only"
		var repair = (t.repair_priority || [])[0] || ""
		var next = repair
			? "Repair: " + String(repair).replace(/_/g, " ")
			: deploy
				? "Review deploy-qualified on Playbook"
				: "Monitor only — patience is the active decision"
		return {
			page: p,
			now: t.operator_sentence || "",
			why: why,
			allowed: allowed,
			blocked: deploy ? "" : "deploy",
			next: next,
			truth_strip: globalTruthStrip(t),
			regime_state: regime,
			deploy_authority: deploy,
			repair_priority: (t.repair_priority || []).slice(0, 5),
		}
	}

	function scopedFreshnessStrip(truth) {
		var t = truth || {}
		if (t.typed_freshness_display) return String(t.typed_freshness_display)
		if (t.truth_strip) return String(t.truth_strip)
		var age = t.brief_age_days
		function label(scope, state) {
			var s = String(state || "unknown").toLowerCase()
			if (scope === "Brief" && s === "expired" && age != null) return "Expired " + age + "d"
			if (scope === "Broker" && (s === "unavailable" || s === "offline")) return "Offline"
			if (s === "fresh") return "Fresh"
			if (s === "stale") return "Stale"
			if (s === "expired") return "Expired"
			if (s === "fallback") return "Fallback"
			if (s === "unavailable") return "Unavailable"
			return s.charAt(0).toUpperCase() + s.slice(1)
		}
		var parts = []
		parts.push("Market: " + label("Market", t.market_data_freshness))
		parts.push("Board: " + label("Board", t.ranked_board_freshness))
		parts.push("Brief: " + label("Brief", t.brief_freshness))
		parts.push("Broker: " + label("Broker", t.broker_freshness))
		parts.push("Authority: " + (t.deploy_authority ? "Open" : "Blocked"))
		return parts.join(" · ")
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
		if (t.qualification_line) return String(t.qualification_line)
		if (f.qualification_line) return String(f.qualification_line)
		var setup = Number(f.setup_qualified_setups || f.watch_qualified_setups) || 0
		var deploy = t.deploy_authority === false ? 0 : Number(f.deploy_qualified_setups) || 0
		var parts = []
		if (setup) parts.push(setup + " setup-qualified")
		parts.push(deploy + " deploy-qualified")
		return parts.join(" · ")
	}

	function todayMissionBlockersTitle(opts) {
		var o = opts || {}
		if (o.waitDay && o.hasSystem) {
			return "System blockers · gate flags"
		}
		if (o.waitDay) {
			return "Gate flags"
		}
		return o.hasSystem ? "System blockers" : "Blockers"
	}

	function todayMissionEmptyBlockersCopy(opts) {
		var o = opts || {}
		if ((o.systemBlockers || []).length && !(o.cardGates || []).length) {
			return "No card-level gate flags"
		}
		return "None flagged"
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
		return "僅監察 · monitor only — " + body + " · 本頁不授權交易"
	}

	var AUTHORITY_COPY = {
		no_trade_authority: "本頁不授權交易 · No trade authority here",
		monitor_item: "監察候選 · monitor item",
		research_item: "研究候選 · research item",
		upgrade_condition: "升級條件 · upgrade condition",
		review_path: "複核路徑 · review path",
		scan_evidence: "掃描證據 · scan evidence",
		playbook_review: "可送交 Playbook 複核 · Playbook review path",
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
			return "僅複核模式 · Confirm-only research"
		}
		if (o.degraded || o.researchOnly) {
			return "降級研究面 · Degraded research surface"
		}
		return "今日不可部署 · No deploy today"
	}

	function authorityBlockedBlockerLine(opts) {
		var o = opts || {}
		var parts = []
		if (o.primaryBlocker) parts.push(String(o.primaryBlocker))
		if (o.brokerOffline) parts.push("IBKR 未就緒 · broker offline")
		if (o.deployQualified === 0 && o.deployQualified != null) {
			parts.push("0 筆通過部署門檻 · 0 deploy-qualified")
		}
		if (o.briefFallback) parts.push("備援簡報板 · brief fallback")
		if (o.execBlocked) parts.push("執行阻斷 · exec blocked")
		if (o.gatedRegime && o.regimeState && o.regimeState !== o.effectiveState) {
			parts.push(
				"體制 " +
					String(o.regimeState) +
					" 已閘為 " +
					String(o.effectiveState || "WAIT")
			)
		}
		if (!parts.length) {
			parts.push("尚未滿足升級條件 · upgrade conditions not met")
		}
		return parts.join(" · ")
	}

	function authorityBlockedNextLine(opts) {
		var o = opts || {}
		if (o.surface === "discovery") {
			return AUTHORITY_COPY.playbook_review
		}
		if (o.surface === "dossier" && o.confirmOnly) {
			return "載入完整檔案後再複核 · Load live dossier, then review on Dashboard"
		}
		if (o.surface === "ibkr") {
			return "依 IBKR 修復清單逐步連線 · Follow IBKR repair checklist"
		}
		if (o.brokerOffline) {
			return "開啟 IBKR 分頁修復連線 · Open IBKR tab — connect before handoff"
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
			return "迴避背景 · avoid context"
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
		return "頂部研究候選 · top research item"
	}

	function discoveryVerdictConfirmedLabel(opts) {
		var o = opts || {}
		if (o.fallback) return "備援監察樣本 · fallback monitor sample"
		if (o.briefFallback) return "簡報備援樣本 · brief fallback sample"
		return "多掃描器重合 · multi-scanner overlap"
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
		if (!missing.length && o.confirmOnly) missing.push("需 live fetch 才授權複核")
		var blockers = []
		if (o.confirmOnly) blockers.push("CONFIRM ONLY — 本頁不授權交易")
		if (o.boardWait) blockers.push("Dashboard WAIT — 無部署權限")
		if (o.brokerOffline) blockers.push("IBKR 未就緒")
		if (o.failedFetch) blockers.push("擷取失敗 — 僅快取研究")
		if (!blockers.length) blockers.push("研究面 — 非交易觸發")
		var safe = []
		safe.push("閱讀研究檔與升級條件")
		safe.push("回 Dashboard 確認體制")
		if (o.hasCached) safe.push("Use cached dossier（仍為 confirm-only）")
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

	function ibkrRepairChecklistState(stepKey, ibkrState) {
		var st = ibkrState || {}
		var key = String(stepKey || "")
		if (key === "ibapi") {
			return st.hasIbapi === false ? "pending" : st.hasIbapi ? "done" : "unknown"
		}
		if (key === "tws") return st.gw ? "done" : "pending"
		if (key === "socket") return st.apiPortOpen ? "done" : st.gw ? "pending" : "pending"
		if (key === "host") return st.hostConfigured ? "done" : "pending"
		if (key === "connect") return st.connected ? "done" : st.gw ? "pending" : "pending"
		if (key === "verify") {
			return st.accountLoaded && st.positionsLoaded ? "done" : st.connected ? "pending" : "pending"
		}
		if (key === "bracket") {
			return st.bracketReady ? "done" : st.connected ? "pending" : "pending"
		}
		return "unknown"
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
			return "Blocked: new cycle sizing · Safe: Guide · monitors until engine ON"
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

	var DOSSIER_CONFIRM_ONLY_SIZING = "No sizing guidance in confirm-only mode"

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

	var DOSSIER_CONFIRM_ONLY_STRIP =
		"Confirm-only: structure review only · no sizing · no handoff"
	var DOSSIER_PAPER_DRAFT_DISABLED =
		"Paper draft disabled — live Dossier + Playbook confirmation required."
	var DOSSIER_MONITOR_RULE_BUTTON = "Create monitor rule · 建立監察規則"
	var DOSSIER_MONITOR_RULE_HINT =
		"Alert only · no sizing · no handoff · requires Playbook confirmation"
	var DOSSIER_LAGGED_CONTEXT_NOTE =
		"Lagged ownership context hidden — not used for confirmation."
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
		var label = String(o.unified_label || "").toUpperCase()
		var confirmLabels = [
			"CONFIRM ONLY",
			"RESEARCH ONLY",
			"REFERENCE ONLY",
			"WATCH ONLY",
			"PASS",
		]
		var confirmOnly =
			confirmLabels.indexOf(label) >= 0 ||
			!!o.research_only ||
			!!o.instant_degraded ||
			!!o.brief_backed ||
			!!o.pending_calibration ||
			!!o.rr_unavailable
		if (confirmOnly) return "structure_review_only"
		if (o.partial || o.load_phase === "core") return "partial"
		return "usable"
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
		return (
			resolveDossierMode(o) === "usable" &&
			!!o.playbook_watch_plus &&
			!o.deploy_blocked &&
			!!o.broker_online
		)
	}

	function dossierStructureSnapshotRows(opts) {
		var o = opts || {}
		var mode = resolveDossierMode(o)
		var review = dossierStructureReviewOnly(mode)
		var ez = o.entry_zone
		var fmt = function (v) {
			return v != null && v !== "" ? "$" + v : "—"
		}
		var entry =
			ez && ez.length >= 2 ? "$" + ez[0] + "–$" + ez[1] : "—"
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
			return (
				"Safe now: monitor queue, Guide checklist, dossier core-only — " +
				"wait for backend import + /health mode=full before sizing or IBKR handoff"
			)
		}
		if (o.fetchFailed || o.instantDegraded) {
			return (
				"Safe now: Guide, monitors, dossier core-only — " +
				"retry when fetch badges clear; no deploy from fallback"
			)
		}
		if (o.waitDay) {
			return "Safe now: upgrade-watch queue · Discovery · Playbook ranking"
		}
		return ""
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
		return String(key || "").replace(/^\d+_/, "").replace(/_/g, " ")
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
						"</td><td class=\"mono\">" +
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
			return (
				probe.indexOf("FAIL") >= 0 ||
				runtime.indexOf("FAIL") >= 0 ||
				runtime.indexOf("UNAVAILABLE") >= 0
			)
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
						escapeExportHtml(truncateExportText(r.runtime || r.runtime_evidence || r.evidence || "—", 120)) +
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
			: Number(funnel.deploy_qualified_setups || funnel.execution_ready_setups) || Number(truth.deploy_qualified_count) || 0
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
			escapeExportHtml(disconnects.ibkr_gateway != null ? (disconnects.ibkr_gateway ? "reachable" : "offline") : "—") +
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
			escapeExportHtml(String(s.error_log_total || 0) + " buffered · showing last " + String((s.error_log || []).length) + " entries") +
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

	function dossierExportBlock(dossier) {
		var d = dossier || {}
		if (!d.ticker) {
			return '<div class="cc-export-muted">No dossier ticker loaded — structure: quote · regime · confirm-only blocks · sizing template.</div>'
		}
		var blocks =
			typeof dossierConfirmOnlyFourBlocks === "function" ? dossierConfirmOnlyFourBlocks(d.intel || d.data || {}) : null
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
				escapeExportHtml(truncateExportText(d.summary || d.note || "Dossier condensed — open tab for full workstation.", 320)) +
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

	/** Populate #cc-export-print-root and open browser print / Save as PDF. */
	function exportReviewPdf(snapshot, opts) {
		var o = opts || {}
		if (typeof document === "undefined") {
			return { ok: false, error: "document unavailable" }
		}
		var root = o.rootEl || document.getElementById("cc-export-print-root")
		if (!root) {
			return { ok: false, error: "missing #cc-export-print-root" }
		}
		root.innerHTML = buildExportReviewHtml(snapshot || {})
		document.body.classList.add("cc-export-printing")
		var cleanup = function () {
			document.body.classList.remove("cc-export-printing")
			if (typeof window !== "undefined") {
				window.removeEventListener("afterprint", cleanup)
			}
		}
		if (typeof window !== "undefined") {
			window.addEventListener("afterprint", cleanup)
			window.setTimeout(function () {
				window.print()
			}, o.delayMs != null ? o.delayMs : 120)
		}
		return { ok: true }
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
		systemTruthMissionBlockers: systemTruthMissionBlockers,
		morningDecisionLine: morningDecisionLine,
		qualificationCountLine: qualificationCountLine,
		playbookQualificationFunnelLine: playbookQualificationFunnelLine,
		todayMissionBlockersTitle: todayMissionBlockersTitle,
		todayMissionEmptyBlockersCopy: todayMissionEmptyBlockersCopy,
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
		resolveDossierMode: resolveDossierMode,
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
		dossierConfirmOnlyFourBlocks: dossierConfirmOnlyFourBlocks,
		ibkrRepairChecklistSteps: ibkrRepairChecklistSteps,
		ibkrRepairChecklistState: ibkrRepairChecklistState,
		buildExportIssuesPage: buildExportIssuesPage,
		buildExportAllSurfacesPage: buildExportAllSurfacesPage,
		buildExportReviewHtml: buildExportReviewHtml,
		exportReviewPdf: exportReviewPdf,
	}
})(typeof window !== "undefined" ? window : globalThis)
