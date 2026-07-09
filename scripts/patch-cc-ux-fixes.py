#!/usr/bin/env python3
"""One-shot CC UX fixes: export discoverability, loading perf, Chinese labels."""
from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "src/api/templates/index.html"

REPLACEMENTS: list[tuple[str, str]] = [
    # —— Export: prominent bilingual header button ——
    (
        """          <!-- ?? EXPORT REVIEW PDF ?? -->
          <button data-cc="export-review-pdf" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy"
            style="display:flex;align-items:center;gap:4px;padding:3px 10px;border-radius:6px;font-size:10px;font-weight:700;border:1px solid var(--bd2);background:var(--s2);color:var(--t1);cursor:pointer;letter-spacing:.3px"
            title="One-click review PDF ? issues page + all surfaces snapshot for ChatGPT review">
            <span x-show="!exportReviewPdfBusy">??</span>
            <span x-show="exportReviewPdfBusy" class="spin"></span>
            <span x-text="exportReviewPdfBusy?'Exporting?':'Export review PDF'"></span>
          </button>""",
        """          <!-- EXPORT ALL PAGES -->
          <button data-cc="export-review-pdf" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy"
            style="display:flex;align-items:center;gap:4px;padding:4px 12px;border-radius:6px;font-size:10px;font-weight:700;border:1px solid var(--green);background:rgba(16,185,129,.12);color:var(--green);cursor:pointer;letter-spacing:.3px"
            title="一鍵匯出全介面 PDF — 問題頁 + 所有分頁快照 · One-click export all pages (issues + surfaces)">
            <span x-show="!exportReviewPdfBusy">📥</span>
            <span x-show="exportReviewPdfBusy" class="spin"></span>
            <span x-text="(typeof CCHelpers!=='undefined'&&CCHelpers.exportAllLabel)?CCHelpers.exportAllLabel(exportReviewPdfBusy):(exportReviewPdfBusy?'Exporting…':'Export All Pages')"></span>
          </button>""",
    ),
    (
        """        <button type="button" data-cc="export-review-pdf" class="btn-s text-[8px] ml-auto" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy" x-text="exportReviewPdfBusy?'Exporting?':'Export review PDF'"></button>""",
        """        <button type="button" data-cc="export-review-pdf" class="btn-s text-[8px] ml-auto" style="border-color:var(--green);color:var(--green)" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy" x-text="(typeof CCHelpers!=='undefined'&&CCHelpers.exportAllLabel)?CCHelpers.exportAllLabel(exportReviewPdfBusy):(exportReviewPdfBusy?'Exporting…':'Export All Pages')"></button>""",
    ),
    (
        """    <button type="button" data-cc="export-review-pdf-fab" class="cc-export-fab" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy" title="One-click review PDF ? issues + all surfaces">
      <span x-show="!exportReviewPdfBusy">??</span>
      <span x-show="exportReviewPdfBusy" class="spin"></span>
      <span x-text="exportReviewPdfBusy?'Exporting?':'Export all'"></span>
    </button>""",
        """    <button type="button" data-cc="export-review-pdf-fab" class="cc-export-fab" @click="exportReviewPdfClick()" :disabled="exportReviewPdfBusy" title="一鍵匯出全介面 · Export all pages (issues + surfaces PDF)">
      <span x-show="!exportReviewPdfBusy">📥</span>
      <span x-show="exportReviewPdfBusy" class="spin"></span>
      <span x-text="(typeof CCHelpers!=='undefined'&&CCHelpers.exportAllLabel)?CCHelpers.exportAllLabel(exportReviewPdfBusy):(exportReviewPdfBusy?'Exporting…':'Export All Pages')"></span>
    </button>""",
    ),
    # —— Dashboard operator block labels ——
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--blue)">?? ? Now</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--blue)">現在 · Now</span>',
    ),
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--amber)">?? ? Why</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--amber)">原因 · Why</span>',
    ),
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--green)">?? ? Allowed</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--green)">允許 · Allowed</span>',
    ),
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--red)">?? ? Blocked</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--red)">禁止 · Blocked</span>',
    ),
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--purple)">VALID CANDIDATES</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--purple)">有效候選 · Valid</span>',
    ),
    (
        '<span class="font-bold uppercase mr-1" style="color:var(--blue)">??? ? Next</span>',
        '<span class="font-bold uppercase mr-1" style="color:var(--blue)">下一步 · Next</span>',
    ),
    # —— Header branding ——
    (
        '<div class="text-base font-bold text-white">CC ? Clarity Console</div>',
        '<div class="text-base font-bold text-white">CC · 清晰控制台 · Clarity Console</div>',
    ),
    (
        '<div class="text-xs mono" style="color:var(--t3)">regime-aware ? decision-grade ? auditable</div>',
        '<div class="text-xs mono" style="color:var(--t3)">體制感知 · 決策級 · 可稽核 · regime-aware · decision-grade · auditable</div>',
    ),
    # —— Export toast messages ——
    (
        "this.showExportToast('Preparing PDF?');",
        "this.showExportToast('準備匯出 PDF… · Preparing PDF…');",
    ),
    (
        "this.showExportToast('Downloaded '+(res.filename||'cc-review.pdf'));",
        "this.showExportToast('已下載 · Downloaded '+(res.filename||'cc-review.pdf'));",
    ),
    (
        "this.showExportToast('PDF export failed');",
        "this.showExportToast('PDF 匯出失敗 · PDF export failed');",
    ),
    (
        "this.showExportToast('PDF export unavailable');",
        "this.showExportToast('PDF 匯出不可用 · PDF export unavailable');",
    ),
    # —— today7 loading state ——
    (
        "today7:{regime:null,top_ranked:[]",
        "today7:{loading:false,regime:null,top_ranked:[]",
    ),
    (
        """      _ccRefreshInflight:{},
      ccStarred:""",
        """      _ccEtagStore:{},
      _ccTodayBodyCache:null,
      _ccRefreshInflight:{},
      ccStarred:""",
    ),
    (
        """        this._hydrateReplayState();
        if(typeof window!=='undefined':""",
        """        this._hydrateReplayState();
        this.hydrateToday7FromCache();
        if(this.today7.regime) this.today7.loading=false;
        else if(!this.replayModeActive()) this.today7.loading=true;
        if(typeof window!=='undefined':""",
    ),
    (
        """        this.hydrateRankedFromCache();
        this.hydrateToday7FromCache();
        this.hydrateScannersFromCache();""",
        """        this.hydrateRankedFromCache();
        this.hydrateScannersFromCache();""",
    ),
    # —— Loading skeleton ——
    (
        """      <div x-show="tab==='today'" data-cc="today-dashboard-body">

      <!-- ?? Operator block""",
        """      <div x-show="tab==='today'" data-cc="today-dashboard-body">

      <div x-show="today7.loading && !today7.regime" class="card card-p m-3 p-6 text-center" style="color:var(--t3)">
        <div class="spin" style="margin:0 auto 12px;width:24px;height:24px;border:2px solid var(--bd2);border-top-color:var(--green);border-radius:50%"></div>
        <div class="text-[11px] font-bold text-white">載入看板中 · Loading dashboard…</div>
        <div class="text-[9px] mt-1">快取快照會先顯示 · cached snapshot shown when available</div>
      </div>

      <div x-show="!today7.loading || today7.regime">

      <!-- Operator block""",
    ),
]

