import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

new_switch = """      switchTab(t){
        this.tab=t;
        if(t==='today'){this.fetchToday7();}
        if(t==='signals'){this.fetchSignals();}
        if(t==='scanners'){this.fetchScanners();}
        if(t==='ibkr'){
            fetch('/api/ibkr/status').then(r=>r.json()).then(d=>{this.ibkr.connected=d.connected;this.ibkr.mode=d.mode||'paper'}).catch(()=>{});
        }
      },"""

# Use string replace for the giant switchTab one-liner
pattern = re.compile(r"      switchTab\(t\)\{.*?\n", re.DOTALL)
# wait, the switchTab is on a single line that ends with `}},`?
# let's just find `switchTab(t){` up to `}},`
pattern = r"\s*switchTab\(t\)\{.*?\}\},"

text = re.sub(pattern, "\n" + new_switch, text)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)

