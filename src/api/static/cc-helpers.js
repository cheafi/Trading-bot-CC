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
		funds_research: "Fund lab still loading — sleeve cards refresh when the API is ready.",
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
		return "Synthesis hint (monitor only): " + parts.join(" · ") + " — not deploy permission"
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
		return "Monitor only — " + parts.join(" · ") + " · no deploy authority"
	}

	function todayMissionWaitSubtitle(opts) {
		if (!opts || !opts.waitDay) return ""
		return "Deploy blocked — use monitors and Playbook ranking only"
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
			parts.push(String(o.topSymbol).toUpperCase() + " upgrade triggers")
		}
		var nm = Number(o.nearMissCount) || 0
		if (nm > 0) {
			parts.push(nm + " near-miss row" + (nm === 1 ? "" : "s"))
		}
		parts.push("deploy unlock checklist below")
		var body = parts.length ? parts.join(" · ") : "near-miss strip · gate context"
		return "Monitor only — " + body + " · no deploy authority"
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
			return "Live structure unavailable — confirm-only dossier"
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
		drawdownSizingLine: drawdownSizingLine,
		quantSleeveHint: quantSleeveHint,
	}
})(typeof window !== "undefined" ? window : globalThis)
