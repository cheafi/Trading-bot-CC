/**
 * CC · Clarity Console — operator workflow E2E (Playwright).
 *
 * ```bash
 * npm install --no-save @playwright/test@1.49.1
 * npx playwright install chromium
 * npx playwright test tests/e2e/cc_operator_workflows.spec.ts
 * ```
 */

import { test, expect, type Page } from "@playwright/test"

async function waitForCcShell(page: Page) {
	await page.goto("/", { waitUntil: "domcontentloaded" })
	const health = await page.request.get("/health")
	expect(health.ok()).toBeTruthy()
	await page.waitForSelector(
		'[data-cc="data-contract-strip"], [data-cc="warmup-context-strip"], [data-cc="instant-degraded-banner"]',
		{
			state: "attached",
			timeout: 20_000,
		},
	)
}

async function openTab(page: Page, pattern: RegExp, dataCcNav?: string) {
	if (dataCcNav) {
		const nav = page.locator(`[data-cc-nav="${dataCcNav}"]`).first()
		if (await nav.count()) {
			await expect(nav).toBeVisible({ timeout: 8_000 })
			await nav.click()
			await page.waitForLoadState("domcontentloaded")
			return
		}
	}
	const link = page.locator("a", { hasText: pattern }).first()
	await expect(link).toBeVisible({ timeout: 8_000 })
	await link.click()
	await page.waitForLoadState("domcontentloaded")
}

