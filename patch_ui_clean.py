import re
import sys

def main():
    try:
        with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # 1. Insert the Hero Card and Summary Banner
        hero_html = """        <template x-if="rankedOpps.rows.length > 0">
          <div class="mb-4 p-4 border border-[var(--bd2)] rounded bg-[var(--bg2)] flex flex-col gap-2 relative">
            <div class="absolute top-2 right-2 text-[10px] font-bold px-2 py-1 rounded bg-[var(--brand)] text-black">Closest to Action</div>
            <div class="flex items-center gap-3">
              <span class="text-xl font-bold text-white" x-text="rankedOpps.rows[0].ticker"></span>
              <span class="text-[10px] px-2 py-1 rounded font-bold pill" 
                    :class="rankedOpps.rows[0].action==='TRADE'?'pg':rankedOpps.rows[0].action==='PILOT'?'pp':rankedOpps.rows[0].action==='AVOID'?'pr':'pa'" 
                    x-text="rankedOpps.rows[0].action"></span>
            </div>
            <div class="grid grid-cols-4 gap-2 text-xs mb-2">
              <div><span class="text-[var(--t3)]">Trigger:</span> <span class="font-bold text-[var(--t1)]" x-text="rankedOpps.rows[0].entry_trigger || '—'"></span></div>
              <div><span class="text-[var(--t3)]">Stop:</span> <span class="font-bold text-[var(--red)]" x-text="(rankedOpps.rows[0].stop_price||0)>0?Number(rankedOpps.rows[0].stop_price||0).toFixed(2):'—'"></span></div>
              <div><span class="text-[var(--t3)]">Target:</span> <span class="font-bold text-[var(--green)]" x-text="(rankedOpps.rows[0].target_price||0)>0?Number(rankedOpps.rows[0].target_price||0).toFixed(2):'—'"></span></div>
              <div><span class="text-[var(--t3)]">R:R:</span> <span class="font-bold text-[var(--t1)]" x-text="(rankedOpps.rows[0].risk_reward||0).toFixed(1),'x'"></span></div>
            </div>
            <div class="text-[11px] text-[var(--t2)] border-t border-[var(--bd1)] pt-2 mt-1">
                <strong class="text-[var(--t1)]">Why now:</strong> <span x-text="rankedOpps.rows[0].why_now"></span><br/>
                <strong class="text-[var(--t1)] mt-1">Invalidates:</strong> <span class="text-[var(--red)]" x-text="rankedOpps.rows[0].invalidation"></span>
            </div>
          </div>
        </template>
        <template x-yf="rankedOpps.rows.length > 0 && !rankedOpps.rows.find(r => r.action === 'TRADE')">
          <div class="mb-4 p-2 text-[10px] text-[var(--t2)] bg-[var(--bg1)] border border-[var(--bd1)] rounded">
              <strong class="text-[var(--purple)]">No TRADE conviction today. Summarizing headwinds:</strong><br/>
              <span x-text="'Failed structurally (AVOID): ' + rankedOpps.rows.filter(r => r.action === 'AVOID').length"></span> |
              <span x-text="'Needs specific triggers (WATCH): ' + rankedOpps.rows.filter(r => r.action === 'WATCH').length"></span> |
              <span x-text="'High risk/half-size limits (PILOT): ' + rankedOpps.rows.filter(r => r.action === 'PILOT').length"></span>
          </div>
        </template>
        <template x-if="rankedOpps.rows.length>0">"""
        
        html = html.replace('<template x-if="rankedOpps.rows.length>0">', hero_html, 1)

        # 2. Update background strip logic
        html = html.replace(
            """<div :style=,"height:3px;background:var(--'+(r.action==='TRADE'||r.action==='BUY'?'green':r.action==='NO_TRADE'||r.action==='AVOID'?'red':'amber'))')'"></div>""",
            """<div :style="'height:3px;background:var(--'+(r.action==='TRADE'||r.action==='BUY'?'green':r.action==='PILOT'?'purple':r.action==='NO_TRADE'||r.action==='AVOID'?'red':'amber')+')'"></div>"""
        )

        # 3. Update capsule badge logic
        html = html.replace(
            """<span class="pill text-[8px] font-bold ml-auto" :class="r.action==='TRADE'||r.action==='BUY'?'pg':r.action==='NO_TRADE'||r.action==='AVOID'?'pr':'pa'" x-text="r.action||'—'"></span>""",
            """<span class="pill text-[8px] font-bold ml-auto" :class="r.action==='TRADE'||r.action==='BUY'?'pg':r.action==='PILOT'?'pp':r.action==='NO_TRADE'||r.action==='AVOID'?'pr':'pa'" x-text="r.action||'—'"></span>"""
        )
        
        # 4. Replace the old verbose why_not block with the 3 drivers inline layout
        old_why_not = """          <template x-if="r.why_not">
                  <div class="text-[10px] mt-2 mb-1" style="color:var(--t2);line-height:1.3;border-left:2px solid var(--red);padding-left:6px">
                    <strong class="text-[10px]" style="color:var(--red)">Why Not:</strong>
                    <span x-text="r.why_not"></span>
                  </div>
                </template>"""
        
        new_why_not = """                <div class="flex items-center gap-4 text-[10px] mt-2 border-t border-[var(--bd1)] pt-2">
                  <span :class="(r.trigger_quality||0) >= 7 ? 'text-[var(--green)]' : 'text-[var(--t3)]'">
                      �7 Trigger Quality: <span x-text="(r.trigger_quality||0)+'/10'"></span>
                  </span>
                  <span :class="(r.relative_strength||0) > 0.3 ? 'text-[var(--purple)]' : 'text-[var(--t3)]'">
                      📡 Rel Strength: <span x-text="(r.relative_strength||0).toFixed(2)"></span>
                  </span>
                  <template x-if="r.runner_up && r.runner_up.ticker">
                     <span class="text-[var(--orange)] font-bold">
                         ⚠ Laggard (Consider <span x-text="r.runner_up.ticker"></span>)
                     </span>
                  </template>
                  <template x-if="!r.runner_up">
                     <span class="text-[var(--t3)] italic" x-text="r.why_not||''b"></span>
                  </template>
                </div>"""

        replaced = False
        if old_why_not in html:
            html = html.replace(old_why_not, new_why_not)
            replaced = True

        with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("-- Successfully patched index.html --")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()