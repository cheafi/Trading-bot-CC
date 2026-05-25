import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# Try a tight regex to replace init() and switchTab()

init_pattern = r"\s*init\(\)\{([\s\S]*?)this\.tab='guide'\}\s*\},\n"
switch_pattern = r"\s*switchTab\(t\)\{([\s\S]*?)catch\(\(\)=>\{\}\)\}\},\n"

new_init = """      init(){
        this.tick();setInterval(()=>this.tick(),1000);
        this.fetchSignals();setInterval(()=>this.fetchSignals(),60000);
        this.fetchToday7();setInterval(()=>this.fetchToday7(),120000);
        if(!localStorage.getItem('cc_guide_seen')){this.tab='guide'}
      },
"""

new_switch = """      switchTab(t){
        this.tab=t;
        if(t==='today'){this.fetchToday7();}
        if(t==='signals'){this.fetchSignals();}
        if(t==='scanners'){this.fetchScanners();}
        if(t==='portfolio'){this.fetchPortfolio();}
        if(t==='dossier'){this.fetchDossier();}
      },
"""

text = re.sub(init_pattern, "\n" + new_init, text)
text = re.sub(switch_pattern, "\n" + new_switch, text)

# Just to be safe, if regex failed because of comma positioning etc:
if "fetchHealth()" in text and "switchTab" in text:
    # let's just do a string replace on switchTab directly since we know exactly what it looks like roughly
    pass

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

print("done")
