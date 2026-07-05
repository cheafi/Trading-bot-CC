import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# Replace init
new_init = """      init(){
        this.tick();setInterval(()=>this.tick(),1000);
        this.fetchSignals();setInterval(()=>this.fetchSignals(),60000);
        this.fetchToday7();setInterval(()=>this.fetchToday7(),120000);
        if(!localStorage.getItem('cc_guide_seen')){this.tab='guide'}
      },"""

# Replace switchTab
new_switch = """      switchTab(t){
        this.tab=t;
        if(t==='today'){this.fetchToday7();}
        if(t==='signals'){this.fetchSignals();}
      },"""

# Find and replace the init()
res1 = re.sub(
    r"\s*init\(\)\{([\s\S]*?)this\.tab='guide'\}\s*\},", "\n" + new_init, text
)

# Find and replace switchTab
res2 = re.sub(r"\s*switchTab\(t\)\{([\s\S]*?)\} \},", "\n" + new_switch, res1)


with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(res2)

print("Fixed init and switchTab")