CC_FETCH_OLD = """      async ccFetch(url, opts={}){
        const replayUrl=this.ccReplayUrl(url);
        if(opts.json||opts.normalize) return this.ccFetchJson(replayUrl, opts);
        const tries=opts.retries??3;
        const backoff=opts.backoff??700;
        const timeoutMs=opts.timeoutMs??0;
        for(let i=0;i<tries;i++){
          try{
            const init={...(opts.init||{})};
            const extSignal=init.signal;
            if(timeoutMs>0||extSignal){
              const ctrl=new AbortController();
              init.signal=ctrl.signal;
              let timer=null;
              if(timeoutMs>0) timer=setTimeout(()=>ctrl.abort(),timeoutMs);
              if(extSignal) extSignal.addEventListener('abort',()=>ctrl.abort(),{once:true});
              try{
                const r=await fetch(replayUrl, init);
                if(timer) clearTimeout(timer);
                if((r.status===503||r.status===502)&&i<tries-1){
                  await new Promise(res=>setTimeout(res,backoff*(i+1)));
                  continue;
                }
                return r;
              }catch(e){
                clearTimeout(timer);
                if(i===tries-1) throw e;
              }
            }else{
              const r=await fetch(replayUrl, init);
              if((r.status===503||r.status===502)&&i<tries-1){
                await new Promise(res=>setTimeout(res,backoff*(i+1)));
                continue;
              }
              return r;
            }
          }catch(e){
            if(i===tries-1) throw e;
            await new Promise(res=>setTimeout(res,backoff*(i+1)));
          }
        }
        return null;
      },"""

