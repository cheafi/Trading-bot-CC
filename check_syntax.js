
    function cc(){return{
      tab:'today',
      disclaimerAccepted:localStorage.getItem('cc_disclaimer_ok')==='1',
      tabs:[
        {id:'today',icon:'🎯',label:'Dashboard'},
        {id:'signals',icon:'📋',label:'Playbook'},
        {id:'scanners',icon:'🔬',label:'Discovery'},
        {id:'portfolio',icon:'💼',label:'Portfolio & Risk'},
        {id:'dossier',icon:'🔍',label:'Search / Dossier'},
      ],
      moreTabs:[
        // ops, ibkr, guide demoted — accessible via top-bar pills (mode→ops, ibkr→ibkr, ?→guide modal)
      ],

      showMore:false,
      showGuideModal:false,
      cc_status:{mode:'OFF',breaker:false,breaker_reason:'',ibkr_connected:false,ibkr_mode:'paper',uptime_s:0,last_fetch:0},
      live:false,clock:'',regime:{},indices:[],macro:[],sectors:[],asia:[],trust:{},
      sig:{mode:'—',source:'',as_of:'',recs:[],strategy_scores:{},no_trade_reason:null,scan_meta:null},
      dos:{ticker:'',loading:false,data:null,error:'',showSignals:true,chartPeriod:'6mo',benchPeriod:'1y',chartSignals:[],benchStats:null,benchSummary:null,benchMonthly:null,benchQuarterly:null,benchYearly:null,benchTab:'monthly',buyPrice:'',advice:null,adviceLoading:false,peers:null,peersLoading:false},
      pf:{loading:false,source:'manual',positions:[],alerts:[],summary:null,corrPreview:null,showAdd:false,addTicker:'',addShares:0,addEntry:0,addStop:0,addT1r:0,addT2r:0,addNotes:'',editTicker:null},
      factory:{loading:false,ticker:'SPY',period:'2y',mode:'demo',result:null,detail:null,showDetail:false,sortBy:'score'},
      brief:{loading:false,data:null},
      bt:{ticker:'AAPL',strategy:'all',period:'5y',loading:false,result:null},
      // ── DEAD-CODE WARNING (no UI binding, kept only because JS methods still reference them) ──
      // To be removed once the corresponding fetch* methods are deleted: factory, benchBT, fundMonitor, pmStrip, tradeIntel, tt, bt
      // Already deleted (true orphans): perfTracker, fundLab, modelFunds, tradeJournal, apiEndpoints, oppScanner, rsData, rsFilter, rejectsData, noTradeData
      benchBT:{period:'5y',benchmark:'SPY',loading:false,data:null,error:''},
      fundMonitor:{loading:false,data:null,error:'',lastRefresh:null,autoRefreshTimer:null,benchmark:'SPY',activeFund:null},
      pmStrip:{funds:[],lastFetch:0},
      tradeIntel:{loading:false,data:null,error:'',confData:null,mistakesData:null,aiLoading:false,aiError:'',aiReview:null,selectedTradeKey:''},
      tt:{ticker:'SPY',date:new Date(Date.now()-5*86400000).toISOString().slice(0,10),strategy:'all',loading:false,result:null},
      ibkr:{connected:false,mode:'paper',host:'127.0.0.1',loading:false,pingResult:null,account:null,positions:[],orderForm:{symbol:'',secType:'STK',action:'BUY',qty:1,orderType:'MKT',limitPrice:'',useBracket:false,stopPrice:'',targetPrice:'',trail:false,trailKind:'percent',trailValue:''},orderResult:null,orderError:'',statusLoading:false,lastRefresh:null,workingBracket:null,bracketArchive:[]},
      ops:{running:false,cycle_count:0,signals_today:0,trades_today:0,circuit_breaker:false,circuit_breaker_reason:'',dry_run:true,components:{}},
      opsDetail:{},
      today7:{regime:null,top_ranked:[],filter_funnel:null,avoid_list:[],tradeability:'',what_changed:[],event_risks:[],best_family:null,pulse:null,narrative:'',ai_narrative:null,ai_loading:false,ai_provider:'',ai_model:'',date:'',trust:{}},
      opps:[],oppsSort:'score',
      changelog:[],
      selfLearn:{status:null,triggering:false,lastResult:'',calibration:null,calibBuckets:null,ab:null,ledger:null,lastAutoSchedule:null,feedback:null},
      stratHealth:{loading:false,data:null,window:30,err:''},
      histVar:{loading:false,data:null,err:'',last_run:0},
      freshness:null,
      risk_alerts:null,
      alerts_history:null,
      showAlertsModal:false,
      brief_status:null,
      brief_regen_loading:false,
      tt:{show:false,ticker:'AAPL',date:'',strategy:'all',loading:false,data:null,err:''},
      exec:{metrics:null},
      risk:{summary:null},
      rl:{thompson:null,featureIC:null},
      notifyLog:{events:[],discord_configured:false,loading:false},
      scannerHub:{loading:false,data:null,category:null,duration_ms:0,last_run:null,universe:0,error:''},
      rankedOpps:{loading:false,rows:[],actionFilter:'',sectorFilter:'',source:'playbook'},
      flowData:{profiles:[],unusual_activity:[]},
      cmd:{
        loading:false,
        activeTicker:'',
        decision:null,
        agent:null,
        agentError:'',
        agentJournal:[],
        agentReliability:null,
        agentReliabilityError:'',
        agentReliabilityLoading:false,
        watchlistRows:[],   // [{ticker,action,confidence,rs_state}]
        error:'',
      },
      _failCount:0,
      _retryTimer:null,
      _fundRetryTimer:null,
      apiError:'',
      healthData:null,
      ac:{query:'',results:[],show:false,target:'',selIdx:-1,timer:null},
      ccStarred:JSON.parse(localStorage.getItem('ccStarred')||'{}'),
      ccLoved:JSON.parse(localStorage.getItem('ccLoved')||'{}'),
      ccWatchlist:JSON.parse(localStorage.getItem('ccWatchlist')||'{}'),
      init(){
        this.tick();setInterval(()=>this.tick(),1000);
        this.fetchSignals();setInterval(()=>this.fetchSignals(),60000);
        this.fetchToday7();setInterval(()=>this.fetchToday7(),120000);
        this.fetchCcStatus();setInterval(()=>this.fetchCcStatus(),30000);
        this.fetchPortfolio();setInterval(()=>this.fetchPortfolio(),180000);
        // Per-strategy realized analytics (cheap; refresh every 10min)
        this.fetchStrategyHealth();setInterval(()=>this.fetchStrategyHealth(),600000);
        // Data freshness watchdog (every 60s; cheap — already-cached histories)
        this.fetchFreshness();setInterval(()=>this.fetchFreshness(),60000);
        // Position-level risk alerts (every 60s)
        this.fetchRiskAlerts();setInterval(()=>this.fetchRiskAlerts(),60000);
        // Morning brief freshness check (every 5 min — cheap, just stats a file)
        this.fetchBriefStatus();setInterval(()=>this.fetchBriefStatus(),300000);
        if(!localStorage.getItem('cc_guide_seen')){this.showGuideModal=true;localStorage.setItem('cc_guide_seen','1')}
      },
      async fetchStrategyHealth(){
        // Per-strategy realized Sharpe / hit-rate / expectancy from closed-trade ledger.
        this.stratHealth.loading=true;this.stratHealth.err='';
        try{
          const w=Number(this.stratHealth.window)||30;
          const r=await fetch('/api/strategy-health/per-strategy?window='+w,{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok){this.stratHealth.err='HTTP '+r.status;this.stratHealth.data=null;return;}
          this.stratHealth.data=await r.json();
        }catch(e){this.stratHealth.err=e.message;this.stratHealth.data=null;}
        finally{this.stratHealth.loading=false}
      },
      async fetchFreshness(){
        try{
          const r=await fetch('/api/data/freshness');
          if(!r.ok)return;
          this.freshness=await r.json();
        }catch(e){/* silent — pill simply won't show */}
      },
      async fetchRiskAlerts(){
        // Position-level risk scan: stop proximity/breach, drawdown, concentration, stale quotes
        try{
          const r=await fetch('/api/portfolio/risk-alerts',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)return;
          this.risk_alerts=await r.json();
        }catch(e){/* silent — pill simply won't show */}
      },
      async fetchAlertsHistory(){
        try{
          const r=await fetch('/api/portfolio/alerts-history?limit=50',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)return;
          this.alerts_history=await r.json();
        }catch(e){/* silent */}
      },
      async clearAlertDedupe(){
        try{
          await fetch('/api/portfolio/alerts-clear-dedupe',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          this.fetchRiskAlerts();
        }catch(e){}
      },
      openReplayForDossier(){
        // Pre-fill Time-Travel modal with current dossier ticker, defaulting to 30 days ago.
        const tk=(this.dos?.ticker||'').trim().toUpperCase();
        if(!tk){alert('No ticker selected in dossier');return;}
        const d=new Date();d.setDate(d.getDate()-30);
        this.tt.ticker=tk;
        this.tt.date=d.toISOString().slice(0,10);
        this.tt.strategy='all';
        this.tt.data=null;this.tt.err='';
        this.tt.show=true;
      },
      async runTimeTravel(){
        const tk=(this.tt.ticker||'').trim().toUpperCase();
        const dt=this.tt.date;
        if(!tk||!dt){this.tt.err='Ticker + date required';return;}
        this.tt.err='';this.tt.loading=true;this.tt.data=null;
        try{
          const url='/api/live/time-travel?ticker='+encodeURIComponent(tk)+'&target_date='+encodeURIComponent(dt)+'&strategy='+encodeURIComponent(this.tt.strategy||'all');
          const r=await fetch(url,{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok){
            let msg='HTTP '+r.status;
            try{const j=await r.json();msg=j.detail||j.error||msg;}catch(e){}
            this.tt.err=msg;return;
          }
          this.tt.data=await r.json();
        }catch(e){this.tt.err=e.message}
        finally{this.tt.loading=false}
      },
      async fetchBriefStatus(){
        try{
          const r=await fetch('/api/brief/status',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)return;
          this.brief_status=await r.json();
        }catch(e){/* silent */}
      },
      async regenerateBrief(){
        if(!confirm('Regenerate morning brief now? Runs the generator (≈60s).'))return;
        this.brief_regen_loading=true;
        try{
          const r=await fetch('/api/brief/regenerate',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          const j=await r.json();
          if(j.ok){alert('✓ Brief regenerated: '+(j.after?.date||'')+' — '+(j.after?.size_bytes||0)+' bytes')}
          else{alert('⛔ Regen failed: '+(j.error||j.stderr_tail||'unknown'))}
          this.fetchBriefStatus();
        }catch(e){alert('Regen error: '+e.message)}
        finally{this.brief_regen_loading=false}
      },
      async rotateAlerts(){
        if(!confirm('Trim data/alerts.jsonl to last 5000 rows? Older rows archived to .bak'))return;
        try{
          const r=await fetch('/api/portfolio/alerts-rotate?keep=5000',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          const j=await r.json();
          alert(j.ok?('✓ Rotated: trimmed '+j.trimmed+', remaining '+j.remaining+(j.archive?' → '+j.archive:'')):'⛔ '+(j.error||'failed'));
          this.fetchAlertsHistory();
        }catch(e){alert('Rotate error: '+e.message)}
      },
      async fetchCcStatus(){
        try{
          const r=await fetch('/api/ops/status');
          if(!r.ok)return;
          const d=await r.json();
          this.opsDetail = d;
          this.ops = d.engine || {};
          const eng = d.engine || {};
          this.cc_status.mode=eng.dry_run===false?'LIVE':(eng.running?'PAPER':'OFF');
          this.cc_status.breaker=!!eng.circuit_breaker;
          this.cc_status.breaker_reason=eng.circuit_breaker_reason||'';
          this.cc_status.uptime_s=d.uptime_seconds||0;
          this.live=eng.running===true;
          if(d.trust)this.trust=d.trust;
        }catch(e){this.cc_status.mode='OFF';this.live=false}
        try{
          const r2=await fetch('/api/ibkr/status');
          if(r2.ok){
            const d2=await r2.json();
            this.cc_status.ibkr_connected=!!d2.connected;
            this.cc_status.ibkr_mode=(d2.mode||'paper').toLowerCase();
          }
        }catch(e){}
        this.cc_status.last_fetch=Date.now();
      },
      tick(){this.clock=new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'})},
      toggleStar(ticker){this.ccStarred[ticker]=!this.ccStarred[ticker];localStorage.setItem('ccStarred',JSON.stringify(this.ccStarred))},
      toggleLove(ticker){this.ccLoved[ticker]=!this.ccLoved[ticker];localStorage.setItem('ccLoved',JSON.stringify(this.ccLoved))},
      toggleWatchlist(ticker){this.ccWatchlist[ticker]=!this.ccWatchlist[ticker];localStorage.setItem('ccWatchlist',JSON.stringify(this.ccWatchlist))},
      switchTab(t){
        this.tab=t;
        if(t==='today'){this.fetchToday7();}
        if(t==='signals'){this.fetchSignals();}
        if(t==='scanners'){this.fetchScanners();}
        if(t==='portfolio'){this.fetchPortfolio();}
        if(t==='dossier'){this.fetchDossier();}
      },

      cmdActionColor(action){
        return({TRADE:'var(--green)',WATCH:'var(--amber)',WAIT:'var(--t3)',NO_TRADE:'var(--red)',REJECT:'var(--red)'})[action]||'var(--t3)';
      },
      cmdConfColor(v){
        return v>=70?'var(--green)':v>=50?'var(--amber)':'var(--red)';
      },

      acInput(val,target){
        this.ac.target=target;
        if(this.ac.timer)clearTimeout(this.ac.timer);
        if(!val||val.length<1){this.ac.results=[];this.ac.show=false;return}
        this.ac.timer=setTimeout(async()=>{
          try{const r=await fetch('/api/tickers?q='+encodeURIComponent(val));if(r.ok){const d=await r.json();this.ac.results=d.results||[];this.ac.show=this.ac.results.length>0;this.ac.selIdx=-1}}catch(e){this.ac.show=false}
        },150);
      },
      acSelect(item){
        const t=this.ac.target;
        if(t==='dos')this.dos.ticker=item.s;
        // 'opt','bt','tt' targets removed — dead routes (sprint-dead-route-purge)
        this.ac.show=false;this.ac.results=[];this.ac.selIdx=-1;
      },
      acKey(e){
        if(!this.ac.show)return;
        if(e.key==='ArrowDown'){e.preventDefault();this.ac.selIdx=Math.min(this.ac.selIdx+1,this.ac.results.length-1)}
        else if(e.key==='ArrowUp'){e.preventDefault();this.ac.selIdx=Math.max(this.ac.selIdx-1,0)}
        else if(e.key==='Enter'&&this.ac.selIdx>=0){e.preventDefault();this.acSelect(this.ac.results[this.ac.selIdx])}
        else if(e.key==='Escape'){this.ac.show=false}
      },
      _clearRetry(){if(this._retryTimer){clearTimeout(this._retryTimer);this._retryTimer=null}},
      dosEquity(){const s=this.pf&&this.pf.summary;return (s&&(s.account_equity||s.equity||s.total_value))||100000;},
      stratSpark(curve){
        // Render cumulative R curve to a 40×14 SVG path.
        if(!curve||curve.length<2)return '';
        const w=40,h=14,pad=1;
        const lo=Math.min(...curve), hi=Math.max(...curve);
        const range=Math.max(0.01, hi-lo);
        const step=(w-2*pad)/(curve.length-1);
        const pts=curve.map((v,i)=>{
          const x=pad+i*step;
          const y=h-pad-((v-lo)/range)*(h-2*pad);
          return (i===0?'M':'L')+x.toFixed(1)+','+y.toFixed(1);
        });
        return pts.join(' ');
      },
      pfRisk(){
        const positions=(this.pf&&this.pf.positions)||[];
        const summary=this.pf&&this.pf.summary;
        const equity=(summary&&(summary.total_value||summary.account_equity))||100000;
        let heatDollars=0,topVal=0,topTicker='';
        let posVolWeighted=0; // Σ (weight_i × σ_i)  — naive but position-aware
        let hasRealVol=false;
        for(const p of positions){
          const px=p.current_price||p.last_price||p.entry_price||0;
          const stop=p.stop_price||p.stop||0;
          const sh=p.shares||p.quantity||0;
          if(px&&stop&&sh){heatDollars+=Math.max(0,(px-stop)*sh);}
          const val=(px*sh)||p.market_value||0;
          if(val>topVal){topVal=val;topTicker=p.ticker||p.symbol||'';}
          // Per-position vol if available (from backend hydration)
          // Falls back to 2% if not present — flagged via hasRealVol
          const sigma = p.daily_vol || p.atr_pct || null;
          if (sigma != null) { hasRealVol = true; }
          const w = equity > 0 ? val / equity : 0;
          posVolWeighted += w * (sigma != null ? sigma : 0.02);
        }
        const heatPct=equity>0?(heatDollars/equity)*100:0;
        const heatR=heatDollars/Math.max(1,equity*0.01); // each 1R = 1% equity
        // VaR-95: prefer historical-simulation (real 1y returns) when available,
        // fall back to position-weighted parametric (1.65σ) — honest fallback.
        let var95, var95Pct, var95Quality, var95Tier=null, var95Sample=null, var95Warning=null;
        const hv = this.histVar && this.histVar.data;
        if (hv && hv.method === 'historical_sim' && hv.var_95_dollar != null) {
          // Historical-sim wins — backend returned a real percentile
          var95 = Math.round(Math.abs(hv.var_95_dollar));
          var95Pct = Math.abs(hv.var_95_pct || 0);
          var95Quality = 'historical';
          var95Tier = hv.tier || 'HISTSIM';
          var95Sample = hv.sample_size;
          var95Warning = hv.warning || null;
        } else {
          const portfolioVol = positions.length > 0 ? posVolWeighted : 0.02;
          var95=Math.round(equity*portfolioVol*1.65);
          var95Pct=(var95/equity)*100;
          var95Quality = hasRealVol ? 'position-vol' : 'estimate';
        }
        const topPct=equity>0?(topVal/equity)*100:0;
        const heatColor=heatPct>=6?'red':heatPct>=4?'amber':'green';
        const heatPctClass=heatPct>=6?'text-red-400':heatPct>=4?'text-amber-300':'text-green-400';
        return{equity,heatDollars,heatPct,heatR,count:positions.length,topPct,topTicker,var95,var95Pct,var95Quality,var95Tier,var95Sample,var95Warning,heatColor,heatPctClass};
      },
      dosVerdict(){
        const d=this.dos&&this.dos.data; if(!d)return{label:'—',pill:'pw',color:'border',conf:0,reason:''};
        const conf=((d.confidence||d.signal?.confidence)?.final)||0;
        const tradeOK=d.regime?d.regime.should_trade!==false:true;
        const conflict=((d.conflict||d.signal?.conflict)?.conflict_level)||'LOW';
        const sect=d.sector||d.signal?.sector||{};
        const leader=sect.leader_status==='LEADER';
        if(!tradeOK)return{label:'NO TRADE',pill:'pr',color:'red',conf,reason:'Regime gate is OFF — VIX/breadth unfavorable. Sit out.'};
        if(conflict==='HIGH')return{label:'AVOID',pill:'pr',color:'red',conf,reason:'High signal conflict — wait for confirmation.'};
        if(conf>=0.7&&conflict==='LOW'&&leader)return{label:'TRADE',pill:'pg',color:'green',conf,reason:'High conviction · low conflict · sector leader. Size at 1R.'};
        if(conf>=0.55&&conflict!=='HIGH')return{label:'WATCH',pill:'pa',color:'amber',conf,reason:'Setup forming — monitor for trigger; do not chase.'};
        return{label:'PASS',pill:'pw',color:'border',conf,reason:'Insufficient conviction. Look elsewhere.'};
      },
      async fetchSignals(){
        try{const r=await fetch('/api/recommendations');if(!r.ok)throw 0;const d=await r.json();this.sig.mode=d.mode||'—';this.sig.source=d.source||'';this.sig.as_of=d.as_of||'';this.sig.recs=d.recommendations||[];this.sig.strategy_scores=d.strategy_scores||{};this.sig.no_trade_reason=d.no_trade_reason||null;this.sig.scan_meta=d.scan_meta||null;this.sig.data_freshness=d.data_freshness||null}catch(e){this.sig.mode='OFFLINE';this.sig.source='error';this.sig.no_trade_reason='⚠ Failed to connect to the scanner. Check if the server is running.'}
      },
      async fetchPortfolio(){
        this.pf.loading=true;
        try{
          const r=await fetch('/api/portfolio/monitor');
          if(!r.ok)throw 0;
          const d=await r.json();
          this.pf.positions=d.positions||[];
          this.pf.alerts=d.alerts||[];
          this.pf.summary=d.summary||null;
          this.pf.source='manual';
          // ── IBKR auto-sync: when broker is connected, broker positions become canonical ──
          // Manual entries are kept as overlay (e.g. for stop/target metadata) but counts/equity reflect IBKR
          try{
            if(this.cc_status&&this.cc_status.ibkr_connected){
              const r2=await fetch('/api/ibkr/positions');
              if(r2.ok){
                const d2=await r2.json();
                const brokerPositions=(d2.positions||[]).map(p=>({
                  ticker:p.symbol||p.ticker,
                  shares:p.position||p.quantity||0,
                  entry_price:p.avg_cost||p.average_cost||0,
                  current_price:p.market_price||p.last_price||0,
                  market_value:p.market_value||0,
                  unrealized_pnl:p.unrealized_pnl||0,
                  // overlay manual stop/target if same ticker exists
                  ...((this.pf.positions||[]).find(m=>(m.ticker||m.symbol)===(p.symbol||p.ticker))||{}),
                  source:'broker'
                }));
                if(brokerPositions.length>0){
                  this.pf.positions=brokerPositions;
                  this.pf.source='ibkr';
                  // Recompute summary from broker truth
                  const totalVal=brokerPositions.reduce((s,p)=>s+(p.market_value||0),0);
                  this.pf.summary={
                    ...this.pf.summary,
                    total_positions:brokerPositions.length,
                    total_value:totalVal,
                    source:'ibkr',
                  };
                }
              }
            }
          }catch(e){console.warn('IBKR sync skipped:',e)}
          // Enrich with trade advice (action + alpha) in background
          if(this.pf.positions.length>0){
            const enrichTasks=this.pf.positions.filter(p=>p.entry_price&&p.ticker).map(p=>
              fetch('/api/dossier/'+p.ticker+'/trade-advice?buy_price='+p.entry_price).then(r=>r.ok?r.json():null).catch(()=>null)
            );
            const results=await Promise.allSettled(enrichTasks);
            const posWithEntry=this.pf.positions.filter(p=>p.entry_price&&p.ticker);
            results.forEach((r,i)=>{
              if(r.status==='fulfilled'&&r.value){
                posWithEntry[i]._action=r.value.action;
                posWithEntry[i]._alpha_spy=r.value.pnl_pct!=null?Math.round((r.value.pnl_pct-(this.today7.regime?.spy_change_pct||0))*100)/100:null;
              }
            });
          }
        }catch(e){console.warn('Portfolio fetch error:',e)}finally{this.pf.loading=false}
        // Auto-trigger historical VaR after positions hydrate (throttled to 5min)
        try{
          const now=Date.now();
          if((this.pf.positions||[]).length>0 && (now - (this.histVar.last_run||0)) > 300000){
            this.fetchHistVar();
          }
        }catch(_){ }
      },
      async seedDemoPortfolio(){
        if(!window.confirm('Seed 3 demo positions (AAPL 100sh, MSFT 50sh, NVDA 30sh)?\n\nThis overwrites any existing manual portfolio.'))return;
        this.pf.loading=true;
        try{
          const r=await fetch('/api/portfolio/seed-demo',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)throw new Error('HTTP '+r.status);
          const d=await r.json();
          await this.fetchPortfolio();
          this.histVar.last_run=0;
          await this.fetchHistVar();
          alert('✅ Seeded '+d.seeded+' positions.\n\n'+d.next);
        }catch(e){alert('Seed failed: '+e.message);}
        finally{this.pf.loading=false}
      },
      async fetchHistVar(){
        // Real historical-sim VaR — pulls 1y daily returns per position from /api/portfolio/var-historical
        if(this.histVar.loading)return;
        const positions=(this.pf&&this.pf.positions)||[];
        if(positions.length===0){this.histVar.data=null;return;}
        const equity=this.pfRisk().equity||100000;
        this.histVar.loading=true;this.histVar.err='';
        try{
          const body={
            positions:positions.map(p=>({
              ticker:p.ticker||p.symbol,
              market_value:p.market_value||((p.current_price||p.entry_price||0)*(p.shares||p.quantity||0)),
            })).filter(p=>p.ticker && p.market_value>0),
            equity:equity,
            lookback_period:'1y',
          };
          const r=await fetch('/api/portfolio/var-historical',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          if(!r.ok)throw new Error('HTTP '+r.status);
          const d=await r.json();
          this.histVar.data=d;
          this.histVar.last_run=Date.now();
        }catch(e){this.histVar.err=String(e);console.warn('histVar fetch error:',e);}
        finally{this.histVar.loading=false}
      },
      async addPosition(){
        if(!this.pf.addTicker)return;
        // Block if correlation guard is hard-blocking
        if(this.pf.corrPreview&&this.pf.corrPreview.blocked){
          alert('🛑 Correlation guard blocked: '+this.pf.corrPreview.message);
          return;
        }
        try{
          const r=await fetch('/api/portfolio/position',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker:this.pf.addTicker,shares:this.pf.addShares||0,entry_price:this.pf.addEntry||0,stop_price:this.pf.addStop||0,target_1r:this.pf.addT1r||0,target_2r:this.pf.addT2r||0,notes:this.pf.addNotes||''})});
          if(!r.ok)throw 0;
          this.pf.showAdd=false;this.pf.addTicker='';this.pf.addShares=0;this.pf.addEntry=0;this.pf.addStop=0;this.pf.addT1r=0;this.pf.addT2r=0;this.pf.addNotes='';this.pf.corrPreview=null;
          await this.fetchPortfolio();
        }catch(e){console.warn('Add position error:',e)}
      },
      // ── Correlation guard: warn (>0.6) / block (>0.7) when adding correlated names ──
      // Uses per-ticker history vs each existing position; fallbacks to sector overlap if API unavailable
      async checkCorrelation(){
        const t=(this.pf.addTicker||'').toUpperCase().trim();
        if(!t){this.pf.corrPreview=null;return;}
        const existing=(this.pf.positions||[]).map(p=>(p.ticker||p.symbol||'').toUpperCase()).filter(x=>x&&x!==t);
        if(existing.length===0){this.pf.corrPreview={blocked:false,warn:false,message:'First position — no correlation risk'};return;}
        try{
          // Pull rolling 60d closes for new ticker and existing — compute pairwise ρ
          const period='3mo';
          const fetchSpark=async(sym)=>{
            const r=await fetch('/api/live/spark/'+sym+'?days=60');
            if(!r.ok)return null;
            const d=await r.json();
            return d.prices||null;
          };
          const newPrices=await fetchSpark(t);
          if(!newPrices||newPrices.length<20){
            this.pf.corrPreview={blocked:false,warn:true,message:'Insufficient price history for '+t+' — proceed with caution'};
            return;
          }
          const newRet=newPrices.slice(1).map((p,i)=>(p/newPrices[i])-1);
          const corrs=[];
          for(const sym of existing){
            const p=await fetchSpark(sym);
            if(!p||p.length<20)continue;
            const r=p.slice(1).map((px,i)=>(px/p[i])-1);
            const n=Math.min(newRet.length,r.length);
            const a=newRet.slice(-n), b=r.slice(-n);
            const ma=a.reduce((s,x)=>s+x,0)/n, mb=b.reduce((s,x)=>s+x,0)/n;
            let num=0, da=0, db=0;
            for(let i=0;i<n;i++){const xa=a[i]-ma, xb=b[i]-mb; num+=xa*xb; da+=xa*xa; db+=xb*xb;}
            const rho=(da>0&&db>0)?num/Math.sqrt(da*db):0;
            corrs.push({sym,rho:Math.round(rho*100)/100});
          }
          if(corrs.length===0){this.pf.corrPreview={blocked:false,warn:true,message:'No correlation data available'};return;}
          corrs.sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho));
          const top=corrs[0];
          if(Math.abs(top.rho)>=0.7){
            this.pf.corrPreview={blocked:true,warn:false,corrs,message:'ρ='+top.rho+' vs '+top.sym+' (>0.7 cap). Concentration risk — block.'};
          }else if(Math.abs(top.rho)>=0.5){
            this.pf.corrPreview={blocked:false,warn:true,corrs,message:'ρ='+top.rho+' vs '+top.sym+' — moderate correlation. Reduce size or pick a less-correlated name.'};
          }else{
            this.pf.corrPreview={blocked:false,warn:false,corrs,message:'Max ρ='+top.rho+' vs '+top.sym+' — diversifying'};
          }
        }catch(e){
          console.warn('Correlation check failed:',e);
          this.pf.corrPreview={blocked:false,warn:true,message:'Correlation check failed — proceed with caution'};
        }
      },
      async removePosition(ticker){
        if(!confirm('Remove '+ticker+' from portfolio?'))return;
        try{await fetch('/api/portfolio/position/'+ticker,{method:'DELETE'});await this.fetchPortfolio()}catch(e){console.warn(e)}
      },
      async confirmBuy(){
        if(!this.dos.data||!this.dos.ticker)return;
        const tp=this.dos.data.trade_plan;
        if(!tp)return;
        const entry=this.dos.data.price||tp.entry_zone[0];
        const shares=prompt('How many shares to track for '+this.dos.ticker+'?','100');
        if(!shares)return;
        try{
          const r=await fetch('/api/portfolio/position',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker:this.dos.ticker,shares:parseFloat(shares),entry_price:entry,stop_price:tp.stop,target_1r:tp.target_1r,target_2r:tp.target_2r,notes:'From dossier trade plan'})});
          if(r.ok){alert('✅ '+this.dos.ticker+' added to portfolio! Check Portfolio tab.');this.tab='portfolio';await this.fetchPortfolio()}
        }catch(e){console.warn(e)}
      },
      async runFactory(){
        this.factory.loading=true;this.factory.result=null;this.factory.showDetail=false;
        try{
          const r=await fetch('/api/strategy-factory/generate?ticker='+encodeURIComponent(this.factory.ticker)+'&period='+this.factory.period+'&mode='+this.factory.mode,{method:'POST'});
          if(!r.ok)throw new Error('Factory failed');
          this.factory.result=await r.json();
        }catch(e){console.warn('Factory error:',e);alert('Strategy Factory error: '+e.message)}finally{this.factory.loading=false}
      },
      viewFactoryDetail(rank){
        if(!this.factory.result)return;
        const all=this.factory.result.best_strategy?[this.factory.result.best_strategy]:[];
        // Find in library or reconstruct from ranking
        const lib=this._factoryLib||[];
        const found=lib.find(s=>s.rank===rank);
        if(found){this.factory.detail=found;this.factory.showDetail=true;return}
        // Fetch full library
        fetch('/api/strategy-factory/library').then(r=>r.json()).then(d=>{
          this._factoryLib=d.strategies||[];
          const s=this._factoryLib.find(x=>x.rank===rank);
          if(s){this.factory.detail=s;this.factory.showDetail=true}
        }).catch(e=>console.warn(e));
      },
      async deployFactory(id){
        try{
          const r=await fetch('/api/strategy-factory/deploy/'+id,{method:'POST'});
          if(r.ok){alert('🚀 Strategy deployed to paper trading monitor!')}
        }catch(e){console.warn(e)}
      },
      async fetchDossier(){
        if(!this.dos.ticker)return;this.dos.loading=true;this.dos.data=null;this.dos.error='';
        try{
          const r=await fetch('/api/live/dossier/'+encodeURIComponent(this.dos.ticker));
          if(!r.ok){const e=await r.json();throw new Error(e.detail||'Not found')}
          this.dos.data=await r.json();
          // Phase 9 enrichment
          const t=encodeURIComponent(this.dos.ticker);
          const [f9fund,f9earn,f9struct]=await Promise.allSettled([
            fetch('/api/v9/fundamentals/'+t).then(r=>r.ok?r.json():null),
            fetch('/api/v9/earnings/'+t).then(r=>r.ok?r.json():null),
            fetch('/api/v9/structure/'+t).then(r=>r.ok?r.json():null),
          ]);
          this.dos.data._p9={fundamentals:f9fund.value||null,earnings:f9earn.value||null,structure:f9struct.value||null};
          // Peer comparison (async, non-blocking)
          this.dos.peers=null;this.dos.peersLoading=true;
          fetch('/api/dossier/'+t+'/peers').then(r=>r.ok?r.json():null).then(d=>{this.dos.peers=d}).catch(()=>{}).finally(()=>{this.dos.peersLoading=false});
          // Render chart
          this.dos.chartPeriod=this.dos.chartPeriod||'6mo';
          this.$nextTick(()=>this.renderDossierChart());
        }catch(e){this.dos.error=e.message}finally{this.dos.loading=false}
      },
      async renderDossierChart(){
        if(!this.dos.data||!this.dos.ticker)return;
        const el=document.getElementById('dossier-chart');
        if(!el||typeof LightweightCharts==='undefined')return;
        el.innerHTML='';
        try{
          const sig=this.dos.showSignals?'&signals=true':'';
          const r=await fetch('/api/live/chart/'+encodeURIComponent(this.dos.ticker)+'?period='+(this.dos.chartPeriod||'6mo')+sig);
          if(!r.ok)return;
          const d=await r.json();
          if(!d.candles||!d.candles.length)return;
          const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:260,layout:{background:{color:'#161b22'},textColor:'#8b949e',fontSize:10},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},crosshair:{mode:0},rightPriceScale:{borderColor:'#21262d'},timeScale:{borderColor:'#21262d',timeVisible:false}});
          const cs=chart.addCandlestickSeries({upColor:'#00d4aa',downColor:'#ff5c5c',borderUpColor:'#00d4aa',borderDownColor:'#ff5c5c',wickUpColor:'#00d4aa',wickDownColor:'#ff5c5c'});
          cs.setData(d.candles);
          if(d.sma20&&d.sma20.length){const s20=chart.addLineSeries({color:'#58a6ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});s20.setData(d.sma20)}
          if(d.sma50&&d.sma50.length){const s50=chart.addLineSeries({color:'#fbbf24',lineWidth:1,priceLineVisible:false,lastValueVisible:false});s50.setData(d.sma50)}
          // Pattern signal markers
          this.dos.chartSignals=d.signals||[];
          if(this.dos.showSignals&&d.signals&&d.signals.length){
            cs.setMarkers(d.signals.map(s=>({
              time:s.time,position:s.position,color:s.color,shape:s.shape,text:s.text
            })));
          }
          // S/R lines from structure
          const st=this.dos.data._p9&&this.dos.data._p9.structure;
          if(st){
            if(st.nearest_support){cs.createPriceLine({price:st.nearest_support,color:'#00d4aa',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'S'})}
            if(st.nearest_resistance){cs.createPriceLine({price:st.nearest_resistance,color:'#ff5c5c',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'R'})}
          }
          chart.timeScale().fitContent();
          new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth})}).observe(el);
          this._dossierChart=chart;
        }catch(e){console.warn('Chart error:',e)}
        // Also render benchmark chart
        this.renderBenchChart();
      },
      async renderBenchChart(){
        if(!this.dos.ticker)return;
        const el=document.getElementById('bench-chart');
        if(!el||typeof LightweightCharts==='undefined')return;
        el.innerHTML='';
        try{
          const r=await fetch('/api/live/perf-vs-spy/'+encodeURIComponent(this.dos.ticker)+'?period='+(this.dos.benchPeriod||'1y'));
          if(!r.ok)return;
          const d=await r.json();
          if(d.error||!d.equity_stock||!d.equity_stock.length)return;
          const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:200,layout:{background:{color:'#161b22'},textColor:'#8b949e',fontSize:10},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},crosshair:{mode:0},rightPriceScale:{borderColor:'#21262d'},timeScale:{borderColor:'#21262d',timeVisible:false}});
          // Stock line (green)
          const sl=chart.addLineSeries({color:'#00d4aa',lineWidth:2,priceLineVisible:false,lastValueVisible:true,title:this.dos.ticker});
          sl.setData(d.equity_stock);
          // SPY line (amber dashed)
          const bl=chart.addLineSeries({color:'#fbbf24',lineWidth:2,priceLineVisible:false,lastValueVisible:true,title:'SPY',lineStyle:2});
          bl.setData(d.equity_spy);
          // Base line at 100
          sl.createPriceLine({price:100,color:'#484f58',lineWidth:1,lineStyle:1,axisLabelVisible:false,title:''});
          chart.timeScale().fitContent();
          new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth})}).observe(el);
          // Store period breakdown data
          this.dos.benchSummary=d.summary||null;
          this.dos.benchMonthly=d.monthly||null;
          this.dos.benchQuarterly=d.quarterly||null;
          this.dos.benchYearly=d.yearly||null;
          // Legacy compat
          if(d.summary){this.dos.benchStats={stockReturn:d.summary.total_return.stock,spyReturn:d.summary.total_return.spy,alpha:d.summary.total_return.alpha}}
        }catch(e){console.warn('Bench chart error:',e)}
      },
      renderBTEquityChart(){
        const ec=this.bt.result&&this.bt.result.equity_chart;
        if(!ec||!ec.bh||!ec.bh.length)return;
        const el=document.getElementById('bt-equity-chart');
        if(!el||typeof LightweightCharts==='undefined')return;
        el.innerHTML='';
        try{
          const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:220,layout:{background:{color:'#161b22'},textColor:'#8b949e',fontSize:10},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},crosshair:{mode:0},rightPriceScale:{borderColor:'#21262d'},timeScale:{borderColor:'#21262d',timeVisible:false}});
          // Strategy line (green)
          if(ec.strategy&&ec.strategy.length){
            const sl=chart.addLineSeries({color:'#00d4aa',lineWidth:2,priceLineVisible:false,lastValueVisible:true,title:'Strategy'});
            sl.setData(ec.strategy);
            // Signal markers
            if(ec.signals&&ec.signals.length){sl.setMarkers(ec.signals)}
          }
          // Buy-hold line (amber dashed)
          const bl=chart.addLineSeries({color:'#fbbf24',lineWidth:1,priceLineVisible:false,lastValueVisible:true,title:'Buy&Hold',lineStyle:2});
          bl.setData(ec.bh);
          // Base 100 line
          bl.createPriceLine({price:100,color:'#484f58',lineWidth:1,lineStyle:1,axisLabelVisible:false,title:''});
          chart.timeScale().fitContent();
          new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth})}).observe(el);
        }catch(e){console.warn('BT equity chart error:',e)}
      },
      renderBenchBTChart(){
        const ec=this.benchBT.data&&this.benchBT.data.equity_curve;
        if(!ec||!ec.strategy||!ec.strategy.length)return;
        const el=document.getElementById('bench-bt-chart');
        if(!el||typeof LightweightCharts==='undefined')return;
        el.innerHTML='';
        try{
          const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:160,layout:{background:{color:'#161b22'},textColor:'#8b949e',fontSize:10},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},crosshair:{mode:0},rightPriceScale:{borderColor:'#21262d'},timeScale:{borderColor:'#21262d',timeVisible:false}});
          // Build time-series from arrays + dates
          const dates=ec.dates||[];
          const stratVals=ec.strategy||[];
          const benchVals=ec.benchmark||[];
          const toData=(vals)=>vals.map((v,i)=>{
            const d=dates[i]||'';
            const parts=d.split('-');
            const ts=parts.length===3?Date.UTC(+parts[0],+parts[1]-1,+parts[2])/1000:i;
            return{time:ts,value:v*100};
          }).filter(d=>d.value>0);
          const sd=toData(stratVals);
          const bd=toData(benchVals);
          if(sd.length){
            const sl=chart.addLineSeries({color:'#00d4aa',lineWidth:2,priceLineVisible:false,lastValueVisible:true,title:'RS Top-5'});
            sl.setData(sd);
          }
          if(bd.length){
            const bl=chart.addLineSeries({color:'#fbbf24',lineWidth:1,priceLineVisible:false,lastValueVisible:true,title:this.benchBT.benchmark,lineStyle:2});
            bl.setData(bd);
          }
          chart.timeScale().fitContent();
          new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth})}).observe(el);
        }catch(e){console.warn('Bench BT chart error:',e)}
      },
      async loadSparklines(items){
        // Load sparkline data for an array of {ticker} objects, sets _spark property
        const tickers=[...new Set(items.filter(o=>o.ticker).map(o=>o.ticker))].slice(0,15);
        const results=await Promise.allSettled(tickers.map(t=>fetch('/api/live/spark/'+encodeURIComponent(t)+'?days=20').then(r=>r.ok?r.json():null)));
        const map={};
        results.forEach((r,i)=>{if(r.status==='fulfilled'&&r.value&&r.value.prices&&r.value.prices.length>=3)map[tickers[i]]=r.value.prices});
        items.forEach(o=>{if(o.ticker&&map[o.ticker]){
          const p=map[o.ticker];
          const mn=Math.min(...p),mx=Math.max(...p);
          const rng=mx-mn||1;
          o._spark=p.map(v=>Math.round((v-mn)/rng*16)+1);
        }});
      },
      async renderTTChart(){
        if(!this.tt.result||!this.tt.result.ticker)return;
        const el=document.getElementById('tt-chart');
        if(!el||typeof LightweightCharts==='undefined')return;
        el.innerHTML='';
        try{
          // Fetch 1y chart data centered around the target date
          const r=await fetch('/api/live/chart/'+encodeURIComponent(this.tt.result.ticker)+'?period=1y');
          if(!r.ok)return;
          const d=await r.json();
          if(!d.candles||!d.candles.length)return;
          const chart=LightweightCharts.createChart(el,{width:el.clientWidth,height:200,layout:{background:{color:'#161b22'},textColor:'#8b949e',fontSize:10},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}},crosshair:{mode:0},rightPriceScale:{borderColor:'#21262d'},timeScale:{borderColor:'#21262d',timeVisible:false}});
          const cs=chart.addCandlestickSeries({upColor:'#00d4aa',downColor:'#ff5c5c',borderUpColor:'#00d4aa',borderDownColor:'#ff5c5c',wickUpColor:'#00d4aa',wickDownColor:'#ff5c5c'});
          cs.setData(d.candles);
          // Mark the entry date
          const targetDate=this.tt.result.target_date;
          if(targetDate){
            const parts=targetDate.split('-');
            if(parts.length===3){
              const targetTs=Date.UTC(+parts[0],+parts[1]-1,+parts[2])/1000;
              // Find nearest candle
              let nearestIdx=0,minDiff=Infinity;
              d.candles.forEach((c,i)=>{const df=Math.abs(c.time-targetTs);if(df<minDiff){minDiff=df;nearestIdx=i}});
              const entryCandle=d.candles[nearestIdx];
              if(entryCandle){
                cs.setMarkers([{time:entryCandle.time,position:'belowBar',color:'#00d4aa',shape:'arrowUp',text:'ENTRY $'+this.tt.result.price}]);
                cs.createPriceLine({price:this.tt.result.price,color:'#58a6ff',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'Entry'});
              }
            }
          }
          // SMA overlays
          if(d.sma20&&d.sma20.length){const s20=chart.addLineSeries({color:'#58a6ff',lineWidth:1,priceLineVisible:false,lastValueVisible:false});s20.setData(d.sma20)}
          if(d.sma50&&d.sma50.length){const s50=chart.addLineSeries({color:'#fbbf24',lineWidth:1,priceLineVisible:false,lastValueVisible:false});s50.setData(d.sma50)}
          chart.timeScale().fitContent();
          new ResizeObserver(()=>{chart.applyOptions({width:el.clientWidth})}).observe(el);
        }catch(e){console.warn('TT chart error:',e)}
      },
      openDossier(ticker){if(ticker){this.dos.ticker=ticker;this.switchTab('dossier');this.fetchDossier()}},
      async runBT(){
        if(!this.bt.ticker)return;this.bt.loading=true;this.bt.result=null;
        try{const u='/api/live/backtest?ticker='+encodeURIComponent(this.bt.ticker)+'&strategy='+this.bt.strategy+'&period='+this.bt.period;const r=await fetch(u,{method:'POST'});if(!r.ok){const e=await r.json();throw new Error(e.detail||'Failed')}this.bt.result=await r.json();this.$nextTick(()=>this.renderBTEquityChart())}catch(e){alert('Error: '+e.message)}finally{this.bt.loading=false}
      },
      // ── 24/7 Fund Monitor (sprint89) ──────────────────────────────────────
      startFundMonitor(){
        // stop any existing timer first
        if(this.fundMonitor.autoRefreshTimer){clearInterval(this.fundMonitor.autoRefreshTimer);this.fundMonitor.autoRefreshTimer=null}
        this.fetchFunds();
        // auto-refresh every 30 minutes (matches /fund-lab/live cache TTL)
        this.fundMonitor.autoRefreshTimer=setInterval(()=>{if(this.tab==='funds')this.fetchFunds();else{clearInterval(this.fundMonitor.autoRefreshTimer);this.fundMonitor.autoRefreshTimer=null}},1800000);
      },
      async ibkrPing(){
        this.ibkr.pingResult=null;this.ibkr.loading=true;
        try{
          const r=await fetch('/api/ibkr/ping',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({host:this.ibkr.host||'127.0.0.1',mode:this.ibkr.mode})});
          this.ibkr.pingResult=await r.json();
        }catch(e){this.ibkr.pingResult={reachable:false,message:'Probe failed: '+e.message}}
        finally{this.ibkr.loading=false}
      },
      async ibkrConnect(){
        this.ibkr.loading=true;
        try{
          const r=await fetch('/api/ibkr/connect',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'},body:JSON.stringify({mode:this.ibkr.mode,host:this.ibkr.host||'127.0.0.1'})});
          const d=await r.json();
          if(!r.ok)throw new Error(d.detail||'Connection failed');
          this.ibkr.connected=true;
          await this.ibkrFetchAccount();
          await this.ibkrFetchPositions();
        }catch(e){alert('IBKR Connect failed: '+e.message)}
        finally{this.ibkr.loading=false}
      },
      async ibkrDisconnect(){
        await fetch('/api/ibkr/disconnect',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}}).catch(()=>{});
        this.ibkr.connected=false;this.ibkr.account=null;this.ibkr.positions=[];
      },
      async ibkrFetchAccount(){
        this.ibkr.loading=true;
        try{
          const r=await fetch('/api/ibkr/account',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)throw new Error('status '+r.status);
          this.ibkr.account=await r.json();
        }catch(e){console.warn('ibkr account failed',e)}
        finally{this.ibkr.loading=false}
      },
      async ibkrFetchPositions(){
        try{
          const r=await fetch('/api/ibkr/positions',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)throw new Error('status '+r.status);
          const d=await r.json();
          this.ibkr.positions=d.positions||[];
        }catch(e){console.warn('ibkr positions failed',e)}
      },
      async ibkrPlaceOrder(){
        // SAFETY: block when circuit breaker tripped
        if(this.cc_status&&this.cc_status.breaker){
          this.ibkr.orderError='⛔ Circuit breaker is TRIPPED ('+(this.cc_status.breaker_reason||'unknown')+'). Reset before trading.';
          return;
        }
        // SAFETY: hard confirm on LIVE mode
        const f=this.ibkr.orderForm;
        const sym=(f.symbol||'').toUpperCase();
        if(!sym){this.ibkr.orderError='Symbol required';return;}
        const px=f.orderType==='MKT'?'MKT':('LMT @ $'+(f.limitPrice||'?'));
        const summary=f.action+' '+f.qty+' '+sym+' '+px;
        if(this.ibkr.mode==='live'){
          const typed=window.prompt('⚠ LIVE ORDER\n\n'+summary+'\n\nThis will submit a REAL order to IBKR.\nType the ticker symbol "'+sym+'" to confirm:');
          if(typed!==sym){this.ibkr.orderError='Cancelled — confirmation did not match.';return;}
        }else{
          if(!window.confirm('PAPER ORDER\n\n'+summary+'\n\nProceed?'))return;
        }
        this.ibkr.loading=true;this.ibkr.orderResult=null;this.ibkr.orderError='';
        try{
          const body={symbol:sym,sec_type:f.secType,action:f.action,quantity:Number(f.qty),order_type:f.orderType};
          if(f.limitPrice)body.limit_price=Number(f.limitPrice);
          const r=await fetch('/api/ibkr/order',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'},body:JSON.stringify(body)});
          const d=await r.json();
          if(!r.ok)throw new Error(d.detail||'Order failed');
          this.ibkr.orderResult=d;
          await this.ibkrFetchPositions();
        }catch(e){this.ibkr.orderError=e.message}
        finally{this.ibkr.loading=false}
      },

      // ── BRACKET ORDER (parent + stop + target, OCA) ─────────────────────────
      ibkrBracketSummary(){
        const f=this.ibkr.orderForm;
        const e=Number(f.limitPrice)||0, s=Number(f.stopPrice)||0, t=Number(f.targetPrice)||0;
        if(!s||!t)return 'Enter stop and target to compute R:R';
        if(!e)return 'Entry will be MKT — R:R will be calculated from fill price';
        const isBuy=f.action==='BUY';
        const risk=isBuy?(e-s):(s-e);
        const reward=isBuy?(t-e):(e-t);
        if(risk<=0)return '⚠ Bad geometry: stop is on wrong side of entry';
        if(reward<=0)return '⚠ Bad geometry: target is on wrong side of entry';
        const rr=(reward/risk).toFixed(2);
        const tier=rr>=3?'🟢 TRADE-tier':rr>=2?'🟡 WATCH-tier':'🔴 Below threshold';
        let kind='STP';
        if(f.trail){
          const tv=Number(f.trailValue)||0;
          kind = tv>0 ? ('TRAIL '+(f.trailKind==='percent'?tv+'%':'$'+tv)) : 'TRAIL (default)';
        }
        return `Risk $${risk.toFixed(2)}/sh · Reward $${reward.toFixed(2)}/sh · R:R ${rr}:1 · ${tier} · stop-kind: ${kind}`;
      },
      ibkrAcceptSuggestedBracket(){
        const f=this.ibkr.orderForm;
        if(f._suggestedStop)f.stopPrice=f._suggestedStop;
        if(f._suggestedTarget)f.targetPrice=f._suggestedTarget;
        f.useBracket=true;
      },
      async ibkrPlaceBracket(){
        if(this.cc_status&&this.cc_status.breaker){
          this.ibkr.orderError='⛔ Circuit breaker TRIPPED ('+(this.cc_status.breaker_reason||'unknown')+'). Reset before trading.';
          return;
        }
        const f=this.ibkr.orderForm;
        const sym=(f.symbol||'').toUpperCase();
        const qty=Number(f.qty)||0;
        const stop=Number(f.stopPrice)||0;
        const target=Number(f.targetPrice)||0;
        const entry=f.limitPrice?Number(f.limitPrice):null;
        if(!sym){this.ibkr.orderError='Symbol required';return;}
        if(!qty||qty<=0){this.ibkr.orderError='Quantity required';return;}
        if(!stop||!target){this.ibkr.orderError='Bracket requires stop + target';return;}
        // Geometry sanity
        if(f.action==='BUY'){
          if(entry!==null && !(stop<entry && entry<target)){this.ibkr.orderError='BUY bracket needs stop<entry<target';return;}
          if(entry===null && !(stop<target)){this.ibkr.orderError='BUY bracket needs stop<target';return;}
        }else{
          if(entry!==null && !(target<entry && entry<stop)){this.ibkr.orderError='SELL bracket needs target<entry<stop';return;}
          if(entry===null && !(target<stop)){this.ibkr.orderError='SELL bracket needs target<stop';return;}
        }
        const risk=f.action==='BUY'?(entry||target)-stop:stop-(entry||target);
        const reward=f.action==='BUY'?target-(entry||stop):(entry||stop)-target;
        const rr=risk>0?(reward/risk).toFixed(2):'?';
        // ── Pre-trade slippage gate (BLOCK on illiquid; WARN on costly) ──
        let slipVerdict=null, slipReasonsText='';
        try{
          const refPx=entry||target||stop||0;
          if(refPx>0){
            const sr=await fetch('/api/slippage/check',{
              method:'POST',
              headers:{'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'},
              body:JSON.stringify({ticker:sym,size_shares:qty,current_price:refPx,side:f.action})
            });
            if(sr.ok){
              slipVerdict=await sr.json();
              slipReasonsText=(slipVerdict.reasons||[]).join('\n  • ');
            }
          }
        }catch(_){ /* gate down — fail open, allow */ }
        if(slipVerdict&&slipVerdict.verdict==='BLOCK'){
          this.ibkr.orderError='🛑 SLIPPAGE BLOCK:\n  • '+slipReasonsText+'\n\n(Spread '+slipVerdict.spread_bps+'bps · ADV-participation '+slipVerdict.participation_pct+'%)';
          this.ibkr.loading=false;
          return;
        }
        const slipBanner = slipVerdict ? (
          slipVerdict.verdict==='WARN'
            ? `\n\n⚠ SLIPPAGE WARN:\n  • ${slipReasonsText}\n  (Spread ${slipVerdict.spread_bps}bps · ADV-pct ${slipVerdict.participation_pct}% · Round-trip ${slipVerdict.estimate&&slipVerdict.estimate.round_trip_bps}bps)`
            : `\n\n✓ Slippage gate: PASS (spread ${slipVerdict.spread_bps}bps · cost ${slipVerdict.estimate&&slipVerdict.estimate.round_trip_bps}bps RT)`
        ) : '';
        const summary=`🎯 BRACKET ${f.action} ${qty}x ${sym}\nEntry: ${entry?'$'+entry:'MKT'}\nStop: $${stop} (risk $${risk.toFixed(2)}/sh)\nTarget: $${target} (reward $${reward.toFixed(2)}/sh)\nR:R: ${rr}:1`+slipBanner;
        if(this.ibkr.mode==='live'){
          const typed=window.prompt('⚠ LIVE BRACKET ORDER\n\n'+summary+'\n\nReal money. Type "'+sym+'" to confirm:');
          if(typed!==sym){this.ibkr.orderError='Cancelled — confirmation did not match.';return;}
        }else{
          if(!window.confirm('PAPER BRACKET\n\n'+summary+'\n\nProceed?'))return;
        }
        this.ibkr.loading=true;this.ibkr.orderResult=null;this.ibkr.orderError='';
        try{
          const body={symbol:sym,sec_type:f.secType,action:f.action,quantity:qty,entry_price:entry,stop_price:stop,take_profit:target};
          // Trail variant — replaces STP child with TRAIL
          if(f.trail){
            body.trail=true;
            const tv=Number(f.trailValue)||0;
            if(tv>0){
              if(f.trailKind==='percent')body.trail_percent=tv;
              else body.trail_amount=tv;
            }
          }
          const headers={'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'};
          if(this.ibkr.mode==='live')headers['X-Confirm-Live-Order']='CONFIRMED';
          const r=await fetch('/api/ibkr/bracket',{method:'POST',headers,body:JSON.stringify(body)});
          const d=await r.json();
          if(!r.ok)throw new Error(d.detail||'Bracket failed');
          // Surface as orderResult so existing success card renders it
          this.ibkr.orderResult={
            order_id: d.parent_order_id,
            status: 'BRACKET '+(d.parent_status||'Submitted'),
            filled: d.parent_filled||0,
            avg_fill_price: d.parent_avg_fill||0,
            warning: d.warning||('Children: '+(d.stop_kind||'STP')+'#'+d.stop_order_id+' / TGT#'+d.target_order_id+' (OCA '+d.oca_group+')')
          };
          // Archive previous working bracket so back-to-back placements don't lose context
          if(this.ibkr.workingBracket){
            this.ibkr.bracketArchive.unshift({...this.ibkr.workingBracket, archived_at: Date.now()});
            this.ibkr.bracketArchive = this.ibkr.bracketArchive.slice(0, 8); // cap at 8
          }
          // Stash full bracket detail for the WORKING BRACKET panel
          this.ibkr.workingBracket={
            symbol: sym,
            parent_order_id: d.parent_order_id,
            stop_order_id: d.stop_order_id,
            target_order_id: d.target_order_id,
            oca_group: d.oca_group,
            stop_kind: d.stop_kind||'STP',
            stop_price: stop,
            take_profit: target,
            parent_status: d.parent_status||'Submitted',
            parent_filled: d.parent_filled||0,
            parent_avg_fill: d.parent_avg_fill||0,
            trail_amount: d.trail_amount,
            trail_percent: d.trail_percent,
            warning: d.warning||null,
            ts: Date.now()
          };
          // Start auto-poll loop (5s) for live status of all 3 legs
          this.ibkrStartBracketPoll();
          await this.ibkrFetchPositions();
        }catch(e){this.ibkr.orderError=e.message}
        finally{this.ibkr.loading=false}
      },

      // ── Bracket live polling + cancel ──────────────────────────────────────
      ibkrStartBracketPoll(){
        if(this._bracketPollTimer){clearInterval(this._bracketPollTimer);this._bracketPollTimer=null}
        // Immediate refresh, then every 5s
        this.ibkrPollBracket();
        this._bracketPollTimer=setInterval(()=>{
          if(!this.ibkr.workingBracket){this.ibkrStopBracketPoll();return;}
          this.ibkrPollBracket();
        },5000);
      },
      ibkrStopBracketPoll(){
        if(this._bracketPollTimer){clearInterval(this._bracketPollTimer);this._bracketPollTimer=null}
      },
      async ibkrPollBracket(){
        const wb=this.ibkr.workingBracket;
        if(!wb)return;
        try{
          const r=await fetch('/api/ibkr/open-orders',{headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)return;
          const d=await r.json();
          const byId={};(d.orders||[]).forEach(o=>{byId[o.order_id]=o});
          const p=byId[wb.parent_order_id], s=byId[wb.stop_order_id], t=byId[wb.target_order_id];
          if(p){wb.parent_status=p.status||wb.parent_status;wb.parent_filled=p.filled||wb.parent_filled;wb.parent_avg_fill=p.avg_fill_price||wb.parent_avg_fill}
          if(s){wb.stop_status=s.status||''}
          if(t){wb.target_status=t.status||''}
          wb.pollAge=Math.round((Date.now()-wb.ts)/1000);
          // Auto-stop poll when all legs reached terminal state
          const term=v=>v&&['filled','cancelled','canceled','inactive','pendingcancel'].includes((v||'').toLowerCase());
          const allDone=term(wb.parent_status)&&(wb.parent_filled>0?(term(wb.stop_status)||term(wb.target_status)):term(wb.stop_status));
          if(allDone){
            // Auto-log to closed_trades.jsonl when we have entry + exit price
            if(wb.parent_filled>0 && !wb._ledgerLogged){
              const stopFilled=(wb.stop_status||'').toLowerCase()==='filled';
              const tgtFilled=(wb.target_status||'').toLowerCase()==='filled';
              const exitPx = tgtFilled ? wb.take_profit : (stopFilled ? wb.stop_price : 0);
              if(exitPx>0 && wb.parent_avg_fill>0){
                wb._ledgerLogged=true;
                try{
                  await fetch('/api/ledger/close-trade',{
                    method:'POST',
                    headers:{'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'},
                    body:JSON.stringify({
                      ticker:wb.symbol,
                      direction:'LONG',
                      entry_price:wb.parent_avg_fill,
                      exit_price:exitPx,
                      shares:wb.parent_filled,
                      stop_price:wb.stop_price,
                      strategy_id:'ibkr_bracket',
                      source:'ibkr_bracket_auto',
                    })
                  });
                  // Refresh strategy health so the new row appears
                  this.fetchStrategyHealth();
                }catch(_){ /* silent */ }
              }
            }
            this.ibkrStopBracketPoll();
          }
        }catch(e){/* silent — keep last known state */}
      },
      async ibkrCancelBracket(){
        const wb=this.ibkr.workingBracket;
        if(!wb)return;
        if(!window.confirm('Cancel bracket for '+wb.symbol+'?\n\nParent #'+wb.parent_order_id+' + stop + target will be cancelled at IB.'))return;
        try{
          const body={parent_order_id:wb.parent_order_id,stop_order_id:wb.stop_order_id,target_order_id:wb.target_order_id};
          const r=await fetch('/api/ibkr/cancel-bracket',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':window._apiKey||'dev-secret-local'},body:JSON.stringify(body)});
          const d=await r.json();
          wb.cancelOk=!!d.ok;
          wb.cancelMsg=d.ok?'✓ Cancel submitted for all 3 legs at '+new Date().toLocaleTimeString():('Cancel partial: '+JSON.stringify(d.results||d.detail||d));
          // Re-poll to pick up PendingCancel/Cancelled status
          this.ibkrPollBracket();
        }catch(e){wb.cancelOk=false;wb.cancelMsg='Cancel failed: '+e.message}
      },
      ibkrDismissBracket(){
        this.ibkrStopBracketPoll();
        if(this.ibkr.workingBracket){
          this.ibkr.bracketArchive.unshift({...this.ibkr.workingBracket, archived_at: Date.now()});
          this.ibkr.bracketArchive = this.ibkr.bracketArchive.slice(0, 8);
        }
        this.ibkr.workingBracket=null;
      },

      fundIcon(name){return name==='FUND_ALPHA'?'🚀':name==='FUND_PENDA'?'🛡':name==='FUND_MACRO'?'🌐':'⚙️'},
      fundColor(name){return name==='FUND_ALPHA'?'var(--green)':name==='FUND_PENDA'?'var(--blue)':name==='FUND_MACRO'?'var(--purple)':'var(--orange)'},

      // ── Playbook → IBKR bracket helper ─────────────────────────────────────
      // Pre-fills the order ticket using the Playbook card's R-based size, then
      // switches to the IBKR tab. PM still has to confirm — no silent submission.
      sendPlaybookToIbkr(r){
        if(!r||!r.ticker){alert('Missing ticker');return;}
        if(!this.cc_status||!this.cc_status.ibkr_connected){
          alert('IBKR not connected. Open the IBKR pill to connect first.');
          return;
        }
        const equity = (this.pf&&this.pf.summary&&(this.pf.summary.total_value||this.pf.summary.account_equity)) || 100000;
        const entry = Number(r.entry_price)||0;
        const stop = Number(r.stop_price)||0;
        let qty = 0;
        if (entry>0 && stop>0 && entry>stop) {
          // 1R = 1% of equity (matches the size pill in Playbook)
          const riskDollars = equity * 0.01;
          const perShareRisk = entry - stop;
          qty = Math.max(1, Math.floor(riskDollars / perShareRisk));
        }
        this.ibkr.orderForm.symbol = (r.ticker||'').toUpperCase();
        this.ibkr.orderForm.action = 'BUY';
        this.ibkr.orderForm.secType = 'STK';
        this.ibkr.orderForm.qty = qty || 1;
        this.ibkr.orderForm.orderType = entry>0 ? 'LMT' : 'MKT';
        if (entry>0) this.ibkr.orderForm.limitPrice = entry;
        // Stash bracket details for the IBKR view to surface (optional bracket builder UI to come)
        this.ibkr.orderForm._suggestedStop = stop || null;
        this.ibkr.orderForm._suggestedTarget = Number(r.target_price)||null;
        this.ibkr.orderForm._suggestedRR = r.risk_reward||null;
        // Auto-enable bracket if both stop + target are available — close alpha→execution loop
        if (stop>0 && Number(r.target_price)>0) {
          this.ibkr.orderForm.stopPrice = stop;
          this.ibkr.orderForm.targetPrice = Number(r.target_price);
          this.ibkr.orderForm.useBracket = true;
        }
        this.tab = 'ibkr';
      },

      // ── PM Strip (model funds mini-cards, refreshed lazily) ────────────────

      // ── Model Funds (productized fund cards) ──────────────────────────────

      // ── Trade Intelligence ────────────────────────────────────────────────

      async selectTradeIntelTrade(t){
        if(!t)return;
        this.tradeIntel.selectedTradeKey=(t.ticker||'')+'|'+(t.entry_time||'');
        await this.fetchSelectedTradeAIReview();
      },
      sortOpps(){
        const k=this.oppsSort;
        this.opps.sort((a,b)=>k==='ticker'?(a.ticker||'').localeCompare(b.ticker||''):(Number(b[k])||0)-(Number(a[k])||0));
      },
      async fetchToday7(){
        try{const r=await fetch('/api/v7/today');if(!r.ok)throw 0;const d=await r.json();this.today7.regime=d.market_regime||null;this.today7.top_ranked=d.top_5||[];this.today7.filter_funnel=d.filter_funnel||null;this.today7.avoid_list=(d.avoid||[]).map(a=>typeof a==='string'?{ticker:'⚠',reason:a}:a);this.today7.tradeability=(d.market_regime||{}).tradeability||'';this.today7.what_changed=d.what_changed||[];this.today7.event_risks=d.event_risks||[];this.today7.best_family=d.best_setup_family||null;this.today7.pulse=d.market_pulse||null;this.today7.narrative=d.narrative||'';this.today7.ai_narrative=d.ai_narrative||null;this.today7.date=d.date||'';this.today7.trust=d.trust||{};
          // DAY-OVER-DAY DIFF — tag NEW vs CARRYOVER vs MOVED
          try{
            const todayKey=(d.date||new Date().toISOString().slice(0,10));
            const prevRaw=localStorage.getItem('cc_yesterday_top');
            const prevDate=localStorage.getItem('cc_yesterday_date');
            const prev=prevRaw?JSON.parse(prevRaw):[];
            const prevMap={}; prev.forEach((t,i)=>{prevMap[t]=i+1;});
            (this.today7.top_ranked||[]).forEach((opp,i)=>{
              const t=opp.ticker; const newRank=i+1;
              if(!(t in prevMap)){opp._diff='NEW';opp._diffMove=null;}
              else{const oldRank=prevMap[t]; const move=oldRank-newRank;
                opp._diff=move>0?'UP':move<0?'DOWN':'SAME';
                opp._diffMove=move;
              }
            });
            // Stash today as "yesterday" if date changed (avoid stomping mid-day)
            if(prevDate!==todayKey){
              localStorage.setItem('cc_yesterday_top',JSON.stringify((this.today7.top_ranked||[]).map(o=>o.ticker)));
              localStorage.setItem('cc_yesterday_date',todayKey);
            }
          }catch(e){console.warn('dod diff failed',e)}
          if(this.today7.top_ranked.length)setTimeout(()=>this.loadSparklines(this.today7.top_ranked),200);
        }catch(e){console.warn('v7/today fetch failed',e)}
      },
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
                this.today7.ai_provider=d.provider||'unknown';
                this.today7.ai_model=d.model||'';
                if(d.ai_narrative){
                    this.today7.ai_narrative=d.ai_narrative;
                    this.today7.trust.ai_powered=d.configured===true;
                } else {
                    this.today7.ai_narrative="AI Analysis unavailable or not configured.";
                    this.today7.ai_provider='none';
                }
            }
        }catch(e){
            console.warn('fetchAINarrative failed',e);
            this.today7.ai_narrative="AI Analysis request failed.";
            this.today7.ai_provider='error';
        }finally{
            this.today7.ai_loading=false;
        }
      },
      async fetchRanked(){
        this.rankedOpps.loading=true;
        try{let u='/api/v7/playbook/ranked?limit=30';if(this.rankedOpps.actionFilter)u+='&action='+this.rankedOpps.actionFilter;if(this.rankedOpps.sectorFilter)u+='&sector='+this.rankedOpps.sectorFilter;const r=await fetch(u);if(!r.ok)throw 0;const d=await r.json();this.rankedOpps.rows=d.opportunities||[];
          // Fallback 1: if playbook empty, try opportunity scanner
          if(!this.rankedOpps.rows.length&&!this.rankedOpps.actionFilter&&!this.rankedOpps.sectorFilter){
            try{const sr=await fetch('/api/v7/opportunity-scanner?regime='+(this.regime.label||'BULL')+'&top_n=30');if(sr.ok){const sd=await sr.json();const cands=(sd.candidates||[]).slice(0,30);if(cands.length){this.rankedOpps.rows=cands.map((c,i)=>({ticker:c.ticker||c.symbol,score:c.score||c.composite_score||0,action:c.tag||c.action||'WATCH',sector_type:c.sector||'',entry_price:c.close||c.price,stop_price:c.stop_loss,target_price:c.activation||c.target,risk_reward:c.rr||0,setup:c.strategy||c.engine||'scanner',grade:c.score>=8?'A':c.score>=6?'B':'C',thesis_conf:0.6,timing_conf:0.5,exec_conf:0.5,data_conf:0.7,why_now:c.tags?c.tags.join(' · '):c.reason||''}));this.rankedOpps.source='scanner'}}}catch(e){console.warn('scanner fallback failed',e)}
          }
          // Fallback 2: if still empty, try brief JSON file
          if(!this.rankedOpps.rows.length){
            try{const br=await fetch('/api/brief');if(br.ok){const bd=await br.json();const all=[...(bd.actionable||[]),...(bd.watch||[])].slice(0,30);if(all.length){this.rankedOpps.rows=all.map((s,i)=>({ticker:s.ticker,score:s.rs_score||0,action:s.conviction||'WATCH',sector_type:'',entry_price:s.entry||s.price,stop_price:s.stop,target_price:s.target_3r||s.target_2r,risk_reward:s.target_3r&&s.stop&&s.entry?((s.target_3r-s.entry)/(s.entry-s.stop)).toFixed(1):3.0,setup:'brief',grade:s.conviction==='TRADE'?'A':s.conviction==='LEADER'?'B':'C',thesis_conf:s.near_52w_high?0.7:0.5,timing_conf:s.vol_ratio>=1.2?0.7:0.5,exec_conf:0.6,data_conf:0.7,why_now:'RS:'+s.rs_score+' · ATR:'+s.atr_pct+'% · Vol:'+s.vol_ratio+'x'}));this.rankedOpps.source='brief'}}}catch(e){}
          }
          if(this.rankedOpps.rows.length)this.loadSparklines(this.rankedOpps.rows)}catch(e){console.warn('ranked fetch failed',e)}finally{this.rankedOpps.loading=false}
      },
      async fetchScanners(cat){
        this.scannerHub.loading=true;this.scannerHub.category=cat||null;this.scannerHub.error='';
        const _t0=performance.now();
        try{let u='/api/v7/playbook/scanners';if(cat)u+='?category='+cat;const r=await fetch(u);if(!r.ok)throw new Error('HTTP '+r.status);this.scannerHub.data=await r.json();
          const d=this.scannerHub.data||{};
          let uni=d.universe_size||d.universe||0;
          if(!uni){let s=0;if(d.scanners){for(const k of Object.keys(d.scanners||{})){const grp=d.scanners[k]||{};for(const sk of Object.keys(grp)){s+=(grp[sk]||[]).length||0;}}}else if(d.hits){s=(d.hits||[]).length;}uni=s;}
          this.scannerHub.universe=uni;
        }catch(e){console.warn('scanners fetch failed',e);this.scannerHub.data=null;this.scannerHub.error=e.message||'fetch failed'}
        finally{this.scannerHub.duration_ms=Math.round(performance.now()-_t0);this.scannerHub.last_run=new Date().toISOString();this.scannerHub.loading=false}
      },
      async triggerSelfLearn(){
        this.selfLearn.triggering=true;this.selfLearn.lastResult='';
        try{
          const r=await fetch('/api/v7/self-learn/trigger',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          const d=await r.json();
          this.selfLearn.lastResult=`Cycle: ${d.trades_analysed||0} trades, ${d.adjustments_applied||0} adjustments. Status: ${d.status}`;
          await this.fetchSelfLearnStatus();
        }catch(e){this.selfLearn.lastResult='Error: '+e.message}
        finally{this.selfLearn.triggering=false}
      },
      async evaluateAB(param){
        try{
          const r=await fetch(`/api/v7/self-learn/ab-evaluate?param=${encodeURIComponent(param)}`,{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          const d=await r.json();
          alert(`A/B ${param}: promoted=${d.promoted} — ${d.reason}`);
          await this.fetchABStatus();
        }catch(e){console.warn('ab-evaluate failed',e)}
      },
      async autoScheduleExperiments(){
        try{
          const r=await fetch('/api/v7/self-learn/auto-schedule-experiments',{method:'POST',headers:{'X-API-Key':window._apiKey||'dev-secret-local'}});
          if(!r.ok)throw new Error('status '+r.status);
          const d=await r.json();
          this.selfLearn.lastAutoSchedule=d;
          await this.fetchABStatus();
          alert(`Auto-schedule: ${d.total_proposed} experiment(s) proposed.`);
        }catch(e){console.warn('auto-schedule failed',e);alert('Auto-schedule failed: '+e.message)}
      },
    }}
    