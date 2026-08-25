import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Restore AI narrative decoupling
new_card = """      <!-- ── AI Analysis Card ── -->
      <div style="padding:0 12px 8px">
        <div class="card card-p" style="padding:12px;border-left:3px solid #8b5cf6;background:linear-gradient(135deg,rgba(139,92,246,.06),rgba(139,92,246,.02))">
          <div class="flex items-center justify-between mb-1">
            <div class="flex items-center gap-2">
              <span style="font-size:12px">✨</span>
              <span class="text-xs font-bold uppercase" style="color:#a78bfa">AI Analysis</span>
              <template x-if="today7.trust?.ai_powered">
                <span style="padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;background:#7c3aed;color:#e9d5ff">NVIDIA NIM</span>
              </template>
            </div>
            <template x-if="!today7.ai_narrative && !today7.ai_loading">
              <button @click="fetchAINarrative()" class="btn-s text-[10px]" style="padding:2px 6px">Generate</button>
            </template>
            <template x-if="today7.ai_loading">
              <span class="text-[10px]" style="color:#a78bfa;font-style:italic">Thinking...</span>
            </template>
          </div>
          <template x-if="today7.ai_narrative">
            <div class="text-[11px] mt-2" style="color:var(--t1);line-height:1.7;white-space:pre-wrap" x-text="today7.ai_narrative"></div>
          </template>
        </div>
      </div>"""

# Ensure we haven't already applied it
if "fetchAINarrative" not in text:
    text = re.sub(
        r"<!-- ── AI Analysis Card ── -->.*?</template>\n\n\s*<!-- ── Regime Action Banner ── -->",
        new_card + "\n\n      <!-- ── Regime Action Banner ── -->",
        text,
        flags=re.DOTALL,
    )

    text = text.replace("ai_narrative:null,", "ai_narrative:null,ai_loading:false,")

    fetch_method = """      },
      async fetchAINarrative(){
        if(this.today7.ai_loading) return;
        this.today7.ai_loading=true;
        try{
            const r=await fetch('/api/v7/today/ai-narrative', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    regime_ctx:this.today7.regime,
                    top_5:this.today7.top_ranked,
                    market_pulse:this.today7.pulse,
                    filter_funnel:this.today7.filter_funnel
                })
            });
            if(r.ok){
                const d=await r.json();
                if(d.ai_narrative){
                    this.today7.ai_narrative=d.ai_narrative;
                    this.today7.trust.ai_powered=true;
                } else {
                    this.today7.ai_narrative="AI Analysis unavailable or not configured.";
                }
            }
        }catch(e){
            console.warn('fetchAINarrative failed',e);
            this.today7.ai_narrative="AI Analysis request failed.";
        }finally{
            this.today7.ai_loading=false;
        }
      },
      async fetchOpps(){"""

    text = text.replace("      },\n      async fetchOpps(){", fetch_method)

# 2. Fix the Scanner fallback (it was done earlier, if it reverted, let's restore it)
if "alert('Scanner Error" not in text:
    # We update the inline ⚡ Force Live Scan
    new_btn = """<button @click="fetch('/api/v7/opportunity-scanner?regime='+(regime.label||'BULL')+'&force_refresh=true').then(r=>{if(!r.ok){r.json().then(e=>alert('Scanner Error: '+(e.detail||'Failed')));throw new Error('Scanner failed');}return r.json()}).then(d=>{if(d.candidates&&d.candidates.length){rankedOpps.rows=d.candidates.slice(0,30).map((c,i)=>({ticker:c.ticker||c.symbol,score:c.score||0,action:c.tag||'WATCH',sector_type:c.sector||'',entry_price:c.close,stop_price:c.stop_loss,target_price:c.activation,risk_reward:c.rr||0,setup:c.engine||'scanner',grade:c.score>=8?'A':c.score>=6?'B':'C',thesis_conf:0.6,timing_conf:0.5,exec_conf:0.5,data_conf:0.7,why_now:c.tags?c.tags.join(' · '):''}));rankedOpps.source='scanner';loadSparklines(rankedOpps.rows)}}).catch(e=>{})" class="btn-p text-[10px]">⚡ Force Live Scan</button>"""
    old_btn = r"""<button @click="fetch\('/api/v7/opportunity-scanner\?regime='\+\(regime\.label\|\|'BULL'\)\+'&force_refresh=true'\)\.then\(r=>r\.json\(\)\)\.then\(d=>\{if\(d\.candidates&&d\.candidates\.length\).*?\)" class="btn-p text-\[10px\]">⚡ Force Live Scan</button>"""
    text = re.sub(old_btn, new_btn, text, flags=re.DOTALL)

# 3. Apply the tabs array modification to consolidate the tabs!
new_tabs = """      tabs:[
        {id:'today',icon:'🎯',label:'Dashboard'},
        {id:'signals',icon:'📋',label:'Playbook'},
        {id:'scanners',icon:'🔬',label:'Discovery'},
        {id:'portfolio',icon:'💼',label:'Portfolio & Risk'},
        {id:'dossier',icon:'🔍',label:'Search / Dossier'},
      ],
      moreTabs:[
        {id:'ops',icon:'⚙️',label:'System Ops'},
        {id:'ibkr',icon:'🏦',label:'IBKR Status'},
        {id:'guide',icon:'📖',label:'Guide'},
      ],"""
text = re.sub(
    r"      tabs:\[\n\s*\{id:'today.*?      \],", new_tabs, text, flags=re.DOTALL
)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)
