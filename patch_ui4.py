import re

with open("src/api/templates/index.html", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "<!-- Ranked Cards -->" in line:
        new_lines.append(line)
        new_lines.append(
            """        <div style="padding:0 12px;display:flex;flex-direction:column;gap:6px">
        <template x-if="rankedOpps.rows.length > 0 && rankedOpps.rows.find(r => r.action !== 'AVOID')">
          <div x-data="{ bestIdea: rankedOpps.rows.find(r => r.action !== 'AVOID') }" class="mb-4 p-4 border border-[var(--bd2)] rounded bg-[var(--bg2)] flex flex-col gap-2 relative">
            <div class="absolute top-2 right-2 text-[10px] font-bold px-2 py-1 rounded bg-[var(--brand)] text-black">Best Near-Miss</div>
            <div class="flex items-center gap-3">
              <span class="text-xl font-bold text-white" x-text="bestIdea.ticker"></span>
              <span class="text-[10px] px-2 py-1 rounded font-bold pill" 
                    :class="bestIdea.action==='TRADE'?'pg':bestIdea.action==='PILOT'?'pp':'pa'"
                    x-text="bestIdea.action"></span>
            </div>
            
            <template x-if="(bestIdea.entry_trigger && bestIdea.entry_trigger !== '—') || (bestIdea.target_price||0)>0">
              <div class="grid grid-cols-4 gap-2 text-xs mb-2">
                <div><span class="text-[var(--t3)]">Trigger:</span> <span class="font-bold text-[var(--t1)]" x-text="bestIdea.entry_trigger || '—'"></span></div> 
                <div><span class="text-[var(--t3)]">Stop:</span> <span class="font-bold text-[var(--red)]" x-text="(bestIdea.stop_price||0)>0?Number(bestIdea.stop_price||0).toFixed(2):'—'"></span></div>
                <div><span class="text-[var(--t3)]">Target:</span> <span class="font-bold text-[var(--green)]" x-text="(bestIdea.target_price||0)>0?Number(bestIdea.target_price||0).toFixed(2):'—'"></span></div>
                <div><span class="text-[var(--t3)]">R:R:</span> <span class="font-bold text-[var(--t1)]" x-text="(bestIdea.risk_reward||0)>0?(bestIdea.risk_reward||0).toFixed(1)+'x':'—'"></span></div>
              </div>
            </template>
            
            <div class="text-[11px] text-[var(--t2)] border-t border-[var(--bd1)] pt-2 mt-1">
                <strong class="text-[var(--t1)]">Why now:</strong> <span x-text="bestIdea.why_now"></span><br/>
                <strong class="text-[var(--amber)] mt-1">Upgrade condition:</strong> <span class="text-[var(--t1)]" x-text="bestIdea.invalidation || 'Breakout with volume'"></span>
            </div>
          </div>
        </template>
        
        <template x-if="rankedOpps.rows.length > 0 && !rankedOpps.rows.find(r => r.action === 'TRADE')">
          <div class="mb-4 p-3 text-[10px] text-[var(--t2)] bg-[var(--bg1)] border border-[var(--bd1)] rounded">
              <strong class="text-[var(--purple)] uppercase tracking-wider mb-2 block">Why No Trades Today — Blockers</strong>
              <div class="grid grid-cols-2 gap-2 mb-2">
                <div><span class="text-[var(--red)]">■</span> Failed Thesis: <strong class="text-white" x-text="rankedOpps.rows.filter(r => (r.thesis_conf||0) < 0.5).length"></strong></div>
                <div><span class="text-[var(--amber)]">■</span> Failed Timing: <strong class="text-white" x-text="rankedOpps.rows.filter(r => (r.timing_conf||0) < 0.5).length"></strong></div>
                <div><span class="text-[var(--blue)]">■</span> Missing Trigger: <strong class="text-white" x-text="rankedOpps.rows.filter(r => (r.action==='WATCH'||r.action==='AVOID'||!r.entry_trigger||r.entry_trigger==='—')).length"></strong></div>
                <div><span class="text-[var(--t3)]">■</span> Failed R:R: <strong class="text-white" x-text="rankedOpps.rows.filter(r => (r.risk_reward||0) < 1.0).length"></strong></div>
              </div>
              <div class="border-t border-[var(--bd2)] pt-2 mt-1">
                <span x-text="'Failed structurally (AVOID): ' + rankedOpps.rows.filter(r => r.action === 'AVOID').length"></span> | 
                <span x-text="'Needs specific triggers (WATCH): ' + rankedOpps.rows.filter(r => r.action === 'WATCH').length"></span> | 
                <span x-text="'High risk/half-size limits (PILOT): ' + rankedOpps.rows.filter(r => r.action === 'PILOT').length"></span>
              </div>
          </div>
        </template>\n"""
        )
        skip = True
        continue

    if skip:
        # Stop skipping when we reach the template that iterates the cards
        if '<template x-if="rankedOpps.rows.length>0">' in line.replace(" ", ""):
            skip = False

    if not skip:
        new_lines.append(line)

with open("src/api/templates/index.html", "w") as f:
    f.writelines(new_lines)