CC_FETCH_NEW = """      async ccFetch(url, opts={}){
        const replayUrl=this.ccReplayUrl(url);
        if(opts.json||opts.normalize) return this.ccFetchJson(replayUrl, opts);
        const tries=opts.retries??3;
        const backoff=opts.backoff??700;
        const timeoutMs=opts.timeoutMs??0;
        const method=String((opts.init||{}).method||'GET').toUpperCase();
        const etagKey=replayUrl.split('?')[0];
        const cacheable=method==='GET'&&(/\\/api\\/v7\\/today$/.test(etagKey)||/\\/api\\/ops\\/cc-header/.test(etagKey));
        for(let i=0;i<tries;i++){
          try{
            const init={...(opts.init||{})};
            const hdrs={...(init.headers||{})};
            if(cacheable&&this._ccEtagStore[etagKey]) hdrs['If-None-Match']=this._ccEtagStore[etagKey];
            init.headers=hdrs;
            const extSignal=init.signal;
            if(timeoutMs>0||extSignal){
              const ctrl=new AbortController();
              init.signal=ctrl.signal;
              let timer=null;
              if(timeoutMs>0) timer=setTimeout(()=>ctrl.abort(),timeoutMs);
              if(extSignal) extSignal.addEventListener('abort',()=>ctrl.abort(),{once:true});
              try{
                const r=await fetch(replayUrl, init);
                if(timer) clearTimeout(timer);
                if(r.status===304&&cacheable){r.notModified=true;return r;}
                const etag=r.headers.get('ETag');
                if(etag&&cacheable&&r.ok) this._ccEtagStore[etagKey]=etag;
                if((r.status===503||r.status===502)&&i<tries-1){
                  await new Promise(res=>setTimeout(res,backoff*(i+1)));
                  continue;
                }
                return r;
              }catch(e){
                clearTimeout(timer);
                if(i===tries-1) throw e;
              }
            }else{
              const r=await fetch(replayUrl, init);
              if(r.status===304&&cacheable){r.notModified=true;return r;}
              const etag=r.headers.get('ETag');
              if(etag&&cacheable&&r.ok) this._ccEtagStore[etagKey]=etag;
              if((r.status===503||r.status===502)&&i<tries-1){
                await new Promise(res=>setTimeout(res,backoff*(i+1)));
                continue;
              }
              return r;
            }
          }catch(e){
            if(i===tries-1) throw e;
            await new Promise(res=>setTimeout(res,backoff*(i+1)));
          }
        }
        return null;
      },"""

FETCH_TODAY_OLD = re.compile(
    r"async _fetchToday7Core\(opts=\{\}\)\{\s*try\{const r=await this\.ccFetch\('/api/v7/today'"
)

FETCH_TODAY_INJECT = """async _fetchToday7Core(opts={}){
        if(!opts.force&&!opts.refresh&&this.today7.regime) this.today7.loading=false;
        else if(!this.today7.regime) this.today7.loading=true;
        try{
          const r=await this.ccFetch('/api/v7/today'"""

HYDRATE_TAIL = """          this.applyPulseToMarketStrip(this.today7.pulse);
        }catch(err){console.warn('today7 cache hydrate failed',err)}
      },"""

HYDRATE_TAIL_NEW = """          this._ccTodayBodyCache=d;
          this.applyPulseToMarketStrip(this.today7.pulse);
          this.today7.loading=false;
        }catch(err){console.warn('today7 cache hydrate failed',err)}
      },"""

QUANT_BLOCK_OLD = """          try{
            const qa=await this.ccFetchJson('/api/v7/quant/sleeve-allocation',{tab:'today',retries:1,backoff:400});
            if(qa.ok)this.today7.quant_alloc=qa.data;
          }catch(e){console.warn('quant sleeve-allocation',e)}
        }catch(e){console.warn('v7/today fetch failed',e);"""

