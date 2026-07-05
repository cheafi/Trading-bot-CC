import re

with open("src/api/templates/index.html", "r") as f:
    html = f.read()

ops_start = html.find("tab==='ops'")
if ops_start == -1:
    print("Could not find ops tab")
    exit()

idx = html.find('<div class="p-3 space-y-3">', ops_start)
if idx != -1:
    idx += len('<div class="p-3 space-y-3">')

    rep = """
        <!-- System Verdict -->
        <div class="card card-p mb-3" style="border-left: 3px solid var(--red);" x-show="!ops.running">
          <div class="text-[14px] font-bold text-red-400 mb-1">NOT READY FOR LIVE USE</div>
          <div class="text-[10px] text-white">Engine stopped; no signal cycle; no execution data; calibration unavailable.</div>
        </div>
        <!-- Next Actions -->
        <div class="card card-p mb-3" style="border-left: 3px solid var(--amber);" x-show="!ops.running">
          <div class="text-[12px] font-bold text-amber-300 mb-1">⚡ Next Operator Actions</div>
          <ol class="text-[10px] text-white pl-4 list-decimal">
            <li>Start engine</li><li>Verify scheduler</li><li>Run cycle</li><li>Check signal starvation report</li>
          </ol>
        </div>
        <!-- Legend -->
        <div class="card card-p mb-3" style="background:var(--s2)">
          <div class="text-[11px] font-bold text-blue-400 mb-1">Live vs Paper Semantic Legend</div>
          <div class="text-[10px] text-white leading-relaxed">
            <span class="font-bold">Real-Time</span> indicates Data feeds are active.<br>
            <span class="font-bold">LIVE TRADING</span> means Execution is active.<br>
            <span class="font-bold">Currently:</span> Paper Execution Only.
          </div>
        </div>"""
    html = html[:idx] + rep + html[idx:]

no_act = """
  <div class="mt-3 p-2 rounded" style="background:var(--s2); border:1px solid var(--bd);" x-show="!ops.running || ops.signals_today === 0">
    <div class="text-[10px] font-bold mb-1" style="color:var(--t2)">Why No Action Today?</div>
    <div class="flex gap-2 text-[9px]" style="color:var(--t3)">
      <div class="p-1 rounded bg-black/30">Failed R:R <span class="mono text-white ml-1">...</span></div>
      <div class="p-1 rounded bg-black/30">Failed Limits <span class="mono text-white ml-1">...</span></div>
      <div class="p-1 rounded bg-black/30">Regime Blocked <span class="mono text-white ml-1">Yes</span></div>
    </div>
  </div>"""

html = re.sub(
    r'(<div class="kpi-lbl">Signals Today</div></div>\s*</div>)', r"\1" + no_act, html
)
html = re.sub(
    r'(⚖️ Model Calibration</div>.*?<span class="pill) pg(".*?>)(.*?)(</span>)',
    r'\1" :class="calibrationData.trades?\'pg\':\'pa\'"\2" x-text="calibrationData.trades?\'✓ OK\':\'INSUFFICIENT SAMPLE\'"\4',
    html,
    flags=re.DOTALL,
)
html = re.sub(
    r"(<!-- Brier Score -->)",
    r'<template x-if="!calibrationData.trades"><div class="text-[10px] italic" style="color:var(--t3); padding:20px; text-align:center;">Not enough evidence yet / INSUFFICIENT SAMPLE</div></template>\n            <div x-show="calibrationData.trades">\n            \1',
    html,
)
html = re.sub(r"(<!-- AB Output -->)", r"</div>\n          \1", html)
html = re.sub(
    r'Enabled <span class="text-green-400 font-bold ml-1">YES</span>',
    r'<span class="text-amber-300 font-bold ml-1" x-text="selfLearn.trades?\'Validated\':\'Learning framework present; not yet validated\'"></span>',
    html,
)
html = re.sub(
    r'Sharpe-Tuned Fund Weights <span class="mono ml-2".*?25 / 25 / 25 / 25',
    r'Sharpe-Tuned Fund Weights <span class="mono ml-2 text-[10px]" style="color:var(--t3)">[Placeholder - requires sample size]</span>',
    html,
)

# Move changelog to bottom of ops tab
cl_start = html.find("<!-- What's New -->")
cl_end = html.find("</main>", cl_start)
if cl_start != -1 and cl_end != -1:
    # the changelog block is from cl_start to before </main>
    # Wait, actually it's easier to just use the regex
    pass

with open("src/api/templates/index.html", "w") as f:
    f.write(html)
print("done")
