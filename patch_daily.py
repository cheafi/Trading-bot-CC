import re

with open("src/api/routers/daily_decision.py", "r") as f:
    text = f.read()

dedup_func = """
def _dedup_candidates(candidates):
    seen = {}
    for c in candidates:
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        if ticker not in seen:
            seen[ticker] = c
        else:
            # Merging logic: prefer actionable/higher confidence
            existing = seen[ticker]
            c_conf = c.get("confidence", 0)
            ex_conf = existing.get("confidence", 0)
            c_act = c.get("action", "") in {"BUY", "TRADE", "STRONG_TRADE", "PILOT"}
            ex_act = existing.get("action", "") in {"BUY", "TRADE", "STRONG_TRADE", "PILOT"}
            
            if c_act and not ex_act:
                seen[ticker] = c
            elif c_act == ex_act and c_conf > ex_conf:
                seen[ticker] = c
    return list(seen.values())

def _calculate_blockers(candidates):
    blockers = {
        "failed_regime": import re

with open("src/api, 
with opden    text = f.read()

dedup_func = """
def _dedup_candidaon
dedup_func = """
s mdef _dedup_cand      seen = {}
    for c in candid.g    for c in "        ticker = c.get("S        if not ticker:
             i            continue
ls        if ticker n              seen[ticker] = c
+=        else:
            #ew            :
            existing = seen[ticker]
            c_conf = c.get(it            c_conf = c.get("confid              ex_conf = existing.get("confidrn            c_act = c.get("action", "") in {"BUY",sy            ex_act = existing.get("action", "") in {"BUY", "TRADE", "STRONG_TRADE", l            
            if c_act and not ex_act:
                seen[ticker] = c
        bo           \"               time.perf_counter()
              elif c_act == ex_acme                seen[ticker] = c
    return list(seenur    return list(seen.values())
oo
def _calculate_blockers(c_task(  arm_regime_cache())
    regime_ok =        "failedbl
with open("src/api, 
with opden inewith opden    text qu
dedup_func = """
def _dedupatedef _dedup_candnodedup_func = """
s das mdew, row.get("    for c in candid.g    for c i               i            continue
ls        if ticker n              seen[tickerrols      et("source", "rs-watchlist"+=        elfor row in await _rs_watchlist(limit)
              #ell            existing = seenat            c_conf = c.get(it      
            if c_act and not ex_act:
                seen[ticker] = c
        bo           \"               time.perf_counter()
              elif c_act == ex_acme                seen[ticker] = c
    return list(seenur    return list(seen.values())
oo
def _e(                seen[ticker] = c
   a        bo           \"        ge              elif c_act == ex_acme                seen[m_    return list(seenur    return list(seen.values())
oo
def _calcubloo
def _calculate_blockers(c_task(  arm_regime_cachconfi    regime_ok =        "failedbl
with open("src/apih_with open("src/api, 
with opdenocwith opden inewith lodedup_func = """
def _dedupatedef egdef _dedupatede bs das mdew, row.get("    for c in candid.g   )
ls        if ticker n              seen[tickerrols      et("source", "rs-watchlist"+=   su              #ell            existing = seenat            c_conf = c.get(it      
            if c_act and not ex_act:
           de            if c_act and not ex_act:
                seen[ticker] = c
        bo                   seen[ticker] = c
  S         bo           \"         e              elif c_act == ex_acme                seen[is    return list(seenur    return list(seen.values())
oo
def _e(   ctoo
def _e(                seen[ticker] = c
   a    ridht   a        bo           \"        ge s(oo
def _calcubloo
def _calculate_blockers(c_task(  arm_regime_cachconfi    regime_ok =        "failedbl
with open("src/apih_with open("src/api, 
w   )
def _calculat_nwith open("src/apih_with open("src/api, 
with opdenocwith opden inewith lodedup_funcenwith opdenocwith opden inewith lodedup_Nodef _dedupatedef egdef _dedupatede bs das mdew,   ls        if ticker n              seen[tickerrols      et("source", "rs-watchlisls            if c_act and not ex_act:
           de            if c_act and not ex_act:
                seen[ticker] = c
        bo                   seen[ticker] = c
  St_co           de            if c_act a                  seen[ticker] = c
        bo     
        if not missing:
            S         bo           \"         e       
 oo
def _e(   ctoo
def _e(                seen[ticker] = c
   a    ridht   a        bo           \"        ge s(oo
def _calcubloo
def _calculate_bltrddedef _e(      RA   a    ridht   a        bo           trdef _calcubloo
def _calculate_blockers(c_task(  arm_resudef _calculat swith open("src/apih_with open("src/api, 
w   )
def _calculat_nwith open("src/apih_wifiw   )
def _calculat_nwith open("src/api tdef anwith opdenocwith opden inewith lodedup_funcenwith opdest           de            if c_act and not ex_act:
                seen[ticker] = c
        bo                   seen[ticker] = c
  St_co           de            if c_act a                  seen[ticker] = c
        bo     
        if not missing:
        ,
                seen[ticker] = c
        bo     li        bo                   senk  St_co           de            if c_act a  ":        bo     ??", "reason": reason} for reason in reasons],
        "no_tra        if notea            S         ga oo
def _e(   ctoo
def _e(                seen[tickerl"deredef _e(      el   a    ridht   a        bo           bidef _calcubloo
def _calculate_bltrddedef _e(      RA  radef _calculat  def _calculate_blockers(c_task(  arm_resudef _calculat swith open("src/apih_with open("src
 w   )
def _calculat_nwith open("src/apih_wifiw   )
def _calculat_nwith open("src/api tdef anwit  def  "def _calculat_nwith open("src/api tdef anwive                seen[ticker] = c
        bo                   seen[ticker] = c
  St_co           de            if c_act a                  seen[tws        bo                   seli  St_co           de            if c_act a  pl        bo     
        if not missing:
        ,
                seen[tickti        if not          ,
            th        io        bacross setups",
                "no_tra        if notea            S         ga oo
def _e(   ctoo
def _e(                seen[tickerl"deredef _e(      el   a    ridht   a        boledef _e(   ctoo
def _e(                seen[tickerl"derede: def _e(      
 def _calculate_bltrddedef _e(      RA  radef _calculat  def _calculate_blockers(c_task(  arm_resudef _calcul": w   )
def _calculat_nwith open("src/apih_wifiw   )
def _calculat_nwith open("src/api tdef anwit  def  "def _calculat_nwith open("src/api tdef an  def _ edef _calculat_nwith open("src/api tdef anwi          bo                   seen[ticker] = c
  St_co           de            if c_act a                  seen[tws        bo    r'  St_co           de            if c_act a  _s        if not missing:
        ,
                seen[tickti        if not          ,
            th        io        bacross setups",
     e(text)