QUANT_BLOCK_NEW = """          setTimeout(async()=>{
            try{
              const qa=await this.ccFetchJson('/api/v7/quant/sleeve-allocation',{tab:'today',retries:1,backoff:400});
              if(qa.ok)this.today7.quant_alloc=qa.data;
            }catch(e){console.warn('quant sleeve-allocation',e)}
          },0);
          this.today7.loading=false;
        }catch(e){console.warn('v7/today fetch failed',e);this.today7.trust={...(this.today7.trust||{}),stale:true,reason:String(e.message||e).slice(0,140)};this.hydrateToday7FromCache();this.today7.loading=false;}"""


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    n = 0
    for old, new in REPLACEMENTS:
        if old not in text:
            print("skip:", old[:55].replace("\n", " "))
            continue
        text = text.replace(old, new, 1)
        n += 1
        print("ok:", old[:55].replace("\n", " "))

    if CC_FETCH_OLD in text:
        text = text.replace(CC_FETCH_OLD, CC_FETCH_NEW, 1)
        n += 1
        print("ok: ccFetch ETag")

    if FETCH_TODAY_OLD.search(text) and "r.notModified" not in text:
        text = FETCH_TODAY_OLD.sub(FETCH_TODAY_INJECT, text, count=1)
        text = text.replace(
            "const d=await r.json();this.captureInstantDegradedBanner(d);",
            "if(r&&r.notModified&&this._ccTodayBodyCache){this.captureInstantDegradedBanner(this._ccTodayBodyCache);this.today7.loading=false;return;}if(!r||!r.ok)throw new Error('HTTP '+(r?r.status:'fail'));const d=await r.json();this._ccTodayBodyCache=d;this.captureInstantDegradedBanner(d);",
            1,
        )
        n += 1
        print("ok: fetchToday7 304 + cache")

    if QUANT_BLOCK_OLD in text:
        text = text.replace(QUANT_BLOCK_OLD, QUANT_BLOCK_NEW, 1)
        n += 1
        print("ok: defer quant sleeve")

    if HYDRATE_TAIL in text and "_ccTodayBodyCache=d" not in text:
        text = text.replace(HYDRATE_TAIL, HYDRATE_TAIL_NEW, 1)
        n += 1
        print("ok: hydrateToday7FromCache")

    if "end today-dashboard-loaded" not in text and "end today-dashboard-body" in text:
        text = text.replace(
            "      </div><!-- end today-dashboard-body -->",
            "      </div><!-- end today-dashboard-loaded -->\n      </div><!-- end today-dashboard-body -->",
            1,
        )
        n += 1
        print("ok: close loading wrapper")

  # Tab labels (regex)
    tab_map = {
        r"\{id:'guide',icon:'[^']*',label:'Guide'\}": "{id:'guide',icon:'📖',label:'Guide · 指南'}",
        r"\{id:'today',icon:'[^']*',label:'Dashboard'\}": "{id:'today',icon:'🎯',label:'Dashboard · 看板'}",
        r"\{id:'signals',icon:'[^']*',label:'Playbook'\}": "{id:'signals',icon:'📋',label:'Playbook · 候選'}",
        r"\{id:'scanners',icon:'[^']*',label:'Discovery'\}": "{id:'scanners',icon:'🔬',label:'Discovery · 掃描'}",
        r"\{id:'funds',icon:'[^']*',label:'Funds'\}": "{id:'funds',icon:'💼',label:'Funds · 策略'}",
        r"\{id:'flow',icon:'[^']*',label:'Flow'\}": "{id:'flow',icon:'💧',label:'Flow · 流量'}",
        r"\{id:'notrade',icon:'[^']*',label:'Rejections'\}": "{id:'notrade',icon:'🚫',label:'Rejections · 拒絕'}",
        r"\{id:'ops',icon:'[^']*',label:'Ops'\}": "{id:'ops',icon:'⚙️',label:'Ops · 運行'}",
        r"\{id:'ibkr',icon:'[^']*',label:'IBKR'\}": "{id:'ibkr',icon:'⚡',label:'IBKR · 券商'}",
        r"\{id:'stratlab',icon:'[^']*',label:'Strategy Lab'\}": "{id:'stratlab',icon:'📊',label:'Strategy Lab · 策略實驗'}",
    }
    for pattern, repl in tab_map.items():
        new_text, count = re.subn(pattern, repl, text, count=1)
        if count:
            text = new_text
            n += 1
            print("ok: tab", repl.split("label:")[1][:20])

    INDEX.write_text(text, encoding="utf-8")
    text.encode("utf-8")
    print(f"done — {n} patches")


if __name__ == "__main__":
    main()
