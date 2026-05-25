with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# Update tabs array
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

import re
text = re.sub(
    r"      tabs:\[.*?      \],", 
    new_tabs, 
    text, 
    flags=re.DOTALL
)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(text)
