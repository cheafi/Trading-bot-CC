import { defineConfig, devices } from "@playwright/test"
import fs from "node:fs"
import path from "node:path"

/**
 * CC E2E — npm i -D @playwright/test && npx playwright install chromium
 * Uses _cc_instant.py on :8000 unless CC_E2E_SKIP_SERVER is set.
 */
function resolveCcPython(): string {
	if (process.env.CC_E2E_PYTHON) return process.env.CC_E2E_PYTHON
	const candidates = [".venv/bin/python3", "venv/bin/python3", "python3"]
	const root = process.cwd()
	for (const rel of candidates) {
		const p = path.join(root, rel)
		if (rel === "python3" || fs.existsSync(p)) return rel
	}
	return "python3"
}

const ccPython = resolveCcPython()
const isCi = !!process.env.CI

export default defineConfig({
	testDir: "tests/e2e",
	fullyParallel: false,
	workers: 1,
	retries: isCi ? 2 : 0,
	timeout: 60_000,
	expect: { timeout: 15_000 },
	forbidOnly: isCi,
	reporter: isCi
		? [["list"], ["junit", { outputFile: "test-results/playwright-junit.xml" }], ["html", { open: "never" }]]
		: [["list"]],
	outputDir: "test-results/playwright",
	use: {
		baseURL: process.env.CC_E2E_BASE_URL || "http://127.0.0.1:8000",
		trace: "on-first-retry",
		screenshot: "only-on-failure",
		video: "retain-on-failure",
		...devices["Desktop Chrome"],
	},
	webServer: process.env.CC_E2E_SKIP_SERVER
		? undefined
		: {
				command: `${ccPython} _cc_instant.py`,
				url: "http://127.0.0.1:8000/health",
				reuseExistingServer: !isCi,
				timeout: 120_000,
			},
})