test.describe("CC operator workflows", () => {
	test.describe.configure({ mode: "serial" })

	test.beforeEach(async ({ page }) => {
		await waitForCcShell(page)
	})

	test("cc-helpers exposes soak confirmation selectors", async ({ page }) => {
		const res = await page.request.get("/static/cc-helpers.js")
		expect(res.ok()).toBeTruthy()
		const body = await res.text()
		expect(body).toContain("soakConfirmationSelectors")
		expect(body).toContain('[data-cc="deploy-status-strip"]')
		expect(body).toContain('[data-cc="ops-recovery-runbook"]')
		expect(body).toContain("playbookCostRankPill")
		expect(body).toContain("playbookStrategyDecayLine")
	})

	test("soak anchors — data-cc selectors attached in shell", async ({ page }) => {
		const anchors = [
			'[data-cc="instant-degraded-banner"]',
			'[data-cc="warmup-context-strip"]',
			'[data-cc="data-contract-strip"]',
			'[data-cc="deploy-status-strip"]',
			'[data-cc="playbook-surface"]',
			'[data-cc="ops-recovery-runbook"]',
		]
		for (const sel of anchors) {
			await expect(page.locator(sel).first()).toBeAttached()
		}
	})

	test("soak anchors — recovery copy helpers in static bundle", async ({ page }) => {
		const res = await page.request.get("/static/cc-helpers.js")
		const body = await res.text()
		expect(body).toContain("staleRefreshRecoveryLine")
		expect(body).toContain("engineOffRecoveryLine")
		expect(body).toContain("ibkrLoginToReadyHint")
		expect(body).toContain("routeAbortRecoveryHint")
	})

	test("loads cc-helpers before Alpine boot", async ({ page }) => {
		const res = await page.request.get("/static/cc-helpers.js")
		expect(res.ok()).toBeTruthy()
		const body = await res.text()
		expect(body).toContain("warmupContextStripVisible")
		expect(body).toContain("loadingSessionRecoveryLine")
		expect(body).toContain("operatorLoadingSafeLine")
		expect(body).toContain("todayMissionWaitSubtitle")
		expect(body).toContain("todayMissionMonitorsColumnHint")
		expect(body).toContain("routeAbortRecoveryHint")
		expect(body).toContain("todayMissionSafeUnlockHint")
	})

	test("health endpoint exposes mode for loading sessions", async ({ request }) => {
		const res = await request.get("/health")
		expect(res.ok()).toBeTruthy()
		const h = await res.json()
		expect(["loading", "full"]).toContain(String(h.mode || "").toLowerCase())
	})

	test("data contract strip uses stable selector when visible", async ({ page }) => {
		const strip = page.locator('[data-cc="data-contract-strip"]')
		if (await strip.isVisible().catch(() => false)) {
			await expect(strip.locator(".pill").first()).toBeVisible()
		} else {
			await expect(strip).toBeAttached()
		}
	})

	test("instant degraded banner precedes warmup strip when visible", async ({ page }) => {
		const banner = page.locator('[data-cc="instant-degraded-banner"]')
		const strip = page.locator('[data-cc="warmup-context-strip"]')
		const bannerVisible = await banner.isVisible().catch(() => false)
		if (bannerVisible) {
			await expect(strip).toBeHidden()
		} else {
			await expect(banner.or(strip)).toBeAttached()
		}
	})

	test("warmup strip shows recovery or safe-operator line when visible", async ({ page }) => {
		const strip = page.locator('[data-cc="warmup-context-strip"]')
		if (await strip.isVisible().catch(() => false)) {
			await expect(
				strip.locator("text=/Cold start|Safe now|WARMING|DEGRADED|LOADING|backend import/i").first(),
			).toBeVisible()
		}
	})

	test("WAIT day — no green deploy TRADE pills on dashboard", async ({ page }) => {
		await openTab(page, /Overview/i, "today")
		const deployPills = page.locator(".pill.pg", { hasText: /^TRADE$/i })
		await expect(deployPills).toHaveCount(0)
	})

	test("fallback cards — downgraded labels not raw deploy", async ({ page }) => {
		await openTab(page, /Playbook|Signals/i, "signals")
		await expect(page.locator("text=/Fallback rank|WATCH ONLY|REFERENCE ONLY/i").first()).toBeVisible({
			timeout: 15_000,
		})
	})

	test("playbook — no Send to IBKR handoff on WAIT board", async ({ page }) => {
		await openTab(page, /Playbook|Signals/i, "signals")
		const surface = page.locator('[data-cc="playbook-surface"]')
		await expect(surface).toBeVisible({ timeout: 12_000 })
		await expect(surface.locator("text=/Send to IBKR/i")).toHaveCount(0)
		await expect(surface.locator("button", { hasText: /Send to IBKR/i })).toHaveCount(0)
	})

	test("playbook — cost-rank and decay-line selectors in shell", async ({ page }) => {
		await openTab(page, /Playbook|Signals/i, "signals")
		const surface = page.locator('[data-cc="playbook-surface"]')
		await expect(surface).toBeAttached({ timeout: 12_000 })
		const costPill = surface.locator('[data-cc="playbook-cost-rank-pill"]')
		const decayLine = surface.locator('[data-cc="playbook-strategy-decay-line"]')
		if ((await costPill.count()) > 0) {
			await expect(costPill.first()).toBeAttached()
		}
		if ((await decayLine.count()) > 0) {
			await expect(decayLine.first()).toBeAttached()
		}
	})

	test("IBKR — LOGIN or OFFLINE when gateway/session not ready", async ({ page }) => {
		await openTab(page, /^IBKR$/i, "ibkr")
		await expect(page.locator("text=/LOGIN|OFFLINE|READY/i").first()).toBeVisible({
			timeout: 10_000,
		})
	})

	test("Guide — no deploy chips", async ({ page }) => {
		await openTab(page, /^Guide$/i, "guide")
		await expect(page.locator('[data-cc="guide-surface"]')).toBeVisible({ timeout: 10_000 })
		await expect(page.locator("text=/Send to IBKR/i")).toHaveCount(0)
		await expect(page.locator("text=/GUIDE MODE/i").first()).toBeVisible({ timeout: 10_000 })
	})

	test("dashboard deploy strip — IBKR and engine pills visible", async ({ page }) => {
		await openTab(page, /Overview/i, "today")
		const strip = page.locator('[data-cc="deploy-status-strip"]')
		await expect(strip).toBeAttached({ timeout: 10_000 })
		await expect(strip.locator("text=/IBKR|ENGINE/i").first()).toBeVisible()
	})

	test("today mission panel — WAIT focus or monitors on dashboard", async ({ page }) => {
		await openTab(page, /Overview/i, "today")
		const panel = page.locator('[data-cc="today-mission-panel"]')
		if (await panel.isVisible().catch(() => false)) {
			await expect(
				panel
					.locator("text=/Today focus|Today mission|Monitors|Deploy blocked|near-miss|watch queue|Safe:/i")
					.first(),
			).toBeVisible()
		}
	})

	test("Rejections — degraded wording or loading shell", async ({ page }) => {
		await openTab(page, /Rejections|No trade/i)
		await expect(
			page.locator("text=/FETCH FAILED|UNAVAILABLE|Retry|still loading|research-only/i").first(),
		).toBeVisible({ timeout: 12_000 })
	})

	test("dossier — core-only path or confirm-only levels", async ({ page }) => {
		await openTab(page, /Search|Dossier/i, "dossier")
		await expect(page.locator('[data-cc="dossier-surface"]')).toBeAttached()
		await expect(page.locator("text=/Load core only|CONFIRM ONLY|research-only/i").first()).toBeVisible({
			timeout: 12_000,
		})
	})

	test("discovery — fallback banner or WAIT empty copy", async ({ page }) => {
		await openTab(page, /Discovery|Scanner/i, "scanners")
		await expect(page.locator('[data-cc="discovery-surface"]')).toBeAttached()
		await expect(page.locator("text=/Fallback|WAIT|monitor funnel|discovery_verdict|Tier 1/i").first()).toBeVisible(
			{ timeout: 15_000 },
		)
	})

	test("portfolio — stop or risk blocker surfaced", async ({ page }) => {
		await openTab(page, /Portfolio/i, "portfolio")
		await expect(page.locator("text=/Set stop|Risk blocker|Stops |heat|Blockers/i").first()).toBeVisible({
			timeout: 15_000,
		})
		const blockers = page.locator('[data-cc="portfolio-stop-blockers"]')
		if (await blockers.isVisible().catch(() => false)) {
			await expect(blockers).toContainText(/Blockers/i)
		}
	})

	test("Ops — recovery runbook when health panel visible", async ({ page }) => {
		await openTab(page, /^Ops$/i, "ops")
		const runbook = page.locator('[data-cc="ops-recovery-runbook"]')
		await expect(runbook).toBeAttached({ timeout: 12_000 })
		await expect(runbook.locator("text=/Retry|Safe in degraded|Blocks capital/i").first()).toBeVisible({
			timeout: 12_000,
		})
	})

	test("Ops — loading line or recovery when console warming", async ({ page }) => {
		await openTab(page, /^Ops$/i, "ops")
		await expect(
			page.locator("text=/Recovery runbook|loading|WARMING|Retry|Safe in degraded/i").first(),
		).toBeVisible({ timeout: 12_000 })
	})

	test("market snapshot — stale downgrade copy when strip stale", async ({ page }) => {
		await openTab(page, /Overview/i, "today")
		const stale = page.locator('[data-cc="market-strip-stale"]')
		if (await stale.isVisible().catch(() => false)) {
			await expect(stale.locator("text=/snapshot|stale|not decision/i").first()).toBeVisible()
		} else {
			await expect(page.locator("text=/Market data|snapshot|Refresh market/i").first()).toBeAttached()
		}
	})
})

test.describe("CC route-abort recovery shells", () => {
	test.describe.configure({ mode: "serial" })

	test.beforeEach(async ({ page }) => {
		await waitForCcShell(page)
	})

	test("dossier — route abort shows degraded research shell", async ({ page }) => {
		await page.route("**/api/dossier/**", (route) => route.abort("failed"))
		await openTab(page, /Search|Dossier/i, "dossier")
		await expect(page.locator('[data-cc="dossier-surface"]')).toBeVisible({ timeout: 12_000 })
		await expect(
			page.locator("text=/Load core only|CONFIRM ONLY|research-only|Retry|unavailable/i").first(),
		).toBeVisible({ timeout: 12_000 })
	})

	test("discovery — route abort shows fallback or WAIT funnel", async ({ page }) => {
		await page.route("**/api/v7/playbook/scanners**", (route) => route.abort("failed"))
		await openTab(page, /Discovery|Scanner/i, "scanners")
		await expect(page.locator('[data-cc="discovery-surface"]')).toBeVisible({ timeout: 12_000 })
		await expect(
			page.locator("text=/Fallback|WAIT|FETCH|monitor funnel|Tier 1|Run Scanners/i").first(),
		).toBeVisible({ timeout: 15_000 })
	})
})
