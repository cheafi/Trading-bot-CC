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
		backtest_research:
			"Backtest warming — research shell may appear before live stats load.",
		funds_research: "Funds warming — sleeve cards refresh when the API is ready.",
		rejections_diagnostic: "Rejections warming — blocker audit will fill in shortly.",
		flow_supporting: "Flow warming — research shell may appear before live provider connects.",
		ops_diagnostic: "Ops warming — refresh in a few seconds.",
		ibkr_execution:
			"IBKR warming — probe status may show LOGIN; wait for /health mode=full.",
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
			return "OFFLINE - API unreachable; cached snapshot may be stale"
		}
		if (mode === "loading") {
			return "WARMING - monitor-only until full"
		}
		if (o.instantDegraded || o.fetchFailed) {
			return "DEGRADED - snapshot only until live ranked data returns"
		}
		if (mode === "full") {
			return "LIVE - ranked payloads are authoritative when fetch badges clear"
		}
		return "LOADING - probing health before treating the board as live"
	}

	function warmupUpgradeQueue(opts) {
		var o = opts || {}
		var mode = String(o.healthMode || "").toLowerCase()
		if (mode !== "loading" && !o.briefFallback) return ""
		var parts = ["live ranked playbook", "today council reconciliation", "dossier enrichment"]
		if (o.nearMiss || o.briefFallback) {
			parts.unshift("monitor queue (brief near-miss + top watch)")
		}
		return "Next: " + parts.join(" · ")
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
		return "Cold start - wait for /health mode=full; restart once if loading exceeds ~2 min"
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
		return "Monitor context: " + parts.join(" · ") + " — not deploy permission"
	}

	function todayExecutionReadinessDiagnostic(er) {
		var e = er || {}
		var sub = e.sub_status || {}
		var gaps = []
		if (sub.broker_transport !== "up") gaps.push("transport down")
		if (sub.session_auth !== "active") gaps.push("session inactive")
		if (sub.engine !== "on") gaps.push("engine off")
		if (sub.handoff_readiness !== "ready") gaps.push("handoff blocked")
		if (sub.bracket_readiness !== "ready") gaps.push("bracket draft")
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
		if (!isNaN(wq) && wq > 0) {
			return wq + " watch-qualified on funnel — mission tickers are attention queue, not extra KPI count"
		}
		if (mc > 0) {
			return "Fallback monitors — scan / near-miss queue; filter_funnel is authority for watch-qualified"
		}
		if (o.waitDay) {
			return "Near-miss · watch queue — priority only, not deploy on WAIT"
		}
		return "Watch / near-miss — ranking for attention, not handoff permission"
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
		return "Monitor only - " + parts.join(" · ") + " · no deploy authority"
	}

	function todayMissionWaitSubtitle(opts) {
		if (!opts || !opts.waitDay) return ""
		return "Deploy blocked - use monitors and Playbook ranking only"
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
			return "Route failed — retry or Load core only"
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
		return "Engine OFF - start the engine in Ops; board may be precomputed only"
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
			return "Blocked: deploy · Safe: monitors · near-miss · Playbook ranking"
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
				"Safe now: monitor queue, Guide, dossier core-only — " +
				"wait for /health mode=full before sizing or IBKR handoff"
			)
		}
		if (o.fetchFailed || o.instantDegraded) {
			return (
				"Safe now: Guide, monitors, dossier core-only — " +
				"retry when fetch badges clear; no deploy from fallback"
			)
		}
		if (o.waitDay) {
			return "Safe now: near-miss monitors, Discovery context, Playbook ranking — " + "deploy blocked on WAIT"
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
