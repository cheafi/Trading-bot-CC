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

	function todayMissionMonitorsLabel(monitors, nearMissCount) {
		var n = (monitors || []).length
		var nm = Number(nearMissCount) || 0
		if (!n && !nm) return "Monitors"
		var base = n ? "Monitors (" + n + ")" : "Monitors"
		return nm ? base + " · " + nm + " near-miss" : base
	}

	/** Clarifies monitor vs near-miss vs deploy — attention routing without tradability. */
	function todayMissionMonitorsColumnHint(opts) {
		var o = opts || {}
		if (o.waitDay) {
			return "Near-miss · watch queue — priority only, not deploy on WAIT"
		}
		return "Watch / near-miss — ranking for attention, not handoff permission"
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

	/** IBKR LOGIN→READY — execution-dependent, not deploy gate alone. */
	function ibkrLoginToReadyHint() {
		return "IBKR LOGIN — connect session on IBKR tab; READY required before handoff (bracket aligned)"
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
		}
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
		todayMissionMonitorsColumnHint: todayMissionMonitorsColumnHint,
		todayMissionWaitSubtitle: todayMissionWaitSubtitle,
		todayMissionSystemBlockers: todayMissionSystemBlockers,
		todayMissionBlockersTitle: todayMissionBlockersTitle,
		todayMissionEmptyBlockersCopy: todayMissionEmptyBlockersCopy,
		partitionHeaderChips: partitionHeaderChips,
		operatorLoadingSafeLine: operatorLoadingSafeLine,
		routeAbortRecoveryHint: routeAbortRecoveryHint,
		staleRefreshRecoveryLine: staleRefreshRecoveryLine,
		engineOffRecoveryLine: engineOffRecoveryLine,
		ibkrLoginToReadyHint: ibkrLoginToReadyHint,
		todayMissionSafeUnlockHint: todayMissionSafeUnlockHint,
		soakConfirmationSelectors: soakConfirmationSelectors,
	}
})(typeof window !== "undefined" ? window : globalThis)
