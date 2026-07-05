import re

with open("src/api/templates/index.html", "r", encoding="utf-8") as f:
    text = f.read()

# We need to remove the first moreTabs array and keep only the Core 5 logic
# Wait, look at line 3183 it has:
#       moreTabs:[
#         {id:'ops',icon:'⚙️',label:'System Ops'},
#         {id:'ibkr',icon:'🏦',label:'IBKR Status'},
#         {id:'guide',icon:'📖',label:'Guide'},
#       ],
# and line 3188 has:
#       moreTabs:[
#         {id:'dossier',icon:'🔍',label:'Dossier'},
#         ...

# Let's remove the second one. 
pattern = r"      moreTabs:\[\n        \{id:'dossier'.*?      \],"
result = re.sub(pattern, "", text, flags=re.DOTALL)

with open("src/api/templates/index.html", "w", encoding="utf-8") as f:
    f.write(result)

print("Fixed moreTabs")
