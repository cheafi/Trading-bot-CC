"""Execute dashboard assertions against the served bundle and app source."""

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run_dashboard_js(assertions: str) -> None:
    """Await returned assertion promises; no Alpine init or real network."""
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const helpers = fs.readFileSync('src/api/static/cc-helpers.js', 'utf8');
const source = fs.readFileSync('src/api/static/cc-app.js', 'utf8');
async function main() {
for (const variant of ['served bundle', 'standalone source']) {
    const storage = new Map();
    const context = vm.createContext({
        assert, URLSearchParams, console,
        location: {search: ''},
        localStorage: {
            getItem: key => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, String(value)),
            removeItem: key => storage.delete(key),
        },
        alerts: [],
        fetch: () => { throw new Error('Unexpected network access'); },
    });
    vm.runInContext(
        'window = globalThis; alert = message => alerts.push(message);',
        context);
    vm.runInContext(helpers, context,
        {filename: 'cc-helpers.js', timeout: 2000});
    if (variant === 'standalone source') {
        vm.runInContext(source, context,
            {filename: 'cc-app.js', timeout: 2000});
    }
    try {
        await vm.runInContext(
            'const app = cc(); const H = CCHelpers;\n' + ASSERTIONS,
            context, {filename: variant + ' assertions', timeout: 2000});
    } catch (error) {
        console.error(variant);
        throw error;
    }
}
console.log('dashboard assertions complete');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
""".replace("ASSERTIONS", json.dumps(assertions))
    result = subprocess.run(
        ["node", "-"],
        input=script,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Node can exit successfully with a never-settling promise and no handles.
    assert "dashboard assertions complete" in result.stdout, result.stderr
